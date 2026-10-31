-- analysis_queries.sql - views and queries for the six reports.        SKELETON - task H6 (Eng. Hussein), due 7-Nov.
-- Used by the Power BI dashboard (task M6, Mahmoud).
-- Rules (data dictionary v4.1):
--   * prices are NON-additive: use MIN / MAX / AVG, never SUM
--   * one product can have two offers on the same site and day (Jumia sellers): first take MIN(sale_price_egp)
--     per product, site and day
--   * sales data is synthetic: write it in every report title or note

-- 0. Base view: one price per product, site and day
-- TODO H6: CREATE VIEW v_price_product_site_day AS
--   SELECT date_key, product_key, site_key, MIN(sale_price_egp) AS price_egp, BOOL_OR(in_stock) AS in_stock
--   FROM fact_price_daily GROUP BY date_key, product_key, site_key;

-- 1. Cheapest site per product per day, and how often each site is the cheapest, by category
-- TODO H6: view v_cheapest_site

-- 2. Price spread between sites (max - min, and %) per product and category over time
-- TODO H6: view v_price_spread

-- 3. Price changes and discounts per site over time
-- TODO H6: query with GROUPING SETS ((site, category), (site), ())

-- 4. Stock availability per site and category
-- TODO H6: query with ROLLUP (category, site)

-- 5. Our sales by category, governorate and week (synthetic)
-- TODO H6: query with CUBE (category, governorate, iso_week)

-- 6. Our price compared with the lowest market price on the same day, and our units sold
-- TODO H6: CREATE MATERIALIZED VIEW mv_our_price_vs_market AS ...
--   (join fact_sales to v_price_product_site_day on product_key and date_key; REFRESH after each daily load)
