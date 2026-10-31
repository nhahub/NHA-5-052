"""
scraper_xprs.py - XPRS (myxprs.com, Tradeline group), public Shopify JSON.        SKELETON - task A5 (Eng. Aya), due 28-Oct.
Replaces 2B (2B blocks bots with HTTP 403 / Cloudflare - we do not work around it).

Source:   GET /collections/<handle>/products.json?limit=250&page=N   (checked 25-Oct-2026). robots.txt has no rule on
          /products.json (it blocks /search and sort/filter URLs only). Terms of service: company description only,
          no scraping clause (checked 25-Oct-2026).
Output:   <out_dir>/offers_xprs_<date>.json, raw JSON under <out_dir>/raw/<date>/xprs/
Run:      python scraper_xprs.py   |   python scraper_xprs.py --sample

Same structure as scraper_dream2000.py; differences:
  * titles are English and usually contain RAM and storage ("Samsung Galaxy A57 5G 8GB 256GB")
  * variant SKU is often the model code (e.g. MZB0P8KEG) and sometimes empty -> model_raw = SKU when present
What to finish (search for TODO):  to_offers() - you can copy it from scraper_dream2000.py once it works there.
"""
import json
import logging
import re
import sys
from pathlib import Path

from common import OUT_DIR, fetch, new_offer, run_dates, save_raw, parse_price, discount_pct

SITE = "xprs"
BASE_URL = "https://myxprs.com"
MAX_PAGES = 40

# site collection handle -> our category (phone / tv / ac)
CATEGORIES = {
    "mobile-phones-egypt": "phone",
    "32-inch-tv": "tv", "43-inch-tv": "tv", "55-inch-tv": "tv", "65-inch-tv": "tv", "75-inch-tv": "tv",
    "85-inch-tv": "tv", "ultra-hd-4k-tvs": "tv", "ultra-hd-8k-tvs": "tv", "neo-qled-tvs": "tv",
}   # a product found in two collections is kept once (same handle:variant id)

EAN_RE = re.compile(r"^\d{13}$")
log = logging.getLogger(SITE)


def to_offers(product, category_site, snapshot_date, scraped_at, raw_file):
    """Turn one Shopify product (dict from products.json) into a list of offers, one per variant.

    TODO A5 (same mapping as Dream 2000) - for each v in product["variants"]:
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
    raise NotImplementedError("TODO A5: to_offers() - same as Dream 2000")


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
    """Scrape every category and write offers_xprs_<date>.json. Returns the file path and the count. READY."""
    out_dir = Path(out_dir or OUT_DIR)
    snapshot_date, scraped_at = run_dates()
    offers = []
    for handle in CATEGORIES:
        offers += scrape_category(handle, snapshot_date, scraped_at, out_dir, max_pages=2 if sample else MAX_PAGES)
    offers = list({o["site_product_id"]: o for o in offers}.values())   # same product in two collections -> once
    if not offers:
        raise RuntimeError("No offers scraped from XPRS - check the site or the parser")
    path = out_dir / f"offers_{SITE}_{snapshot_date}.json"
    path.write_text(json.dumps(offers, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Done: %d offers -> %s", len(offers), path)
    return {"offers_file": str(path), "offers": len(offers)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run(sample="--sample" in sys.argv))
