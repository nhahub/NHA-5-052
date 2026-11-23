# Sample data

One real day of offers, so the pipeline can be tried without scraping the sites.

| File | Site | Offers |
|---|---|---|
| `offers/offers_xprs_2026-11-20.json` | XPRS (myxprs.com, Shopify JSON) | 259 |
| `offers/offers_dream2000_2026-11-20.json` | Dream 2000 (dream2000.com, Shopify JSON) | 594 |
| `offers/offers_elghazawy_2026-11-20.json` | El Ghazawy (elghazawy.com, HTML) | 349 |

- Scraped on 20-Nov-2026 from one machine with `02_nosql/scripts/scraper_<site>.py` (5 s between requests for XPRS and Dream 2000, 2 s for El Ghazawy; no HTTP 429 or 403 that day).
- 20-Nov-2026 is the first day with the three sites scraped on the same day, so the reports can compare El Ghazawy with XPRS and Dream 2000.
- Format: one JSON list of offers per site, the same fields as `catalog.offers` in MongoDB (see `02_nosql/02_nosql.md` and the data dictionary).
- The raw pages (`data/offers/raw/`) are not included.

Load into MongoDB (from the repository root, with `MONGO_USER` and `MONGO_PASSWORD` set from `.env`):

```
python 02_nosql/scripts/mongo_load.py "sample_data/offers/offers_*.json"
```

Then run `prices_daily_dag` (or `load_prices.py`) to load the day into the warehouse.
