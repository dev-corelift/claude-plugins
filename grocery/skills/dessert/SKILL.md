---
name: dessert
description: >
  This skill should be used when the user asks about "baking", "dessert", "what should I bake",
  "I want to make something sweet", "I'm in a pie mood", "cake ideas", "cookies", "Amanda bake",
  or any mention of baking or sweet recipes.
  It guides Amanda through an interactive conversation to discover and select a dessert recipe
  from the recipes DB, then writes the full recipe to ~/Documents/kitchen/dessert/.
version: 0.1.0
---

# Dessert / Baking

Interactive recipe discovery for Amanda. Narrow down options through conversation until
she finds exactly what she wants to make, then write the full recipe.

## Interaction Flow

This skill is conversational — do NOT dump a wall of recipes upfront. Guide her step by step.

### Step 1 — Open with a mood check

Ask what she's feeling. Present as a short list to pick from:

```
What are you in the mood to bake?

  🥧 Pie or tart
  🎂 Cake or cupcakes
  🍪 Cookies or bars
  🍮 Something creamy (cheesecake, pudding, mousse, custard)
  🍩 Fried or yeasted (donuts, babka, cinnamon rolls)
  🎲 Surprise me

  Or just describe it — "something chocolatey", "easy and fast", "impressive for guests"
```

### Step 2 — Query recipes-db for candidates

Based on her answer, query `recipes-db` MCP:
```sql
SELECT r.id, r.name, r.total_mins, r.yield_servings, r.rating, r.rating_count, r.calories,
       GROUP_CONCAT(CASE WHEN t.type='category' THEN t.value END) as categories
FROM recipes r
LEFT JOIN tags t ON t.recipe_id = r.id
WHERE r.rating >= 4.3
  AND r.rating_count >= 20
  AND r.total_mins IS NOT NULL
  AND (t.type = 'category' AND t.value LIKE '%[mood keyword]%')
GROUP BY r.id
ORDER BY r.rating DESC, r.rating_count DESC
LIMIT 50
```

Filter to 4-6 diverse options — vary difficulty, time, and style within her chosen category.

### Step 3 — Present the shortlist

Show 4-6 options with just enough info to choose:

```
Here are some great [pies] to consider:

1. **Brown Butter Pecan Pie** — rich, nutty, classic  |  75 min  |  4.9★ (312 ratings)
2. **Chocolate Silk Pie** — silky smooth, no-bake filling  |  45 min + chill  |  4.8★ (445 ratings)
3. **Strawberry Rhubarb Pie** — tart and sweet, seasonal  |  90 min  |  4.7★ (189 ratings)
4. **Apple Galette** — rustic, free-form, forgiving  |  60 min  |  4.8★ (201 ratings)

Pick one, ask for something different, or tell me more:
"easier", "more chocolate", "something I can make ahead", "what goes with vanilla ice cream"
```

### Step 4 — Refine if needed

If she wants to narrow further, re-query with tighter filters and present a new shortlist.
Keep going until she says "that one" or picks a number.

### Step 5 — Fetch full recipe

```sql
SELECT text FROM ingredients WHERE recipe_id = ? ORDER BY position;
SELECT text FROM steps WHERE recipe_id = ? ORDER BY position;
```

### Step 6 — Ask about servings

"How many people are you baking for?" — default to 7 if she says family.
Scale ingredient quantities accordingly.

### Step 7 — Write the recipe file

Write to `~/Documents/kitchen/dessert/YYYY-MM-DD-recipe-name.md`

```markdown
# [Recipe Name]
**Baked:** [Date] | **Serves:** X | **Time:** XX min | **Rating:** X.X★

## Ingredients
- X cups flour
- ...

## Steps
1. ...
2. ...

## Notes
Any tips, substitutions, or make-ahead instructions from the recipe.
```

### Step 8 — Wrap up

Tell her:
- What you wrote and where it's saved
- Any tips from the recipe (make-ahead, storage, substitutions)
- "Want to add ingredients to this week's shopping list?" — if yes, append to `~/Documents/kitchen/dinner/YYYY-WXX/shopping-list.md` and `instacart-paste.md`

## Rules

- **Keep it short and fun** — this isn't a chore, she's choosing something to bake
- **Never show more than 6 options at once** — curate, don't overwhelm
- **Always ask about servings** — scaling matters for baking
- **Offer to add to shopping list** at the end — ingredients might not be in the pantry
