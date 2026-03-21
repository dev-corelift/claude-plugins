#!/usr/bin/env python3
"""Scrape all recipes from diethood.com via sitemap + JSON-LD.

Pulls URLs from the post sitemaps, fetches each page, extracts the
Recipe JSON-LD block (Yoast/WPRM), and inserts into recipes.db.

Usage: python3 scrape-diethood.py [--dry-run]
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

SITEMAP_INDEX = "https://diethood.com/sitemap_index.xml"
SOURCE_SITE = "diethood"
REQUEST_DELAY = 0.3
HTTP_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "data", "recipes.db")


def fetch(url):
    """GET a URL and return the response body as a string."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_sitemap_urls():
    """Pull all post URLs from the sitemap index."""
    xml = fetch(SITEMAP_INDEX)
    root = ET.fromstring(xml)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    post_sitemaps = []
    for sitemap in root.findall("sm:sitemap", ns):
        loc = sitemap.find("sm:loc", ns)
        if loc is not None and "post-sitemap" in loc.text:
            post_sitemaps.append(loc.text)

    urls = []
    for sitemap_url in sorted(post_sitemaps):
        print(f"  Fetching sitemap: {sitemap_url}")
        xml = fetch(sitemap_url)
        root = ET.fromstring(xml)
        for url_elem in root.findall("sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is not None:
                urls.append(loc.text)
        time.sleep(REQUEST_DELAY)

    return urls


def extract_recipe_jsonld(html):
    """Extract the Recipe JSON-LD block from HTML. Returns dict or None."""
    matches = re.findall(
        r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    for raw in matches:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Direct Recipe type
        if isinstance(data, dict) and data.get("@type") == "Recipe":
            return data

        # Yoast @graph wrapper
        if isinstance(data, dict) and "@graph" in data:
            for node in data["@graph"]:
                if isinstance(node, dict) and node.get("@type") == "Recipe":
                    return node

        # Array of types
        if isinstance(data, list):
            for node in data:
                if isinstance(node, dict) and node.get("@type") == "Recipe":
                    return node

    return None


def parse_iso_duration(duration):
    """Parse ISO 8601 duration like PT10M or PT1H30M into minutes."""
    if not duration:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return hours * 60 + mins if (hours or mins) else None


def parse_servings(yield_field):
    """Extract integer servings from recipeYield (string, int, or array)."""
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
    """Extract nutrition values from the nutrition sub-object."""
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
    """Flatten recipeInstructions into a list of step strings."""
    if not instructions:
        return []
    steps = []
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
    """Get the first image URL from the image field."""
    img = recipe.get("image")
    if isinstance(img, str):
        return img
    if isinstance(img, list) and img:
        return img[0] if isinstance(img[0], str) else img[0].get("url", "")
    if isinstance(img, dict):
        return img.get("url", "")
    return ""


def source_id_from_url(url):
    """Extract a stable source ID from the URL slug."""
    # https://diethood.com/easy-chicken-enchiladas/ -> easy-chicken-enchiladas
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else url


def extract_keywords(recipe):
    """Parse keywords from the recipe JSON-LD."""
    kw = recipe.get("keywords")
    if not kw:
        return []
    if isinstance(kw, list):
        return [k.strip() for k in kw if isinstance(k, str) and k.strip()]
    if isinstance(kw, str):
        return [k.strip() for k in kw.split(",") if k.strip()]
    return []


def extract_categories(recipe):
    """Parse recipeCategory from JSON-LD."""
    cat = recipe.get("recipeCategory")
    if not cat:
        return []
    if isinstance(cat, list):
        return [c.strip() for c in cat if isinstance(c, str) and c.strip()]
    if isinstance(cat, str):
        return [c.strip() for c in cat.split(",") if c.strip()]
    return []


def extract_cuisines(recipe):
    """Parse recipeCuisine from JSON-LD."""
    cuis = recipe.get("recipeCuisine")
    if not cuis:
        return []
    if isinstance(cuis, list):
        return [c.strip() for c in cuis if isinstance(c, str) and c.strip()]
    if isinstance(cuis, str):
        return [c.strip() for c in cuis.split(",") if c.strip()]
    return []


def scrape_recipe(url):
    """Fetch a URL and extract recipe data. Returns dict or None."""
    try:
        html = fetch(url)
    except Exception as e:
        print(f"    FETCH ERROR: {e}")
        return None

    recipe = extract_recipe_jsonld(html)
    if not recipe:
        return None

    prep = parse_iso_duration(recipe.get("prepTime"))
    cook = parse_iso_duration(recipe.get("cookTime"))
    total = parse_iso_duration(recipe.get("totalTime"))
    if not total and prep and cook:
        total = prep + cook

    nutrition = parse_nutrition(recipe)
    ingredients = recipe.get("recipeIngredient", [])
    steps = extract_steps(recipe.get("recipeInstructions", []))

    # Rating
    agg = recipe.get("aggregateRating", {})
    rating = None
    rating_count = None
    if agg:
        try:
            rating = float(agg.get("ratingValue", 0))
            rating_count = int(agg.get("ratingCount", 0))
        except (ValueError, TypeError):
            pass

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
        "categories": extract_categories(recipe),
        "cuisines": extract_cuisines(recipe),
        "keywords": extract_keywords(recipe),
    }


def insert_recipe(db, r):
    """Insert a recipe and its ingredients, steps, and tags into the DB."""
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

    return recipe_id


def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("DIETHOOD RECIPE SCRAPER")
    print("=" * 60)

    # Get all URLs from sitemaps
    print("\nFetching sitemaps...")
    urls = get_sitemap_urls()
    print(f"  Found {len(urls)} URLs total")

    # Open DB
    db = sqlite3.connect(DB_PATH, isolation_level=None)

    # Check which URLs we already have
    existing = set()
    for row in db.execute(
        "SELECT source_id FROM recipes WHERE source_site = ?", (SOURCE_SITE,)
    ):
        existing.add(row[0])
    print(f"  Already in DB: {len(existing)} recipes from {SOURCE_SITE}")

    # Filter to new URLs only
    to_scrape = []
    for url in urls:
        sid = source_id_from_url(url)
        if sid not in existing:
            to_scrape.append(url)
    print(f"  New URLs to scrape: {len(to_scrape)}")

    if dry_run:
        print("\n[DRY RUN] Would scrape these URLs:")
        for url in to_scrape[:20]:
            print(f"  {url}")
        if len(to_scrape) > 20:
            print(f"  ... and {len(to_scrape) - 20} more")
        db.close()
        return

    # Scrape
    scraped = 0
    skipped = 0
    errors = 0
    started = time.time()

    for i, url in enumerate(to_scrape, 1):
        slug = source_id_from_url(url)
        print(f"  [{i}/{len(to_scrape)}] {slug}... ", end="", flush=True)

        recipe = scrape_recipe(url)
        if not recipe:
            print("no recipe found, skipping")
            skipped += 1
            time.sleep(REQUEST_DELAY)
            continue

        if not recipe["name"]:
            print("empty name, skipping")
            skipped += 1
            time.sleep(REQUEST_DELAY)
            continue

        try:
            db.execute("BEGIN")
            rid = insert_recipe(db, recipe)
            db.execute("COMMIT")
            n_ing = len(recipe["ingredients"])
            n_steps = len(recipe["steps"])
            print(f"#{rid} — {n_ing} ingredients, {n_steps} steps")
            scraped += 1
        except sqlite3.IntegrityError as e:
            db.execute("ROLLBACK")
            print(f"duplicate, skipping ({e})")
            skipped += 1
        except Exception as e:
            db.execute("ROLLBACK")
            print(f"ERROR: {e}")
            errors += 1

        time.sleep(REQUEST_DELAY)

    elapsed = int(time.time() - started)
    db.close()

    print(f"\n{'=' * 60}")
    print(f"COMPLETE in {elapsed}s")
    print(f"  Scraped: {scraped}")
    print(f"  Skipped: {skipped} (no recipe or duplicate)")
    print(f"  Errors:  {errors}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
