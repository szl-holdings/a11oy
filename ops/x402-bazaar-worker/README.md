<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# x402 Bazaar discovery shim

**Source-tested only. Not deployed or payment-qualified by this change.**
The canonical source lane is `ops/x402-bazaar-worker/` in `szl-holdings/a11oy`.
No production route, price, payee, credential, DNS record, or readiness gate
is changed by this repair.

## Request contract

The shim claims only `/v1/chat/completions`:

- `POST` without a nonempty payment header returns 402. `PAYMENT-REQUIRED`
  contains base64-encoded UTF-8 JSON equal to the body, including the
  existing discovery metadata. The existing payment terms are unchanged.
- `OPTIONS` permits POST with Content-Type, PAYMENT-SIGNATURE, and X-PAYMENT.
  It performs no inference, payment, or upstream request. CORS is public and
  does not allow cookies/credential mode. Other methods return 405.
- Caller-supplied `x-szl-bazaar-passthrough` is rejected for every value.
  It is not an authentication mechanism or an internal routing capability.
- Payment-bearing POSTs require an explicit `PAYMENT_GATEWAY` HTTP service
  binding. Missing binding returns 503. There is no global `fetch()` fallback,
  same-zone routing assumption, or direct-origin path.
- The bound service owns real verification and settlement. The shim forwards
  the request/body/payment header once with redirect mode `manual`; redirects
  and exceptions become 502. Gateway errors retain their status and body.
- Successful content requires a syntactically valid `PAYMENT-RESPONSE` with
  `success: true`, the expected network, and a nonempty transaction value.
  This is a shape check, **not cryptographic or on-chain verification**.
  Streaming bodies and settlement headers pass through; responses are not cached.

## Local regression tests

From the repository root, with Node.js 22 or later:

```sh
node --test ops/x402-bazaar-worker/worker.test.mjs
npm --prefix ops/x402-bazaar-worker/verification ci --ignore-scripts --no-audit --no-fund
node ops/x402-bazaar-worker/verification/generate-discovery.mjs --check
node --test ops/x402-bazaar-worker/verification/discovery.test.mjs
```

The lockfile pins the test-only SDK dependency graph. No SDK package is imported
by the deployed Worker; the Worker remains one self-contained JavaScript file.
The `--check` command verifies the generated declaration without editing source.

Tests replace all global network calls and use an explicit in-memory gateway.
They cover header spoofing, unpaid requests, exact challenge/header parity,
payment-term preservation, CORS preflight, method/path boundaries, missing
binding, gateway errors/redirects, and settlement-response shape checks.
Fixtures are not paid transactions, model outputs, or deployment evidence.

## Generated discovery declaration

`discovery-config.json` is the editable input to the official
`declareDiscoveryExtension` helper. To regenerate the marked block in
`worker.js` after editing that configuration:

```sh
npm --prefix ops/x402-bazaar-worker/verification run generate
```

The generated extension supplies `info.input.type`, POST method, JSON body,
input/output examples, and the matching JSON Schema. Resource description
and media type belong to `resource`, not a custom extension envelope.
The advertised example describes a non-streaming text response; it does not
claim to enumerate every upstream parameter or modality. Its model ID is
bound to a timestamped public registry observation in `verification/provenance.json`.
That observation is not a guarantee of future availability or model quality.
All output examples are fixtures, not measured inference results or receipts.

The SDK tests validate the complete V2 challenge, protocol-level metadata,
example/schema consistency, exact generation parity, echoed metadata extraction,
and negative cases including external schema references. They perform no
network requests, wallet operations, payment verification, or settlement.
Local validation is a source-contract result, not a marketplace listing.

## Managed Cloudflare integration boundary

Cloudflare documents a separate origin contract: its managed gateway forwards
an Ed25519-signed `PAYMENT-CONTEXT` JWT, which the origin must validate against
the pinned Cloudflare JWKS. For fixed pricing, the gateway owns settlement and
the payment receipt. A parsed payment response is not a substitute for that
signature check. This discovery shim does not implement or qualify that
origin integration, and documented service bindings alone do not establish
that the managed gateway can be used as `PAYMENT_GATEWAY`. Keep the current
managed-gateway production route unchanged until the supported architecture,
origin verification, and staging evidence are established.

## Deployment gates â€” all remain required

1. Independent source review and protected CI must pass. No bypass or automatic
   deployment is introduced here.
2. Identify a supported, owner-approved verification gateway to bind as
   `PAYMENT_GATEWAY`. Cloudflare documents Worker-to-Worker service bindings;
   this does **not** establish that its managed Monetization Gateway is
   available as a bindable service. Do not bind this to a raw inference origin
   or back to this shim. Without a verified integration, keep this staged and
   leave the existing managed-gateway production route unchanged.
3. Reconcile quoted payment terms with the gateway immediately before staging.
   The source terms are the recorded 2026-11-15 baseline, not a live-price oracle.
4. Test routing, invalid/expired/replayed payments, settlement, failure handling,
   streaming completion, and receipt binding in the approved staging environment.
5. The local metadata shape is generated and validated against
   `@x402/extensions@2.31.0` and `@x402/core@2.31.0`. This does not prove
   acceptance by the live CDP validator, client echo, or catalog inclusion.
   Reconcile SDK versions and staging behavior before a release.
6. After an approved public staging deployment, call the documented validation
   endpoint with `resource` and `method` (not the raw challenge):

```sh
curl -X POST https://api.cdp.coinbase.com/platform/v2/x402/validate \
  -H 'Content-Type: application/json' \
  -d '{"resource":"https://inference.a-11-oy.com/v1/chat/completions","method":"POST"}'
```

Use the actual approved staging URL when validating staging. Validation alone
is not settlement or indexing. One separately authorized funded-wallet canary
and independent receipt/settlement verification remain required. This repair
performs none of those operations and handles no keys.

## References

- x402 V2 transport headers: https://docs.x402.org/core-concepts/http-402
- Bazaar protocol/schema: https://docs.x402.org/extensions/bazaar
- Managed gateway origin validation: https://developers.cloudflare.com/monetization-gateway/configuration/payment-validation/
- Bazaar discovery/validation: https://docs.cdp.coinbase.com/x402/seller/get-discovered
- HTTP service bindings: https://developers.cloudflare.com/workers/runtime-apis/bindings/service-bindings/http/

Historical payment baseline (2026-11-15): Base `eip155:8453`, USDC asset
`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, payee
`0x7b133ef996852c223379d6d1245430300970291A`, amount `20000` atomic units,
`maxTimeoutSeconds: 3600`. This is source configuration, not revenue evidence.
