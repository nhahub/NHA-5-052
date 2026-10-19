"""
extract_olist.py — Extract step: Olist Brazilian E-Commerce dataset (Kaggle)

Splits orders, order_items and order_reviews into monthly batches by purchase
month (CSV and JSON). The 9 original files are copied unchanged.

Run by hand:   python extract_olist.py
Output:        data/raw/olist/<name>_YYYY-MM.csv / .json
"""

import logging
import shutil
from pathlib import Path

import kagglehub
import pandas as pd

DATASET = "olistbr/brazilian-ecommerce"
RAW_DIR = Path("data/raw/olist")
SPLIT_FILES = ["order_items", "order_reviews"]

log = logging.getLogger("extract_olist")


def download_dataset():
    """Download the Olist files from Kaggle and return the folder."""
    return Path(kagglehub.dataset_download(DATASET))


def copy_originals(source_dir, raw_dir):
    """Copy the 9 original files unchanged."""
    orig_dir = raw_dir / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    for f in source_dir.glob("*.csv"):
        shutil.copy(f, orig_dir / f.name)


def save_batches(df, name, raw_dir):
    """Save one CSV and one JSON file per month (batch_id is kept in the file name)."""
    for batch, part in df.groupby("batch_id"):
        part = part.drop(columns="batch_id")
        part.to_csv(raw_dir / f"{name}_{batch}.csv", index=False)
        part.to_json(raw_dir / f"{name}_{batch}.json", orient="records", force_ascii=False)


def split_orders(source_dir, raw_dir):
    """Split orders by purchase month and return them with a batch_id column."""
    orders = pd.read_csv(source_dir / "olist_orders_dataset.csv")
    orders["batch_id"] = pd.to_datetime(orders["order_purchase_timestamp"]).dt.strftime("%Y-%m")
    save_batches(orders, "orders", raw_dir)
    return orders


def split_children(source_dir, raw_dir, batch_of):
    """Split items and reviews by the month of their order."""
    for name in SPLIT_FILES:
        df = pd.read_csv(source_dir / f"olist_{name}_dataset.csv")
        df["batch_id"] = df["order_id"].map(batch_of)
        missing = df["batch_id"].isna().sum()
        if missing:
            raise ValueError(f"{name}: {missing} rows have no matching order")
        save_batches(df, name, raw_dir)


def run(raw_dir=None):
    """Entry point for Airflow or for running by hand."""
    raw_dir = Path(raw_dir or RAW_DIR)
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_dir = download_dataset()
    copy_originals(source_dir, raw_dir)
    orders = split_orders(source_dir, raw_dir)
    batch_of = orders.set_index("order_id")["batch_id"]
    split_children(source_dir, raw_dir, batch_of)
    n_files = len(list(raw_dir.glob("*_*.csv")))
    log.info("Saved %d monthly CSV files to %s", n_files, raw_dir)
    return str(raw_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
