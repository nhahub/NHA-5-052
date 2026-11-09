"""
Validation tests for load_prices.py - Task N3.

Covers the three pre-write functions the ETL relies on:
  validate()           reject bad offers before they reach the warehouse
  new_snapshot_dates() watermark filtering (must not reload old days)
  insert_prices()      empty-return paths, skip logic, insert count/sum

All tests are offline. No PostgreSQL / MongoDB is contacted.
psycopg2 is mocked at call site; if not installed at all, the test exits
with an install instruction instead of crashing with a stack trace.

Run: python 05_etl/tests/test_load_prices_validation.py
"""
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from load_prices import insert_prices, new_snapshot_dates, validate
except ImportError as e:
    sys.exit(
        f"ERROR: cannot import load_prices ({e}).\n"
        f"Install: pip install -r requirements.txt"
    )


class _MockCollection:
    def __init__(self, values):
        self._values = values
    def distinct(self, field):
        return self._values


class _MockMongoDB:
    def __init__(self, snapshot_values):
        self.offers = _MockCollection(snapshot_values)


class _MockCursor:
    def __init__(self, fetchall_queue):
        self.fetchall_queue = list(fetchall_queue)
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def execute(self, sql, params=None):
        return None
    def fetchall(self):
        if not self.fetchall_queue:
            raise AssertionError("_MockCursor: fetchall() exhausted")
        return self.fetchall_queue.pop(0)


class _MockConn:
    def __init__(self, fetchall_queue):
        self.fetchall_queue = list(fetchall_queue)
    def cursor(self):
        return _MockCursor(self.fetchall_queue)


# ------------------------------------------------------------ validate
def test_validate_ok_offers_pass():
    offers = [
        {"category": "phone", "sale_price": 100.0, "site": "xprs"},
        {"category": "tv",    "sale_price": "50",  "site": "jumia"},
        {"category": "phone", "sale_price": 1,     "site": "dream2000"},
    ]
    ok, bad = validate(offers)
    assert len(ok) == 3 and len(bad) == 0


def test_validate_rejects_unknown_category():
    offers = [{"category": "fridge", "sale_price": 100.0, "site": "xprs"}]
    ok, bad = validate(offers)
    assert len(ok) == 0 and len(bad) == 1
    assert bad[0][1] == "category"


def test_validate_rejects_non_numeric_price():
    offers = [{"category": "phone", "sale_price": "abc", "site": "xprs"}]
    ok, bad = validate(offers)
    assert len(ok) == 0 and len(bad) == 1
    assert bad[0][1] == "sale_price"


def test_validate_rejects_zero_price():
    offers = [{"category": "phone", "sale_price": 0, "site": "xprs"}]
    ok, bad = validate(offers)
    assert len(bad) == 1 and bad[0][1] == "sale_price"


def test_validate_rejects_negative_price():
    offers = [{"category": "phone", "sale_price": -5.0, "site": "xprs"}]
    ok, bad = validate(offers)
    assert len(bad) == 1 and bad[0][1] == "sale_price"


def test_validate_rejects_missing_site():
    offers = [{"category": "phone", "sale_price": 100.0}]
    ok, bad = validate(offers)
    assert len(bad) == 1 and bad[0][1] == "site"


def test_validate_empty_input():
    ok, bad = validate([])
    assert ok == [] and bad == []


def test_validate_rejects_renewed_brand():
    """Decision 27-Oct-2026: refurbished ('Renewed') offers are not matched or loaded."""
    o = {"site": "jumia", "category": "phone", "sale_price": 9999.0, "brand": "renewed"}
    ok, bad = validate([o])
    assert ok == [] and bad[0][1] == "excluded brand"


# ------------------------------------------------------------ new_snapshot_dates
def test_new_snapshot_dates_filters_by_watermark():
    """The watermark day is loaded again (late offers of that day) together with every newer day."""
    db = _MockMongoDB(["2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"])
    assert new_snapshot_dates(db, datetime(2026, 10, 30)) == [date(2026, 10, 30), date(2026, 10, 31)]


def test_new_snapshot_dates_skips_falsy_values():
    db = _MockMongoDB([None, "", "2026-10-31"])
    assert new_snapshot_dates(db, datetime(2026, 10, 30)) == [date(2026, 10, 31)]


def test_new_snapshot_dates_sorts_result():
    db = _MockMongoDB(["2026-10-31", "2026-10-28", "2026-10-29"])
    assert new_snapshot_dates(db, datetime(2026, 10, 27)) == [
        date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 31),
    ]


def test_new_snapshot_dates_accepts_date_watermark():
    db = _MockMongoDB(["2026-10-31"])
    assert new_snapshot_dates(db, date(2026, 10, 30)) == [date(2026, 10, 31)]


def test_new_snapshot_dates_accepts_date_objects_in_values():
    db = _MockMongoDB([date(2026, 10, 31)])
    assert new_snapshot_dates(db, date(2026, 10, 30)) == [date(2026, 10, 31)]


def test_new_snapshot_dates_returns_empty_when_no_new_day():
    db = _MockMongoDB(["2026-10-28", "2026-10-29"])
    assert new_snapshot_dates(db, datetime(2026, 10, 30)) == []


def test_new_snapshot_dates_reloads_watermark_day():
    """A site scraped again later on the watermark day must still reach the warehouse."""
    db = _MockMongoDB(["2026-10-29", "2026-10-30"])
    assert new_snapshot_dates(db, datetime(2026, 10, 30)) == [date(2026, 10, 30)]


# ------------------------------------------------------------ insert_prices
def test_insert_prices_returns_zero_when_no_matches():
    offers = [{"site": "xprs", "site_product_id": "p1", "sale_price": 999.0}]
    conn = _MockConn(fetchall_queue=[[("xprs", 1)], []])
    inserted, total = insert_prices(conn, offers, [], run_id=1)
    assert inserted == 0 and total == 0.0


def test_insert_prices_skips_unmatched_pc_none():
    offers = [{"site": "xprs", "site_product_id": "p1", "sale_price": 999.0,
               "snapshot_date": "2026-10-31"}]
    matches = [("xprs", "p1", None, "new", None)]
    conn = _MockConn(fetchall_queue=[[("xprs", 1)], []])
    inserted, total = insert_prices(conn, offers, matches, run_id=1)
    assert inserted == 0 and total == 0.0


def test_insert_prices_skips_unknown_site():
    offers = [{"site": "unknown", "site_product_id": "p1", "sale_price": 999.0,
               "snapshot_date": "2026-10-31"}]
    matches = [("unknown", "p1", "code1", "name_spec", "code1")]
    conn = _MockConn(fetchall_queue=[[("xprs", 1)], [("code1", 10)]])
    inserted, total = insert_prices(conn, offers, matches, run_id=1)
    assert inserted == 0 and total == 0.0


def test_insert_prices_skips_unknown_product():
    offers = [{"site": "xprs", "site_product_id": "p1", "sale_price": 999.0,
               "snapshot_date": "2026-10-31"}]
    matches = [("xprs", "p1", "unknown_code", "name_spec", "unknown_code")]
    conn = _MockConn(fetchall_queue=[[("xprs", 1)], []])
    inserted, total = insert_prices(conn, offers, matches, run_id=1)
    assert inserted == 0 and total == 0.0


def test_insert_prices_happy_path_returns_count_and_sum():
    offers = [
        {"site": "xprs", "site_product_id": "p1", "sale_price": 999.0,
         "snapshot_date": "2026-10-31", "scraped_at": "2026-10-31T06:00:00Z"},
        {"site": "jumia", "site_product_id": "p2", "sale_price": 1000.0,
         "snapshot_date": "2026-10-31", "scraped_at": "2026-10-31T06:00:00Z"},
    ]
    matches = [
        ("xprs", "p1", "code1", "name_spec", "code1"),
        ("jumia", "p2", "code2", "name_spec", "code2"),
    ]
    conn = _MockConn(fetchall_queue=[
        [("xprs", 1), ("jumia", 2)],
        [("code1", 10), ("code2", 20)],
        [(999.0,), (1000.0,)],
    ])
    with patch("load_prices.execute_values", return_value=None):
        inserted, total = insert_prices(conn, offers, matches, run_id=1)
    assert inserted == 2
    assert abs(total - 1999.0) < 0.001


# ------------------------------------------------------------ main
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
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
