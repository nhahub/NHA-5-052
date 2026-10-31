# Module 1 — OLTP Database (MySQL): our store's sales

**Owner:** Eng. Hussein Saeed · **Data:** synthetic (generated), on real products and real market prices

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Files

| File | Task | Status |
|---|---|---|
| `scripts/oltp.sql` | H1 — 4 tables, one collation, index on `order_purchase_ts` | skeleton |
| `scripts/generate_sales.py` | H4 customers · H5 products and daily orders | skeleton |
| `scripts/load_batch.py` | H5 — load the CSV files into MySQL | skeleton |
| `scripts/datadump.sh` | H5 — compressed, dated mysqldump in `backups/` | skeleton |

## Steps

### 1. Create the database and tables (H1)
Run `scripts/oltp.sql` in DBeaver (MySQL, `localhost:3306`). Check `SHOW TABLES;`, `SHOW INDEX FROM orders;` and the collation query at the end of the file.
```
# commands / output
```

### 2. Generate the customers (H4)
`python 01_oltp/scripts/generate_sales.py customers` — write the generator settings (CONFIG) used here.
```
# commands / output
```

### 3. Generate the products and the daily orders (H5)
Needs the products matched on 2+ sites (N2, N3). `python 01_oltp/scripts/generate_sales.py products`, then `... orders <date>`.
```
# commands / output
```

### 4. Load the batches and check the counts (H5)
`python 01_oltp/scripts/load_batch.py reference` then `... day <date>`; rows in each file = rows inserted.
```
# commands / output
```

### 5. Export the database (H5)
`bash 01_oltp/scripts/datadump.sh`
```
# commands / output
```

## Deliverables
- [ ] `oltp.sql` · [ ] `generate_sales.py` · [ ] `load_batch.py` · [ ] `datadump.sh` + a dump in `backups/`
- [ ] `images/` — tables, index, row counts, dump
