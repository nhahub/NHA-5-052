# Module 4 — Analytics and Dashboard

**Owners:** Eng. Hussein Saeed (SQL), Mahmoud Dahroug (Power BI)

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Reports (data dictionary, sheet Star_Schema)
1. Cheapest site per product per day, and how often each site is the cheapest, by category
2. Price spread between sites (max − min, and %) per product and category over time
3. Price changes and discounts per site over time
4. Stock availability per site and category
5. Our sales by category, governorate and week (**synthetic** sales)
6. Our price against the lowest market price on the same day, and our units sold

Prices are non-additive: use MIN / MAX / AVG, never SUM.

## Files

| File | Task | Status |
|---|---|---|
| `scripts/analysis_queries.sql` | H6 — views, GROUPING SETS, ROLLUP, CUBE, materialized view | **done** |
| `Dashboard/ecommerce_dashboard.pbix` | M5 connect · M6 six report pages | **done** (20-Nov-2026, first data snapshot) |
| `Dashboard/ecommerce_dashboard.pdf` | the six pages exported to PDF (viewable on GitHub without Power BI) | **done** |

## Steps

> **Note (review of 3-Nov-2026):** the outputs below that show 3 products, 8 price rows or 108 sales lines were produced with the test seed (`05_etl/tests/fixtures/seed_mongo.py`, 8 hand-written offers), not with scraped data. Replace them with the outputs of a run on the real offers files before the final presentation. A review run on all the real daily files (27-Oct to 2-Nov-2026, 7,530 offers) gave: 7,508 price rows, **143 phones and 30 TVs on 2+ sites on 29-Oct** (the day with the three sites), 181 products sold by our store, 511 order items over 6 days. See `REVIEW_FIXES.md`.

> The reports are now views (`v_report1_cheapest_site` … `v_report5_our_sales`, plus `mv_our_price_vs_market`): import these in Power BI. Reports 1, 2 and 6 use only products sold on 2+ sites the same day; reports 5 and 6 count delivered orders only; Jumia and El Ghazawy are left out of report 4 (their listings show only items in stock, so they are always 100%); XPRS has no old prices, so it has no discounts in report 3.

### 1. Analytical SQL (H6)
```sql
-- file: 04_analytics/scripts/analysis_queries.sql
-- creates: v_price_product_site_day, v_cheapest_site, v_price_spread, mv_our_price_vs_market
-- plus 4 aggregation queries (GROUPING SETS / ROLLUP / CUBE / plain)
```

Execution on the warehouse:
```
Get-Content -Raw "04_analytics\scripts\analysis_queries.sql" | docker exec -i ecommerce-postgres-dw psql -U dw_user -d ecommerce_dw -v ON_ERROR_STOP=1
DROP MATERIALIZED VIEW
DROP VIEW
CREATE VIEW
CREATE VIEW
 category | site_code | times_cheapest | pct_of_category   -- report 1 (empty until fact_price_daily is loaded)
----------+-----------+----------------+-----------------
(0 rows)
CREATE VIEW
 year_month | site_code | category | distinct_products | ... -- report 3 GROUPING SETS (empty until loaded)
(0 rows)
 category | site_code | price_rows | in_stock_rows | in_stock_pct  -- report 4 ROLLUP (empty until loaded)
(0 rows)
 category | governorate | iso_week | units_sold | revenue_egp   -- report 5 CUBE (empty until loaded)
(0 rows)
SELECT 0
CREATE INDEX

-- verify views and matview exist
SELECT viewname FROM pg_views WHERE schemaname='public' ORDER BY viewname;
 v_cheapest_site
 v_price_product_site_day
 v_price_spread
(3 rows)

SELECT matviewname, ispopulated FROM pg_matviews WHERE schemaname='public';
 mv_our_price_vs_market | t
(1 row)
```

### 2. After the pipeline runs (facts populated)
```
REFRESH MATERIALIZED VIEW mv_our_price_vs_market;
SELECT COUNT(*) FROM mv_our_price_vs_market;   -- 3 (products × days with our sales + market prices)

 date_key | product_key | category | brand   | model_key           | units_sold | revenue_egp | our_avg_unit_price_egp | lowest_market_price_egp | diff_vs_lowest_egp | diff_vs_lowest_pct
----------+-------------+----------+---------+---------------------+------------+-------------+------------------------+-------------------------+--------------------+--------------------
 20261031 |           4 | tv       | lg      | 55U7000             |         29 |   708042.61 |     24415.262413793103 |                23500.00 | 915.262413793103   |               3.89
 20261031 |           1 | tv       | samsung | 55U8000H            |         38 |  1071377.83 |     28194.153421052632 |                26300.00 | 1894.153421052632  |               7.20
 20261031 |           6 | phone    | samsung | galaxy-a57-5g-ram|8|256 |   50 |  1409433.95 |     28188.679000000000 |                26295.00 | 1893.679000000000  |               7.20
(3 rows)
```

The three example rows confirm the SQL reports work: our average unit price per product/day is compared against the lowest market price of the same day, and the % difference is computed. Values are plausible (3–8% above the cheapest competitor) because our generated price = average market price ±5%.

### 3. Power BI (M5, M6)

**Data used (first snapshot).** The warehouse of the Docker stack (Eng. Nouran) was copied on 18-Nov-2026 and restored into a local PostgreSQL 17 (`localhost:5432`, database `ecommerce_dw`):

```
# on the Docker machine
docker exec ecommerce-postgres-dw pg_dump -U dw_user -d ecommerce_dw --inserts --no-owner --no-privileges -f /tmp/ecommerce_dw.sql
docker cp ecommerce-postgres-dw:/tmp/ecommerce_dw.sql .\ecommerce_dw.sql

# on the Power BI machine, in psql connected to the empty database ecommerce_dw
\set ON_ERROR_STOP on
\set QUIET on
\i 'C:/path/to/ecommerce_dw.sql'
SET search_path TO public;   -- the dump empties search_path for the session
```

The dump starts with `\restrict` / `\unrestrict` lines (psql commands), so it is restored with psql, not with DBeaver's SQL editor.

Row counts after the restore:

| Table | Rows |
|---|---|
| fact_price_daily | 1,302 (XPRS 371 + Dream 2000 581 on 31-Oct; El Ghazawy 350 on 14-Nov) |
| fact_sales | 104 (31-Oct) |
| dim_product | 382 (144 sold on 2+ sites) |
| dim_customer | 3,000 |

**Connection.** Power BI Desktop → Get data → PostgreSQL database → `localhost` / `ecommerce_dw` → Import. The five report views were selected in the Navigator. `mv_our_price_vs_market` is a materialized view and does not appear in the Navigator, so it was imported with *Advanced options → SQL statement*: `SELECT * FROM public.mv_our_price_vs_market`.

To use the Docker warehouse instead: Transform data → Data source settings → Change Source → `localhost:5433`.

**Pages (one per report).**

| Page | Source | Visual | Result on this snapshot |
|---|---|---|---|
| 1 Cheapest site | `v_report1_cheapest_site` | clustered columns: category × site, `times_cheapest` | phones: XPRS cheapest for 81 products, Dream 2000 for 2; TVs: Dream 2000 for 2 |
| 2 Price spread | `v_report2_price_spread` | table sorted by Difference %, totals off | 85 products on 2+ sites on 31-Oct; largest gap Xiaomi Redmi 15C 6/128: 7,699 vs 13,990 EGP (81.71%) |
| 3 Discounts | `v_report3_price_changes` | clustered columns: site × category, `avg_discount_pct` | El Ghazawy phones 9.1%, TVs 9.8%; Dream 2000 phones 7.9%, TVs 4.7%; XPRS has no old prices |
| 4 Stock | `v_report4_stock` | clustered columns: site × category, `in_stock_pct` | Dream 2000 phones 61%, TVs 98%; XPRS phones 46%, TVs 100% |
| 5 Our sales | `v_report5_our_sales` | clustered bars: governorate × category, `revenue_egp` | Cairo ≈ 533k EGP, Alexandria ≈ 366k, Giza ≈ 268k; 17 governorates with revenue, ≈ 2.42M EGP in all |
| 6 Our price vs market | `mv_our_price_vs_market` | clustered bars: brand, **Average** of `diff_vs_lowest_pct` | our store is above the lowest market price by 6% on average; Xiaomi +11.1%, Vivo +9.0%; LG −1.6%, Huawei and Fresh −0.8% |

**Settings that matter.**
- Reports 3, 4 and 5 use GROUPING SETS / ROLLUP / CUBE, so they contain subtotal rows with a blank site, category, governorate or week. Each visual has the filter *is not blank* on those columns; without it the subtotals are counted twice.
- Percentages are never summed: page 6 uses Average, and page 2 has totals off.
- `price_changes` in report 3 is 0 on this snapshot, because no site has two consecutive days yet. It will fill in when daily runs are loaded.

**Refresh.** When more days are loaded into the warehouse, take a new dump, restore it, then *Home → Refresh* in Power BI and export the PDF again.

## Deliverables
- [x] `analysis_queries.sql` · [x] `Dashboard/ecommerce_dashboard.pbix` · [x] `Dashboard/ecommerce_dashboard.pdf` (one page per report)
- [ ] Refresh with the daily price history before the final presentation