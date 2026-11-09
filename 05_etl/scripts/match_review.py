"""
match_review.py - the manual matching tool (the last level of matching).   Added 6-Nov-2026 (instructor's request).

Matching levels: 1) same barcode (EAN)  2) same key from the title (regex: brand + model + RAM + storage, TV model code)
                 3) THIS TOOL: a person links the offers that levels 1-2 could not match.

  export   writes a review file (CSV, opens in Excel, Arabic OK) with every product of the last 7 days that is on
           ONE site only (view v_unmatched_offers; colour variants of one product in one group, ids joined by ';') and,
           for each, up to 3 suggested products from the other sites: same brand and category, same storage (phones)
           or screen size (TVs), the same model numbers (Note 15 is never suggested for Note 17), ranked by how
           similar the model is. Products with a suggestion come first.
  import   reads the reviewed file: the reviewer writes "yes" in the column decision next to the right suggestion
           (or writes a product_code in other_product_code). The choices are appended to 05_etl/config/manual_matches.csv,
           which the next price load applies first (match_method = 'manual').
           With --apply-db the warehouse is corrected at once: product_map and the past rows of fact_price_daily of
           that offer move to the chosen product.

Run:  python 05_etl/scripts/match_review.py export                      -> data/review/match_review_<date>.csv
      python 05_etl/scripts/match_review.py import data/review/match_review_<date>.csv --by "Mahmoud" [--apply-db]
"""
import argparse
import csv
import re
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config"
MANUAL = CONFIG / "manual_matches.csv"
MANUAL_FIELDS = ["site", "site_product_id", "product_code", "reason", "checked_by", "checked_on"]
YES = {"yes", "y", "نعم", "ok", "1", "x", "✓"}
COLUMNS = ["site", "site_product_id", "title", "price_egp", "url", "current_product_code", "rank",
           "candidate_product_code", "candidate_title", "candidate_sites", "candidate_min_price_egp", "similarity",
           "decision", "other_product_code"]


def _model(product_code):
    """'samsung|tv|43F6000' -> '43F6000';  'samsung|phone|a18|4|128' -> 'a18'."""
    parts = product_code.split("|")
    return parts[2] if len(parts) > 2 else product_code


def similarity(a, b):
    """0..1 - how alike two model keys are (characters and tokens)."""
    a, b = a.lower(), b.lower()
    chars = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(re.split(r"[-|]", a)) - {""}, set(re.split(r"[-|]", b)) - {""}
    tokens = len(ta & tb) / len(ta | tb) if ta | tb else 0
    return round(max(chars, tokens), 3)


def model_numbers(model):
    """The numbers of a model key, network tokens left out: 'note-15-pro' -> ('15',); '43F6000F' -> ('43', '6000');
    'a36-5g' -> ('36',). Two products whose numbers differ are different models (Note 15 is not Note 17)."""
    model = re.sub(r"(?<![a-z0-9])[2345]g(?![a-z0-9])", " ", model.lower())
    return tuple(re.findall(r"\d+", model))


VARIANT_WORDS = {"pro", "plus", "ultra", "max", "lite", "mini", "fe", "neo", "prime", "edge", "fold", "flip"}


def variant_words(model):
    """'15-note-pro-redmi' -> {'pro'}. A Pro is not the plain model, a Lite is not the plain model."""
    return set(re.split(r"[-|\s]+", model.lower())) & VARIANT_WORDS


def suggest(offer, products, top=3, minimum=0.5):
    """Up to `top` candidate products for one unmatched offer.
    offer: dict(site, brand, category, product_code, ram_gb, storage_gb, screen_size_in)
    products: list of dict(product_code, brand, category, ram_gb, storage_gb, screen_size_in, sites, title, min_price)"""
    out = []
    offer_model = _model(offer["product_code"])
    for p in products:
        if p["product_code"] == offer["product_code"] or p["brand"] != offer["brand"] or p["category"] != offer["category"]:
            continue
        if offer["site"] in p["sites"]:
            continue                                   # a site does not sell the same product twice under two keys
        if offer["category"] == "phone" and offer.get("storage_gb") and p.get("storage_gb") \
                and offer["storage_gb"] != p["storage_gb"]:
            continue
        if offer["category"] == "tv" and offer.get("screen_size_in") and p.get("screen_size_in") \
                and offer["screen_size_in"] != p["screen_size_in"]:
            continue
        cand_model = _model(p["product_code"])
        if model_numbers(offer_model) != model_numbers(cand_model):
            continue                                   # Redmi Note 15 vs Note 17, Reno 15 vs Reno 16: never the same
        if offer["category"] == "phone" and variant_words(offer_model) != variant_words(cand_model):
            continue                                   # Note 15 Pro vs Note 15, V60 Lite vs V60
        score = similarity(offer_model, cand_model)
        if score >= minimum:
            out.append((score, p))
    out.sort(key=lambda x: (-x[0], x[1]["product_code"]))
    return out[:top]


def build_rows(unmatched, products):
    """Review rows: ONE group per unmatched product (its colour / variant offers on that site together, ids joined
    by ';'), with up to 3 suggestions. Products with a suggestion come first, the most similar at the top."""
    groups = {}
    for o in unmatched:
        g = groups.setdefault((o["site"], o["product_code"]), {**o, "ids": [], "prices": []})
        g["ids"].append(str(o["site_product_id"]))
        if o.get("price") is not None:
            g["prices"].append(o["price"])
    scored = []
    for g in groups.values():
        cands = suggest(g, products)
        scored.append((-(cands[0][0] if cands else 0), g["site"], g["product_code"], g, cands))
    scored.sort(key=lambda x: x[:3])
    rows = []
    for _, _, _, g, cands in scored:
        base = {"site": g["site"], "site_product_id": ";".join(sorted(set(g["ids"]))), "title": g["title"],
                "price_egp": min(g["prices"]) if g["prices"] else "", "url": g["url"],
                "current_product_code": g["product_code"], "decision": "", "other_product_code": ""}
        if not cands:
            rows.append({**base, "rank": "", "candidate_product_code": "", "candidate_title": "", "candidate_sites": "",
                         "candidate_min_price_egp": "", "similarity": ""})
        for i, (score, p) in enumerate(cands, 1):
            rows.append({**base, "rank": i, "candidate_product_code": p["product_code"], "candidate_title": p["title"],
                         "candidate_sites": ",".join(sorted(p["sites"])), "candidate_min_price_egp": p["min_price"],
                         "similarity": score})
    return rows, len(groups), sum(1 for x in scored if x[4])


# ------------------------------------------------------------------ export
def export(pg_conn, out_path):
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT site_code, site_product_id, category, brand, product_code, ram_gb, storage_gb,
                              screen_size_in, title, url, sale_price_egp FROM v_unmatched_offers
                       ORDER BY category, brand, product_code""")
        unmatched = [dict(zip(["site", "site_product_id", "category", "brand", "product_code", "ram_gb", "storage_gb",
                               "screen_size_in", "title", "url", "price"], r)) for r in cur.fetchall()]
        cur.execute("""SELECT dp.product_code, dp.brand, dp.category, dp.ram_gb, dp.storage_gb, dp.screen_size_in,
                              ARRAY_AGG(DISTINCT ds.site_code), MIN(pm.title_last),
                              (SELECT MIN(f.sale_price_egp) FROM fact_price_daily f WHERE f.product_key = dp.product_key)
                       FROM dim_product dp JOIN product_map pm ON pm.product_key = dp.product_key
                       JOIN dim_site ds ON ds.site_key = pm.site_key
                       GROUP BY dp.product_key""")
        products = [dict(zip(["product_code", "brand", "category", "ram_gb", "storage_gb", "screen_size_in", "sites",
                              "title", "min_price"], r)) for r in cur.fetchall()]
    rows, n_products, with_suggestion = build_rows(unmatched, products)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:      # utf-8-sig: Excel shows Arabic correctly
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(unmatched)} unmatched offers = {n_products} products, {with_suggestion} with a suggestion -> {out_path}")
    return {"unmatched_offers": len(unmatched), "unmatched_products": n_products, "with_suggestion": with_suggestion,
            "rows": len(rows), "file": str(out_path)}


# ------------------------------------------------------------------ import
def read_decisions(path):
    """{(site, site_product_id): product_code} from a reviewed file; raises if one offer has two different choices."""
    chosen = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            code = (r.get("other_product_code") or "").strip()
            if not code and (r.get("decision") or "").strip().lower() in YES:
                code = (r.get("candidate_product_code") or "").strip()
            if not code:
                continue
            for spid in (r["site_product_id"] or "").split(";"):     # one row may hold several offers of one product
                if not spid.strip():
                    continue
                key = (r["site"].strip(), spid.strip())
                if key in chosen and chosen[key] != code:
                    raise ValueError(f"Two different choices for {key}: {chosen[key]} and {code}")
                chosen[key] = code
    return chosen


def append_manual(chosen, checked_by, source, manual_path=MANUAL):
    """Add the choices to manual_matches.csv (a later choice for the same offer replaces the earlier one)."""
    existing = []
    if Path(manual_path).exists():
        with open(manual_path, newline="", encoding="utf-8-sig") as fh:
            existing = [r for r in csv.DictReader(fh) if (r["site"], r["site_product_id"]) not in chosen]
    today = date.today().isoformat()
    new = [{"site": s, "site_product_id": spid, "product_code": code, "reason": f"match_review {Path(source).name}",
            "checked_by": checked_by, "checked_on": today} for (s, spid), code in sorted(chosen.items())]
    with open(manual_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANUAL_FIELDS)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in MANUAL_FIELDS} for r in existing] + new)
    return len(new)


def apply_db(pg_conn, chosen):
    """Move the offers (map + past price rows) to the chosen products now, in one transaction."""
    moved = 0
    with pg_conn.cursor() as cur:
        for (site, spid), code in chosen.items():
            cur.execute("SELECT product_key FROM dim_product WHERE product_code = %s", (code,))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"{code} is not in dim_product: run the price load first, it creates manual products")
            cur.execute("""UPDATE product_map pm SET product_key = %s, match_method = 'manual', match_key = %s
                           FROM dim_site ds WHERE ds.site_key = pm.site_key AND ds.site_code = %s
                             AND pm.site_product_id = %s""", (row[0], code[:120], site, spid))
            cur.execute("""UPDATE fact_price_daily f SET product_key = %s
                           FROM dim_site ds WHERE ds.site_key = f.site_key AND ds.site_code = %s
                             AND f.site_product_id = %s""", (row[0], site, spid))
            moved += 1
    pg_conn.commit()
    return moved


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--out", default=f"data/review/match_review_{date.today().isoformat()}.csv")
    i = sub.add_parser("import")
    i.add_argument("file")
    i.add_argument("--by", required=True, help="name of the reviewer")
    i.add_argument("--apply-db", action="store_true")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from postgresqlconnect import get_postgres_dw_connection
    if args.cmd == "export":
        pg = get_postgres_dw_connection()
        try:
            return export(pg, args.out)
        finally:
            pg.close()
    chosen = read_decisions(args.file)
    n = append_manual(chosen, args.by, args.file)
    print(f"{n} manual matches added to {MANUAL}")
    if args.apply_db and chosen:
        pg = get_postgres_dw_connection()
        try:
            print(f"{apply_db(pg, chosen)} offers moved in the warehouse")
        finally:
            pg.close()
    return {"added": n}


if __name__ == "__main__":
    main(sys.argv[1:])
