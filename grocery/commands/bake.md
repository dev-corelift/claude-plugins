---
description: Interactive dessert and baking recipe discovery for Amanda
allowed-tools: Read, Write, mcp__recipes-db__*, mcp__schnucks-db__*
---

# Bake

Trigger the dessert skill for interactive baking recipe discovery.

Load `${CLAUDE_PLUGIN_ROOT}/context/household.md` for config, then execute the dessert skill:
- Ask what Amanda's in the mood to bake
- Present a curated shortlist from the recipes DB
- Refine through conversation until she finds the one
- Write the full scaled recipe to ~/Documents/kitchen/dessert/
