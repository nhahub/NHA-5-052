# Matching lists (one place each)

Used by `05_etl/scripts/matching.py` (task N2). Rules: data dictionary, sheet **Matching_Rules**.

| File | What it holds | Filled by |
|---|---|---|
| `brand_aliases.csv` | Arabic and English spellings of each brand -> one brand | Aya (A7), after the first full scrape |
| `model_suffixes.csv` | Region / retailer parts removed from model codes | Aya (A7) |
| `category_map.csv` | Site category / collection -> phone or tv | Aya (A2, A5, A6) |
| `manual_matches.csv` | Corrections found in the weekly review of 20 random matches | Mahmoud (M4) and Islam (I1) |

Rows marked `planned` come from the site evaluation of 22-Oct-2026 and must be confirmed on real data.
