"""
scraper_jumia.py - Jumia Egypt (jumia.com.eg), server-rendered HTML marketplace.        Task A6 (Eng. Aya) - done.

Permission: robots.txt (checked 22-Oct-2026) permits scraping IF the User-Agent clearly identifies the bot and its owner
            contact and stays under 200 requests per minute (the User-Agent is set in common.py).
            On 25-Oct-2026 page 4 of phones answered HTTP 403 at 1 request per second, so this scraper waits
            DELAY seconds between pages and STOPS the category on 403 (BlockedError) - never retries around a block.
            It disallows /en/, URLs deeper than three folders (/*/*/*/), filter parameters and q= (search).
Source:     category pages /mobile-phones/?page=N and /televisions/?page=N (cards: article.prd, name .name, price .prc -
            confirmed in the overlap test of 25-Oct-2026)
Output:     <out_dir>/offers_jumia_<date>.json, raw HTML under <out_dir>/raw/<date>/jumia/
Run:        python scraper_jumia.py   |   python scraper_jumia.py --sample   (2 pages per category, for A1)

"""
import json
import logging
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from common import OUT_DIR, BlockedError, fetch, new_offer, run_dates, save_raw, parse_price, discount_pct

SITE = "jumia"
BASE_URL = "https://www.jumia.com.eg"
MAX_PAGES = 50
DELAY = 4            # seconds between pages (3-5 s; see the note at the top)

# category path -> our category
CATEGORIES = {
    "/mobile-phones/": "phone",
    "/televisions/": "tv",
}
log = logging.getLogger(SITE)
BLOCKED = []         # categories stopped by HTTP 403 in the current run

_SKU_URL_RE = re.compile(r"-(\d+)\.html")
_MODEL_RE = re.compile(r"\b[A-Z]{0,4}\d{2,4}[A-Z]{1,3}\d{2,5}[A-Z0-9]{0,8}\b")
_ACCESSORY_WORDS = (
    "case", "cover", "protector", "charger", "cable",
    "air conditioner",
    "\u0645\u0643\u064a\u0641", "\u062a\u0643\u064a\u064a\u0641",
    "\u063a\u0637\u0627\u0621", "\u062d\u0627\u0641\u0638\u0629",
    "\u0634\u0627\u062d\u0646", "\u0643\u0627\u0628\u0644",
)


def find_tiles(soup):
    """Return the product cards of a category page."""
    return soup.select("article.prd")


def parse_tile(tile, category_site, snapshot_date, scraped_at, raw_file):
    """One card -> one offer document, or None if the card is not a real product."""
    link = tile.select_one("a.core") or tile.find("a", href=True)
    if link is None or not link.get("href"):
        return None
    href = link["href"]
    if not href.endswith(".html"):
        return None
    url = href if href.startswith("http") else f"{BASE_URL}{href}"

    url_sku = _SKU_URL_RE.search(href)
    sku = tile.get("data-id") or tile.get("data-sku") or (url_sku.group(1) if url_sku else None)
    if not sku:
        return None

    name_el = tile.select_one("h3.name") or tile.select_one(".name")
    title = name_el.get_text(" ", strip=True) if name_el else ""
    if not title:
        return None
    if any(word in title.lower() for word in _ACCESSORY_WORDS):
        return None

    price_el = tile.select_one(".prc")
    sale_price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None

    old_el = tile.select_one(".old")
    original_price = parse_price(old_el.get_text(" ", strip=True)) if old_el else None
    if original_price is not None and sale_price is not None and original_price <= sale_price:
        original_price = None
    discount = discount_pct(sale_price, original_price)

    badge_el = tile.select_one(".bdg._dsct")
    if badge_el is not None:
        badge_text = badge_el.get_text(strip=True).lstrip("-").rstrip("%").strip()
        if badge_text.isdigit() and 0 <= int(badge_text) < 100:
            discount = int(badge_text)

    brand_raw = (tile.get("data-brand") or "").strip() or None
    if brand_raw is None:
        brand_raw = title.split(" ", 1)[0] or None

    model_match = _MODEL_RE.search(title.upper())
    model_raw = model_match.group(0) if model_match else None

    stock_el = tile.select_one(".stock")
    stock_text = stock_el.get_text(" ", strip=True) if stock_el else None
    if stock_text == "":
        stock_text = None
    in_stock = not (stock_text and ("out of stock" in stock_text.lower() or "غير متوفر" in stock_text))

    return new_offer(
        site=SITE,
        site_product_id=str(sku),
        snapshot_date=snapshot_date,
        scraped_at=scraped_at,
        url=url,
        title=title,
        brand_raw=brand_raw,
        model_raw=model_raw,
        ean=None,
        category_site=category_site,
        category=CATEGORIES[category_site],
        sale_price=sale_price,
        original_price=original_price,
        discount_pct=discount,
        currency="EGP",
        stock_text=stock_text,
        in_stock=in_stock,
        seller=None,
        source_format="html",
        raw_file=raw_file,
    )


def scrape_category(path, snapshot_date, scraped_at, out_dir, max_pages=MAX_PAGES):
    """Walk ?page=1,2,... until a page has no cards or repeats the previous page. READY."""
    offers, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            html = fetch(f"{BASE_URL}{path}?page={page}", delay=DELAY)
        except BlockedError as error:          # the site said no: keep what we have, log it, stop this category
            log.warning("%s stopped at page %d: %s", path, page, error)
            BLOCKED.append(f"{path} page {page}")
            break
        raw_file = save_raw(html, SITE, f"{path.strip('/').replace('/', '_')}_p{page}.html", snapshot_date, out_dir)
        tiles = find_tiles(BeautifulSoup(html, "html.parser"))
        page_offers = [o for o in (parse_tile(t, path, snapshot_date, scraped_at, raw_file) for t in tiles) if o]
        ids = {o["site_product_id"] for o in page_offers}
        if not page_offers or ids <= seen:
            break
        offers += [o for o in page_offers if o["site_product_id"] not in seen]   # no duplicates across pages
        seen |= ids
        log.info("%s page %d: %d offers", path, page, len(page_offers))
    return offers


def run(out_dir=None, sample=False):
    """Scrape every category and write offers_jumia_<date>.json. READY."""
    out_dir = Path(out_dir or OUT_DIR)
    snapshot_date, scraped_at = run_dates()
    BLOCKED.clear()
    offers = []
    for path in CATEGORIES:
        offers += scrape_category(path, snapshot_date, scraped_at, out_dir, max_pages=2 if sample else MAX_PAGES)
    if not offers and BLOCKED:
        # blocked before any product: the DAG must NOT retry (that would visit a site that said no again)
        raise BlockedError(f"Jumia blocked the scraper before any offer: {', '.join(BLOCKED)}")
    if not offers:
        raise RuntimeError("No offers scraped from Jumia - check the site or the parser")
    out = out_dir / f"offers_{SITE}_{snapshot_date}.json"
    out.write_text(json.dumps(offers, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Done: %d offers -> %s", len(offers), out)
    return {"offers_file": str(out), "offers": len(offers)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run(sample="--sample" in sys.argv))
