# Grocery Plugin

Weekly meal planning, coupon stacking, Instacart cart building, and baking for a family of 7.

## Components

### Commands
| Command | Description |
|---------|-------------|
| `/plan-week` | Plan this week's 7 dinners, price them, write recipe files |
| `/build-cart` | Consolidate ingredients and build Instacart cart |
| `/deals` | Show this week's best Ibotta coupon stacks |
| `/bake` | Interactive baking and dessert recipe discovery (Amanda) |

### Skills (auto-trigger)
| Skill | Triggers on |
|-------|------------|
| `meal-planning` | "plan meals", "what should we eat", "plan this week" |
| `cart-builder` | "build my cart", "add to Instacart", "shopping list" |
| `deal-finder` | "deals", "coupons", "what's on sale", "stack coupons" |
| `dessert` | "baking", "what should I bake", "I want to make something sweet", "pie mood" |

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
  dessert/
    YYYY-MM-DD-recipe-name.md
  breakfast/                ← future
  lunch/                    ← future
```

## Setup

1. Ensure DBs are in `data/` — `schnucks.db` and `recipes.db`
2. Update `context/household.md` if budget or paths change
3. When Instacart dev key arrives, add MCP to `.mcp.json`

## Instacart (pending)

Instacart MCP will be added to `.mcp.json` once developer access is approved.
The cart-builder skill already has the wiring — it will push directly when connected.
