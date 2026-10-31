"""
automation.py - incremental sales load: MySQL ecommerce_oltp -> fact_sales.   SKELETON - task N4 (Eng. Nouran), due 4-Nov.

Same design as the version that passed 28 integration checks on 21-Oct-2026 (old Olist repository), adapted to the
new tables (data dictionary v4.1, sheets OLTP_MySQL and fact_sales):
  * read only orders with order_purchase_ts > watermark of pipeline 'orders_incremental'
  * upsert dim_customer, then insert fact_sales ON CONFLICT (order_id, item_no) DO NOTHING
  * product_key = dim_product row with the same product_code as MySQL products.product_code
  * facts, dimensions and the etl_state row are committed together; any error -> rollback, 'failed' row, re-raise
Run by hand:  python automation.py          In Airflow: sales_daily_dag -> run_etl()
"""
import logging

from etl_common import get_watermark, record_failure, record_run
from mysqlconnect import get_mysql_engine
from postgresqlconnect import get_postgres_dw_connection

PIPELINE = "orders_incremental"
log = logging.getLogger(PIPELINE)


def extract(engine, watermark):
    """TODO N4: SELECT orders JOIN order_items JOIN products (product_code) WHERE order_purchase_ts > :wm,
    plus the customers of those orders. Return dict with items, customers, orders_count, max_ts."""
    raise NotImplementedError("TODO N4: extract()")


def validate(items):
    """TODO N4: quantity > 0, unit_price_egp > 0, status and payment in the allowed lists; return (valid, rejected)."""
    raise NotImplementedError("TODO N4: validate()")


def transform(items):
    """TODO N4: date_key = YYYYMMDD of order_purchase_ts; batch_id = 'YYYY-MM-DD'; trim / lower-case status and payment."""
    raise NotImplementedError("TODO N4: transform()")


def load(pg_conn, customers, facts):
    """TODO N4: upsert dim_customer; insert fact_sales through a temporary staging table with key lookups
    (customer_key, product_key); ON CONFLICT DO NOTHING RETURNING line_total_egp -> (rows_out, checksum).
    Fail if a product_code has no dim_product row."""
    raise NotImplementedError("TODO N4: load()")


def run_etl():
    """Orchestration (same order as the tested version). READY once the four functions above are done."""
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
