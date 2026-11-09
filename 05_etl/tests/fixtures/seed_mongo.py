"""seed_mongo.py - TEST FIXTURE ONLY: 8 hand-written offers for 3 products on 2026-10-31 (not real scraped data).
Use it only to test the pipeline on an empty MongoDB. It DELETES every offer of 2026-10-31 first.
Never use its results (3 products, their sales) as project results: load the real offers files instead
(python 02_nosql/scripts/mongo_load.py "data/offers/offers_*.json").
Run: python 05_etl/tests/fixtures/seed_mongo.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from etl_common import get_mongo_db  # noqa: E402

SNAP = "2026-10-31"
SCRAPED = datetime(2026, 10, 31, 6, 0, 0)

PRODUCTS = [
    {"brand_raw": "Samsung", "category": "tv", "title": "Samsung 55 Inch 4K UHD Smart LED TV UA55U8000H",
     "model_raw": "UA55U8000H", "ean": None,
     "offers": {"xprs": ("xprs-tv-55u8000", 28899.0, 30899.0, 7, "In Stock"),
                "dream2000": ("d2k-ua55u8000", 29500.0, None, None, "Only 2 left"),
                "jumia": ("jum-ua55u8000h", 26300.0, 28999.0, 9, "In Stock")}},
    {"brand_raw": "LG", "category": "tv", "title": "LG 55 Inch 4K Smart TV 55U7000",
     "model_raw": "55U7000", "ean": None,
     "offers": {"xprs": ("xprs-lg-55u7000", 24999.0, 26999.0, 7, "In Stock"),
                "jumia": ("jum-55u7000", 23500.0, 24999.0, 6, "In Stock")}},
    {"brand_raw": "Samsung", "category": "phone", "title": "Samsung Galaxy A57 5G 8GB RAM 256GB Black",
     "model_raw": "SM-A576", "ean": "8806099049485",
     "offers": {"xprs": ("xprs-a57-8-256", 30299.0, 32999.0, 8, "In Stock"),
                "jumia": ("jum-a57-8-256", 26295.0, None, None, "In Stock"),
                "dream2000": ("d2k-a57-8256", 27900.0, 29900.0, 6, "Only 1 left")}},
]


def main():
    db = get_mongo_db()
    db.offers.delete_many({"snapshot_date": SNAP})
    docs = []
    for p in PRODUCTS:
        for site, (spid, sale, orig, disc, stock_text) in p["offers"].items():
            docs.append({
                "site": site, "site_product_id": spid, "snapshot_date": SNAP,
                "scraped_at": SCRAPED, "url": f"https://{site}.example/{spid}",
                "title": p["title"], "brand_raw": p["brand_raw"], "model_raw": p["model_raw"],
                "ean": p["ean"], "category_site": p["category"], "category": p["category"],
                "sale_price": sale, "original_price": orig, "discount_pct": disc,
                "currency": "EGP", "stock_text": stock_text, "in_stock": True,
                "seller": "Jumia" if site == "jumia" else None,
                "source_format": "json" if site != "jumia" else "html",
                "raw_file": f"seed/{site}_{spid}.json",
            })
    if docs:
        db.offers.insert_many(docs)
    print(f"inserted {len(docs)} offers for {SNAP}")


if __name__ == "__main__":
    main()