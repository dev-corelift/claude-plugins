# Grocery Plugin

Weekly dinner planning, school lunches, coupon stacking, and baking for a family of 7.

## Components

### Commands
| Command | Description |
|---------|-------------|
| `/plan-week` | Plan this week's 7 dinners, price them, write recipe files |
| `/plan-lunches` | Plan this week's 5 school day lunches for the girls |
| `/deals` | Show this week's best Ibotta coupon stacks |
| `/bake` | Menu-driven baking and dessert recipe discovery (Amanda) |

### Skills (auto-trigger)
| Skill | Triggers on |
|-------|------------|
| `dinner-planner` | "plan meals", "what should we eat", "plan this week", "what's for dinner" |
| `lunch-planner` | "school lunches", "pack lunches", "girls lunches", "what should I pack" |
| `deal-finder` | "deals", "coupons", "what's on sale", "stack coupons" |
| `dessert-planner` | "baking", "what should I bake", "I want to make something sweet", "pie mood" |

### MCP Servers
- `schnucks-db` — Schnucks prices, sales, and Ibotta coupons
- `recipes-db` — 31,814 recipes from AllRecipes, Serious Eats, Simply Recipes, ATK

## Output Structure

```
~/Documents/kitchen/
  dinner/
    YYYY-WXX/
      meal-plan.md          ← week summary (budget, meals, tax)
      shopping-list.md      ← categorized ingredients with prices
      instacart-paste.md    ← clean paste-ready list for ChatGPT Instacart
      monday-meal-name.md   ← full recipe, scaled to 7
      tuesday-meal-name.md
      ...
  lunch/
    YYYY-WXX/
      lunch-plan.md         ← 5-day lunch summary
      shopping-list.md      ← lunch-only shopping list
  dessert/
    YYYY-MM-DD-recipe-name.md
    YYYY-MM-DD-recipe-name-shopping-list.md
  breakfast/                ← future
```

## Setup

1. Ensure DBs are in `data/` — `schnucks.db` and `recipes.db`
2. Update `context/household.md` if budget or paths change
3. When Instacart dev key arrives, add MCP to `.mcp.json`

## Instacart (pending)

Instacart MCP will be added to `.mcp.json` once developer access is approved.
