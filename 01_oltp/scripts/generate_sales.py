"""
generate_sales.py - synthetic sales of our store (CSV files for MySQL).
  Tasks H4 (customers) and H5 (products + daily orders) - Eng. Hussein.
All data made here is SYNTHETIC (approved by the instructor on 22-Oct-2026); the products and market prices are real.

Outputs (folder data/sales/, one set per run):
  customers.csv                     customer_id, governorate, city, signup_date
  products.csv                      product_id, product_code, category, display_name,
                                    list_price_egp, is_active
  orders_YYYY-MM-DD.csv             order_id, customer_id, order_purchase_ts, order_status, payment_method
  order_items_YYYY-MM-DD.csv        order_id, item_no, product_id, quantity, unit_price_egp

Run:
  python generate_sales.py customers
  python generate_sales.py products            (needs dim_product + fact_price_daily in the warehouse: tasks N2, N3)
  python generate_sales.py orders 2026-10-27   (one day; the sales DAG calls this every day)

Rules (data dictionary v4.1, OLTP_MySQL notes):
  * fixed random seed -> the same input gives the same files
  * products = products found on at least 2 sites
  * our price on a day = average market price of that day (all sites) +/- up to 5%
  * no names, phones or addresses (no PII)
  * product_id = 'P' + dim_product.product_key (e.g. P00042): the same product keeps the same id in every run,
    so refreshing products.csv never renames products that already have orders (changed 3-Nov-2026)
"""
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

def get_postgres_dw_connection():
    """Lazy import: psycopg2 is only required by the products / orders subcommands."""
    import os
    import sys as _sys
    from pathlib import Path as _Path
    candidates = [
        os.getenv("ETL_SCRIPTS_PATH"),
        "/opt/airflow/scripts",
        str(_Path(__file__).resolve().parents[2] / "05_etl" / "scripts"),
    ]
    for p in candidates:
        if p and _Path(p, "postgresqlconnect.py").exists():
            _sys.path.insert(0, p)
            break
    else:
        raise RuntimeError(f"Cannot find postgresqlconnect.py in any of: {candidates}")
    from postgresqlconnect import get_postgres_dw_connection as _get
    return _get()

SEED = 2026
OUT = Path("data/sales")

CONFIG = {
    "customers": 3000,
    "orders_per_day": (40, 90),             # min, max
    "items_per_order": {1: 0.80, 2: 0.17, 3: 0.03},
    "quantity_per_item": {1: 0.92, 2: 0.06, 3: 0.02},
    "status": {"delivered": 0.88, "canceled": 0.08, "returned": 0.04},
    "payment": {"cash_on_delivery": 0.45, "card": 0.30, "installments": 0.15, "wallet": 0.10},
    "price_band": 0.05,                     # +/- 5% around the average market price
}

GOVERNORATES = {
    "Cairo": 0.22, "Giza": 0.16, "Alexandria": 0.12, "Qalyubia": 0.06, "Sharqia": 0.05, "Dakahlia": 0.05,
    "Gharbia": 0.04, "Monufia": 0.03, "Beheira": 0.03, "Others": 0.24,
}
REMAINING_GOVS = [
    "Kafr El Sheikh", "Damietta", "Port Said", "Ismailia", "Suez", "Faiyum", "Beni Suef", "Minya",
    "Asyut", "Sohag", "Qena", "Luxor", "Aswan", "Red Sea", "New Valley", "Matrouh",
    "North Sinai", "South Sinai",
]
CITY_OF_GOV = {
    "Cairo": "Cairo", "Giza": "Giza", "Alexandria": "Alexandria", "Qalyubia": "Banha",
    "Sharqia": "Zagazig", "Dakahlia": "Mansoura", "Gharbia": "Tanta", "Monufia": "Shebin El-Kom",
    "Beheira": "Damanhour", "Kafr El Sheikh": "Kafr El Sheikh", "Damietta": "Damietta",
    "Port Said": "Port Said", "Ismailia": "Ismailia", "Suez": "Suez", "Faiyum": "Faiyum",
    "Beni Suef": "Beni Suef", "Minya": "Minya", "Asyut": "Asyut", "Sohag": "Sohag",
    "Qena": "Qena", "Luxor": "Luxor", "Aswan": "Aswan", "Red Sea": "Hurghada",
    "New Valley": "Kharga", "Matrouh": "Marsa Matruh", "North Sinai": "Arish", "South Sinai": "Sharm El-Sheikh",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {path}")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# H4 - customers
# ---------------------------------------------------------------------------
def make_customers(n=CONFIG["customers"], rng=None):
    rng = rng or random.Random(SEED)
    govs = list(GOVERNORATES.keys())
    weights = list(GOVERNORATES.values())
    rows = []
    for i in range(1, n + 1):
        gov = rng.choices(govs, weights=weights, k=1)[0]
        if gov == "Others":
            gov = rng.choice(REMAINING_GOVS)
        signup = date(2025, 1, 1) + timedelta(days=rng.randint(0, 638))   # 2025-01-01 .. 2026-10-01
        rows.append({
            "customer_id": f"C{i:06d}",
            "governorate": gov,
            "city": CITY_OF_GOV[gov],
            "signup_date": signup.isoformat(),
        })
    write_csv(OUT / "customers.csv",
              ["customer_id", "governorate", "city", "signup_date"], rows)
    return rows


# ---------------------------------------------------------------------------
# H5 - products
# ---------------------------------------------------------------------------
def make_products():
    pg_conn = get_postgres_dw_connection()
    try:
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT dp.product_key, dp.product_code, dp.category, dp.display_name
                FROM dim_product dp
                JOIN product_map pm ON pm.product_key = dp.product_key
                GROUP BY dp.product_key, dp.product_code, dp.category, dp.display_name
                HAVING COUNT(DISTINCT pm.site_key) >= 2
                ORDER BY dp.product_key
            """)
            prods = cur.fetchall()
            if not prods:
                sys.exit("No products on 2+ sites in dim_product yet: run the price ETL (tasks N2, N3) first.")
            cur.execute("""
                WITH latest AS (
                    SELECT product_key, MAX(date_key) AS last_day
                    FROM fact_price_daily
                    GROUP BY product_key
                )
                SELECT fpd.product_key, AVG(fpd.sale_price_egp)::numeric(10,2)
                FROM fact_price_daily fpd
                JOIN latest l ON l.product_key = fpd.product_key AND l.last_day = fpd.date_key
                GROUP BY fpd.product_key
            """)
            prices = {pk: float(p) for pk, p in cur.fetchall()}
    finally:
        pg_conn.close()

    rows = []
    for pk, code, cat, name in prods:
        if pk not in prices:
            continue
        rows.append({
            "product_id": f"P{pk:05d}",
            "product_code": code,
            "category": cat,
            "display_name": (name or "")[:150],        # MySQL products.display_name is VARCHAR(150)
            "list_price_egp": f"{prices[pk]:.2f}",
            "is_active": 1,
        })
    write_csv(OUT / "products.csv",
              ["product_id", "product_code", "category", "display_name", "list_price_egp", "is_active"], rows)
    return rows


# ---------------------------------------------------------------------------
# H5 - daily orders
# ---------------------------------------------------------------------------
def load_market_prices(pg_conn, day):
    date_key = int(day.strftime("%Y%m%d"))
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT dp.product_code, AVG(fpd.sale_price_egp)::numeric(10,2)
            FROM fact_price_daily fpd
            JOIN dim_product dp ON dp.product_key = fpd.product_key
            WHERE fpd.date_key = %s
            GROUP BY dp.product_code
        """, (date_key,))
        return {code: float(p) for code, p in cur.fetchall()}


def make_orders(day, customers, products, market_price, rng=None):
    rng = rng or random.Random(f"{SEED}-{day}")
    n_orders = rng.randint(*CONFIG["orders_per_day"])
    statuses = list(CONFIG["status"].keys());  status_w = list(CONFIG["status"].values())
    payments = list(CONFIG["payment"].keys()); payment_w = list(CONFIG["payment"].values())
    items_n = list(CONFIG["items_per_order"].keys()); items_w = list(CONFIG["items_per_order"].values())
    qty_n = list(CONFIG["quantity_per_item"].keys()); qty_w = list(CONFIG["quantity_per_item"].values())

    orders_rows, items_rows = [], []
    emitted = 0
    for _ in range(n_orders):
        cust = rng.choice(customers)
        h, m, s = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
        ts = f"{day.isoformat()} {h:02d}:{m:02d}:{s:02d}"
        status = rng.choices(statuses, weights=status_w, k=1)[0]
        payment = rng.choices(payments, weights=payment_w, k=1)[0]

        n_items = rng.choices(items_n, weights=items_w, k=1)[0]
        picked = set()
        order_items_for_this_order = []
        item_no = 0
        for _ in range(n_items):
            for _try in range(20):
                prod = rng.choice(products)
                if prod["product_code"] in picked:
                    continue
                base = market_price.get(prod["product_code"])
                if base is None:
                    continue
                picked.add(prod["product_code"])
                item_no += 1
                band = rng.uniform(-CONFIG["price_band"], CONFIG["price_band"])
                price = round(base * (1.0 + band), 2)
                qty = rng.choices(qty_n, weights=qty_w, k=1)[0]
                order_items_for_this_order.append({
                    "item_no": item_no,
                    "product_id": prod["product_id"],
                    "quantity": qty,
                    "unit_price_egp": f"{price:.2f}",
                })
                break

        if not order_items_for_this_order:
            continue

        emitted += 1
        # order_id: 'O' + YYMMDD + NNNN (11 chars, fits orders.order_id VARCHAR(12)).
        # 'O' + YYYYMMDD + NNNN would be 13 chars -> exceeds the column.
        order_id = f"O{day.strftime('%y%m%d')}{emitted:04d}"
        orders_rows.append({
            "order_id": order_id,
            "customer_id": cust["customer_id"],
            "order_purchase_ts": ts,
            "order_status": status,
            "payment_method": payment,
        })
        for oi in order_items_for_this_order:
            oi["order_id"] = order_id
        items_rows.extend(order_items_for_this_order)

    write_csv(OUT / f"orders_{day.isoformat()}.csv",
              ["order_id", "customer_id", "order_purchase_ts", "order_status", "payment_method"], orders_rows)
    write_csv(OUT / f"order_items_{day.isoformat()}.csv",
              ["order_id", "item_no", "product_id", "quantity", "unit_price_egp"], items_rows)
    return orders_rows, items_rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv):
    OUT.mkdir(parents=True, exist_ok=True)
    if argv[:1] == ["customers"]:
        make_customers(rng=random.Random(SEED))
    elif argv[:1] == ["products"]:
        make_products()
    elif argv[:1] == ["orders"] and len(argv) == 2:
        day = date.fromisoformat(argv[1])
        custs_path = OUT / "customers.csv"
        prods_path = OUT / "products.csv"
        if not custs_path.exists():
            sys.exit(f"{custs_path} is missing: run 'generate_sales.py customers' first.")
        if not prods_path.exists():
            sys.exit(f"{prods_path} is missing: run 'generate_sales.py products' first (needs dim_product with 2+ site products).")
        custs = read_csv(custs_path)
        prods = read_csv(prods_path)
        if not custs:
            sys.exit("customers.csv is empty.")
        if not prods:
            sys.exit("products.csv is empty.")
        pg_conn = get_postgres_dw_connection()
        try:
            prices = load_market_prices(pg_conn, day)
        finally:
            pg_conn.close()
        if not prices:
            sys.exit(f"No market prices in fact_price_daily for {day}: run the price ETL for that day first.")
        make_orders(day, custs, prods, prices, rng=random.Random(f"{SEED}-{day}"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])