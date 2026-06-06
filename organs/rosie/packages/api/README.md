# rosie-api

The execution and observability API behind the **rosie widget** and the **rosie
admin console** (the standalone `SZLHOLDINGS/rosie-operator-console` Gradio
Space).

rosie commands a11oy, which enforces; a11oy delegates to amaru and sentra;
vessels carries the load. rosie-api is the layer that turns an operator question
or command into receipts and, where required, a human-confirmed action.

## What rosie-api is

Two surfaces call this one API:

- the floating **rosie widget** embedded in a11oy / amaru / sentra / vessels
- the standalone **rosie operator console** (its 6 tabs are being migrated from
  in-process logic into these API routes)

It exposes three capability classes:

- **read queries** — receipts, mesh health, doctrine sweep, live formulas
- **ask** — `POST /v1/ask` answers a question and records the Q+A as an audit
  receipt
- **execute** — a two-phase, human-confirmed flow: `POST /v1/execute` returns a
  signed *proposal*; `POST /v1/execute/confirm` performs it after a step-up
  re-auth

## API surface

The full contract is the OpenAPI 3.1 spec: [`openapi.yaml`](./openapi.yaml).
It validates against the 3.1 schema (`npm run lint:openapi`, i.e.
`redocly lint openapi.yaml`).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/health` | Liveness + version + commit SHA + uptime (unauthenticated) |
| POST | `/v1/ask` | Answer a question; record an audit receipt |
| POST | `/v1/execute` | Propose an execution (signed, human-confirmable receipt) |
| POST | `/v1/execute/confirm` | Confirm a proposal (irreversible; requires step-up) |
| GET | `/v1/receipts` | List receipts (paginated) |
| GET | `/v1/receipts/{id}` | One receipt with full DSSE envelope + chain pointers |
| GET | `/v1/receipts/stream` | SSE stream of receipts (30s heartbeat) |
| POST | `/v1/receipts/verify` | Verify a receipt's DSSE signature + chain integrity |
| GET | `/v1/mesh/health` | Per-module health (a11oy + szl-receipts-server + sentra) |
| GET | `/v1/doctrine/sweep` | Doctrine v7 sweep checker |
| GET | `/v1/formulas/live` | Formula moat status from a11oy policy gates |
| GET | `/v1/about` | About metadata |

## Auth model

All endpoints except `/v1/health` are behind **OIDC Bearer** tokens issued by
Keycloak and fronted by the **UDS authservice** — the same Keycloak realm the
`szl-receipts-server` uses. The middleware (`jose`) verifies the JWT against the
realm JWKS and enforces:

- `aud === rosie-api`
- `groups` includes **`szl-operators`** for read endpoints
- `groups` includes **`szl-executors`** for `/v1/execute*`

### Step-up for `/v1/execute/confirm`

The "human-confirm" guarantee is enforced at the auth layer. `/v1/execute/confirm`
additionally requires a **fresh step-up re-authentication**: the JWT must carry a
`step_up_completed_at` claim (ISO-8601 or epoch seconds) **less than 5 minutes
old**. A long-lived bearer token alone therefore cannot confirm an irreversible
action — the operator must re-authenticate immediately before confirming. Stale
or missing step-up returns `403` with an RFC 7807 `application/problem+json` body
(`/errors/step-up-required`, `/errors/step-up-stale`).

This pairs with the proposal model: a proposal expires 5 minutes after creation
(`410 Gone` on confirm after expiry), and confirmation is idempotent on the
supplied `idempotency_key` (repeat → `already_executed`).

## Receipt model

Every write path (ask, propose, confirm) emits a **DSSE envelope** receipt:

- `payload` — base64 of the **canonical-JSON** body (RFC 8785-style: NFC,
  key-sorted, `undefined` dropped, non-finite numbers rejected)
- `payloadType` — `application/vnd.szl.receipt.v1+json`
- `signatures[]` — `{ keyid, sig, alg: "ed25519" }`
- `chain` — `{ prev_hash, index, ts }` (linear SHA-256 hash chain; genesis =
  `"GENESIS"`)

Signatures are computed over the **canonical DSSE v1 PAE** that PhD Crypto
unified (finding A1):

```
PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body      (SP = 0x20)
```

This is vendored in [`src/lib/dsse-pae.ts`](./src/lib/dsse-pae.ts) byte-for-byte
from the canonical `@szl-holdings/a11oy` PAE module — **do not re-invent it**.
The proposal/confirm flow records the proposal and the confirmation as two
separate chain entries.

Signing uses **Ed25519** with a **runtime-loaded** private key (PEM at
`SZL_ED25519_KEY_PATH`), the same pattern as `szl-uds-deployment#19`. No HMAC,
no demo keys, and no key material are committed anywhere in this package
(findings A2 + I). If no key is present the emitter runs in an honest
**unsigned/degraded** mode (it still chains receipts) rather than fabricating a
signature.

## Relationship to the organs

- **a11oy** — owns the receipt substrate. rosie-api emits and verifies receipts
  via `@szl-holdings/a11oy-receipt-substrate` (injected at runtime; see below).
  rosie commands a11oy, a11oy enforces.
- **sentra** — gate verdicts feed the read path and `/v1/mesh/health`.
- **amaru** — memory backs the `/v1/ask` answer engine.
- **vessels** — state is read by `/v1/ask`; vessels carries the deployed load.
- **szl-receipts-server** — the durable receipt backend
  (`RECEIPTS_BACKEND_URL`); aggregated into `/v1/mesh/health`.

## Develop locally

```bash
cd packages/api
npm install

# Type-check, test, coverage.
npm run build           # tsc --noEmit
npm run test            # vitest run
npm run test:coverage   # vitest run --coverage  (threshold: 80% lines/statements)

# Run the server (Node 20+; native TypeScript via --experimental-strip-types).
npm run dev
```

The receipt substrate (`@szl-holdings/a11oy-receipt-substrate`) is not published
yet. We use `import type` for compile-time shapes and **dependency injection**
for the runtime emitter, so the API builds and tests standalone — the same
chicken-and-egg the widget hits. Tests use a local in-memory Ed25519 signer; a
widget/front-end integration would stub the substrate with **MSW**.

No real network is used in tests — every test calls `app.request(...)` against
the Hono app directly. Auth tests mint EdDSA JWTs verified against a locally
injected JWKS.

## Deploy

A Helm chart for **UDS Core** lives in [`chart/`](./chart):

```bash
helm install rosie-api ./chart --namespace rosie
```

It renders:

- **Deployment** — `replicas: 2`, soft pod anti-affinity, requests
  `cpu 100m / mem 256Mi`, non-root, read-only root filesystem, all caps dropped
- **Service** — ClusterIP on port 8080
- **UDS Package CR** — `sso.clientId: rosie-api`, authservice selector, OTLP
  egress to `monitoring/opentelemetry-collector:4317`, ingress allowed only from
  the rosie widget hosts, egress to the receipt backend
- **ServiceMonitor** — Prometheus scrape on `/metrics`
- **PodDisruptionBudget** — `minAvailable: 1`

The container is built by [`Dockerfile`](./Dockerfile) (multi-stage, Node 20
alpine, non-root, `EXPOSE 8080`, `HEALTHCHECK` against `/v1/health`). It runs in
production with **minimal permissions** — only Node's `--experimental-strip-types`
flag, never `--allow-all`.

### Key custody

The Ed25519 signing key and the JWT public-key source are provisioned per the
**key-custody runbook** authored by PhD SecOps (`docs/runbooks/key-custody.md`).
The chart mounts an existing `Secret` (`rosie-api-ed25519`) read-only; it never
creates or embeds key bytes.

## Coordination with the rosie widget

The widget (`packages/widget/`) and this API share types so neither redefines
`Receipt`:

- shared types live in [`src/types/index.ts`](./src/types/index.ts) and export
  `Receipt`, `ExecuteProposal`, `MeshHealth` (as `ModuleHealth` +
  `MeshHealthReport`), and `Verdict`
- the widget imports them via the `@szl-holdings/rosie-api-types` package name
  (this directory is the source; `package.json` maps the `./types` export)
- once `@szl-holdings/a11oy-receipt-substrate` is published, the `Receipt`
  family here should re-export from it (kept structurally identical meanwhile)

## Citation

This package implements the PhD Crypto verdict findings:

- **A1 — canonical DSSE PAE.** Single unified PAE
  (`"DSSEv1" SP LEN SP type SP LEN SP body`) vendored in `src/lib/dsse-pae.ts`;
  signatures are computed over it.
  Source: PhD Crypto / SecOps Verdict (2026-05-30), §A "DSSE envelope + PAE",
  and the DSSE spec
  <https://github.com/secure-systems-lab/dsse/blob/master/protocol.md>.
- **I — key custody.** Asymmetric Ed25519 signing with a runtime-loaded key (no
  committed/HMAC demo keys); custody documented in the key-custody runbook.
  Source: PhD Crypto / SecOps Verdict (2026-05-30), §I "Key management story".
- **E — admission semantics.** The enforcing/human-confirm posture is
  represented here as the step-up gate on `/v1/execute/confirm` (fail-closed on
  missing/stale step-up) and the two-phase confirm.
  Source: PhD Crypto / SecOps Verdict (2026-05-30), §E "Pepr admission semantics".
