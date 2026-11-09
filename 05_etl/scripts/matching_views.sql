-- matching_views.sql - which products are matched across sites and which are not.   Added 6-Nov-2026 (instructor's request).
-- Run in DBeaver on ecommerce_dw after 03_dwh/scripts/schema.sql (re-runnable). Power BI can import every view.
--
--   v_product_crosswalk   one row per real product: our product_key next to the product id and URL on every site
--                         (Shopify handle:variant_id on XPRS and Dream 2000, SKU on Jumia, product id on El Ghazawy), and how it was matched
--   v_matching_status     per category and site: offers, offers matched with another site, single-site offers,
--                         and the match method (ean / model_code / name_spec / manual / new)
--   v_unmatched_offers    the offers seen in the last 7 days whose product is on ONE site only - the review list
--                         (05_etl/scripts/match_review.py turns it into a file with suggested matches)

DROP VIEW IF EXISTS v_unmatched_offers, v_matching_status, v_product_crosswalk CASCADE;

-- one row per product; the four sites as columns (jumia: history 27-Oct to 1-Nov), any later site in other_sites
CREATE VIEW v_product_crosswalk AS
SELECT
    dp.product_key,
    dp.product_code,
    dp.category,
    dp.brand,
    dp.display_name,
    COUNT(DISTINCT pm.site_key)                                                        AS site_count,
    STRING_AGG(DISTINCT pm.match_method, ', ')                                         AS match_methods,
    STRING_AGG(pm.site_product_id, ' | ') FILTER (WHERE ds.site_code = 'xprs')        AS xprs_product_id,
    MIN(pm.url)                           FILTER (WHERE ds.site_code = 'xprs')        AS xprs_url,
    STRING_AGG(pm.site_product_id, ' | ') FILTER (WHERE ds.site_code = 'dream2000')   AS dream2000_product_id,
    MIN(pm.url)                           FILTER (WHERE ds.site_code = 'dream2000')   AS dream2000_url,
    STRING_AGG(pm.site_product_id, ' | ') FILTER (WHERE ds.site_code = 'jumia')       AS jumia_product_id,
    MIN(pm.url)                           FILTER (WHERE ds.site_code = 'jumia')       AS jumia_url,
    STRING_AGG(pm.site_product_id, ' | ') FILTER (WHERE ds.site_code = 'elghazawy')   AS elghazawy_product_id,
    MIN(pm.url)                           FILTER (WHERE ds.site_code = 'elghazawy')   AS elghazawy_url,
    STRING_AGG(ds.site_code || ':' || pm.site_product_id, ' | ')
        FILTER (WHERE ds.site_code NOT IN ('xprs', 'dream2000', 'jumia', 'elghazawy')) AS other_sites,
    MAX(pm.last_seen_date)                                                             AS last_seen_date
FROM dim_product dp
JOIN product_map pm ON pm.product_key = dp.product_key
JOIN dim_site    ds ON ds.site_key    = pm.site_key
GROUP BY dp.product_key, dp.product_code, dp.category, dp.brand, dp.display_name;

-- matched = the offer's product is sold on at least one other site
CREATE VIEW v_matching_status AS
WITH offer AS (
    SELECT pm.site_key, pm.site_product_id, pm.match_method, dp.category,
           (SELECT COUNT(DISTINCT pm2.site_key) FROM product_map pm2 WHERE pm2.product_key = pm.product_key) AS site_count
    FROM product_map pm
    JOIN dim_product dp ON dp.product_key = pm.product_key
)
SELECT
    o.category,
    ds.site_code,
    COUNT(*)                                                       AS offers,
    COUNT(*) FILTER (WHERE o.site_count >= 2)                      AS matched_offers,
    COUNT(*) FILTER (WHERE o.site_count = 1)                       AS single_site_offers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE o.site_count >= 2) / COUNT(*), 1) AS matched_pct,
    COUNT(*) FILTER (WHERE o.match_method = 'ean')                 AS by_ean,
    COUNT(*) FILTER (WHERE o.match_method IN ('model_code', 'name_spec')) AS by_key,
    COUNT(*) FILTER (WHERE o.match_method = 'manual')              AS by_manual,
    COUNT(*) FILTER (WHERE o.match_method = 'new')                 AS without_key
FROM offer o
JOIN dim_site ds ON ds.site_key = o.site_key
GROUP BY ROLLUP (o.category, ds.site_code);

-- the review list: offers of the last 7 days whose product is on one site only, with the latest price
CREATE VIEW v_unmatched_offers AS
WITH single AS (
    SELECT product_key FROM product_map GROUP BY product_key HAVING COUNT(DISTINCT site_key) = 1
),
latest AS (
    SELECT DISTINCT ON (f.site_key, f.site_product_id) f.site_key, f.site_product_id, f.sale_price_egp, d.full_date
    FROM fact_price_daily f
    JOIN dim_date d ON d.date_key = f.date_key
    ORDER BY f.site_key, f.site_product_id, f.date_key DESC
)
SELECT
    ds.site_code,
    pm.site_product_id,
    dp.category,
    dp.brand,
    dp.product_code,
    dp.ram_gb,
    dp.storage_gb,
    dp.screen_size_in,
    pm.match_method,
    pm.title_last AS title,
    pm.url,
    l.sale_price_egp,
    l.full_date   AS last_price_date
FROM product_map pm
JOIN single      s  ON s.product_key  = pm.product_key
JOIN dim_product dp ON dp.product_key = pm.product_key
JOIN dim_site    ds ON ds.site_key    = pm.site_key
LEFT JOIN latest l  ON l.site_key = pm.site_key AND l.site_product_id = pm.site_product_id
WHERE pm.last_seen_date >= (SELECT MAX(last_seen_date) FROM product_map) - 7;
