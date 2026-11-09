"""
automation.py - incremental sales load: MySQL ecommerce_oltp -> fact_sales.   Task N4 (Eng. Nouran).

Same design as the version that passed 28 integration checks on 21-Oct-2026 (old Olist repository), adapted to the
new tables (data dictionary v4.1, sheets OLTP_MySQL and fact_sales):
  * read only orders with orders.loaded_at > watermark of pipeline 'orders_incremental'
    (loaded_at = when the row reached MySQL; a day that is generated late still has a new loaded_at, while its
     order_purchase_ts is old - so filtering on the purchase time would skip it. Changed 3-Nov-2026 after the review.)
  * rows loaded during the current second are left for the next run (loaded_at < NOW()): loaded_at has a precision
    of one second, so a row written in the same second as the read could otherwise fall behind the new watermark
  * upsert dim_customer, then insert fact_sales ON CONFLICT (order_id, item_no) DO NOTHING
  * product_key = dim_product row with the same product_code as MySQL products.product_code
  * facts, dimensions and the etl_state row are committed together; any error -> rollback, 'failed' row, re-raise
Run by hand:  python automation.py          In Airflow: sales_daily_dag -> run_etl()
"""
import logging

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

from etl_common import get_watermark, record_failure, record_run
from mysqlconnect import get_mysql_engine
from postgresqlconnect import get_postgres_dw_connection

PIPELINE = "orders_incremental"
log = logging.getLogger(PIPELINE)

ALLOWED_STATUS = {"delivered", "canceled", "returned"}
ALLOWED_PAYMENT = {"cash_on_delivery", "card", "installments", "wallet"}


def extract(engine, watermark):
    """New orders + items + all customers (3000 rows, cheap)."""
    q = text("""
        SELECT o.order_id, oi.item_no, o.customer_id, o.order_purchase_ts,
               o.order_status, o.payment_method,
               p.product_code, oi.quantity, oi.unit_price_egp, o.loaded_at
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN products p     ON p.product_id = oi.product_id
        WHERE o.loaded_at > :wm
          AND o.loaded_at < NOW()
        ORDER BY o.loaded_at, o.order_id, oi.item_no
    """)
    items = pd.read_sql(q, engine, params={"wm": watermark})
    if items.empty:
        return {"items": items, "customers": items, "orders_count": 0, "max_ts": watermark}

    customers = pd.read_sql(
        text("SELECT customer_id, governorate, city, signup_date FROM customers"), engine
    )
    return {
        "items": items,
        "customers": customers,
        "orders_count": int(items["order_id"].nunique()),
        "max_ts": pd.to_datetime(items["loaded_at"]).max().to_pydatetime(),
    }


def validate(items):
    """Keep rows with quantity>0, unit_price>0, allowed status/payment."""
    if items.empty:
        return items, items
    mask = (
        (items["quantity"] > 0)
        & (items["unit_price_egp"] > 0)
        & (items["order_status"].isin(ALLOWED_STATUS))
        & (items["payment_method"].isin(ALLOWED_PAYMENT))
    )
    return items[mask].copy(), items[~mask].copy()


def transform(items):
    """date_key = YYYYMMDD, batch_id = YYYY-MM-DD, trimmed lower-case status/payment."""
    if items.empty:
        return items
    df = items.copy()
    df["order_status"] = df["order_status"].astype(str).str.strip().str.lower()
    df["payment_method"] = df["payment_method"].astype(str).str.strip().str.lower()
    df["order_purchase_ts"] = pd.to_datetime(df["order_purchase_ts"])
    df["date_key"] = df["order_purchase_ts"].dt.strftime("%Y%m%d").astype(int)
    df["batch_id"] = df["order_purchase_ts"].dt.strftime("%Y-%m-%d")
    return df


def load(pg_conn, customers, facts):
    """Upsert dim_customer, then bulk insert fact_sales with key lookups."""
    if facts.empty:
        return 0, 0.0

    with pg_conn.cursor() as cur:
        for _, row in customers.iterrows():
            cur.execute(
                """INSERT INTO dim_customer (customer_id, governorate, city, signup_date)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (customer_id) DO UPDATE SET
                       governorate = EXCLUDED.governorate,
                       city        = EXCLUDED.city,
                       signup_date = EXCLUDED.signup_date""",
                (row["customer_id"], row["governorate"], row["city"], row["signup_date"]),
            )

        cur.execute("SELECT customer_id, customer_key FROM dim_customer")
        cust_map = dict(cur.fetchall())
        cur.execute("SELECT product_code, product_key FROM dim_product")
        prod_map = dict(cur.fetchall())

        rows, missing = [], []
        for _, row in facts.iterrows():
            ck = cust_map.get(row["customer_id"])
            pk = prod_map.get(row["product_code"])
            if ck is None:
                missing.append(("customer", row["customer_id"])); continue
            if pk is None:
                missing.append(("product", row["product_code"])); continue
            rows.append((
                row["order_id"], int(row["item_no"]), int(row["date_key"]),
                int(ck), int(pk),
                row["order_purchase_ts"].to_pydatetime(),
                row["order_status"], row["payment_method"],
                int(row["quantity"]), float(row["unit_price_egp"]),
                row["batch_id"],
            ))
        if missing:
            raise ValueError(f"Missing dimensions (first 5): {missing[:5]}")

        inserted_rows = []
        for i in range(0, len(rows), 500):
            execute_values(cur, """
                INSERT INTO fact_sales
                  (order_id, item_no, date_key, customer_key, product_key,
                   order_purchase_ts, order_status, payment_method,
                   quantity, unit_price_egp, batch_id)
                VALUES %s
                ON CONFLICT (order_id, item_no) DO NOTHING
                RETURNING line_total_egp
            """, rows[i:i+500], page_size=500)
            inserted_rows.extend(cur.fetchall())

    inserted = len(inserted_rows)
    checksum = float(sum(r[0] for r in inserted_rows)) if inserted_rows else 0.0
    return inserted, checksum


def run_etl():
    """Orchestration (same order as the tested version)."""
    engine = get_mysql_engine()
    pg_conn = get_postgres_dw_connection()
    try:
        watermark = get_watermark(pg_conn, PIPELINE)
        data = extract(engine, watermark)
        if data["orders_count"] == 0:
            record_run(pg_conn, PIPELINE, "no_data", message="No new orders in MySQL")
            pg_conn.commit()
            return {"status": "no_data", "rows_in": 0, "rows_out": 0}
        valid, rejected = validate(data["items"])
        facts = transform(valid)
        rows_out, checksum = load(pg_conn, data["customers"], facts)
        if facts.empty:
            batch_id = None                       # every item was rejected: the run is recorded, nothing loaded
        else:
            days = sorted(facts["batch_id"].unique())
            batch_id = days[0] if len(days) == 1 else f"{days[0]}..{days[-1]}"
        record_run(pg_conn, PIPELINE, "success", data["max_ts"], batch_id, len(data["items"]), rows_out, checksum,
                   f"{data['orders_count']} new orders; {len(rejected)} items rejected")
        pg_conn.commit()
        return {"status": "success", "rows_in": len(data["items"]), "rows_out": rows_out}
    except Exception as error:
        pg_conn.rollback()
        record_failure(pg_conn, PIPELINE, error)
        log.error("Sales load failed: %s", error)
        raise
    finally:
        pg_conn.close()
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run_etl())