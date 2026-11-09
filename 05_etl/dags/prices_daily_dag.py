"""
prices_daily_dag - daily prices of the three sites -> MongoDB -> warehouse.   Task N5 (Eng. Nouran).

Sites (changed 9-Nov-2026): XPRS, Dream 2000 and El Ghazawy. Jumia answers HTTP 403 since 2-Nov-2026, so it is no longer
scraped (we never work around a block); its prices of 27-Oct to 1-Nov stay in the warehouse as history.

  extract (3 scrapers, in parallel) -> store offers in MongoDB -> validate + match + load prices -> quality check

Failure rules (revised 3-Nov-2026 after the review):
  * a site that answers HTTP 403 (BlockedError) fails its task at once, WITHOUT retries: we never visit again a site
    that said no. Network errors and timeouts are still retried (retries=3).
  * store_offers runs when the three extract tasks are finished, even if one failed (trigger_rule='all_done'),
    and stores the files that exist - one blocked site does not lose the day of the two others.
  * the quality check then fails the DAG if a site has fewer than 70% of its previous offers (a missing site = 0).
  * the quality check uses the snapshot dates the load really processed (returned by run_prices), not {{ ds }}:
    in Airflow 2 ds is the START of the data interval, i.e. the day BEFORE the run of a daily DAG.
"""
import sys
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

for path in ("/opt/airflow/scripts", "/opt/airflow/nosql"):
    if path not in sys.path:
        sys.path.insert(0, path)

SITES = ("dream2000", "xprs", "elghazawy")       # jumia removed 9-Nov-2026 (HTTP 403 since 2-Nov)
default_args = {"owner": "Nouran", "retries": 3, "retry_delay": timedelta(minutes=10), "email_on_failure": False}


def _scrape(module_name):
    # imported inside the task, so the scheduler does not load the scrapers on every DAG parse
    def run(**_):
        from common import BlockedError
        module = __import__(module_name)
        try:
            return module.run(out_dir="/opt/airflow/data/offers")["offers_file"]
        except BlockedError as error:
            raise AirflowFailException(f"{module_name}: site blocked the scraper, no retry - {error}") from error
    return run


def _store_offers(ti, **_):
    from mongo_load import load_files
    files = [ti.xcom_pull(task_ids=f"extract_{site}") for site in SITES]
    files = [f for f in files if f]                      # a failed extract has no file
    if not files:
        raise AirflowFailException("No site produced an offers file today")
    return load_files(files)


def _load_prices(**_):
    from load_prices import run_prices
    return run_prices()


def _quality_check(ti, data_interval_end, **_):
    from postgresqlconnect import get_postgres_dw_connection
    from etl_common import get_mongo_db
    from quality_checks import check_prices
    result = ti.xcom_pull(task_ids="validate_match_load_prices") or {}
    # the dates loaded by this run; if there was nothing new, check the day the scrapers stamped (Cairo date)
    dates = result.get("dates") or [data_interval_end.in_timezone("Africa/Cairo").to_date_string()]
    pg_conn = get_postgres_dw_connection()
    try:
        return [check_prices(pg_conn, get_mongo_db(), day, sites=SITES) for day in dates]
    finally:
        pg_conn.close()


with DAG(
    dag_id="prices_daily_dag",
    default_args=default_args,
    description="Scrape XPRS, Dream 2000 and El Ghazawy, match the offers and load daily prices",
    start_date=pendulum.datetime(2026, 10, 27, tz="Africa/Cairo"),
    schedule="0 6 * * *",          # every day at 06:00 Cairo time
    catchup=False,
    max_active_runs=1,
    tags=["module-05", "prices"],
) as dag:
    extract = [PythonOperator(task_id=f"extract_{site}", python_callable=_scrape(f"scraper_{site}"))
               for site in SITES]
    store = PythonOperator(task_id="store_offers_mongodb", python_callable=_store_offers,
                           trigger_rule=TriggerRule.ALL_DONE)
    load = PythonOperator(task_id="validate_match_load_prices", python_callable=_load_prices)
    check = PythonOperator(task_id="quality_check", python_callable=_quality_check)

    extract >> store >> load >> check
