---
name: dessert-planner
description: >
  This skill should be used when the user asks about "baking", "dessert", "what should I bake",
  "I want to make something sweet", "I'm in a pie mood", "cake ideas", "cookies", "Amanda bake",
  or any mention of baking or sweet recipes.
  It guides Amanda through a fully menu-driven selection flow — no typing required at any step.
  Write the full recipe to ~/Documents/kitchen/YYYY-WXX/dessert/.
version: 0.1.0
---

# Dessert Planner

Fully menu-driven baking recipe discovery for Amanda.
**Every step presents numbered options — she never needs to type free text.**

---

## Interaction Flow

### Step 1 — Welcome Amanda + mood menu

Always open by addressing Amanda by name with warmth, then deliver Justin's message, then go straight into the menu. Keep it light and fun.

**Present all menus as a plain bullet list — NO numbers. This triggers clickable button rendering in Claude desktop.**

```
Hi Amanda! 🎂 Let's find you something amazing to bake.

By the way, Justin says Love you Babe 🥰

What are you in the mood to bake?

- 🥧 Pie or tart
- 🎂 Cake or cupcakes
- 🍪 Cookies or bars
- 🍮 Something creamy (cheesecake, pudding, mousse, custard)
- 🍩 Fried or yeasted (donuts, babka, cinnamon rolls)
- 🎲 Surprise me!
```

### Step 2 — Refine menu

After mood, offer a quick second filter — max 4 options.

**Pie:**
```
- 🍫 Chocolate
- 🍎 Fruit-based
- 🥜 Nut or custard
- ✨ Any — surprise me
```

**Cake:**
```
- 🍫 Chocolate
- 🍋 Citrus or fruity
- 🍦 Vanilla / classic
- ✨ Any — surprise me
```

**Cookies:**
```
- 🍫 Chocolate chip or brownie
- 🧁 Soft and chewy
- 🫙 Crispy or shortbread
- ✨ Any — surprise me
```

**All other categories:**
```
- ⚡ Quick (under 1 hour)
- 🕐 Takes time (1+ hour)
- ✨ Don't care — surprise me
```

### Step 3 — Query recipes-db

Use the actual category values from the DB based on her menu selection:

| Menu choice | DB category filter |
|---|---|
| Pie or tart | `value IN ('Pie', 'Pies')` |
| Cake or cupcakes | `value IN ('Cake', 'Cakes', 'Layer Cakes', 'Cupcake')` |
| Cookies or bars | `value IN ('Cookies', 'Cookie', 'Oatmeal Cookie', 'Shortbread Cookies')` |
| Something creamy | `value IN ('Cheesecakes', 'Puddings and Custards', 'Ice Cream', 'Bread Pudding')` |
| Fried or yeasted | `value IN ('Bread', 'Pastry', 'Pancake')` |
| Surprise me | `value IN ('Dessert', 'Desserts or Baked Goods')` |

```sql
SELECT r.id, r.name, r.total_mins, r.yield_servings, r.rating, r.rating_count,
       GROUP_CONCAT(CASE WHEN t.type='category' THEN t.value END) as categories
FROM recipes r
LEFT JOIN tags t ON t.recipe_id = r.id
WHERE r.rating >= 4.3
  AND r.rating_count >= 20
  AND r.total_mins IS NOT NULL
  AND r.id IN (
    SELECT recipe_id FROM tags
    WHERE type = 'category' AND value IN ([mapped values from table above])
  )
GROUP BY r.id
ORDER BY RANDOM()
LIMIT 50
```

Filter down to exactly **4 options** — vary time, style, difficulty.

### Step 4 — Recipe menu

```
Here are 4 great [pies]:

- 🥧 Brown Butter Pecan Pie — 75 min | 4.9★ | rich & nutty
- 🍫 Chocolate Silk Pie — 45 min | 4.8★ | silky, no-bake filling
- 🍓 Strawberry Rhubarb Pie — 90 min | 4.7★ | tart and sweet
- 🍎 Apple Galette — 60 min | 4.8★ | rustic, easy
- 🔄 Show me different options
```

Option 5 always re-rolls the list from the DB.

### Step 5 — Servings menu

```
How many people are you baking for?

- 👨‍👩‍👧 Just us (4–5)
- 👨‍👩‍👧‍👦 Family of 7
- 🎉 Guests (10–12)
- 🍰 Big batch (15+)
```

### Step 6 — Fetch full recipe

```sql
SELECT text FROM ingredients WHERE recipe_id = ? ORDER BY position;
SELECT text FROM steps WHERE recipe_id = ? ORDER BY position;
```

Scale all quantities to the selected serving size.

### Step 6b — Check budget before confirming

Read `~/Documents/kitchen/YYYY-WXX/budget.md` — show Amanda what's left in this week's pool before committing.
Price the baking ingredients against `schnucks-db` to get an estimated cost.

### Step 7 — Confirm before writing

```
Ready to save?

  Brown Butter Pecan Pie — serves 7 — 75 min — est. $XX.XX
  Week budget remaining: $XXX.XX

- ✅ Yes, save it!
- 🔄 Pick a different recipe
```

### Step 8 — Write recipe file

Write to `~/Documents/kitchen/YYYY-WXX/dessert/YYYY-MM-DD-recipe-name.md`:

```markdown
# [Recipe Name]
**Baked:** [Date] | **Serves:** X | **Time:** XX min | **Rating:** X.X★

## Ingredients
- X cups flour
- ...

## Steps
1. ...

## Notes
Tips, substitutions, make-ahead instructions.
```

### Step 9 — Shopping decision menu

```
Do you need to pick up ingredients, Amanda?

- 🏠 I have everything at home
- 🛒 Add to this week's Instacart order
- 🚗 Separate quick run
```

**Option 1 — Have everything:**
- Skip shopping list entirely
- Just write the recipe file
- Do not touch budget.md or instacart-paste.md

**Option 2 — Add to weekly Instacart order:**
- Write `~/Documents/kitchen/YYYY-WXX/dessert/YYYY-MM-DD-recipe-name-shopping-list.md`
- Append baking items to `~/Documents/kitchen/YYYY-WXX/instacart-paste.md` under `## BAKING ITEMS`
- Update `~/Documents/kitchen/YYYY-WXX/budget.md` with baking total
- Check if all three categories filled — if so, append week to `~/Documents/kitchen/ledger.md`

**Option 3 — Separate quick run:**
- Write `~/Documents/kitchen/YYYY-WXX/dessert/YYYY-MM-DD-quick-run.md` (standalone list, not part of Instacart order)
- Do NOT append to instacart-paste.md or update budget.md
- Format as a simple grab-and-go list for the store

```markdown
# Baking List — [Recipe Name] — [Date]

## Ingredients to Buy
- X cups all-purpose flour — ~$X.XX
- ...

## Probably Already in Pantry
- baking soda, salt, vanilla extract, butter, sugar, eggs
```

Query `schnucks-db` to price what you can. Flag pantry staples separately.

### Step 10 — Done menu

```
All saved! ✅

  Brown Butter Pecan Pie — 7 servings — 75 min
  ~/Documents/kitchen/YYYY-WXX/dessert/

- 🛒 View shopping list
- 🎂 Find another recipe
- ✅ Done
```

---

## Rules

- **Every step is a numbered menu** — no free text entry, no typing numbers unprompted
- **Max 5 options per menu** — always include a re-roll or "any" escape hatch
- **Always separate baking shopping list** — never touch dinner lists
- **Re-roll always available** — option 5 on recipe menu re-queries the DB fresh
