# SZL Warhacker Meta-Bundle — v0.4.0

> "It'd be awesome to see a running deployment of what you've built."
> — Andrew Greene, Defense Unicorns (Option A endorsement)

A single UDS bundle that brings up the SZL governed-AI substrate on a local k3d
cluster (`szl-warhacker`) for the **Warhacker 2026** demo (San Diego, June 16–19).

This bundle follows **Doctrine V7 §10**: *every claim cites verifiable evidence; no
"ready" without HTTP 200.* Read the **Artifact status** table before demoing — it is
the difference between an honest live demo and a slideware claim.

---

## What actually deploys today

`uds run start` brings up, in order:

1. **Zarf init** — `ghcr.io/defenseunicorns/packages/init:v0.77.0` ✅ available
2. **uds-core slim-dev** — `ghcr.io/defenseunicorns/packages/uds/core:0.34.0-slim-dev` ✅ available (Istio + Pepr + Keycloak-lite + Prometheus)
3. **szl-receipts** — local Zarf package: Pepr admission webhook + DSSE receipt server ✅ available (Apache-2.0)
4. **vessels-uds** — maritime UI, port 7863 ⚠️ signed package exists, but **gated on FA-001** (founder must push the vessels image to GHCR). Shipped as an `optionalComponent`.

## What is referenced but STAGED (not deployable)

The four modules below publish **only SBOM JSON** at their `uds-v0.3.0` releases —
no signed Zarf package, no image, no `zarf.yaml`. They are documented in
`uds-bundle.yaml` as the target topology and are **commented out** so `uds run
start` neither fails nor misrepresents them as working:

| Module | Role | Port | Blocker |
|---|---|---|---|
| amaru-uds | memory cortex | 7860 | no signed package + FA-001 |
| a11oy-uds | orchestration mediator | 8080 | no signed package + FA-001 |
| sentra-uds | security gates | 7861 | no signed package + FA-001 |
| rosie-uds | operator console | 7862 | no signed package + FA-001 |

**Target topology (when live):** all four discover a11oy via Kubernetes service DNS
at `a11oy.szl-platform.svc.cluster.local:8080` and register gate-results to it;
a11oy is the orchestration mediator.

### Artifact status (verified 2026-05-30)

| Module | `uds-v0.3.0` assets | Signed Zarf pkg | Deployable now |
|---|---|---|---|
| vessels | `vessels-uds-0.3.0.tar.zst` + `.sig` + `.sigstore.json` | ✅ | ⚠️ after FA-001 |
| amaru | SBOM only | ❌ | ❌ STAGED |
| a11oy | SBOM only | ❌ | ❌ STAGED |
| sentra | SBOM only | ❌ | ❌ STAGED |
| rosie | SBOM only | ❌ | ❌ STAGED |

> The szl-receipts **bundle artifact** is not cosign-signed yet (Phase 2, org key
> U5). `cosign verify` on the bundle will fail until then. Receipts themselves are
> HMAC-SHA-256 signed in demo mode (Ed25519 in production).

---

## Prerequisites

`docker` 24+, `k3d` 5.6+, `zarf` 0.77+, `uds` (uds-cli), `kubectl` 1.29+, `jq`, `curl`.
Verify: `for t in docker k3d zarf uds kubectl jq curl; do command -v $t || echo "MISSING $t"; done`

## Run it

```bash
cd bundles/szl-warhacker
uds run start          # cluster + init + uds-core slim-dev + szl-receipts (+ vessels if FA-001 done)
uds run verify         # Doctrine §10 evidence: pod health + HTTP 200 on /health
uds run demo:scenario  # apply a workload, watch a DSSE receipt fire (mirrors docs/WARHACKER_DEMO.md)
uds run cleanup        # delete the szl-warhacker cluster
```

The 5-minute live talk track is **`docs/WARHACKER_DEMO.md`** — this bundle is built to
serve exactly that flow (uds-core + szl-receipts; modules light up as their packages ship).

## To make all five modules literally boot together

1. **FA-001** — push each module image to `ghcr.io/szl-holdings/<module>`.
2. Author a `zarf.yaml` + build a Zarf package for amaru/a11oy/sentra/rosie (none exist today).
3. `zarf package publish` each signed package to `ghcr.io/szl-holdings/<module>-uds`.
4. Uncomment the matching package block in `uds-bundle.yaml`, then `uds run start` + `uds run verify`.

## Licensing

szl-receipts (Pepr policy + receipt server) is **Apache-2.0** — the contribution offer
to Defense Unicorns. It runs as a separate add-on; no AGPL entanglement with uds-core.
