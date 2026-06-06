<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SZL Holdings — Λ-Bounty webhook surface · Sign: Yachay <yachay@szlholdings.dev> -->

# Λ-Bounty Webhook Surface

A **working** intake surface for **Conjecture 1** (PURIQ formula **F23** —
Λ-aggregator uniqueness, 9-axis geometric mean). It validates a submission
payload, emits a hash-chained **Khipu intake receipt**, and optionally opens a
GitHub tracking issue.

> **Honesty first.** A webhook receipt acknowledges **intake only**. Eligibility
> for the founder-set award is decided **solely** by the `verify-proof` CI on a
> pull request to this repo. This receiver never declares a winner and never
> moves money. Conjecture 1 is **NOT a theorem**.

## Files

| File | Purpose |
|---|---|
| `submission.schema.json` | JSON Schema (draft 2020-12) for a Conjecture-1 submission payload. |
| `intake.py` | The receiver. FastAPI app (`app`) when fastapi/uvicorn are present; otherwise a zero-dependency stdlib HTTP server. Exposes `handle_submit(payload) -> (http_code, body)`. |
| `../.github/workflows/bounty-webhook.yml` | GitHub-native intake via `repository_dispatch` + `workflow_dispatch`; commits the receipt to `submissions/receipts/`. |
| `../submissions/receipts/intake_ledger.jsonl` | Append-only, hash-chained intake ledger (created on first receipt). |

## Endpoints

| Method | Path | Behaviour |
|---|---|---|
| `GET`  | `/healthz` | Liveness + live Conjecture-1 status block. |
| `POST` | `/api/lambda-bounty/submit` | Validate payload → `200` + receipt (accepted) or `422` + errors (rejected). Either way a receipt is appended. |
| `GET`  | `/api/lambda-bounty/receipts` | The append-only intake ledger as `application/x-ndjson`. |

## Run it

```bash
# Zero-dependency stdlib server (default port 8099)
python3 intake.py

# Or as a FastAPI app (if fastapi + uvicorn installed)
uvicorn intake:app --port 8099
```

```bash
# Health
curl -s localhost:8099/healthz

# Submit (valid example)
curl -s -X POST localhost:8099/api/lambda-bounty/submit \
  -H 'Content-Type: application/json' \
  -d '{
        "submitter": {"name": "Ada Lovelace", "github": "ada"},
        "pr_url": "https://github.com/szl-holdings/lambda-bounty/pull/42",
        "lean_toolchain": "leanprover/lean4:v4.13.0",
        "axiom_print": "propext, Quot.sound, Classical.choice",
        "sorry_free_claim": true,
        "strategy": "induction on axis count, discharge CAUCHY_ND",
        "discharges_cauchy_nd": true
      }'

# Read the ledger
curl -s localhost:8099/api/lambda-bounty/receipts
```

## GitHub-native intake (no server to host)

The workflow accepts an external POST to the `repository_dispatch` API:

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/szl-holdings/lambda-bounty/dispatches \
  -d '{"event_type":"lambda-bounty-submit","client_payload":{
        "submitter":{"name":"Ada Lovelace"},
        "pr_url":"https://github.com/szl-holdings/lambda-bounty/pull/42",
        "lean_toolchain":"leanprover/lean4:v4.13.0",
        "axiom_print":"propext, Quot.sound, Classical.choice",
        "sorry_free_claim":true}}'
```

It can also be triggered manually from the **Actions** tab (`workflow_dispatch`).
Each run validates the payload, appends the receipt, and writes a job summary.

## Validation rules (enforced at intake)

- All `required` fields present (`submitter.name`, `pr_url`, `lean_toolchain`, `axiom_print`, `sorry_free_claim`).
- `pr_url` matches `https://github.com/szl-holdings/lambda-bounty/pull/<n>`.
- `lean_toolchain == leanprover/lean4:v4.13.0` (the pinned toolchain).
- `sorry_free_claim == true` (CI verifies this independently).
- `axiom_print` is rejected at intake if it contains `sorryAx`.

These are *pre-triage* checks. The **authoritative** gate is `verify-proof.yml`:
`lake build` green, no `sorry`/`sorryAx` under `Lambda/`, axioms restricted to
`propext` / `Quot.sound` / `Classical.choice`, no new `axiom` declarations, no
`native_decide` escape hatch.

## Receipt format

Each line of `intake_ledger.jsonl` is a JSON object:

```json
{
  "receipt_type": "lambda_bounty_intake",
  "conjecture": "Conjecture 1 (F23 Λ-aggregator uniqueness)",
  "ts": "2026-06-01T15:07:02Z",
  "submitter": "Ada Lovelace",
  "pr_url": "https://github.com/szl-holdings/lambda-bounty/pull/42",
  "accepted_intake": true,
  "errors": [],
  "eligibility_note": "Intake acknowledgement only. Award eligibility = verify-proof CI green on the PR.",
  "prev": "<hash of previous receipt or 'genesis'>",
  "hash": "<sha256 of the receipt body>",
  "hmac_sha256": "<HMAC-SHA-256 over hash; dev key by default, set LAMBDA_BOUNTY_HMAC_KEY in prod>"
}
```

`prev` chains each receipt to the one before it (Khipu hash chain), so the ledger
is tamper-evident. In production set `LAMBDA_BOUNTY_HMAC_KEY` (and, in the SZL
stack, swap to Ed25519/cosign signing to match the UDS Governance Receipt schema).

*Sign: Yachay <yachay@szlholdings.dev> · Doctrine v12 · Co-Authored-By: Perplexity Computer Agent*
