# Token Refresh

## Do I Need to Do This?

Probably not soon. The token captured January 2026 was still alive in March 2026.
Test first before assuming it's expired.

## Quick Token Test

```bash
source scripts/.env && curl -s -o /dev/null -w "%{http_code}" \
  "https://api.schnucks.com/coupon-api/v1/coupons" \
  -H "authorization: $SCHNUCKS_AUTH_TOKEN" \
  -H "x-schnucks-client-type: WEB_EXT" \
  -H "x-schnucks-client-id: $SCHNUCKS_CLIENT_ID"
```

- `200` = still works
- `401` or `403` = expired, follow steps below

## Refresh Process

**This must be done manually** — it requires intercepting live HTTPS traffic from a browser session. It cannot be automated.

1. Open an SSL proxy tool (API Ghost, Charles Proxy, Proxyman, mitmproxy — any works)
2. Browse to **schnucks.com**, log in, click around a few categories
3. Find a request to `api.schnucks.com` and grab these headers:
   ```
   authorization: <TOKEN>
   x-schnucks-client-id: <CLIENT_ID>
   ```
4. Update `scripts/.env` with the new values
5. Re-run the token test above to confirm

## Signs It's Expired

- Harvester returns 401/403
- Empty responses from API calls
- `python3 harvester.py coupons` shows 0 results
