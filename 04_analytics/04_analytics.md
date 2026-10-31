# Module 4 — Analytics and Dashboard

**Owners:** Eng. Hussein Saeed (SQL), Mahmoud Dahroug (Power BI)

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Reports (data dictionary, sheet Star_Schema)
1. Cheapest site per product per day, and how often each site is the cheapest, by category
2. Price spread between sites (max − min, and %) per product and category over time
3. Price changes and discounts per site over time
4. Stock availability per site and category
5. Our sales by category, governorate and week (**synthetic** sales)
6. Our price against the lowest market price on the same day, and our units sold

Prices are non-additive: use MIN / MAX / AVG, never SUM.

## Files

| File | Task | Status |
|---|---|---|
| `scripts/analysis_queries.sql` | H6 — views, GROUPING SETS, ROLLUP, CUBE, materialized view | skeleton |
| `dashboard/*.pbix` | M5 connect · M6 six report pages | to do |

## Steps
### 1. Analytical SQL (H6)
```
# query + output for each report
```
### 2. Power BI (M5, M6)
Connect Power BI Desktop to PostgreSQL (`localhost:5433`, `ecommerce_dw`), import the views, build one page per report.

## Deliverables
- [ ] `analysis_queries.sql` · [ ] `.pbix` · [ ] one screenshot per report page
