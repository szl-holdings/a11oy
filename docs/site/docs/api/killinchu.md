# killinchu API

The [killinchu](/flagships/killinchu) drone-intelligence flagship runs as a FastAPI service on
Hugging Face Spaces. Base path: `/api/killinchu`. The OpenAPI schema is served at `/openapi.json`
on the live Space.

> Live base: [`https://szlholdings-killinchu.hf.space/api/killinchu`](https://szlholdings-killinchu.hf.space/api/killinchu/v1/honest)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Liveness |
| GET | `/readyz` | Readiness (drone DB + decoders loaded) |
| GET | `/v1/honest` | Doctrine v11 honesty disclosure (JSON) |
| POST | `/v1/remote-id/decode` | Decode OpenDroneID / ASTM F3411 hex |
| POST | `/v1/ads-b/decode` | Decode ADS-B (single frame or even/odd pair) |
| POST | `/v1/mavlink/parse` | Parse MAVLink v1/v2 frames |
| GET | `/v1/drones/database` | Drone DB (filters: `side`, `group`, `country`, `role`) |
| GET | `/v1/drones/{id}` | Single drone record |
| POST | `/v1/counter-uas/evaluate` | Haversine geofence + 13-axis Λ-gate + receipt |
| GET/POST | `/v1/swarm/topology` | Union-Find swarm component detection |
| GET | `/v1/threats/active` | Active threat board |
| POST | `/v1/receipt/emit` | Emit a Khipu DSSE receipt |
| GET | `/v1/receipt/ledger` | Khipu Merkle ledger |
| GET | `/v1/lambda` | Λ-gate axis definitions |
| GET | `/v1/research` | Sourced research corpus |
| GET | `/v1/samples` | Verified sample test vectors |

**Preserved `vessels` aliases (additive, GREEN baseline untouched):**
`/api/vessels/healthz`, `/api/vessels/v1/killinchu-redirect`.

## Honesty disclosure (`GET /v1/honest`)

```json
{
  "doctrine": "v11",
  "lambda": "Conjecture, not Theorem — decision aid, not proof of safety",
  "dsse_signature": "PLACEHOLDER — Sigstore CI not yet wired; SHA-256 Merkle digest is real",
  "slsa": "L1 (honest)",
  "signal_trust": "Broadcast Remote-ID / ADS-B / civilian MAVLink are unauthenticated and spoofable; each decoded field is a claim, not ground truth",
  "errors": "Malformed input returns an honest error, never a silent pass",
  "corpus": "749 declarations / 14 unique axioms / 163 sorries (v11 LOCKED)"
}
```

## Example requests

```bash
# Honest disclosure
curl -s https://szlholdings-killinchu.hf.space/api/killinchu/v1/honest | jq .

# Decode Remote-ID hex
curl -s -X POST https://szlholdings-killinchu.hf.space/api/killinchu/v1/remote-id/decode \
  -H 'content-type: application/json' -d '{"hex":"0d01..."}'

# Counter-UAS evaluation (geofence + Λ-gate + receipt)
curl -s -X POST https://szlholdings-killinchu.hf.space/api/killinchu/v1/counter-uas/evaluate \
  -H 'content-type: application/json' \
  -d '{"track":{"lat":32.7,"lon":-117.1,"alt_m":120},"geofence":{"center":[32.70,-117.10],"radius_m":500}}'

# Λ-gate axis definitions
curl -s https://szlholdings-killinchu.hf.space/api/killinchu/v1/lambda | jq .
```

## Stack

FastAPI · uvicorn · `pyModeS` v3 · `pymavlink` · React + Vite SPA · MapLibre GL · Docker on HF Spaces.
