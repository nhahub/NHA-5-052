"""
scraper_dream2000.py - Dream 2000 (dream2000.com), public Shopify JSON.        Task A2 (Eng. Aya) - done.

Source:   GET /collections/<handle>/products.json?limit=250&page=N   (checked 22-Oct-2026: returns vendor, variants
          with sku, price, compare_at_price, available). robots.txt blocks only sort/filter URLs.
Output:   <out_dir>/offers_dream2000_<date>.json  - a list of offer documents (fields: data dictionary, NoSQL_MongoDB)
          raw JSON of every page under <out_dir>/raw/<date>/dream2000/
Run:      python scraper_dream2000.py            (all categories)
          python scraper_dream2000.py --sample   (2 pages per category, for the overlap test A1)

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
PAGE_SIZE = 250            # products.json?limit=250: a shorter page is the last one
DELAY_SECONDS = 5.0       # 5 s between requests (13-Nov-2026; on 10-Nov the site answered HTTP 429 at 1 request per second)

# site collection handle -> our category (phone / tv / ac)
CATEGORIES = {
    "mobiles": "phone",
    "brands": "tv", "lg-tvs": "tv", "lg-tv": "tv", "hisense-tvs": "tv", "haier-tvs": "tv", "haier-tv": "tv",
    "fresh-tvs": "tv", "fresh-tv": "tv", "ata-tvs": "tv", "armadillo-tvs": "tv", "master-electron-tvs": "tv",
}   # a product found in two collections is kept once (same handle:variant id)

EAN_RE = re.compile(r"^\d{13}$")
log = logging.getLogger(SITE)


def to_offers(product, category_site, snapshot_date, scraped_at, raw_file):
    """Turn one Shopify product (dict from products.json) into a list of offers, one per variant."""
    handle = product.get("handle") or ""
    title_base = (product.get("title") or "").strip()
    vendor = (product.get("vendor") or "").strip() or None
    category = CATEGORIES[category_site]
    offers = []
    for v in product.get("variants") or []:
        vid = v.get("id")
        if vid is None:
            continue
        variant_title = (v.get("title") or "").strip()
        title = title_base if variant_title in ("", "Default Title") else f"{title_base} - {variant_title}"
        sku = (v.get("sku") or "").strip()
        ean = sku if EAN_RE.match(sku) else None
        model_raw = None if (not sku or ean) else sku
        sale_price = parse_price(v.get("price"))
        orig = parse_price(v.get("compare_at_price"))
        if orig is not None and sale_price is not None and orig <= sale_price:
            orig = None
        disc = discount_pct(sale_price, orig)
        offers.append(new_offer(
            site=SITE,
            site_product_id=f"{handle}:{vid}",
            snapshot_date=snapshot_date,
            scraped_at=scraped_at,
            url=f"{BASE_URL}/products/{handle}?variant={vid}",
            title=title,
            brand_raw=vendor,
            model_raw=model_raw,
            ean=ean,
            category_site=category_site,
            category=category,
            sale_price=sale_price,
            original_price=orig,
            discount_pct=disc,
            currency="EGP",
            stock_text=None,
            in_stock=bool(v.get("available", False)),
            seller=None,
            source_format="json",
            raw_file=raw_file,
        ))
    return offers


def scrape_category(handle, snapshot_date, scraped_at, out_dir, max_pages=MAX_PAGES):
    """Read products.json page by page; stop after a page with fewer than PAGE_SIZE products (no extra request
    for an empty page)."""
    offers = []
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/collections/{handle}/products.json?limit={PAGE_SIZE}&page={page}"
        data = fetch(url, as_json=True, delay=DELAY_SECONDS)
        raw_file = save_raw(json.dumps(data, ensure_ascii=False), SITE, f"{handle}_page{page}.json", snapshot_date, out_dir)
        products = data.get("products", [])
        if not products:
            break
        for p in products:
            offers += to_offers(p, handle, snapshot_date, scraped_at, raw_file)
        log.info("%s page %d: %d products", handle, page, len(products))
        if len(products) < PAGE_SIZE:
            break
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
