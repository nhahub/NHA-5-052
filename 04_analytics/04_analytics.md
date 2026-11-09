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
| `dashboard/*.pbix` | M5 connect · M6 six report pages | to do |

## Steps

> **Note (review of 3-Nov-2026):** the outputs below that show 3 products, 8 price rows or 108 sales lines were produced with the test seed (`05_etl/tests/fixtures/seed_mongo.py`, 8 hand-written offers), not with scraped data. Replace them with the outputs of a run on the real offers files before the final presentation. A review run on all the real daily files (27-Oct to 2-Nov-2026, 7,530 offers) gave: 7,508 price rows, **143 phones and 30 TVs on 2+ sites on 29-Oct** (the day with the three sites), 181 products sold by our store, 511 order items over 6 days. See `REVIEW_FIXES.md`.

> The reports are now views (`v_report1_cheapest_site` … `v_report5_our_sales`, plus `mv_our_price_vs_market`): import these in Power BI. Reports 1, 2 and 6 use only products sold on 2+ sites the same day; reports 5 and 6 count delivered orders only; Jumia is left out of report 4 (always 100% in stock); XPRS has no old prices, so it has no discounts in report 3.

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
Connect Power BI Desktop to PostgreSQL (`localhost:5433`, `ecommerce_dw`), import the views, build one page per report.

## Deliverables
- [x] `analysis_queries.sql` · [ ] `.pbix` · [ ] one screenshot per report page