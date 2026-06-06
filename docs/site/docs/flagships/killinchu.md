# killinchu — drone intelligence

<div class="quechua">
<strong>Etymology.</strong> Quechua <strong><em>killinchu</em></strong> = <strong>kestrel</strong>,
a small Andean falcon — a precise hunter that hovers, watches, and strikes only when the
target is resolved. Gloss: <a href="https://kaikki.org/eswiktionary/">kaikki.org Quechua</a>.
</div>

## Overview

`killinchu` 🦅 is the SZL **drone-intelligence flagship**: a formally-governed **counter-UAS
rule engine** with **Λ-gate governance**, **DSSE Khipu receipts**, and **real protocol
ingest**. It is the SZL counter-UAS rule engine for the governance substrate.

**Anatomy mapping:** killinchu is the **embodied bridge organ** — the
[Killinchu-bridge](/anatomy/#killinchu-bridge) — that extends digital governance to
physical-space actuation (see sub-formula [SF-12](/doctrine/puriq#sf-12)).

## Real protocol decoders (no mocks)

| Protocol | Decoder | Standard |
|----------|---------|----------|
| **Remote ID** | OpenDroneID / ASTM F3411-22a 25-byte parser (Basic ID, Location/Vector, Self ID, System, Operator ID) | ASTM F3411 |
| **ADS-B** | Mode-S 1090ES (DF17) via `pyModeS` v3, incl. CPR even/odd global position | RTCA DO-260B |
| **MAVLink** | v1/v2 frame parsing via `pymavlink` (HEARTBEAT and beyond) | MAVLink |

- **Drone database** — 53 systems across allied, dual-use, adversary, and counter-UAS
  categories, organized by US DoD UAS Groups 1–5, each with telemetry surfaces, specs, and
  sourced notes.
- **Counter-UAS Λ-gate** — a **haversine** geofence breach check fused with a
  [13-axis `yuyay_v3`](/doctrine/v11-v12) governance score (Λ); decisions emit a DSSE Khipu
  receipt anchored in an in-memory Merkle DAG (real SHA-256).
- **Swarm topology** — **Union-Find** connected-component detection over proximity graphs to
  flag coordinated swarms.

## Honesty disclosure (Doctrine v11)

`GET /api/killinchu/v1/honest` returns this disclosure as JSON:

- **Λ is a Conjecture, not a Theorem.** The 13-axis governance score is a decision aid, not a proof of safety.
- **DSSE receipt signatures are `PLACEHOLDER`** — Sigstore CI signing is not yet wired. Receipts carry a real SHA-256 Merkle digest but an unsigned envelope. **SLSA L1 honest.**
- **Broadcast Remote ID, ADS-B, and civilian MAVLink are unauthenticated and spoofable.** Every decoded field is a *claim*, not ground truth. Malformed input returns an honest error, never a silent pass.
- Formal corpus at v11 lock: <span class="locked">749 declarations</span> / <span class="locked">14 unique axioms</span> / <span class="locked">163 sorries</span>.

## API

Base: `/api/killinchu`. See the [full API reference](/api/killinchu) for request/response shapes.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` · `/readyz` | Liveness / readiness |
| GET | `/v1/honest` | Doctrine v11 honesty disclosure |
| POST | `/v1/remote-id/decode` | Decode OpenDroneID / ASTM F3411 hex |
| POST | `/v1/ads-b/decode` | Decode ADS-B (single frame or even/odd pair) |
| POST | `/v1/mavlink/parse` | Parse MAVLink v1/v2 frames |
| GET | `/v1/drones/database` · `/v1/drones/{id}` | Drone DB (filters: side, group, country, role) |
| POST | `/v1/counter-uas/evaluate` | Geofence + 13-axis Λ-gate + receipt |
| GET/POST | `/v1/swarm/topology` | Union-Find swarm component detection |
| GET | `/v1/threats/active` | Active threat board |
| POST | `/v1/receipt/emit` · GET `/v1/receipt/ledger` | Emit / read Khipu DSSE receipts |
| GET | `/v1/lambda` | Λ-gate axis definitions |
| GET | `/v1/research` · `/v1/samples` | Sourced research corpus / verified test vectors |

## Example — decode + evaluate

```bash
# Honest disclosure
curl -s https://szlholdings-killinchu.hf.space/api/killinchu/v1/honest | jq .

# Decode a Remote-ID broadcast
curl -s -X POST https://szlholdings-killinchu.hf.space/api/killinchu/v1/remote-id/decode \
  -H 'content-type: application/json' -d '{"hex":"0d01..."}' | jq .

# Geofence + 13-axis Λ-gate + receipt
curl -s -X POST https://szlholdings-killinchu.hf.space/api/killinchu/v1/counter-uas/evaluate \
  -H 'content-type: application/json' \
  -d '{"track":{"lat":...,"lon":...},"geofence":{"center":[...],"radius_m":500}}' | jq .
```

## Stack

FastAPI · uvicorn · `pyModeS` v3 · `pymavlink` · React + Vite SPA (wouter) ·
MapLibre GL (OpenFreeMap tokenless tiles) · Docker on Hugging Face Spaces.

## Source & evidence

- **Repo:** [github.com/szl-holdings/killinchu](https://github.com/szl-holdings/killinchu)
- **Live Space:** [szlholdings-killinchu.hf.space](https://szlholdings-killinchu.hf.space)
- **License:** Apache-2.0 · Doctrine v11 · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
- **Legal boundaries:** counter-UAS engagement guidance is decision-support only; see the repo's `LEGAL_BOUNDARIES.md`.
