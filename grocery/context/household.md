# Household Config

## Family
- **Size:** 7 people
- **Dietary restrictions:** none
- **School lunch rule:** NO peanut butter — girls are not allowed to bring it to school

## Budget
- **Monthly food budget:** $1,400
- **Weekly target:** ~$350 (monthly ÷ 4 weeks)
- **Sales tax:** 8.35% — always add to subtotal for true weekly cost
- **Target:** 7 dinners per week, stay within weekly budget

## Paths
- **Kitchen folder:** ~/Documents/kitchen
- **Week folders:** ~/Documents/kitchen/YYYY-WXX/ (week is top-level organizer)
  - dinner/ — 7 dinner recipe files + meal-plan.md + shopping-list.md
  - lunch/ — 5 lunch files + lunch-plan.md + shopping-list.md
  - dessert/ — baking recipes + shopping lists
  - budget.md — shared weekly budget across all three categories
  - instacart-paste.md — combined master paste for the whole week
- **Ledger:** ~/Documents/kitchen/ledger.md (permanent running record, never delete)
- **Schnucks DB:** /Users/jnuts74/Documents/kitchen/schnucks.db (writable copy — plugin cache is read-only)
- **Recipes DB:** /Users/jnuts74/Documents/kitchen/recipes.db (writable copy)
- **Harvester:** python3 ${CLAUDE_PLUGIN_ROOT}/scripts/harvester.py (stdlib only, no dependencies)

## Budget Tracking
- Weekly budget is a **shared pool** across dinner + lunch + baking — $350/week total
- Each planner reads `budget.md` at start to see what's left before proposing a plan
- Each planner writes its approved total back to `budget.md` after approval
- After all shopping is done, the week's totals get appended to `ledger.md`
- `ledger.md` tracks week-over-week and month-over-month spend — never delete it

## Schnucks DB Schema (quick reference)
- `items` — upc_id, name, brand_name, regular_price, sale_price, full_upc, aisle
- `coupons` — id, source, value_text, expiration_date, description
- `item_coupons` — upc_id, coupon_id (junction table)
- `categories` — id, name, parent_id, is_leaf
- Active Ibotta coupons: WHERE source = 'IBOTTA' AND expiration_date > strftime('%s','now') * 1000

## Recipes DB Schema (quick reference)
- `recipes` — id, name, description, image_url, yield_servings, total_mins, prep_mins, cook_mins, calories, protein_g, fat_g, carbs_g, rating, rating_count, source_site, source_url
- `ingredients` — id, recipe_id, position, text
- `steps` — id, recipe_id, position, text
- `tags` — id, recipe_id, type ('category'|'cuisine'|'keyword'), value
- `recipes_fts` — FTS5 virtual table: search with `recipes_fts MATCH 'chicken'`
- 31,814 recipes from AllRecipes, Serious Eats, Simply Recipes, America's Test Kitchen

## Notes
- Refresh Schnucks DB before planning: SCHNUCKS_DB_PATH=/Users/jnuts74/Documents/kitchen/schnucks.db python3 ${CLAUDE_PLUGIN_ROOT}/scripts/harvester.py full
- Both DBs are exposed via MCP — query directly, no need to shell out for reads
