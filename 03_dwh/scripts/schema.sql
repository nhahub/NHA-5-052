-- schema.sql - PostgreSQL data warehouse ecommerce_dw.        SKELETON - task H2 (Eng. Hussein), due 28-Oct; run on the team server = H3.
-- Source of truth: docs/data_dictionary.xlsx, sheets Star_Schema, fact_price_daily, fact_sales, dim_product,
--                  product_map, dim_site, dim_customer, dim_date (types, keys, CHECK rules, indexes, notes).
-- Run in DBeaver on the warehouse (localhost:5433, database ecommerce_dw), then run 05_etl/scripts/etl_state.sql.
-- Create in this order (foreign keys): dim_date, dim_site, dim_customer, dim_product, product_map, fact_price_daily, fact_sales.

-- 1. dim_date (12 columns) - one row per day, 2026-01-01 to 2027-12-31 = 730 rows; is_weekend = Friday and Saturday
-- TODO H2: CREATE TABLE dim_date (...);
-- TODO H2: INSERT INTO dim_date SELECT ... FROM generate_series('2026-01-01'::date, '2027-12-31'::date, interval '1 day') AS d;
--          (TO_CHAR 'Day' and 'Month' pad with spaces: use TRIM; is_weekend = EXTRACT(ISODOW FROM d) IN (5, 6))

-- 2. dim_site (8 columns) - 3 rows: xprs, dream2000, jumia (values in the dim_site sheet note)
-- TODO H2: CREATE TABLE dim_site (...);  INSERT the 3 rows.

-- 3. dim_customer (6 columns) - UNIQUE (customer_id)
-- TODO H2

-- 4. dim_product (13 columns) - UNIQUE (product_code); CHECK category IN ('phone','tv'); indexes on category, brand
-- TODO H2

-- 5. product_map (10 columns) - PRIMARY KEY (site_key, site_product_id); FK product_key -> dim_product
-- TODO H2

-- 6. fact_price_daily (13 columns) - UNIQUE (date_key, site_key, site_product_id); CHECK sale_price_egp > 0;
--    indexes on date_key, product_key, site_key
-- TODO H2

-- 7. fact_sales (14 columns) - UNIQUE (order_id, item_no);
--    line_total_egp NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price_egp) STORED;
--    indexes on date_key, customer_key, product_key, order_status
-- TODO H2

-- Check after running (paste the output in 03_dwh.md):
--   SELECT COUNT(*) FROM dim_date;   -- 730
--   SELECT * FROM dim_site;          -- 3 rows
