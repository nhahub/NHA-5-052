# Module 3 — Data Warehouse (PostgreSQL)

**Owner:** Eng. Hussein Saeed

> **Status:** skeleton — the owner fills each step with the commands used, the output, and a screenshot.

## Objectives

- Design a star schema that answers the company reports.
- Create the fact and dimension tables and their relationships.

## Steps

### 1. Reporting requirements

Total sales per year per state; per month per category; per quarter per state; per category per state.

```
# commands
```

_Output / screenshot:_

### 2. Design the star schema

Fact Sales; Dim Customer, Dim Product, Dim Date (see the data dictionary).

```
# commands
```

_Output / screenshot:_

### 3. Create the tables

Run `scripts/schema.sql` in PostgreSQL (DBeaver).

```
# commands
```

_Output / screenshot:_

### 4. Generate Dim Date

generate_series from 2016-01-01 to 2018-12-31.

```
# commands
```

_Output / screenshot:_

### 5. Draw the ERD

Save as `images/erd.png`.

```
# commands
```

_Output / screenshot:_

## Deliverables

- [ ] `scripts/schema.sql`
- [ ] `images/erd.png`
