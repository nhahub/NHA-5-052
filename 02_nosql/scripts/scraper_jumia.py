"""
scraper_jumia.py - Jumia Egypt (jumia.com.eg), server-rendered HTML marketplace.        SKELETON - task A6 (Eng. Aya), due 29-Oct.

Permission: robots.txt (checked 22-Oct-2026) permits scraping IF the User-Agent clearly identifies the bot and its owner
            contact and stays under 200 requests per minute (the User-Agent is set in common.py).
            On 25-Oct-2026 page 4 of phones answered HTTP 403 at 1 request per second, so this scraper waits
            DELAY seconds between pages and STOPS the category on 403 (BlockedError) - never retries around a block.
            It disallows /en/, URLs deeper than three folders (/*/*/*/), filter parameters and q= (search).
Source:     category pages /mobile-phones/?page=N and /televisions/?page=N (cards: article.prd, name .name, price .prc -
            confirmed in the overlap test of 25-Oct-2026)
Output:     <out_dir>/offers_jumia_<date>.json, raw HTML under <out_dir>/raw/<date>/jumia/
Run:        python scraper_jumia.py   |   python scraper_jumia.py --sample   (2 pages per category, for A1)

What to finish (search for TODO):
  1. find_tiles() and parse_tile(): selectors above work; read one saved raw page for the old price, badge and SKU.
  2. Exclude air coolers / accessories that appear inside the TV or phone pages (title words), as in the overlap test.
"""
import json
import logging
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


def find_tiles(soup):
    """Return the product cards of a category page.

    TODO A6: return soup.select("article.prd")   (confirmed 25-Oct-2026)
    """
    raise NotImplementedError("TODO A6: find_tiles()")


def parse_tile(tile, category_site, snapshot_date, scraped_at, raw_file):
    """One card -> one offer document (new_offer(...)), or None if the card has no product link.

    TODO A6:
        url             = product link (absolute; product URLs end with .html)
        site_product_id = the product SKU (data attribute on the card, or the code at the end of the URL)
        title           = name text;  brand_raw = brand on the card if present, else first word of the title
        model_raw       = model code found in the title (e.g. 'UA32H5000FUXEG');  ean = None
        sale_price      = parse_price(price);  original_price = parse_price(old price) if > sale_price
        discount_pct    = badge value if shown, else discount_pct(sale_price, original_price)
        stock_text      = visible text if any;  in_stock = True unless the card says out of stock
        seller          = seller name if the card shows it (marketplace), else None
        category        = CATEGORIES[category_site];  source_format = "html"
    Skip sponsored / "inspired by" items only if they have no real brand (keep a note in 02_nosql.md).
    """
    raise NotImplementedError("TODO A6: parse_tile()")


def scrape_category(path, snapshot_date, scraped_at, out_dir, max_pages=MAX_PAGES):
    """Walk ?page=1,2,... until a page has no cards or repeats the previous page. READY."""
    offers, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            html = fetch(f"{BASE_URL}{path}?page={page}", delay=DELAY)
        except BlockedError as error:          # the site said no: keep what we have, log it, stop this category
            log.warning("%s stopped at page %d: %s", path, page, error)
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
    offers = []
    for path in CATEGORIES:
        offers += scrape_category(path, snapshot_date, scraped_at, out_dir, max_pages=2 if sample else MAX_PAGES)
    if not offers:
        raise RuntimeError("No offers scraped from Jumia - check the site or the parser")
    out = out_dir / f"offers_{SITE}_{snapshot_date}.json"
    out.write_text(json.dumps(offers, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Done: %d offers -> %s", len(offers), out)
    return {"offers_file": str(out), "offers": len(offers)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run(sample="--sample" in sys.argv))
