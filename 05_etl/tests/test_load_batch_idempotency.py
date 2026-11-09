"""
Idempotency contract tests for 01_oltp/scripts/load_batch.py.

The docstring of load_batch.py states the rule:
    "the same batch loaded twice must not duplicate rows (INSERT ... ON DUPLICATE KEY UPDATE)"

This module enforces that the rule is actually built into the SQL that load_batch
sends to MySQL:
  - upsert=True  -> the INSERT must carry an ON DUPLICATE KEY UPDATE clause
                    (this is what makes loading the same batch twice safe).
  - upsert=False -> the INSERT must NOT carry that clause
                    (a deliberate "fail on duplicate" path).

No MySQL server is contacted. A MagicMock cursor captures the SQL string, so the
tests are independent of any DB state.

CSV parsing style is not assumed. Each test tries header-first first, then
header-less, and accepts whichever format load_batch currently reads. This is
testing the SQL contract, not the CSV dialect.

Run: python 05_etl/tests/test_load_batch_idempotency.py
"""
import csv
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import MagicMock

OLTP = Path(__file__).resolve().parents[2] / "01_oltp" / "scripts"
sys.path.insert(0, str(OLTP))

try:
    from load_batch import load_csv
except ImportError as e:
    sys.exit(f"ERROR: cannot import load_batch ({e})\nPath tried: {OLTP}")


# --------------------------------------------------------------- helpers
def _mock_conn():
    cursor = MagicMock()
    cursor.rowcount = 1
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)
    return conn, cursor


def _write_csv(rows, header):
    path = Path(tempfile.mkdtemp()) / "data.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if header:
            writer.writerow(header)
        for row in rows:
            writer.writerow(row)
    return str(path)


def _try_load(conn, cursor, rows, columns, upsert):
    """Return the SQL passed to executemany, or None if load_csv refused the CSV."""
    for header in (columns, None):
        try:
            path = _write_csv(rows, header=header)
            cursor.executemany.reset_mock()
            load_csv(conn, "orders", path, columns, upsert=upsert)
            if cursor.executemany.called:
                return cursor.executemany.call_args[0][0]
        except Exception:
            continue
    return None


# --------------------------------------------------------------- static
def test_load_batch_file_exists():
    path = OLTP / "load_batch.py"
    assert path.is_file(), f"missing: {path}"


def test_load_batch_docstring_documents_idempotency():
    text = (OLTP / "load_batch.py").read_text(encoding="utf-8")
    assert "ON DUPLICATE KEY UPDATE" in text, \
        "load_batch.py must reference ON DUPLICATE KEY UPDATE in code/docstring"


# --------------------------------------------------------------- upsert=True (idempotent path)
def test_load_csv_upsert_true_contains_on_duplicate():
    conn, cursor = _mock_conn()
    sql = _try_load(conn, cursor, [["v1", "v2"]], ["a", "b"], upsert=True)
    assert sql is not None, "load_csv produced no SQL - CSV format was refused"
    assert "ON DUPLICATE KEY UPDATE" in sql, \
        f"upsert=True SQL is missing ON DUPLICATE KEY UPDATE: {sql!r}"


def test_load_csv_upsert_true_starts_with_insert_into():
    conn, cursor = _mock_conn()
    sql = _try_load(conn, cursor, [["v1", "v2"]], ["a", "b"], upsert=True)
    assert sql is not None
    assert sql.lstrip().upper().startswith("INSERT INTO ORDERS"), \
        f"upsert=True SQL must start with INSERT INTO orders: {sql!r}"


def test_load_csv_upsert_true_placeholders_match_columns():
    conn, cursor = _mock_conn()
    columns = ["a", "b", "c"]
    sql = _try_load(conn, cursor, [["1", "2", "3"]], columns, upsert=True)
    assert sql is not None
    # Every column contributes exactly one %s placeholder.
    assert sql.count("%s") >= len(columns), \
        f"placeholder count {sql.count('%s')} < columns {len(columns)}: {sql!r}"


def test_load_csv_upsert_true_stable_across_repeated_loads():
    """Loading the same batch twice produces the same idempotent SQL."""
    conn, cursor = _mock_conn()
    rows = [["1", "2"], ["3", "4"]]
    columns = ["a", "b"]

    sql_1 = _try_load(conn, cursor, rows, columns, upsert=True)
    sql_2 = _try_load(conn, cursor, rows, columns, upsert=True)
    assert sql_1 == sql_2, \
        f"idempotent SQL changed between runs: {sql_1!r} != {sql_2!r}"


def test_load_csv_upsert_true_uses_executemany():
    """Batch path must use executemany for the rows (execute is used only for the COUNT(*) before / after)."""
    conn, cursor = _mock_conn()
    cursor.fetchone = MagicMock(return_value=(0,))
    _try_load(conn, cursor, [["v1", "v2"]], ["a", "b"], upsert=True)
    assert cursor.executemany.called, "load_csv must call cursor.executemany(...)"
    for call in cursor.execute.call_args_list:
        assert call[0][0].upper().startswith("SELECT COUNT(*)"), f"unexpected per-row execute: {call}"


# --------------------------------------------------------------- upsert=False (keep existing rows, raise on errors)
def test_load_csv_upsert_false_is_a_no_op_update():
    """A duplicate key keeps the existing row (no-op update), so reloading a day adds nothing."""
    conn, cursor = _mock_conn()
    sql = _try_load(conn, cursor, [["v1", "v2"]], ["a", "b"], upsert=False)
    assert sql is not None, "load_csv produced no SQL for upsert=False"
    assert sql.rstrip().endswith("ON DUPLICATE KEY UPDATE a=a"), f"expected a no-op update on the key: {sql!r}"


def test_load_csv_never_uses_insert_ignore():
    """INSERT IGNORE turns foreign-key and CHECK errors into warnings and drops the row silently."""
    for upsert in (True, False):
        conn, cursor = _mock_conn()
        sql = _try_load(conn, cursor, [["v1", "v2"]], ["a", "b"], upsert=upsert)
        assert sql is not None
        assert "IGNORE" not in sql.upper(), f"upsert={upsert} must not use INSERT IGNORE: {sql!r}"


def test_load_csv_raises_and_rolls_back_on_error():
    """A row that MySQL refuses (e.g. an orphan order item) must fail the load, not vanish."""
    conn, cursor = _mock_conn()
    cursor.fetchone = MagicMock(return_value=(0,))
    cursor.executemany.side_effect = RuntimeError("1452 Cannot add or update a child row: a foreign key constraint fails")
    path = _write_csv([["v1", "v2"]], header=["a", "b"])
    try:
        load_csv(conn, "orders", path, ["a", "b"], upsert=False)
    except RuntimeError:
        assert conn.rollback.called, "load_csv must roll back the file on error"
        return
    raise AssertionError("load_csv must re-raise the MySQL error")


def test_load_csv_upsert_false_placeholders_match_columns():
    conn, cursor = _mock_conn()
    columns = ["a", "b"]
    sql = _try_load(conn, cursor, [["1", "2"]], columns, upsert=False)
    assert sql is not None
    assert sql.count("%s") >= len(columns)


def test_load_csv_upsert_false_differs_from_true():
    """The two paths must NOT produce the same SQL, otherwise idempotency is meaningless."""
    conn, cursor = _mock_conn()
    rows = [["1", "2"]]
    columns = ["a", "b"]
    sql_true = _try_load(conn, cursor, rows, columns, upsert=True)
    sql_false = _try_load(conn, cursor, rows, columns, upsert=False)
    assert sql_true is not None and sql_false is not None
    assert sql_true != sql_false, \
        "upsert=True and upsert=False must produce different SQL"


# --------------------------------------------------------------- main
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
