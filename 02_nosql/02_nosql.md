# Module 2 — NoSQL Catalogue (MongoDB)

**Owner:** Eng. Aya Elgarwany

> **Status:** skeleton — the owner fills each step with the commands used, the output, and a screenshot.

## Objectives

- Collect The Conran Shop product catalogue with a permitted web scraper.
- Store the catalogue in MongoDB.
- Query and export the catalogue.

## Steps

### 1. Scrape the catalogue

Run the scraper on the collection pages (`?page=N`, one request per second, clear User-Agent; no `/search` or sort/filter URLs). Output: dated JSON.

```
# commands
```

_Output / screenshot:_

### 2. Import into MongoDB

`mongoimport` into database `catalog`, collection `products`.

```
# commands
```

_Output / screenshot:_

### 3. Create indexes

Unique (handle, snapshot_date); brand; collection.

```
# commands
```

_Output / screenshot:_

### 4. Query the catalogue

Document count, products per brand and per collection, average price, stock status.

```
# commands
```

_Output / screenshot:_

### 5. Export to CSV

`mongoexport` to `data/products.csv`.

```
# commands
```

_Output / screenshot:_

## Deliverables

- [ ] `scripts/` — scraper and queries
- [ ] `data/products.csv`
- [ ] `images/` — import, indexes, query results
