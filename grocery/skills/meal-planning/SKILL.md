---
name: meal-planning
description: >
  This skill should be used when the user asks to "plan meals", "plan this week",
  "what should we eat", "what's for dinner", "make a meal plan", or "plan the week's dinners".
  It generates a 7-dinner weekly plan for a family of 7, priced against live Schnucks data,
  with full recipes written to ~/dinners/YYYY-WXX/.
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
Scan `~/dinners/` for the last 4 week folders (YYYY-WXX), read each `meal-plan.md`:
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
- Sum total cost per recipe, then scale to family of 7 (recipe yield_servings → 7)
- Flag any ingredients with active Ibotta coupons as savings opportunities

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

Create the week folder: `~/dinners/YYYY-WXX/` (use current ISO week number)

Write these files:

### meal-plan.md (summary — this is what future weeks will read back)

```markdown
# Week XX — Mon MMM D - Sun MMM D, YYYY
**Budget used:** $XXX.XX
**Meals:** meal one, meal two, meal three, meal four, meal five, meal six, meal seven
**Notes:** any relevant notes (e.g. had extra budget, skipped Sunday)
```

### shopping-list.md (consolidated ingredients)

```markdown
# Shopping List — Week XX

**Estimated total:** $XXX.XX

## Produce
- item, qty, ~$X.XX

## Meat & Seafood
- item, qty, ~$X.XX

## Dairy
...

## Pantry
...
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

## After Writing

Tell the user:
- The week's 7 meals with estimated cost each
- Total weekly spend vs budget remaining
- Any meals that are especially cheap or use good coupon deals this week
- Confirm all files are written and where to find them
