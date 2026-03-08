---
description: Interactive dessert and baking recipe discovery for Amanda
allowed-tools: Read, Write, mcp__recipes-db__*, mcp__schnucks-db__*
---

# Bake

Trigger the dessert-planner skill for Amanda's personal baking assistant.

Load `${CLAUDE_PLUGIN_ROOT}/context/household.md` for config, then execute the dessert-planner skill:
- Address Amanda by name throughout — warm, personal, fun tone
- Open with her name, then deliver Justin's love you message, then the menu
- Every step is a numbered menu — she never types free text
- Mood → refine → pick recipe → servings → confirm → save
- Writes recipe + separate shopping list to ~/Documents/kitchen/dessert/
