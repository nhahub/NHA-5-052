"""
Offline test of mongo_load.py - no MongoDB server needed (mongomock).
Run:  pip install mongomock  &&  python 02_nosql/tests/test_mongo_load.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import mongomock                     # noqa: E402
import mongo_load                    # noqa: E402
from common import new_offer         # noqa: E402

PASSED = []


def check(name, ok, detail=""):
    if not ok:
        raise AssertionError(f"FAILED: {name} {detail}")
    PASSED.append(name)
    print(f"  ok  {name}")


def offer(site, pid, price, in_stock=True, category="phone", day="2026-10-27"):
    return new_offer(site=site, site_product_id=pid, snapshot_date=day, scraped_at=f"{day}T06:00:12Z",
                     title="Samsung Galaxy A57 5G 8GB 256GB", category=category, sale_price=price, in_stock=in_stock,
                     source_format="json", raw_file="raw/x")


def write(docs):
    path = Path(tempfile.mkdtemp()) / "offers.json"
    path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    return str(path)


def main():
    client = mongomock.MongoClient()
    db = client["catalog"]
    day1 = [offer("xprs", "a57:1", 30299.0), offer("jumia", "SA948MW", 26295.0),
            offer("dream2000", "a17-5g:9", 0.0),                       # price 0 (seen on Dream 2000, 25-Oct)
            offer("jumia", "TV1", 9205.0, in_stock=None, category="tv"),
            offer("jumia", "AC1", 19480.0, category="ac"),             # air conditioners are out of scope
            {**offer("xprs", "bad", 10.0), "colour": "black"},         # field not in the data dictionary
            {**offer("xprs", "", 10.0)}]                               # missing key
    f1 = write(day1)

    print("1. first load")
    r = mongo_load.load_files([f1], client=client)
    check("2 good offers stored", r["offers"] == 2 and db.offers.count_documents({}) == 2, r)
    check("3 quarantined, 2 refused", r["quarantine"] == 3 and r["refused"] == 2, r)
    reasons = sorted(d["reason"] for d in db.offers_quarantine.find())
    check("quarantine reasons", reasons == ["no price", "no stock state", "out of scope"], reasons)
    doc = db.offers.find_one({"site": "xprs"})
    check("20 dictionary fields (+ _id)", len(doc) == 21, sorted(doc))
    check("scraped_at stored as a date", hasattr(doc["scraped_at"], "year"), type(doc["scraped_at"]))
    check("unique index ux_offer_day", db.offers.index_information()["ux_offer_day"].get("unique") is True)
    check("indexes on site and category", {"ix_site", "ix_category"} <= set(db.offers.index_information()))

    print("2. same file again")
    mongo_load.load_files([f1], client=client)
    check("no duplicates in offers", db.offers.count_documents({}) == 2)
    check("no duplicates in quarantine", db.offers_quarantine.count_documents({}) == 3)

    print("3. the Dream 2000 offer is fixed later the same day")
    mongo_load.load_files([write([offer("dream2000", "a17-5g:9", 20590.0)])], client=client)
    check("it moves to offers", db.offers.count_documents({"site_product_id": "a17-5g:9"}) == 1)
    check("and leaves the quarantine", db.offers_quarantine.count_documents({"site_product_id": "a17-5g:9"}) == 0)

    print("4. next day = new documents (price history)")
    mongo_load.load_files([write([offer("xprs", "a57:1", 29999.0, day="2026-10-28")])], client=client)
    check("two days of the same offer", db.offers.count_documents({"site_product_id": "a57:1"}) == 2)

    print("5. a new site is accepted only after it is added to OFFER_SITES")
    new_site = [offer("newsite", "13421", 7999.0)]
    os.environ.pop("OFFER_SITES", None)
    r = mongo_load.load_files([write(new_site)], client=client)
    check("unknown site -> quarantine 'out of scope'", r["quarantine"] == 1 and r["offers"] == 0, r)
    os.environ["OFFER_SITES"] = "xprs,dream2000,jumia,elghazawy,newsite"
    try:
        r = mongo_load.load_files([write(new_site)], client=client)
    finally:
        os.environ.pop("OFFER_SITES", None)
    check("listed site -> offers", r["offers"] == 1 and db.offers.count_documents({"site": "newsite"}) == 1, r)
    check("and it leaves the quarantine", db.offers_quarantine.count_documents({"site": "newsite"}) == 0)

    print(f"\nALL {len(PASSED)} CHECKS PASSED")


if __name__ == "__main__":
    main()
