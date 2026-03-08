---
description: Interactive dessert and baking recipe discovery for Amanda
allowed-tools: Read, Write, mcp__recipes-db__*, mcp__schnucks-db__*
---

# Bake

Trigger the dessert-planner skill for fully menu-driven baking recipe discovery.

Load `${CLAUDE_PLUGIN_ROOT}/context/household.md` for config, then execute the dessert-planner skill:
- Every step is a numbered menu — Amanda never types free text
- Mood → refine → pick recipe → servings → confirm → save
- Writes recipe + separate shopping list to ~/Documents/kitchen/dessert/
