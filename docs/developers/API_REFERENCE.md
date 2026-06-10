# API Reference

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

All endpoints are HTTPS. Base URLs are the live Hugging Face Spaces. Doctrine v11 · Apache-2.0.
Honest note: some routes are demo/public; commercial usage is metered via API keys issued by the
customer portal. Λ uniqueness is **Conjecture 1 (not a theorem)**; SLSA **L1 (honest)**.

| Organ | Base URL |
|-------|----------|
| a11oy | `https://szlholdings-a11oy.hf.space` |
| killinchu | `https://szlholdings-killinchu.hf.space` |
| rosie | `https://szlholdings-rosie.hf.space` |
| sentra | `https://szlholdings-sentra.hf.space` |
| amaru | `https://szlholdings-amaru.hf.space` |

---

## Common provenance endpoints (a11oy, amaru, killinchu, rosie, sentra)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Liveness + Doctrine v11 numbers (749/14/163, locked `c7c0ba17`). |
| POST | `/khipu/sign` | Sign a JSON `payload` into a DSSE envelope (ECDSA-P256-SHA256). |
| POST | `/khipu/verify` | Verify a DSSE envelope; returns `verified`, `keyid_match`. |
| GET | `/khipu/pubkey` | Public key (PEM) + `fingerprint_sha256` + `keyid`. |
| GET | `/khipu/pubkey.pem` | Raw PEM public key. |
| GET/POST | `/wires/D` | Wire D — W3C traceparent propagation surface. |

### `POST /khipu/sign`
Request:
```json
{ "payload": { "any": "json" } }
```
Response (DSSE):
```json
{
  "payloadType": "application/vnd.szl.khipu+json",
  "payload": "<base64>",
  "signatures": [{ "keyid": "szlholdings-...", "sig": "<base64-ecdsa>" }]
}
```

### `POST /khipu/verify`
Request: the DSSE envelope. Response:
```json
{ "verified": true, "keyid_match": true, "fingerprint_sha256": "a4d73120..." }
```

---

## a11oy — Λ-gate router / substrate

Base: `https://szlholdings-a11oy.hf.space`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Health + doctrine numbers. |
| POST | `/khipu/sign` · POST `/khipu/verify` · GET `/khipu/pubkey` | Receipt signing/verification (see common). |
| GET/POST | `/wires/D` | Wire D traceparent surface. |
| GET | `/api/a11oy/v1/puriq/formulas` | PURIQ formula catalog (master formula + axes). 5 PROVED ({F1,F11,F12,F18,F19}) recompute live with a fresh Khipu receipt chain. |
| GET | `/api/a11oy/v1/puriq/formulas/{id}` | One formula, recomputed live (e.g. `/F1`, `/F11`, `/F12`, `/F18`, `/F19`). |
| POST | `/api/a11oy/v2/unay/recall` | Unay memory recall (semantic lookup over governed memory). |
| GET | `/api/a11oy/v1/mcp/tools` · POST `/api/a11oy/v1/mcp/call` | **Canonical live MCP surface** — JSON tool catalog + tool invocation (currently 4 governed tools: `a11oy_gate`, `lambda_score`, …). |
| GET | `/viz/khipu` · `/viz/doctrine` · `/viz/router` | Live Three.js visualizations. |
| GET | `/mcp/` | Hatun-MCP **landing page** (HTML). The Streamable-HTTP JSON-RPC transport is **roadmap, not live** — see honest note below. |

### MCP — honest live status
The **live, working** MCP surface is `GET /api/a11oy/v1/mcp/tools` (JSON catalog, **4 tools** today) and
`POST /api/a11oy/v1/mcp/call`. The Streamable-HTTP JSON-RPC server at `/mcp/` (the "16-tool Hatun-MCP"
described in [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)) is **NOT yet served as a JSON-RPC transport** —
a `POST /mcp/` `initialize`/`tools/list` returns **HTTP 405** on the deployed Space; `GET /mcp/` serves
an HTML landing page. Use the `/api/a11oy/v1/mcp/*` REST surface until the JSON-RPC transport ships.

---

## killinchu — defense vertical (counter-UAS / drone intelligence)

Base: `https://szlholdings-killinchu.hf.space` · Repo is **private** (defense IP); endpoints below are the public-API contract.

| Method | Path | Superpower |
|--------|------|-----------|
| GET | `/healthz` | Health + doctrine numbers. |
| POST | `/api/killinchu/v2/geofence/check` | Geofence containment check (real nm-distance math). |
| GET | `/api/killinchu/v2/geofence/zones` | List geofence zones (static snapshot — honest label). |
| POST | `/api/killinchu/v2/mission/plan` | Mission plan via PURIQ-F7 + Yuyay-13 gate; returns **signed mission plan**. |
| POST | `/api/killinchu/v2/swarm/coordinate` | Swarm coordination (boids model; SIMULATED positions — honest). |
| POST | `/api/killinchu/v2/mavlink/decode` | MAVLink frame decode (real byte parsing). |
| POST | `/api/killinchu/v2/adsb/decode` | ADS-B decode (real — e.g. ICAO `4840D6`, callsign `KLM1023`). |
| POST | `/api/killinchu/v2/remote-id/decode` | Remote-ID decode. |
| GET | `/api/killinchu/v2/twin/{id}` · `/twin/_all` | Digital twin state (+ tamper tripwires). |
| POST | `/api/killinchu/v2/threat/assess` | Threat assessment. |
| GET | `/api/killinchu/v2/warhacker/missions` | 8 Warhacker mission packs (P1–P8). |
| GET | `/globe` | Cesium globe HUD with live Doctrine v11 chip + `LEGAL_BOUNDARIES`. |

> **Posture:** *"We sense, we evidence; we do not jack into third-party drones."* Drone positions
> are deterministic **SIMULATED** (seeded); geofence is a **static snapshot** — both honestly labeled.

---

## rosie — personal aide / operator console

Base: `https://szlholdings-rosie.hf.space`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Health + doctrine numbers. |
| POST | `/api/rosie/v2/command` | Dispatch one of the **16-command** aide catalog (recall, sign-action, replay, etc.). Routed through the Λ-gate; sub-floor → HTTP 403/`gate_fail`. |
| GET | `/api/rosie/v2/commands` | List the 16-command catalog. |
| POST | `/api/rosie/v2/unay/recall` | Unay memory recall (semantic lookup). *(Root `/unay/recall` is **not** served — 404.)* |
| GET/POST | `/api/rosie/v2/khipu/lmdb/*` | Local Khipu LMDB stats/tail/append (operator-local receipt store). *(Root `/khipu/lmdb/*` is **not** served — 404.)* |
| GET | `/console` | Operator console SPA (verdicts + live receipt stream, Wire C). |

> **MCP on rosie is roadmap, not live:** `/mcp/` returns **404** on the deployed rosie Space.
> The shared MCP REST surface lives on a11oy (`/api/a11oy/v1/mcp/tools`).

> Every `/api/rosie/v2/command` payload is first filtered through **sentra** (`/sentra/rosie/filter`).
> `verdict=block` → HTTP 403 with sentra's reasons; `verdict=allow` → command proceeds.

---

## sentra — cross-cutting immune system

Base: `https://szlholdings-sentra.hf.space`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sentra/healthz` | Health (`{"status":"ok","gates":8,"slsa":"L1 honest …"}`). |
| POST | `/sentra/rosie/filter` | **Immune filter for aide actions** — dual-use + injection detection; returns `verdict` (allow/warn/block), `reasons[]`, `filtered_payload`, and a **DSSE `signed_receipt`** (real Ed25519). This is the canonical always-on dual-use/injection check. |
| POST | `/api/sentra/v1/verdict` | Full immune verdict (Wire B). Real ENFORCING gates today: threat-signature scan + size/DoS guard. Emits a signed receipt. |
| POST | `/api/sentra/v1/verdict/attested` | Verdict + DSSE Ed25519-attested receipt (independently verifiable). |
| POST | `/api/sentra/v1/inspect` | Full-signal inspect (no short-circuit). |
| GET | `/api/sentra/v1/gates` · `/api/sentra/v1/gates/{id}` | List / detail the 8 immune gates (3 enforcing, 5 declarative — honest). |
| GET | `/drone-cyber` · `/dual-use/check` | **HTML console pages** (Three.js UI), *not* JSON APIs. A `POST` returns 405 — the enforcement logic is exposed via `/api/sentra/v1/verdict` + `/sentra/rosie/filter` above. |

> **Honest gate posture:** of the 8 named gates, **gate-01 (threat signature), gate-02 (size guard)**
> are enforcing in the live verdict engine; gates 03–08 are declarative/pass-through today (roadmap).
> Λ-threshold enforcement and a `/section889/screen` allow-deny endpoint are implemented on a branch
> and go live on the next sentra Space rebuild (see operational scorecard).

### `POST /sentra/rosie/filter`
Request:
```json
{ "payload": "<user input or aide-action-context>", "caller": "rosie", "session_id": "abc123" }
```
Response:
```json
{
  "verdict": "allow",
  "reasons": [],
  "filtered_payload": "<original if allowed>",
  "signed_receipt": { "payloadType": "...", "payload": "<b64>", "signatures": [ ... ] }
}
```
Injection signatures detected include `</system>`, `ignore previous`, and common jailbreak patterns.

---

## amaru — memory cortex

Base: `https://szlholdings-amaru.hf.space`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Health + doctrine numbers. |
| GET | `/api/amaru/khipu/ledger` | Khipu receipt ledger (the DSSE-wrapped memory-write chain). *(There is no `POST /v1/ledger`.)* |
| GET | `/api/amaru/v1/khipu/dag` · `/api/amaru/v1/khipu/{hash}` | Khipu DAG / single-receipt lookup. |
| POST | `/khipu/sign` · `/api/amaru/khipu/sign` · POST `/khipu/verify` · GET `/khipu/pubkey` | Receipt signing/verification (see common). |
| GET | `/api/amaru/v1/mcp/tools` · POST `/api/amaru/v1/mcp/call` | MCP REST surface (shared substrate). |

---

## Errors

Standard HTTP semantics: `200` success, `400` malformed request, `403` blocked by sentra (body
includes `reasons`), `404` unknown route, `429` quota exceeded, `5xx` server error. All governed
responses are accompanied by a signed receipt where applicable.

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
