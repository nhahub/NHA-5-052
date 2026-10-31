"""
matching.py - the integration step: offers of the three sites -> one product list.   SKELETON - task N2 (Eng. Nouran), due 1-Nov.

Rules: docs/data_dictionary.xlsx, sheet Matching_Rules (steps 1-8). Lists: 05_etl/config/*.csv (brand aliases,
model suffixes, category map, manual matches) - one place each, filled by Aya (A7) and Mahmoud / Islam (reviews).
Starting point: 02_nosql/scripts/overlap_test.py already builds a first key (brand | category | model) that worked on
Arabic and English titles; this module makes it exact and stores the result.

Output (PostgreSQL):
  dim_product   one row per real product   (upsert on product_code)
  product_map   one row per site offer     (upsert on site_key + site_product_id) with match_method and match_key
Match order (step 5):  ean -> model_code (TV) / name_spec (phone) -> manual -> new
"""
import csv
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config"


def read_csv(name):
    """Rows of a config file as dicts. READY."""
    with open(CONFIG / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def product_code(brand, category, model_key):
    """Natural key of dim_product: brand | category | model_key (step 6). READY."""
    return f"{brand}|{category}|{model_key}"


def normalize_brand(brand_raw, title, aliases):
    """Step 2. TODO N2: lower case, trim; map with aliases (brand_aliases.csv); if brand_raw is empty use the first
    word of the title. Return e.g. 'samsung'."""
    raise NotImplementedError("TODO N2: normalize_brand()")


def model_key(offer, suffixes):
    """Steps 3-4. TODO N2:
       TV      : code from model_raw or title -> upper case, no spaces/dots/hyphens, remove suffixes listed in
                 model_suffixes.csv for that brand (keep the model-year letter: U8000F and U8000H are different)
       phone   : model name + RAM + storage, colour ignored  (e.g. 'galaxy-a57-5g|8|256'); keep FE, +, Plus, Pro, Max,
                 Ultra, Lite and 4G/5G in the name (overlap test 25-Oct: S26 / S26+ / S26 FE and A17 4G / 5G are different)
       Return None when no key can be built (the offer then becomes match_method 'new')."""
    raise NotImplementedError("TODO N2: model_key()")


def match_offers(offers, existing_map, manual):
    """Step 5. TODO N2: for each offer return (site, site_product_id, product_code, match_method, match_key):
       1. a row in manual_matches.csv wins ('manual')
       2. same EAN as an already matched offer ('ean')
       3. same product_code built from brand + category + model_key ('model_code' for tv, 'name_spec' for phone)
       4. otherwise a new product ('new')
       existing_map = the current product_map, so an offer keeps its product from day to day."""
    raise NotImplementedError("TODO N2: match_offers()")


def upsert_products_and_map(pg_conn, matches, offers, snapshot_date):
    """TODO N2: INSERT ... ON CONFLICT (product_code) DO UPDATE for dim_product (display_name, last_seen_date,
    updated_at) and ON CONFLICT (site_key, site_product_id) DO UPDATE for product_map (title_last, url,
    last_seen_date, is_active). Set is_active = FALSE for offers of the site missing from today's run.
    Do NOT commit here: load_prices.py commits once, together with the price rows."""
    raise NotImplementedError("TODO N2: upsert_products_and_map()")
