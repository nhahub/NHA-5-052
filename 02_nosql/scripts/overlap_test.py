"""
overlap_test.py - how many products are sold on 2 or 3 sites, per category.        READY - task A1 (Eng. Aya). DONE 25-Oct-2026 (notebook).

Decision rule (data dictionary v4.1): a category with fewer than 20 products found on 2+ sites is dropped.
Result 25-Oct-2026 (Dream 2000, Jumia 5 pages, XPRS): phones 53-63 keep; TVs 19-20 keep and recount after the first
full scrape; air conditioners 6 dropped. Re-run this script on the first full scrape to recount TVs.

Steps:
  1. Run each scraper in sample mode (2 pages per category):
        python scraper_dream2000.py --sample ; python scraper_xprs.py --sample ; python scraper_jumia.py --sample
  2. python overlap_test.py data/offers/offers_*_<date>.json
  3. Read the summary printed on screen and open overlap_report.csv: check 20 rows by eye (same product? yes / no).

The keys here are a quick ESTIMATE for the decision only. The real matching rules are in 05_etl/scripts/matching.py (N2).
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BRAND_ALIASES = {"سامسونج": "samsung", "ال جي": "lg", "إل جي": "lg", "كاريير": "carrier", "شارب": "sharp",
                 "أبل": "apple", "ابل": "apple", "شاومي": "xiaomi", "lg electronics": "lg"}
SPEC = re.compile(r"(\d+)\s*(gb|tb)", re.I)
RAM = re.compile(r"(\d+)\s*gb\s*(?:ram|رام)", re.I)
CODE = re.compile(r"\b(?=[a-z0-9-]*[a-z])(?=(?:[a-z-]*\d){2})[a-z0-9-]{5,}\b", re.I)
PHONE_WORDS = {"pro", "max", "plus", "ultra", "lite", "fe", "mini"}


def brand_of(offer):
    raw = (offer.get("brand_raw") or (offer.get("title") or "").split(" ")[0]).strip().lower()
    return BRAND_ALIASES.get(raw, raw)


def phone_key(title):
    """model tokens before the first spec (latin letters+digits, plus pro/max/...) + RAM + storage."""
    t = title.lower()
    first_spec = SPEC.search(t)
    head = t[:first_spec.start()] if first_spec else t
    tokens = [w for w in re.findall(r"[a-z0-9]+", head) if re.search(r"\d", w) or w in PHONE_WORDS]
    tokens = [w for w in tokens if w not in ("4g", "5g")]
    ram = RAM.search(t)
    sizes = [int(n) * (1024 if u.lower() == "tb" else 1) for n, u in SPEC.findall(t)]
    ram_gb = int(ram.group(1)) if ram else None
    storage = max([s for s in sizes if s != ram_gb], default=None)
    if not tokens or storage is None:
        return None
    return f"{'-'.join(tokens)}|{ram_gb or ''}|{storage}"


def code_key(offer):
    """Longest model-like code in model_raw + title, upper case, without hyphens."""
    text = f"{offer.get('model_raw') or ''} {offer.get('title') or ''}"
    codes = [c.replace("-", "").upper() for c in CODE.findall(text) if not re.fullmatch(r"\d+(gb|tb|hp|inch)?", c, re.I)]
    return max(codes, key=len) if codes else None


def key_of(offer):
    cat = offer.get("category")
    if cat not in ("phone", "tv"):
        return None
    k = phone_key(offer.get("title") or "") if cat == "phone" else code_key(offer)
    return f"{brand_of(offer)}|{cat}|{k}" if k else None


def main(files):
    offers = []
    for f in files:
        offers += json.loads(Path(f).read_text(encoding="utf-8"))
    groups = defaultdict(lambda: defaultdict(list))         # key -> site -> titles
    per_site = defaultdict(lambda: defaultdict(int))        # category -> site -> offers
    no_key = defaultdict(int)
    for o in offers:
        per_site[o.get("category")][o["site"]] += 1
        k = key_of(o)
        if k:
            groups[k][o["site"]].append(f'{o.get("title")} | {o.get("sale_price")}')
        else:
            no_key[o.get("category")] += 1

    print(f"{'category':10}{'offers by site':40}{'products':>10}{'on 2+ sites':>13}{'on 3 sites':>12}  decision")
    for cat in ("phone", "tv"):
        keys = [k for k in groups if k.split("|")[1] == cat]
        two = sum(1 for k in keys if len(groups[k]) >= 2)
        three = sum(1 for k in keys if len(groups[k]) >= 3)
        sites = ", ".join(f"{s}={n}" for s, n in sorted(per_site[cat].items()))
        decision = "KEEP" if two >= 20 else "DROP (fewer than 20 on 2+ sites)"
        print(f"{cat:10}{sites:40}{len(keys):>10}{two:>13}{three:>12}  {decision}   (no key: {no_key[cat]})")

    with open("overlap_report.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "sites", "titles and prices (per site)", "same product? (check by eye)"])
        for k, by_site in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(by_site) >= 2:
                w.writerow([k, len(by_site), " || ".join(f"{s}: {t[0]}" for s, t in sorted(by_site.items())), ""])
    print("overlap_report.csv written (products on 2+ sites).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python overlap_test.py offers_dream2000_<date>.json offers_xprs_<date>.json offers_jumia_<date>.json")
    main(sys.argv[1:])
