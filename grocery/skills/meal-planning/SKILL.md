---
name: meal-planning
description: >
  This skill should be used when the user asks to "plan meals", "plan this week",
  "what should we eat", "what's for dinner", "make a meal plan", or "plan the week's dinners".
  It generates a 7-dinner weekly plan for a family of 7, priced against live Schnucks data,
  with full recipes written to ~/Documents/kitchen/dinner/YYYY-WXX/.
version: 0.1.0
---

# Meal Planning

Plan 7 dinners for a family of 7, within budget, avoiding recent repeats, with full printable recipes.

## Workflow

### Step 1 — Load household config
Read `${CLAUDE_PLUGIN_ROOT}/context/household.md`
- Family size, dietary restrictions, monthly budget, dinners folder path, DB paths

### Step 2 — Check Schnucks DB freshness
Query `SELECT MAX(updated_at) FROM items` via `schnucks-db` MCP:
- Today is **Sunday** → always refresh: run `${CLAUDE_PLUGIN_ROOT}/scripts/harvester full`
- Last update **older than 7 days** → refresh: run `${CLAUDE_PLUGIN_ROOT}/scripts/harvester full`
- Otherwise → skip. Tell the user: "Schnucks DB last updated X days ago, skipping refresh."

### Step 3 — Check recent meal history
Scan `~/Documents/kitchen/dinner/` for the last 4 week folders (YYYY-WXX), read each `meal-plan.md`:
- Extract: meals already made (to avoid repeats), money spent per week
- Calculate: total spent this month so far, remaining weekly budget

### Step 4 — Find recipe candidates from recipes.db
Query `recipes-db` MCP to find 20-30 candidates:
```sql
SELECT r.id, r.name, r.total_mins, r.yield_servings, r.calories, r.rating, r.rating_count,
       GROUP_CONCAT(CASE WHEN t.type='category' THEN t.value END) as categories,
       GROUP_CONCAT(CASE WHEN t.type='cuisine' THEN t.value END) as cuisines
FROM recipes r
LEFT JOIN tags t ON t.recipe_id = r.id
WHERE r.rating >= 4.0
  AND r.rating_count >= 25
  AND r.total_mins <= 60
  AND r.total_mins IS NOT NULL
GROUP BY r.id
ORDER BY r.rating DESC, r.rating_count DESC
LIMIT 200
```
- Filter out any meals made in the last 3 weeks
- Pick 20-30 diverse candidates covering Dinner, mixing proteins and cuisines
- For Sunday, allow total_mins up to 90 (bigger meal ok)

### Step 5 — Fetch full recipe details
For each of the 7 chosen recipes, query:
```sql
SELECT text FROM ingredients WHERE recipe_id = ? ORDER BY position;
SELECT text FROM steps WHERE recipe_id = ? ORDER BY position;
```

### Step 6 — Price ingredients against Schnucks
For each recipe's ingredient list, query `schnucks-db` MCP:
- Match ingredient name against `items.name` — use the sale_price if available, otherwise regular_price
- Flag any ingredients with active Ibotta coupons as savings opportunities

**Pricing rules — items are priced differently based on how Schnucks sells them:**

1. **Fresh meat (per-lb price)** — items in `aisle = 'MEAT F'` with NO size in parentheses in the name
   - e.g. `Schnucks - Fresh Natural Boneless Skinless Chicken Thighs` at $4.79
   - Price IS per lb → multiply by lbs needed after scaling to 7 servings
   - Example: recipe needs 1.5 lbs for 4 servings → scale to 7 → 2.625 lbs → $4.79 × 2.625 = $12.57

2. **Packaged meat/frozen** — items with `(X Oz)` or `(X Lb)` in name
   - e.g. `Schnucks - Frozen Bagged Boneless Skinless Chicken Breast (48 Oz)` at $10.99
   - Price is per package → calculate lbs needed (scaled to 7), divide by package size, round up to whole packages
   - Example: need 3 lbs → 48 Oz = 3 lbs → 1 package → $10.99

3. **Produce — per-unit items** — peppers, cucumbers, limes, onions, garlic, etc. (sold individually)
   - Price is per each → estimate count needed scaled to 7 servings
   - Example: recipe calls for 2 bell peppers for 4 → scale to 7 → ~4 peppers → $0.99 × 4 = $3.96

4. **Produce — per-lb items** — bananas, loose carrots, potatoes, etc. (no unit count in recipe)
   - Price is per lb → multiply by lbs needed scaled to 7 servings

5. **Pantry/packaged goods** — canned goods, pasta, spices, sauces
   - Price is per package/can/bottle → estimate how many packages needed for scaled recipe

**When in doubt:** if the ingredient text has an explicit weight (lbs/oz), use weight-based math. If it has a count (2 peppers, 3 cloves), use count-based math scaled to 7.

### Step 7 — Select final 7 meals
Pick the best 7 from candidates that:
- Stay within remaining weekly budget combined
- Mix proteins across the week (no more than 2 chicken, 1 beef, 1 pork, etc.)
- Include at least 1 vegetarian meal
- Include breakfast-for-dinner or a lighter meal mid-week if budget is tight

## Planning Rules

- **Never repeat** a meal made in the last 3 weeks
- **Stay under** remaining weekly budget (monthly budget minus weeks already spent)
- **Variety** — mix proteins and cuisines across the week
- **Realistic** — weeknight meals 30-45 min; one bigger Sunday meal ok (up to 90 min)
- **Family of 7** — scale all recipe quantities accordingly

## Output — What to Write

Create the week folder: `~/Documents/kitchen/dinner/YYYY-WXX/` (use current ISO week number)

Write these files:

### meal-plan.md (summary — this is what future weeks will read back)

```markdown
# Week XX — Mon MMM D - Sun MMM D, YYYY
**Subtotal:** $XXX.XX | **Tax (8.35%):** $XX.XX | **Total:** $XXX.XX
**Meals:** meal one, meal two, meal three, meal four, meal five, meal six, meal seven
**Notes:** any relevant notes (e.g. had extra budget, skipped Sunday)
```

### shopping-list.md (consolidated ingredients)

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

## Dairy
...

## Pantry & Canned
...

## Pantry Staples (if needed)
...

## Savings This Week
- item on sale — save $X.XX
```

### One file per dinner: `monday-meal-name.md`, `tuesday-meal-name.md`, etc.

```markdown
# [Meal Name] — [Day] [Date]
**Serves:** 7 | **Est. Cost:** $XX.XX | **Time:** XX min

## Ingredients
- X lbs item — $X.XX (Schnucks[, on sale])
- ...

## Steps
1. Step one
2. Step two
3. ...

## Notes
Any tips, substitutions, or make-ahead instructions.
```

### Step 9 — Add dinners to shared iCloud calendar

After all files are written, create calendar events for each dinner using osascript.
Use the shared family calendar named "Family" (or the first shared calendar found if "Family" doesn't exist).

For each of the 7 dinners, run:
```bash
osascript -e '
tell application "Calendar"
  tell calendar "Family"
    make new event with properties {
      summary: "[Meal Name]",
      start date: date "[Weekday Mon D, YYYY] at 6:00 PM",
      end date: date "[Weekday Mon D, YYYY] at 7:00 PM",
      description: "Est. cost: $XX.XX | Time: XX min"
    }
  end tell
end tell'
```

- Set time to 6:00 PM – 7:00 PM each night
- Title = meal name only (short, readable on phone calendar)
- Description = estimated cost + cook time
- If Calendar returns an error, report it but do not fail — files are already written

### Step 8 — Generate instacart-paste.md

After all dinner files and shopping-list.md are written, run the cart-builder workflow:
- Consolidate all ingredients across all 7 recipes into a single clean list
- Write `~/Documents/kitchen/dinner/YYYY-WXX/instacart-paste.md` (item + quantity only, no prices)
- This is ready to copy/paste into ChatGPT to build the Instacart cart

## Handling Swaps

If the user says anything like "swap that out", "replace Tuesday's dinner", "I don't like that one", or names a specific meal to change:

1. **Pick a replacement** from the already-queried candidate list (or re-query if needed)
   - Must not repeat anything from the last 3 weeks
   - Must fit within remaining budget after removing the swapped meal's cost
   - Respect protein variety rules (don't create a 3rd chicken if swapping to chicken)

2. **Rewrite the dinner file** — delete the old day's file, write the new one with full ingredients + steps

3. **Update `meal-plan.md`** — replace the swapped meal name, adjust subtotal/tax/total if cost changed

4. **Regenerate `shopping-list.md`** — remove ingredients only used in the old meal, add new ones, re-tally totals

5. **Regenerate `instacart-paste.md`** — full fresh rebuild from the updated recipe set

Tell the user the new meal, estimated cost difference, and confirm all files are updated.

## After Writing

Tell the user:
- The week's 7 meals with estimated cost each
- Total weekly spend vs budget remaining
- Any meals that are especially cheap or use good coupon deals this week
- Confirm all files are written and where to find them
