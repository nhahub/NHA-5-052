"""
load_prices.py - daily price load: MongoDB catalog.offers -> fact_price_daily.   SKELETON - task N3 (Eng. Nouran), due 2-Nov.

One run loads every snapshot date newer than the watermark of pipeline 'prices_daily' (so the first run loads all
the days scraped since 27-Oct). For each date, in ONE transaction:
   read offers -> validate -> match (matching.py) -> upsert dim_product + product_map -> insert prices -> etl_state
Rules: ON CONFLICT (date_key, site_key, site_product_id) DO NOTHING (re-runs never duplicate);
       any error -> rollback, 'failed' row in etl_state, re-raise (Airflow marks the task FAILED and retries).
Run by hand:  python load_prices.py          In Airflow: prices_daily_dag -> run_prices()
"""
import logging

from etl_common import get_mongo_db, get_watermark, record_failure, record_run
from postgresqlconnect import get_postgres_dw_connection

PIPELINE = "prices_daily"
log = logging.getLogger(PIPELINE)


def new_snapshot_dates(mongo_db, watermark):
    """TODO N3: distinct snapshot_date values in catalog.offers greater than the watermark date, sorted."""
    raise NotImplementedError("TODO N3: new_snapshot_dates()")


def validate(offers):
    """TODO N3: keep offers with category in (phone, tv), sale_price > 0, a known site; return (valid, rejected)."""
    raise NotImplementedError("TODO N3: validate()")


def insert_prices(pg_conn, offers, run_id):
    """TODO N3: execute_values INSERT INTO fact_price_daily (...) ON CONFLICT DO NOTHING RETURNING sale_price_egp;
    return (rows_inserted, checksum = SUM(sale_price_egp))."""
    raise NotImplementedError("TODO N3: insert_prices()")


def run_prices():
    """Orchestration: one transaction per snapshot date. TODO N3: fill the loop body (steps in the module docstring)."""
    pg_conn = get_postgres_dw_connection()
    try:
        watermark = get_watermark(pg_conn, PIPELINE)
        dates = new_snapshot_dates(get_mongo_db(), watermark)
        if not dates:
            record_run(pg_conn, PIPELINE, "no_data", message="No new snapshot in MongoDB")
            pg_conn.commit()
            return {"status": "no_data"}
        for day in dates:
            raise NotImplementedError("TODO N3: read -> validate -> match -> upsert -> insert -> record_run -> commit")
        return {"status": "success", "dates": dates}
    except Exception as error:
        pg_conn.rollback()
        record_failure(pg_conn, PIPELINE, error)
        log.error("Price load failed: %s", error)
        raise
    finally:
        pg_conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run_prices())
