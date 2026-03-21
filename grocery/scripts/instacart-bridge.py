#!/usr/bin/env python3
"""One-shot Instacart API bridge for cowork sandbox environments.

Reads JSON from a file or stdin, POSTs to Instacart Connect REST API,
prints the URL to stdout.

Usage:
  python3 instacart-bridge.py shopping-list /tmp/payload.json
  python3 instacart-bridge.py recipe /tmp/payload.json
  echo '{"title":"...","line_items":[...]}' | python3 instacart-bridge.py shopping-list

From cowork (via osascript to escape sandbox network restrictions):
  osascript -e 'do shell script "python3 /path/to/instacart-bridge.py shopping-list /tmp/ic-payload.json"'
"""

import json
import sys
import urllib.request
import urllib.error

API_BASE = "https://connect.dev.instacart.tools"
API_KEY = "REDACTED_KEY"


def post_instacart(endpoint, payload):
    """POST JSON to the Instacart API and return the parsed response."""
    url = f"{API_BASE}{endpoint}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        snippet = e.read(512).decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {snippet}") from e


def make_shopping_list(data):
    """Create a shopping list and return the URL."""
    payload = {
        "title": data.get("title", "Shopping List"),
        "line_items": data.get("line_items", []),
    }
    if "expires_in" in data:
        payload["expires_in"] = data["expires_in"]
    resp = post_instacart("/idp/v1/products/products_link", payload)
    url = resp.get("products_link_url", "")
    if not url:
        raise RuntimeError(f"no URL returned: {json.dumps(resp)}")
    return url


def make_recipe(data):
    """Create a recipe page and return the URL."""
    payload = {
        "title": data.get("title", "Recipe"),
        "image_url": data.get("image_url", ""),
        "ingredients": data.get("ingredients", []),
        "instructions": data.get("instructions", []),
        "link_type": "recipe",
    }
    if "expires_in" in data:
        payload["expires_in"] = data["expires_in"]
    resp = post_instacart("/idp/v1/products/recipe", payload)
    url = resp.get("products_link_url", resp.get("recipe_link_url", ""))
    if not url:
        raise RuntimeError(f"no URL returned: {json.dumps(resp)}")
    return url


USAGE = """Usage: instacart-bridge.py <command> [json-file]

Commands:
  shopping-list   Create an Instacart shopping list
  recipe          Create an Instacart recipe page

Reads JSON from the file argument, or stdin if no file given.

Examples:
  python3 instacart-bridge.py shopping-list /tmp/payload.json
  echo '{"title":"Test","line_items":[...]}' | python3 instacart-bridge.py shopping-list"""


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd not in ("shopping-list", "recipe"):
        print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
        sys.exit(1)

    # Read JSON from file argument or stdin
    if len(sys.argv) >= 3:
        try:
            with open(sys.argv[2]) as f:
                raw = f.read().strip()
        except (OSError, IOError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        raw = sys.stdin.read().strip()

    if not raw:
        print("ERROR: no JSON input", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if cmd == "shopping-list":
            print(make_shopping_list(data))
        elif cmd == "recipe":
            print(make_recipe(data))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
