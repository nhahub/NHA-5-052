"""
sales_daily_dag - synthetic sales of the day -> MySQL -> warehouse.   SKELETON - task N6 (Eng. Nouran), due 6-Nov.

  generate the day's orders (CSV) -> load them into MySQL -> incremental ETL to fact_sales -> quality check
Runs after the price DAG, because our daily price is based on that day's market prices.
The DAG file is ready and loads in Airflow; the task functions are finished in tasks H5 / N4 / N6.
"""
import subprocess
import sys
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

if "/opt/airflow/scripts" not in sys.path:
    sys.path.insert(0, "/opt/airflow/scripts")

default_args = {"owner": "Nouran", "retries": 3, "retry_delay": timedelta(minutes=10), "email_on_failure": False}


def _generate_orders(ds, **_):
    # ds = the run date (YYYY-MM-DD); generate_sales.py and load_batch.py live in 01_oltp/scripts (mounted at /opt/airflow/oltp)
    subprocess.run([sys.executable, "/opt/airflow/oltp/generate_sales.py", "orders", ds], check=True, cwd="/opt/airflow")


def _load_mysql(ds, **_):
    subprocess.run([sys.executable, "/opt/airflow/oltp/load_batch.py", "day", ds], check=True, cwd="/opt/airflow")


def _run_etl(**_):
    from automation import run_etl
    return run_etl()


def _quality_check(**_):
    raise NotImplementedError("TODO N6: call quality_checks.check_sales() for the day's batch")


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
    generate = PythonOperator(task_id="generate_orders_csv", python_callable=_generate_orders)
    load_mysql = PythonOperator(task_id="load_orders_mysql", python_callable=_load_mysql)
    etl = PythonOperator(task_id="extract_validate_transform_load", python_callable=_run_etl)
    check = PythonOperator(task_id="quality_check", python_callable=_quality_check)

    generate >> load_mysql >> etl >> check
