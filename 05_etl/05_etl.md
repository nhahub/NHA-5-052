# Module 5 — ETL and Pipelines (Python and Apache Airflow)

**Owner:** Eng. Nouran Elshwehy

> Fill each step with the command you ran, its output and a screenshot (`images/`).

## Two pipelines

| Pipeline | DAG | Flow | etl_state.pipeline |
|---|---|---|---|
| Prices | `dags/prices_daily_dag.py` (06:00 Cairo) | 3 scrapers → MongoDB → validate + **match** + load `fact_price_daily` → quality check | `prices_daily` |
| Sales | `dags/sales_daily_dag.py` (08:00 Cairo) | generate the day's orders → MySQL → incremental load `fact_sales` → quality check | `orders_incremental` |

Both commit facts and the `etl_state` row in one transaction; a failed run is recorded and re-raised (Airflow retries).

## Files

| File | Task | Status |
|---|---|---|
| `scripts/mysqlconnect.py`, `scripts/postgresqlconnect.py` | connections (settings from `.env`) | **ready** |
| `scripts/etl_common.py` | watermark, run log, MongoDB connection | **ready** |
| `scripts/etl_state.sql` | control table | **ready** |
| `scripts/matching.py` | N2 — the integration step | skeleton |
| `scripts/load_prices.py` | N3 — MongoDB → `fact_price_daily` | skeleton |
| `scripts/automation.py` | N4 — MySQL → `fact_sales` (incremental) | skeleton |
| `scripts/quality_checks.py` | N5 / N6 — checks that fail the DAG | skeleton |
| `dags/prices_daily_dag.py`, `dags/sales_daily_dag.py` | N5 / N6 | DAG ready, tasks to finish |
| `config/*.csv` | matching lists (see `config/README.md`) | to fill (A7) |

## Steps
### 1. Start the services (N1)
`cp .env.example .env` then `docker compose up -d`; Airflow UI at http://localhost:8081.
```
# commands / output
```
### 2. Matching (N2) and price load (N3)
```
# commands / output   (products on 2+ sites; rows in fact_price_daily per day)
```
### 3. Sales load (N4)
```
# commands / output   (run twice: the second run must report no_data)
```
### 4. DAGs (N5, N6)
Screenshots: DAG list, graph view, a green run, the logs, and `SELECT * FROM etl_state ORDER BY run_id DESC;`.
### 5. Failure tests (N7 with H7)
Site unreachable · bad batch · database down — show the FAILED task, the retries and the `failed` row in `etl_state`.

## Deliverables
- [ ] matching, price and sales ETL · [ ] two DAGs with green runs · [ ] failure-test log · [ ] `images/`
