---
name: dessert-planner
description: >
  This skill should be used when the user asks about "baking", "dessert", "what should I bake",
  "I want to make something sweet", "I'm in a pie mood", "cake ideas", "cookies", "Amanda bake",
  or any mention of baking or sweet recipes.
  It guides Amanda through a fully menu-driven selection flow — no typing required at any step.
  Write the full recipe to ~/Documents/kitchen/dessert/.
version: 0.1.0
---

# Dessert Planner

Fully menu-driven baking recipe discovery for Amanda.
**Every step presents numbered options — she never needs to type free text.**

---

## Interaction Flow

### Step 1 — Mood menu

```
What are you in the mood to bake?

  1. 🥧 Pie or tart
  2. 🎂 Cake or cupcakes
  3. 🍪 Cookies or bars
  4. 🍮 Something creamy (cheesecake, pudding, mousse, custard)
  5. 🍩 Fried or yeasted (donuts, babka, cinnamon rolls)
  6. 🎲 Surprise me
```

### Step 2 — Refine menu

After mood, offer a quick second filter — max 4 options.

**Pie:**
```
  1. 🍫 Chocolate
  2. 🍎 Fruit-based
  3. 🥜 Nut or custard
  4. ✨ Any — surprise me
```

**Cake:**
```
  1. 🍫 Chocolate
  2. 🍋 Citrus or fruity
  3. 🍦 Vanilla / classic
  4. ✨ Any — surprise me
```

**Cookies:**
```
  1. 🍫 Chocolate chip or brownie
  2. 🧁 Soft and chewy
  3. 🫙 Crispy or shortbread
  4. ✨ Any — surprise me
```

**All other categories:**
```
  1. ⚡ Quick (under 1 hour)
  2. 🕐 Takes time (1+ hour)
  3. ✨ Don't care — surprise me
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

  1. Brown Butter Pecan Pie         75 min  |  4.9★  |  rich & nutty
  2. Chocolate Silk Pie             45 min  |  4.8★  |  silky, no-bake filling
  3. Strawberry Rhubarb Pie         90 min  |  4.7★  |  tart and sweet
  4. Apple Galette                  60 min  |  4.8★  |  rustic, easy

  5. 🔄 Show me different options
```

Option 5 always re-rolls the list from the DB.

### Step 5 — Servings menu

```
How many people are you baking for?

  1. Just us (4–5)
  2. Family of 7
  3. Guests (10–12)
  4. Big batch (15+)
```

### Step 6 — Fetch full recipe

```sql
SELECT text FROM ingredients WHERE recipe_id = ? ORDER BY position;
SELECT text FROM steps WHERE recipe_id = ? ORDER BY position;
```

Scale all quantities to the selected serving size.

### Step 7 — Confirm before writing

```
Ready to save?

  Brown Butter Pecan Pie — serves 7 — 75 min

  1. ✅ Yes, save recipe + shopping list
  2. 🔄 Pick a different recipe instead
```

### Step 8 — Write recipe file

Write to `~/Documents/kitchen/dessert/YYYY-MM-DD-recipe-name.md`:

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

### Step 9 — Write baking shopping list

Always write separately to `~/Documents/kitchen/dessert/YYYY-MM-DD-recipe-name-shopping-list.md`.
Never touch dinner shopping lists or instacart-paste.

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
  ~/Documents/kitchen/dessert/

  1. 🛒 View shopping list
  2. 🎂 Find another recipe
  3. ✅ Done
```

---

## Rules

- **Every step is a numbered menu** — no free text entry, no typing numbers unprompted
- **Max 5 options per menu** — always include a re-roll or "any" escape hatch
- **Always separate baking shopping list** — never touch dinner lists
- **Re-roll always available** — option 5 on recipe menu re-queries the DB fresh
