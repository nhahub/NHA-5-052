-- oltp.sql - MySQL OLTP database of our store (synthetic sales).        SKELETON - task H1 (Eng. Hussein), due 26-Oct.
-- Source of truth: docs/data_dictionary.xlsx, sheet OLTP_MySQL (types, keys, CHECK rules, notes).
-- Run in DBeaver on the MySQL container (localhost:3306), as root or oltp_user.
--
-- Rules:
--   * ONE character set and collation everywhere: utf8mb4 / utf8mb4_0900_ai_ci (mixing collations broke joins on 21-Oct).
--   * Load order: customers, products -> orders -> order_items (foreign keys).
--   * Index on orders.order_purchase_ts (the incremental ETL filters on it).

CREATE DATABASE IF NOT EXISTS ecommerce_oltp CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ecommerce_oltp;

DROP TABLE IF EXISTS order_items, orders, products, customers;

-- customers (4 columns): customer_id PK VARCHAR(10), governorate VARCHAR(30), city VARCHAR(60), signup_date DATE
-- TODO H1: CREATE TABLE customers (...) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- products (6 columns): product_id PK VARCHAR(10), product_code VARCHAR(120) UNIQUE (= dim_product.product_code),
--   category VARCHAR(10) CHECK in ('phone','tv'), display_name VARCHAR(150), list_price_egp DECIMAL(10,2) CHECK > 0,
--   is_active TINYINT(1)
-- TODO H1: CREATE TABLE products (...)

-- orders (6 columns): order_id PK VARCHAR(12), customer_id FK -> customers, order_purchase_ts DATETIME + INDEX,
--   order_status VARCHAR(15) CHECK in ('delivered','canceled','returned'),
--   payment_method VARCHAR(20) CHECK in ('cash_on_delivery','card','installments','wallet'),
--   loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- TODO H1: CREATE TABLE orders (...)

-- order_items (5 columns): order_id FK -> orders, item_no SMALLINT CHECK >= 1, PRIMARY KEY (order_id, item_no),
--   product_id FK -> products, quantity SMALLINT CHECK > 0, unit_price_egp DECIMAL(10,2) CHECK > 0
-- TODO H1: CREATE TABLE order_items (...)

-- Check after running (paste the output in 01_oltp.md):
--   SHOW TABLES;  SHOW INDEX FROM orders;
--   SELECT table_name, table_collation FROM information_schema.tables WHERE table_schema = 'ecommerce_oltp';
