"""
quality_checks.py - checks run as the last task of each DAG.   Tasks N5 / N6.

Every check raises an error when it fails, so the Airflow task turns FAILED
(data dictionary v4.1, Star_Schema 'Load checks').
"""
import logging
from datetime import datetime

log = logging.getLogger(__name__)


def _to_date_key(snapshot_date):
    if isinstance(snapshot_date, str):
        return int(snapshot_date.replace("-", ""))
    if hasattr(snapshot_date, "strftime"):
        return int(snapshot_date.strftime("%Y%m%d"))
    return int(snapshot_date)


def _batch_range(batch_id):
    """Handles 'YYYY-MM-DD' and 'YYYY-MM-DD..YYYY-MM-DD'."""
    if ".." in batch_id:
        start, end = batch_id.split("..", 1)
    else:
        start = end = batch_id
    return start, end


def check_prices(pg_conn, mongo_db, snapshot_date, sites=None):
    """Raise ValueError if any of the price-load checks fails.
    sites = the sites the DAG scrapes now (prices_daily_dag.SITES). A site the team stopped scraping on purpose
    (Jumia after 2-Nov-2026) is then not counted as a failure; None = check every site of the previous run."""
    dk = _to_date_key(snapshot_date)
    s = str(dk).zfill(8)
    dstr = f"{s[:4]}-{s[4:6]}-{s[6:8]}"

    with pg_conn.cursor() as cur:
        # (1) per-site offers today vs previous run
        cur.execute("""
            SELECT ds.site_code, COUNT(*)
            FROM fact_price_daily fp
            JOIN dim_site ds ON ds.site_key = fp.site_key
            WHERE fp.date_key = %s
            GROUP BY ds.site_code
        """, (dk,))
        today_by_site = dict(cur.fetchall())

        cur.execute("SELECT MAX(date_key) FROM fact_price_daily WHERE date_key < %s", (dk,))
        prev_dk = cur.fetchone()[0]

        if prev_dk is not None:
            cur.execute("""
                SELECT ds.site_code, COUNT(*)
                FROM fact_price_daily fp
                JOIN dim_site ds ON ds.site_key = fp.site_key
                WHERE fp.date_key = %s
                GROUP BY ds.site_code
            """, (prev_dk,))
            prev_by_site = dict(cur.fetchall())
            # loop over the PREVIOUS run's sites: a site that returned nothing today counts as 0 offers
            for site, n_prev in prev_by_site.items():
                if sites is not None and site not in sites:
                    continue                       # retired on purpose, e.g. jumia (HTTP 403 since 2-Nov-2026)
                n_today = today_by_site.get(site, 0)
                if n_prev > 0 and n_today < 0.70 * n_prev:
                    raise ValueError(
                        f"Price check failed: {site} has {n_today} offers on {dstr} vs "
                        f"{n_prev} on previous run (date_key={prev_dk}); 70% threshold = {0.70*n_prev:.0f}"
                    )

        # (2) fact_price_daily rows = rows inserted by all successful runs of the day
        #     (a day can be loaded by more than one run: each run inserts only the offers that are new)
        cur.execute("""
            SELECT SUM(rows_out) FROM etl_state
            WHERE pipeline='prices_daily' AND status='success' AND batch_id=%s
        """, (dstr,))
        row = cur.fetchone()
        expected = int(row[0]) if row and row[0] is not None else None

        cur.execute("SELECT COUNT(*) FROM fact_price_daily WHERE date_key = %s", (dk,))
        actual = cur.fetchone()[0]
        if actual == 0:
            raise ValueError(f"Price check failed: no rows in fact_price_daily for {dstr}")
        if expected is not None and expected != actual:
            raise ValueError(
                f"Price check failed: fact_price_daily has {actual} rows for {dstr}, "
                f"but the successful runs of etl_state inserted {expected}"
            )

        # (3) NULL keys and duplicates
        cur.execute("""
            SELECT COUNT(*) FROM fact_price_daily
            WHERE date_key = %s AND (product_key IS NULL OR site_key IS NULL OR site_product_id IS NULL)
        """, (dk,))
        nulls = cur.fetchone()[0]
        if nulls > 0:
            raise ValueError(f"Price check failed: {nulls} rows with NULL keys for {dstr}")

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT date_key, site_key, site_product_id
                FROM fact_price_daily WHERE date_key = %s
                GROUP BY date_key, site_key, site_product_id HAVING COUNT(*) > 1
            ) d
        """, (dk,))
        dups = cur.fetchone()[0]
        if dups > 0:
            raise ValueError(f"Price check failed: {dups} duplicate (date_key, site_key, site_product_id) on {dstr}")

        # (4) log matching quality: share of products on 2+ sites
        cur.execute("SELECT COUNT(DISTINCT product_key) FROM product_map")
        total_products = cur.fetchone()[0] or 0
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT product_key FROM product_map
                GROUP BY product_key HAVING COUNT(DISTINCT site_key) >= 2
            ) m
        """)
        multi_site = cur.fetchone()[0] or 0
        share = (100.0 * multi_site / total_products) if total_products else 0.0

    log.info("Price check OK for %s: %d rows, %d products, %d (%.1f%%) on 2+ sites",
             dstr, actual, total_products, multi_site, share)
    return {
        "date": dstr,
        "rows": actual,
        "products_total": total_products,
        "products_on_2plus_sites": multi_site,
        "share_2plus_pct": round(share, 2),
    }


def check_sales(pg_conn, mysql_engine, batch_id):
    """Raise ValueError if any of the sales-load checks fails."""
    import pandas as pd
    from sqlalchemy import text

    start_str, end_str = _batch_range(batch_id)

    # (1) MySQL side
    mysql_q = text("""
        SELECT COUNT(*) AS items_count,
               COALESCE(SUM(oi.quantity * oi.unit_price_egp), 0) AS total_egp
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE DATE(o.order_purchase_ts) BETWEEN :start AND :end
    """)
    mysql_df = pd.read_sql(mysql_q, mysql_engine, params={"start": start_str, "end": end_str})
    mysql_items = int(mysql_df["items_count"].iloc[0])
    mysql_egp = float(mysql_df["total_egp"].iloc[0])

    if mysql_items == 0:
        raise ValueError(
            f"Sales check failed: MySQL has no order items for {start_str}..{end_str} "
            f"(upstream generate/load step probably failed)"
        )

    # (2) PostgreSQL side
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(line_total_egp), 0)
            FROM fact_sales fs
            JOIN dim_date d ON d.date_key = fs.date_key
            WHERE d.full_date BETWEEN %s AND %s
        """, (start_str, end_str))
        pg_items, pg_egp = cur.fetchone()
    pg_items = int(pg_items)
    pg_egp = float(pg_egp)

    if pg_items != mysql_items:
        raise ValueError(
            f"Sales check failed: fact_sales has {pg_items} rows for {start_str}..{end_str}, "
            f"but MySQL has {mysql_items} order items"
        )
    if abs(pg_egp - mysql_egp) > 0.01:
        raise ValueError(
            f"Sales check failed: SUM(line_total_egp) in PostgreSQL = {pg_egp:.2f}, "
            f"but SUM(quantity*unit_price_egp) in MySQL = {mysql_egp:.2f} for {start_str}..{end_str}"
        )

    # (3) NULL keys
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fact_sales
            WHERE order_id IS NULL OR customer_key IS NULL OR product_key IS NULL OR date_key IS NULL
        """)
        nulls = cur.fetchone()[0]
    if nulls > 0:
        raise ValueError(f"Sales check failed: {nulls} rows with NULL keys in fact_sales")

    log.info("Sales check OK for %s..%s: %d rows, total_egp=%.2f",
             start_str, end_str, pg_items, pg_egp)
    return {
        "batch_id": f"{start_str}..{end_str}",
        "rows": pg_items,
        "total_egp": round(pg_egp, 2),
    }