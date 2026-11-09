"""
scraper_xprs.py - XPRS (myxprs.com, Tradeline group), public Shopify JSON.        Task A5 (Eng. Aya) - done.
Replaces 2B (2B blocks bots with HTTP 403 / Cloudflare - we do not work around it).

Source:   GET /collections/<handle>/products.json?limit=250&page=N   (checked 25-Oct-2026). robots.txt has no rule on
          /products.json (it blocks /search and sort/filter URLs only). Terms of service: company description only,
          no scraping clause (checked 25-Oct-2026).
Output:   <out_dir>/offers_xprs_<date>.json, raw JSON under <out_dir>/raw/<date>/xprs/
Run:      python scraper_xprs.py   |   python scraper_xprs.py --sample

Same structure as scraper_dream2000.py; differences:
  * titles are English and usually contain RAM and storage ("Samsung Galaxy A57 5G 8GB 256GB")
  * variant SKU is often the model code (e.g. MZB0P8KEG) and sometimes empty -> model_raw = SKU when present
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
