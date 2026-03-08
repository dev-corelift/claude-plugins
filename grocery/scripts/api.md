# Schnucks API Reference

Base URL: `https://api.schnucks.com`

## Auth Headers

```
authorization: <SCHNUCKS_AUTH_TOKEN>
x-schnucks-client-type: WEB_EXT
x-schnucks-client-id: <SCHNUCKS_CLIENT_ID>
content-type: application/json
```

Credentials live in `scripts/.env`. If requests return 401/403, see `token_refresh.md`.

---

## Endpoints

### GET /coupon-api/v1/coupons

Returns all coupons — both Schnucks store coupons and Ibotta rebates.

Key response fields:
| Field | Description |
|-------|-------------|
| `id` | Coupon ID (matches `couponIds` on items) |
| `source` | `SCHNUCKS` or `IBOTTA` |
| `valueText` | e.g. `"Save $3"`, `"Buy 2, Save $4"`, `"Spend $30 Get $10 Rewards"` |
| `expirationDate` | Unix timestamp (milliseconds) |
| `category` | Product category |

---

### GET /item-catalog-api/v1/category-trees/HOME_SHOP

Returns full category hierarchy with IDs. Rarely changes — cache it.

---

### GET /item-catalog-api/v1/categories/{categoryId}/items

Query params: `store=144`, `fulfillmentType=SELF`, `page=0`, `size=100`

Key response fields:
| Field | Description |
|-------|-------------|
| `upcId` | Internal ID (used in DB as primary key) |
| `fullUpc` | 14-digit UPC (use for Instacart matching) |
| `regularAmount` | Normal price |
| `adAmount` | Sale price (null if not on sale) |
| `couponIds` | Array of applicable coupon IDs |
| `buyQuantity` / `freeQuantity` | BOGO deal details |
| `markdown` / `markdownPrice` | Clearance flag and price |

---

## Coupon Stacking Logic

```
Register price = adAmount (if on sale) OR regularAmount
True cost = Register price - Ibotta cashback (submitted via app after purchase)

Stackable: Sale + Schnucks store coupon + Ibotta rebate + P&G threshold bonus
```

P&G threshold (Schnucks store coupon — changes weekly):
- Spend $30 on P&G products → get $10 rewards
- Spend $60 on P&G products → get $20 rewards

P&G brands: Tide, Gain, Downy, Bounty, Charmin, Pampers, Gillette, Oral B, Olay, Secret, Old Spice, Crest, Swiffer, Febreze, Pantene, Head & Shoulders, Always, Tampax

---

## High-Value Category IDs

| ID | Name | Brands |
|----|------|--------|
| 5487 | Laundry | Tide, Gain, Downy |
| 5502 | Paper Goods | Bounty, Charmin |
| 5535 | Cleaning | Dawn, Swiffer, Febreze |
| 5571 | Oral Hygiene | Crest, Oral B |
| 5523 | Hair Care | Pantene, Head & Shoulders |
| 5528 | Deodorant | Secret, Old Spice |
| 5568 | Body Care | Olay |
| 5332 | Shaving | Gillette, Venus |
| 5478 | Feminine Care | Always, Tampax |
| 5522 | Diapers | Pampers, Luvs |

---

## Notes

- Rate limit: 0.3s between requests (harvester enforces this)
- Coupons reset weekly — refresh on Tuesdays
- `couponIds` on items directly links to coupon `id` — no fuzzy matching needed
