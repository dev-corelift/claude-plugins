# Household Config

## Family
- **Size:** 7 people
- **Dietary restrictions:** none

## Budget
- **Monthly food budget:** $1,400
- **Weekly target:** ~$350 (monthly ÷ 4 weeks)
- **Sales tax:** 8.35% — always add to subtotal for true weekly cost
- **Target:** 7 dinners per week, stay within weekly budget

## Paths
- **Kitchen folder:** ~/Documents/kitchen
- **Dinners folder:** ~/Documents/kitchen/dinner
- **Schnucks DB:** ${CLAUDE_PLUGIN_ROOT}/data/schnucks.db
- **Recipes DB:** ${CLAUDE_PLUGIN_ROOT}/data/recipes.db
- **Harvester:** ${CLAUDE_PLUGIN_ROOT}/scripts/harvester (Go binary, no dependencies)

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
- Refresh Schnucks DB before planning: ${CLAUDE_PLUGIN_ROOT}/scripts/harvester full
- Both DBs are exposed via MCP — query directly, no need to shell out for reads
