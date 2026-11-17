# Ouroboros Model Anatomy Passport

One verifiable object per model revision. A11oy does not merely train a
model; it produces a model with a checkable history.

## The artifact

Every model revision receives a content-addressed passport that links
authorization, source data, dataset, training, evaluation, runtime,
cost/energy, settlement, and rollback into one independently verifiable
JSON object. The digest is `sha256` over the canonical JSON of every
field except the digest itself. Parents point to receipt digests, forming
a causal evidence chain: no receipt is rewritten in place.

## Honesty contract

Every claim is labeled with an evidence class:

| Class | Meaning |
|---|---|
| MEASURED | backed by a receipt; source recorded |
| UNKNOWN | not yet measured; blocks promotion |
| ABSTAIN | deliberate non-claim |
| NOT_RUN | scheduled but not executed |
| BLOCKED | attempted and refused |

A passport never claims more than its receipts prove.

## Promotion predicate

The local eligibility predicate requires a valid content digest and exactly one
MEASURED observation with the boolean value `true` for every required term:

eligible = tenant_isolated and source_authorized and provenance_complete
  and transform_chain_verified and license_policy_clear and split_disjoint
  and evaluation_passed and runtime_witnessed and rollback_available

UNKNOWN, ABSTAIN, NOT_RUN, BLOCKED, or MISSING all block promotion.
Absence of evidence can never promote a model. A measured `false`, a non-boolean
value, duplicate required evidence, an invalid digest, or malformed evidence also
blocks eligibility. The supported passport version and nonblank model, tenant,
and revision identities are required. The response includes structural
verification and blocking reasons.

`PROMOTED` is the result of this predicate over the supplied passport. It does not
authorize deployment or establish that a receipt issuer is trusted. The SHA-256
content digest is not a signature: issuer authentication, receipt freshness, and
independent runtime admission remain separate requirements.

## CLI

    python -m ouroboros_passport build training_report.json train.jsonl > p.passport.json
    python -m ouroboros_passport verify p.passport.json
    python -m ouroboros_passport promote p.passport.json
    python -m ouroboros_passport selftest

`verify` exits 0 only for a structurally valid passport; `promote` exits 0 only
for an eligible passport. Both return 1 for a blocked result and still emit JSON.
The selftest and regression fixtures are offline tests, not model qualification.

## Anatomy server (front end + back end)

    python -m ouroboros_passport.serve --dir passports/ --port 8787

Routes: /healthz, /v1/models, /v1/models/{id}/anatomy,
/v1/models/{id}/promotion, /v1/passports/{digest}.
Model IDs may contain a namespace (for example `SZLHOLDINGS/model`), with either
a literal slash or `%2F`. Query strings do not alter route lookup.
Read-only and stateless; the server only projects passports.

## Hugging Face alignment

    python -m ouroboros_passport.hf_bind p.passport.json SZLHOLDINGS/<model>

Uploads passport.json and projects the anatomy into the model card, so
the HF card becomes the public projection of the passport.

## Monetization boundary

Passports are the metering and trust object for paid inference: an x402-
gated Cloudflare worker can bind each paid inference call to the passport
digest of the model revision that served it, making every answer
settleable against a verifiable model history. See
`x402/WORKER_CONTRACT.md` in this repo.
