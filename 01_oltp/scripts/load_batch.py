"""
load_batch.py - load generated CSV files into MySQL ecommerce_oltp.        SKELETON - task H5 (Eng. Hussein), due 3-Nov.

Run:   python load_batch.py reference            customers.csv + products.csv (insert new rows, update changed ones)
       python load_batch.py day 2026-10-27        orders_<day>.csv then order_items_<day>.csv
Rules: * the same batch loaded twice must not duplicate rows (INSERT ... ON DUPLICATE KEY UPDATE, or skip existing keys)
       * check: rows in each file = rows inserted (print both); foreign keys will refuse orphan rows
       * connection: 05_etl/scripts/mysqlconnect.py (get_mysql_connection)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "05_etl" / "scripts"))
from mysqlconnect import get_mysql_connection  # noqa: E402

DATA = Path("data/sales")


def load_csv(conn, table, path, columns):
    """TODO H5: read the CSV, insert in batches (cursor.executemany), commit, and return (rows_in_file, rows_inserted)."""
    raise NotImplementedError("TODO H5: load_csv()")


def main(argv):
    conn = get_mysql_connection()
    try:
        if argv[:1] == ["reference"]:
            raise NotImplementedError("TODO H5: load customers.csv and products.csv")
        elif argv[:1] == ["day"] and len(argv) == 2:
            raise NotImplementedError("TODO H5: load orders_<day>.csv then order_items_<day>.csv")
        else:
            sys.exit(__doc__)
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
