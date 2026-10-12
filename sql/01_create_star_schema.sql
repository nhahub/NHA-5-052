
-- =====================================================
-- Project: E-Commerce Data Integration & Analytics
-- Purpose: Create the core analytical star schema
-- Database: PostgreSQL
-- =====================================================

-- 1. Organize the database objects
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;


-- 2. Customer Dimension
CREATE TABLE IF NOT EXISTS analytics.dim_customer (
    customer_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    olist_customer_id TEXT NOT NULL UNIQUE,
    customer_unique_id TEXT NOT NULL,
    customer_city TEXT,
    customer_state TEXT,
    customer_zip_code_prefix TEXT
);


-- 3. Product Dimension
CREATE TABLE IF NOT EXISTS analytics.dim_product (
    product_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    olist_product_id TEXT NOT NULL UNIQUE,
    product_category_name TEXT,
    product_category_english TEXT,
    product_name_length INTEGER,
    product_description_length INTEGER,
    product_photos_qty INTEGER,
    product_weight_g NUMERIC(12, 2),
    product_length_cm NUMERIC(12, 2),
    product_height_cm NUMERIC(12, 2),
    product_width_cm NUMERIC(12, 2)
);


-- 4. Date Dimension
CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_of_month SMALLINT NOT NULL
        CHECK (day_of_month BETWEEN 1 AND 31),
    month_number SMALLINT NOT NULL
        CHECK (month_number BETWEEN 1 AND 12),
    month_name TEXT NOT NULL,
    quarter_number SMALLINT NOT NULL
        CHECK (quarter_number BETWEEN 1 AND 4),
    year_number INTEGER NOT NULL
);


-- 5. Sales Fact
-- Grain: One row per item in an order
CREATE TABLE IF NOT EXISTS analytics.fact_sales (
    sales_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    order_id TEXT NOT NULL,
    order_item_id INTEGER NOT NULL
        CHECK (order_item_id > 0),

    order_status TEXT NOT NULL,

    customer_key BIGINT NOT NULL
        REFERENCES analytics.dim_customer(customer_key),

    product_key BIGINT NOT NULL
        REFERENCES analytics.dim_product(product_key),

    purchase_date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    delivery_date_key INTEGER
        REFERENCES analytics.dim_date(date_key),

    purchase_timestamp TIMESTAMP NOT NULL,
    delivery_timestamp TIMESTAMP,

    item_price NUMERIC(12, 2) NOT NULL
        CHECK (item_price >= 0),

    freight_value NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (freight_value >= 0),

    CONSTRAINT uq_fact_sales_order_item
        UNIQUE (order_id, order_item_id)
);


-- 6. Indexes used by common analytical queries
CREATE INDEX IF NOT EXISTS idx_fact_sales_purchase_date
    ON analytics.fact_sales(purchase_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_sales_delivery_date
    ON analytics.fact_sales(delivery_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer
    ON analytics.fact_sales(customer_key);

CREATE INDEX IF NOT EXISTS idx_fact_sales_product
    ON analytics.fact_sales(product_key);

CREATE INDEX IF NOT EXISTS idx_dim_customer_state
    ON analytics.dim_customer(customer_state);

CREATE INDEX IF NOT EXISTS idx_dim_product_category
    ON analytics.dim_product(product_category_english);
