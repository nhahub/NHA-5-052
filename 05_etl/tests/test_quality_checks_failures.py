"""
Failure tests for quality_checks.py - the gatekeepers of the ETL pipeline.

Every check must raise ValueError on the specific failure branch.
If any test below passes without the corresponding ValueError, a real
pipeline failure would silently pass through Airflow -> ETL is NOT safe.

Branches covered (line refs in 05_etl/scripts/quality_checks.py):
  check_prices:
    L78-79   no rows in fact_price_daily
    L80-84   fact_price_daily rows != etl_state.rows_out
    L92-93   N rows with NULL keys
    L103-104 N duplicate (date_key, site_key, site_product_id)
    L59-65   site dropped below 70% of previous run
  check_sales:
    L148-152 MySQL has no order items (upstream failure)
    L166-170 fact_sales rows != MySQL order_items count
    L171-175 SUM(line_total_egp) != SUM(quantity * unit_price_egp)
    L184-185 N rows with NULL keys in fact_sales

Run as plain script:
    python 05_etl/tests/test_quality_checks_failures.py
Run under pytest:
    pytest 05_etl/tests/test_quality_checks_failures.py -v
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pandas as pd  # noqa: E402

from quality_checks import (  # noqa: E402
    _batch_range, _to_date_key, check_prices, check_sales,
)


class _MockCursor:
    def __init__(self, fetchone_queue, fetchall_queue):
        self.fetchone_queue = fetchone_queue
        self.fetchall_queue = fetchall_queue

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        if not self.fetchone_queue:
            raise AssertionError("MockCursor: fetchone() called more times than queued")
        return self.fetchone_queue.pop(0)

    def fetchall(self):
        if not self.fetchall_queue:
            raise AssertionError("MockCursor: fetchall() called more times than queued")
        return self.fetchall_queue.pop(0)


class _MockConn:
    def __init__(self, fetchone_queue, fetchall_queue=None):
        self.fetchone_queue = list(fetchone_queue)
        self.fetchall_queue = list(fetchall_queue or [])

    def cursor(self):
        return _MockCursor(self.fetchone_queue, self.fetchall_queue)


def _expect_valueerror(fn, fragment):
    try:
        fn()
    except ValueError as e:
        if fragment not in str(e):
            raise AssertionError(
                f"ValueError raised but message does not contain {fragment!r}: {e}"
            )
        return
    raise AssertionError(f"Expected ValueError containing {fragment!r} - none raised")


def test_to_date_key_accepts_iso_string():
    assert _to_date_key("2026-10-31") == 20261031
    assert _to_date_key("2026-01-05") == 20260105


def test_to_date_key_accepts_datetime():
    assert _to_date_key(datetime(2026, 10, 31)) == 20261031


def test_to_date_key_accepts_int():
    assert _to_date_key(20261031) == 20261031


def test_batch_range_single_day():
    assert _batch_range("2026-10-31") == ("2026-10-31", "2026-10-31")


def test_batch_range_span():
    assert _batch_range("2026-10-01..2026-10-31") == ("2026-10-01", "2026-10-31")


def test_check_prices_fails_when_no_rows_for_day():
    conn = _MockConn(
        fetchone_queue=[(None,), (None,), (0,)],
        fetchall_queue=[[]],
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-10-31"),
        "no rows in fact_price_daily",
    )


def test_check_prices_fails_when_rows_out_mismatch():
    conn = _MockConn(
        fetchone_queue=[(None,), (20,), (10,)],
        fetchall_queue=[[("xprs", 10)]],
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-10-31"),
        "successful runs of etl_state inserted 20",
    )


def test_check_prices_fails_on_null_keys():
    conn = _MockConn(
        fetchone_queue=[(None,), (None,), (10,), (3,)],
        fetchall_queue=[[("xprs", 10)]],
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-10-31"),
        "3 rows with NULL keys",
    )


def test_check_prices_fails_on_duplicates():
    conn = _MockConn(
        fetchone_queue=[(None,), (None,), (10,), (0,), (2,)],
        fetchall_queue=[[("xprs", 10)]],
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-10-31"),
        "2 duplicate",
    )


def test_check_prices_fails_on_site_drop_below_70pct():
    conn = _MockConn(
        fetchone_queue=[(20261030,)],
        fetchall_queue=[[("xprs", 5)], [("xprs", 10)]],
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-10-31"),
        "70% threshold",
    )


def test_check_prices_fails_when_a_site_returns_nothing():
    """A site with 0 rows today is missing from today's counts: it must still fail the 70% rule."""
    conn = _MockConn(
        fetchone_queue=[(20261030,)],
        fetchall_queue=[[("xprs", 360), ("dream2000", 560)],                     # today: jumia missing
                        [("xprs", 362), ("dream2000", 561), ("jumia", 950)]],    # previous run
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-10-31"),
        "jumia has 0 offers",
    )


def test_check_prices_skips_a_retired_site():
    """jumia is no longer scraped (HTTP 403 since 2-Nov-2026): with sites=SITES of the DAG it must not fail the
    70% rule; the check goes on to the next rule (here: no rows for the day)."""
    conn = _MockConn(
        fetchone_queue=[(20261101,), (None,), (0,)],
        fetchall_queue=[[("xprs", 360), ("dream2000", 560), ("elghazawy", 300)],
                        [("xprs", 362), ("dream2000", 561), ("jumia", 950)]],
    )
    _expect_valueerror(
        lambda: check_prices(conn, mongo_db=None, snapshot_date="2026-11-09",
                             sites=("dream2000", "xprs", "elghazawy")),
        "no rows in fact_price_daily",
    )


def test_check_sales_fails_when_mysql_empty():
    with patch("pandas.read_sql", return_value=pd.DataFrame(
            [{"items_count": 0, "total_egp": 0.0}])):
        _expect_valueerror(
            lambda: check_sales(pg_conn=None, mysql_engine=None, batch_id="2026-10-31"),
            "MySQL has no order items",
        )


def test_check_sales_fails_on_row_count_mismatch():
    with patch("pandas.read_sql", return_value=pd.DataFrame(
            [{"items_count": 10, "total_egp": 5000.0}])):
        conn = _MockConn(fetchone_queue=[(5, 2500.0)])
        _expect_valueerror(
            lambda: check_sales(pg_conn=conn, mysql_engine=None, batch_id="2026-10-31"),
            "fact_sales has 5 rows",
        )


def test_check_sales_fails_on_amount_mismatch():
    with patch("pandas.read_sql", return_value=pd.DataFrame(
            [{"items_count": 10, "total_egp": 5000.0}])):
        conn = _MockConn(fetchone_queue=[(10, 4000.0)])
        _expect_valueerror(
            lambda: check_sales(pg_conn=conn, mysql_engine=None, batch_id="2026-10-31"),
            "SUM(line_total_egp)",
        )


def test_check_sales_fails_on_null_keys():
    with patch("pandas.read_sql", return_value=pd.DataFrame(
            [{"items_count": 10, "total_egp": 5000.0}])):
        conn = _MockConn(fetchone_queue=[(10, 5000.0), (2,)])
        _expect_valueerror(
            lambda: check_sales(pg_conn=conn, mysql_engine=None, batch_id="2026-10-31"),
            "2 rows with NULL keys in fact_sales",
        )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed, failed = 0, 0
    for fn in tests:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
