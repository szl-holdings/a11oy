# Frontier cut — 2026-09-11

Product: https://a-11-oy.com
Proof: https://a11oy.net

## Signer truth (MEASURED)

Lean `/healthz` signer is ABSENT **on that probe** — it does not mint.
Live DSSE is REAL:

- Rollup: `GET /api/a11oy/healthz` → `rollup.signer.status = DSSE-LIVE`
- Status: `GET /api/a11oy/v1/signing-status` → REAL ECDSA-P256
- Credential: `GET /api/a11oy/v1/assurance/credential` → signing_available true
- Mint: `POST /api/a11oy/khipu/sign` → `signed: true`
- Pubkey: https://a-11-oy.com/cosign.pub
- Fingerprint: `9926bf69b799ea663fc5cf5a8c5d8f594d99d7b323700d6a20b803bd4c9f4e15`

Do not use `GET /api/a11oy/v1/ledger` as the receipt UI. It is a separate empty process store (count 0, mint false).
Use `GET /api/a11oy/khipu/ledger` and lake `GET /api/lake/v1/receipts`.

`GET /api/a11oy/v1/khipu/verify/{digest}` still prints DSSE_PLACEHOLDER. That route is stale. Verify against `/cosign.pub`.

## Gated path (MEASURED this session)

`POST /api/a11oy/v1/agent/loop`
- ALLOW at λ 0.91 — digest issued
- HALT H1 at λ 0.05

Khipu lab READY: https://szlholdings-szl-model-inference-lab.hf.space/v1/models
GPU inference remains ROADMAP. CPU lab is enough for the gate demo.

## Killinchu

Sensing LIVE. Effector SIMULATED. Do not arm the public effector.

## Estate

Two origins only. Forge is not a runtime flagship. Hub Spaces 16 API / 17 UI. Atlas 48 is stale.

## Mint this session

- `POST /api/a11oy/v1/be/khipu/append` → sqlite seq 0
- `POST /api/a11oy/khipu/sign` → digest `7120bbe1c30166ab5ac63043594afd31ecdc748589ff47efd2a1f17b41e1c9a9` signed true
- Khipu ledger count 2 after the cut
