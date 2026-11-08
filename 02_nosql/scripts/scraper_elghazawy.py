"""
scraper_elghazawy.py - El Ghazawy (elghazawy.com), HTML listing pages.        Task A10 (Aya).
Replaces Jumia (Jumia answers HTTP 403 since 2-Nov-2026 - we do not work around it).

Source:   GET /en/search?category=<handle>&ct=<id>&page=N   (45 products per page). robots.txt blocks only /cgi-bin/.
Output:   <out_dir>/offers_elghazawy_<date>.json, raw HTML under <out_dir>/raw/<date>/elghazawy/
Run:      python scraper_elghazawy.py   |   python scraper_elghazawy.py --sample

Same structure as scraper_xprs.py; differences:
  * not Shopify: product cards are read from the HTML page (product link + nearest block that holds a price)
  * a discounted card shows "Save X EGP": that amount is removed so it is never taken as the price
  * 2 seconds between requests
"""
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common import OUT_DIR, fetch, new_offer, run_dates, save_raw, discount_pct

SITE = "elghazawy"
BASE_URL = "https://elghazawy.com"
MAX_PAGES = 20
DELAY_SECONDS = 2.0

# site category handle -> (ct id, our category)
CATEGORIES = {
    "smart-phone": (1079, "phone"),
    "tvs": (1163, "tv"),
    "smart-tv": (1570, "tv"),
}   # a product found in two categories is kept once (same product id)

PRODUCT_RE = re.compile(r"/product/(\d{6,})(?:/|$)")
PRICE_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(?:EGP|LE|ج\.?م|جنيه)", re.I)
OUT_OF_STOCK_RE = re.compile(r"out of stock|not available|sold out|غير متوفر|نفذت", re.I)
log = logging.getLogger(SITE)


def parse_prices(text):
    """(sale_price, original_price) from the text of one card. Drops the 'Save X' amount (X = original - sale)."""
    values = [float(m.replace(",", "")) for m in PRICE_RE.findall(text)]
    values = [v for v in values if v >= 100]
    values = [v for v in values if not any(abs(a - b - v) < 1 and v < b for a in values for b in values)]
    if not values:
        return None, None
    sale, top = min(values), max(values)
    return sale, (top if top > sale else None)


def card_of(link):
    """The smallest block around a product link that holds a price and only this one product."""
    node = link
    for _ in range(8):
        node = node.parent
        if node is None:
            return None
        ids = {m.group(1) for a in node.find_all("a", href=True) for m in [PRODUCT_RE.search(a["href"])] if m}
        if len(ids) > 1:
            return None
        if PRICE_RE.search(node.get_text(" ", strip=True)):
            return node
    return None


def page_offers(html, category_site, snapshot_date, scraped_at, raw_file):
    """Turn one listing page into a list of offers, one per product."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        m = PRODUCT_RE.search(a["href"])
        if not m:
            continue
        item = found.setdefault(m.group(1), {"url": None, "titles": [], "card": None})
        if item["url"] is None:
            item["url"] = urljoin(BASE_URL, a["href"].split("?")[0])
        img = a.find("img")
        for t in [a.get_text(" ", strip=True), a.get("title"), img.get("alt") if img else None]:
            if t and len(t) > 8 and not PRICE_RE.search(t):
                item["titles"].append(t.strip())
        if item["card"] is None:
            item["card"] = card_of(a)
    offers = []
    for pid, item in found.items():
        if not item["titles"]:
            continue
        title = max(item["titles"], key=len)
        card_text = item["card"].get_text(" ", strip=True) if item["card"] else ""
        sale, original = parse_prices(card_text)
        stock = OUT_OF_STOCK_RE.search(card_text)
        offers.append(new_offer(
            site=SITE,
            site_product_id=pid,
            snapshot_date=snapshot_date,
            scraped_at=scraped_at,
            url=item["url"],
            title=title,
            brand_raw=title.split()[0],
            category_site=category_site,
            category=CATEGORIES[category_site][1],
            sale_price=sale,
            original_price=original,
            discount_pct=discount_pct(sale, original),
            stock_text=stock.group(0) if stock else None,
            in_stock=False if stock else (True if sale else None),
            source_format="html",
            raw_file=raw_file,
        ))
    return offers


def scrape_category(handle, snapshot_date, scraped_at, out_dir, max_pages=MAX_PAGES):
    """Read the listing page by page until a page has no new product of this category."""
    ct = CATEGORIES[handle][0]
    offers, seen = [], set()
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/en/search?category={handle}&ct={ct}&page={page}"
        html = fetch(url, delay=DELAY_SECONDS)
        raw_file = save_raw(html, SITE, f"{handle}_page{page}.html", snapshot_date, out_dir)
        got = [o for o in page_offers(html, handle, snapshot_date, scraped_at, raw_file) if o["site_product_id"] not in seen]
        if not got:
            break
        seen.update(o["site_product_id"] for o in got)
        offers += got
        log.info("%s page %d: %d products", handle, page, len(got))
    return offers


def run(out_dir=None, sample=False):
    """Scrape every category and write offers_elghazawy_<date>.json. Returns the file path and the count."""
    out_dir = Path(out_dir or OUT_DIR)
    snapshot_date, scraped_at = run_dates()
    offers = {}
    for handle in CATEGORIES:
        for o in scrape_category(handle, snapshot_date, scraped_at, out_dir, max_pages=2 if sample else MAX_PAGES):
            offers.setdefault(o["site_product_id"], o)   # same product in two categories -> once
    offers = list(offers.values())
    if not offers:
        raise RuntimeError("No offers scraped from El Ghazawy - check the site or the parser")
    path = out_dir / f"offers_{SITE}_{snapshot_date}.json"
    path.write_text(json.dumps(offers, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Done: %d offers -> %s", len(offers), path)
    return {"offers_file": str(path), "offers": len(offers)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run(sample="--sample" in sys.argv))
