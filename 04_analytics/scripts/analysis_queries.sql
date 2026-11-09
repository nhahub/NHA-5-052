-- analysis_queries.sql - views for the six reports.        Task H6.
-- Used by the Power BI dashboard (task M6): import the v_report* views and mv_our_price_vs_market.
-- Rules (data dictionary v4.1):
--   * prices are NON-additive: use MIN / MAX / AVG, never SUM
--   * one product can have two offers on the same site and day (Jumia sellers): first take MIN(sale_price_egp)
--     per product, site and day
--   * a comparison between sites only makes sense for products sold on 2+ sites the same day (reports 1, 2, 6)
--   * our sales = DELIVERED orders; canceled and returned orders are shown as separate measures
--   * sales data is synthetic: write it in every report title or note
-- Revised 3-Nov-2026 after the review: single-site products removed from reports 1-2, delivered filter in 5-6,
--   report 3 measures real day-over-day price changes, every report is a view (Power BI reads views).
-- Run in DBeaver on the warehouse (localhost:5433, database ecommerce_dw), after 03_dwh/scripts/schema.sql.
-- Re-runnable: drops and recreates all views and the materialized view.
-- The materialized view is refreshed by sales_daily_dag (task refresh_report_view).

DROP MATERIALIZED VIEW IF EXISTS mv_our_price_vs_market CASCADE;
DROP VIEW IF EXISTS v_report5_our_sales, v_report4_stock, v_report3_price_changes, v_report2_price_spread,
                    v_report1_cheapest_site, v_cheapest_site, v_price_spread, v_price_product_site_day CASCADE;

-- 0. Base view: one price per product, site and day
CREATE VIEW v_price_product_site_day AS
SELECT
    p.date_key,
    p.product_key,
    p.site_key,
    MIN(p.sale_price_egp) AS price_egp,
    BOOL_OR(p.in_stock)   AS in_stock
FROM fact_price_daily p
GROUP BY p.date_key, p.product_key, p.site_key;

-- Spread per product and day (all products; site_count tells how many sites sell it that day)
CREATE VIEW v_price_spread AS
SELECT
    date_key,
    product_key,
    COUNT(DISTINCT site_key)                                                          AS site_count,
    MIN(price_egp)                                                                    AS min_price_egp,
    MAX(price_egp)                                                                    AS max_price_egp,
    MAX(price_egp) - MIN(price_egp)                                                   AS spread_egp,
    ROUND(100.0 * (MAX(price_egp) - MIN(price_egp)) / NULLIF(MIN(price_egp), 0), 2) AS spread_pct
FROM v_price_product_site_day
GROUP BY date_key, product_key;

-- 1a. Cheapest site per product per day - only products sold on 2+ sites that day
--     (ties broken by lowest site_key, so one row per product-date)
CREATE VIEW v_cheapest_site AS
SELECT DISTINCT ON (v.date_key, v.product_key)
    v.date_key,
    v.product_key,
    v.site_key,
    v.price_egp,
    s.site_count
FROM v_price_product_site_day v
JOIN v_price_spread s ON s.date_key = v.date_key AND s.product_key = v.product_key
WHERE s.site_count >= 2
ORDER BY v.date_key, v.product_key, v.price_egp ASC, v.site_key ASC;

-- 1b. Report 1: how often each site is the cheapest, by category
CREATE VIEW v_report1_cheapest_site AS
SELECT
    dp.category,
    ds.site_code,
    COUNT(*)                                                                  AS times_cheapest,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY dp.category), 2) AS pct_of_category
FROM v_cheapest_site cs
JOIN dim_site    ds ON ds.site_key    = cs.site_key
JOIN dim_product dp ON dp.product_key = cs.product_key
GROUP BY dp.category, ds.site_code;

-- 2. Report 2: price spread between sites per product, category and day - products on 2+ sites only
CREATE VIEW v_report2_price_spread AS
SELECT
    d.full_date,
    dp.category,
    dp.brand,
    dp.product_code,
    s.site_count,
    s.min_price_egp,
    s.max_price_egp,
    s.spread_egp,
    s.spread_pct
FROM v_price_spread s
JOIN dim_product dp ON dp.product_key = s.product_key
JOIN dim_date    d  ON d.date_key     = s.date_key
WHERE s.site_count >= 2;

-- 3. Report 3: price changes and discounts per site and category by week (GROUPING SETS)
--    price change = the same offer (site + site_product_id) compared with its previous scraped day
--    note: XPRS publishes no old price (compare_at_price), so its discount measures are empty
CREATE VIEW v_report3_price_changes AS
WITH offer_days AS (
    SELECT
        fp.*,
        LAG(fp.sale_price_egp) OVER (PARTITION BY fp.site_key, fp.site_product_id ORDER BY fp.date_key) AS prev_price_egp
    FROM fact_price_daily fp
)
SELECT
    d.year,
    d.iso_week,
    ds.site_code,
    dp.category,
    COUNT(*)                                                                        AS price_rows,
    COUNT(o.prev_price_egp)                                                         AS rows_with_previous_day,
    SUM(CASE WHEN o.prev_price_egp IS NOT NULL AND o.sale_price_egp <> o.prev_price_egp THEN 1 ELSE 0 END)
                                                                                    AS price_changes,
    ROUND(AVG(CASE WHEN o.prev_price_egp IS NOT NULL
                   THEN 100.0 * (o.sale_price_egp - o.prev_price_egp) / o.prev_price_egp END), 2)
                                                                                    AS avg_change_pct,
    ROUND(AVG(o.discount_pct), 2)                                                   AS avg_discount_pct,
    ROUND(100.0 * COUNT(o.discount_pct) / COUNT(*), 2)                              AS pct_rows_with_discount
FROM offer_days o
JOIN dim_site    ds ON ds.site_key    = o.site_key
JOIN dim_product dp ON dp.product_key = o.product_key
JOIN dim_date    d  ON d.date_key     = o.date_key
GROUP BY GROUPING SETS (
    (d.year, d.iso_week, ds.site_code, dp.category),
    (d.year, d.iso_week, ds.site_code),
    (d.year, d.iso_week)
);

-- 4. Report 4: stock availability per site and category (ROLLUP)
--    Jumia is left out: its category pages list only items that can be bought, so it is always 100% in stock
CREATE VIEW v_report4_stock AS
SELECT
    dp.category,
    ds.site_code,
    COUNT(*)                                                                              AS price_rows,
    SUM(CASE WHEN fp.in_stock THEN 1 ELSE 0 END)                                          AS in_stock_rows,
    ROUND(100.0 * SUM(CASE WHEN fp.in_stock THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS in_stock_pct
FROM fact_price_daily fp
JOIN dim_site    ds ON ds.site_key    = fp.site_key
JOIN dim_product dp ON dp.product_key = fp.product_key
WHERE ds.site_code <> 'jumia'
GROUP BY ROLLUP (dp.category, ds.site_code);

-- 5. Report 5: our sales by category, governorate and week (CUBE). Synthetic sales.
--    units and revenue = delivered orders; canceled and returned are separate measures
CREATE VIEW v_report5_our_sales AS
SELECT
    dp.category,
    dc.governorate,
    d.iso_week,
    SUM(fs.quantity)       FILTER (WHERE fs.order_status = 'delivered') AS units_sold,
    SUM(fs.line_total_egp) FILTER (WHERE fs.order_status = 'delivered') AS revenue_egp,
    COUNT(DISTINCT fs.order_id) FILTER (WHERE fs.order_status = 'delivered') AS delivered_orders,
    COUNT(DISTINCT fs.order_id) FILTER (WHERE fs.order_status = 'canceled')  AS canceled_orders,
    COUNT(DISTINCT fs.order_id) FILTER (WHERE fs.order_status = 'returned')  AS returned_orders
FROM fact_sales fs
JOIN dim_product  dp ON dp.product_key  = fs.product_key
JOIN dim_customer dc ON dc.customer_key = fs.customer_key
JOIN dim_date     d  ON d.date_key      = fs.date_key
GROUP BY CUBE (dp.category, dc.governorate, d.iso_week);

-- 6. Report 6: our price vs. lowest market price on the same day, and our units sold. Synthetic sales.
--    our price = average unit price of DELIVERED items; market = every site selling the product that day
--    To refresh after a daily load (done by sales_daily_dag):  REFRESH MATERIALIZED VIEW mv_our_price_vs_market;
CREATE MATERIALIZED VIEW mv_our_price_vs_market AS
WITH sales_agg AS (
    SELECT
        fs.date_key,
        fs.product_key,
        SUM(fs.quantity)                                      AS units_sold,
        SUM(fs.line_total_egp)                                AS revenue_egp,
        SUM(fs.line_total_egp) / NULLIF(SUM(fs.quantity), 0)  AS our_avg_unit_price_egp
    FROM fact_sales fs
    WHERE fs.order_status = 'delivered'
    GROUP BY fs.date_key, fs.product_key
),
market_agg AS (
    SELECT
        v.date_key,
        v.product_key,
        COUNT(*)         AS market_site_count,
        MIN(v.price_egp) AS lowest_market_price_egp,
        AVG(v.price_egp) AS avg_market_price_egp
    FROM v_price_product_site_day v
    GROUP BY v.date_key, v.product_key
)
SELECT
    s.date_key,
    s.product_key,
    dp.category,
    dp.brand,
    dp.model_key,
    s.units_sold,
    s.revenue_egp,
    s.our_avg_unit_price_egp,
    m.lowest_market_price_egp,
    m.avg_market_price_egp,
    s.our_avg_unit_price_egp - m.lowest_market_price_egp AS diff_vs_lowest_egp,
    CASE WHEN m.lowest_market_price_egp > 0
         THEN ROUND(100.0 * (s.our_avg_unit_price_egp - m.lowest_market_price_egp) / m.lowest_market_price_egp, 2)
         ELSE NULL
    END AS diff_vs_lowest_pct,
    m.market_site_count
FROM sales_agg s
JOIN market_agg  m  ON m.date_key    = s.date_key AND m.product_key = s.product_key
JOIN dim_product dp ON dp.product_key = s.product_key;

CREATE UNIQUE INDEX uk_mv_opvm_date_product ON mv_our_price_vs_market (date_key, product_key);

-- Check after running (paste the output in 04_analytics.md):
--   SELECT viewname FROM pg_views WHERE schemaname='public' ORDER BY viewname;      -- 9 views
--   SELECT matviewname, ispopulated FROM pg_matviews WHERE schemaname='public';
--   SELECT * FROM v_report1_cheapest_site;
--   SELECT category, COUNT(DISTINCT product_code), ROUND(AVG(spread_pct),1) FROM v_report2_price_spread GROUP BY 1;
--   SELECT COUNT(*) FROM mv_our_price_vs_market;
