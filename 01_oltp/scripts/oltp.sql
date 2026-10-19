-- ============================================================
-- Project: E-Commerce Data Integration & Analytics Pipeline
-- Module: 01_oltp
-- Database: ecommerce_oltp (MySQL)
-- Purpose: Create the operational schema for the Olist dataset
-- Based on: ECommerce_Data_Dictionary_v3.2
-- ============================================================

-- Create the database with Unicode support for city names/text.
CREATE DATABASE IF NOT EXISTS ecommerce_oltp
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ecommerce_oltp;

-- ------------------------------------------------------------
-- 1. Category translation
-- Loaded before products. No FK from products to this table,
-- because some source product categories have no translation.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS category_translation (
    product_category_name VARCHAR(60) NOT NULL,
    product_category_name_english VARCHAR(60) NOT NULL,
    CONSTRAINT pk_category_translation
        PRIMARY KEY (product_category_name)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. Customers
-- customer_id identifies the source customer record used by an
-- order. customer_unique_id may repeat across customer records.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(32) NOT NULL,
    customer_unique_id VARCHAR(32) NOT NULL,
    customer_zip_code_prefix CHAR(5) NOT NULL,
    customer_city VARCHAR(100) NOT NULL,
    customer_state CHAR(2) NOT NULL,
    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 3. Sellers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sellers (
    seller_id VARCHAR(32) NOT NULL,
    seller_zip_code_prefix CHAR(5) NOT NULL,
    seller_city VARCHAR(100) NOT NULL,
    seller_state CHAR(2) NOT NULL,
    CONSTRAINT pk_sellers PRIMARY KEY (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 4. Products
-- Category translation is a lookup, not a mandatory FK, because
-- some product categories do not have a translation row.
-- The original Olist spelling "lenght" is used in source columns
-- only; these fields remain in MySQL even though the warehouse
-- does not currently load them.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(32) NOT NULL,
    product_category_name VARCHAR(60) NULL,
    product_name_lenght SMALLINT NULL,
    product_description_lenght SMALLINT NULL,
    product_photos_qty SMALLINT NULL,
    product_weight_g INT NULL,
    product_length_cm SMALLINT NULL,
    product_height_cm SMALLINT NULL,
    product_width_cm SMALLINT NULL,
    CONSTRAINT pk_products PRIMARY KEY (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 5. Orders
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(32) NOT NULL,
    customer_id VARCHAR(32) NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    order_purchase_timestamp DATETIME NOT NULL,
    order_approved_at DATETIME NULL,
    order_delivered_carrier_date DATETIME NULL,
    order_delivered_customer_date DATETIME NULL,
    order_estimated_delivery_date DATETIME NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_orders PRIMARY KEY (order_id),
    CONSTRAINT fk_orders_customers
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CONSTRAINT chk_orders_status CHECK (
        order_status IN (
            'created', 'approved', 'invoiced', 'processing',
            'shipped', 'delivered', 'unavailable', 'canceled'
        )
    ),
    -- Supports date filtering and the incremental-load marker.
    INDEX idx_orders_purchase_timestamp (order_purchase_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 6. Order items
-- One row represents one item in an order.
-- Composite PK prevents the same item number being repeated
-- within the same order.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    order_id VARCHAR(32) NOT NULL,
    order_item_id SMALLINT NOT NULL,
    product_id VARCHAR(32) NOT NULL,
    seller_id VARCHAR(32) NOT NULL,
    shipping_limit_date DATETIME NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    freight_value DECIMAL(10,2) NOT NULL,
    CONSTRAINT pk_order_items PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT fk_order_items_orders
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_order_items_products
        FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT fk_order_items_sellers
        FOREIGN KEY (seller_id) REFERENCES sellers(seller_id),
    CONSTRAINT chk_order_items_id CHECK (order_item_id >= 1),
    CONSTRAINT chk_order_items_price CHECK (price > 0),
    CONSTRAINT chk_order_items_freight CHECK (freight_value >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 7. Order payments
-- Some orders have multiple payment rows, so the PK is composite.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_payments (
    order_id VARCHAR(32) NOT NULL,
    payment_sequential SMALLINT NOT NULL,
    payment_type VARCHAR(20) NOT NULL,
    payment_installments SMALLINT NOT NULL,
    payment_value DECIMAL(10,2) NOT NULL,
    CONSTRAINT pk_order_payments PRIMARY KEY (order_id, payment_sequential),
    CONSTRAINT fk_order_payments_orders
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT chk_payment_sequential CHECK (payment_sequential >= 1),
    CONSTRAINT chk_payment_type CHECK (
        payment_type IN ('credit_card', 'boleto', 'voucher', 'debit_card', 'not_defined')
    ),
    CONSTRAINT chk_payment_installments CHECK (payment_installments >= 0),
    CONSTRAINT chk_payment_value CHECK (payment_value >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- 8. Order reviews
-- review_id can appear on more than one order, so use both
-- review_id and order_id as the composite primary key.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_reviews (
    review_id VARCHAR(32) NOT NULL,
    order_id VARCHAR(32) NOT NULL,
    review_score TINYINT NOT NULL,
    review_comment_title VARCHAR(100) NULL,
    review_comment_message TEXT NULL,
    review_creation_date DATETIME NOT NULL,
    review_answer_timestamp DATETIME NOT NULL,
    CONSTRAINT pk_order_reviews PRIMARY KEY (review_id, order_id),
    CONSTRAINT fk_order_reviews_orders
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT chk_review_score CHECK (review_score BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- End of schema creation.
-- Data loading is done separately, in parent-before-child order.
