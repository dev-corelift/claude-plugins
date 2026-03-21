#!/usr/bin/env python3
"""Scrape all recipes from bakewithzoha.com.

No JSON-LD available — uses WebFetch-style HTML extraction via the Tasty Recipes
plugin markup. Small site (~76 recipes), sequential is fine.

Usage: python3 scrape-zoha.py
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

SOURCE_SITE = "bakewithzoha"
SITEMAP_URL = "https://bakewithzoha.com/post-sitemap.xml"
HTTP_TIMEOUT = 15
REQUEST_DELAY = 0.5
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "data", "recipes.db")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_urls():
    xml_data = fetch(SITEMAP_URL)
    root = ET.fromstring(xml_data)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [u.find("sm:loc", ns).text for u in root.findall("sm:url", ns)]


def strip_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#8217;', "'", text)
    text = re.sub(r'&#8220;|&#8221;', '"', text)
    text = re.sub(r'&#8211;|&#8212;', '-', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&#\d+;', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def source_id(url):
    return url.rstrip("/").split("/")[-1]


def extract_recipe(html, url):
    """Extract recipe from Tasty Recipes plugin HTML."""
    # Recipe name — try tasty title first, fall back to page title
    name = None
    m = re.search(r'class="tasty-recipes-title[^"]*"[^>]*>(.*?)</', html, re.DOTALL)
    if m:
        name = strip_html(m.group(1))
    if not name:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            name = strip_html(m.group(1))
    if not name:
        return None

    # Description
    desc = ""
    m = re.search(r'class="tasty-recipes-description[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        desc = strip_html(m.group(1))

    # Image — og:image or first large content image
    image_url = ""
    m = re.search(r'property="og:image"[^>]*content="([^"]+)"', html)
    if m:
        image_url = m.group(1)

    # Times
    prep = cook = total = None
    m = re.search(r'class="tasty-recipes-prep-time"[^>]*>(\d+)', html)
    if m: prep = int(m.group(1))
    m = re.search(r'class="tasty-recipes-cook-time"[^>]*>(\d+)', html)
    if m: cook = int(m.group(1))
    m = re.search(r'class="tasty-recipes-total-time"[^>]*>(\d+)', html)
    if m: total = int(m.group(1))
    if not total and prep and cook:
        total = prep + cook

    # Servings
    servings = None
    m = re.search(r'class="tasty-recipes-yield"[^>]*>.*?(\d+)', html, re.DOTALL)
    if m: servings = int(m.group(1))

    # Ingredients — look for the ingredients section
    ingredients = []
    ing_section = re.search(
        r'class="tasty-recipes-ingredients[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if ing_section:
        items = re.findall(r'<li[^>]*>(.*?)</li>', ing_section.group(1), re.DOTALL)
        ingredients = [strip_html(i) for i in items if strip_html(i)]

    # If no ingredients found, try broader search between Ingredients/Instructions headers
    if not ingredients:
        section = re.search(r'Ingredients(.*?)Instructions', html, re.DOTALL)
        if section:
            items = re.findall(r'<li[^>]*>(.*?)</li>', section.group(1), re.DOTALL)
            ingredients = [strip_html(i) for i in items if strip_html(i)]

    # Steps
    steps = []
    step_section = re.search(
        r'class="tasty-recipes-instructions[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if step_section:
        items = re.findall(r'<li[^>]*>(.*?)</li>', step_section.group(1), re.DOTALL)
        steps = [strip_html(i) for i in items if strip_html(i)]

    if not steps:
        section = re.search(r'Instructions(.*?)(?:Notes|Nutrition|Video|$)', html, re.DOTALL)
        if section:
            items = re.findall(r'<li[^>]*>(.*?)</li>', section.group(1), re.DOTALL)
            steps = [strip_html(i) for i in items if strip_html(i)]

    # Categories from breadcrumbs or tags
    categories = []
    cats = re.findall(r'rel="tag"[^>]*>(.*?)<', html)
    categories = list(dict.fromkeys(strip_html(c) for c in cats if strip_html(c)))

    if not ingredients and not steps:
        return None

    return {
        "source_site": SOURCE_SITE,
        "source_id": source_id(url),
        "source_url": url,
        "name": name,
        "description": desc,
        "image_url": image_url,
        "yield_servings": servings,
        "prep_mins": prep,
        "cook_mins": cook,
        "total_mins": total,
        "ingredients": ingredients,
        "steps": steps,
        "categories": categories,
    }


def main():
    print("=" * 60)
    print("BAKEWITHZOHA RECIPE SCRAPER")
    print("=" * 60)

    print("\nFetching sitemap...")
    urls = get_urls()
    print(f"  Found {len(urls)} URLs")

    db = sqlite3.connect(DB_PATH)
    existing = set(
        r[0] for r in db.execute(
            "SELECT source_id FROM recipes WHERE source_site = ?", (SOURCE_SITE,)
        )
    )
    print(f"  Already in DB: {len(existing)}")

    to_scrape = [u for u in urls if source_id(u) not in existing]
    print(f"  New URLs: {len(to_scrape)}")

    scraped = 0
    skipped = 0
    errors = 0

    for i, url in enumerate(to_scrape, 1):
        slug = source_id(url)
        print(f"  [{i}/{len(to_scrape)}] {slug}... ", end="", flush=True)

        try:
            html = fetch(url)
            recipe = extract_recipe(html, url)
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
            time.sleep(REQUEST_DELAY)
            continue

        if not recipe:
            print("no recipe found")
            skipped += 1
            time.sleep(REQUEST_DELAY)
            continue

        try:
            cur = db.execute(
                """INSERT INTO recipes (source_site, source_id, source_url, name, description,
                    image_url, yield_servings, prep_mins, cook_mins, total_mins, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                (recipe["source_site"], recipe["source_id"], recipe["source_url"],
                 recipe["name"], recipe["description"], recipe["image_url"],
                 recipe["yield_servings"], recipe["prep_mins"], recipe["cook_mins"],
                 recipe["total_mins"]),
            )
            rid = cur.lastrowid
            for j, text in enumerate(recipe["ingredients"], 1):
                db.execute("INSERT INTO ingredients (recipe_id, position, text) VALUES (?,?,?)",
                           (rid, j, text))
            for j, text in enumerate(recipe["steps"], 1):
                db.execute("INSERT INTO steps (recipe_id, position, text) VALUES (?,?,?)",
                           (rid, j, text))
            for cat in recipe["categories"]:
                db.execute("INSERT INTO tags (recipe_id, type, value) VALUES (?,?,?)",
                           (rid, "category", cat))
            db.commit()
            print(f"#{rid} — {len(recipe['ingredients'])} ing, {len(recipe['steps'])} steps")
            scraped += 1
        except sqlite3.IntegrityError:
            print("duplicate")
            skipped += 1
        except Exception as e:
            print(f"DB ERROR: {e}")
            errors += 1

        time.sleep(REQUEST_DELAY)

    db.close()
    print(f"\n{'=' * 60}")
    print(f"COMPLETE — {scraped} scraped, {skipped} skipped, {errors} errors")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
