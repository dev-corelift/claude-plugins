#!/usr/bin/env python3
"""Schnucks store data harvester — Python port of main.go.

Fetches coupons, categories, and the full item catalog from the Schnucks API
and stores them in a local SQLite database for offline deal analysis.

Usage: python3 harvester.py <command>
Commands: init, coupons, categories, items, full, stats, deals
"""

import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# ============================================================================
# Constants
# ============================================================================

BASE_URL = "https://api.schnucks.com"
REQUEST_DELAY = 0.3  # 300ms between paginated requests
HTTP_TIMEOUT = 30
PAGE_SIZE = 100

# ============================================================================
# Configuration
# ============================================================================

def load_env(path):
    """Parse a .env file and set each key=value pair as an environment variable."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()
    except FileNotFoundError:
        pass


def must_env(key):
    """Return the value of the named env var, or exit if unset/empty."""
    v = os.environ.get(key, "")
    if not v:
        print(f"ERROR: required env var {key} is not set — see scripts/token_refresh.md", file=sys.stderr)
        sys.exit(1)
    return v


def load_config(db_path=""):
    """Build a config dict from environment variables."""
    if not db_path:
        db_path = os.environ.get("SCHNUCKS_DB_PATH", "")
    store_id = os.environ.get("SCHNUCKS_STORE_ID", "144")
    client_type = os.environ.get("SCHNUCKS_CLIENT_TYPE", "WEB_EXT")
    return {
        "auth_token": must_env("SCHNUCKS_AUTH_TOKEN"),
        "client_id": must_env("SCHNUCKS_CLIENT_ID"),
        "client_type": client_type,
        "store_id": store_id,
        "db_path": db_path,
    }

# ============================================================================
# HTTP client
# ============================================================================

def api_get(cfg, url, params=None):
    """Perform an authenticated GET against the Schnucks API and return parsed JSON."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    req.add_header("authorization", cfg["auth_token"])
    req.add_header("x-schnucks-client-type", cfg["client_type"])
    req.add_header("x-schnucks-client-id", cfg["client_id"])
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            if resp.status != 200:
                snippet = resp.read(512).decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {resp.status} from {url}: {snippet}")
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        snippet = e.read(512).decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code} from {url}: {snippet}") from e

# ============================================================================
# Database schema
# ============================================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS coupons (
    id                INTEGER PRIMARY KEY,
    source            TEXT    NOT NULL,
    description       TEXT,
    value_text        TEXT,
    limit_text        TEXT,
    terms             TEXT,
    category          TEXT,
    brand             TEXT,
    image_url         TEXT,
    expiration_date   INTEGER,
    clip_start_date   INTEGER,
    clip_end_date     INTEGER,
    expiry_type       TEXT,
    app_only          INTEGER DEFAULT 0,
    featured          INTEGER DEFAULT 0,
    fulfillment_type  TEXT,
    custom_categories TEXT,
    created_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    upc_id         INTEGER PRIMARY KEY,
    upc            TEXT,
    full_upc       TEXT,
    name           TEXT    NOT NULL,
    description    TEXT,
    brand_name     TEXT,
    regular_price  REAL,
    sale_price     REAL,
    price_string   TEXT,
    buy_quantity   INTEGER,
    free_quantity  INTEGER,
    markdown       INTEGER DEFAULT 0,
    markdown_price REAL,
    size_measure   REAL,
    size_uom       TEXT,
    aisle          TEXT,
    image_url      TEXT,
    tax_rate       REAL,
    area           TEXT,
    active         INTEGER DEFAULT 1,
    created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_coupons (
    upc_id     INTEGER NOT NULL,
    coupon_id  INTEGER NOT NULL,
    created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (upc_id, coupon_id),
    FOREIGN KEY (upc_id)    REFERENCES items(upc_id),
    FOREIGN KEY (coupon_id) REFERENCES coupons(id)
);

CREATE TABLE IF NOT EXISTS categories (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    parent_id     INTEGER,
    image_url     TEXT,
    display_order INTEGER,
    is_leaf       INTEGER DEFAULT 0,
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_categories (
    upc_id      INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (upc_id, category_id),
    FOREIGN KEY (upc_id)      REFERENCES items(upc_id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_type   TEXT    NOT NULL,
    category_id   INTEGER,
    items_count   INTEGER,
    coupons_count INTEGER,
    started_at    TEXT,
    completed_at  TEXT,
    status        TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_coupons_source     ON coupons(source);
CREATE INDEX IF NOT EXISTS idx_coupons_expiration ON coupons(expiration_date);
CREATE INDEX IF NOT EXISTS idx_items_brand        ON items(brand_name);
CREATE INDEX IF NOT EXISTS idx_items_sale         ON items(sale_price) WHERE sale_price IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_item_coupons       ON item_coupons(coupon_id);

CREATE VIEW IF NOT EXISTS v_best_deals AS
SELECT
    i.upc_id,
    i.name,
    i.brand_name,
    i.regular_price,
    i.sale_price,
    COALESCE(i.sale_price, i.regular_price) AS effective_price,
    i.aisle,
    c.source      AS coupon_source,
    c.value_text,
    c.description AS coupon_desc
FROM items i
JOIN item_coupons ic ON i.upc_id    = ic.upc_id
JOIN coupons      c  ON ic.coupon_id = c.id
WHERE c.expiration_date > (strftime('%s', 'now') * 1000)
ORDER BY i.brand_name, i.name;
"""

# ============================================================================
# Database helpers
# ============================================================================

def open_db(path):
    """Open the SQLite database and apply the schema."""
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def log_scrape(db, scrape_type, category_id, items_count, coupons_count, started, run_err=None):
    """Record a scrape run in the scrape_log table."""
    status = "success"
    err_msg = None
    if run_err is not None:
        status = "error"
        err_msg = str(run_err)
    started_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    db.execute(
        """INSERT INTO scrape_log (scrape_type, category_id, items_count, coupons_count,
           started_at, completed_at, status, error_message)
           VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,?,?)""",
        (scrape_type, category_id, items_count, coupons_count, started_str, status, err_msg),
    )


def bool_to_int(b):
    return 1 if b else 0


def truncate(s, n):
    if len(s) <= n:
        return s
    return s[: n - 1] + "\u2026"

# ============================================================================
# Upsert helpers
# ============================================================================

def upsert_coupon(db, c):
    """Insert or update a single coupon row."""
    cats = json.dumps(c.get("customCategories", []))
    db.execute(
        """INSERT INTO coupons (
            id, source, description, value_text, limit_text, terms,
            category, brand, image_url, expiration_date, clip_start_date,
            clip_end_date, expiry_type, app_only, featured, fulfillment_type,
            custom_categories, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            source            = excluded.source,
            description       = excluded.description,
            value_text        = excluded.value_text,
            limit_text        = excluded.limit_text,
            terms             = excluded.terms,
            category          = excluded.category,
            brand             = excluded.brand,
            image_url         = excluded.image_url,
            expiration_date   = excluded.expiration_date,
            clip_start_date   = excluded.clip_start_date,
            clip_end_date     = excluded.clip_end_date,
            expiry_type       = excluded.expiry_type,
            app_only          = excluded.app_only,
            featured          = excluded.featured,
            fulfillment_type  = excluded.fulfillment_type,
            custom_categories = excluded.custom_categories,
            updated_at        = CURRENT_TIMESTAMP""",
        (
            c["id"], c.get("source", ""), c.get("description", ""),
            c.get("valueText", ""), c.get("limitText", ""), c.get("terms", ""),
            c.get("category", ""), c.get("brand", ""), c.get("imageUrl", ""),
            c.get("expirationDate"), c.get("clipStartDate"), c.get("clipEndDate"),
            c.get("expiryType", ""), bool_to_int(c.get("appOnly", False)),
            bool_to_int(c.get("featured", False)), c.get("fulfillmentType", ""),
            cats,
        ),
    )


def upsert_item(db, item):
    """Insert or update an item row and refresh coupon/category links."""
    loc = item.get("location")
    area = loc["area"] if loc else ""
    upc_id = item["upcId"]

    db.execute(
        """INSERT INTO items (
            upc_id, upc, full_upc, name, description, brand_name,
            regular_price, sale_price, price_string,
            buy_quantity, free_quantity, markdown, markdown_price,
            size_measure, size_uom, aisle, image_url, tax_rate, area, active,
            updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(upc_id) DO UPDATE SET
            upc            = excluded.upc,
            full_upc       = excluded.full_upc,
            name           = excluded.name,
            description    = excluded.description,
            brand_name     = excluded.brand_name,
            regular_price  = excluded.regular_price,
            sale_price     = excluded.sale_price,
            price_string   = excluded.price_string,
            buy_quantity   = excluded.buy_quantity,
            free_quantity  = excluded.free_quantity,
            markdown       = excluded.markdown,
            markdown_price = excluded.markdown_price,
            size_measure   = excluded.size_measure,
            size_uom       = excluded.size_uom,
            aisle          = excluded.aisle,
            image_url      = excluded.image_url,
            tax_rate       = excluded.tax_rate,
            area           = excluded.area,
            active         = excluded.active,
            updated_at     = CURRENT_TIMESTAMP""",
        (
            upc_id, str(item.get("upc", "")), str(item.get("fullUpc", "")),
            item.get("name", ""), item.get("description", ""), item.get("brandName", ""),
            item.get("regularAmount"), item.get("adAmount"),
            item.get("priceString", ""),
            item.get("buyQuantity"), item.get("freeQuantity"),
            bool_to_int(item.get("markdown", False)), item.get("markdownPrice"),
            item.get("packageSizeMeasure"), item.get("packageSizeUom", ""),
            item.get("aisle", ""), item.get("mainImageUrl", ""),
            item.get("taxRate", 0), area, bool_to_int(item.get("active", True)),
        ),
    )

    # Refresh coupon links
    db.execute("DELETE FROM item_coupons WHERE upc_id = ?", (upc_id,))
    for cid in item.get("couponIds", []):
        db.execute(
            "INSERT OR IGNORE INTO item_coupons (upc_id, coupon_id) VALUES (?,?)",
            (upc_id, cid),
        )

    # Refresh category links
    db.execute("DELETE FROM item_categories WHERE upc_id = ?", (upc_id,))
    for cat in item.get("categoryInfoList", []):
        db.execute(
            "INSERT OR IGNORE INTO item_categories (upc_id, category_id) VALUES (?,?)",
            (upc_id, cat["id"]),
        )


def upsert_category(db, cat, parent_id=None):
    """Recursively insert or update a category node and all descendants."""
    is_leaf = bool_to_int(
        len(cat.get("upcIds", [])) > 0 or len(cat.get("childCategories", [])) == 0
    )
    db.execute(
        """INSERT INTO categories (id, name, parent_id, image_url, display_order, is_leaf)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name          = excluded.name,
            parent_id     = excluded.parent_id,
            image_url     = excluded.image_url,
            display_order = excluded.display_order,
            is_leaf       = excluded.is_leaf""",
        (cat["categoryId"], cat["name"], parent_id, cat.get("imageUrl", ""),
         cat.get("displayOrder", 0), is_leaf),
    )
    for child in cat.get("childCategories", []):
        upsert_category(db, child, parent_id=cat["categoryId"])

# ============================================================================
# API fetchers
# ============================================================================

def fetch_coupons(cfg):
    """Retrieve all coupons from the Schnucks API."""
    resp = api_get(cfg, BASE_URL + "/coupon-api/v1/coupons")
    return resp.get("data", [])


def fetch_category_tree(cfg):
    """Retrieve the full product category hierarchy."""
    resp = api_get(cfg, BASE_URL + "/item-catalog-api/v1/category-trees/HOME_SHOP",
                   {"store": cfg["store_id"]})
    return resp.get("data", {})


def fetch_all_items_in_category(cfg, category_id):
    """Paginate through all items in a category."""
    all_items = []
    page = 0
    while True:
        params = {
            "store": cfg["store_id"],
            "fulfillmentType": "SELF",
            "page": str(page),
            "size": str(PAGE_SIZE),
        }
        url = f"{BASE_URL}/item-catalog-api/v1/categories/{category_id}/items"
        resp = api_get(cfg, url, params)
        data = resp.get("data", [])
        pagination = resp.get("pagination", {})
        all_items.extend(data)
        total_pages = pagination.get("totalPages", 1)
        if page >= total_pages - 1 or not data:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return all_items

# ============================================================================
# Commands
# ============================================================================

def cmd_init(cfg):
    db = open_db(cfg["db_path"])
    db.close()
    print(f"Database initialized: {cfg['db_path']}")


def cmd_coupons(cfg):
    started = time.time()
    db = open_db(cfg["db_path"])
    try:
        print("Fetching coupons...")
        coupons = fetch_coupons(cfg)

        db.execute("BEGIN")
        for c in coupons:
            upsert_coupon(db, c)
        db.execute("COMMIT")

        schnucks = sum(1 for c in coupons if c.get("source") == "SCHNUCKS")
        ibotta = sum(1 for c in coupons if c.get("source") == "IBOTTA")
        print(f"  Stored {len(coupons)} coupons ({schnucks} Schnucks + {ibotta} Ibotta)")
        log_scrape(db, "coupons", None, 0, len(coupons), started)
    except Exception as e:
        try:
            db.execute("ROLLBACK")
        except Exception:
            pass
        log_scrape(db, "coupons", None, 0, 0, started, e)
        raise
    finally:
        db.close()


def cmd_categories(cfg):
    started = time.time()
    db = open_db(cfg["db_path"])
    try:
        print("Fetching category tree...")
        tree = fetch_category_tree(cfg)

        db.execute("BEGIN")
        upsert_category(db, tree)
        db.execute("COMMIT")

        row = db.execute("SELECT COUNT(*) FROM categories").fetchone()
        count = row[0] if row else 0
        print(f"  Stored {count} categories")
        log_scrape(db, "categories", None, count, 0, started)
    except Exception as e:
        try:
            db.execute("ROLLBACK")
        except Exception:
            pass
        log_scrape(db, "categories", None, 0, 0, started, e)
        raise
    finally:
        db.close()


def cmd_items(cfg):
    started = time.time()
    db = open_db(cfg["db_path"])
    try:
        rows = db.execute("SELECT id, name FROM categories WHERE is_leaf = 1").fetchall()
        print(f"Scraping {len(rows)} categories...")
        total = 0
        for i, (cat_id, cat_name) in enumerate(rows, 1):
            print(f"  [{i}/{len(rows)}] {cat_name} ({cat_id})... ", end="", flush=True)
            try:
                items = fetch_all_items_in_category(cfg, cat_id)
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            db.execute("BEGIN")
            for item in items:
                upsert_item(db, item)
            db.execute("COMMIT")

            print(f"{len(items)} items")
            total += len(items)
            time.sleep(REQUEST_DELAY)

        print(f"Total items scraped: {total}")
        log_scrape(db, "items", None, total, 0, started)
    except Exception as e:
        try:
            db.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        db.close()


def cmd_full(cfg):
    started = time.time()
    sep = "=" * 60
    print(f"{sep}\nSCHNUCKS FULL SCRAPE\n{sep}")

    cmd_coupons(cfg)
    cmd_categories(cfg)
    cmd_items(cfg)

    elapsed = int(time.time() - started)
    print(f"{sep}\nCOMPLETE in {elapsed}s\n{sep}")


def cmd_stats(cfg):
    db = sqlite3.connect(cfg["db_path"])
    try:
        queries = [
            ("Coupons", "SELECT COUNT(*) FROM coupons"),
            ("Schnucks", "SELECT COUNT(*) FROM coupons WHERE source='SCHNUCKS'"),
            ("Ibotta", "SELECT COUNT(*) FROM coupons WHERE source='IBOTTA'"),
            ("Items", "SELECT COUNT(*) FROM items"),
            ("Links", "SELECT COUNT(*) FROM item_coupons"),
            ("Categories", "SELECT COUNT(*) FROM categories"),
            ("Items w/ coupons", "SELECT COUNT(DISTINCT upc_id) FROM item_coupons"),
            ("On sale", "SELECT COUNT(*) FROM items WHERE sale_price IS NOT NULL"),
        ]
        vals = {}
        for name, q in queries:
            row = db.execute(q).fetchone()
            vals[name] = row[0] if row else 0

        print(
            f"Schnucks Deal Database\n"
            f"======================\n"
            f"Coupons:    {vals['Coupons']} total ({vals['Schnucks']} Schnucks + {vals['Ibotta']} Ibotta)\n"
            f"Items:      {vals['Items']} products\n"
            f"Links:      {vals['Links']} item-coupon links\n"
            f"Categories: {vals['Categories']}\n\n"
            f"Items with coupons: {vals['Items w/ coupons']}\n"
            f"Items on sale:      {vals['On sale']}"
        )
    finally:
        db.close()


def cmd_deals(cfg):
    db = sqlite3.connect(cfg["db_path"])
    try:
        rows = db.execute(
            """SELECT i.brand_name, i.name, i.regular_price, c.value_text
            FROM items i
            JOIN item_coupons ic ON i.upc_id    = ic.upc_id
            JOIN coupons      c  ON ic.coupon_id = c.id
            WHERE c.expiration_date > (strftime('%s','now') * 1000)
            ORDER BY i.brand_name, i.name
            LIMIT 50"""
        ).fetchall()
        for brand, name, price, value_text in rows:
            print(f"{truncate(brand or '', 20):<20} {truncate(name or '', 45):<45} ${price or 0:5.2f}  {value_text or ''}")
    finally:
        db.close()

# ============================================================================
# Entry point
# ============================================================================

USAGE = """Usage: harvester.py <command>

Commands:
  init        Initialize database schema
  coupons     Scrape coupons only
  categories  Scrape category tree
  items       Scrape all items (requires categories)
  full        Full scrape: coupons + categories + items
  stats       Show database statistics
  deals       Show items with active coupons"""


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    db_path = os.path.join(script_dir, "..", "data", "schnucks.db")

    load_env(env_path)
    cfg = load_config(db_path)

    cmd = sys.argv[1].lower()
    commands = {
        "init": lambda: cmd_init(cfg),
        "coupons": lambda: cmd_coupons(cfg),
        "categories": lambda: cmd_categories(cfg),
        "items": lambda: cmd_items(cfg),
        "full": lambda: cmd_full(cfg),
        "stats": lambda: cmd_stats(cfg),
        "deals": lambda: cmd_deals(cfg),
    }

    if cmd not in commands:
        print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
        sys.exit(1)

    try:
        commands[cmd]()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
