"""
Regression + outcome tests for matching.py (rewritten 3-Nov-2026 with the new keys).

The old tests checked the shape of the keys but none failed when the real offers produced 0 products on two sites.
These tests check OUTCOMES on real titles of the three sites:
  * the same product on two or three sites gets ONE key (Arabic and English titles, any word order)
  * different products keep different keys (S26 / S26+ / S26 FE, A17 4G / 5G, colours ignored)
  * golden test: the matched groups of the overlap test A1 (25-Oct-2026, fixtures/a1_overlap_matches_2026-10-25.csv)
    must still agree (70 of 73 phone and TV groups on 3-Nov; the 3 others are real differences A1 had merged)
Run: python 05_etl/tests/test_matching_edge_cases.py      (or pytest)
"""
import csv
import sys
import traceback
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import matching as m  # noqa: E402

ALIASES = m.read_csv("brand_aliases.csv")
SUFFIXES = m.read_csv("model_suffixes.csv")


def offer(site, title, category="phone", brand_raw=None, model_raw=None, spid=None, ean=None):
    return {"site": site, "site_product_id": spid or f"{site}:{title[:20]}", "title": title, "category": category,
            "brand_raw": brand_raw, "model_raw": model_raw, "ean": ean}


def keys(*offers):
    batch = [dict(o) for o in offers]
    m.assign_keys(batch, ALIASES, SUFFIXES)
    return [m.product_code(o["brand"], o["category"], o["model_key"]) if o["model_key"] else None for o in batch]


# ------------------------------------------------------------ text clean-up and memory
def test_clean_text_removes_direction_marks_and_translates_arabic():
    t = m.clean_text("‏⁦سامسونج⁩ جالاكسي A17 - 4 جيجابايت")
    assert t.split()[:3] == ["samsung", "galaxy", "a17"], t
    assert "gb" in t.split()


def test_memory_ram_then_storage():
    assert m.memory(m.clean_text("Samsung Galaxy S26+ 12GB RAM 256GB")) == ("12", "256")


def test_memory_storage_then_ram_with_slash():
    assert m.memory(m.clean_text("Galaxy A17 - 6.7\" 256GB/8GB Dual SIM 5G")) == ("8", "256")


def test_memory_arabic_units():
    assert m.memory(m.clean_text("سامسونج جالاكسي A17 - أسود / 128 جيجابايت / 6 جيجابايت")) == ("6", "128")
    assert m.memory(m.clean_text("هونر X7e بلس - 8 جيجا بايت / 256 جيجا بايت / اسود")) == ("8", "256")


def test_memory_terabyte_and_unitless_storage():
    assert m.memory(m.clean_text("IPhone 18 Pro 2TB")) == (None, "2048")
    assert m.memory(m.clean_text("Infinix HOT 60i 128/ 6GB Mobile Phone")) == ("6", "128")


def test_memory_feature_phone_megabytes_ignored():
    assert m.memory(m.clean_text("نوكيا 235 4G TA-1614 64 ميجابايت رام")) == (None, None)


# ------------------------------------------------------------ same product -> one key
def test_same_phone_arabic_and_english_titles():
    a, b = keys(offer("dream2000", "سامسونج جالاكسي A57 5G - 12 جيجابايت / 256 جيجابايت / أزرق", brand_raw="Samsung"),
                offer("xprs", "Samsung Galaxy A57 5G 12GB 256GB - Gray", brand_raw="Samsung"))
    assert a == b == "samsung|phone|a57|12|256", (a, b)


def test_same_phone_on_three_sites():
    a, b, c = keys(offer("dream2000", "هونر X5C بلس - 4 جيجابايت / 128 جيجابايت / أزرق", brand_raw="Honor"),
                   offer("xprs", "Honor X5c Plus 4G - 4GB Ram - 128GB - Ocian Cyan", brand_raw="Honor"),
                   offer("jumia", "Honor X5c Plus Dual SIM 4G 128GB/4GB - Midnight Black", brand_raw="Honor"))
    assert a == b == c, (a, b, c)


def test_colour_and_filler_words_ignored():
    a, b = keys(offer("xprs", "Infinix Smart 20 4G Dual Sim 4GB Ram 128GB - Sunlike Orange", brand_raw="Infinix"),
                offer("xprs", "Infinix Smart 20 4G Dual Sim 4GB Ram 128GB - Polaris Titanium", brand_raw="Infinix",
                      spid="x2"))
    assert a == b, (a, b)


def test_apple_ram_is_not_part_of_the_key():
    a, b = keys(offer("dream2000", "أبل آيفون 15 - أسود / 128 جيجابايت / 6 جيجابايت", brand_raw="Apple"),
                offer("jumia", "Apple iPhone 15 128GB - Black", brand_raw="Apple"))
    assert a == b, (a, b)


def test_network_word_dropped_when_model_has_one_version():
    # Galaxy S26 is sold only as 5G: Dream 2000 does not write it, XPRS does - still one product
    a, b = keys(offer("dream2000", "سامسونج جالاكسي S26 - أبيض / 256 جيجابايت / 12 جيجابايت", brand_raw="Samsung"),
                offer("xprs", "Samsung Galaxy S26 5G 12GB Ram 256GB - White", brand_raw="Samsung"))
    assert a == b, (a, b)


def test_hyphen_inside_model_name():
    a, b = keys(offer("jumia", "Samsung Galaxy-A27 – Dual SIM 5G 8GB/128GB - black", brand_raw="Samsung"),
                offer("xprs", "Samsung Galaxy A27 5G 8GB Ram 128GB", brand_raw="Samsung"))
    assert a == b, (a, b)


def test_arabic_spelling_variants_and_series_word():
    # Dream 2000 writes Galaxy as جالكسي as well as جالاكسي; Jumia sometimes leaves "Galaxy" out
    a, b, c = keys(offer("dream2000", "سامسونج جالكسي A18 - 4GB / 128GB / Black", brand_raw="Samsung"),
                   offer("xprs", "Samsung Galaxy A18 4G 128GB 4GB RAM - Black", brand_raw="Samsung"),
                   offer("jumia", "Samsung A18 Dual SIM 4G 128GB/4GB - Black", brand_raw="Samsung"))
    assert a == b == c, (a, b, c)


def test_arabic_i_suffix_joins_the_number():
    a, b = keys(offer("dream2000", "إنفينكس هوت 60 اي - 6 جيجابايت / 128 جيجابايت / أسود", brand_raw="Infinix"),
                offer("jumia", "Infinix HOT 60i 128/ 6GB Mobile Phone Titanium Silver", brand_raw="Infinix"))
    assert a == b, (a, b)


# ------------------------------------------------------------ different products -> different keys
def test_plus_and_fe_are_different_products():
    a, b, c = keys(offer("xprs", "Samsung Galaxy S26 5G 12GB Ram 256GB", brand_raw="Samsung", spid="1"),
                   offer("xprs", "Samsung Galaxy S26+ 5G 12GB Ram 256GB", brand_raw="Samsung", spid="2"),
                   offer("xprs", "Samsung Galaxy S26 FE 5G 12GB Ram 256GB", brand_raw="Samsung", spid="3"))
    assert len({a, b, c}) == 3, (a, b, c)


def test_4g_and_5g_versions_stay_apart():
    a4, a5, d = keys(offer("xprs", "Samsung Galaxy A17 4G — 8GB RAM / 256GB - Black", brand_raw="Samsung", spid="1"),
                     offer("xprs", "Samsung Galaxy A17 5G — 8GB RAM / 256GB - Gray", brand_raw="Samsung", spid="2"),
                     offer("dream2000", "سامسونج جالاكسي A17 - أسود / 256 جيجابايت / 8 جيجابايت", brand_raw="Samsung"))
    assert a4 != a5, (a4, a5)
    assert d == a4, "a title without 4G/5G counts as the 4G version"


def test_conflicting_network_across_sites_stays_apart():
    a, b = keys(offer("dream2000", "اوبو A6T 5G - 6 جيجابايت / 128 جيجابايت / ازرق", brand_raw="Oppo"),
                offer("xprs", "Oppo A6t Dual Sim 4G 6GB Ram 128GB - Blue", brand_raw="OPPO"))
    assert a != b, (a, b)


def test_different_storage_is_a_different_product():
    a, b = keys(offer("xprs", "Vivo Y05 4G 4GB 128GB - Black", brand_raw="VIVO", spid="1"),
                offer("xprs", "Vivo Y05 4G 4GB 64GB - Black", brand_raw="VIVO", spid="2"))
    assert a != b


# ------------------------------------------------------------ TVs
def test_tv_code_from_sku_with_suffix_and_prefix():
    (k,) = keys(offer("xprs", "Samsung 43\" Smart TV", "tv", "Samsung", model_raw="UA43F6000FUXEG"))
    assert k == "samsung|tv|43F6000F", k


def test_tv_code_from_arabic_title_with_direction_marks():
    (k,) = keys(offer("dream2000", "‏⁦ATA⁩تلفزيون ⁦43⁩ بوصة، بدون إطار، FHD، ATA43FLN - أسود",
                      "tv", "ATA", ean="6224005120028"))
    assert k == "ata|tv|43FLN", k


def test_tv_size_words_are_not_codes():
    (k,) = keys(offer("jumia", "Samsung 43-Inch Smart LED Full HD TV – 43F6000F", "tv", "Samsung"))
    assert k == "samsung|tv|43F6000F", k


def test_tv_two_letter_series():
    (k,) = keys(offer("dream2000", "ال جي 43 بوصة FHD HDR LED تلفزيون سمارت، 43LM6370PVA - أسود", "tv", "LG"))
    assert k == "lg|tv|43LM6370PVA", k


def test_tv_barcode_or_text_sku_ignored():
    (k1,) = keys(offer("dream2000", "Fresh شاشة 43 بوصة، 43MF435G - فضي", "tv", "Fresh", model_raw="62211031002284"))
    (k2,) = keys(offer("xprs", "Pluto 32\" Smart TV - HD32D-N224", "tv", "Pluto", model_raw="ModelHD32D-N224Screen Size32\""))
    assert k1 == "fresh|tv|43MF435G" and k2 == "pluto|tv|HD32DN224", (k1, k2)


# ------------------------------------------------------------ match order
def test_match_order_manual_ean_existing_key_new():
    offers = [dict(offer("xprs", "Samsung Galaxy A57 5G 12GB 256GB", brand_raw="Samsung", spid="m"), brand="samsung",
                   model_key="x"),
              dict(offer("jumia", "Samsung Galaxy A57", brand_raw="Samsung", spid="e", ean="880"), brand="samsung",
                   model_key=None),
              dict(offer("xprs", "Samsung Galaxy A57", brand_raw="Samsung", spid="old", ean="880"), brand="samsung",
                   model_key="y"),
              dict(offer("xprs", "Samsung Galaxy A57 5G 12GB 256GB", brand_raw="Samsung", spid="k"), brand="samsung",
                   model_key="a57|12|256"),
              dict(offer("dream2000", "سامسونج", brand_raw="Samsung", spid="n"), brand="samsung", model_key=None)]
    existing = {("xprs", "old"): ("samsung|phone|a57-galaxy|12|256", "name_spec", "k")}
    manual = [{"site": "xprs", "site_product_id": "m", "product_code": "samsung|phone|manual"}]
    res = {r[1]: r for r in m.match_offers(offers, existing, manual)}
    assert res["m"][3] == "manual"
    assert res["e"][3] == "ean" and res["e"][2] == "samsung|phone|a57-galaxy|12|256"
    assert res["old"][3] == "name_spec" and res["old"][2] == "samsung|phone|a57-galaxy|12|256"
    assert res["k"][3] == "name_spec" and res["k"][2] == "samsung|phone|a57|12|256"
    assert res["n"][3] == "new" and res["n"][2].startswith("samsung|phone|dream2000-"), res["n"]


# ------------------------------------------------------------ golden test (overlap test A1)
def test_golden_a1_overlap_groups_agree():
    rows = list(csv.DictReader(open(HERE / "fixtures" / "a1_overlap_matches_2026-10-25.csv", encoding="utf-8-sig")))
    groups = defaultdict(list)
    for r in rows:
        groups[r["key"]].append(r)
    agree = total = 0
    for key, members in groups.items():
        brand, category, _ = key.split("|", 2)
        if category not in ("phone", "tv"):
            continue                                  # air conditioners were dropped on 25-Oct
        total += 1
        values = set()
        for r in members:
            b = m.normalize_brand(brand, r["title"], ALIASES)
            if category == "phone":
                values.add("-".join(m.phone_parts(r["title"], b)[0]))
            else:
                values.add(m.tv_code({"title": r["title"], "model_raw": None}, b, SUFFIXES))
        agree += len(values) == 1 and None not in values and "" not in values
    assert total == 73, total
    assert agree >= 68, f"only {agree} of {total} A1 groups get one model name - matching has regressed"


# ------------------------------------------------------------ main
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
