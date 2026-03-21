---
name: dinner-planner
description: >
  This skill should be used when the user asks to "plan meals", "plan this week",
  "what should we eat", "what's for dinner", "make a meal plan", or "plan the week's dinners".
  It generates a 7-dinner weekly plan for a family of 7, priced against live Schnucks data,
  with full recipes written to ~/Documents/kitchen/YYYY-WXX/dinner/.
version: 0.1.0
---

# Meal Planning

Plan 7 dinners for a family of 7, within budget, avoiding recent repeats, with full printable recipes.

**Two phases — nothing gets written until the user approves both the meal selection AND the shopping list.**

---

## PHASE 1 — Discovery (no file writes)

### Step 1 — Load household config
Read `${CLAUDE_PLUGIN_ROOT}/context/household.md`
- Family size, dietary restrictions, monthly budget, paths, DB locations

### Step 1b — Read ledger and budget
- Read `~/Documents/kitchen/ledger.md` — check total spent this month vs $1,400 monthly budget
- Read `~/Documents/kitchen/YYYY-WXX/budget.md` if it exists — check what lunch/baking have already claimed this week
- Calculate: remaining weekly budget = $350 minus any already-logged lunch or baking spend
- Tell the user: "This week's budget: $350. [Lunch: $XX, Baking: $XX already planned.] Dinner budget: $XXX remaining."

### Step 2 — Check Schnucks DB freshness
Query `SELECT MAX(updated_at) FROM items` via `schnucks-db` MCP:
- Today is **Tuesday** → always refresh: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/harvester.py full`
- Last update **older than 7 days** → refresh: run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/harvester.py full`
- Otherwise → skip. Tell the user: "Schnucks DB last updated X days ago, skipping refresh."

### Step 3 — Check recent meal history
Scan `~/Documents/kitchen/` for the last 4 week folders (YYYY-WXX), read each `dinner/meal-plan.md`:
- Extract: meals already made (to avoid repeats), money spent per week
- Calculate: total spent this month so far, remaining weekly budget

### Step 4 — Check what's on sale this week
Query `schnucks-db` for items currently on sale (sale_price IS NOT NULL):
- Focus on proteins: chicken, beef, pork, seafood
- Note sale items as a soft preference — **not a hard requirement**
- Sale items get a small boost in recipe selection, but recipe quality and variety come first

```sql
SELECT name, brand_name, regular_price, sale_price, aisle
FROM items
WHERE sale_price IS NOT NULL
  AND aisle IN ('Meat', 'MEAT F', 'MEAT &', 'Seafood', 'Produce')
ORDER BY (regular_price - sale_price) DESC
LIMIT 30
```

### Step 5 — Find recipe candidates from recipes.db

Run **7 separate queries** — one per protein/category — each pulling a random pool.
This forces variety and prevents always surfacing the same top-rated recipes.

**Categories to target across the 7 queries:** chicken, beef, pork, seafood, pasta, vegetarian, soup/stew

```sql
SELECT r.id, r.name, r.total_mins, r.yield_servings, r.rating, r.rating_count,
       GROUP_CONCAT(CASE WHEN t.type='category' THEN t.value END) as categories,
       GROUP_CONCAT(CASE WHEN t.type='cuisine' THEN t.value END) as cuisines
FROM recipes r
LEFT JOIN tags t ON t.recipe_id = r.id
WHERE r.rating >= 4.0
  AND r.rating_count >= 15
  AND r.total_mins <= 60
  AND r.total_mins IS NOT NULL
  AND r.id IN (
    SELECT recipe_id FROM tags
    WHERE type = 'category' AND value LIKE '%[category]%'
  )
GROUP BY r.id
ORDER BY RANDOM()
LIMIT 10
```

- From each pool of 10, pick the 1 best fit
- Filter out anything made in the last 3 weeks
- **Give a mild preference** to recipes whose primary protein is on sale this week — but do NOT sacrifice recipe quality or variety for a sale item
- For Sunday, allow `total_mins <= 90`
- **Never sort by rating DESC across the full DB** — this causes repetition

**Variety rules across the 7 picks:**
- Max 2 chicken dishes
- Max 1 beef, 1 pork, 1 seafood
- At least 1 fully vegetarian
- At least 2 different cuisine styles (Mexican, Asian, Italian, American, Mediterranean, etc.)
- No two dishes with the same primary cooking method

### Step 6 — Present proposed meals for approval

Show the 7 proposed meals. **Wait for approval before going further.**

```
Here's this week's proposed plan:

Mon — Chicken Tikka Masala         45 min | 4.7★ | ~$18
Tue — Beef & Broccoli Stir Fry     30 min | 4.6★ | ~$22  🏷️ beef on sale
Wed — Pasta Primavera (veg)        25 min | 4.5★ | ~$12
Thu — Sheet Pan Pork Tenderloin    40 min | 4.8★ | ~$20
Fri — Shrimp Tacos                 30 min | 4.6★ | ~$24
Sat — Slow Cooker Chicken Soup     60 min | 4.7★ | ~$16
Sun — Lasagna                      90 min | 4.9★ | ~$28

Est. total: ~$140 + tax | Budget: $350

Approve this plan, or tell me what to swap.
```

🏷️ flag = primary protein is on sale this week

Handle swaps here conversationally before moving on. See "Handling Swaps" section below.

### Step 7 — Fetch full recipe details (after approval)

For each approved recipe:
```sql
SELECT text FROM ingredients WHERE recipe_id = ? ORDER BY position;
SELECT text FROM steps WHERE recipe_id = ? ORDER BY position;
```

### Step 8 — Price ingredients against Schnucks

For each recipe's ingredient list, query `schnucks-db` MCP:
- Match ingredient name against `items.name` — use sale_price if available, otherwise regular_price
- Flag any ingredients with active Ibotta coupons as savings opportunities

**Pricing rules:**

1. **Fresh meat (per-lb)** — aisle `MEAT F`, no size in parentheses in name
   - Price IS per lb → multiply by lbs needed scaled to 7 servings
   - Example: 1.5 lbs for 4 servings → scale to 7 → 2.625 lbs × $4.79 = $12.57

2. **Packaged meat/frozen** — has `(X Oz)` or `(X Lb)` in name
   - Price is per package → calculate lbs needed, divide by package size, round up
   - Example: need 3 lbs, package is 48 Oz (3 lbs) → 1 package → $10.99

3. **Produce — per-unit** — peppers, cucumbers, limes, onions, garlic (sold individually)
   - Price per each → scale count to 7 servings

4. **Produce — per-lb** — bananas, carrots, potatoes (sold by weight)
   - Price per lb → multiply by lbs needed scaled to 7

5. **Pantry/packaged goods** — canned goods, pasta, spices, sauces
   - Price per package → estimate packages needed for scaled recipe

**When in doubt:** explicit weight in recipe = weight math; count in recipe = count math, scaled to 7.

### Step 9 — Present shopping list for approval

Show the consolidated shopping list with totals. **Wait for approval before writing any files.**

```
Shopping list for the week:

MEAT & SEAFOOD
  Chicken thighs (fresh, ~3.5 lbs)     $6.97   Schnucks $1.99/lb
  Ground beef 80% lean (~2 lbs)        $13.98  on sale
  Shrimp, 1 lb                         $9.99
  Pork tenderloin, ~2 lbs              $9.58

PRODUCE
  ...

PANTRY
  ...

Subtotal:  $XXX.XX
Tax 8.35%: $XX.XX
Total:     $XXX.XX  (Budget remaining: $XXX.XX)

Ibotta savings available: [list any]

Ready to write files and add to calendar?
```

---

## PHASE 2 — Commit (only after approval)

### Step 10 — Write all files

Create `~/Documents/kitchen/YYYY-WXX/dinner/` and write:

**meal-plan.md**
```markdown
# Week XX — Mon MMM D - Sun MMM D, YYYY
**Subtotal:** $XXX.XX | **Tax (8.35%):** $XX.XX | **Total:** $XXX.XX
**Meals:** meal one, meal two, meal three, meal four, meal five, meal six, meal seven
**Notes:** any relevant notes
```

**shopping-list.md**
```markdown
# Shopping List — Week XX

**Subtotal:** $XXX.XX
**Tax (8.35%):** $XX.XX
**Total with tax:** $XXX.XX
**Weekly budget:** $350.00 | **Remaining:** $XX.XX

## Meat & Seafood
- item, qty, ~$X.XX

## Produce
- item, qty, ~$X.XX

## Dairy / Pantry / etc.
...

## Savings This Week
- item on sale — save $X.XX
```

**One file per dinner:** `monday-meal-name.md` through `sunday-meal-name.md`
```markdown
# [Meal Name] — [Day] [Date]
**Serves:** 7 | **Est. Cost:** $XX.XX | **Time:** XX min

## Ingredients
- X lbs item — $X.XX (Schnucks[, on sale])

## Steps
1. ...

## Notes
Tips, substitutions, make-ahead instructions.
```

**Instacart shopping list** — after writing the shopping-list.md, create the Instacart link using the `mcp__Control_your_Mac__osascript` tool. This runs on the host Mac outside the sandbox, so it can reach the Instacart API.

Call `mcp__Control_your_Mac__osascript` with a single `script` parameter containing AppleScript:
```applescript
do shell script "echo '<JSON_PAYLOAD>' > /tmp/ic-payload.json && python3 '/Users/jnuts74/projects/tools/cowork-plugins/grocery/scripts/instacart-bridge.py' shopping-list /tmp/ic-payload.json 2>&1"
```
- Replace `<JSON_PAYLOAD>` with the actual JSON containing `title`, `expires_in`, and `line_items`
- Escape single quotes in the JSON as `'\\''`
- Build the `line_items` array from the approved shopping list (see conversion table below)
- The bridge returns a single Instacart URL — include it in the confirmation message so the user can click to add everything to their cart

**Converting recipe quantities to grocery quantities for Instacart lineItems:**

Instacart matches product names to real store items. Send names and quantities that match how items are actually sold, not recipe measurements.

| Category | Rule | Example |
|---|---|---|
| Meat/seafood (sold by weight) | Send recipe weight | `"sea scallops", qty: 1, unit: "pound"` |
| Produce (sold by weight) | Send recipe weight | `"white button mushrooms", qty: 0.5, unit: "pound"` |
| Produce (sold by each) | Send count | `"lemon", qty: 1, unit: "each"` |
| Butter/dairy/eggs | Send 1 package | `"eggs", qty: 1, unit: "dozen"` — never "egg yolk" |
| Wine/liquor | Send 1 bottle | `"white wine", qty: 1, unit: "each"` — never "1 cup" |
| Cream/milk | Send 1 container | `"heavy whipping cream", qty: 1, unit: "each"` |
| Spices/seasonings | Send 1 jar | `"cayenne pepper", qty: 1, unit: "each"` |
| Cheese | Include form in name | `"shredded Gruyere cheese", qty: 1, unit: "each"` |
| Canned goods | Send can count | `"black olives", qty: 1, unit: "each"` |
| Pasta/rice/dry goods | Send 1 package | `"fusilli pasta", qty: 1, unit: "each"` |

**Key rules:**
- Never send recipe-only terms as item names (e.g. "egg yolk" — send "eggs")
- Never send fractional pantry quantities (e.g. "2 tablespoons butter" — send 1 each butter)
- Include form/cut in the name when it affects the product match (e.g. "shredded", "sliced", "boneless skinless")

### Step 10b — Update budget.md and ledger.md

Write/update `~/Documents/kitchen/YYYY-WXX/budget.md`:
```markdown
# Week Budget — YYYY-WXX
**Weekly target:** $350.00

| Category | Estimated | Status |
|----------|-----------|--------|
| Dinner   | $XXX.XX   | approved |
| Lunch    | $XX.XX    | [status from existing file or —] |
| Baking   | $XX.XX    | [status from existing file or —] |
| **Total** | **$XXX.XX** | |
| **Remaining** | **$XXX.XX** | |
```

Append to `~/Documents/kitchen/ledger.md` only when all three categories are filled in for the week. Otherwise leave it — lunch or baking may not be planned yet.

### Step 11 — Create iCal events

For each dinner, create a calendar event in the "Dinner" calendar:
```bash
osascript -e '
tell application "Calendar"
  tell calendar "Dinner"
    make new event with properties {summary:"[Meal Name]", start date:date "[Weekday Mon D, YYYY] at 6:00 PM", end date:date "[Weekday Mon D, YYYY] at 7:00 PM", description:"Est. cost: $XX.XX | Time: XX min"}
  end tell
end tell'
```
- If Calendar errors, report it but do not fail — files are already written

### Step 12 — Confirm

Tell the user all files are written, where they are, and any savings highlights for the week.

---

## Handling Swaps

If the user wants to swap a meal (at Step 6 or any time after):

1. Pick a replacement — must not repeat last 3 weeks, fit budget, respect variety rules
2. If files already written: rewrite that dinner file, update meal-plan.md, regenerate shopping-list.md and instacart-paste.md
3. Tell the user the new meal, cost difference, and confirm files are updated

## Planning Rules

- **Never repeat** a meal made in the last 3 weeks
- **Stay under** remaining weekly budget
- **Sales are a bonus, not the criteria** — pick great recipes first, prefer sale proteins when quality is equal
- **Variety** — mix proteins and cuisines across the week
- **Realistic** — weeknight meals 30-45 min; Sunday up to 90 min ok
- **Family of 7** — scale all recipe quantities accordingly
