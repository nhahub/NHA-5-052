"""
generate_sales.py - synthetic sales of our store (CSV files for MySQL).        SKELETON - tasks H4 (customers, due 30-Oct)
                                                                                and H5 (products + daily orders, due 3-Nov) - Eng. Hussein.
All data made here is SYNTHETIC (approved by the instructor on 22-Oct-2026); the products and market prices are real.

Outputs (folder data/sales/, one set per run):
  customers.csv                     customer_id, governorate, city, signup_date                         (H4, once)
  products.csv                      product_id, product_code, category, display_name, list_price_egp,
                                    is_active                                                            (H5, refreshed)
  orders_YYYY-MM-DD.csv             order_id, customer_id, order_purchase_ts, order_status, payment_method (H5, daily)
  order_items_YYYY-MM-DD.csv        order_id, item_no, product_id, quantity, unit_price_egp               (H5, daily)
Run:
  python generate_sales.py customers
  python generate_sales.py products            (needs dim_product + fact_price_daily in the warehouse: tasks N2, N3)
  python generate_sales.py orders 2026-10-27   (one day; the sales DAG calls this every day)

Rules (data dictionary v4.1, OLTP_MySQL notes):
  * fixed random seed -> the same input gives the same files
  * products = products found on at least 2 sites
  * our price on a day = average market price of that day (all sites) +/- up to 5%
  * no names, phones or addresses (no PII)
"""
import random
import sys
from datetime import date
from pathlib import Path

SEED = 2026
OUT = Path("data/sales")
CONFIG = {                                  # change here, and write the values in 01_oltp.md
    "customers": 3000,
    "orders_per_day": (40, 90),             # min, max
    "items_per_order": {1: 0.80, 2: 0.17, 3: 0.03},
    "status": {"delivered": 0.88, "canceled": 0.08, "returned": 0.04},
    "payment": {"cash_on_delivery": 0.45, "card": 0.30, "installments": 0.15, "wallet": 0.10},
    "price_band": 0.05,                     # +/- 5% around the average market price
}
GOVERNORATES = {                            # weight = share of customers (TODO H4: confirm or simplify)
    "Cairo": 0.22, "Giza": 0.16, "Alexandria": 0.12, "Qalyubia": 0.06, "Sharqia": 0.05, "Dakahlia": 0.05,
    "Gharbia": 0.04, "Monufia": 0.03, "Beheira": 0.03, "Others": 0.24,
}


def make_customers(n=CONFIG["customers"], rng=None):
    """TODO H4: n rows: customer_id 'C000001'..., governorate by GOVERNORATES weights ('Others' = one of the remaining
    governorates in Value_Domains), city (one main city per governorate is enough), signup_date in 2025-01-01..2026-10-01.
    Return a list of dicts and write customers.csv."""
    raise NotImplementedError("TODO H4: make_customers()")


def make_products():
    """TODO H5: read from PostgreSQL the products sold on 2+ sites (product_map, COUNT(DISTINCT site_key) >= 2),
    give each a product_id 'P0001'..., list_price_egp = latest average market price, and write products.csv."""
    raise NotImplementedError("TODO H5: make_products()")


def make_orders(day, customers, products, market_price, rng=None):
    """TODO H5: orders of one day.
       order_id 'O' + YYYYMMDD + 4-digit number; order_purchase_ts = random time on that day (Cairo time);
       status / payment / items by CONFIG weights; unit_price_egp = market_price[product_code][day] * (1 +/- price_band).
       Write orders_<day>.csv and order_items_<day>.csv."""
    raise NotImplementedError("TODO H5: make_orders()")


def main(argv):
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    if argv[:1] == ["customers"]:
        make_customers(rng=rng)
    elif argv[:1] == ["products"]:
        make_products()
    elif argv[:1] == ["orders"] and len(argv) == 2:
        day = date.fromisoformat(argv[1])
        random.seed(f"{SEED}-{day}")          # same day -> same orders
        raise NotImplementedError("TODO H5: load customers.csv, products.csv and the day's market prices, then make_orders()")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
