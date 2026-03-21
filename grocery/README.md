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

### Instacart Bridge
- `scripts/instacart-bridge.py` — one-shot CLI that creates Instacart shopping lists/recipes via REST API
- Works in cowork sandbox (no MCP server needed, no blocked domains)
- Usage: `echo '{"title":"...","line_items":[...]}' | python3 scripts/instacart-bridge.py shopping-list`

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

## Updating the Plugin Locally (GitHub bypass)

When the GitHub repo is unavailable, update the cowork plugin cache directly.

### Cowork paths

Cowork reads from two locations. Both must be updated for changes to take effect.

**Marketplace source** (plugin definition cowork reads at session start):
```
~/Library/Application Support/Claude/local-agent-mode-sessions/afaec8d2-365e-42b9-9102-127ec6ef13b8/22d47750-f24c-4b0d-bbc7-5f7d534bea39/cowork_plugins/marketplaces/dev-corelift-plugins/grocery/
```

**Cache** (versioned copy with data and binaries):
```
~/Library/Application Support/Claude/local-agent-mode-sessions/afaec8d2-365e-42b9-9102-127ec6ef13b8/22d47750-f24c-4b0d-bbc7-5f7d534bea39/cowork_plugins/cache/dev-corelift-plugins/grocery/0.2.0/
```

### Refresh the database

```bash
cd ~/projects/tools/cowork-plugins/grocery
python3 scripts/harvester.py full
```

### Push to cowork

```bash
SRC=~/projects/tools/cowork-plugins/grocery
BASE=~/Library/Application\ Support/Claude/local-agent-mode-sessions/afaec8d2-365e-42b9-9102-127ec6ef13b8/22d47750-f24c-4b0d-bbc7-5f7d534bea39/cowork_plugins
MARKET="$BASE/marketplaces/dev-corelift-plugins/grocery"
CACHE="$BASE/cache/dev-corelift-plugins/grocery/0.2.0"

# MCP config (must go to BOTH marketplace and cache)
cp "$SRC/.mcp.json" "$MARKET/.mcp.json"
cp "$SRC/.mcp.json" "$CACHE/.mcp.json"

# Plugin metadata
cp "$SRC/.claude-plugin/plugin.json" "$CACHE/.claude-plugin/plugin.json"

# Skills and commands
cp "$SRC/skills/dinner-planner/SKILL.md" "$CACHE/skills/dinner-planner/SKILL.md"
cp "$SRC/skills/lunch-planner/SKILL.md" "$CACHE/skills/lunch-planner/SKILL.md"
cp "$SRC/skills/dessert-planner/SKILL.md" "$CACHE/skills/dessert-planner/SKILL.md"
cp "$SRC/skills/deal-finder/SKILL.md" "$CACHE/skills/deal-finder/SKILL.md"
cp "$SRC/commands/"*.md "$CACHE/commands/"

# Context
cp "$SRC/context/household.md" "$CACHE/context/household.md"

# Data
cp "$SRC/data/schnucks.db" "$CACHE/data/schnucks.db"

# Scripts
cp "$SRC/scripts/harvester.py" "$CACHE/scripts/harvester.py"
cp "$SRC/scripts/instacart-bridge.py" "$CACHE/scripts/instacart-bridge.py"
cp "$SRC/scripts/.env" "$CACHE/scripts/.env"
```

Start a new cowork session to pick up the changes.

### When GitHub is back

Push to the `ul0gic/cowork-plugins` repo and the normal sync resumes. Both marketplace and cache will be overwritten on next update.

## Instacart

**Local (Claude Code):** Instacart MCP server in `.mcp.json` works directly — `mcp__instacart__create-shopping-list` etc.

**Cowork:** Instacart domains are blocked by the sandbox. Skills use `scripts/instacart-bridge.py` instead — a one-shot CLI that pipes JSON to the Instacart REST API and prints the URL. The cowork `.mcp.json` does not include the instacart MCP server.

**To switch to production:** update the API key and endpoint in `instacart-bridge.py` from `connect.dev.instacart.tools` to the prod URL.
