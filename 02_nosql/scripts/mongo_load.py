"""
mongo_load.py - load the offers files of the three scrapers into MongoDB.        READY - task A3 (Eng. Aya), tested offline 26-Oct-2026.

Target (data dictionary v4.3, sheet NoSQL_MongoDB):
  catalog.offers             one document per site offer per snapshot date (20 fields)
                             unique index (site, site_product_id, snapshot_date) 'ux_offer_day'; indexes on site and category
  catalog.offers_quarantine  offers that must not reach the warehouse, with a 'reason' field:
                               'no price'        sale_price missing, 0 or negative (e.g. Dream 2000 A17 5G at 0 on 25-Oct)
                               'no stock state'  in_stock missing
                               'out of scope'    category not phone / tv, or an unknown site
Rules:
  * loading the same file twice never creates duplicates (upsert on the unique key) - the counts stay the same
  * a document missing a key field, or with a field that is not in the data dictionary, is refused and logged
  * scraped_at is stored as a real date (BSON date, UTC), as the data dictionary says
  * if an offer was quarantined and a later load of the same day brings it complete, it moves to offers
Run:      python mongo_load.py data/offers/offers_*_2026-10-27.json
In Airflow: prices_daily_dag -> store_offers_mongodb -> load_files([...])
"""
import glob
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ASCENDING, MongoClient, UpdateOne

from common import OFFER_FIELDS

log = logging.getLogger("mongo_load")
KEY = ("site", "site_product_id", "snapshot_date")
SITES = {"xprs", "dream2000", "jumia"}
CATEGORIES = {"phone", "tv"}


def get_db(client=None):
    """catalog database; settings from environment variables (docker-compose.yaml / .env)."""
    if client is None:
        host, port = os.getenv("MONGO_HOST", "localhost"), int(os.getenv("MONGO_PORT", "27017"))
        user = os.getenv("MONGO_USER")   # not set = local MongoDB without a password (Aya's laptop)
        if user:
            client = MongoClient(host=host, port=port, username=user, password=os.getenv("MONGO_PASSWORD"))
        else:
            client = MongoClient(host=host, port=port)
    return client[os.getenv("MONGO_DB", "catalog")]


def ensure_indexes(db):
    """Create the indexes of the data dictionary (safe to run every time)."""
    key = [(k, ASCENDING) for k in KEY]
    db.offers.create_index(key, unique=True, name="ux_offer_day")
    db.offers.create_index([("site", ASCENDING)], name="ix_site")
    db.offers.create_index([("category", ASCENDING)], name="ix_category")
    db.offers_quarantine.create_index(key, unique=True, name="ux_offer_day")


def _to_date(value):
    """'2026-10-27T06:00:12Z' -> datetime (UTC). Leaves real dates and None as they are."""
    if isinstance(value, str):
        # also accepts milliseconds, e.g. '2026-10-26T13:02:05.761Z' (Dream 2000 file of 26-Oct)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return value


def reason_of(doc):
    """Why an offer goes to quarantine, or None if it is complete."""
    if doc.get("site") not in SITES or doc.get("category") not in CATEGORIES:
        return "out of scope"
    price = doc.get("sale_price")
    if not isinstance(price, (int, float)) or price <= 0:
        return "no price"
    if doc.get("in_stock") is None:
        return "no stock state"
    return None


def split(docs):
    """Return (good, quarantined, refused). Refused documents cannot be stored at all and are only logged."""
    good, quarantined, refused = [], [], []
    for d in docs:
        missing = [k for k in KEY if not d.get(k)]
        unknown = sorted(set(d) - set(OFFER_FIELDS) - {"reason"})
        if missing or unknown:
            refused.append(d)
            log.warning("Refused %s: missing %s, unknown fields %s", d.get("site_product_id"), missing, unknown)
            continue
        doc = {f: d.get(f) for f in OFFER_FIELDS}
        doc["scraped_at"] = _to_date(doc["scraped_at"])
        reason = reason_of(doc)
        if reason:
            quarantined.append({**doc, "reason": reason})
        else:
            good.append(doc)
    return good, quarantined, refused


def upsert(collection, docs):
    """Insert new documents and update existing ones on the unique key. Returns the number of documents written."""
    if not docs:
        return 0
    ops = [UpdateOne({k: d[k] for k in KEY}, {"$set": d}, upsert=True) for d in docs]
    result = collection.bulk_write(ops, ordered=False)
    return result.upserted_count + result.matched_count


def load_files(files, client=None):
    """Load one or more offers files. Returns counts per collection."""
    db = get_db(client)
    ensure_indexes(db)
    docs = []
    for f in files:
        docs += json.loads(Path(f).read_text(encoding="utf-8"))
    good, bad, refused = split(docs)
    if good:   # an offer that is complete now leaves the quarantine of the same day
        db.offers_quarantine.delete_many({"$or": [{k: d[k] for k in KEY} for d in good]})
    result = {"read": len(docs), "offers": upsert(db.offers, good), "quarantine": upsert(db.offers_quarantine, bad),
              "refused": len(refused)}
    reasons = {}
    for d in bad:
        reasons[d["reason"]] = reasons.get(d["reason"], 0) + 1
    log.info("Loaded %s; quarantine reasons %s", result, reasons)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    paths = [p for a in sys.argv[1:] for p in sorted(glob.glob(a))]
    if not paths:
        sys.exit("usage: python mongo_load.py data/offers/offers_*_<date>.json")
    print(load_files(paths))
