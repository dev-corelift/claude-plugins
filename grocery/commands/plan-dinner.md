---
description: Plan this week's 7 dinners, price them, write recipe files
allowed-tools: Read, Write, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/harvester:*), Bash(osascript:*), mcp__schnucks-db__*, mcp__recipes-db__*
---

# Plan Dinners

Trigger the dinner-planner skill to generate this week's dinner plan.

Load `${CLAUDE_PLUGIN_ROOT}/context/household.md` for config, then execute the full dinner-planner skill workflow:
- Check last 4 weeks of ~/Documents/kitchen/dinner/ for recent meals and spend
- Generate 7 dinners for family of 7 within remaining budget
- Price against live Schnucks DB
- Write meal-plan.md + 7 recipe files to ~/Documents/kitchen/dinner/YYYY-WXX/
