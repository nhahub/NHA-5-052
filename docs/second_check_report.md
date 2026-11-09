# Second Check Report — Product Matching

**Date:** 2026-10-31 · **Auditor:** Islam Hassan (component 3) · **Scope:** `05_etl/scripts/matching.py`, `05_etl/scripts/load_prices.py`, `dim_product`, `product_map`

## Methodology
- Code review of `matching.py` (185 lines) and `load_prices.py` (167 lines)
- DW data scan: 276 products, 916 product_map offers, 916 fact_price_daily rows
- Sample of 30 phone model_keys + 20 TV model_keys
- Distribution queries on match_method, ram/storage NULL counts, punctuation counts

## Findings (10 issues, 9 confirmed bugs + 1 pending manual review)

### Bug 1 — Storage regex picks RAM value (severity: high, 23 phones)
`matching.py:82`: `re.search(r"(\d{2,4})\s*GB(?:\s*(?:ROM|Storage))?", text, re.I)` matches the first "NNGB" token in the title. When RAM >= 10GB, "12GB RAM" matches first and is wrongly assigned as storage.
Evidence: `honor|phone|400-5g----|12|12` — storage=12, actual=512.

### Bug 2 — Multi-dash in model_key (severity: medium, 116 products)
`matching.py:93`: `"-".join(words[:4])` treats "-" tokens as words. Result: `400-5g----`, `a6-4g---,`.

### Bug 3 — Comma/punctuation in model_key (severity: medium, 23 products)
Same root cause: `name.split()` keeps `,`, `(`, `)` as tokens. Result: `600,dual-sim-5g,-,`, `14-pro-5g-(`.

### Bug 4 — Silent drop of unmatched offers (severity: low–medium, 44 offers)
`load_prices.py:146`: `message = f"{len(bad)} rejected"` — counts only `validate()` rejections, ignores unmatched (where match_offers returns pc=None).
Evidence: run 9 = `960 in / 916 out / "0 rejected"` — 44 silent.

### Bug 5 — Null dimension attributes (severity: medium, 276 products)
`matching.py:163`: passes `None, None, None` for `ram_gb, storage_gb, screen_size_in` always. `ON CONFLICT` never updates them.
Evidence: `total=276, ram_set=0, storage_set=0, screen_set=0`.

### Bug 6 — Arabic colour names not stripped (severity: medium, count TBD)
`matching.py:90`: `COLOURS` only contains English. `600-lite---أسود` reveals Arabic survives.

### Bug 7 — Em-dash (severity: low, 3 products)
`galaxy-a17-4g-—` — Unicode em-dash U+2014.

### Bug 8 — Parenthesis (severity: low, 3 products)
`14-pro-5g-(` — literal "(" in code.

### Bug 9 — Barcode as TV model (severity: low, 1 product)
`62211031002284` — 14-digit EAN captured by title regex.

### Bug 10 — TV suffix split (severity: low, needs manual review)
`43F6000` vs `43F6000F` — same physical TV or different variant? Requires manual `manual_matches.csv` entry — do NOT auto-strip "F" (would merge legitimately different models like 55F6000 vs 55F6001).

## Fix Scope
Bugs 1, 2, 3, 5, 6, 7, 8, 9: fixed in `matching.py`.
Bug 4: fixed in `load_prices.py`.
Bug 10: requires manual review — add to `manual_matches.csv` once confirmed.

## Post-fix verification
Expected: 0 multi-dash, 0 comma, 0 non-ASCII, 0 paren, ram/storage/screen all non-null for phones/TVs.

## Impact on existing data
All existing `dim_product` product_codes are stale. Full rebuild required. Downtime: ~5 minutes. Data loss: none (MongoDB offers preserved, MySQL orders preserved).
