# Module 5 — ETL and Pipelines (Python and Apache Airflow)

**Owner:** Eng. Nouran Elshwehy

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Two pipelines

| Pipeline | DAG | Flow | etl_state.pipeline |
|---|---|---|---|
| Prices | `dags/prices_daily_dag.py` (06:00 Cairo) | 3 scrapers (XPRS, Dream 2000, El Ghazawy) → MongoDB → validate + **match** + load `fact_price_daily` → quality check | `prices_daily` |
| Sales | `dags/sales_daily_dag.py` (08:00 Cairo) | generate the day's orders → MySQL → incremental load `fact_sales` → quality check | `orders_incremental` |

Both commit facts and the `etl_state` row in one transaction; a failed run is recorded and re-raised (Airflow retries).

**Sites (9-Nov-2026):** Jumia answers HTTP 403 since 2-Nov-2026, so `prices_daily_dag.SITES` is now `dream2000, xprs, elghazawy`. The quality check receives the same list (`check_prices(..., sites=SITES)`): a site the team stopped on purpose is not counted as "0 offers today", but a site of the list that returns too few offers still fails the DAG (70% rule). Jumia's prices of 27-Oct to 1-Nov stay in the warehouse.

## Files

| File | Task | Status |
|---|---|---|
| `scripts/mysqlconnect.py`, `scripts/postgresqlconnect.py` | connections (settings from `.env`) | **ready** |
| `scripts/etl_common.py` | watermark, run log, MongoDB connection | **ready** |
| `scripts/etl_state.sql` | control table | **ready** |
| `scripts/matching.py` | N2 — the integration step | **done** |
| `scripts/load_prices.py` | N3 — MongoDB → `fact_price_daily` | **done** |
| `scripts/automation.py` | N4 — MySQL → `fact_sales` (incremental) | **done** |
| `scripts/quality_checks.py` | N5 / N6 — checks that fail the DAG | **done** |
| `dags/prices_daily_dag.py`, `dags/sales_daily_dag.py` | N5 / N6 | **DAG ready, quality_check wired** |
| `config/*.csv` | matching lists (see `config/README.md`) | **filled** by A7 |
| `scripts/matching_views.sql` | crosswalk + matching status + review list (views for DBeaver / Power BI) | **done** (6-Nov) |
| `scripts/match_review.py` | level 3: the manual matching tool (export / import) | **done** (6-Nov), 12 tests |

## Matching in three levels (instructor's request, 6-Nov-2026)

| Level | How | Where | `match_method` |
|---|---|---|---|
| 1. Barcode | same EAN / GTIN on two sites | `matching.py` (used when a site gives a barcode) | `ean` |
| 2. Composite key (regex) | phones: brand + model + RAM + storage (e.g. `samsung\|phone\|a57\|8\|256`); TVs: brand + model code (e.g. `samsung\|tv\|43F6000F`) | `matching.py` + `config/*.csv` | `name_spec`, `model_code` |
| 3. Manual tool | a person links what levels 1–2 could not match, helped by suggestions | `match_review.py` → `config/manual_matches.csv` (applied first at every load) | `manual` |
| — | no key (title without model or memory) | the offer stays a single-site product | `new` |

**The crosswalk table** (our product id next to each site's id): `product_map` stores one row per site offer → `product_key`. The view `v_product_crosswalk` shows one row per product with `xprs_product_id` (Shopify `handle:variant_id`), `dream2000_product_id` (Shopify), `jumia_product_id` (SKU), `elghazawy_product_id`, the URL on each site and `other_sites` (any later site).

**Which products are matched and which are not:** `v_matching_status` (per category and site: offers, matched, single-site, % matched, and how many by each level) and `v_unmatched_offers` (the review list).

Setup (once, after `etl_state.sql`): run `05_etl/scripts/matching_views.sql` in DBeaver.

Weekly review (about 15 minutes):
```
python 05_etl/scripts/match_review.py export
-> 602 unmatched offers = 412 products, 42 with a suggestion -> data/review/match_review_2026-11-06.csv
```
Open the file in Excel. One product per group (its colour variants together, ids joined by `;`), up to 3 suggestions, the most similar first. Suggestions are only products of the same brand and category, the same storage (phones) or screen size (TVs), the same model numbers (Note 15 is never suggested for Note 17) and, for phones, the same variant words (Pro, Plus, Ultra, Lite, …). Check both links, then write `yes` in `decision` next to the right suggestion, or a product code in `other_product_code`. Save as CSV, then:
```
python 05_etl/scripts/match_review.py import data/review/match_review_2026-11-06.csv --by "Nouran" --apply-db
-> 1 manual matches added to 05_etl/config/manual_matches.csv
-> 1 offers moved in the warehouse
```
`--apply-db` moves the offer and its past price rows to the chosen product at once; without it the change applies at the next price load. Commit `manual_matches.csv` to GitHub (it is the record of who checked what, and when).

Test (6-Nov-2026, Aya's 13 daily files + a sample of 90 Elghazawy offers): the reviewer accepted XPRS `43F6000` → `43F6000F`; after the next load the offer stayed `manual` and the product was on 4 sites. Phones 75.9 % of offers matched, TVs 34.5 %.

## Steps

> **Note (review of 3-Nov-2026):** the outputs below that show 3 products, 8 price rows or 108 sales lines were produced with the test seed (`05_etl/tests/fixtures/seed_mongo.py`, 8 hand-written offers), not with scraped data. Replace them with the outputs of a run on the real offers files before the final presentation. A review run on all the real daily files (27-Oct to 2-Nov-2026, 7,530 offers) gave: 7,508 price rows, **143 phones and 30 TVs on 2+ sites on 29-Oct** (the day with the three sites), 181 products sold by our store, 511 order items over 6 days. See `REVIEW_FIXES.md`.

### 1. Start the services (N1)
`cp .env.example .env` then `docker compose up -d`; Airflow UI at http://localhost:8081.
```
docker compose ps
NAME                                               STATE     STATUS
ecommerce-data-pipeline-main-airflow-scheduler-1   running   Up ... (healthy)
ecommerce-data-pipeline-main-airflow-webserver-1   running   Up ... (healthy)
ecommerce-data-pipeline-main-postgres-1            running   Up ... (healthy)
ecommerce-mongodb                                  running   Up ...
ecommerce-mysql                                    running   Up ... (healthy)
ecommerce-postgres-dw                              running   Up ... (healthy)
```

### 2. Matching (N2) and price load (N3)
```
$env:MONGO_HOST="localhost";$env:MONGO_PORT="27017";$env:MONGO_USER="mongo_admin";$env:MONGO_PASSWORD="mongo_password";$env:MONGO_DB="catalog"
python 05_etl\scripts\load_prices.py
2026-10-31 ... INFO 2026-10-31 -> 8 offers, 8 inserted, checksum=217692.00

-- products on 2+ sites (matching quality)
SELECT COUNT(*) FROM dim_product;   -- 3
SELECT COUNT(*) FROM product_map;   -- 8
SELECT match_method, COUNT(*) FROM product_map GROUP BY match_method;
 name_spec  | 3
 model_code | 5

-- fact_price_daily per day
SELECT COUNT(*), MIN(sale_price_egp), MAX(sale_price_egp), SUM(sale_price_egp) FROM fact_price_daily;
 8 | 23500.00 | 30299.00 | 217692.00
```

### 3. Sales load (N4)
`python 05_etl/scripts/automation.py` — run twice: the second run must report no_data.
```
# run 1: full load
python 05_etl\scripts\automation.py
{'status': 'success', 'rows_in': 108, 'rows_out': 108}

# run 2: watermark prevents re-loading
python 05_etl\scripts\automation.py
{'status': 'no_data', 'rows_in': 0, 'rows_out': 0}

-- verification
SELECT COUNT(*) FROM fact_sales;              -- 108
SELECT COUNT(*) FROM dim_customer;            -- 3000
SELECT SUM(quantity), SUM(line_total_egp) FROM fact_sales;
 117 | 3188854.39

SELECT pipeline, status, batch_id, rows_in, rows_out, checksum FROM etl_state ORDER BY run_id;
 prices_daily       | failed  |            |   0 |   0 |          --
 prices_daily       | success | 2026-10-31 |   8 |   8 |   217692.00
 orders_incremental | success | 2026-10-31 | 108 | 108 | 3188854.39
```

### 4. DAGs (N5, N6)
Screenshots: DAG list, graph view, a green run, the logs, and `SELECT * FROM etl_state ORDER BY run_id DESC;`.
```
# sales_daily_dag test (proves the whole chain runs end-to-end with the real quality_check)
airflow dags test sales_daily_dag "2026-10-31T08:00:00+02:00"

# tasks (all success):
generate_orders_csv             ... wrote 85 rows; wrote 108 rows              -> SUCCESS
load_orders_mysql               ... orders 0/85; order_items 0/108             -> SUCCESS
extract_validate_transform_load ... {'status': 'no_data', 'rows_in': 0}        -> SUCCESS
quality_check                   ... Sales check OK: 108 rows, total_egp=3188854.39 -> SUCCESS

# DagRun Finished: dag_id=sales_daily_dag, ..., state=success
```

`prices_daily_dag` runs the 3 finished scrapers (`02_nosql/scripts/scraper_*.py`; earlier Aya ran the same code from
Google Colab and the real offers are not committed); the pipeline itself (validate → match → load → quality check) is
verified by the direct N3 run above.

### 5. Failure tests (N7 with H7)
Site unreachable · bad batch · database down — show the FAILED task, the retries and the `failed` row in `etl_state`.

**Test 1 — bad batch (missing dimension):** insert a product in MySQL whose `product_code` does not exist in `dim_product`, run `automation.py`:
```
ValueError: Missing dimensions (first 5): [('product', 'test|product|missing')]
-- etl_state wrote a 'failed' row (run_id=6, pipeline=orders_incremental)
```

**Test 2 — MySQL down:**
```
docker stop ecommerce-mysql
python 05_etl\scripts\automation.py
sqlalchemy.exc.DatabaseError: ... Can't connect to MySQL server on 'localhost:3306' (10061)
-- etl_state wrote a 'failed' row (run_id=7, pipeline=orders_incremental)
docker start ecommerce-mysql
```

**Test 3 — site unreachable (HTTP 403, evidenced in 02_nosql.md):** Jumia blocked phone pages with HTTP 403 at page 13 on 27-Oct-2026; the scraper stops and keeps what it has, and `etl_state` records the run that produced the data without duplicates.

**Proof that failures do not corrupt the warehouse** (after both tests):
```
SELECT 'fact_sales',COUNT(*) FROM fact_sales UNION ALL SELECT 'fact_price_daily',COUNT(*) FROM fact_price_daily UNION ALL SELECT 'dim_customer',COUNT(*) FROM dim_customer;
 fact_sales       |  108
 fact_price_daily |    8
 dim_customer     | 3000
```
Same numbers as before the tests: failed runs write only a `failed` row in `etl_state` and never move the watermark.

Full etl_state after both tests:
```
 run_id |      pipeline      | status  |  batch_id  |                  message
--------+--------------------+---------+------------+-------------------------------------------
      1 | prices_daily       | failed  |            | No module named 'pymongo'
      2 | prices_daily       | success | 2026-10-31 | 0 rejected
      3 | orders_incremental | success | 2026-10-31 | 85 new orders; 0 items rejected
      4 | orders_incremental | no_data |            | No new orders in MySQL
      5 | orders_incremental | no_data |            | No new orders in MySQL
      6 | orders_incremental | failed  |            | Missing dimensions (first 5): [('product', 'test|p
      7 | orders_incremental | failed  |            | (mysql.connector.errors.DatabaseError) 2003 (HY000
```

## Deliverables
- [x] matching, price and sales ETL · [x] two DAGs with green runs (sales_daily_dag tested end-to-end; prices_daily_dag logic verified by direct N3 run) · [x] failure-test log (2 synthetic + 1 real from 02_nosql) · [ ] `images/`