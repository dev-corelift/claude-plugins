#!/usr/bin/env python3
"""Scrape recipes from justapinch.com via sitemap + JSON-LD.

Uses Bright Data residential proxies with concurrent workers for speed.
Only inserts recipes meeting quality thresholds (rating, review count).

Usage:
  python3 scrape-justapinch.py                  # full scrape, all sitemaps
  python3 scrape-justapinch.py --limit 5000     # cap at N URLs
  python3 scrape-justapinch.py --workers 10     # adjust concurrency
  python3 scrape-justapinch.py --dry-run        # count URLs only
  python3 scrape-justapinch.py --no-proxy       # skip proxy (local dev)
"""

import json
import os
import re
import sqlite3
import ssl
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ============================================================================
# Config
# ============================================================================

SITEMAP_INDEX = "https://www.justapinch.com/sitemap.xml"
SITEMAP_URLS = [
    "https://www.justapinch.com/sitemaps/sitemap2.xml.gz",
    "https://www.justapinch.com/sitemaps/sitemap2.1.xml.gz",
    "https://www.justapinch.com/sitemaps/sitemap2.2.xml.gz",
    "https://www.justapinch.com/sitemaps/sitemap2.3.xml.gz",
]
SOURCE_SITE = "justapinch"
DEFAULT_WORKERS = 25
HTTP_TIMEOUT = 20
MIN_RATING = 4.0
MIN_REVIEWS = 3
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Bright Data residential proxy
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = 33335
PROXY_USER = "brd-customer-hl_42c64f82-zone-resprox01"
PROXY_PASS = "g2xzsn4x3l03"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "data", "recipes.db")

# ============================================================================
# HTTP
# ============================================================================

def make_opener(use_proxy=True):
    """Build a urllib opener with optional proxy support."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    handlers = [urllib.request.HTTPSHandler(context=ssl_ctx)]
    if use_proxy:
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        handlers.append(urllib.request.ProxyHandler({
            "http": proxy_url,
            "https": proxy_url,
        }))
    return urllib.request.build_opener(*handlers)


def fetch(url, opener):
    """GET a URL and return the response body as a string."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")

# ============================================================================
# Sitemap parsing
# ============================================================================

def get_recipe_urls(opener):
    """Pull all recipe URLs from the sitemaps."""
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []

    for sitemap_url in SITEMAP_URLS:
        print(f"  Fetching {sitemap_url}...")
        try:
            xml_data = fetch(sitemap_url, opener)
            root = ET.fromstring(xml_data)
            for url_elem in root.findall("sm:url", ns):
                loc = url_elem.find("sm:loc", ns)
                if loc is not None and "/recipes/" in loc.text:
                    urls.append(loc.text)
        except Exception as e:
            print(f"    ERROR: {e}")

    return urls

# ============================================================================
# JSON-LD extraction (same logic as diethood scraper)
# ============================================================================

def extract_recipe_jsonld(html):
    matches = re.findall(
        r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL
    )
    for raw in matches:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Recipe":
            return data
        if isinstance(data, dict) and "@graph" in data:
            for node in data["@graph"]:
                if isinstance(node, dict) and node.get("@type") == "Recipe":
                    return node
        if isinstance(data, list):
            for node in data:
                if isinstance(node, dict) and node.get("@type") == "Recipe":
                    return node
    return None


def parse_iso_duration(duration):
    if not duration:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return hours * 60 + mins if (hours or mins) else None


def parse_servings(yield_field):
    if isinstance(yield_field, int):
        return yield_field
    if isinstance(yield_field, list):
        for item in yield_field:
            if isinstance(item, int):
                return item
            if isinstance(item, str):
                nums = re.findall(r"\d+", item)
                if nums:
                    return int(nums[0])
        return None
    if isinstance(yield_field, str):
        nums = re.findall(r"\d+", yield_field)
        return int(nums[0]) if nums else None
    return None


def parse_nutrition(recipe):
    nut = recipe.get("nutrition", {})
    if not nut:
        return {}
    def parse_num(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        nums = re.findall(r"[\d.]+", str(val))
        return float(nums[0]) if nums else None
    return {
        "calories": parse_num(nut.get("calories")),
        "protein_g": parse_num(nut.get("proteinContent")),
        "fat_g": parse_num(nut.get("fatContent")),
        "carbs_g": parse_num(nut.get("carbohydrateContent")),
        "fiber_g": parse_num(nut.get("fiberContent")),
        "sugar_g": parse_num(nut.get("sugarContent")),
        "sodium_mg": parse_num(nut.get("sodiumContent")),
        "cholesterol_mg": parse_num(nut.get("cholesterolContent")),
    }


def extract_steps(instructions):
    if not instructions:
        return []
    steps = []
    if isinstance(instructions, str):
        return [instructions.strip()]
    for item in instructions:
        if isinstance(item, str):
            steps.append(item.strip())
        elif isinstance(item, dict):
            if item.get("@type") == "HowToSection":
                for sub in item.get("itemListElement", []):
                    if isinstance(sub, dict):
                        steps.append(sub.get("text", "").strip())
                    elif isinstance(sub, str):
                        steps.append(sub.strip())
            else:
                text = item.get("text", "").strip()
                if text:
                    steps.append(text)
    return [s for s in steps if s]


def extract_image(recipe):
    img = recipe.get("image")
    if isinstance(img, str):
        return img
    if isinstance(img, list) and img:
        return img[0] if isinstance(img[0], str) else img[0].get("url", "")
    if isinstance(img, dict):
        return img.get("url", "")
    return ""


def source_id_from_url(url):
    parts = url.rstrip("/").split("/")
    slug = parts[-1] if parts else url
    return slug.replace(".html", "")


def extract_list_field(recipe, key):
    val = recipe.get(key)
    if not val:
        return []
    if isinstance(val, list):
        return [v.strip() for v in val if isinstance(v, str) and v.strip()]
    if isinstance(val, str):
        return [v.strip() for v in val.split(",") if v.strip()]
    return []

# ============================================================================
# Scrape single recipe
# ============================================================================

def scrape_recipe(url, opener):
    """Fetch a URL and extract recipe data. Returns dict or None."""
    html = fetch(url, opener)
    recipe = extract_recipe_jsonld(html)
    if not recipe or not recipe.get("name", "").strip():
        return None

    # Check quality threshold before doing full parse
    agg = recipe.get("aggregateRating", {})
    rating = None
    rating_count = None
    if agg:
        try:
            rating = float(agg.get("ratingValue", 0))
            rating_count = int(agg.get("ratingCount", agg.get("reviewCount", 0)))
        except (ValueError, TypeError):
            pass

    if rating is not None and rating < MIN_RATING:
        return "low_rating"
    if rating_count is not None and rating_count < MIN_REVIEWS:
        return "low_reviews"

    prep = parse_iso_duration(recipe.get("prepTime"))
    cook = parse_iso_duration(recipe.get("cookTime"))
    total = parse_iso_duration(recipe.get("totalTime"))
    if not total and prep and cook:
        total = prep + cook

    nutrition = parse_nutrition(recipe)
    ingredients = recipe.get("recipeIngredient", [])
    if isinstance(ingredients, str):
        ingredients = [ingredients]
    steps = extract_steps(recipe.get("recipeInstructions", []))

    return {
        "source_site": SOURCE_SITE,
        "source_id": source_id_from_url(url),
        "source_url": url,
        "name": recipe.get("name", "").strip(),
        "description": recipe.get("description", "").strip(),
        "image_url": extract_image(recipe),
        "yield_servings": parse_servings(recipe.get("recipeYield")),
        "yield_text": str(recipe.get("recipeYield", "")),
        "prep_mins": prep,
        "cook_mins": cook,
        "total_mins": total,
        "calories": nutrition.get("calories"),
        "protein_g": nutrition.get("protein_g"),
        "fat_g": nutrition.get("fat_g"),
        "carbs_g": nutrition.get("carbs_g"),
        "fiber_g": nutrition.get("fiber_g"),
        "sugar_g": nutrition.get("sugar_g"),
        "sodium_mg": nutrition.get("sodium_mg"),
        "cholesterol_mg": nutrition.get("cholesterol_mg"),
        "rating": rating,
        "rating_count": rating_count,
        "ingredients": ingredients,
        "steps": steps,
        "categories": extract_list_field(recipe, "recipeCategory"),
        "cuisines": extract_list_field(recipe, "recipeCuisine"),
        "keywords": extract_list_field(recipe, "keywords"),
    }

# ============================================================================
# DB insert
# ============================================================================

def insert_recipe(db, lock, r):
    """Thread-safe insert of a recipe into the DB."""
    with lock:
        cursor = db.execute(
            """INSERT INTO recipes (
                source_site, source_id, source_url, name, description, image_url,
                yield_servings, yield_text, prep_mins, cook_mins, total_mins,
                calories, protein_g, fat_g, carbs_g, fiber_g, sugar_g,
                sodium_mg, cholesterol_mg, rating, rating_count, scraped_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (
                r["source_site"], r["source_id"], r["source_url"], r["name"],
                r["description"], r["image_url"], r["yield_servings"], r["yield_text"],
                r["prep_mins"], r["cook_mins"], r["total_mins"],
                r["calories"], r["protein_g"], r["fat_g"], r["carbs_g"],
                r["fiber_g"], r["sugar_g"], r["sodium_mg"], r["cholesterol_mg"],
                r["rating"], r["rating_count"],
            ),
        )
        recipe_id = cursor.lastrowid

        for i, text in enumerate(r["ingredients"], 1):
            db.execute(
                "INSERT INTO ingredients (recipe_id, position, text) VALUES (?,?,?)",
                (recipe_id, i, text),
            )
        for i, text in enumerate(r["steps"], 1):
            db.execute(
                "INSERT INTO steps (recipe_id, position, text) VALUES (?,?,?)",
                (recipe_id, i, text),
            )
        for cat in r["categories"]:
            db.execute(
                "INSERT INTO tags (recipe_id, type, value) VALUES (?,?,?)",
                (recipe_id, "category", cat),
            )
        for cuis in r["cuisines"]:
            db.execute(
                "INSERT INTO tags (recipe_id, type, value) VALUES (?,?,?)",
                (recipe_id, "cuisine", cuis),
            )
        for kw in r["keywords"]:
            db.execute(
                "INSERT INTO tags (recipe_id, type, value) VALUES (?,?,?)",
                (recipe_id, "keyword", kw),
            )
        db.commit()
        return recipe_id

# ============================================================================
# Worker
# ============================================================================

# Shared counters
class Stats:
    def __init__(self):
        self.scraped = 0
        self.filtered = 0
        self.no_recipe = 0
        self.errors = 0
        self.dupes = 0
        self.lock = Lock()

    def total_processed(self):
        return self.scraped + self.filtered + self.no_recipe + self.errors + self.dupes


def process_url(url, opener, db, db_lock, stats):
    """Worker function: fetch, parse, filter, insert."""
    slug = source_id_from_url(url)
    try:
        result = scrape_recipe(url, opener)

        if result is None:
            with stats.lock:
                stats.no_recipe += 1
            return None

        if result == "low_rating" or result == "low_reviews":
            with stats.lock:
                stats.filtered += 1
            return None

        try:
            rid = insert_recipe(db, db_lock, result)
            with stats.lock:
                stats.scraped += 1
            return (slug, rid, len(result["ingredients"]), len(result["steps"]))
        except sqlite3.IntegrityError:
            with stats.lock:
                stats.dupes += 1
            return None

    except Exception as e:
        with stats.lock:
            stats.errors += 1
        return None

# ============================================================================
# Main
# ============================================================================

def main():
    # Parse args
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    use_proxy = "--no-proxy" not in args
    limit = 0
    workers = DEFAULT_WORKERS

    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == "--workers" and i + 1 < len(args):
            workers = int(args[i + 1])

    print("=" * 60)
    print("JUSTAPINCH RECIPE SCRAPER")
    print(f"  Workers: {workers} | Proxy: {'ON' if use_proxy else 'OFF'}")
    print(f"  Quality filter: rating >= {MIN_RATING}, reviews >= {MIN_REVIEWS}")
    if limit:
        print(f"  URL limit: {limit}")
    print("=" * 60)

    # Build opener (no proxy for sitemaps — they're not blocked)
    plain_opener = make_opener(use_proxy=False)
    proxy_opener = make_opener(use_proxy=use_proxy)

    # Get URLs
    print("\nFetching sitemaps...")
    urls = get_recipe_urls(plain_opener)
    print(f"  Found {len(urls)} recipe URLs")

    # Check existing
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")

    existing = set()
    for row in db.execute(
        "SELECT source_id FROM recipes WHERE source_site = ?", (SOURCE_SITE,)
    ):
        existing.add(row[0])
    print(f"  Already in DB: {len(existing)} from {SOURCE_SITE}")

    to_scrape = [u for u in urls if source_id_from_url(u) not in existing]
    if limit and len(to_scrape) > limit:
        to_scrape = to_scrape[:limit]
    print(f"  URLs to scrape: {len(to_scrape)}")

    if dry_run:
        print("\n[DRY RUN] Would scrape these URLs:")
        for url in to_scrape[:20]:
            print(f"  {url}")
        if len(to_scrape) > 20:
            print(f"  ... and {len(to_scrape) - 20} more")
        db.close()
        return

    if not to_scrape:
        print("Nothing to scrape.")
        db.close()
        return

    # Scrape with thread pool
    stats = Stats()
    db_lock = Lock()
    started = time.time()
    last_report = started

    print(f"\nScraping with {workers} workers...")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(process_url, url, proxy_opener, db, db_lock, stats): url
            for url in to_scrape
        }

        for future in as_completed(futures):
            result = future.result()
            processed = stats.total_processed()

            # Progress report every 5 seconds
            now = time.time()
            if now - last_report >= 5 or processed == len(to_scrape):
                elapsed = now - started
                rate = processed / elapsed if elapsed > 0 else 0
                eta = int((len(to_scrape) - processed) / rate) if rate > 0 else 0
                print(
                    f"  [{processed}/{len(to_scrape)}] "
                    f"{stats.scraped} saved, {stats.filtered} filtered, "
                    f"{stats.no_recipe} no recipe, {stats.errors} errors | "
                    f"{rate:.1f}/s | ETA {eta}s"
                )
                last_report = now

    db.close()
    elapsed = int(time.time() - started)

    print(f"\n{'=' * 60}")
    print(f"COMPLETE in {elapsed}s")
    print(f"  Scraped:  {stats.scraped} recipes inserted")
    print(f"  Filtered: {stats.filtered} (below rating/review threshold)")
    print(f"  No recipe: {stats.no_recipe} (no JSON-LD)")
    print(f"  Dupes:    {stats.dupes}")
    print(f"  Errors:   {stats.errors}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
