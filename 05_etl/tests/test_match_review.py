"""
Tests for match_review.py, the manual matching tool (offline, no database).
Run: python 05_etl/tests/test_match_review.py      (or pytest)
"""
import csv
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import match_review as mr  # noqa: E402

PRODUCTS = [
    {"product_code": "samsung|tv|43F6000F", "brand": "samsung", "category": "tv", "screen_size_in": 43,
     "storage_gb": None, "ram_gb": None, "sites": ["dream2000", "jumia"], "title": "Samsung 43F6000F", "min_price": 14699},
    {"product_code": "samsung|tv|55F6000F", "brand": "samsung", "category": "tv", "screen_size_in": 55,
     "storage_gb": None, "ram_gb": None, "sites": ["dream2000"], "title": "Samsung 55F6000F", "min_price": 19999},
    {"product_code": "samsung|phone|a18|4|128", "brand": "samsung", "category": "phone", "screen_size_in": None,
     "storage_gb": 128, "ram_gb": 4, "sites": ["dream2000"], "title": "Galaxy A18 4/128", "min_price": 7999},
    {"product_code": "samsung|phone|a18|4|64", "brand": "samsung", "category": "phone", "screen_size_in": None,
     "storage_gb": 64, "ram_gb": 4, "sites": ["dream2000"], "title": "Galaxy A18 4/64", "min_price": 6999},
    {"product_code": "lg|tv|43LM6370PVA", "brand": "lg", "category": "tv", "screen_size_in": 43,
     "storage_gb": None, "ram_gb": None, "sites": ["xprs"], "title": "LG 43LM6370PVA", "min_price": 15000},
]


def test_similarity_year_letter():
    assert mr.similarity("43F6000", "43F6000F") > 0.9


def test_suggest_tv_same_brand_same_size():
    offer = {"site": "xprs", "brand": "samsung", "category": "tv", "product_code": "samsung|tv|43F6000",
             "screen_size_in": 43}
    cands = mr.suggest(offer, PRODUCTS)
    assert [p["product_code"] for _, p in cands] == ["samsung|tv|43F6000F"], cands


def test_suggest_phone_needs_same_storage():
    offer = {"site": "jumia", "brand": "samsung", "category": "phone", "product_code": "samsung|phone|a18-dual|4|128",
             "storage_gb": 128}
    codes = [p["product_code"] for _, p in mr.suggest(offer, PRODUCTS)]
    assert codes == ["samsung|phone|a18|4|128"], codes


def test_suggest_skips_products_already_on_the_same_site():
    offer = {"site": "dream2000", "brand": "samsung", "category": "tv", "product_code": "samsung|tv|43F6000",
             "screen_size_in": 43}
    assert mr.suggest(offer, PRODUCTS) == []


def test_model_numbers_ignore_network():
    assert mr.model_numbers("note-15-pro") == ("15",)
    assert mr.model_numbers("a36-5g") == ("36",)
    assert mr.model_numbers("43F6000F") == ("43", "6000")


def test_suggest_never_a_different_model_number():
    products = [{"product_code": "xiaomi|phone|note-17|8|256", "brand": "xiaomi", "category": "phone",
                 "storage_gb": 256, "sites": ["jumia"], "title": "Redmi Note 17", "min_price": 9000},
                {"product_code": "xiaomi|phone|note-15-pro|8|256", "brand": "xiaomi", "category": "phone",
                 "storage_gb": 256, "sites": ["jumia"], "title": "Redmi Note 15 Pro", "min_price": 11000},
                {"product_code": "xiaomi|phone|note-15-redmi|8|256", "brand": "xiaomi", "category": "phone",
                 "storage_gb": 256, "sites": ["jumia"], "title": "Redmi Note 15", "min_price": 9500}]
    offer = {"site": "xprs", "brand": "xiaomi", "category": "phone", "product_code": "xiaomi|phone|note-15|8|256",
             "storage_gb": 256}
    codes = [p["product_code"] for _, p in mr.suggest(offer, products)]
    assert codes == ["xiaomi|phone|note-15-redmi|8|256"], codes      # Note 17 and Note 15 Pro are other models


def test_variant_words():
    assert mr.variant_words("15-note-pro-redmi") == {"pro"} and mr.variant_words("a18-dual") == set()


def test_build_rows_one_group_per_product():
    unmatched = [{"site": "xprs", "site_product_id": f"tv-43:{i}", "category": "tv", "brand": "samsung",
                  "product_code": "samsung|tv|43F6000", "screen_size_in": 43, "title": "Samsung 43F6000",
                  "url": "u", "price": 15000 + i} for i in (2, 1)]
    unmatched.append({"site": "jumia", "site_product_id": "Z1", "category": "tv", "brand": "zzz",
                      "product_code": "zzz|tv|X1", "screen_size_in": 32, "title": "Z", "url": "u", "price": 5000})
    rows, n_products, with_suggestion = mr.build_rows(unmatched, PRODUCTS)
    assert (n_products, with_suggestion, len(rows)) == (2, 1, 2), rows
    assert rows[0]["site_product_id"] == "tv-43:1;tv-43:2" and rows[0]["price_egp"] == 15001, rows[0]
    assert rows[1]["current_product_code"] == "zzz|tv|X1" and rows[1]["rank"] == ""     # no suggestion -> last


def test_read_decisions_splits_grouped_ids():
    path = _review_file([{"site": "xprs", "site_product_id": "tv-43:1;tv-43:2",
                          "candidate_product_code": "samsung|tv|43F6000F", "decision": "نعم"}])
    assert mr.read_decisions(path) == {("xprs", "tv-43:1"): "samsung|tv|43F6000F",
                                       ("xprs", "tv-43:2"): "samsung|tv|43F6000F"}


def _review_file(rows):
    path = Path(tempfile.mkdtemp()) / "review.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=mr.COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in mr.COLUMNS})
    return path


def test_read_decisions_yes_and_other_code():
    path = _review_file([
        {"site": "xprs", "site_product_id": "tv-43:1", "candidate_product_code": "samsung|tv|43F6000F", "decision": "yes"},
        {"site": "xprs", "site_product_id": "tv-43:1", "candidate_product_code": "samsung|tv|55F6000F", "decision": ""},
        {"site": "jumia", "site_product_id": "123", "other_product_code": "samsung|phone|a18|4|128"},
        {"site": "jumia", "site_product_id": "999", "candidate_product_code": "lg|tv|43LM6370PVA", "decision": ""},
    ])
    assert mr.read_decisions(path) == {("xprs", "tv-43:1"): "samsung|tv|43F6000F",
                                       ("jumia", "123"): "samsung|phone|a18|4|128"}


def test_read_decisions_refuses_two_choices_for_one_offer():
    path = _review_file([
        {"site": "xprs", "site_product_id": "1", "candidate_product_code": "a", "decision": "yes"},
        {"site": "xprs", "site_product_id": "1", "candidate_product_code": "b", "decision": "yes"},
    ])
    try:
        mr.read_decisions(path)
    except ValueError:
        return
    raise AssertionError("two different choices for one offer must be refused")


def test_append_manual_adds_and_replaces():
    manual = Path(tempfile.mkdtemp()) / "manual_matches.csv"
    mr.append_manual({("xprs", "1"): "samsung|tv|43F6000F"}, "Mahmoud", "review1.csv", manual)
    mr.append_manual({("xprs", "1"): "samsung|tv|43F6000"}, "Aya", "review2.csv", manual)   # later choice wins
    rows = list(csv.DictReader(open(manual, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["product_code"] == "samsung|tv|43F6000" and rows[0]["checked_by"] == "Aya", rows
    assert list(rows[0].keys()) == mr.MANUAL_FIELDS


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
