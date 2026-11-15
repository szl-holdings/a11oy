# x402 Passport-Gated Inference - Worker Contract

## Goal

Monetize governed inference so that every paid answer settles against
the verifiable history of the exact model revision that served it.

The Cloudflare worker (`inference.a-11-oy.com`, currently serving the
`szl-inference-v3` backend, 1 model in /v1/models) becomes an x402-
payment-gated gateway that binds each call to an Ouroboros Model
Anatomy Passport digest.

## Response contract

Every inference response carries:

- `X-Ouroboros-Passport-Digest`: content digest of the serving model revision passport
- `X-Ouroboros-Promotion`: promotion decision at serve time (PROMOTED or CANDIDATE)
- `X-Ouroboros-Model-Revision`: exact model revision that produced the answer
- receipt id and parent chain pointer

A CANDIDATE (not PROMOTED) model may serve canary traffic at reduced
price, but the response MUST disclose that the model is not promoted.
Serving a CANDIDATE as PROMOTED is a contract violation.

## Payment flow (x402)

1. Client requests `POST /v1/inference` without payment -> worker returns `402` with payment-required headers and the price for the requested model.
2. Client retries with x402 payment header.
3. Worker verifies payment, proxies to the Salad backend (`szl-inference-v3` / llama.cpp llama-server), attaches the passport headers, and emits a settlement receipt.
4. Settlement receipts chain to the passport digest, so revenue is auditable against model history.

## Pricing honesty

Prices are quoted per model revision, not per model name. If the backend
revision changes, the price table and the passport digest change
together. Energy observations from the worker JOULE deltas flow into the
passport cost section, so the price can be grounded in measured cost.

## Endpoints

- `GET /v1/models` - list serving models with their passport digests
- `GET /v1/models/{id}/passport` - full anatomy projection (JSON)
- `GET /v1/models/{id}/promotion` - live promotion decision
- `POST /v1/inference` - x402-gated inference (402 without payment)
- `GET /v1/inference/{receipt_id}/receipt` - settlement receipt

## Deployment

Deploy targets the existing content-addressed worker
`szl-a11oy-governed-inference-f9bd7a86f72e2d2` (or successor).
Requires: Cloudflare API token (dashboard session), upstream URL,
x402 payment facilitator key, and a passport directory (per-tenant
passports served from szl-lake or the anatomy server).
