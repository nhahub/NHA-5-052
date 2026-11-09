"""
load_prices.py - daily price load: MongoDB catalog.offers -> fact_price_daily.   Task N3.
One run loads the watermark date again and every newer snapshot date (inserts are idempotent, so offers that arrive
later on the same day - e.g. a site scraped again after a failure - are still loaded).
Per date, in ONE transaction: read -> validate -> match -> upsert dim_product + product_map -> insert prices -> etl_state.
"""
import logging
from datetime import datetime, date

from psycopg2.extras import execute_values

from etl_common import get_mongo_db, get_watermark, record_failure, record_run
from postgresqlconnect import get_postgres_dw_connection
from matching import EXCLUDED_BRANDS, assign_keys, match_offers, read_csv, upsert_products_and_map

PIPELINE = "prices_daily"
log = logging.getLogger(PIPELINE)


def new_snapshot_dates(mongo_db, watermark):
    """Snapshot dates to load: the watermark date itself (late offers of that day) and every later date.
    Before the first successful run (watermark = 1900-01-01) this is every date in MongoDB."""
    wm_date = watermark.date() if isinstance(watermark, datetime) else watermark
    vals = mongo_db.offers.distinct("snapshot_date")
    out = []
    for v in vals:
        if not v:
            continue
        d = datetime.strptime(v, "%Y-%m-%d").date() if isinstance(v, str) else v
        if d >= wm_date:
            out.append(d)
    return sorted(out)


def validate(offers):
    ok, bad = [], []
    for o in offers:
        if o.get("category") not in ("phone", "tv"):
            bad.append((o, "category")); continue
        if (o.get("brand") or "").lower() in EXCLUDED_BRANDS:
            bad.append((o, "excluded brand")); continue
        try:
            p = float(o.get("sale_price"))
        except (TypeError, ValueError):
            bad.append((o, "sale_price")); continue
        if p <= 0:
            bad.append((o, "sale_price")); continue
        if not o.get("site"):
            bad.append((o, "site")); continue
        ok.append(o)
    return ok, bad


def insert_prices(pg_conn, offers, matches, run_id):
    by_key = {(o["site"], o["site_product_id"]): o for o in offers}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT site_code, site_key FROM dim_site")
        sites = dict(cur.fetchall())
        cur.execute("SELECT product_code, product_key FROM dim_product")
        prods = dict(cur.fetchall())

        rows = []
        for site, spid, pc, _method, _mk in matches:
            off = by_key.get((site, spid))
            if not off or pc is None:
                continue
            sk = sites.get(site)
            pk = prods.get(pc)
            if sk is None or pk is None:
                continue
            sd = off.get("snapshot_date")
            if isinstance(sd, str):
                date_key = int(sd.replace("-", ""))
            else:
                date_key = int(sd.strftime("%Y%m%d"))
            scraped = off.get("scraped_at")
            if isinstance(scraped, str):
                try:
                    scraped = datetime.fromisoformat(scraped.replace("Z", "+00:00"))
                except ValueError:
                    scraped = datetime.utcnow()
            rows.append((
                date_key, sk, spid, pk,
                float(off["sale_price"]),
                float(off["original_price"]) if off.get("original_price") else None,
                int(off["discount_pct"]) if off.get("discount_pct") is not None else None,
                bool(off.get("in_stock", True)),
                off.get("stock_text") or None,
                off.get("seller") or None,
                scraped,
                run_id,
            ))

        if not rows:
            return 0, 0.0

        sql = """
            INSERT INTO fact_price_daily
              (date_key, site_key, site_product_id, product_key, sale_price_egp,
               original_price_egp, discount_pct, in_stock, stock_text, seller, scraped_at, run_id)
            VALUES %s
            ON CONFLICT (date_key, site_key, site_product_id) DO NOTHING
            RETURNING sale_price_egp
        """
        returned = []
        page_size = 500
        for i in range(0, len(rows), page_size):
            execute_values(cur, sql, rows[i:i + page_size], page_size=page_size)
            returned.extend(cur.fetchall())
        return len(returned), float(sum(r[0] for r in returned)) if returned else 0.0


def run_prices():
    pg_conn = get_postgres_dw_connection()
    try:
        watermark = get_watermark(pg_conn, PIPELINE)
        mongo_db = get_mongo_db()
        dates = new_snapshot_dates(mongo_db, watermark)
        if not dates:
            record_run(pg_conn, PIPELINE, "no_data", message="No new snapshot in MongoDB")
            pg_conn.commit()
            return {"status": "no_data"}

        aliases = read_csv("brand_aliases.csv")
        suffixes = read_csv("model_suffixes.csv")
        manual = read_csv("manual_matches.csv")

        for day in dates:
            dstr = day.strftime("%Y-%m-%d")
            raw = list(mongo_db.offers.find({"snapshot_date": dstr}))
            assign_keys(raw, aliases, suffixes)          # brand + model_key for the whole day (5g rule needs it)

            ok, bad = validate(raw)
            # existing map
            with pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT ds.site_code, pm.site_product_id, dp.product_code, pm.match_method, pm.match_key
                    FROM product_map pm
                    JOIN dim_site ds ON ds.site_key = pm.site_key
                    JOIN dim_product dp ON dp.product_key = pm.product_key
                """)
                existing_map = {(s, sp): (pc, mm, mk) for s, sp, pc, mm, mk in cur.fetchall()}

            matches = match_offers(ok, existing_map, manual)

            unmatched_count = sum(1 for m in matches if m[2] is None)
            single_site = sum(1 for m in matches if m[3] == "new")
            run_id = record_run(pg_conn, PIPELINE, "success", watermark=datetime.combine(day, datetime.min.time()),
                                batch_id=dstr, rows_in=len(ok), rows_out=0, checksum=0.0,
                                message=f"{len(bad)} rejected, {unmatched_count} without product, "
                                        f"{single_site} single-site (no key)")
            upsert_products_and_map(pg_conn, matches, ok, day, {})
            inserted, checksum = insert_prices(pg_conn, ok, matches, run_id)
            with pg_conn.cursor() as cur:
                cur.execute("UPDATE etl_state SET rows_out=%s, checksum=%s WHERE run_id=%s",
                            (inserted, checksum, run_id))
            pg_conn.commit()
            log.info("%s -> %d offers, %d inserted, checksum=%.2f", dstr, len(ok), inserted, checksum)

        return {"status": "success", "dates": [d.isoformat() for d in dates]}
    except Exception as error:
        pg_conn.rollback()
        record_failure(pg_conn, PIPELINE, error)
        log.exception("Price load failed")
        raise
    finally:
        pg_conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run_prices())