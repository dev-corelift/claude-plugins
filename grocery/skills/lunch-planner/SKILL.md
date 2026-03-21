---
name: lunch-planner
description: >
  This skill should be used when the user asks about "school lunches", "pack lunches",
  "girls lunches", "what should I pack", "lunch ideas for the week", or "plan lunches".
  It plans 5 school day lunches for the girls, kid-friendly, quick to pack, NO peanut butter.
  Writes files to ~/Documents/kitchen/YYYY-WXX/lunch/.
version: 0.1.0
---

# Lunch Planner

Plan 5 school day lunches for the girls — kid-friendly, quick to pack, no peanut butter.

**Two phases — present and approve before writing anything.**

---

## PHASE 1 — Discovery

### Step 1 — Load household config
Read `${CLAUDE_PLUGIN_ROOT}/context/household.md`
- Confirm: NO peanut butter — girls cannot bring it to school

### Step 1b — Read budget
- Read `~/Documents/kitchen/YYYY-WXX/budget.md` if it exists
- Check what dinner and baking have already claimed this week
- Remaining lunch budget = $350 minus dinner and baking spend
- Tell the user what the lunch budget is before suggesting anything

### Step 2 — Check recent lunch history
Scan `~/Documents/kitchen/` for the last 4 week folders, read each `YYYY-WXX/lunch/lunch-plan.md`:
- Extract what was packed recently to avoid repeating the same thing too often
- Kids get bored fast — don't repeat anything from the last 2 weeks

### Step 3 — Query recipes-db for lunch candidates

Run separate queries per lunch type to ensure variety across the week:

**Lunch categories in DB:** `Lunch`, `Sandwich`, `Salad`, `Snack`

```sql
SELECT r.id, r.name, r.total_mins, r.yield_servings, r.rating, r.rating_count
FROM recipes r
WHERE r.rating >= 4.0
  AND r.rating_count >= 10
  AND (r.total_mins <= 20 OR r.total_mins IS NULL)
  AND r.id IN (
    SELECT recipe_id FROM tags
    WHERE type = 'category' AND value IN ('Lunch', 'Sandwich', 'Salad', 'Sandwiches')
  )
  AND r.id NOT IN (
    SELECT recipe_id FROM ingredients
    WHERE LOWER(text) LIKE '%peanut butter%' OR LOWER(text) LIKE '%peanut%'
  )
ORDER BY RANDOM()
LIMIT 20
```

**Hard rules:**
- NO peanut butter or peanut ingredients — ever
- Nothing that requires reheating at school
- Simple enough for a kid to eat with a fork or hands
- Prep time ideally under 15 minutes

### Step 4 — Build 5-day lunch plan

Mix across the week — no two identical mains:
- 1–2 sandwich/wrap days
- 1–2 salad or grain bowl days  
- 1 fun/theme day (pinwheels, DIY lunchable-style, mini sliders, etc.)

Each lunch should include:
- **Main** — recipe from DB
- **Side** — fruit, veggie, crackers (simple, no recipe needed)
- **Snack** — something from the pantry/produce

### Step 5 — Present plan for approval

```
Here's this week's lunch plan for the girls:

Mon — Turkey & Cheese Pinwheels + apple slices + goldfish crackers
Tue — Greek Pasta Salad + grapes + baby carrots
Wed — Ham & Cheese Sandwich + orange + pretzels
Thu — Chicken Caesar Wrap + strawberries + string cheese
Fri — DIY Lunchable (deli meat, cheese cubes, crackers) + fruit cup

Est. grocery additions: ~$XX.XX

Approve or swap any day?
```

Handle swaps conversationally. Once approved, move to Phase 2.

---

## PHASE 2 — Commit (only after approval)

### Step 6 — Write lunch-plan.md

Write to `~/Documents/kitchen/YYYY-WXX/lunch/lunch-plan.md`:

```markdown
# School Lunches — Week XX (Mon MMM D – Fri MMM D)

| Day | Main | Side | Snack |
|-----|------|------|-------|
| Monday | Turkey & Cheese Pinwheels | Apple slices | Goldfish crackers |
| Tuesday | Greek Pasta Salad | Grapes | Baby carrots |
| Wednesday | Ham & Cheese Sandwich | Orange | Pretzels |
| Thursday | Chicken Caesar Wrap | Strawberries | String cheese |
| Friday | DIY Lunchable | Fruit cup | — |
```

### Step 7 — Write lunch shopping list

Write to `~/Documents/kitchen/YYYY-WXX/lunch/shopping-list.md`.
Only include what needs to be bought — flag common fridge staples (deli meat, cheese, bread) separately.

```markdown
# Lunch Shopping — Week XX

## Buy This Week
- item — qty | UPC: XXXX | ~$X.XX
- ...

## Check Fridge/Pantry First
- bread, deli turkey, sliced cheese, mayo
- ...

**Lunch est. total: ~$XX.XX**
```

### Step 8 — Update budget.md and create Instacart list

Update `~/Documents/kitchen/YYYY-WXX/budget.md` with lunch total.

Create the Instacart link using the `mcp__Control_your_Mac__osascript` tool (runs on host Mac, bypasses sandbox network):

Call `mcp__Control_your_Mac__osascript` with a single `script` parameter:
```applescript
do shell script "echo '<JSON_PAYLOAD>' > /tmp/ic-payload.json && python3 '/Users/jnuts74/projects/tools/cowork-plugins/grocery/scripts/instacart-bridge.py' shopping-list /tmp/ic-payload.json 2>&1"
```
- Replace `<JSON_PAYLOAD>` with JSON containing `title`, `expires_in`, and `line_items`
- Escape single quotes in the JSON as `'\\''`
- The bridge returns a single Instacart URL — include it in the confirmation message
- **Grocery quantities, not recipe quantities:** send items as they are purchased (1 package deli turkey, 1 loaf bread, 1 bag grapes — never "4 slices turkey" or "0.5 cup grapes"). Meat/produce sold by weight keep their weight. Packaged goods = qty 1 each.

Check if all three categories (dinner, lunch, baking) are now filled in budget.md — if so, append the week to `~/Documents/kitchen/ledger.md`.

### Step 9 — Confirm

Tell the user all files are written to `~/Documents/kitchen/YYYY-WXX/lunch/` and share the Instacart link to add items to their cart.

---

## Rules

- **Never suggest peanut butter** in any form — it's a school rule
- **Keep mains simple** — these are packed the night before or morning of
- **No hot food** — nothing that requires a microwave at school
- **Kid-approved flavors** — nothing too spicy, unfamiliar, or exotic
- **Variety across the week** — no two identical mains Mon–Fri
