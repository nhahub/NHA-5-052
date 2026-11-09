-- schema.sql - PostgreSQL data warehouse ecommerce_dw.        Task H2 (Eng. Hussein).
-- Source of truth: docs/data_dictionary.xlsx, sheets Star_Schema, fact_price_daily, fact_sales, dim_product,
--                  product_map, dim_site, dim_customer, dim_date (types, keys, CHECK rules, indexes, notes).
-- Run in DBeaver on the warehouse (localhost:5433, database ecommerce_dw), then run 05_etl/scripts/etl_state.sql.
-- Create in this order (foreign keys): dim_date, dim_site, dim_customer, dim_product, product_map, fact_price_daily, fact_sales.

DROP TABLE IF EXISTS fact_sales, fact_price_daily, product_map, dim_product, dim_customer, dim_site, dim_date CASCADE;

-- 1. dim_date (12 columns) - one row per day, 2026-01-01 to 2027-12-31 = 730 rows; is_weekend = Friday and Saturday
CREATE TABLE dim_date (
    date_key         INTEGER      NOT NULL,
    full_date        DATE         NOT NULL,
    day_of_month     SMALLINT     NOT NULL,
    day_name         VARCHAR(9)   NOT NULL,
    iso_day_of_week  SMALLINT     NOT NULL,
    iso_week         SMALLINT     NOT NULL,
    month_num        SMALLINT     NOT NULL,
    month_name       VARCHAR(9)   NOT NULL,
    quarter          SMALLINT     NOT NULL,
    year             SMALLINT     NOT NULL,
    year_month       CHAR(7)      NOT NULL,
    is_weekend       BOOLEAN      NOT NULL,
    CONSTRAINT pk_dim_date         PRIMARY KEY (date_key),
    CONSTRAINT uk_dim_date_full    UNIQUE (full_date),
    CONSTRAINT ck_dim_date_dom     CHECK (day_of_month    BETWEEN 1 AND 31),
    CONSTRAINT ck_dim_date_isodow  CHECK (iso_day_of_week BETWEEN 1 AND 7),
    CONSTRAINT ck_dim_date_isoweek CHECK (iso_week        BETWEEN 1 AND 53),
    CONSTRAINT ck_dim_date_month   CHECK (month_num       BETWEEN 1 AND 12),
    CONSTRAINT ck_dim_date_quarter CHECK (quarter         BETWEEN 1 AND 4)
);

INSERT INTO dim_date (date_key, full_date, day_of_month, day_name, iso_day_of_week, iso_week,
                      month_num, month_name, quarter, year, year_month, is_weekend)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT,
    d,
    EXTRACT(DAY     FROM d)::SMALLINT,
    TRIM(TO_CHAR(d, 'Day')),
    EXTRACT(ISODOW  FROM d)::SMALLINT,
    EXTRACT(WEEK    FROM d)::SMALLINT,
    EXTRACT(MONTH   FROM d)::SMALLINT,
    TRIM(TO_CHAR(d, 'Month')),
    EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(YEAR    FROM d)::SMALLINT,
    TO_CHAR(d, 'YYYY-MM'),
    EXTRACT(ISODOW FROM d) IN (5, 6)
FROM generate_series('2026-01-01'::date, '2027-12-31'::date, interval '1 day') AS d;

-- 2. dim_site (8 columns) - 4 rows: xprs, dream2000, jumia (scraped 27-Oct to 1-Nov-2026 only: HTTP 403 since 2-Nov), elghazawy (from 9-Nov-2026)
CREATE TABLE dim_site (
    site_key        SMALLINT      GENERATED ALWAYS AS IDENTITY,
    site_code       VARCHAR(20)   NOT NULL,
    site_name       VARCHAR(60)   NOT NULL,
    base_url        VARCHAR(100)  NOT NULL,
    platform        VARCHAR(30),
    data_format     VARCHAR(10)   NOT NULL,
    is_marketplace  BOOLEAN       NOT NULL,
    added_at        DATE          NOT NULL,
    CONSTRAINT pk_dim_site        PRIMARY KEY (site_key),
    CONSTRAINT uk_dim_site_code   UNIQUE (site_code),
    CONSTRAINT ck_dim_site_format CHECK (data_format IN ('html','json'))
);

INSERT INTO dim_site (site_code, site_name, base_url, platform, data_format, is_marketplace, added_at) VALUES
    ('xprs',      'XPRS',        'https://myxprs.com',       'Shopify', 'json', FALSE, '2026-10-26'),
    ('dream2000', 'Dream 2000',  'https://dream2000.com',    'Shopify', 'json', FALSE, '2026-10-26'),
    ('jumia',     'Jumia Egypt', 'https://www.jumia.com.eg', NULL,      'html', TRUE,  '2026-10-26'),
    ('elghazawy', 'El Ghazawy',  'https://elghazawy.com',    NULL,      'html', FALSE, '2026-11-09');
-- Already have the warehouse? Add only the new site (no need to rebuild):
--   INSERT INTO dim_site (site_code, site_name, base_url, platform, data_format, is_marketplace, added_at)
--   VALUES ('elghazawy', 'El Ghazawy', 'https://elghazawy.com', NULL, 'html', FALSE, '2026-11-09')
--   ON CONFLICT (site_code) DO NOTHING;

-- 3. dim_customer (6 columns) - UNIQUE (customer_id); index on governorate
CREATE TABLE dim_customer (
    customer_key  INTEGER       GENERATED ALWAYS AS IDENTITY,
    customer_id   VARCHAR(10)   NOT NULL,
    governorate   VARCHAR(30)   NOT NULL,
    city          VARCHAR(60)   NOT NULL,
    signup_date   DATE          NOT NULL,
    loaded_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_dim_customer    PRIMARY KEY (customer_key),
    CONSTRAINT uk_dim_customer_id UNIQUE (customer_id)
);
CREATE INDEX ix_dim_customer_governorate ON dim_customer (governorate);

-- 4. dim_product (13 columns) - UNIQUE (product_code); CHECK category IN ('phone','tv'); indexes on category, brand
CREATE TABLE dim_product (
    product_key      INTEGER       GENERATED ALWAYS AS IDENTITY,
    product_code     VARCHAR(120)  NOT NULL,
    category         VARCHAR(10)   NOT NULL,
    brand            VARCHAR(40)   NOT NULL,
    model_key        VARCHAR(80)   NOT NULL,
    display_name     VARCHAR(200)  NOT NULL,
    ram_gb           SMALLINT,
    storage_gb       SMALLINT,
    screen_size_in   SMALLINT,
    first_seen_date  DATE          NOT NULL,
    last_seen_date   DATE          NOT NULL,
    loaded_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_dim_product          PRIMARY KEY (product_key),
    CONSTRAINT uk_dim_product_code     UNIQUE (product_code),
    CONSTRAINT ck_dim_product_category CHECK (category IN ('phone','tv'))
);
CREATE INDEX ix_dim_product_category ON dim_product (category);
CREATE INDEX ix_dim_product_brand    ON dim_product (brand);

-- 5. product_map (10 columns) - PRIMARY KEY (site_key, site_product_id); FK product_key -> dim_product
CREATE TABLE product_map (
    site_key         SMALLINT      NOT NULL,
    site_product_id  VARCHAR(200)  NOT NULL,
    product_key      INTEGER       NOT NULL,
    match_method     VARCHAR(12)   NOT NULL,
    match_key        VARCHAR(120)  NOT NULL,
    title_last       VARCHAR(300)  NOT NULL,
    url              VARCHAR(400)  NOT NULL,
    first_seen_date  DATE          NOT NULL,
    last_seen_date   DATE          NOT NULL,
    is_active        BOOLEAN       NOT NULL,
    CONSTRAINT pk_product_map         PRIMARY KEY (site_key, site_product_id),
    CONSTRAINT fk_product_map_site    FOREIGN KEY (site_key)    REFERENCES dim_site (site_key),
    CONSTRAINT fk_product_map_product FOREIGN KEY (product_key) REFERENCES dim_product (product_key),
    CONSTRAINT ck_product_map_method  CHECK (match_method IN ('ean','model_code','name_spec','manual','new'))
);

-- 6. fact_price_daily (13 columns) - UNIQUE (date_key, site_key, site_product_id); CHECK sale_price_egp > 0
CREATE TABLE fact_price_daily (
    price_key           BIGINT        GENERATED ALWAYS AS IDENTITY,
    date_key            INTEGER       NOT NULL,
    site_key            SMALLINT      NOT NULL,
    site_product_id     VARCHAR(200)  NOT NULL,
    product_key         INTEGER       NOT NULL,
    sale_price_egp      NUMERIC(10,2) NOT NULL,
    original_price_egp  NUMERIC(10,2),
    discount_pct        SMALLINT,
    in_stock            BOOLEAN       NOT NULL,
    stock_text          VARCHAR(60),
    seller              VARCHAR(100),
    scraped_at          TIMESTAMPTZ   NOT NULL,
    run_id              INTEGER       NOT NULL,
    CONSTRAINT pk_fact_price_daily     PRIMARY KEY (price_key),
    CONSTRAINT uk_fact_price_daily     UNIQUE (date_key, site_key, site_product_id),
    CONSTRAINT fk_fact_price_date      FOREIGN KEY (date_key)    REFERENCES dim_date (date_key),
    CONSTRAINT fk_fact_price_site      FOREIGN KEY (site_key)    REFERENCES dim_site (site_key),
    CONSTRAINT fk_fact_price_product   FOREIGN KEY (product_key) REFERENCES dim_product (product_key),
    CONSTRAINT ck_fact_price_sale      CHECK (sale_price_egp > 0),
    CONSTRAINT ck_fact_price_original  CHECK (original_price_egp IS NULL OR original_price_egp > sale_price_egp),
    CONSTRAINT ck_fact_price_discount  CHECK (discount_pct IS NULL OR discount_pct BETWEEN 0 AND 99)
);
CREATE INDEX ix_fact_price_date    ON fact_price_daily (date_key);
CREATE INDEX ix_fact_price_product ON fact_price_daily (product_key);
CREATE INDEX ix_fact_price_site    ON fact_price_daily (site_key);

-- 7. fact_sales (14 columns) - UNIQUE (order_id, item_no); line_total_egp generated STORED; indexes on date/customer/product/status
CREATE TABLE fact_sales (
    sales_key           BIGINT        GENERATED ALWAYS AS IDENTITY,
    order_id            VARCHAR(12)   NOT NULL,
    item_no             SMALLINT      NOT NULL,
    date_key            INTEGER       NOT NULL,
    customer_key        INTEGER       NOT NULL,
    product_key         INTEGER       NOT NULL,
    order_purchase_ts   TIMESTAMP     NOT NULL,
    order_status        VARCHAR(15)   NOT NULL,
    payment_method      VARCHAR(20)   NOT NULL,
    quantity            SMALLINT      NOT NULL,
    unit_price_egp      NUMERIC(10,2) NOT NULL,
    line_total_egp      NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price_egp) STORED,
    batch_id            CHAR(10)      NOT NULL,
    loaded_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_fact_sales          PRIMARY KEY (sales_key),
    CONSTRAINT uk_fact_sales          UNIQUE (order_id, item_no),
    CONSTRAINT fk_fact_sales_date     FOREIGN KEY (date_key)     REFERENCES dim_date (date_key),
    CONSTRAINT fk_fact_sales_customer FOREIGN KEY (customer_key) REFERENCES dim_customer (customer_key),
    CONSTRAINT fk_fact_sales_product  FOREIGN KEY (product_key)  REFERENCES dim_product (product_key),
    CONSTRAINT ck_fact_sales_status   CHECK (order_status   IN ('delivered','canceled','returned')),
    CONSTRAINT ck_fact_sales_payment  CHECK (payment_method IN ('cash_on_delivery','card','installments','wallet')),
    CONSTRAINT ck_fact_sales_item_no  CHECK (item_no >= 1),
    CONSTRAINT ck_fact_sales_qty      CHECK (quantity > 0),
    CONSTRAINT ck_fact_sales_price    CHECK (unit_price_egp > 0)
);
CREATE INDEX ix_fact_sales_date     ON fact_sales (date_key);
CREATE INDEX ix_fact_sales_customer ON fact_sales (customer_key);
CREATE INDEX ix_fact_sales_product  ON fact_sales (product_key);
CREATE INDEX ix_fact_sales_status   ON fact_sales (order_status);

-- Check after running (paste the output in 03_dwh.md):
--   SELECT COUNT(*) FROM dim_date;   -- 730
--   SELECT * FROM dim_site ORDER BY site_key;   -- 3 rows