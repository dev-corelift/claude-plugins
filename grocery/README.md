# Grocery Plugin

Weekly dinner planning, school lunches, coupon stacking, and baking for a family of 7.

## Components

### Commands
| Command | Description |
|---------|-------------|
| `/plan-dinner` | Plan this week's 7 dinners, price them, write recipe files |
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
  ledger.md                 ← permanent week-over-week spending record
  YYYY-WXX/
    budget.md               ← shared $350 pool across dinner + lunch + baking
    instacart-paste.md      ← combined master paste for the whole week
    dinner/
      meal-plan.md
      shopping-list.md
      monday-meal-name.md
      ...
    lunch/
      lunch-plan.md
      shopping-list.md
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
