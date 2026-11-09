# Module 1 — OLTP Database (MySQL): our store's sales

**Owner:** Eng. Hussein Saeed · **Data:** synthetic (generated), based on real products and real market prices

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Files

| File | Task | Status |
|---|---|---|
| `scripts/oltp.sql` | H1 — 4 tables, one collation, index on `order_purchase_ts` | **done** |
| `scripts/generate_sales.py` | H4 customers · H5 products and daily orders | **done** |
| `scripts/load_batch.py` | H5 — load the CSV files into MySQL | **done** |
| `scripts/datadump.sh` | H5 — compressed, dated mysqldump in `backups/` | **done** |

## Steps

> **Note (review of 3-Nov-2026):** the outputs below that show 3 products, 8 price rows or 108 sales lines were produced with the test seed (`05_etl/tests/fixtures/seed_mongo.py`, 8 hand-written offers), not with scraped data. Replace them with the outputs of a run on the real offers files before the final presentation. A review run on all the real daily files (27-Oct to 2-Nov-2026, 7,530 offers) gave: 7,508 price rows, **143 phones and 30 TVs on 2+ sites on 29-Oct** (the day with the three sites), 181 products sold by our store, 511 order items over 6 days. See `REVIEW_FIXES.md`.


### 1. Create the database and tables (H1)
Run `scripts/oltp.sql` in DBeaver (MySQL, `localhost:3306`). Check `SHOW TABLES;`, `SHOW INDEX FROM orders;` and the collation query at the end of the file.
```
SHOW TABLES FROM ecommerce_oltp;
+------------------------+
| Tables_in_ecommerce_oltp |
+------------------------+
| customers              |
| order_items            |
| orders                 |
| products               |
+------------------------+

SHOW INDEX FROM ecommerce_oltp.orders;
+--------+------------+----------------------+--------------+------------------+-----------+-------------+
| Table  | Non_unique | Key_name             | Seq_in_index | Column_name      | Collation | Cardinality |
+--------+------------+----------------------+--------------+------------------+-----------+-------------+
| orders |          0 | PRIMARY              |            1 | order_id         | A         |           0 |
| orders |          1 | ix_orders_purchase_ts|            1 | order_purchase_ts| A         |           0 |
| orders |          1 | fk_orders_customer   |            1 | customer_id      | A         |           0 |
+--------+------------+----------------------+--------------+------------------+-----------+-------------+

SELECT table_name, table_collation FROM information_schema.tables WHERE table_schema='ecommerce_oltp';
+------------+--------------------+
| TABLE_NAME | TABLE_COLLATION    |
+------------+--------------------+
| customers  | utf8mb4_0900_ai_ci |
| order_items| utf8mb4_0900_ai_ci |
| orders     | utf8mb4_0900_ai_ci |
| products   | utf8mb4_0900_ai_ci |
+------------+--------------------+
```

### 2. Generate the customers (H4)
`python 01_oltp/scripts/generate_sales.py customers` — write the generator settings (CONFIG) used here.

CONFIG: `customers=3000`, governorates weighted (Cairo 22%, Giza 16%, Alexandria 12%, ..., Others 24% = one of the remaining 18 governorates uniformly), `signup_date` uniform on 2025-01-01..2026-10-01, seed=2026.
```
python 01_oltp/scripts/generate_sales.py customers
wrote 3000 rows -> data\sales\customers.csv

head -5 data\sales\customers.csv
customer_id,governorate,city,signup_date
C000001,Cairo,Cairo,2026-05-30
C000002,Ismailia,Ismailia,2025-08-17
C000003,South Sinai,Sharm El-Sheikh,2026-03-07
C000004,South Sinai,Sharm El-Sheikh,2026-05-18
C000005,Beheira,Damanhour,2026-08-24
```

### 3. Generate the products and the daily orders (H5)
Needs the products matched on 2+ sites (N2, N3). `python 01_oltp/scripts/generate_sales.py products`, then `... orders <date>`.
```
python 01_oltp/scripts/generate_sales.py products
wrote 3 rows -> data\sales\products.csv

python 01_oltp/scripts/generate_sales.py orders 2026-10-31
wrote 85 rows -> data\sales\orders_2026-10-31.csv
wrote 108 rows -> data\sales\order_items_2026-10-31.csv

head -3 data\sales\orders_2026-10-31.csv
order_id,customer_id,order_purchase_ts,order_status,payment_method
O2610310001,C001568,2026-10-31 08:01:25,canceled,cash_on_delivery
O2610310002,C001529,2026-10-31 11:41:58,delivered,installments
O2610310003,C001271,2026-10-31 02:37:40,delivered,installments

head -3 data\sales\order_items_2026-10-31.csv
order_id,item_no,product_id,quantity,unit_price_egp
O2610310001,1,P0001,1,29050.48
O2610310002,1,P0001,1,28437.09
O2610310003,1,P0001,1,28981.27
```

### 4. Load the batches and check the counts (H5)
`python 01_oltp/scripts/load_batch.py reference` then `... day <date>`; rows in each file = rows inserted.
```
python 01_oltp/scripts/load_batch.py reference
customers: file customers.csv -> 3000 rows in, 0 inserted
products:  file products.csv  -> 3 rows in, 3 inserted
reference total: customers 0/3000, products 3/3

python 01_oltp/scripts/load_batch.py day 2026-10-31
orders:      file orders_2026-10-31.csv      -> 85 rows in, 85 inserted
order_items: file order_items_2026-10-31.csv -> 108 rows in, 108 inserted
day 2026-10-31 total: orders 85/85, order_items 108/108

# idempotency: re-run reference -> 0 inserted on both
python 01_oltp/scripts/load_batch.py reference
customers: file customers.csv -> 3000 rows in, 0 inserted
products:  file products.csv  -> 3 rows in, 0 inserted

# count verification
SELECT 'customers',COUNT(*) FROM ecommerce_oltp.customers UNION ALL SELECT 'products',COUNT(*) ...
+------------+-------+
| customers  |  3000 |
| products   |     3 |
| orders     |    85 |
| order_items|   108 |
+------------+-------+
```

### 5. Export the database (H5)
`bash 01_oltp/scripts/datadump.sh`
```
# dump produced (equivalent of the script run from Git Bash / WSL)
cmd /c "docker exec ecommerce-mysql mysqldump -uroot -prootpassword --single-transaction --routines --databases ecommerce_oltp | docker run --rm -i alpine:3.20 gzip -c > 01_oltp\backups\ecommerce_oltp_2026-10-31.sql.gz"

Get-Item 01_oltp\backups\ecommerce_oltp_2026-10-31.sql.gz | Select Name, Length
Name                             Length
ecommerce_oltp_2026-10-31.sql.gz  21268

# gzip header + CREATE TABLE count
line1: -- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
line2: --
CREATE TABLE: 4
INSERT INTO customers: 1
CREATE DATABASE: 1

# restore test (proves the dump is valid)
restored_customers | 3000
Tables: customers, order_items, orders, products
```

## Deliverables
- [x] `oltp.sql` · [x] `generate_sales.py` · [x] `load_batch.py` · [x] `datadump.sh` + a dump in `backups/`
- [ ] `images/` — tables, index, row counts, dump (screenshots to be added)