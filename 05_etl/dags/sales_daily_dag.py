"""
sales_daily_dag - synthetic sales of the day -> MySQL -> warehouse.   Task N6 (Eng. Nouran).

  refresh reference data -> generate the day's orders (CSV) -> load them into MySQL -> incremental ETL to fact_sales
  -> quality check -> refresh the materialized view of report 6

The day: {{ ds }} = the start of the data interval = YESTERDAY for this daily DAG. Yesterday's orders are generated
from yesterday's market prices, which prices_daily_dag loaded at 06:00 yesterday. The check uses the same day.
Reference data (revised 3-Nov-2026 after the review): customers.csv is created once if missing; products.csv is
rebuilt every run from the products found on 2+ sites (ids stay stable: P + product_key) and loaded into MySQL,
so a fresh clone can run the DAG and new matched products start selling.
"""
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

if "/opt/airflow/scripts" not in sys.path:
    sys.path.insert(0, "/opt/airflow/scripts")

OLTP = "/opt/airflow/oltp"
default_args = {"owner": "Nouran", "retries": 3, "retry_delay": timedelta(minutes=10), "email_on_failure": False}


def _run(*args):
    subprocess.run([sys.executable, *args], check=True, cwd="/opt/airflow")


def _refresh_reference(**_):
    if not Path("/opt/airflow/data/sales/customers.csv").exists():
        _run(f"{OLTP}/generate_sales.py", "customers")
    _run(f"{OLTP}/generate_sales.py", "products")
    _run(f"{OLTP}/load_batch.py", "reference")


def _generate_orders(ds, **_):
    _run(f"{OLTP}/generate_sales.py", "orders", ds)


def _load_mysql(ds, **_):
    _run(f"{OLTP}/load_batch.py", "day", ds)


def _run_etl(**_):
    from automation import run_etl
    return run_etl()


def _quality_check(ds, **_):
    from mysqlconnect import get_mysql_engine
    from postgresqlconnect import get_postgres_dw_connection
    from quality_checks import check_sales
    pg_conn = get_postgres_dw_connection()
    engine = get_mysql_engine()
    try:
        return check_sales(pg_conn, engine, ds)
    finally:
        pg_conn.close()
        engine.dispose()


def _refresh_report_view(**_):
    from postgresqlconnect import get_postgres_dw_connection
    pg_conn = get_postgres_dw_connection()
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.mv_our_price_vs_market')")
            if cur.fetchone()[0] is None:
                return "mv_our_price_vs_market not created yet: run 04_analytics/scripts/analysis_queries.sql"
            cur.execute("REFRESH MATERIALIZED VIEW mv_our_price_vs_market")
        pg_conn.commit()
        return "refreshed"
    finally:
        pg_conn.close()


with DAG(
    dag_id="sales_daily_dag",
    default_args=default_args,
    description="Generate the day's synthetic orders, load MySQL, then load fact_sales incrementally",
    start_date=pendulum.datetime(2026, 10, 27, tz="Africa/Cairo"),
    schedule="0 8 * * *",          # 08:00 Cairo time, after prices_daily_dag (06:00)
    catchup=False,
    max_active_runs=1,
    tags=["module-05", "sales"],
) as dag:
    reference = PythonOperator(task_id="refresh_reference_data", python_callable=_refresh_reference)
    generate = PythonOperator(task_id="generate_orders_csv", python_callable=_generate_orders)
    load_mysql = PythonOperator(task_id="load_orders_mysql", python_callable=_load_mysql)
    etl = PythonOperator(task_id="extract_validate_transform_load", python_callable=_run_etl)
    check = PythonOperator(task_id="quality_check", python_callable=_quality_check)
    refresh = PythonOperator(task_id="refresh_report_view", python_callable=_refresh_report_view)

    reference >> generate >> load_mysql >> etl >> check >> refresh
