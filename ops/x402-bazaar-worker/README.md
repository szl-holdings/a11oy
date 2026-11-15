# x402 Bazaar discovery shim (a11oy monetization edge lane)

## Why
Measured 2026-11-15 from the owner laptop: the live 402 challenge on
https://inference.a-11-oy.com/v1/chat/completions (Cloudflare Monetization
Gateway, closed beta) carries **no extensions field**, so the resource cannot
be discovered via the CDP x402 Bazaar (23k+ resources, opt-in). The managed
gateway's response shape is fixed and cannot be extended by configuration.

## What this does
A first-party Cloudflare Worker that claims the exact route
/v1/chat/completions (narrower than the gateway's /v1/*, so CF route
precedence gives this worker the single most-specific match):

- **Unpaid requests** get a 402 challenge in byte-parity with the live
  gateway challenge (same accepts/payTo/asset/amount/help) PLUS the
  `extensions.bazaar` discovery block (method, description, input/output
  JSON schemas and examples per docs.cdp.coinbase.com/x402/seller/get-discovered).
- **Paid requests** are passed through to the CF Monetization Gateway for
  REAL verification (sentinel header `x-szl-bazaar-passthrough: 1`). This
  worker never verifies payments and never serves content unpaid (fail-closed).

## Parity constants
Probed 2026-11-15 (~10:06Z), evidence: `C:\SZL\edge-debug\bazaar_probe.txt`
and decisions.md. payTo 0x7b133ef996852c223379d6d1245430300970291A, USDC
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913, eip155:8453 (Base), amount 20000
atomic (0.02 USDC/request), maxTimeoutSeconds 3600.

## Deployment (OWNER-GATED — do not deploy without owner direction)
1. Deploy this worker via the Cloudflare dashboard (Edge CDP session) on route
   `inference.a-11-oy.com/v1/chat/completions`.
2. Validate the 402: `POST https://api.cdp.coinbase.com/platform/v2/x402/validate`
   with the challenge body (no API key needed).
3. Indexing paid call: one PAID request through the CDP Facilitator triggers
   Bazaar indexing — **requires a funded wallet** (the standing owner item
   gating the revenue canary AND indexing).
4. Publish the receipt (challenge sha256 + route) to
   SZLHOLDINGS/frontier-54-runs per doctrine.

## Open questions (honest, pre-review)
- Same-zone subrequest re-entry: the sentinel design assumes the inner
  `fetch()` re-enters routing and reaches the managed gateway. If the inner
  fetch instead returns to THIS worker (CF runs only the first matching worker
  per request chain), the passthrough must instead forward to a dedicated
  gateway-claimed path (e.g. an internal alias route). Verified only in
  staging before production cutover — never assume readiness.
- `PAYMENT-REQUIRED` header parity: the gateway emits it base64; the shim
  emits body-only (the body is authoritative per the x402 v2 spec). Confirm
  with a Bazaar validate call whether the header is required for discovery.
- CORS/OPTIONS: #3386 fixed OPTIONS on the gateway route; the shim must not
  regress preflight (OPTIONS returns 404 from the shim — extend before
  deployment if browser buyers are in scope).
