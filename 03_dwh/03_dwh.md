# Module 3 — Data Warehouse (PostgreSQL)

**Owner:** Eng. Hussein Saeed

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Design (data dictionary, sheet Star_Schema)
Two fact tables — `fact_price_daily` (site offer per day) and `fact_sales` (item in an order of our store) — share
`dim_product` and `dim_date`. Plus `dim_site`, `dim_customer` and the bridge `product_map` (which offer on which site is which product).
This shared product dimension is what lets us compare market prices with our sales.

## Files

| File | Task | Status |
|---|---|---|
| `scripts/schema.sql` | H2 — 7 tables, dim_date (730 days), 3 sites, keys and indexes | **done** |
| `../05_etl/scripts/etl_state.sql` | control table of both pipelines | **ready** |
| `images/erd.png` | H2 — ERD from the created schema (DBeaver ER diagram) | **done** (103,670 bytes) |

## Steps

### 1. Create the warehouse (H2, H3)
Run `scripts/schema.sql` then `05_etl/scripts/etl_state.sql` in DBeaver (`localhost:5433`, database `ecommerce_dw`).
```
Get-Content -Raw "03_dwh\scripts\schema.sql" | docker exec -i ecommerce-postgres-dw psql -U dw_user -d ecommerce_dw -v ON_ERROR_STOP=1
NOTICE:  table "fact_sales" does not exist, skipping
NOTICE:  table "fact_price_daily" does not exist, skipping
NOTICE:  table "product_map" does not exist, skipping
NOTICE:  table "dim_product" does not exist, skipping
NOTICE:  table "dim_customer" does not exist, skipping
NOTICE:  table "dim_site" does not exist, skipping
NOTICE:  table "dim_date" does not exist, skipping
DROP TABLE
CREATE TABLE
INSERT 0 730
CREATE TABLE
INSERT 0 3
CREATE TABLE
CREATE INDEX
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE TABLE
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE INDEX

Get-Content -Raw "05_etl\scripts\etl_state.sql" | docker exec -i ecommerce-postgres-dw psql -U dw_user -d ecommerce_dw -v ON_ERROR_STOP=1
CREATE TABLE
CREATE INDEX

-- Verify tables / views / matviews
SELECT relname, relkind FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v','m') ORDER BY relname;
 dim_customer     | r
 dim_date         | r
 dim_product      | r
 dim_site         | r
 etl_state        | r
 fact_price_daily | r
 fact_sales       | r
 product_map      | r
(8 rows)

SELECT COUNT(*) FROM dim_date;
 dim_date_rows
---------------
           730

SELECT site_key, site_code, site_name, platform, data_format, is_marketplace FROM dim_site ORDER BY site_key;
 site_key | site_code |  site_name  | platform | data_format | is_marketplace
----------+-----------+-------------+----------+-------------+----------------
        1 | xprs      | XPRS        | Shopify  | json        | f
        2 | dream2000 | Dream 2000  | Shopify  | json        | f
        3 | jumia     | Jumia Egypt |          | html        | t
-- (output of 3-Nov-2026; from 9-Nov schema.sql adds row 4: elghazawy | El Ghazawy | | html | f)

-- fact_sales has 14 columns; line_total_egp is generated ALWAYS
SELECT table_name, column_name, is_generated FROM information_schema.columns WHERE table_name='fact_sales' ORDER BY ordinal_position;
(14 rows, line_total_egp | ALWAYS, all others NEVER)

-- 25 indexes, 39 constraints (pk+uk+ck+fk) as required by the data dictionary
SELECT COUNT(*) FROM pg_indexes WHERE schemaname='public';       -- 25
SELECT COUNT(*) FROM pg_constraint WHERE connamespace='public'::regnamespace AND contype IN ('c','f','u','p');  -- 39
```

### 2. ERD (H2)
DBeaver → database → ER Diagram → export PNG to `images/erd.png`.

```
FullName                                                            Length
E:\project-nha5\ecommerce-data-pipeline-main\03_dwh\images\erd.png  103670
```

The ERD shows: `product_map → dim_site`, `product_map → dim_product`, `fact_price_daily → dim_date / dim_site / dim_product`,
`fact_sales → dim_date / dim_customer / dim_product`, plus the 3 analysis views and the materialized view.

The same ERD as a diagram that GitHub draws from text (main columns; the dashed line = same offer, no foreign key):

```mermaid
erDiagram
    dim_date     ||--o{ fact_price_daily : "price day"
    dim_site     ||--o{ fact_price_daily : "site"
    dim_product  ||--o{ fact_price_daily : "product"
    dim_date     ||--o{ fact_sales       : "order day"
    dim_customer ||--o{ fact_sales       : "customer"
    dim_product  ||--o{ fact_sales       : "product sold"
    dim_site     ||--o{ product_map      : "offers on the site"
    dim_product  ||--|{ product_map      : "matched offers"
    product_map  ||..o{ fact_price_daily : "same offer (no FK)"

    dim_date {
        int      date_key PK "20261114"
        date     full_date UK
        smallint iso_week
        smallint month_num
        smallint year
        boolean  is_weekend "Fri and Sat"
    }
    dim_site {
        smallint site_key PK
        varchar  site_code UK "xprs, dream2000, jumia, elghazawy"
        varchar  site_name
        varchar  data_format "html or json"
        boolean  is_marketplace
        date     added_at
    }
    dim_customer {
        int     customer_key PK
        varchar customer_id UK
        varchar governorate
        varchar city
        date    signup_date
    }
    dim_product {
        int      product_key PK "our product id"
        varchar  product_code UK "brand|category|model"
        varchar  category "phone or tv"
        varchar  brand
        varchar  model_key
        varchar  display_name
        smallint ram_gb
        smallint storage_gb
        smallint screen_size_in
    }
    product_map {
        smallint site_key PK, FK
        varchar  site_product_id PK "Shopify id, SKU, site id"
        int      product_key FK
        varchar  match_method "ean, model_code, name_spec, manual, new"
        varchar  match_key
        varchar  url
        date     last_seen_date
    }
    fact_price_daily {
        bigint   price_key PK
        int      date_key FK
        smallint site_key FK
        varchar  site_product_id "UK with date_key, site_key"
        int      product_key FK
        numeric  sale_price_egp "greater than 0"
        numeric  original_price_egp
        smallint discount_pct
        boolean  in_stock
    }
    fact_sales {
        bigint   sales_key PK
        varchar  order_id "UK with item_no"
        smallint item_no
        int      date_key FK
        int      customer_key FK
        int      product_key FK
        varchar  order_status "delivered, canceled, returned"
        smallint quantity
        numeric  unit_price_egp
        numeric  line_total_egp "quantity x unit price"
    }
```

## Deliverables
- [x] `schema.sql` · [x] `images/erd.png` · [ ] screenshots of the tables and counts (to add)