---
name: cart-builder
description: >
  This skill should be used when the user asks to "build my cart", "add to Instacart",
  "create shopping list", "ready to order", or "send to Instacart".
  It reads the current week's recipe files, consolidates all ingredients,
  maps them to Schnucks UPCs, and either outputs the list or pushes to Instacart.
version: 0.1.0
---

# Cart Builder

Turn this week's meal plan into a consolidated shopping list mapped to real Schnucks products,
and generate a clean paste-ready file for Instacart via ChatGPT.

## Steps

1. **Find current week folder** — look in `~/Documents/kitchen/dinner/` for the current ISO week (YYYY-WXX)
   - If not found, tell the user to run meal planning first

2. **Read all recipe files** — read every `*.md` file in the week folder except `meal-plan.md` and `shopping-list.md`
   - Extract ingredients + quantities from each recipe

3. **Consolidate** — merge duplicate ingredients across all recipes
   - e.g. if 3 recipes use garlic, combine into one line item with total quantity

4. **Map to Schnucks DB** — for each ingredient, query the Schnucks SQLite DB
   - Match by name/brand, get UPC, current price, sale status
   - Flag any items not found in DB (may need manual add)

5. **Price the cart** — sum all items, apply 8.35% tax, compare to weekly budget

6. **Write `shopping-list.md`** — full categorized list with prices (already written by meal-planning, update if re-running)

7. **Write `instacart-paste.md`** — clean item + quantity only, no prices, no categories, no noise
   - This is what you copy and paste into ChatGPT to use its Instacart connector
   - One item per line, quantity first

   If Instacart MCP is connected (future):
   - Push cart items directly using full_upc for exact product matching
   - Report what was added, what needs manual search

## instacart-paste.md Format

One item per line. Always include UPC when available, exact brand name, exact size.
This is pasted directly into ChatGPT's Instacart connector — precision prevents wrong items being added.

```markdown
# Instacart Cart — Week XX

## ADD TO CART

- Schnucks Fresh Natural Boneless Skinless Chicken Thighs — 4 lbs | UPC: 041331010254
- 80% Lean Ground Beef — 2 lbs | UPC: 041331020000
- Hunt's Diced Tomatoes 14.5 oz — 2 cans | UPC: 027000387627
- Kraft Shredded Mexican Cheese 8 oz — 1 bag | UPC: 021000015603
- Gala Apples — 6 loose | PLU: 4135 (loose from produce, NOT bagged)
- Baby Carrots 16 oz — 1 bag | search: "Grimmway Farms baby carrots 16 oz" (NOT snack combo pack)

---

## NOT IN DB — SEARCH MANUALLY

- Fresh cilantro bunch — search: "cilantro bunch"
- Specialty item — describe exactly what you need
```

**Rules for instacart-paste.md:**
- Always use `full_upc` from schnucks DB when available
- Always include exact brand name and package size
- For produce sold by PLU, include the PLU code and note loose vs bagged
- If no UPC, write a precise search phrase in quotes so ChatGPT knows exactly what to find
- Add a warning note for items where a wrong variant is easy to grab (snack pack vs full bag, light vs regular, etc.)
