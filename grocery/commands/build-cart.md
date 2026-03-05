---
description: Build Instacart cart from this week's meal plan
allowed-tools: Read, Write, mcp__schnucks-db__*, mcp__recipes-db__*
---

# Build Cart

Trigger the cart-builder skill to consolidate this week's ingredients and build the shopping cart.

Load `${CLAUDE_PLUGIN_ROOT}/context/household.md` for config, then execute the cart-builder skill:
- Read all recipe files from ~/dinners/current week/
- Consolidate and deduplicate ingredients
- Map to Schnucks UPCs and current prices
- Push to Instacart if connected, otherwise write shopping-list.md
