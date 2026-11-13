"""
Offline test of the polite-scraping rules in common.fetch() and the Shopify scrapers - no internet needed
(the site answers are written by hand; time.sleep is recorded instead of really waiting).
Run:  python 02_nosql/tests/test_polite_fetch.py      (or pytest)

Rules (13-Nov-2026, after XPRS and Dream 2000 answered HTTP 429 on 10-Nov):
  * HTTP 403 -> BlockedError at once, one request only
  * HTTP 429 -> wait as long as the site asks (Retry-After), 60 s if it does not say; at most 2 waits;
               a third 429, or a wait longer than 5 minutes -> RateLimitedError (stop for today)
  * XPRS and Dream 2000: 5 s before every request; no request for an empty page after a short page
"""
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common  # noqa: E402
import scraper_dream2000  # noqa: E402
import scraper_xprs  # noqa: E402


class FakeResponse:
    def __init__(self, status, headers=None, body=None):
        self.status_code, self.headers, self._body = status, headers or {}, body if body is not None else {}

    def json(self):
        return self._body

    @property
    def text(self):
        return str(self._body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise common.requests.HTTPError(f"HTTP {self.status_code}")


class FakeSite:
    """Replaces session.get and time.sleep; answers come from a list, sleeps are recorded."""

    def __init__(self, answers):
        self.answers, self.calls, self.sleeps = list(answers), [], []

    def __enter__(self):
        self._get, self._sleep = common.session.get, common.time.sleep
        common.session.get = self.get
        common.time.sleep = self.sleeps.append
        return self

    def __exit__(self, *exc):
        common.session.get, common.time.sleep = self._get, self._sleep
        return False

    def get(self, url, timeout=None):
        self.calls.append(url)
        return self.answers.pop(0)


def expect(error_class, fn):
    try:
        fn()
    except error_class as error:
        return error
    raise AssertionError(f"{error_class.__name__} expected")


def test_403_stops_at_once():
    with FakeSite([FakeResponse(403)]) as site:
        expect(common.BlockedError, lambda: common.fetch("https://x/p.json", as_json=True))
    assert len(site.calls) == 1, site.calls


def test_429_waits_as_long_as_the_site_asks_then_continues():
    with FakeSite([FakeResponse(429, {"Retry-After": "30"}), FakeResponse(200, body={"products": []})]) as site:
        data = common.fetch("https://x/p.json", as_json=True, delay=5)
    assert data == {"products": []}
    assert site.sleeps == [5, 30, 5], site.sleeps          # 5 s pause, 30 s asked by the site, 5 s pause


def test_429_without_retry_after_waits_one_minute():
    with FakeSite([FakeResponse(429), FakeResponse(200, body={})]) as site:
        common.fetch("https://x/p.json", as_json=True, delay=5)
    assert 60 in site.sleeps, site.sleeps


def test_third_429_stops_for_today():
    with FakeSite([FakeResponse(429, {"Retry-After": "10"})] * 3) as site:
        expect(common.RateLimitedError, lambda: common.fetch("https://x/p.json", as_json=True, delay=5))
    assert len(site.calls) == 3 and site.sleeps.count(10) == 2, (site.calls, site.sleeps)


def test_a_very_long_wait_is_not_shortened_we_stop():
    with FakeSite([FakeResponse(429, {"Retry-After": "3600"})]) as site:
        expect(common.RateLimitedError, lambda: common.fetch("https://x/p.json", as_json=True, delay=5))
    assert len(site.calls) == 1 and 3600 not in site.sleeps, (site.calls, site.sleeps)


def test_retry_after_as_http_date():
    resp = FakeResponse(429, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})   # a date in the past -> 0 s
    assert common.retry_after_seconds(resp) == 0
    assert common.retry_after_seconds(FakeResponse(429, {"Retry-After": "120"})) == 120
    assert common.retry_after_seconds(FakeResponse(429)) is None


def _shopify_page(n):
    return {"products": [{"id": i, "handle": f"p{i}", "title": "Samsung Galaxy A57 5G 8GB 256GB", "vendor": "Samsung",
                          "variants": [{"id": i, "price": "1000.00", "available": True}]} for i in range(n)]}


def test_shopify_scrapers_wait_5_seconds_and_skip_the_empty_page():
    for module in (scraper_xprs, scraper_dream2000):
        handle = next(iter(module.CATEGORIES))
        with FakeSite([FakeResponse(200, body=_shopify_page(3))]) as site:      # one short page = last page
            module.scrape_category(handle, "2026-11-13", "2026-11-13T04:00:00Z", Path(tempfile.mkdtemp()))
        assert len(site.calls) == 1, (module.SITE, site.calls)                   # no request for page 2
        assert site.sleeps == [5.0], (module.SITE, site.sleeps)
        assert "limit=250&page=1" in site.calls[0]


def test_shopify_scraper_reads_the_next_page_after_a_full_page():
    handle = next(iter(scraper_xprs.CATEGORIES))
    with FakeSite([FakeResponse(200, body=_shopify_page(250)), FakeResponse(200, body=_shopify_page(1))]) as site:
        scraper_xprs.scrape_category(handle, "2026-11-13", "2026-11-13T04:00:00Z", Path(tempfile.mkdtemp()))
    assert len(site.calls) == 2 and site.calls[1].endswith("page=2"), site.calls


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
