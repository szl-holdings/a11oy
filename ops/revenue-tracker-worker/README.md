# Request tracker Worker (`szl-revenue-tracker`)

This Worker sits on `a-11-oy.com/api/a11oy/v1/*` and `a-11-oy.com/v1/*`. It
forwards every request unchanged and writes one Workers Analytics Engine point
per request to the `x402_revenue` dataset. Despite the dataset name, it records
**requests, not revenue**: it never sees a payment, price or settlement.

Before this source existed, the live Worker wrote only a JSON blob with the
method, path and timestamp, so people could not be told apart from automation.
Those older rows have a JSON string in `blob1`; rows from this source have
`blob1 = 'v2'`.

## What a v2 point holds

| Field | Value |
|---|---|
| `index1` | request path (unchanged from v1) |
| `blob1` | `v2` |
| `blob2`–`blob4` | method, path, host |
| `blob5`–`blob7` | Cloudflare country, ASN, colo |
| `blob8` | client class: `browser`, `crawler`, `cli`, `library`, `verified-bot`, `empty`, `other` |
| `blob9` | Cloudflare verified-bot category, when Cloudflare provides one |
| `blob10` | daily visitor key: first 128 bits of HMAC-SHA256 over the UTC day, client IP and user agent |
| `blob11` | `HMAC_DAILY`, or `UNAVAILABLE` when no secret is configured |
| `double1`–`double3` | start time (ms), origin status (`0` if the origin fetch threw), duration (ms) |

No IP address, user agent, query string or cookie is stored. The visitor key
changes every UTC day and cannot be reversed or linked across days without the
secret. The client class is a heuristic over the user agent, except that a
Cloudflare verified-bot category always wins; treat `browser` as "claims to be
a browser", not as a confirmed person.

The secret is set by the owner, never committed:

```shell
npx wrangler secret put VISITOR_KEY_SECRET --config ops/revenue-tracker-worker/wrangler.jsonc
```

Without it (or with fewer than 32 characters) the Worker still records every
other field and labels the visitor key `UNAVAILABLE`.

## Queries (Analytics Engine SQL API)

People versus automation, last 7 days:

```sql
SELECT blob8 AS client, SUM(_sample_interval) AS requests
FROM x402_revenue
WHERE blob1 = 'v2' AND timestamp > NOW() - INTERVAL '7' DAY
GROUP BY client ORDER BY requests DESC
```

Distinct visitors per day (requires `HMAC_DAILY` rows):

```sql
SELECT toStartOfDay(timestamp) AS day, blob8 AS client, COUNT(DISTINCT blob10) AS visitors
FROM x402_revenue
WHERE blob1 = 'v2' AND blob11 = 'HMAC_DAILY' AND timestamp > NOW() - INTERVAL '7' DAY
GROUP BY day, client ORDER BY day, visitors DESC
```

Requests to the priced route families:

```sql
SELECT blob3 AS path, blob8 AS client, SUM(_sample_interval) AS requests
FROM x402_revenue
WHERE blob1 = 'v2' AND (blob3 LIKE '/v1/data%' OR blob3 LIKE '/v1/acoustic%'
  OR blob3 LIKE '/api/a11oy/v1/experimental%')
GROUP BY path, client ORDER BY requests DESC
```

## Deploy

Only from a reviewed, merged commit, by `.github/workflows/revenue-tracker-worker.yml`,
which then checks that a live request carries `x-szl-tracker: written`.
