# Module 1 — OLTP Database (MySQL)

**Owner:** Eng. Hussein Saeed

> **Status:** skeleton — the owner fills each step with the commands used, the output, and a screenshot.

## Objectives

- Design the OLTP schema for the Olist sales data.
- Load the Olist data in monthly batches to simulate new sales.
- Index the purchase timestamp.
- Automate the database export.

## Steps

### 1. Prepare the monthly batches

Run `scripts/extract_olist.py` (downloads the dataset and splits orders, order items and reviews by purchase month).

```
# commands
```

_Output / screenshot:_

### 2. Create the database and tables

`CREATE DATABASE ecommerce_oltp;` then run `scripts/oltp.sql` (8 tables — see the data dictionary, sheet OLTP_MySQL).

```
# commands
```

_Output / screenshot:_

### 3. Load the reference tables

category_translation, customers, sellers, products (full files, once).

```
# commands
```

_Output / screenshot:_

### 4. Load the monthly batches

For each month: orders → order_items → order_payments → order_reviews. Verify with `SELECT COUNT(*)` per table.

```
# commands
```

_Output / screenshot:_

### 5. Create the index

Index on `orders.order_purchase_timestamp`; check with `SHOW INDEX FROM orders;`.

```
# commands
```

_Output / screenshot:_

### 6. Export the database

Run `scripts/datadump.sh` (mysqldump).

```
# commands
```

_Output / screenshot:_

## Deliverables

- [ ] `scripts/extract_olist.py`
- [ ] `scripts/oltp.sql`
- [ ] `scripts/datadump.sh`
- [ ] `images/` — tables, row counts, index, export
