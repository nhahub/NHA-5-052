# Module 2 — NoSQL (MongoDB): daily offers of the websites
**Owner:** Aya Elgarwany · **Sites:** XPRS (JSON), Dream 2000 (JSON), El Ghazawy (HTML, from 9-Nov-2026) · Jumia Egypt (HTML, 27-Oct to 1-Nov-2026 only) · **Categories:** phone, tv

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Polite scraping (all scrapers, already in `scripts/common.py`)
One request per second on XPRS and Dream 2000, one every 2 seconds on El Ghazawy, one every 3-5 seconds on Jumia · HTTP 403 = stop (never work around a block) · User-Agent with the bot name and the contact in `SCRAPER_CONTACT` (`.env`) · raw pages kept under `data/offers/raw/<date>/<site>/`.

## Sources: Jumia replaced by El Ghazawy (9-Nov-2026)
Jumia answers **HTTP 403 since 2-Nov-2026**, so it is no longer scraped (we never work around a block). Its offers of 27-Oct, 29-Oct and 1-Nov stay in MongoDB and in the warehouse as price history. El Ghazawy (`scraper_elghazawy.py`, task A10) takes its place in `prices_daily_dag`:
`GET https://elghazawy.com/en/search?category=<handle>&ct=<id>&page=N` (server-rendered HTML, 45 products per page, English titles); categories `smart-phone` (phone), `tvs` and `smart-tv` (tv); robots.txt blocks only `/cgi-bin/`.

## Files

All the code is in Python files (`scripts/*.py`), as the instructor asked: Airflow runs `.py` files, not notebooks. The Colab notebooks used to develop the scrapers (26-30 Oct) were removed from the repository on 8-Nov-2026.

| File | Task | Status |
|---|---|---|
| `scripts/common.py` | fetch, raw files, price parsing, offer document | **ready** |
| `scripts/overlap_test.py` | A1 — products on 2+ sites per category (keep a category only with 20+) | **done 25-Oct**: phones 53-63, TVs 19-20, ACs 6 (dropped) |
| `scripts/scraper_dream2000.py` | A2 — Shopify `products.json`, one offer per variant | **done 26-Oct** |
| `scripts/mongo_load.py` | A3 — `catalog.offers` + `catalog.offers_quarantine` (reasons: no price / no stock state / out of scope), indexes, no duplicates on re-load | **done 26-Oct** on the real MongoDB (local, no auth); offline test `tests/test_mongo_load.py` (15 checks). Sites accepted: `OFFER_SITES` in `.env` (default `xprs,dream2000,jumia,elghazawy`); a new site is added there, not in the code |
| `scripts/scraper_xprs.py` | A5 — Shopify `products.json`, same code as Dream 2000 (replaces 2B, which blocks bots) | **done 27-Oct** |
| `scripts/scraper_jumia.py` | A6 — HTML category pages (`?page=N`) | **done 27-Oct**; not run since 2-Nov (HTTP 403) |
| `scripts/scraper_elghazawy.py` | A10 — HTML search pages (`?page=N`) | **done 8-Nov**; brand and price fixes 9-Nov; offline test `tests/test_scraper_elghazawy.py` (5 tests) |
| `05_etl/config/*.csv` | A7 — brand / suffix / category lists | **done 27-Oct** (El Ghazawy categories added 9-Nov) |

## Steps

### 1. Scrapers (A2, A5, A6, A10)

`05_etl/dags/prices_daily_dag.py` runs the scrapers at **06:00 Cairo time every day** (tasks `extract_dream2000`, `extract_xprs`,
`extract_elghazawy`, in parallel), then `store_offers_mongodb` (`mongo_load.py`), `validate_match_load_prices` and
`quality_check`.

| Site | Script (run by Airflow) | Function called | Output |
|---|---|---|---|
| Dream 2000 | `scripts/scraper_dream2000.py` | `run(out_dir)` | `data/offers/offers_dream2000_<date>.json` |
| XPRS | `scripts/scraper_xprs.py` | `run(out_dir)` | `data/offers/offers_xprs_<date>.json` |
| El Ghazawy | `scripts/scraper_elghazawy.py` | `run(out_dir)` | `data/offers/offers_elghazawy_<date>.json` |

To run one scraper by hand (from the repository folder): `python 02_nosql/scripts/scraper_elghazawy.py` (add `--sample` for the first 2 pages of each category only).
Offline tests (no internet, no MongoDB): `python 02_nosql/tests/test_scraper_elghazawy.py` and `python 02_nosql/tests/test_mongo_load.py`.

Before 9-Nov the scrapers were run by hand in Colab (26-30 Oct) with the same code.

Output of the last cell, 29-Oct-2026:
```
dream2000: 583 offers | quarantine: 0          -> dream2000_offers_2026-10-29.json
xprs:      per category: {'phone': 336, 'tv': 21}  no price: 0   -> xprs_offers_2026-10-29.json
jumia:     per category: {'phone': 558, 'tv': 399} no price: 0   -> jumia_offers_2026-10-29.json
```
Jumia blocked the phone pages with HTTP 403 at page 13 on 27-Oct; the scraper stops there and keeps what it has (no work-around).

Screenshots: `images/` (runs of 26-29 Oct).

### 2. Overlap test (A1)
Done 25-Oct-2026 in Colab (same code as `scripts/overlap_test.py`) on Dream 2000 + XPRS + Jumia. Match key = `brand|category|model` (phones: model + pro/max words, no RAM / storage / colour; TVs and ACs: model code). The matched products are saved in `overlap_matches.csv`.

| Category | Products on 2+ sites | Decision |
|---|---|---|
| phone | 53-63 (23 on all three) | keep |
| tv | 19-20 | keep for now, recount after the first full scrape |
| ac | 6 | **dropped** (Mahmoud, 25-Oct) |

TV recount after the full scrape: 26 models on 2+ sites on 27-Oct (30 with the A7 lists), 27 on 29-Oct -> **TVs stay**.

2B (2b.com.eg) was replaced by XPRS: it blocks bots with Cloudflare (HTTP 403); we did not work around it.

### 3. Load into MongoDB (A3)
`python 02_nosql/scripts/mongo_load.py data/offers/offers_*_<date>.json` — load the same files twice: the counts must not change.
Offline test (no MongoDB needed): `pip install mongomock` then `python 02_nosql/tests/test_mongo_load.py`.
```
# run 1 and run 2 on 26-Oct-2026 (local MongoDB on my laptop)
py -3.13 "mongo_load (1).py" ..\..\dream2000_offers_2026-10-26.json
2026-10-26 23:53:21,542 INFO Loaded {'read': 557, 'offers': 557, 'quarantine': 0, 'refused': 0}; quarantine reasons {}

py -3.13 "mongo_load (1).py" ..\..\dream2000_offers_2026-10-26.json
2026-10-26 23:54:55,500 INFO Loaded {'read': 557, 'offers': 557, 'quarantine': 0, 'refused': 0}; quarantine reasons {}
# same counts on the second run = no duplicates
```

### 4. Daily scraping from 27 October (A4)
| Date | Dream 2000 | XPRS | Jumia |
|---|---|---|---|
| 2026-10-27 | 557 | 345 | 904 |
| 2026-10-28 | — | — | — |
| 2026-10-29 | 583 | 357 | 957 |
| 2026-10-30 | 561 | 362 | — (Jumia 503 / timeout) |

28-Oct was missed (prices can only be scraped on the day itself). Until the DAG took over, each day the three scrapers were run in Colab, the three JSON files downloaded to the laptop, then loaded one by one:
```
py -3.13 "mongo_load (1).py" ..\..\dream2000_offers_2026-10-29.json
py -3.13 "mongo_load (1).py" ..\..\xprs_offers_2026-10-29.json
py -3.13 "mongo_load (1).py" ..\..\jumia_offers_2026-10-29.json
# offers loaded: 583 / 357 / 957 (same counts as Colab)
```
If the loader prints `ServerSelectionTimeoutError ... localhost:27017`, MongoDB is stopped: open **Services** > **MongoDB Server** > **Start**, then run the command again.

Run the three scrapers and the loader every day until the Airflow DAG takes over (N5). Keep a line per day here: date, offers per site.

**Move the history into the pipeline (review 3-Nov-2026):** copy every daily file (27, 29, 30, 31 Oct and later) into `data/offers/` on the machine that runs Docker, rename them `offers_<site>_<date>.json`, then load them all into the stack's MongoDB with one command:
```
python 02_nosql/scripts/mongo_load.py "data/offers/offers_*.json"
```
The next run of `prices_daily_dag` (or `python 05_etl/scripts/load_prices.py`) loads every day into the warehouse.

### 5. Brand and suffix lists (A7)
Fill `05_etl/config/brand_aliases.csv`, `model_suffixes.csv` and `category_map.csv` from the first full scrape.

Done 27-Oct-2026 in Colab, from the 27-Oct scrape (Dream 2000 557, XPRS 345, Jumia 904 offers).

| File | Rows | What it does | Result |
|---|---|---|---|
| `category_map.csv` | 24 | site category -> phone / tv | all 24 site categories mapped |
| `brand_aliases.csv` | 13 | other spelling -> one brand (after lower case) | 86 brand names -> 71 |
| `model_suffixes.csv` | 17 | prefix / suffix removed from TV model codes (`*` = all brands) | TV models on 2+ sites: 26 -> 30 |

Not fixed by the lists (for `manual_matches.csv`): XPRS writes some Samsung codes without the year letter (`43F6000` vs `43F6000F`); Dream 2000 `UA85U8000FU` and `Q55Q6F`.

Decided 27-Oct-2026 (Mahmoud): offers with brand "Renewed" (10 refurbished iPhones on Jumia) are excluded from matching.

### 6. Queries and export (A8)
Count offers per site and category, average price per category and site, in-stock share; `mongoexport` to CSV in `data/`.

**Done 27-Oct-2026** in the MongoDB shell of Compass (`use catalog`), on all loaded days (26-Oct = Dream 2000 only, 27-Oct = three sites).

Total: `db.offers.countDocuments()` -> **2363** (1806 on 27-Oct + 557 on 26-Oct), `offers_quarantine` = 0.

Group used by the three queries:
```
{$group:{_id:{date:"$snapshot_date",site:"$site",category:"$category"}, ... }}
```
- offers: `offers:{$sum:1}`
- average price: `avg_price:{$avg:"$sale_price"}`
- in-stock share: `in_stock_pct:{$avg:{$cond:["$in_stock",100,0]}}`

| Date | Site | Category | Offers | Avg price (EGP) | In stock |
|---|---|---|---|---|---|
| 2026-10-26 | dream2000 | phone | 500 | 31,899 | 60.8% |
| 2026-10-26 | dream2000 | tv | 57 | 18,557 | 93.0% |
| 2026-10-27 | dream2000 | phone | 500 | 34,766 | 61.0% |
| 2026-10-27 | dream2000 | tv | 57 | 21,963 | 93.0% |
| 2026-10-27 | jumia | phone | 478 | 23,036 | 100.0% |
| 2026-10-27 | jumia | tv | 426 | 18,373 | 100.0% |
| 2026-10-27 | xprs | phone | 324 | 38,347 | 44.4% |
| 2026-10-27 | xprs | tv | 21 | 40,861 | 100.0% |

Notes: Jumia is always 100% in stock because its category pages only list items that can be bought. 27-Oct numbers were checked against the JSON files (same values).

Export (MongoDB Database Tools 100.20.0):
```
"C:\Program Files\MongoDB\Tools\100\bin\mongoexport.exe" --db=catalog --collection=offers --type=csv --fields=site,site_product_id,snapshot_date,scraped_at,url,title,brand_raw,model_raw,ean,category_site,category,sale_price,original_price,discount_pct,currency,stock_text,in_stock,seller,source_format,raw_file --out=data\offers.csv
exported 2363 records
```
Screenshots: `images/` (A8 counts, average price, in-stock share, mongoexport).

## Deliverables
- [x] scrapers (`.py`: XPRS, Dream 2000, El Ghazawy; Jumia until 1-Nov) · [x] `mongo_load.py` · [x] overlap test result · [x] daily snapshots · [x] lists in `05_etl/config/` · [x] queries + CSV · [x] `images/`

