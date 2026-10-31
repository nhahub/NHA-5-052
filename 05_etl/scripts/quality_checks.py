"""
quality_checks.py - checks run as the last task of each DAG.   SKELETON - tasks N5 / N6 (Eng. Nouran), due 5-6 Nov.

Every check raises an error when it fails, so the Airflow task turns FAILED (data dictionary v4.1, Star_Schema 'Load checks').
"""


def check_prices(pg_conn, mongo_db, snapshot_date):
    """TODO N5:
       1. offers per site today >= 70% of the previous run (else a site changed or blocked us)
       2. rows in fact_price_daily for the day = valid offers of the day (from etl_state rows_out)
       3. no NULL product_key / site_key; no duplicate (date_key, site_key, site_product_id)
       4. log the share of products found on 2+ sites (matching quality)"""
    raise NotImplementedError("TODO N5: check_prices()")


def check_sales(pg_conn, mysql_engine, batch_id):
    """TODO N6:
       1. fact rows added = new order items in MySQL for the batch
       2. no NULL keys in fact_sales
       3. SUM(line_total_egp) in PostgreSQL = SUM(quantity * unit_price_egp) in MySQL for the batch"""
    raise NotImplementedError("TODO N6: check_sales()")
