"""
matching.py - the integration step: offers of the three sites -> one product list.   Task N2.
Rules: docs/data_dictionary.xlsx, sheet Matching_Rules (steps 1-8). Lists: 05_etl/config/*.csv.
Output (PostgreSQL): dim_product (upsert on product_code), product_map (upsert on site_key + site_product_id).

Match order (step 5): manual list -> same EAN as an already mapped offer -> offer already in product_map
                      -> model_code (TV) / name_spec (phone) -> new (a product seen on one site only)

How a key is built (revised 3-Nov-2026 after the review: the old key matched 0 products across sites):
  * text clean-up: Unicode direction marks removed, NFKC, lower case, Arabic words -> English (ARABIC_WORDS)
  * phone key = model tokens | RAM | storage
      - model tokens = the part of the title before the first separator (" - ", "—", "–", "(", ",", "/"),
        without brand words, memory, network, colour, SIM and filler words; '+' -> 'plus'; tokens sorted
        (so "Pro Max" = "Max Pro" and the Arabic word order does not matter)
      - RAM = the largest memory value <= 24 GB, storage = the largest value >= 32 GB (1 TB = 1024); colour ignored
      - Apple: RAM is left out (XPRS and Jumia do not show it; it is fixed per iPhone model)
      - 4G/5G: the token '5g' is kept ONLY for model names that some title in the batch calls 5G and another
        title explicitly calls 4G (e.g. Galaxy A17 4G and A17 5G, Oppo A6t); a title that says neither counts as 4G.
        Otherwise the token is dropped, because some sites omit it (Galaxy S25 Ultra is always 5G)
  * TV key = normalised model code: from the SKU when it looks like a model code, else from the title;
    upper case, no spaces/dots/hyphens, prefixes/suffixes of model_suffixes.csv removed; the year letter is kept
  * no key -> a 'new' product that belongs to this site only (its prices are still loaded)
"""
import csv
import hashlib
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config"
EXCLUDED_BRANDS = {"renewed"}            # decision 27-Oct-2026 (Mahmoud): refurbished offers are not matched

_BIDI = re.compile("[‎‏‪-‮⁦-⁩﻿]")
_SEPARATORS = re.compile(r"\s[-–—]\s|[–—(,/|]")
_MEMORY = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb|mb)\b")
_INTERNAL_CODE = re.compile(r"^[a-z]{1,2}\d{4,}$")         # e.g. Infinix X6879 (internal code, not the model name)

# Arabic words -> English (longest first is not needed: matching is on whole words)
ARABIC_WORDS = {
    # brands and series
    "سامسونج": "samsung", "جالاكسي": "galaxy", "جلاكسي": "galaxy", "جالكسي": "galaxy", "جلكسي": "galaxy", "أبل": "apple", "ابل": "apple", "آبل": "apple",
    "آيفون": "iphone", "ايفون": "iphone", "أيفون": "iphone", "شاومي": "xiaomi", "ريدمي": "redmi", "بوكو": "poco",
    "هونر": "honor", "إنفينكس": "infinix", "انفينكس": "infinix", "انفنكس": "infinix", "انفنيكس": "infinix",
    "انفينيكس": "infinix", "تكنو": "tecno", "تيكنو": "tecno", "ريلمي": "realme", "ريلمى": "realme", "موتو": "moto", "اوبو": "oppo", "أوبو": "oppo", "فيفو": "vivo", "نوكيا": "nokia", "هواوي": "huawei",
    "موتورولا": "motorola", "نوت": "note", "هوت": "hot", "سمارت": "smart", "زيرو": "zero", "كامون": "camon",
    "سبارك": "spark", "بوفا": "pova", "فانتوم": "phantom", "رينو": "reno", "نوفا": "nova", "ماجيك": "magic",
    "تشويز": "choice", "بلاي": "play", "بلاى": "play",
    # model words
    "برو": "pro", "ماكس": "max", "ألترا": "ultra", "الترا": "ultra", "أولترا": "ultra", "بلس": "plus", "لايت": "lite",
    "ميني": "mini", "فولد": "fold", "فليب": "flip", "إيدج": "edge", "ايدج": "edge", "اير": "air", "إير": "air",
    "نيو": "neo", "بريميوم": "premium", "جو": "go", "اي": "i",
    # units
    "جيجابايت": "gb", "جيجا": "gb", "غيغابايت": "gb", "غيغا": "gb", "جيجابايتس": "gb", "تيرابايت": "tb", "تيرا": "tb",
    "ميجابايت": "mb", "ميغابايت": "mb", "رام": "ram", "رامات": "ram",
}
# "8 جيجا بايت" -> "8 gb"
_ARABIC_PHRASES = [("جيجا بايت", "gb"), ("غيغا بايت", "gb"), ("تيرا بايت", "tb"), ("ميجا بايت", "mb")]

FILLER = {
    "dual", "sim", "esim", "ds", "single", "phone", "mobile", "smartphone", "cell", "4g", "lte", "nfc", "new",
    "pre", "order", "preorder", "global", "version", "international", "ram", "rom", "storage", "memory", "gb", "tb",
    "mb", "with", "and", "the", "&", "+", "unlocked", "renewed", "official", "warranty", "egypt", "charger",
}
# series words that some sites write and others leave out ("Samsung A17" / "Samsung Galaxy A17")
SERIES_WORDS = {"samsung": {"galaxy"}, "apple": {"iphone"}}
COLOURS = {"black", "white", "blue", "red", "green", "gold", "silver", "gray", "grey", "purple", "pink", "titanium",
           "graphite", "midnight", "starlight", "violet", "orange", "yellow", "navy", "light", "dark", "cyan",
           "lavender", "mint", "cream", "beige", "bronze", "brown", "teal"}


def read_csv(name):
    with open(CONFIG / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def product_code(brand, category, model_key):
    return f"{brand}|{category}|{model_key}"


def clean_text(text):
    """Remove direction marks, normalise Unicode, lower case, translate Arabic words, separate '+'."""
    t = unicodedata.normalize("NFKC", _BIDI.sub("", text or "")).lower()
    for ar, en in _ARABIC_PHRASES:
        t = t.replace(ar, f" {en} ")
    t = re.sub(r"\b(ram|rom)(\d)", r"\1 \2", t)                      # "ram128gb" -> "ram 128gb"
    t = re.sub(r"(\d)\s*(gb|tb|mb)", r"\1 \2", t)                  # "8gb" -> "8 gb"
    t = re.sub(r"(?<=[a-z0-9])-(?=[a-z0-9])", " ", t)                 # "galaxy-a27" -> "galaxy a27"
    t = re.sub(r"(?<=[a-z0-9])\+", " plus ", t)                       # "s26+" -> "s26 plus"
    t = re.sub(r"\s\+\s", " | ", t)                                   # "600 pro + band 10" -> bundle, cut
    t = re.sub(r"\+", " ", t)
    words = re.findall(r"[\w.]+|[^\w\s]", t)
    out = " ".join(ARABIC_WORDS.get(w, w) for w in words)
    return re.sub(r"\b(\d+) i\b", r"\1i", out)                      # Arabic "60 اي" -> "60i" (Hot 60i)


def normalize_brand(brand_raw, title, aliases):
    alias_map = {a["alias"].strip().lower(): a["brand"].strip().lower() for a in aliases}
    text = clean_text(brand_raw).strip()
    if not text:
        words = clean_text(title).split()
        text = words[0] if words else ""
    if text in alias_map:
        return alias_map[text]
    for tok in text.split():
        if tok in alias_map:
            return alias_map[tok]
    return text


def memory(text):
    """(ram, storage) in GB as strings, from every 'N GB/TB' in the text. MB values (feature phones) are ignored.
    A storage size written without a unit next to '/' ("128/ 6GB", "4+4/128") is also accepted."""
    sizes = []
    for value, unit in _MEMORY.findall(text):
        if unit == "mb":
            continue
        v = float(value) * (1024 if unit == "tb" else 1)
        sizes.append(int(v))
    rams = [v for v in sizes if v <= 24]
    stores = [v for v in sizes if v >= 32]
    if not stores:
        m = re.search(r"\b(32|64|128|256|512)\s*/|/\s*(32|64|128|256|512)\b", text)
        if m:
            stores = [int(m.group(1) or m.group(2))]
    return (str(max(rams)) if rams else None), (str(max(stores)) if stores else None)


def network(text):
    """'5g', '4g' (written explicitly) or None (not written)."""
    if re.search(r"\b5g\b", text):
        return "5g"
    if re.search(r"\b4g\b|\blte\b", text):
        return "4g"
    return None


def phone_parts(title, brand):
    """(model_tokens, network, ram, storage) for a phone title."""
    text = clean_text(title)
    ram, storage = memory(text)
    has_5g = network(text)
    head = _SEPARATORS.split(" " + text + " ", maxsplit=1)[0]
    head = re.split(r"\b\d+(?:\.\d+)?\s(?:gb|tb|mb)\b", head, maxsplit=1)[0]   # model words come before the memory
    brand_words = set(brand.split()) | {brand} | SERIES_WORDS.get(brand, set())
    tokens = []
    for w in head.split():
        if not re.fullmatch(r"[a-z0-9]+", w):          # punctuation and words that stayed Arabic
            continue
        if w in FILLER or w in COLOURS or w in brand_words or w == "5g":
            continue
        if re.fullmatch(r"\d+(gb|tb|mb)", w) or _INTERNAL_CODE.match(w):
            continue
        tokens.append(w)
    # memory numbers left in the head ("8 / 256" written without GB) are not model words
    mem_values = {ram, storage} - {None}
    tokens = [w for w in tokens if w not in mem_values]
    return sorted(set(tokens)), has_5g, ram, storage


def _looks_like_tv_code(code):
    return bool(re.fullmatch(r"[A-Z]{0,4}\d{2}[A-Z0-9]{2,14}", code)) and bool(re.search(r"\d{2}.*[A-Z]", code))


def tv_code(offer, brand, suffixes):
    """Normalised TV model code, or None."""
    candidates = []
    sku = _BIDI.sub("", offer.get("model_raw") or "").strip().upper()
    if sku and " " not in sku and not re.fullmatch(r"\d{8,}", sku):
        candidates.append(re.sub(r"[^A-Z0-9]", "", sku))
    title = unicodedata.normalize("NFKC", _BIDI.sub("", offer.get("title") or "")).upper()
    title_codes = []
    for tok in re.findall(r"[A-Z0-9][A-Z0-9-]{4,}", title):
        tok = tok.replace("-", "")
        if re.search(r"(INCH|INCHES|HZ|UHD|FHD|QLED|OLED|LED)$", tok):
            continue                                              # "43-Inch", "144HZ": not model codes
        title_codes.append(tok)
    candidates += sorted(title_codes, key=len, reverse=True)      # the full code is longer than its series (U8000H)
    for code in candidates:
        if _looks_like_tv_code(code) and not re.fullmatch(r"\d+", code):
            code = _apply_suffixes(code, brand, suffixes)
            if _looks_like_tv_code(code):
                return code
    return None


def _apply_suffixes(code, brand, suffixes):
    for row in suffixes:
        b = row["brand"].strip().lower()
        if b != "*" and b != brand:
            continue
        pos = row["position"].strip().lower()
        text = row["text"].strip().upper().replace(" ", "")
        if not text:
            continue
        if pos == "suffix" and code.endswith(text) and len(code) > len(text):
            code = code[: -len(text)]
        elif pos == "prefix" and code.startswith(text) and len(code) > len(text):
            code = code[len(text):]
    return code


def model_key(offer, suffixes, network_models=None):
    """Key of one offer (see the module docstring). network_models = model names that need the 5g token."""
    category = (offer.get("category") or "").strip()
    brand = offer.get("brand") or ""
    if category == "tv":
        return tv_code(offer, brand, suffixes)
    if category == "phone":
        tokens, net, ram, storage = phone_parts(offer.get("title") or "", brand)
        if not tokens or not storage:
            return None
        name = "-".join(tokens)
        if net == "5g" and (network_models is None or (brand, name) in network_models):
            name += "-5g"
        ram_part = "" if brand == "apple" else (ram or "")
        return f"{name}|{ram_part}|{storage}"
    return None


def assign_keys(offers, aliases, suffixes):
    """Set offer['brand'] and offer['model_key'] for a whole batch (the 5g rule needs the batch)."""
    seen = defaultdict(set)                      # (brand, name) -> {'5g', '4g', None}
    for o in offers:
        o["brand"] = normalize_brand(o.get("brand_raw"), o.get("title"), aliases)
        if o.get("category") == "phone":
            tokens, net, _r, _s = phone_parts(o.get("title") or "", o["brand"])
            if tokens:
                seen[(o["brand"], "-".join(tokens))].add(net)
    network_models = {key for key, nets in seen.items() if "5g" in nets and "4g" in nets}
    for o in offers:
        o["model_key"] = model_key(o, suffixes, network_models)
    return network_models


def _site_only_code(offer):
    digest = hashlib.sha1(f"{offer.get('site')}:{offer.get('site_product_id')}".encode()).hexdigest()[:10]
    return f"{offer.get('site')}-{digest}"


def match_offers(offers, existing_map, manual):
    """Return (site, site_product_id, product_code, match_method, match_key) for every offer."""
    manual_map = {(m["site"], m["site_product_id"]): m["product_code"] for m in manual if m.get("product_code")}
    ean_to_code = {}
    for off in offers:
        key = (off.get("site"), off.get("site_product_id"))
        if key in existing_map and off.get("ean"):
            ean_to_code[off["ean"]] = existing_map[key][0]

    results = []
    for off in offers:
        site, spid = off.get("site"), off.get("site_product_id")
        key = (site, spid)
        brand, category, mk = off.get("brand"), off.get("category"), off.get("model_key")
        if key in manual_map:
            pc = manual_map[key]
            results.append((site, spid, pc, "manual", pc))
            continue
        ean = off.get("ean")
        if ean and ean in ean_to_code and key not in existing_map:
            pc = ean_to_code[ean]
            results.append((site, spid, pc, "ean", pc))
            continue
        if key in existing_map:
            pc, method, mkey = existing_map[key]
            results.append((site, spid, pc, method, mkey))
            continue
        if brand and category and mk:
            pc = product_code(brand, category, mk)
            results.append((site, spid, pc, "model_code" if category == "tv" else "name_spec", pc))
        elif brand and category:
            pc = product_code(brand, category, _site_only_code(off))
            results.append((site, spid, pc, "new", pc))
        else:
            results.append((site, spid, None, "new", None))
    return results


def extract_specs(offer):
    category = (offer.get("category") or "").strip()
    out = {"ram_gb": None, "storage_gb": None, "screen_size_in": None}
    text = clean_text(offer.get("title") or "")
    if category == "phone":
        ram, storage = memory(text)
        out["ram_gb"] = int(ram) if ram else None
        out["storage_gb"] = int(storage) if storage and int(storage) <= 32767 else None
    elif category == "tv":
        m = re.search(r"\b(\d{2,3})\s*(?:inch|in\b|\"|”|بوصة)", text)
        if m:
            out["screen_size_in"] = int(m.group(1))
    return out


def _display_name(offer):
    """Prefer a short English title (Arabic titles stay only when no English one exists)."""
    title = (offer.get("title") or "").strip()
    return title[:200]


def upsert_products_and_map(pg_conn, matches, offers, snapshot_date, brand_by_key=None):
    by_key = {(o["site"], o["site_product_id"]): o for o in offers}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT site_code, site_key FROM dim_site")
        sites = dict(cur.fetchall())
        for site, spid, pc, method, mk in matches:
            off = by_key.get((site, spid), {})
            if pc is None or site not in sites:
                continue
            brand, category, model = pc.split("|", 2)
            specs = extract_specs(off)
            english = bool(re.search(r"[A-Za-z]{3}", off.get("title") or "")) and not re.search(r"[؀-ۿ]", off.get("title") or "")
            cur.execute("""
                INSERT INTO dim_product (product_code, category, brand, model_key, display_name,
                                         ram_gb, storage_gb, screen_size_in, first_seen_date, last_seen_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (product_code) DO UPDATE SET
                    display_name   = CASE WHEN %s THEN EXCLUDED.display_name ELSE dim_product.display_name END,
                    ram_gb         = COALESCE(dim_product.ram_gb,         EXCLUDED.ram_gb),
                    storage_gb     = COALESCE(dim_product.storage_gb,     EXCLUDED.storage_gb),
                    screen_size_in = COALESCE(dim_product.screen_size_in, EXCLUDED.screen_size_in),
                    last_seen_date = GREATEST(dim_product.last_seen_date, EXCLUDED.last_seen_date),
                    updated_at     = now()
                RETURNING product_key
            """, (pc, category, brand, model[:80], _display_name(off) or pc,
                  specs["ram_gb"], specs["storage_gb"], specs["screen_size_in"], snapshot_date, snapshot_date,
                  english))
            product_key = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO product_map (site_key, site_product_id, product_key, match_method, match_key,
                                         title_last, url, first_seen_date, last_seen_date, is_active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                ON CONFLICT (site_key, site_product_id) DO UPDATE SET
                    product_key = EXCLUDED.product_key,
                    match_method = EXCLUDED.match_method,
                    match_key = EXCLUDED.match_key,
                    title_last = EXCLUDED.title_last,
                    url = EXCLUDED.url,
                    last_seen_date = GREATEST(product_map.last_seen_date, EXCLUDED.last_seen_date),
                    is_active = TRUE
            """, (sites[site], spid, product_key, method, (mk or pc)[:120],
                  (off.get("title") or "")[:300], (off.get("url") or "")[:400], snapshot_date, snapshot_date))
