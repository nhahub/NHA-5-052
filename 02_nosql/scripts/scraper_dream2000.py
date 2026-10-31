"""
scraper_dream2000.py - Dream 2000 (dream2000.com), public Shopify JSON.        SKELETON - task A2 (Eng. Aya), due 27-Oct.

Source:   GET /collections/<handle>/products.json?limit=250&page=N   (checked 22-Oct-2026: returns vendor, variants
          with sku, price, compare_at_price, available). robots.txt blocks only sort/filter URLs.
Output:   <out_dir>/offers_dream2000_<date>.json  - a list of offer documents (fields: data dictionary, NoSQL_MongoDB)
          raw JSON of every page under <out_dir>/raw/<date>/dream2000/
Run:      python scraper_dream2000.py            (all categories)
          python scraper_dream2000.py --sample   (2 pages per category, for the overlap test A1)

What to finish (search for TODO):
  1. CATEGORIES: checked in the overlap test (25-Oct-2026); add a TV brand collection if a new one appears.
  2. to_offers(): one offer per variant (each storage option is a separate offer).
"""
import json
import logging
import re
import sys
from pathlib import Path

from common import OUT_DIR, fetch, new_offer, run_dates, save_raw, parse_price, discount_pct

SITE = "dream2000"
BASE_URL = "https://dream2000.com"
MAX_PAGES = 40

# site collection handle -> our category (phone / tv / ac)
CATEGORIES = {
    "mobiles": "phone",
    "brands": "tv", "lg-tvs": "tv", "lg-tv": "tv", "hisense-tvs": "tv", "haier-tvs": "tv", "haier-tv": "tv",
    "fresh-tvs": "tv", "fresh-tv": "tv", "ata-tvs": "tv", "armadillo-tvs": "tv", "master-electron-tvs": "tv",
}   # a product found in two collections is kept once (same handle:variant id)

EAN_RE = re.compile(r"^\d{13}$")
log = logging.getLogger(SITE)


def to_offers(product, category_site, snapshot_date, scraped_at, raw_file):
    """Turn one Shopify product (dict from products.json) into a list of offers, one per variant.

    TODO A2 - for each v in product["variants"]:
        site_product_id = f'{product["handle"]}:{v["id"]}'
        url             = f'{BASE_URL}/products/{product["handle"]}?variant={v["id"]}'
        title           = product["title"] + (' - ' + v["title"] if v["title"] != 'Default Title' else '')
        brand_raw       = product["vendor"]
        ean             = v["sku"] if it matches EAN_RE else None
        model_raw       = v["sku"] if it is not an EAN, else None (the matching step also reads the title)
        sale_price      = parse_price(v["price"]);  original_price = parse_price(v["compare_at_price"]) if > sale_price
        discount_pct    = discount_pct(sale_price, original_price)
        in_stock        = v["available"];  stock_text = None (the JSON has no text)
        category_site   = category_site;   category = CATEGORIES[category_site];  source_format = "json"
    and build each document with new_offer(site=SITE, ..., raw_file=raw_file).
    """
    raise NotImplementedError("TODO A2: to_offers()")


def scrape_category(handle, snapshot_date, scraped_at, out_dir, max_pages=MAX_PAGES):
    """Read products.json page by page until a page is empty. READY."""
    offers = []
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/collections/{handle}/products.json?limit=250&page={page}"
        data = fetch(url, as_json=True)
        raw_file = save_raw(json.dumps(data, ensure_ascii=False), SITE, f"{handle}_page{page}.json", snapshot_date, out_dir)
        products = data.get("products", [])
        if not products:
            break
        for p in products:
            offers += to_offers(p, handle, snapshot_date, scraped_at, raw_file)
        log.info("%s page %d: %d products", handle, page, len(products))
    return offers


def run(out_dir=None, sample=False):
    """Scrape every category and write offers_dream2000_<date>.json. Returns the file path and the count. READY."""
    out_dir = Path(out_dir or OUT_DIR)
    snapshot_date, scraped_at = run_dates()
    offers = []
    for handle in CATEGORIES:
        offers += scrape_category(handle, snapshot_date, scraped_at, out_dir, max_pages=2 if sample else MAX_PAGES)
    offers = list({o["site_product_id"]: o for o in offers}.values())   # same product in two collections -> once
    if not offers:
        raise RuntimeError("No offers scraped from Dream 2000 - check the site or the parser")
    path = out_dir / f"offers_{SITE}_{snapshot_date}.json"
    path.write_text(json.dumps(offers, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Done: %d offers -> %s", len(offers), path)
    return {"offers_file": str(path), "offers": len(offers)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run(sample="--sample" in sys.argv))
