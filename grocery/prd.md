# Product Requirements Document: Kitchen Planner Web App

**Version:** 1.0
**Date:** 2026-03-14
**Author:** Justin
**Status:** Draft

---

## 1. Executive Summary

Kitchen Planner is a web application for weekly meal planning, grocery budgeting, coupon optimization, and shopping list management for a family of 7. It replaces an existing CLI-based plugin system that currently runs inside Claude Code / Cowork. The webapp must preserve all existing workflows -- dinner planning, school lunch planning, baking/dessert discovery, and deal finding -- while making them accessible through a browser on both desktop and mobile.

The system integrates three data sources: a local grocery store product/coupon database (Schnucks), a recipe database (~37,000 recipes from 9 sources), and the Instacart Connect API for one-click shopping list creation. All planning operates within a shared weekly budget of $350 ($1,400/month), with spending tracked across categories in a persistent ledger.

---

## 2. Users

### 2.1 Justin (Primary)
- Manages the system, runs dinner planning and deal finding.
- Comfortable with technical interfaces.
- Needs full visibility into budget, spending history, data freshness, and system health.
- Uses desktop and mobile.

### 2.2 Amanda (Justin's Wife)
- Uses the baking/dessert planner and occasionally lunch planning.
- Not technical. Needs a simple, warm, guided interface.
- Strongly prefers menu-driven interactions -- selecting from numbered options rather than typing free text.
- Frequently uses her phone at the grocery store. Mobile experience is critical for her.
- Tone of all interactions directed at Amanda should be warm and personal, addressing her by name.

### 2.3 Future Users
- Older children may eventually have accounts to submit lunch preferences or rate meals.
- No requirements for this now, but the user model should not be hard-coded to two users.

---

## 3. Household Configuration

These values must be configurable by an admin user (Justin), not hard-coded.

| Parameter | Current Value |
|-----------|---------------|
| Family size | 7 |
| Monthly food budget | $1,400 |
| Weekly food budget | $350 |
| Sales tax rate | 8.35% |
| Dietary restrictions | None household-wide |
| School lunch restriction | NO peanut butter (school rule, absolute) |
| Grocery store | Schnucks (Store ID 144) |
| Week start day | Monday |

---

## 4. Core Workflows

### 4.1 Dinner Planner

**Purpose:** Plan 7 dinners for the week for a family of 7, priced against real grocery store data, with full recipes and a consolidated shopping list.

**Two-phase flow: Discovery (propose) then Commit (write). Nothing is persisted until the user explicitly approves both the meal selection and the shopping list.**

#### Phase 1 -- Discovery

**Step 1: Load context and budget**
- Read the current week's budget to determine what lunch and baking have already claimed.
- Read the permanent ledger to check month-to-date spend against the $1,400 monthly budget.
- Display to the user: weekly budget ($350), amounts already claimed by other categories, and the remaining dinner budget.

**Step 2: Check grocery store data freshness**
- Query the store database for the most recent item update timestamp.
- If today is Tuesday, always trigger a full data refresh (Schnucks resets sales weekly on Tuesday).
- If the last update is older than 7 days, trigger a full data refresh.
- Otherwise, skip the refresh and display the age of the data to the user.
- The refresh process is described in Section 7.1.

**Step 3: Check recent meal history**
- Scan the last 4 weeks of saved dinner plans.
- Extract: meal names (to avoid repeats), money spent per week (for trend visibility).
- No meal should repeat within the most recent 3 weeks.

**Step 4: Check sale items**
- Query the store database for items currently on sale, focusing on proteins (chicken, beef, pork, seafood).
- Sale items are a soft preference that gives a mild boost during recipe selection. They are not a hard requirement. Recipe quality and variety always come first.

**Step 5: Find recipe candidates**
- Execute 7 separate queries against the recipe database, one per protein/category target: chicken, beef, pork, seafood, pasta, vegetarian, soup/stew.
- Each query pulls a randomized pool of candidates (not sorted by rating -- that causes repetition).
- Quality floor: minimum 4.0 rating, minimum 15 ratings.
- Time constraint: weeknight meals 60 minutes or less; Sunday may be up to 90 minutes.
- From each pool, select the best fit considering: whether the protein is on sale, variety rules, and recent meal history.

**Variety rules across the 7 selected meals:**
- Maximum 2 chicken dishes.
- Maximum 1 beef, 1 pork, 1 seafood.
- At least 1 fully vegetarian meal.
- At least 2 different cuisine styles (Mexican, Asian, Italian, American, Mediterranean, etc.).
- No two dishes with the same primary cooking method (e.g., not two sheet pan meals).

**Step 6: Present proposed meals for approval**
- Display all 7 meals with: day, meal name, cook time, rating, estimated cost, and a flag if the primary protein is on sale.
- Display the estimated weekly total.
- The user may approve the plan as-is, or request swaps conversationally (e.g., "swap Thursday for something Mexican" or "replace the vegetarian one").
- Swaps must respect the same variety rules, budget, and 3-week non-repeat constraint.

**Step 7: Fetch full recipe details**
- For each approved meal, retrieve the complete ingredient list and step-by-step instructions from the recipe database.

**Step 8: Price ingredients against the store database**
- For each ingredient, match against the store product catalog. Use sale price if available, otherwise regular price.
- Flag any ingredients with active Ibotta coupons as potential savings.

**Pricing rules by category:**

| Category | Pricing Model | Example |
|----------|---------------|---------|
| Fresh meat (per-lb, no package size in name) | Price per lb, multiply by weight needed scaled to 7 servings | 1.5 lbs for 4 servings -> 2.625 lbs for 7 -> 2.625 x $4.79 |
| Packaged meat/frozen (has size in name like "48 Oz") | Price per package, calculate packages needed, round up | Need 3 lbs, package is 48 oz (3 lbs) -> 1 package |
| Produce sold by unit (peppers, onions, limes) | Price per each, scale count to 7 servings | |
| Produce sold by weight (potatoes, carrots, bananas) | Price per lb, multiply by weight needed scaled to 7 | |
| Pantry/packaged goods (canned, pasta, spices, sauces) | Price per package, estimate packages needed for scaled recipe | |

General rule: if the recipe specifies weight, use weight math. If the recipe specifies count, use count math. All quantities scaled to 7 servings.

**Step 9: Present shopping list for approval**
- Display consolidated shopping list grouped by store section (Meat & Seafood, Produce, Dairy, Pantry, etc.).
- Each line item: item name, quantity, price, whether it is on sale.
- Display: subtotal, tax (8.35%), total with tax, remaining budget after this purchase.
- List any available Ibotta savings separately.
- Wait for explicit user approval before proceeding.

#### Phase 2 -- Commit (after approval)

**Step 10: Persist all outputs**

The following must be saved:

- **Meal plan summary** -- week number, date range, all 7 meals with costs, subtotal/tax/total.
- **Shopping list** -- full itemized list with prices, grouped by section, with subtotal/tax/total and budget remaining.
- **Individual recipe files** -- one per dinner (7 total), each containing: meal name, day, date, serving count, estimated cost, cook time, full ingredient list with prices, step-by-step instructions, and any notes/tips/substitutions.

**Step 11: Create Instacart shopping list**
- Send the approved shopping list to the Instacart Connect API to generate a clickable URL.
- Quantities must be converted from recipe measurements to grocery purchase quantities (see Section 6.2 for conversion rules).
- Display the Instacart URL to the user for one-click cart population.

**Step 12: Update budget tracking**
- Record the dinner total in the current week's budget.
- If all three categories (dinner, lunch, baking) are now filled for the week, append the week's totals to the permanent ledger.

**Step 13: Create calendar events**
- For each dinner, create a calendar event: 6:00-7:00 PM on the appropriate day, in a "Dinner" calendar.
- Calendar integration failures should be reported but should not block the workflow -- all files are already saved.

**Step 14: Confirmation**
- Show the user: where files are saved, total cost, budget remaining, any savings highlights, and the Instacart link.

#### Handling Swaps (at any point after initial proposal)

- If the user wants to swap a meal, the replacement must: not repeat anything from the last 3 weeks, fit the budget, and respect variety rules.
- If the plan has already been committed, the swap must update: the individual recipe file, the meal plan summary, the shopping list, and the Instacart list.
- Show the user the cost difference from the swap.

---

### 4.2 Lunch Planner

**Purpose:** Plan 5 school-day lunches (Monday-Friday) for the girls. Quick to pack, kid-friendly, no reheating required.

**HARD RULE: No peanut butter in any form, ever. This is a school policy. The system must never suggest peanut butter, peanut-containing ingredients, or recipes that include peanuts. This filter must be applied at the query level, not just as a display warning.**

**Two-phase flow: Discovery then Commit, same approval gate as dinner.**

#### Phase 1 -- Discovery

**Step 1: Load context and budget**
- Read the current week's budget. Calculate remaining lunch budget after dinner and baking claims.
- Display the lunch budget to the user before suggesting anything.

**Step 2: Check recent lunch history**
- Scan the last 4 weeks of saved lunch plans.
- Do not repeat any specific lunch from the last 2 weeks (kids get bored faster than adults).

**Step 3: Query recipe candidates**
- Query the recipe database for lunch-appropriate recipes: categories Lunch, Sandwich, Salad, Snack.
- Quality floor: minimum 4.0 rating, minimum 10 ratings.
- Time constraint: total time 20 minutes or less (or null -- many lunch items do not have cook times).
- Exclude any recipe containing peanut butter or peanut ingredients at the query level.

**Step 4: Build 5-day plan**

Each lunch consists of three components:
- **Main** -- from the recipe database.
- **Side** -- fruit, veggie, or crackers (simple, no recipe needed).
- **Snack** -- pantry/produce item.

Weekly variety rules:
- 1-2 sandwich/wrap days.
- 1-2 salad or grain bowl days.
- 1 fun/theme day (pinwheels, DIY lunchable-style, mini sliders, etc.).
- No two identical mains across the week.

Additional constraints:
- Nothing that requires a microwave at school.
- Simple enough for a kid to eat with a fork or hands.
- Prep time ideally under 15 minutes.
- Kid-approved flavors -- nothing too spicy, unfamiliar, or exotic.

**Step 5: Present plan for approval**
- Display the 5-day plan in a table: day, main, side, snack.
- Display estimated grocery additions cost.
- User may approve or request swaps for specific days.

#### Phase 2 -- Commit

**Step 6: Save lunch plan** -- week number, date range, 5-day table with main/side/snack.

**Step 7: Save shopping list**
- Only include items that need to be purchased.
- Separately flag common fridge/pantry staples (bread, deli meat, cheese, mayo) as "check first" items.

**Step 8: Update budget and create Instacart list**
- Record lunch total in the week's budget.
- Create Instacart shopping list with grocery-appropriate quantities (1 package deli turkey, 1 loaf bread -- never "4 slices turkey").
- Check if all three categories are filled; if so, append to ledger.

**Step 9: Confirmation** -- display where files are saved and the Instacart link.

---

### 4.3 Dessert/Baking Planner (Amanda's)

**Purpose:** Guide Amanda through discovering and selecting a baking recipe. This is Amanda's personal workflow and must feel warm, personal, and effortless.

**Critical UX requirements:**
- Every single step presents a numbered menu. Amanda types a number to select. She never needs to type free text.
- Maximum 5 options per menu. Always include an escape hatch (re-roll, surprise me, go back).
- Always address Amanda by name.
- Warm, encouraging tone throughout.
- Always open the session with: "Justin says Love you Babe"
- On mobile, numbered menus must be tappable (large touch targets).

#### Interaction Flow

**Step 1: Welcome + Mood Menu**
- Greet Amanda by name.
- Deliver Justin's message.
- Present mood menu (6 options):
  1. Pie or tart
  2. Cake or cupcakes
  3. Cookies or bars
  4. Something creamy (cheesecake, pudding, mousse, custard)
  5. Fried or yeasted (donuts, babka, cinnamon rolls)
  6. Surprise me

**Step 2: Refine Menu**
- Based on mood selection, present a 3-4 option refinement menu.
- Examples:
  - Pie: Chocolate / Fruit-based / Nut or custard / Surprise me
  - Cake: Chocolate / Citrus or fruity / Vanilla classic / Surprise me
  - Cookies: Chocolate chip or brownie / Soft and chewy / Crispy or shortbread / Surprise me
  - Other categories: Quick (under 1 hour) / Takes time (1+ hour) / Surprise me

**Step 3: Query recipe database**
- Map the mood + refinement selections to the appropriate database category filters.
- Quality floor: minimum 4.3 rating, minimum 20 ratings.
- Pull a randomized pool, then filter to exactly 4 diverse options varying by time, style, and difficulty.

**Step 4: Recipe Selection Menu**
- Present 4 recipes with: name, total time, rating, brief description.
- Option 5 is always "Show me different options" (re-rolls from the database with a fresh random seed).

**Step 5: Servings Menu**
- 4 options: Just us (4-5) / Family of 7 / Guests (10-12) / Big batch (15+).

**Step 6: Full Recipe + Budget Check**
- Fetch the complete recipe (ingredients and steps) and scale all quantities to the selected serving size.
- Read the current week's budget to show Amanda what is left.
- Price the baking ingredients against the store database for an estimated cost.

**Step 7: Confirm Before Saving**
- Show: recipe name, serving count, total time, estimated cost, budget remaining.
- Two options: Save it / Pick a different recipe.

**Step 8: Save Recipe File**
- Save the full recipe with: name, date baked, serving count, time, rating, scaled ingredient list, step-by-step instructions, notes/tips.

**Step 9: Shopping Decision Menu**
- Three options, each with different behavior:

| Option | Behavior |
|--------|----------|
| "I have everything at home" | Save recipe file only. Do not touch budget or shopping lists. |
| "Add to this week's Instacart order" | Save recipe file + shopping list. Create Instacart link (grocery quantities, not recipe quantities). Update budget with baking total. Check if all three categories are filled; if so, append to ledger. |
| "Separate quick run" | Save recipe file + standalone shopping list (not linked to weekly Instacart order). Separate "buy" vs. "probably in pantry" sections with prices from store DB. Do not update budget. |

**Step 10: Done Menu**
- Show confirmation of what was saved and where.
- Three options: View shopping list / Find another recipe / Done.

---

### 4.4 Deal Finder

**Purpose:** Find the best coupon stacking opportunities using current Schnucks prices and Ibotta rebates, focused on household and personal care items.

#### Savings Layers

The system must understand and calculate three stackable savings layers:

1. **Schnucks sale price** -- the in-store promotional price (sale_price on the item).
2. **Ibotta rebate** -- cashback submitted through the Ibotta app after purchase. Linked to items via the item_coupons junction table.
3. **P&G threshold bonus** -- a Schnucks store coupon that gives a bonus when P&G brand spending hits a threshold:
   - Spend $40 on P&G products -> $10 bonus
   - Spend $60 on P&G products -> $20 bonus

**P&G brands to track:** Tide, Gain, Downy, Bounty, Charmin, Pampers, Gillette, Oral B, Olay, Secret, Old Spice, Crest, Swiffer, Febreze, Pantene, Head & Shoulders, Always, Tampax.

#### Flow

**Step 1: Query store database**
- Fetch all items with active Ibotta coupons (expiration_date > now).
- Join items -> item_coupons -> coupons WHERE source = 'IBOTTA'.
- Include: item name, brand, regular price, sale price, coupon value_text, coupon description.

**Step 2: Parse rebate values**
- Parse the value_text field to extract structured savings data:
  - "Save $X.XX" -> minimum quantity 1, savings amount X.XX
  - "Buy N, Save $X.XX" -> minimum quantity N, savings amount X.XX

**Step 3: Find best single deals**
- For each coupon, find the cheapest qualifying items.
- Calculate: net cost = (effective_price x minimum_quantity) - savings_amount.
- Rank by savings percentage.

**Step 4: Find best multi-deal stacks**
- Combine 2-4 P&G deals that together hit the $40 or $60 threshold.
- Add the P&G threshold bonus to the total savings calculation.
- Rank stacks by overall savings percentage.

**Step 5: Present results**
- Show top single deals with: item, retail price, price after rebate, savings percentage.
- Show best stack combinations with: items included, total retail, total after all savings, breakdown of savings by layer.
- Include the tip to submit Ibotta rebates through the Ibotta app after purchase.

**Step 6: Next steps**
- Offer to create an Instacart shopping list for selected deals.
- Offer to show the full list of all active deals.
- If deals are selected, create the Instacart link with appropriate quantities (deal items are packaged goods -- typically qty 1 each unless the deal requires buying multiples).

---

## 5. Data Models

### 5.1 Store Product Database (Schnucks)

**items**

| Column | Type | Description |
|--------|------|-------------|
| upc_id | INTEGER PK | Internal Schnucks product ID |
| upc | TEXT | Short UPC |
| full_upc | TEXT | 14-digit UPC (used for Instacart matching) |
| name | TEXT NOT NULL | Product name, often includes size (e.g., "Tide Pods (42 Ct)") |
| description | TEXT | Product description |
| brand_name | TEXT | Brand (e.g., "Tide", "Schnucks") |
| regular_price | REAL | Normal shelf price |
| sale_price | REAL | Current promotional price (NULL if not on sale) |
| price_string | TEXT | Display string for complex pricing |
| buy_quantity | INTEGER | BOGO: number to buy |
| free_quantity | INTEGER | BOGO: number free |
| markdown | INTEGER | Clearance flag (0/1) |
| markdown_price | REAL | Clearance price |
| size_measure | REAL | Package size numeric value |
| size_uom | TEXT | Package size unit of measure |
| aisle | TEXT | Store aisle/department (e.g., "Meat", "MEAT F", "Produce", "Seafood") |
| image_url | TEXT | Product image URL |
| tax_rate | REAL | Item-specific tax rate |
| area | TEXT | Store area |
| active | INTEGER | Whether item is currently stocked (0/1) |
| created_at | TEXT | First seen timestamp |
| updated_at | TEXT | Last updated timestamp |

**coupons**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Coupon ID (matches couponIds array on items) |
| source | TEXT NOT NULL | "SCHNUCKS" or "IBOTTA" |
| description | TEXT | Human-readable description |
| value_text | TEXT | Savings description (e.g., "Save $3", "Buy 2, Save $4") |
| limit_text | TEXT | Usage limits |
| terms | TEXT | Terms and conditions |
| category | TEXT | Product category |
| brand | TEXT | Brand the coupon applies to |
| image_url | TEXT | Coupon image |
| expiration_date | INTEGER | Expiry as Unix timestamp in milliseconds |
| clip_start_date | INTEGER | When coupon becomes available (ms) |
| clip_end_date | INTEGER | When coupon can no longer be clipped (ms) |
| expiry_type | TEXT | Expiration type |
| app_only | INTEGER | Whether coupon is app-exclusive (0/1) |
| featured | INTEGER | Whether coupon is featured (0/1) |
| fulfillment_type | TEXT | Fulfillment type |
| custom_categories | TEXT | JSON array of custom category strings |
| created_at | TEXT | First seen |
| updated_at | TEXT | Last updated |

**item_coupons** (junction table)

| Column | Type | Description |
|--------|------|-------------|
| upc_id | INTEGER PK | FK to items |
| coupon_id | INTEGER PK | FK to coupons |
| created_at | TEXT | Link creation time |

**categories** (hierarchical)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Category ID from Schnucks API |
| name | TEXT NOT NULL | Category name |
| parent_id | INTEGER | FK to parent category (NULL for root) |
| image_url | TEXT | Category image |
| display_order | INTEGER | Sort order |
| is_leaf | INTEGER | Whether this is a leaf category (0/1) |
| created_at | TEXT | First seen |

**item_categories** (junction table)

| Column | Type | Description |
|--------|------|-------------|
| upc_id | INTEGER PK | FK to items |
| category_id | INTEGER PK | FK to categories |

**scrape_log**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| scrape_type | TEXT | "coupons", "categories", "items", "full" |
| category_id | INTEGER | Category being scraped (for items) |
| items_count | INTEGER | Number of items processed |
| coupons_count | INTEGER | Number of coupons processed |
| started_at | TEXT | Scrape start time |
| completed_at | TEXT | Scrape completion time |
| status | TEXT | "success" or "error" |
| error_message | TEXT | Error details if failed |

**v_best_deals** (database view)

Pre-joined view of items with active coupons, sorted by brand and name. Joins items -> item_coupons -> coupons WHERE expiration_date > now.

### 5.2 Recipe Database

Current size: ~37,329 recipes from 9 sources.

**recipes**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| source_site | TEXT NOT NULL | Origin site identifier (e.g., "allrecipes", "seriouseats", "americastestkitchen", "simplyrecipes", "diethood", "justapinch", "noracooks", "bakewithzoha", "sallysbakingaddiction") |
| source_id | TEXT NOT NULL | URL slug used for deduplication |
| source_url | TEXT NOT NULL | Original recipe URL |
| name | TEXT NOT NULL | Recipe name |
| description | TEXT | Recipe description |
| image_url | TEXT | Recipe photo URL |
| yield_servings | INTEGER | Number of servings |
| yield_text | TEXT | Raw yield string from source |
| prep_mins | INTEGER | Preparation time in minutes |
| cook_mins | INTEGER | Cooking time in minutes |
| total_mins | INTEGER | Total time in minutes |
| calories | INTEGER | Calories per serving |
| protein_g | REAL | Protein grams per serving |
| fat_g | REAL | Fat grams per serving |
| carbs_g | REAL | Carbs grams per serving |
| fiber_g | REAL | Fiber grams per serving |
| sugar_g | REAL | Sugar grams per serving |
| sodium_mg | REAL | Sodium mg per serving |
| cholesterol_mg | REAL | Cholesterol mg per serving |
| rating | REAL | Average user rating (typically 0-5) |
| rating_count | INTEGER | Number of ratings/reviews |
| scraped_at | TEXT | When the recipe was scraped |

Unique constraint: (source_site, source_id) -- prevents duplicate imports from the same source.

**ingredients**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| recipe_id | INTEGER NOT NULL | FK to recipes |
| position | INTEGER NOT NULL | Ingredient order (1-based) |
| text | TEXT NOT NULL | Full ingredient line (e.g., "2 cups all-purpose flour") |

**steps**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| recipe_id | INTEGER NOT NULL | FK to recipes |
| position | INTEGER NOT NULL | Step order (1-based) |
| text | TEXT NOT NULL | Full step instruction text |

**tags**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| recipe_id | INTEGER NOT NULL | FK to recipes |
| type | TEXT NOT NULL | One of: "category", "cuisine", "keyword" |
| value | TEXT NOT NULL | Tag value (e.g., "Chicken", "Mexican", "quick dinner") |

**recipes_fts** -- FTS5 virtual table for full-text search across recipe names and descriptions. Query with: `recipes_fts MATCH 'search term'`.

### 5.3 Application Data (New -- Not in Current System)

The webapp must introduce the following application-level data, which currently exists as markdown files on disk.

**Meal Plans**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| week_id | ISO week identifier (YYYY-WXX) |
| category | "dinner", "lunch", or "dessert" |
| created_at | When the plan was created |
| status | "draft", "approved", "committed" |
| total_cost | Estimated total cost |
| tax_amount | Tax at 8.35% |
| instacart_url | Generated Instacart shopping list URL |

**Meal Plan Items**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| meal_plan_id | FK to meal plan |
| day_of_week | "monday" through "sunday" (dinners) or "monday" through "friday" (lunches) |
| recipe_id | FK to recipe (from recipes DB) |
| recipe_name | Denormalized recipe name |
| estimated_cost | Per-meal cost estimate |
| side | Side dish (lunches) |
| snack | Snack item (lunches) |
| position | Sort order |

**Shopping Lists**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| meal_plan_id | FK to meal plan |
| created_at | When generated |
| subtotal | Pre-tax total |
| tax | Tax amount |
| total | Post-tax total |
| instacart_url | Instacart link |

**Shopping List Items**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| shopping_list_id | FK to shopping list |
| item_name | Product name |
| quantity | Amount needed |
| unit | Unit of measure |
| estimated_price | Price from store DB |
| store_upc_id | FK to Schnucks items (for price lookup) |
| on_sale | Whether item is currently on sale |
| coupon_savings | Any coupon savings available |
| section | Store section grouping (Meat, Produce, Dairy, Pantry, etc.) |
| is_pantry_check | Whether this is a "check if you have it" item |

**Weekly Budget**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| week_id | ISO week identifier (YYYY-WXX) |
| target | Weekly budget target ($350) |
| dinner_amount | Dinner spend (NULL if not yet planned) |
| dinner_status | "planned", "approved", NULL |
| lunch_amount | Lunch spend |
| lunch_status | Status |
| baking_amount | Baking spend |
| baking_status | Status |

**Ledger**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| week_id | ISO week identifier (YYYY-WXX) |
| week_start_date | Monday date of the week |
| dinner_total | Final dinner spend |
| lunch_total | Final lunch spend |
| baking_total | Final baking spend |
| week_total | Combined total |
| created_at | When the ledger entry was finalized |

A ledger entry is created only when all three categories for a week are filled.

**Saved Recipes (Dessert)**

| Field | Description |
|-------|-------------|
| id | Unique identifier |
| recipe_id | FK to recipe (from recipes DB) |
| baked_date | Date baked |
| servings | Scaled serving count |
| estimated_cost | Estimated ingredient cost |
| week_id | ISO week (YYYY-WXX) |
| shopping_option | "have_everything", "add_to_instacart", "separate_quick_run" |
| instacart_url | If created |
| created_at | When saved |

---

## 6. Integrations

### 6.1 Schnucks API (Store Data Harvester)

**Purpose:** Populate and refresh the store product database with current prices, sales, and coupons.

**Base URL:** `https://api.schnucks.com`

**Authentication:**
- Requires two header values: an auth token and a client ID.
- These are obtained by intercepting HTTPS traffic from a live browser session on schnucks.com. This is a manual process and cannot be automated.
- Tokens are long-lived (observed: 2+ months).
- The webapp must store these credentials securely and provide an admin interface for updating them when they expire.
- The webapp should detect authentication failures (401/403 responses) and alert the admin.

**Endpoints consumed:**

| Endpoint | Purpose |
|----------|---------|
| GET /coupon-api/v1/coupons | All coupons (Schnucks store + Ibotta rebates) |
| GET /item-catalog-api/v1/category-trees/HOME_SHOP?store={id} | Full product category hierarchy |
| GET /item-catalog-api/v1/categories/{categoryId}/items?store={id}&fulfillmentType=SELF&page={n}&size=100 | All items in a leaf category (paginated) |

**Refresh process ("full scrape"):**
1. Fetch all coupons. Upsert into coupons table.
2. Fetch category tree. Recursively upsert all categories.
3. For each leaf category, paginate through all items. Upsert each item. Refresh item-coupon and item-category linkages.
4. Log the scrape in the scrape_log table.

**Rate limiting:** 300ms minimum delay between paginated API requests.

**Refresh triggers:**
- Every Tuesday (Schnucks resets weekly sales).
- Whenever data is older than 7 days.
- Manual trigger by admin.
- The webapp should support scheduled/automatic refreshes (e.g., every Tuesday at 5 AM).

**Current scale:** ~20,536 products, ~734 coupons. A full scrape takes several minutes.

### 6.2 Instacart Connect API

**Purpose:** Create shopping lists on Instacart that users can click to add items to their Instacart cart.

**Base URL:** `https://connect.dev.instacart.tools` (dev); production URL TBD.

**Authentication:** Bearer token in Authorization header.

**Endpoints consumed:**

| Endpoint | Purpose | Key Fields |
|----------|---------|------------|
| POST /idp/v1/products/products_link | Create a shopping list | title, line_items[], expires_in |
| POST /idp/v1/products/recipe | Create a recipe page | title, image_url, ingredients[], instructions[] |

**Response:** Returns a `products_link_url` -- a clickable URL that opens Instacart with the items pre-populated.

**Quantity conversion rules (recipe -> grocery):**

The system must convert recipe-style measurements into grocery-purchase quantities before sending to Instacart. Instacart matches against real store products, so items must be described as they are sold.

| Category | Rule | Send to Instacart |
|----------|------|-------------------|
| Meat/seafood (sold by weight) | Send the recipe weight | name: "sea scallops", qty: 1, unit: "pound" |
| Produce (sold by weight) | Send the recipe weight | name: "mushrooms", qty: 0.5, unit: "pound" |
| Produce (sold by each) | Send count | name: "lemon", qty: 1, unit: "each" |
| Butter/dairy/eggs | Send 1 package | name: "eggs", qty: 1, unit: "dozen" -- never "egg yolk" |
| Wine/liquor | Send 1 bottle | name: "white wine", qty: 1, unit: "each" -- never "1 cup" |
| Cream/milk | Send 1 container | name: "heavy whipping cream", qty: 1, unit: "each" |
| Spices/seasonings | Send 1 jar | name: "cayenne pepper", qty: 1, unit: "each" |
| Cheese | Include form in name | name: "shredded Gruyere cheese", qty: 1, unit: "each" |
| Canned goods | Send can count | name: "black olives", qty: 1, unit: "each" |
| Pasta/rice/dry goods | Send 1 package | name: "fusilli pasta", qty: 1, unit: "each" |
| Deal items (household goods) | Send per product, qty matches deal requirement | name: "Oral B toothbrush", qty: 2, unit: "each" |

**Key rules:**
- Never send recipe-only terms as item names (e.g., "egg yolk" -- send "eggs").
- Never send fractional pantry quantities (e.g., "2 tablespoons butter" -- send 1 each butter).
- Include form/cut in the name when it affects product matching (e.g., "shredded", "sliced", "boneless skinless").

### 6.3 Calendar Integration

**Purpose:** Create dinner events on the user's calendar.

**Current behavior:** Creates events via Apple Calendar (osascript) for each dinner, 6-7 PM, in a "Dinner" calendar.

**Webapp requirement:** The webapp should support calendar event creation. Options include:
- iCal file (.ics) download/export per meal or per week.
- Direct integration with Google Calendar, Apple Calendar, or Outlook via their respective APIs.
- At minimum, generate downloadable .ics files that the user can import.

Calendar integration failures must never block the planning workflow.

### 6.4 Recipe Ingestion Pipeline

**Purpose:** Scrape recipes from food blogs and insert them into the recipe database.

**Current sources (9 sites):**

| Source | Method | Scale |
|--------|--------|-------|
| AllRecipes | JSON-LD | Large |
| America's Test Kitchen | JSON-LD | Medium |
| Serious Eats | JSON-LD | Medium |
| Simply Recipes | JSON-LD | Medium |
| Diethood | JSON-LD (Yoast/WPRM) | Medium |
| Just A Pinch | JSON-LD + proxy | Large (~40k+ URLs) |
| Nora Cooks | JSON-LD | Small |
| Bake With Zoha | HTML parsing (Tasty Recipes plugin, no JSON-LD) | Small (~76 recipes) |
| Sally's Baking Addiction | JSON-LD | Medium |

**Ingestion process:**
1. Fetch the site's sitemap XML (or sitemap index -> child sitemaps).
2. Extract all post/recipe URLs.
3. Check which URLs are already in the database (deduplicate by source_site + source_id).
4. For each new URL, fetch the page and extract recipe data:
   - Primary method: Parse JSON-LD `@type: Recipe` blocks (supports direct, Yoast @graph wrapper, and array formats).
   - Fallback method: HTML parsing for sites without JSON-LD (e.g., Tasty Recipes plugin markup).
5. Extract: name, description, image, servings, prep/cook/total time, nutrition, ingredients, steps, categories, cuisines, keywords, rating, rating count.
6. Apply quality filters (configurable per source): minimum rating, minimum review count.
7. Insert into the database with all related data (ingredients, steps, tags).

**Operational requirements:**
- Support concurrent scraping with configurable worker count (current default: 25 workers).
- Support residential proxy routing for sites that block scrapers (current: Bright Data).
- Incremental -- only scrape URLs not already in the database.
- Log progress and provide statistics (scraped, filtered, skipped, errors, dupes).
- The webapp should provide an admin interface to: trigger scrapes for specific sources, view scrape history/status, add new sources, and configure quality filters.

---

## 7. Budget Tracking

### 7.1 Weekly Budget

- Each week has a shared $350 pool across three categories: dinner, lunch, and baking.
- Every planner reads the current week's budget before proposing a plan. The user is told how much is available before any suggestions are made.
- After a plan is approved and committed, the planner writes its cost back to the budget.
- All costs include 8.35% sales tax in the total.

### 7.2 Ledger

- The ledger is the permanent, append-only record of week-over-week and month-over-month spending.
- A week's entry is appended to the ledger only when all three categories (dinner, lunch, baking) have been filled for that week.
- The ledger must never be deleted or overwritten. New entries are only appended.
- The webapp should provide views for:
  - Current week's budget status across all categories.
  - Month-to-date spend vs. $1,400 monthly target.
  - Historical spending trends (week-over-week, month-over-month).
  - Per-category spending trends.

### 7.3 Monthly Budget

- Monthly budget is $1,400 (4 weeks x $350).
- The system should warn the user when month-to-date spending is on track to exceed the monthly budget.
- Remaining monthly budget should be visible on the dashboard.

---

## 8. Non-Functional Requirements

### 8.1 Mobile Experience

Amanda is the primary mobile user. She uses her phone at the grocery store. The mobile experience must be treated as a first-class concern, not a responsive afterthought.

**Requirements:**
- All workflows must be fully functional on mobile.
- Menu-driven interfaces (especially the dessert planner) must have large, tappable buttons -- not tiny text links.
- Shopping lists must be easy to read and check off on a phone screen.
- Instacart links must be tappable and open in the Instacart app if installed.
- The app should work well on spotty cell signal (grocery stores often have poor reception). Critical data (the current shopping list, the current meal plan) should be available offline or at minimum cached aggressively.
- No horizontal scrolling on mobile. Tables must reflow or stack vertically.

### 8.2 Performance

- Recipe searches should return results in under 2 seconds. The recipe database has ~37,000 recipes -- queries must be indexed properly (FTS5 is already available).
- Store database queries (price lookups, sale items, coupon joins) should return in under 1 second.
- Instacart list creation should complete in under 5 seconds.
- Data refresh (full Schnucks scrape) may take several minutes -- this should run in the background with progress reporting. It must not block the user from using the app.

### 8.3 Data Integrity

- The ledger is append-only. The system must prevent accidental deletion or modification of historical ledger entries.
- Budget updates must be atomic -- if two planners run concurrently, they must not overwrite each other's budget claims. Use optimistic locking or equivalent.
- Recipe and store data refreshes must use upsert logic -- never drop and recreate.

### 8.4 Authentication and Authorization

- The app is for a single household. It does not need multi-tenant architecture.
- However, it does need user accounts:
  - Justin: full admin access (data refresh, recipe ingestion, all planners, configuration, deal finder).
  - Amanda: access to dessert planner, lunch planner, shopping lists, and budget view. No access to data refresh, recipe ingestion, or system configuration.
- Authentication can be simple (password-based). No need for OAuth or SSO.
- Sessions should persist -- Amanda should not have to log in every time she opens the app on her phone.

### 8.5 Reliability

- The store data harvester relies on tokens obtained manually. The app must gracefully handle expired tokens: detect 401/403, surface a clear "token expired" alert to admin, and continue functioning with stale data rather than crashing.
- Instacart API failures should not block the workflow. If the Instacart call fails, save everything else and let the user retry the Instacart link later.
- Calendar integration failures should not block the workflow.

---

## 9. Pages and Views

### 9.1 Dashboard
- Current week's meal plan status (dinner: planned/not planned, lunch: planned/not planned, baking: X recipes saved).
- Budget overview: $350 weekly target, amount claimed per category, remaining.
- Month-to-date spending vs. $1,400 target.
- Data freshness: when the Schnucks DB was last refreshed, number of active coupons, number of items on sale.
- Quick-action buttons: Plan Dinners, Plan Lunches, Bake Something, Find Deals.

### 9.2 Dinner Planner
- Guided multi-step flow matching the Phase 1/Phase 2 workflow described in Section 4.1.
- Budget and history context displayed before the user takes any action.
- Meal proposal view: 7-day card layout with swap controls per day.
- Shopping list review: grouped by store section, with line-item prices, subtotal/tax/total, and budget impact.
- Post-commit confirmation: file locations, Instacart link, calendar status.

### 9.3 Lunch Planner
- Guided multi-step flow matching Section 4.2.
- 5-day table view with main/side/snack per day.
- Shopping list with "buy" vs. "check pantry" sections.

### 9.4 Dessert Planner (Amanda's View)
- Full-screen, menu-driven interface. Every screen is a selection menu with large numbered/tappable options.
- Warm tone, personal greeting, Justin's message at session start.
- Recipe cards with images when available.
- Shopping decision flow with three clear paths.
- Must feel like a personal assistant conversation, not a form.

### 9.5 Deal Finder
- Results view: top single deals and best stacks, with clear savings breakdowns.
- Ability to select deals and create an Instacart list from selections.
- Filter/sort by brand, savings percentage, category.

### 9.6 Shopping Lists
- View all active shopping lists (dinner, lunch, baking).
- Consolidated "master list" view that merges all active lists for the week.
- Checkable items (for use at the store on mobile).
- Each list has its Instacart link.

### 9.7 Meal History
- Browse past weeks' meal plans.
- See what was made, what it cost, recipe links.
- Useful for "we liked that, let's make it again" moments.

### 9.8 Budget & Ledger
- Current week's budget breakdown.
- Historical ledger: week-by-week and month-by-month spend.
- Trend charts (spending over time, per-category breakdowns).

### 9.9 Admin (Justin Only)
- Schnucks data refresh: manual trigger, status, last run, error log.
- Recipe ingestion: trigger scrapes per source, view history, add new sources.
- Household configuration: family size, budget, tax rate, dietary restrictions.
- Token management: update Schnucks API credentials, test connectivity.
- System health: database sizes, scrape logs, error counts.

---

## 10. Saved Output Format

The current system writes markdown files to `~/Documents/kitchen/`. The webapp must produce equivalent structured output, accessible both within the app and as downloadable/printable documents.

### 10.1 Output Organization (Logical)

```
Week YYYY-WXX/
  Budget summary
  Dinner/
    Meal plan summary (7 meals, costs, totals)
    Shopping list (itemized, grouped by section)
    7 individual recipe files (one per dinner)
  Lunch/
    Lunch plan (5-day table: main, side, snack)
    Shopping list
  Dessert/
    Each saved recipe with date
    Per-recipe shopping lists (if applicable)
Ledger (permanent, append-only, all weeks)
```

### 10.2 Recipe File Content

Each saved recipe (dinner or dessert) must contain:
- Recipe name, day/date, serving count, estimated cost, total time, rating.
- Full ingredient list with prices from store DB and sale/coupon flags.
- Step-by-step instructions.
- Notes, tips, substitutions, make-ahead instructions (from source recipe).

### 10.3 Export Capabilities

- Print-friendly recipe view (for posting on the fridge or taking to the kitchen).
- Downloadable shopping list (for offline use at the store).
- Shareable Instacart link (per shopping list).

---

## 11. Constraints and Hard Rules

These rules are absolute and must be enforced by the system at all times, regardless of user input.

1. **No peanut butter in school lunches.** This is a school policy. The lunch planner must exclude peanut butter and peanut-containing ingredients at the database query level. This is not a soft preference.

2. **No file writes before approval.** Both the dinner and lunch planners operate in two phases. Nothing is persisted (no meal plans saved, no budget updated, no Instacart lists created) until the user has explicitly approved both the meal selection and the shopping list.

3. **The ledger is append-only.** Historical spending records are never modified or deleted.

4. **Budget is a shared pool.** The $350 weekly budget is shared across dinner, lunch, and baking. Each planner must check what other planners have already claimed before proposing a plan. Concurrent budget claims must not overwrite each other.

5. **Sales tax (8.35%) is always included.** All cost displays to the user must include tax. The budget tracks post-tax totals.

6. **Recipe variety rules.** The dinner planner must enforce: max 2 chicken, max 1 each of beef/pork/seafood, at least 1 vegetarian, at least 2 cuisine styles, no duplicate cooking methods. These are not suggestions.

7. **No meal repeats within 3 weeks** (dinners) or **2 weeks** (lunches).

8. **Instacart quantities are grocery quantities.** Never send recipe measurements (e.g., "2 tablespoons butter") to Instacart. Always convert to purchase units (e.g., "1 each butter").

9. **Amanda's dessert planner is always menu-driven.** Every interaction step presents numbered options. She never needs to type free text.

---

## 12. Open Questions

1. **Recipe database expansion:** Should the webapp support user-submitted recipes (manual entry or URL import), or is the scraper pipeline the only ingestion path?

2. **Multi-store support:** The system is currently Schnucks-only. Should the data model support adding a second store in the future (e.g., Aldi, Costco)?

3. **Meal ratings/feedback:** Should the family be able to rate meals after making them, to improve future suggestions?

4. **Leftover tracking:** Some meals produce leftovers. Should the system track this to reduce the next week's plan (e.g., "you have leftover soup, plan 6 dinners instead of 7")?

5. **Breakfast planning:** The current file structure reserves a `breakfast/` folder. Is breakfast planning a future requirement?

6. **Notification system:** Should the app send notifications (e.g., "Tuesday -- time to plan dinners", "Schnucks data refreshed", "Budget 80% spent this week")?

7. **Recipe scaling accuracy:** The current system scales linearly. Some recipes do not scale linearly (baking especially). Should the system flag recipes that may not scale well beyond their original yield?

8. **Offline mode depth:** How much functionality should work offline? Just viewing saved plans and shopping lists, or also creating new plans against cached data?

---

## 13. Glossary

| Term | Definition |
|------|------------|
| Schnucks | Regional grocery store chain (St. Louis area). The family's primary grocery store. |
| Ibotta | Cashback rebate app. Rebates are submitted after purchase via the Ibotta mobile app. |
| P&G threshold | A Schnucks store coupon offering bonus rewards when spending on Procter & Gamble products reaches $40 or $60. |
| Instacart Connect | Instacart's REST API for programmatically creating shopping lists that users can import into their Instacart cart. |
| Harvester | The script that fetches product data from the Schnucks API and populates the local database. |
| FTS5 | SQLite Full-Text Search extension, version 5. Used for fast text search across recipe names and descriptions. |
| Ledger | The permanent, append-only record of weekly spending across all categories. |
| Week ID | ISO week identifier in the format YYYY-WXX (e.g., 2026-W11). |
| UPC | Universal Product Code. The barcode number on grocery products. |
