# Fixes after the technical review (3-Nov-2026)

This file lists every change made after the technical review of the local copy *project-nha5* (31-Oct-2026).
Each module owner should read the lines of his or her module, check the change, and push it from his or her own
GitHub account (the weekly evaluation is individual).

## Result on the real offers of 31-Oct-2026 (Dream 2000 581, XPRS 371, Jumia 31 from the one saved page)

| Measure | Before | After |
|---|---|---|
| Products on 2+ sites | **0** of 425 | **86** of 314 (84 phones, 2 TVs) |
| Offers loaded into `fact_price_daily` | 938 of 983 (45 Dream 2000 TVs dropped) | 983 of 983 |
| Groups of the overlap test A1 that get one model name | — | 70 of 73 (the other 3 are real differences: S26 / S26 FE, V70 / V70 FE, Honor T10) |
| Products sold by our store | 3 (seed data) | 86 (real matched products) |
| Price check when a site returns nothing | passes | fails: `jumia has 0 offers ... vs 31 on previous run` |
| Order item for a product that does not exist | silently dropped (INSERT IGNORE) | load fails with MySQL error 1452 |

Tests: 106 checks, all pass (94 under pytest + 12 MongoDB-loader checks); the shape-only matching tests were replaced by outcome tests on real titles. Both DAGs load in Airflow 2.9.2 with no import errors.
End-to-end run: PostgreSQL 16 + MySQL 8.0 + mongomock, all six report views and the materialized view.

## Result on all the daily files of Aya (27-Oct to 2-Nov-2026, 13 files, 7,530 offers)

Days and sites: 27-Oct Dream 2000 + Jumia · 28-Oct none · 29-Oct all three · 30-Oct Dream 2000 + XPRS · 31-Oct Dream 2000 + XPRS ·
1-Nov all three (Jumia TVs only) · 2-Nov Dream 2000 + XPRS.

| Measure | Result |
|---|---|
| Offers in MongoDB (loaded twice: no duplicates) | 7,530 |
| Rows in `fact_price_daily` | 7,508 (the 22 'Renewed' offers are excluded, decision of 27-Oct) |
| Products on 2+ sites on 29-Oct (the day with all three sites) | **143 phones** (64 on all three) and **30 TVs** |
| Products on 2+ sites at least once in the period | 152 phones, 31 TVs |
| XPRS on 29-Oct: 336 phone offers = 115 products (colours merged) | 93 products (81%) found on another site, covering 277 offers (82%); 18 of the 22 others are models the two other sites do not sell (e.g. Galaxy Z Fold 8 pre-order, iPhone Air, Oppo Find X9 Pro), 4 are other RAM/storage versions |
| Manual check of 22 random matched groups of 29-Oct | 22 correct |
| Price quality check per day | OK on 27, 29, 31-Oct and 1-Nov; **fails on 30-Oct and 2-Nov because Jumia was not scraped** (as it should) |
| Our store | 181 products, 6 days of orders, 511 order items; every sales check OK; a second ETL run reports no_data |
| Report 3 | real day-over-day price changes, e.g. 741 changes on Dream 2000 phones in week 44 |
| Report 6 (materialized view) | 361 rows, 165 products, 6 days; our price is 6.3% above the lowest market price on average |

Added on 6-Nov-2026: Arabic spelling variants (جالكسي, انفنكس, ريلمى, اي -> 60i, جو -> go) and series words that
some sites leave out ("Samsung A18" = "Samsung Galaxy A18"; "Apple 17 Pro" = "Apple iPhone 17 Pro").

Found and fixed during this run: the sales watermark (orders.loaded_at) has a precision of one second, so a batch loaded
in the same second as the previous ETL read was skipped. The ETL now reads only rows loaded before the current second
(`loaded_at < NOW()`); the rows of the current second are read by the next run.

## Changes

| # | Problem (review) | Change | Files | Owner |
|---|---|---|---|---|
| C1 | Matching gave 0 cross-site products | New keys: Arabic words translated, direction marks removed, model words before the first separator and before the memory, sorted; RAM = largest value up to 24 GB, storage = largest from 32 GB; Apple without RAM; '5g' kept only when a model is sold as 4G and 5G; TV code from the SKU or the longest code in the title; offers without a key become single-site products instead of being dropped | `05_etl/scripts/matching.py`, `05_etl/scripts/load_prices.py` | Nouran (N2) |
| C1 | No test of the outcome | Golden test on the A1 groups + 22 tests on real titles of the three sites | `05_etl/tests/test_matching_edge_cases.py`, `05_etl/tests/fixtures/a1_overlap_matches_2026-10-25.csv` | Nouran, Aya |
| C2 | Seed data presented as results | Seed moved to `05_etl/tests/fixtures/seed_mongo.py` and labelled TEST FIXTURE; a note in the guides of modules 01, 04 and 05 | guides | each owner |
| C3 | Daily files outside the pipeline | One command to load every daily file into the stack's MongoDB | `02_nosql/02_nosql.md`, `README.md` | Aya (A4) |
| C4 | `.gitignore` ignored nothing | Leading spaces removed (checked with `git check-ignore`); `*.bak` added; same fix in `.env.example` | `.gitignore`, `.env.example` | Mahmoud |
| C5 | Price check blind to a dead site | Loops over the previous run's sites; a missing site counts as 0 | `05_etl/scripts/quality_checks.py` | Nouran (N5) |
| C6 | Price check used `ds` (the day before) | Checks the dates returned by the load; Cairo date of the interval end when there was nothing new | `05_etl/dags/prices_daily_dag.py` | Nouran (N5) |
| I1 | Single-site products in reports 1, 2 | Only products sold on 2+ sites that day | `04_analytics/scripts/analysis_queries.sql` | H6 |
| I2 | Canceled and returned orders counted as sales | Units and revenue = delivered; canceled / returned as separate measures | same | H6 |
| I3 | Materialized view never refreshed | Task `refresh_report_view` at the end of `sales_daily_dag` | `05_etl/dags/sales_daily_dag.py` | Nouran (N6) |
| I4 | Late data lost | Prices: the watermark day is loaded again (idempotent); the row check sums all successful runs of the day. Sales: watermark on `orders.loaded_at` | `load_prices.py`, `quality_checks.py`, `automation.py` | Nouran (N3, N4) |
| I5 | One failed site lost the day; retries re-hit a blocked site | 403 → `AirflowFailException` (no retry); Jumia raises `BlockedError` when blocked before any offer; `store_offers_mongodb` runs with `all_done` on the files that exist | `prices_daily_dag.py`, `02_nosql/scripts/scraper_jumia.py` | Nouran, Aya |
| I6 | INSERT IGNORE hid bad rows; wrong counts | `ON DUPLICATE KEY UPDATE pk=pk` (errors raise), one commit per file with rollback, counts with `SELECT COUNT(*)` | `01_oltp/scripts/load_batch.py` | H5 |
| I7 | Product ids changed every run; products never refreshed | `product_id = 'P' + product_key`; names cut to 150 characters (MySQL column); task `refresh_reference_data` rebuilds products and loads customers / products | `generate_sales.py`, `sales_daily_dag.py` | H5, N6 |
| I8 | '+' removed, storage after RAM lost | Covered by C1 (tests: S26 / S26+ / S26 FE, "12GB RAM 256GB") | `matching.py` | Nouran |
| I9 | Tests froze weak choices | Removed the test that required INSERT IGNORE and the one that required the TODO; added outcome tests | `05_etl/tests/*` | all |
| — | Leftover files | `matching.py.bak`, `__pycache__`, `logs/`, `_dag_test.txt` removed; SKELETON / TODO headers removed from finished files; reports are views for Power BI; report 3 measures day-over-day price changes with LAG | several | Mahmoud |

## Added on 13-Nov-2026 (HTTP 429 on XPRS and Dream 2000)

On 10-Nov both Shopify sites answered the first page, then HTTP 429 ("too many requests"), even after two days without scraping (reported by Eng. Aya). A 429 is not a block: the site asks us to slow down. The old `fetch()` retried it after 2, 4, 8 and 16 seconds, and Airflow retried the task 3 more times.

| What | File | Owner |
|---|---|---|
| 5 seconds between requests on XPRS and Dream 2000 (was 1 second) | `02_nosql/scripts/scraper_xprs.py`, `scraper_dream2000.py` | Aya |
| No request for an empty page after a page with fewer than 250 products (about half the requests) | same files | Aya |
| HTTP 429: wait as long as the site asks (`Retry-After`; 60 s if it does not say), at most twice; then `RateLimitedError` = stop for the day. A site that asks for more than 5 minutes is left until tomorrow | `02_nosql/scripts/common.py` | Aya |
| `RateLimitedError` fails the extract task without Airflow retries, like a 403; the other sites are still stored (`all_done`) | `05_etl/dags/prices_daily_dag.py`, test `test_prices_block_fails_without_retry` | Nouran |
| Offline test of these rules (8 tests) | `02_nosql/tests/test_polite_fetch.py` | — |
| Docs: README, 02_nosql.md, data dictionary v4.5 | | Mahmoud |

Not done, on purpose: no browser-like User-Agent, no proxy or other network to avoid the limit. If the sites still answer 429 at 5 seconds, the day of that site is missing and the price check of that day fails; the prices already collected stay in the warehouse.

## Added on 9-Nov-2026 (review of the GitHub repo NHA-5-052, Jumia replaced, .py files only)

The GitHub repository still held the skeleton of 26-Oct plus the files of 8-Nov (El Ghazawy scraper); this version is the complete code.

| What | File | Owner |
|---|---|---|
| Jumia answers HTTP 403 since 2-Nov-2026: the DAG scrapes XPRS, Dream 2000 and **El Ghazawy**; Jumia's prices of 27-Oct to 1-Nov stay as history | `05_etl/dags/prices_daily_dag.py`, `03_dwh/scripts/schema.sql` (dim_site row 4), `05_etl/scripts/matching_views.sql` (El Ghazawy columns), `.env.example`, `docker-compose.yaml`, `02_nosql/scripts/mongo_load.py` (`OFFER_SITES`) | Nouran, Aya |
| The price quality check skips a site the team stopped on purpose (`sites=SITES`); before this, the first day without Jumia would fail the DAG ("jumia has 0 offers") | `05_etl/scripts/quality_checks.py`, test `test_check_prices_skips_a_retired_site` | Nouran |
| El Ghazawy scraper: the brand is the first known brand in the title (before: the first word, "Smart TV LG …" gave brand "Smart" and the offer could never match); a price is read with the currency before or after the number ("EGP 12,999" gave no price) | `02_nosql/scripts/scraper_elghazawy.py`, new offline test `02_nosql/tests/test_scraper_elghazawy.py` (5 tests) | Aya |
| All code in `.py` files (instructor): the Colab notebooks are not in the repository; guides updated | `02_nosql/02_nosql.md`, `README.md` | Aya, Mahmoud |
| `pip install -r requirements.txt` failed on Python 3.13 (no wheel for pandas 2.1.4 / psycopg2-binary 2.9.9) | `requirements.txt`: pandas 2.2.3, psycopg2-binary 2.9.10 | — |
| Data dictionary v4.4: source S5 El Ghazawy, Jumia stopped, dim_site row, Changelog | `docs/data_dictionary.xlsx` | Mahmoud |

Mini end-to-end test (9-Nov): offers of 1-Nov (XPRS, Dream 2000, Jumia) and 9-Nov (XPRS, Dream 2000, El Ghazawy) → MongoDB (mongomock) → warehouse: the El Ghazawy S25 Ultra 12/256 and LG 43LM6370PVA joined the products of the other sites (crosswalk on 4 and 3 sites); the quality check of 9-Nov passes with the DAG's sites and fails without them, as expected.

`docs/architecture.png` updated the same day (El Ghazawy in place of Jumia; Jumia 27 Oct – 1 Nov only). First real El Ghazawy run (Aya, 9-Nov, her laptop): 347 offers (268 phones, 79 TVs), 0 without a price, 5 of 5 prices checked by hand equal to the site, 347 loaded into MongoDB. Still to do: the first El Ghazawy run inside Airflow.

## Added on 6-Nov-2026 (instructor's request: three matching levels and a crosswalk)

| What | File | Owner |
|---|---|---|
| `v_product_crosswalk` (our product id next to the Shopify id / Jumia SKU / URL of every site), `v_matching_status` (matched vs single-site per category and site, by level), `v_unmatched_offers` (review list) | `05_etl/scripts/matching_views.sql` | Nouran |
| Manual matching tool: `export` (review file with up to 3 suggestions per unmatched product) and `import` (writes `manual_matches.csv`, `--apply-db` moves the offer and its price history) | `05_etl/scripts/match_review.py`, 12 tests in `05_etl/tests/test_match_review.py` | Nouran, Mahmoud |
| Suggestions never pair different model numbers (Redmi Note 15 / Note 17, Reno 15 / 16, iPhone 17 / 18) or a Pro / Lite / Plus with the plain model (in the test the number rule alone removed 132 wrong product pairs) | `match_review.py` | — |
| A new site is accepted by the MongoDB loader through `.env` (`OFFER_SITES=xprs,dream2000,jumia,elghazawy`), not by changing code; before this the 90 Elghazawy test offers were quarantined as "out of scope" | `02_nosql/scripts/mongo_load.py`, `.env.example`, test step 5 (15 checks) | Aya |
| LG OLED codes: prefix `OLED` removed (`OLED55B66LA` = `55B66LA`) | `05_etl/config/model_suffixes.csv` | Aya (A7) |

Test on Aya's 13 daily files + 90 Elghazawy offers (sample of 6-Nov-2026, taken from the first page of the phones and TVs categories only):

| Site | Phone offers matched | TV offers matched |
|---|---|---|
| XPRS | 289 of 350 (82.6 %) | 10 of 21 |
| Dream 2000 | 419 of 588 (71.3 %) | 31 of 60 |
| Jumia | 506 of 662 (76.4 %) | 124 of 461 |
| Elghazawy (sample) | 24 of 32 (75.0 %) | 42 of 58 (72.4 %) |

Elghazawy products: phones 12 of 15 and TVs 42 of 58 are on another site; 39 of its TVs are also on Jumia, 17 on XPRS or Dream 2000. Review list: 602 unmatched offers = 412 products, 42 with a suggestion (most are Samsung year letters, e.g. 43F6000 → 43F6000F, 32H5000 → 32H5000F).

## One-time steps after these changes (the keys and ids changed)

1. PostgreSQL (DBeaver, `ecommerce_dw`): run `03_dwh/scripts/schema.sql` (it drops and recreates the warehouse),
   then `TRUNCATE etl_state;` (or run `05_etl/scripts/etl_state.sql` on a new database), then `05_etl/scripts/matching_views.sql` and `04_analytics/scripts/analysis_queries.sql`.
2. MySQL (DBeaver): run `01_oltp/scripts/oltp.sql` (the synthetic sales are regenerated; product ids are now P + product_key).
3. Delete `data/sales/products.csv` (the old seed products). Keep `customers.csv`.
4. Load every real daily offers file: `python 02_nosql/scripts/mongo_load.py "data/offers/offers_*.json"`
   (and delete the seed offers if `seed_mongo.py` was run: `db.offers.deleteMany({raw_file: /^seed\//})` in Compass).
5. Run `prices_daily_dag`, then `sales_daily_dag`, and take the screenshots for the guides from this run.
6. If the warehouse was built before 9-Nov and you do not rebuild it: add the El Ghazawy row with the INSERT written under dim_site in `03_dwh/scripts/schema.sql`, then run `05_etl/scripts/matching_views.sql` again (new El Ghazawy columns).

## Still open (not changed)

* TVs: 30 TVs were on 2+ sites on the days when Jumia was scraped, but only 2 on the days without Jumia. Jumia is now blocked (HTTP 403 since 2-Nov); El Ghazawy takes its place: in the 6-Nov sample 42 of its 58 TVs were also on another site. Check the TV count after the first week of El Ghazawy runs.
* Some Jumia sellers publish placeholder prices (e.g. Honor Play 20A 4/128 at EGP 100,000 on 29-Oct, ten times the other sites). Add an outlier rule (for example: a price more than 3 times the median of the other sites goes to quarantine) or filter it in the reports.
* Samsung codes written without the year letter on XPRS (43F6000 vs 43F6000F): use the manual matching tool (`match_review.py`) — the pairs come first in the review file.
* Power BI dashboard (M5, M6) and the module guides with real outputs and screenshots.
* `schema.sql` still starts with DROP … CASCADE; `docker-compose.yaml` still installs unpinned packages.
