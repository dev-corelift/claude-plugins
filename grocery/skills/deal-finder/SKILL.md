---
name: deal-finder
description: >
  This skill should be used when the user asks about "deals", "coupons", "Ibotta",
  "best savings", "stack coupons", "what's on sale", or "household item deals".
  It runs the coupon stack optimizer against current Schnucks data and surfaces
  the best Ibotta stacks for household and personal care items.
version: 0.1.0
---

# Deal Finder

Find this week's best coupon stacks using current Schnucks prices and Ibotta rebates.

## What This Does

Household items (P&G brands — Tide, Gain, Crest, Oral B, Olay, Secret, Old Spice, etc.)
have layered savings available every week:
- Layer 1: Schnucks sale price
- Layer 2: Ibotta rebate (requires buying N items)
- Layer 3: P&G threshold bonus ($10 bonus at $40 spend, $20 bonus at $60 spend)

This skill finds the best combinations to maximize savings.

## Steps

1. **Load household config** — `${CLAUDE_PLUGIN_ROOT}/context/household.md`
   - Get Schnucks DB path

2. **Query Schnucks DB** — fetch all items with active Ibotta coupons (expiration_date > now)
   - Join: items → item_coupons → coupons WHERE source = 'IBOTTA'
   - Include: upc_id, name, brand_name, regular_price, sale_price, value_text from coupons

3. **Parse rebate values** from value_text:
   - "Save $X.XX" → min_qty=1, save=X
   - "Buy N, Save $X.XX" → min_qty=N, save=X

4. **Find best single deals** — for each coupon, pick cheapest qualifying items
   - Calculate: net cost = (eff_price × min_qty) - save_amt
   - Sort by savings %

5. **Find best stacks** — combine 2-4 P&G deals that hit $40 or $60 threshold
   - Add P&G bonus ($10 at $40, $20 at $60) to total savings
   - Sort by overall savings %

6. **Present results**

```
=== THIS WEEK'S BEST IBOTTA DEALS ===

Top single deals:
  Buy 2 Oral B toothbrushes   $7.48 retail → $3.48 after rebate  (53% off)
  ...

Best stack (68% off):
  Buy 2 Oral B + Olay cleanser + Buy 2 Secret + Buy 3 Old Spice
  $60.12 retail → $19.12 true cost
  Savings: $21 Ibotta rebates + $20 P&G threshold bonus

Tip: Submit Ibotta rebates through the Ibotta app after purchase.
```

7. **Offer next steps**
   - "Want me to add any of these to this week's cart?"
   - "Want the full list of all active deals?"
