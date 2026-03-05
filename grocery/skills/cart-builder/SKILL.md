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

Turn this week's meal plan into a consolidated shopping list mapped to real Schnucks products.

## Steps

1. **Find current week folder** — look in `~/dinners/` for the current ISO week (YYYY-WXX)
   - If not found, tell the user to run meal planning first

2. **Read all recipe files** — read every `*.md` file in the week folder except `meal-plan.md` and `shopping-list.md`
   - Extract ingredients + quantities from each recipe

3. **Consolidate** — merge duplicate ingredients across all recipes
   - e.g. if 3 recipes use garlic, combine into one line item with total quantity

4. **Map to Schnucks DB** — for each ingredient, query the Schnucks SQLite DB
   - Match by name/brand, get UPC, current price, sale status
   - Flag any items not found in DB (may need manual add)

5. **Price the cart** — sum all items, compare to weekly budget

6. **Output**

   If Instacart MCP is connected:
   - Push cart items to Instacart using full_upc for exact product matching
   - Report what was added, what needs manual search

   If Instacart MCP is NOT connected:
   - Write/update `~/dinners/YYYY-WXX/shopping-list.md` with consolidated list
   - Format for easy manual Instacart entry or in-store shopping

## Shopping List Format

```markdown
# Shopping List — Week XX
**Cart total:** $XXX.XX | **Budget:** $XXX.XX remaining

## Meat & Seafood
- [ ] Chicken thighs, 4 lbs — $X.XX — UPC: XXXXXXXXXXXXXX
- [ ] Ground beef 80/20, 3 lbs — $X.XX — UPC: XXXXXXXXXXXXXX

## Produce
- [ ] Garlic, 2 heads — $X.XX
...

## Not found in Schnucks DB (add manually)
- item
```
