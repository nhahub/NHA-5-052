"""
common.py - helpers shared by the three scrapers (Module 02).        READY - tested, no change needed.

  fetch(url)              polite GET: 1 request per second by default, identified User-Agent, retries with back-off;
                          HTTP 403 = the site blocks us -> BlockedError at once, never retried or worked around
  save_raw(...)           keeps the raw page / JSON of every run (raw/<date>/<site>/...)
  parse_price(text)       "EGP 28,899" / "28,899.00 LE" / "٢٨٬٨٩٩ ج.م" -> 28899.0
  run_dates()             snapshot_date (Cairo) and scraped_at (UTC), computed when a run starts
  new_offer(...)          an offer document with every field of the data dictionary (sheet NoSQL_MongoDB)

Built from the reviewed Conran Shop scraper (fetch, retries, raw HTML) of October 2026.
"""
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

DELAY_SECONDS = 1.0                      # one request per second on every site
CONTACT = os.getenv("SCRAPER_CONTACT", "team-email@example.com")
USER_AGENT = f"DEPI-Student-PriceBot/1.0 (educational project; contact: {CONTACT})"
OUT_DIR = Path(os.getenv("SCRAPER_OUT_DIR", "data/offers"))
CAIRO = ZoneInfo("Africa/Cairo")

log = logging.getLogger("scrapers")
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en,ar;q=0.8"})


class BlockedError(RuntimeError):
    """The site answered 403: it does not want this request. Stop; do not retry or try to get around it."""


def fetch(url, retries=5, as_json=False, delay=DELAY_SECONDS):
    """GET with a pause before each request, back-off on 429/503 and network errors. Raises after the last retry.
    HTTP 403 raises BlockedError at once (no retry)."""
    wait = 2
    for attempt in range(1, retries + 1):
        time.sleep(delay)
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 403:
                raise BlockedError(f"HTTP 403 (blocked) on {url}")
            if resp.status_code in (429, 503):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json() if as_json else resp.text
        except (requests.RequestException, ValueError) as error:
            if attempt == retries:
                raise RuntimeError(f"Gave up on {url}: {error}") from error
            log.warning("Attempt %d/%d failed for %s: %s - waiting %ss", attempt, retries, url, error, wait)
            time.sleep(wait)
            wait *= 2


def save_raw(content, site, name, snapshot_date, out_dir=None):
    """Save the raw page (str) or JSON text so a run can be re-parsed later. Returns the relative path."""
    folder = Path(out_dir or OUT_DIR) / "raw" / snapshot_date / site
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(content, encoding="utf-8")
    return str(Path("raw") / snapshot_date / site / name)


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٬٫", "0123456789,.")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_price(text):
    """First number in a price text, as float. Removes currency words and thousands separators. None if no number."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    t = str(text).translate(_ARABIC_DIGITS)
    m = _NUMBER.search(t)
    if not m:
        return None
    value = float(m.group(0).replace(",", ""))
    return value if value > 0 else None


def discount_pct(sale, original):
    """round(100 * (1 - sale / original)) when original > sale, else None."""
    if sale and original and original > sale:
        return round(100 * (1 - sale / original))
    return None


def run_dates():
    """(snapshot_date in Cairo as YYYY-MM-DD, scraped_at in UTC ISO) - computed per run, never at import time."""
    now = datetime.now(timezone.utc)
    return now.astimezone(CAIRO).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%dT%H:%M:%SZ")


OFFER_FIELDS = ["site", "site_product_id", "snapshot_date", "scraped_at", "url", "title", "brand_raw", "model_raw", "ean",
                "category_site", "category", "sale_price", "original_price", "discount_pct", "currency", "stock_text",
                "in_stock", "seller", "source_format", "raw_file"]


def new_offer(**values):
    """Offer document with all 20 fields of the data dictionary; unknown keys are refused."""
    unknown = set(values) - set(OFFER_FIELDS)
    if unknown:
        raise KeyError(f"Not in the data dictionary: {sorted(unknown)}")
    doc = {f: None for f in OFFER_FIELDS}
    doc["currency"] = "EGP"
    doc.update(values)
    return doc


def is_complete(doc):
    """An offer goes to the warehouse only with a price and a stock state; otherwise it goes to quarantine."""
    return bool(doc.get("sale_price")) and doc.get("in_stock") is not None
