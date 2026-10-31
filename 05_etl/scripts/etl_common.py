"""
etl_common.py - shared by both pipelines: watermark and run log in etl_state, MongoDB connection.   READY - tested, no change needed.

Taken from the incremental ETL that passed 28 integration checks (21-Oct-2026):
  * the watermark comes only from successful runs, so a failed run never moves it
  * every run (success / failed / no_data) is recorded with rows in / out and a checksum
"""
import os
from datetime import datetime

START_WATERMARK = datetime(1900, 1, 1)


def get_watermark(pg_conn, pipeline):
    """Last committed watermark of a pipeline ('prices_daily' or 'orders_incremental')."""
    with pg_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.etl_state')")
        if cur.fetchone()[0] is None:
            raise RuntimeError("Table etl_state is missing: run 05_etl/scripts/etl_state.sql once in ecommerce_dw.")
        cur.execute("SELECT MAX(watermark) FROM etl_state WHERE pipeline = %s AND status = 'success'", (pipeline,))
        value = cur.fetchone()[0]
    return value or START_WATERMARK


def record_run(pg_conn, pipeline, status, watermark=None, batch_id=None, rows_in=0, rows_out=0, checksum=None, message=None):
    """Insert one row in etl_state and return its run_id. The caller commits (together with the loaded rows)."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl_state (pipeline, batch_id, watermark, rows_in, rows_out, checksum, status, message)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING run_id""",
            (pipeline, batch_id, watermark, rows_in, rows_out, checksum, status, message),
        )
        return cur.fetchone()[0]


def record_failure(pg_conn, pipeline, error):
    """After a rollback: keep a 'failed' row in its own transaction, then let the caller re-raise."""
    try:
        record_run(pg_conn, pipeline, "failed", message=str(error)[:500])
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()


def get_mongo_db():
    """catalog database (settings from docker-compose.yaml)."""
    from pymongo import MongoClient
    client = MongoClient(host=os.getenv("MONGO_HOST", "mongodb"), port=int(os.getenv("MONGO_PORT", "27017")),
                         username=os.getenv("MONGO_USER", "mongo_admin"), password=os.getenv("MONGO_PASSWORD", "mongo_password"))
    return client[os.getenv("MONGO_DB", "catalog")]
