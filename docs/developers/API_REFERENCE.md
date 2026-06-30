# API Reference

All endpoints are HTTPS. Base URLs are the live Hugging Face Spaces. Doctrine v11 · Apache-2.0.
Honest note: some routes are demo/public; commercial usage is metered via API keys issued by the
customer portal. Λ uniqueness is **Conjecture 1 (not a theorem)**; SLSA **L1 (honest)**.

Two products ship live today; their Spaces are deployed and return `/healthz`:

| Product | Base URL | Status |
|---------|----------|--------|
| a11oy | `https://szlholdings-a11oy.hf.space` | **Live** |
| killinchu | `https://szlholdings-killinchu.hf.space` | **Live** |

> The Provenance Anchor, Operator, and Policy roles (internal codenames *amaru*, *rosie*,
> *sentra* — retired) are **roadmap**: the Spaces `szlholdings-amaru/rosie/sentra.hf.space`
> are **not deployed** (HTTP 404) and the standalone repos do not exist yet. The live policy
> gate, memory ledger, and receipt DAG ship **inside a11oy** today (see below). The roadmap
> route shapes are listed at the end for forward reference only — do not call them as live.

---

## Common provenance endpoints (a11oy, killinchu)

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
| GET | `/api/a11oy/v1/puriq/formulas` | PURIQ formula catalog (master formula + axes). 8 PROVED ({F1,F4,F7,F11,F12,F18,F19,F22}) recompute live with a fresh Khipu receipt chain. |
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
> are deterministic **SIMULATED** (seeded); geofence is a **static snapshot**; the effector path
> is a **command demonstration, simulated** — all honestly labeled.

---

## a11oy frontier endpoints (PINN · E8 · specdec · materials · evidence-pack · conformal)

Base: `https://a-11-oy.com` · live a11oy Space. These shipped 2026-06-28+ and are governed by
the same doctrine: **8 locked-proven** {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel `c7c0ba17`;
**Λ = Conjecture 1** (advisory, capped ≤ 0.99, never a theorem); values **MODELED** unless
MEASURED; every action emits a SHA3-256 Khipu receipt (honestly `signed` or `DSSE_PLACEHOLDER`).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/a11oy/v1/govern/infer` | Governed inference: model routing + Λ-gate + split-conformal block + signed receipt. |
| POST | `/api/a11oy/v1/pinn/identify` | Inverse-PINN identification (demos `duffing`, `calphad`; `case:ill_posed` ⇒ RED). Self-doubt gate refuses non-identifiable params. |
| GET | `/api/a11oy/v1/pinn/health` | PINN organ liveness; `supported_systems: [duffing, redlich_kister]`. |
| GET/POST | `/api/a11oy/v1/e8/verify` | E8-lattice encoding of a 256-bit digest → nearest lattice point. **Error-detection geometry only.** |
| GET | `/api/a11oy/v1/specdec/health` | Speculative-decoding readiness (same-family draft+target probe). |
| POST | `/api/a11oy/v1/specdec/run` | Spec-decode run; honest **`SPEC-DECODE ROADMAP`** + `measured:UNAVAILABLE` when no same-family pair. |
| POST | `/api/a11oy/v1/materials/novelty` | Crystal-novelty via isometry-invariant PDD fingerprint + chained receipt. |
| POST | `/api/a11oy/v1/materials/certify` | PAC-Bayes (McAllester 1999) certified risk bound + receipt. |
| GET | `/api/a11oy/v1/assurance/evidence-pack` | Offline-verifiable auditor pack with `pack_sha3_256` self-digest. |
| GET | `/api/lake/v1/health` | szl-lake receipt ledger health; per-organ `chain_head`. |

### `POST /govern/infer`
Request: `{ "prompt": "..." }`. Returns `decision` (`allow`/`block`), `answer`, `governance`
(Λ advisory + named gates), a `conformal` coverage block (split-conformal, Vovk 1999 /
Angelopoulos & Bates 2021; label `CP-90 SAMPLE`), and the doctrine block. The router policy is
`sensitivity-first → license(GREEN) → smallest-tier → max-ctx`.

### `POST /pinn/identify`
Request: `{ "demo": "duffing" | "calphad", "case"?: "ill_posed" }`. Returns `convergence.label`
(`GREEN`/`RED`), `discovered[]` (each with `value`, `ci95`, `fisher_information`, `identifiable`,
`label:"MODELED"`, F19 Bekenstein plausibility), and a `lambda_advisory` (capped ≤ 0.99). The
self-doubt gate marks any parameter with Fisher `< 1e-08` or `κ(FIM) ≥ 1e+08` as
**RED/UNIDENTIFIABLE** and does **not** assert it. CALPHAD recovers Redlich-Kister L0/L1/L2.

### `GET/POST /e8/verify`
POST `{ "digest": "<64-hex sha3_256>" }` (GET verifies a live ledger head). Returns the 8 ×
32-bit `coords`, `nearest_lattice_point`, `min_squared_distance` (0 ⇒ on-lattice), and an
`error_detection` block. **Honest:** E8 optimality is **Viazovska (2017, *Annals* 185:991–1015)**,
formalized in Lean (EPFL) — **cited, not produced here**. Error-DETECTION geometry only; **NOT**
adversarial-substitution resistance, collision resistance, or BFT safety; adds **0** to locked-8.

### `GET /specdec/health` · `POST /specdec/run`
Leviathan et al. 2023 (arXiv:2211.17192), **reimplemented from the public paper**. Lossless
spec-decode needs a draft+target sharing one tokenizer. When no same-family pair is reachable the
run returns `label:"SPEC-DECODE ROADMAP"`, `measured:"UNAVAILABLE"`, `quality_delta:"UNAVAILABLE"`
and a clearly-labelled `accounting_modeled` curve — **no faked speedup**.

### `POST /materials/novelty` · `POST /materials/certify`
There is **no** `/materials/predict`. **novelty**: POST a crystal
`{a,b,c,alpha,beta,gamma,sites:[{el,x,y,z}]}`; returns `novel`, a Kurlin-style PDD
`fingerprint`/`fingerprint_digest`, and a receipt. Fingerprint comparison is **REAL**;
injectivity is **Conjecture 2 — ROADMAP, NOT proven** (`Lutar/Materials/PDDInjective.lean`).
**certify**: POST `{empirical_risk,kl,n,delta}` or `{family}` (`intermetallics`/`oxides`/
`refractory_hea`); returns the McAllester bound `R(Q) ≤ R̂(Q) + sqrt((KL+ln(2√n/δ))/(2n))`.
Formula **proven on paper**, computation **exact**; **Lean proof is an open SORRY/ROADMAP**
(`Lutar/Materials/PACBayesMaterials.lean`) — not in locked-8. Presets are `SAMPLE/MODELED`.

### `GET /assurance/evidence-pack`
Returns an envelope `{pack, pack_sha3_256, digest_alg:"sha3_256", digest_canonicalization,
offline_verify, signature}`. The `pack` bundles the assurance matrix, Khipu organ chain heads,
lake health, doctrine block, and cosign public key. Recompute `sha3_256` over the canonicalised
`pack` to verify offline (zero round-trip). `signature.signed:false` /`DSSE_PLACEHOLDER` when no
runtime signing key — **honest-unsigned**; the self-digest is always recomputable.

### Conformal prediction (cross-cutting)
`/govern/infer` (and forecast/RAG surfaces) embed a **split-conformal** block: calibration split,
nonconformity score `|Λ−y|`, finite-sample quantile `q̂`, and a prediction interval with
**marginal coverage ≥ 1−α** (distribution-free, under exchangeability). NOT Hoeffding, NOT a
Bayesian posterior, NOT conditional coverage. Refs: Vovk 1999; Angelopoulos & Bates 2021
(arXiv:2107.07511). Labelled `CP-90 SAMPLE` until `n_real ≥ 500` real outcomes upgrade it to
MEASURED.


---

## a11oy governance, provenance & lake endpoints

Live endpoints newly surfaced (all verified `200` at `https://a-11-oy.com`, 2026-06-30). Base: `https://a-11-oy.com` (same as `https://szlholdings-a11oy.hf.space`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/a11oy/v1/honest` | Full doctrine status: `doctrine_lock` (v11, 749/14/163, `c7c0ba17`), 8 locked-proven IDs, Λ advisory, persistence note. The canonical machine-readable "what we claim" endpoint. |
| GET | `/api/a11oy/v1/signing-status` | Receipt signing posture: `key_source` (`ephemeral` or `persistent`), `dsse_keyid`, `hmac_layer` status, `non_repudiation` flag, honest note. Set `A11OY_RECEIPT_KEY_PATH` + `A11OY_HMAC_KEY` as Space secrets for persistent non-repudiation. |
| GET | `/api/a11oy/v1/frontier/manifest` | Live roll-up of all 8 frontier capabilities as tiles, each with `MEASURED`/`MODELED`/`ROADMAP`/`SAMPLE`/`UNAVAILABLE` label. Includes `universal_verifier` address, `labels_legend`, `summary` (`tiles:8`, `label_counts`), and a per-capability `capabilities[]` array. |
| GET | `/api/a11oy/v1/energy/ledger` | Hash-chained NVML joule receipt chain. Returns `chain_length`, `links_intact`, `persistence` note. `chain_length:0` is correct when no sovereign GPU job ran this process — honest, not an error. |
| GET | `/api/a11oy/v1/energy/sci` | Software Carbon Intensity score (GSF SCI / ISO 21031:2024). Returns `label` (`UNAVAILABLE` when no NVML), `sci_score_gco2_per_call`, `grid_intensity_gco2_per_kwh` (MODELED, EPA eGRID 2023 default; set `ELECTRICITY_MAPS_API_KEY` for MEASURED), and `meter_reachable` flag. Energy never fabricated. |
| GET | `/api/a11oy/v1/verify/intoto` | In-toto verification guide: describes how to verify a Khipu receipt as an in-toto Statement, with `fetch_endpoint` pointer to `/khipu/intoto/<receipt_id>`. |
| GET | `/khipu/intoto/{receipt_id}` | Fetch a receipt by ID as an in-toto Statement v1 envelope. Returns `404` for unknown IDs (correct — honest). Use a real `receipt_id` from `/api/a11oy/v1/ledger`. |
| GET | `/api/lake/v1/log` | szl-lake Merkle log head: `log_id`, `tree_size`, `root_hash`, `honest_label` (`"self-hosted SZL Merkle log; NOT Sigstore Rekor"`), `seed_count`. Recompute `root_hash` offline to verify integrity. |

### `GET /api/a11oy/v1/honest` — example response (abbreviated)
```json
{
  "doctrine_lock": {
    "doctrine": "v11", "state": "LOCKED",
    "declarations": 749, "axioms": 14, "sorries": 163,
    "commit": "c7c0ba17", "lambda": "Conjecture 1",
    "locked_formula_count": 8,
    "locked_formula_ids": ["F1","F4","F7","F11","F12","F18","F19","F22"]
  },
  "honest_labels": { "persistence": "Khipu receipts persist via backend=sqlite (durable=True)" }
}
```

### `GET /api/a11oy/v1/signing-status` — example response
```json
{
  "key_source": "ephemeral",
  "key_persistent": false,
  "dsse_keyid": "dc4ddfdb0969ef86",
  "hmac_layer": "placeholder",
  "non_repudiation": false,
  "doctrine": "v11",
  "honesty": "PARTIAL -- ECDSA-P256 key is ephemeral; HMAC layer is placeholder. Set A11OY_RECEIPT_KEY_PATH/DIR and A11OY_HMAC_KEY as HF Space secrets for full non-repudiation."
}
```

### `GET /api/lake/v1/log` — example response
```json
{
  "log_id": "szl-lake-merkle-v1",
  "tree_size": 5,
  "root_hash": "01077a19a40ea1ca19c50533308aba6fb089c824bd6615ba9a39563f58825883",
  "honest_label": "self-hosted SZL Merkle log; NOT Sigstore Rekor",
  "seed_count": 0
}
```

**Honesty note on `/api/lake/v1/log`:** `tree_size` reflects the in-process Merkle log state; the persistent
`szl-lake` HF dataset receipt chain may lag (see szl-lake sync gap in FRONTIER_VISION). Both sources are
independently verifiable — recompute `root_hash` offline over the leaf list.


---

## Errors

Standard HTTP semantics: `200` success, `400` malformed request, `403` blocked by policy gate (body
includes `reasons`), `404` unknown route, `429` quota exceeded, `5xx` server error. All governed
responses are accompanied by a signed receipt where applicable.

---

## Roadmap roles — NOT yet served (forward reference only)

The following route shapes describe roadmap roles. **Their Spaces are not deployed** —
`szlholdings-amaru/rosie/sentra.hf.space` return HTTP 404 today. The live equivalents ship
inside a11oy. Do not call these as live endpoints; they are documented so the eventual public
contract is stable.

- **Provenance Anchor** *(internal codename amaru, retired)* — memory cortex / Khipu receipt
  ledger + DAG. Live equivalent today: a11oy `/khipu/*` and the governed memory under
  `/api/a11oy/v2/unay/recall`.
- **Operator** *(internal codename rosie, retired)* — aide / operator console, 16-command
  catalog, operator-local Khipu LMDB store, Wire-C receipt stream. Roadmap.
- **Policy** *(internal codename sentra, retired)* — cross-cutting immune system: dual-use +
  injection filter, verdict/inspect engine, 8 named gates. Live equivalent today: the policy
  gate enforced inside a11oy's Λ-gate router.

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*

*Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com> (DCO) — Dev D wiring pass 2026-06-30*
