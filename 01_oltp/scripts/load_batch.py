"""
load_batch.py - load generated CSV files into MySQL ecommerce_oltp.        Task H5 (Eng. Hussein).

Run:   python load_batch.py reference            customers.csv + products.csv (insert new rows, update changed ones)
       python load_batch.py day 2026-10-27        orders_<day>.csv then order_items_<day>.csv
Rules: * the same batch loaded twice must not duplicate rows (INSERT ... ON DUPLICATE KEY UPDATE)
       * a row that breaks a foreign key or a CHECK rule must FAIL the load (no INSERT IGNORE: it would turn the
         error into a warning and silently drop the row)
       * check: rows in each file vs rows that are new in the table (counted with SELECT COUNT(*) before and after;
         cursor.rowcount is not a row count for ON DUPLICATE KEY UPDATE)
       * connection: 05_etl/scripts/mysqlconnect.py (get_mysql_connection)
"""
import csv
import sys
from pathlib import Path

def _find_etl_scripts():
    import os
    candidates = [
        os.getenv("ETL_SCRIPTS_PATH"),
        "/opt/airflow/scripts",
        str(Path(__file__).resolve().parents[2] / "05_etl" / "scripts"),
    ]
    for p in candidates:
        if p and Path(p, "mysqlconnect.py").exists():
            return p
    raise RuntimeError(f"Cannot find mysqlconnect.py in any of: {candidates}")


sys.path.insert(0, _find_etl_scripts())
from mysqlconnect import get_mysql_connection  # noqa: E402

DATA = Path("data/sales")
BATCH = 1000


def _count(conn, table):
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
    finally:
        cur.close()


def load_csv(conn, table, path, columns, upsert=False):
    """Read the CSV, insert in batches, commit, return (rows_in_file, rows_new_in_table).
    upsert=True : existing rows are updated (reference data: customers, products)
    upsert=False: existing rows are kept as they are (orders of a day already loaded); errors still raise"""
    path = Path(path)
    if not path.exists():
        sys.exit(f"missing file: {path}")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(tuple(r[c] if r[c] != "" else None for c in columns))

    n_in = len(rows)
    if n_in == 0:
        print(f"{table}: file {path.name} is empty -> 0 rows in, 0 inserted")
        return 0, 0

    pk_col = columns[0]
    if upsert:
        # update every non-PK column on conflict
        non_pk = [c for c in columns if c != pk_col]
        assignments = ", ".join(f"{c}=VALUES({c})" for c in non_pk)
    else:
        # keep the existing row: a no-op update, so a duplicate key is skipped but any other error still raises
        assignments = f"{pk_col}={pk_col}"
    sql = (f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s']*len(columns))}) "
           f"ON DUPLICATE KEY UPDATE {assignments}")

    before = _count(conn, table)
    cursor = conn.cursor()
    try:
        for i in range(0, n_in, BATCH):
            chunk = rows[i:i+BATCH]
            cursor.executemany(sql, chunk)
        conn.commit()                       # one commit per file: a failed file leaves nothing half-loaded
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
    inserted = _count(conn, table) - before

    print(f"{table}: file {path.name} -> {n_in} rows in, {inserted} new in the table")
    return n_in, inserted


def main(argv):
    conn = get_mysql_connection()
    try:
        if argv[:1] == ["reference"]:
            c_in, c_out = load_csv(conn, "customers",
                                   DATA / "customers.csv",
                                   ["customer_id", "governorate", "city", "signup_date"],
                                   upsert=True)
            p_in, p_out = load_csv(conn, "products",
                                   DATA / "products.csv",
                                   ["product_id", "product_code", "category",
                                    "display_name", "list_price_egp", "is_active"],
                                   upsert=True)
            print(f"reference total: customers {c_out}/{c_in}, products {p_out}/{p_in}")
        elif argv[:1] == ["day"] and len(argv) == 2:
            day = argv[1]
            o_in, o_out = load_csv(conn, "orders",
                                   DATA / f"orders_{day}.csv",
                                   ["order_id", "customer_id", "order_purchase_ts",
                                    "order_status", "payment_method"],
                                   upsert=False)
            oi_in, oi_out = load_csv(conn, "order_items",
                                     DATA / f"order_items_{day}.csv",
                                     ["order_id", "item_no", "product_id",
                                      "quantity", "unit_price_egp"],
                                     upsert=False)
            print(f"day {day} total: orders {o_out}/{o_in}, order_items {oi_out}/{oi_in}")
        else:
            sys.exit(__doc__)
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])