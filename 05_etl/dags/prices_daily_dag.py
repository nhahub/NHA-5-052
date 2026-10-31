"""
prices_daily_dag - daily prices of the three sites -> MongoDB -> warehouse.   SKELETON - task N5 (Eng. Nouran), due 5-Nov.

  extract (3 scrapers, in parallel) -> store offers in MongoDB -> validate + match + load prices -> quality check
The DAG file is ready and loads in Airflow; the task functions it calls are finished in tasks A2/A3/A5/A6/N3/N5.
TODO N5: decide whether one failed or blocked site should stop the load (now: yes, every upstream task must succeed),
         and add an email / log alert if you want.
"""
import sys
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

for path in ("/opt/airflow/scripts", "/opt/airflow/nosql"):
    if path not in sys.path:
        sys.path.insert(0, path)

default_args = {"owner": "Nouran", "retries": 3, "retry_delay": timedelta(minutes=10), "email_on_failure": False}


def _scrape(module_name):
    # imported inside the task, so the scheduler does not load the scrapers on every DAG parse
    def run(**_):
        module = __import__(module_name)
        return module.run(out_dir="/opt/airflow/data/offers")["offers_file"]
    return run


def _store_offers(ti, **_):
    from mongo_load import load_files
    files = [ti.xcom_pull(task_ids=t) for t in ("extract_dream2000", "extract_xprs", "extract_jumia")]
    return load_files(files)


def _load_prices(**_):
    from load_prices import run_prices
    return run_prices()


def _quality_check(**_):
    raise NotImplementedError("TODO N5: call quality_checks.check_prices() for today's snapshot")


with DAG(
    dag_id="prices_daily_dag",
    default_args=default_args,
    description="Scrape XPRS, Dream 2000 and Jumia, match the offers and load daily prices",
    start_date=pendulum.datetime(2026, 10, 27, tz="Africa/Cairo"),
    schedule="0 6 * * *",          # every day at 06:00 Cairo time
    catchup=False,
    max_active_runs=1,
    tags=["module-05", "prices"],
) as dag:
    extract = [PythonOperator(task_id=f"extract_{site}", python_callable=_scrape(f"scraper_{site}"))
               for site in ("dream2000", "xprs", "jumia")]
    store = PythonOperator(task_id="store_offers_mongodb", python_callable=_store_offers)
    load = PythonOperator(task_id="validate_match_load_prices", python_callable=_load_prices)
    check = PythonOperator(task_id="quality_check", python_callable=_quality_check)

    extract >> store >> load >> check
