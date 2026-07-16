---
title: SZL Immune
emoji: "🛡️"
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Deterministic-first inspection with fail-closed tool authority and DSSE receipts
---

# SZL Immune v0.1

SZL Immune is a source-backed inspection boundary for prompts, retrieved passages,
memory records, tool responses, and proposed tool actions. It does not claim that a
classifier exists when weights are absent. It does not let a public demo mutate global
state. It does not authorize a tool without both a qualified, immutable-pinned local
classifier and a real Ed25519-signed receipt.

## Decision order

1. Parse a fixed request schema and apply bounded canonicalization.
2. Evaluate source trust, actor identity, Unicode changes, secret/shell/role/encoding,
   egress, and capability rules.
3. Run HUKLLA tripwires, explicitly reporting `NOT_IMPLEMENTED` where evidence is absent.
4. Invoke the local classifier adapter only after deterministic controls pass.
5. Apply highest-risk-wins policy.
6. Hash the input and action, then append a DSSE/Ed25519 receipt when a signer exists.
7. Permit tool execution only after a qualified classifier and signed receipt exist.

Receipt appends are serialized and use an explicit file-descriptor
`open → write → fsync → close` sequence. Public request counters reset every 60 seconds;
the independent session TTL remains 30 minutes and both timestamps are exposed by the
session-state contract.

The current repository contains no model weights. The default classifier target is a
third-party baseline identifier only; it remains `UNAVAILABLE` until all of these are
supplied and verified locally:

- exact 40-character immutable model revision;
- SHA-256 hashes and local paths for weights and tokenizer;
- local adapter implementation;
- runtime and device identity;
- an Ed25519-signed qualification receipt whose key ID is explicitly allowed through
  `IMMUNE_QUALIFICATION_KEYID`.

## API

| Method | Endpoint | Contract |
|---|---|---|
| `GET` | `/api/immune/v1/status` | Service, policy, classifier, signer, and chain evidence |
| `POST` | `/api/immune/v1/inspect` | Deterministic-first input inspection |
| `POST` | `/api/immune/v1/tool-authorize` | Fail-closed tool authorization |
| `GET` | `/api/immune/v1/receipts/{receiptId}` | DSSE envelope and public receipt payload |
| `GET` | `/api/immune/v1/tripwires` | Implemented and unimplemented HUKLLA tripwires |
| `GET/POST` | `/api/immune/v1/session/state` | Session-scoped demo state only |
| `GET` | `/openapi.json` | OpenAPI 3.1 contract |

Legacy `POST /api/immune/state` and reset/global ledger mutation are denied. The legacy
`GET /api/immune/state` response is derived from the caller's session and never exposes a
global mutable mode.

## Run and verify

Requires Node 20 or newer; there are no runtime package dependencies.

```bash
npm run contracts:check
npm test
npm start
```

To enable signed receipts, place a base64 Ed25519 PKCS#8 private key (or 32-byte seed) in
the approved secret store as `IMMUNE_SIGNING_KEY`. Never commit it. Runtime receipts are
written to `data/immune/v1-receipts.jsonl` or `IMMUNE_LEDGER_PATH`. Signer and
qualification key IDs are full 64-character SHA-256 digests of their SPKI public keys.

## Prior art boundary

The design is informed by defense-in-depth work including CaMeL, AgentDojo, NeMo
Guardrails, garak, PyRIT, and OWASP guidance. Those projects are references, not evidence
that this implementation inherits their measurements or endorsements. SZL-specific claims
remain limited to tests and receipts emitted by this source tree.

Apache-2.0 · SZL Holdings · fail closed · no fabricated green states
