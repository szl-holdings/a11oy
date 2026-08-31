# Domain Parity Audit — 2026-08-31T21:11:10.083636+00:00

Domains: a-11-oy.com (product) · a11oy.net (proof registry)
Method: live HTTP fetch of both front doors + route inventory from rendered
link sets; live bytes of a11oy.net/ hashed against szl-holdings/a11oy-net@main.

## Deployment drift — the headline check
- a11oy.net `/` live HTML SHA-256: **37ec7a849608a9c0…** == repo `index.html` SHA-256: **37ec7a849608a9c0…** → **MATCH**. Deployed revision == reviewed source revision on the front door.
- Live `<title>`: `a11oy Proof Registry | SZL Holdings` — canonical lexicon, zero banned terms in live HTML (0 occurrences of banned vocabulary).
- a-11-oy.com `<title>`: `a11oy — Governed Agent Change Management` — canonical.
- NOTE: a cached third-party snapshot of a11oy.net still serves a retired
  pre-rebrand title. Live origin is clean; cache staleness is not drift.

## Route parity gaps (present on one domain only)
| Route | Domain | State | Decision needed |
|---|---|---|---|
| /decision, /terra, /aegis, /puriq-markets, /counsel, /five-space | a-11-oy.com only | LIVE stubs | founder: MIRROR or keep product-only |
| /record/, /record.json, /khipu/, /ayllu/psyche/, /experiments/, /atlas.json | a11oy.net only | LIVE | proof-only by design — document, do not mirror |
| /healthz | both | a-11-oy.com LIVE · a11oy.net 404 (self-declared) | consistent with stated posture |

## Division of labor (verified consistent with copy)
a-11-oy.com = product + buyer demo · a11oy.net = proof registry + machine
contracts (/record.json, /atlas.json, /health.json). No route contradicted
its stated truth state during this pass. Mobile viewport rendering
(375/768/1440px): NOT_INSPECTED — recorded honestly, not assumed PASS.
