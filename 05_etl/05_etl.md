# Module 5 — ETL and Pipelines (Python and Apache Airflow)

**Owner:** Eng. Nouran Elshwehy, Eng. Aya Elgarwany

> **Status:** skeleton — the owner fills each step with the commands used, the output, and a screenshot.

## Objectives

- Move only new data from MySQL and MongoDB into the warehouse.
- Validate and transform the data on the way.
- Automate the daily loads with Airflow.

## Steps

### 1. Start the services

Docker Compose with Airflow, MySQL, MongoDB and PostgreSQL.

```
# commands
```

_Output / screenshot:_

### 2. Connection modules

`scripts/mysqlconnect.py`, `scripts/postgresqlconnect.py`.

```
# commands
```

_Output / screenshot:_

### 3. Incremental ETL

`scripts/automation.py`: read the last loaded purchase time from the warehouse, take newer orders from MySQL, validate, transform, load.

```
# commands
```

_Output / screenshot:_

### 4. DAG: daily incremental load

extract new orders → validate → transform → load → quality check; retries and logging.

```
# commands
```

_Output / screenshot:_

### 5. DAG: daily catalogue scrape

scrape → MongoDB → Dim Product.

```
# commands
```

_Output / screenshot:_

### 6. Deploy and monitor

Copy the DAGs to `$AIRFLOW_HOME/dags`, unpause, and check DAG runs, graph view and logs.

```
# commands
```

_Output / screenshot:_

## Deliverables

- [ ] `scripts/` — connection modules, transformations, automation.py
- [ ] `dags/` — the two DAG files
- [ ] `images/` — DAG list, unpause, DAG runs, graph view, logs
