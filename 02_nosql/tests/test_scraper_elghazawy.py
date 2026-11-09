"""
Offline test of scraper_elghazawy.py - no internet needed (a small listing page written by hand).
Run:  python 02_nosql/tests/test_scraper_elghazawy.py      (or pytest)
After the first real run, a saved page from data/offers/raw/<date>/elghazawy/ can replace PAGE below.
"""
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scraper_elghazawy as eg  # noqa: E402

PAGE = """<html><body><div class="grid">
<div class="card">
  <a href="/en/product/38074270286885/samsung-galaxy-s25-ultra"><img alt="Samsung Galaxy S25 Ultra 12GB 256GB"></a>
  <a href="/en/product/38074270286885/samsung-galaxy-s25-ultra">Samsung Galaxy S25 Ultra 12GB 256GB</a>
  <span>54,999 EGP</span><del>64,999 EGP</del><b>Save 10,000 EGP</b>
</div>
<div class="card">
  <a href="/en/product/38074270287304/lg-43">Smart TV LG 43 Inch Full HD 43LM6370PVA</a>
  <span>EGP 15,200</span><span>Out of stock</span>
</div>
<div class="card">
  <a href="/en/product/38074270290001/no-price">Xiaomi Redmi Note 15 8GB 256GB</a>
</div>
</div></body></html>"""


def offers(category="smart-phone"):
    return {o["site_product_id"]: o for o in eg.page_offers(PAGE, category, "2026-11-09", "2026-11-09T04:00:00Z", "raw")}


def test_brand_is_a_known_brand_not_the_first_word():
    assert eg.brand_of("Smart TV LG 43 Inch 43LM6370PVA") == "LG"
    assert eg.brand_of("Ultra HD 4K Smart TV Samsung 55 Inch") == "Samsung"     # "Ultra HD" is not the brand Ultra
    assert eg.brand_of("Ultra 32 Inch HD LED TV UT32REL1") == "Ultra"
    assert eg.brand_of("iPhone 17 Pro 256GB") == "Apple"
    assert eg.brand_of("Galaxy A57 5G 8GB 256GB") == "Samsung"
    assert eg.brand_of("Unknown Phone X1") is None


def test_price_with_currency_after_or_before():
    assert eg.parse_prices("12,999 EGP 14,999 EGP Save 2,000 EGP") == (12999.0, 14999.0)
    assert eg.parse_prices("EGP 12,999 EGP 14,999 Save EGP 2,000") == (12999.0, 14999.0)
    assert eg.parse_prices("15,200 L.E") == (15200.0, None)
    assert eg.parse_prices("no price here") == (None, None)


def test_page_offers_reads_each_card_once():
    o = offers()
    assert set(o) == {"38074270286885", "38074270287304", "38074270290001"}, o.keys()
    s25 = o["38074270286885"]
    assert (s25["brand_raw"], s25["sale_price"], s25["original_price"], s25["discount_pct"], s25["in_stock"]) == \
        ("Samsung", 54999.0, 64999.0, 15, True), s25
    tv = o["38074270287304"]
    assert (tv["brand_raw"], tv["sale_price"], tv["in_stock"]) == ("LG", 15200.0, False), tv
    assert tv["url"] == "https://elghazawy.com/en/product/38074270287304/lg-43"
    no_price = o["38074270290001"]
    assert no_price["sale_price"] is None and no_price["in_stock"] is None   # -> quarantine in mongo_load


def test_scrape_category_stops_when_a_page_has_no_new_product():
    calls = []
    real_fetch, real_save = eg.fetch, eg.save_raw
    eg.fetch = lambda url, delay=0: calls.append(url) or PAGE          # the site repeats the last page
    eg.save_raw = lambda html, site, name, day, out_dir: f"raw/{day}/{site}/{name}"
    try:
        got = eg.scrape_category("smart-phone", "2026-11-09", "t", Path(tempfile.mkdtemp()))
    finally:
        eg.fetch, eg.save_raw = real_fetch, real_save
    assert len(got) == 3 and len(calls) == 2, (len(got), calls)        # page 2 had nothing new -> stop
    assert calls[0].endswith("/en/search?category=smart-phone&ct=1079&page=1")


def test_blocked_site_stops_the_run():
    real_fetch = eg.fetch

    def blocked(url, delay=0):
        raise eg.BlockedError(f"HTTP 403 (blocked) on {url}")
    eg.fetch = blocked
    try:
        eg.scrape_category("tvs", "2026-11-09", "t", Path(tempfile.mkdtemp()))
    except eg.BlockedError:
        return
    finally:
        eg.fetch = real_fetch
    raise AssertionError("HTTP 403 must stop the scraper (BlockedError), never be worked around")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
