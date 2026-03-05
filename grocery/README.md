# Grocery Plugin

Weekly meal planning, coupon stacking, and Instacart cart building for a family of 7.

## Components

### Commands
| Command | Description |
|---------|-------------|
| `/plan-week` | Plan this week's 7 dinners, price them, write recipe files |
| `/build-cart` | Consolidate ingredients and build Instacart cart |
| `/deals` | Show this week's best Ibotta coupon stacks |

### Skills (auto-trigger)
| Skill | Triggers on |
|-------|------------|
| `meal-planning` | "plan meals", "what should we eat", "plan this week" |
| `cart-builder` | "build my cart", "add to Instacart", "shopping list" |
| `deal-finder` | "deals", "coupons", "what's on sale", "stack coupons" |

### MCP Servers
- `schnucks-db` — SQLite MCP server pointed at the Schnucks deals database

## Output

All meal plans and recipes are written to `~/dinners/YYYY-WXX/`:
- `meal-plan.md` — week summary (budget used, meals made)
- `shopping-list.md` — consolidated ingredient list with prices
- `monday-meal-name.md` through `sunday-meal-name.md` — printable recipes

## Setup

1. Ensure Schnucks DB is populated: run `python3 harvester.py full` from the schnucks folder
2. Update `context/household.md` if budget or paths change
3. When Instacart dev key arrives, add to `.mcp.json`

## Instacart (pending)

Instacart MCP will be added to `.mcp.json` once developer access is approved.
The cart-builder skill already has the wiring — it will push directly to Instacart when connected.
