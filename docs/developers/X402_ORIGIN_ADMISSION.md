# Origin payment admission

The acoustic, dataset, and experimental handlers are the supported monetized
reads. This repository does not store their prices. Cloudflare rules stay
outside this process. A verified `PAYMENT-CONTEXT` is not settlement and is
not turned into a `PAYMENT-SETTLEMENT` or `PAYMENT-RESPONSE` header.

## What is true before configuration

With `A11OY_X402_PUBLIC_BASE`, `A11OY_X402_SCHEME`, and the family amount unset,
each family is `UNCONFIGURED`. The handler still runs. `PAYMENT-SIGNATURE`,
`X-Payment-Verified`, `Host`, and `X-Forwarded-Host` are not payment authority.
The response says `x-a11oy-payment-enforcement: unconfigured` and
`x-a11oy-settlement-evidence: false`. That state is not deployed enforcement.

## What configuration is required before enforcement

A family is enforced only when its own amount is set. Base and scheme are then
required for that family. An unset amount leaves the family `UNCONFIGURED`
even when another family is configured. A set amount with a missing or invalid
base, scheme, amount, or leeway is HTTP 503 `CONFIGURATION_INCOMPLETE` for
that family and does not run its handler.

| Variable | Meaning |
|---|---|
| `A11OY_X402_PUBLIC_BASE` | `https://host` with no path. Audience is this base plus the path. |
| `A11OY_X402_SCHEME` | `exact`. `upto` is refused. |
| `A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC` | Expected atomic amount for `/v1/acoustic/` and its three checks. |
| `A11OY_X402_DATA_AMOUNT_ATOMIC` | Expected atomic amount for `/v1/data/` and `/v1/data/{name}`. |
| `A11OY_X402_EXPERIMENTAL_AMOUNT_ATOMIC` | Expected atomic amount for `/api/a11oy/v1/experimental/`. |
| `A11OY_X402_LEEWAY_SECONDS` | Optional clock leeway, 0 through 30. Default 5. |

The amount is the gateway rule's atomic price (1 unit = $0.000001), from 1000
to 100000000, supplied by the operator. Source does not copy a live rule.

`upto` with a family amount set is HTTP 503 `UPTO_NOT_SUPPORTED` before the
handler. A successful upto response must carry `PAYMENT-SETTLEMENT` with the
actual amount, and an authorization below that price must not be served. The
pinned validator accepts that shorter authorization when the configured price
is passed as its maximum, and this origin does not emit a settlement header.
Live gateway rules are unchanged. `exact` success carries no
`PAYMENT-SETTLEMENT` and no `PAYMENT-RESPONSE`.

Verification for `exact` is `szl_trust_x402_payment_context.validate_payment_context`,
the estate copy of szl-trust `scripts/x402_payment_context.py`. Ed25519 keys
come only from the pinned JWKS `https://payments.cloudflare.com/certs`, unless
a test injects `app.state.x402_keys`. One resolver is shared by the process.
Its fetch runs off the event loop, and a failed fetch is HTTP 503 without the
handler. The image installs `pyjwt` so that call can run. Tests do not contact
the pinned URL.

Missing, malformed, wrong algorithm, untrusted key, bad signature, expired,
not-yet-valid, wrong audience, wrong scheme, and wrong amount contexts are
HTTP 403 before the handler. Two `PAYMENT-CONTEXT` headers are
`AMBIGUOUS_CONTEXT`. There is no JWT replay blacklist.

## What a verified request returns

The handler result, `x-a11oy-payment-enforcement: context-verified`, and
`x-a11oy-settlement-evidence: false`. No settlement header is written.
HEAD on these paths is HTTP 405 and does not run the handler. A different
case or a trailing slash is not the paid route.

The spend ledger is a separate in-process cap. Its lock is not durable across
restart or replicas. These reads do not call it, because no ledger amount is
configured for them. Invalid amounts, including NaN and a value that rounds to
zero, are refused. An operation retry is the same id, canonical amount, and
payload digest; a conflict does not append. Admission memory is bounded by
refusing new ids, not by forgetting old ones.

Public proof and health routes are not in the three families.

## What this source does not establish

No deployment has been shown to set the variables above, to reach the pinned
JWKS, or to match a live gateway rule. Until that readback exists, enforcement
is source capability plus configuration, not tested deployment.
