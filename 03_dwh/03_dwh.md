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
| `scripts/schema.sql` | H2 — 7 tables, dim_date (730 days), 3 sites, keys and indexes | skeleton |
| `../05_etl/scripts/etl_state.sql` | control table of both pipelines | **ready** |
| `images/erd.png` | H2 — ERD from the created schema (DBeaver ER diagram) | to do |

## Steps

### 1. Create the warehouse (H2, H3)
Run `scripts/schema.sql` then `05_etl/scripts/etl_state.sql` in DBeaver (`localhost:5433`, database `ecommerce_dw`).
```
# commands / output   (SELECT COUNT(*) FROM dim_date; -> 730   SELECT * FROM dim_site; -> 3 rows)
```

### 2. ERD (H2)
DBeaver → database → ER Diagram → export PNG to `images/erd.png`.

## Deliverables
- [ ] `schema.sql` · [ ] `images/erd.png` · [ ] screenshots of the tables and counts
