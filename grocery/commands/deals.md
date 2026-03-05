---
description: Show this week's best Ibotta coupon stacks
allowed-tools: Read, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/harvester:*), mcp__schnucks-db__*
---

# Deals

Trigger the deal-finder skill to show this week's best coupon stacks.

Load `${CLAUDE_PLUGIN_ROOT}/context/household.md` for config, then execute the deal-finder skill:
- Query Schnucks DB for active Ibotta coupons
- Find best single deals and P&G threshold stacks
- Present top deals sorted by savings %
