<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# x402 passport-bound inference reference

**MODELED design; source behavior is BLOCKED.** `x402/worker.js` is a disabled
reference, not a qualified payment gateway or proof of a deployed service.
It has no admitted model, verified passport, payment verifier, settlement
receipt store, or deployment configuration.

The previous skeleton forwarded on any nonempty `X-PAYMENT` header and
attached a placeholder passport digest plus a random identifier. Neither
established authorization, model identity, or settlement. The reference now
performs no upstream request and creates no receipt identifier.

## Current source behavior

| Request | Result |
|---|---|
| `GET /v1/models` | 200 with an empty `data` list and `state: BLOCKED` |
| `POST /v1/inference` | 503 with `reference_gateway_unconfigured`, for every model and payment header |
| `OPTIONS` on either implemented path | 204 without payment or inference work |
| Other methods on those paths | 405 with the allowed methods |
| Other paths, including passport, promotion, and receipt lookup | 404 |

Responses are private and non-cacheable. The reference issues no payment
challenge, price quote, passport/promotion header, or settlement claim.
Supplying an environment binding cannot activate it.

Repository deployment code does not identify this file as a deployed source.
The similarly named content-addressed deployment in
[`scripts/deploy_cloudflare_governed_inference.py`](../scripts/deploy_cloudflare_governed_inference.py)
uses `cloudflare/a11oy-governed-inference-worker.mjs` for
`a-11-oy.com/api/v2/*`. That is a different source and route; its existence
does not establish that this reference serves `inference.a-11-oy.com`.
Provider deployment state has not been qualified by these source tests.

## Required verification contract

A future integration must choose the actual gateway/origin boundary before
enabling forwarding. Reuse the estate's existing contracts:

- The canonical Workers origin verifier is
  [`szl-trust/ops/evidence-snapshot-worker/src/payment-context.mjs`](https://github.com/szl-holdings/szl-trust/blob/96a67afe50c4d9717db4f8e330396a22b0e2dcbf/ops/evidence-snapshot-worker/src/payment-context.mjs).
  Its companion `payment-keys.mjs` resolves only Ed25519 keys from the pinned
  Cloudflare JWKS endpoint `https://payments.cloudflare.com/certs`.
  It checks the signature, exact resource audience, scheme, atomic amount,
  and required validity claims with bounded clock leeway. Raw `X-PAYMENT`, `PAYMENT-SIGNATURE`,
  or a parsed settlement response cannot substitute for those checks.
  A verified context explicitly has `settlement_evidence: false`.
- [`ops/x402-bazaar-worker/`](../ops/x402-bazaar-worker/README.md) is a
  separately tested discovery shim. It requires an explicit trusted payment
  service binding, rejects redirects, and checks the settlement-response shape.
  That shape check is not cryptographic verification; the shim's own deployment
  and payment qualification gates remain required. It must not be bound to a
  raw inference origin to bypass verification.

The origin verifier and the discovery shim have different responsibilities.
Importing one, copying its checks, or supplying a binding does not establish
a supported managed-gateway integration.

## Remaining implementation and qualification

Before this reference can serve inference, a reviewed implementation must bind
the exact model revision to a verified passport and current promotion decision,
use the selected payment contract for that resource and price, and retain
independently verifiable settlement and receipt evidence. A candidate model
must be identified as a candidate; an authorization or random identifier must
never be described as a settlement receipt.

Passport, promotion, receipt-chain, and paid-canary behavior remain ROADMAP
for this reference. Changes to payment terms, routes, credentials, deployment,
and any funded canary require their own reviewed execution. Local fixtures
are not transactions, settled payments, or live model outputs.

## Regression tests

From the repository root, with Node.js 22 or later:

```sh
node --test x402/worker.test.mjs ops/x402-bazaar-worker/worker.test.mjs
```

The tests replace network calls and use explicit fixtures. They prove that
payment-shaped headers, model selectors, and environment bindings cannot
unlock the disabled reference, and that it emits no placeholder passport,
payment challenge, or fabricated receipt.
