-- oltp.sql - MySQL OLTP database of our store (synthetic sales).        Task H1 (Eng. Hussein).
-- Source of truth: docs/data_dictionary.xlsx, sheet OLTP_MySQL (types, keys, CHECK rules, notes).
-- Run in DBeaver on the MySQL container (localhost:3306), as root or oltp_user.
--
-- Rules:
--   * ONE character set and collation everywhere: utf8mb4 / utf8mb4_0900_ai_ci.
--   * Load order: customers, products -> orders -> order_items (foreign keys).
--   * Index on orders.order_purchase_ts (the incremental ETL filters on it).

CREATE DATABASE IF NOT EXISTS ecommerce_oltp
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE ecommerce_oltp;

DROP TABLE IF EXISTS order_items, orders, products, customers;

-- customers (4 columns): customer_id PK VARCHAR(10), governorate VARCHAR(30), city VARCHAR(60), signup_date DATE
CREATE TABLE customers (
    customer_id   VARCHAR(10)  NOT NULL,
    governorate   VARCHAR(30)  NOT NULL,
    city          VARCHAR(60)  NOT NULL,
    signup_date   DATE         NOT NULL,
    PRIMARY KEY (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- products (6 columns): product_id PK VARCHAR(10), product_code VARCHAR(120) UNIQUE,
--   category VARCHAR(10) CHECK in ('phone','tv'), display_name VARCHAR(150),
--   list_price_egp DECIMAL(10,2) CHECK > 0, is_active TINYINT(1)
CREATE TABLE products (
    product_id      VARCHAR(10)   NOT NULL,
    product_code    VARCHAR(120)  NOT NULL,
    category        VARCHAR(10)   NOT NULL,
    display_name    VARCHAR(150)  NOT NULL,
    list_price_egp  DECIMAL(10,2) NOT NULL,
    is_active       TINYINT(1)    NOT NULL,
    PRIMARY KEY (product_id),
    UNIQUE KEY uq_products_product_code (product_code),
    CONSTRAINT ck_products_category   CHECK (category IN ('phone','tv')),
    CONSTRAINT ck_products_list_price CHECK (list_price_egp > 0),
    CONSTRAINT ck_products_is_active  CHECK (is_active IN (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- orders (6 columns): order_id PK VARCHAR(12), customer_id FK -> customers,
--   order_purchase_ts DATETIME + INDEX, order_status VARCHAR(15) CHECK in
--   ('delivered','canceled','returned'), payment_method VARCHAR(20) CHECK in
--   ('cash_on_delivery','card','installments','wallet'), loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
CREATE TABLE orders (
    order_id           VARCHAR(12) NOT NULL,
    customer_id        VARCHAR(10) NOT NULL,
    order_purchase_ts  DATETIME    NOT NULL,
    order_status       VARCHAR(15) NOT NULL,
    payment_method     VARCHAR(20) NOT NULL,
    loaded_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id),
    KEY ix_orders_purchase_ts (order_purchase_ts),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    CONSTRAINT ck_orders_status   CHECK (order_status IN ('delivered','canceled','returned')),
    CONSTRAINT ck_orders_payment  CHECK (payment_method IN ('cash_on_delivery','card','installments','wallet'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- order_items (5 columns): order_id FK -> orders, item_no SMALLINT CHECK >= 1,
--   PRIMARY KEY (order_id, item_no), product_id FK -> products,
--   quantity SMALLINT CHECK > 0, unit_price_egp DECIMAL(10,2) CHECK > 0
CREATE TABLE order_items (
    order_id        VARCHAR(12)   NOT NULL,
    item_no         SMALLINT      NOT NULL,
    product_id      VARCHAR(10)   NOT NULL,
    quantity        SMALLINT      NOT NULL,
    unit_price_egp  DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_id, item_no),
    CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES orders (order_id),
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT ck_items_item_no  CHECK (item_no >= 1),
    CONSTRAINT ck_items_quantity CHECK (quantity > 0),
    CONSTRAINT ck_items_price    CHECK (unit_price_egp > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Check after running (paste the output in 01_oltp.md):
--   SHOW TABLES;  SHOW INDEX FROM orders;
--   SELECT table_name, table_collation FROM information_schema.tables WHERE table_schema = 'ecommerce_oltp';