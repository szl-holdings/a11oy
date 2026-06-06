# UDS Catalog-Grade — SZL Receipts v0.3.1

**PR target:** `szl-holdings/szl-uds-deployment`  
**Branch:** `feat/uds-catalog-grade-0.3.1`  
**Audit session:** 2026-05-29 evening  
**Doctrine:** v6 strict — no fake catalog acceptance, no fake signed assets, honest STAGED labels  
**Andrew Greene Option A endorsement:** 2026-05-22 — authorizes UDS licensing compliance work

---

## What this PR adds

This PR adds catalog-grade Kubernetes artifacts to `szl-uds-deployment`, elevating the v0.1.0 Warhacker demo to meet UDS catalog requirements per the Option A directive.

| File | Purpose |
|---|---|
| `charts/szl-receipts/templates/uds-package.yaml` | UDS Package CR (SSO + Istio expose + network allow) |
| `charts/szl-receipts/templates/networkpolicy.yaml` | Kubernetes NetworkPolicy (deny-all + explicit allows) |
| `charts/szl-receipts/templates/servicemonitor.yaml` | Prometheus ServiceMonitor (30s scrape, honest metrics) |
| `charts/szl-receipts/templates/podsecuritystandard.yaml` | PSS restricted, PDB, ResourceQuota, LimitRange |
| `uds-bundle.yaml` | Updated bundle v0.3.1 (init v0.40.0 + core-slim-dev 0.34.0) |
| `tasks.yaml` | `demo:start`, `demo:verify`, `demo:reset` UDS tasks |
| `tests/uds-package-validation.sh` | Validation script (YAML, helm lint, kubectl dry-run) |

---

## Dependencies

### Required (deploy will fail without these)

| Dependency | Version | Source |
|---|---|---|
| `uds` CLI | >= 0.16.0 | [github.com/defenseunicorns/uds-cli](https://github.com/defenseunicorns/uds-cli/releases) |
| `zarf` CLI | >= 0.43.0 | [github.com/zarf-dev/zarf](https://github.com/zarf-dev/zarf/releases) |
| `k3d` | >= 5.7.0 | [k3d.io](https://k3d.io) |
| Docker | any recent | For k3d cluster |
| `kubectl` | >= 1.28 | For verification tasks |
| `helm` | >= 3.14 | For lint and render |

### Install all deps with one command

```bash
uds run install-deps
```

### UDS Core prerequisite (STAGED — see below)

`core-slim-dev 0.34.0-slim-dev` must be deployed before the UDS Package CR is reconciled. The bundle handles this in the correct layer order (init → core-slim-dev → szl-receipts), but manual deploys must follow this order.

---

## How to deploy

### Full demo bootstrap (recommended)

```bash
# From repo root:
uds run demo:start
```

This runs in ≈90 seconds on a modern laptop and does:
1. Checks for required tools
2. Creates k3d cluster `uds-szl-demo`
3. Builds the szl-receipts Zarf package
4. Creates the UDS bundle
5. Deploys: `init` → `core-slim-dev` → `szl-receipts`
6. Port-forwards receipts-server to `localhost:8443`
7. Verifies the health endpoint

### Manual deploy sequence

```bash
# 1. Create cluster
k3d cluster create uds-szl-demo \
  --k3s-arg "--disable=traefik@server:0" \
  --port "443:443@loadbalancer"

# 2. Build
zarf package create . --set DOMAIN=uds.dev --confirm
uds create . --confirm

# 3. Deploy
uds deploy uds-bundle-szl-receipts-bundle-amd64-0.3.1.tar.zst \
  --set DOMAIN=uds.dev \
  --set INSECURE_ADMIN_PASSWORD_GENERATION=true \
  --confirm
```

---

## Verification steps

### Quick verify (all-in-one)

```bash
uds run demo:verify
```

Expected output with no workloads:
```
Fetching receipts from http://localhost:8443/receipts ...
Found 0 receipt(s).
No receipts to verify. Deploy a workload first.
UDS Package CR status: Ready   ← only if core-slim-dev is deployed
```

### After deploying a workload

```bash
kubectl apply -f scripts/demo_workload.yaml
sleep 5
uds run demo:verify
```

Expected:
```
  PASS  a3f2b1c4…  2026-06-16T14:23:01Z  subject=szl-demo-workload/Deployment/szl-demo-agent
  PASS  b2c3d4e5…  2026-06-16T14:23:02Z  subject=szl-demo-workload/Job/szl-demo-job

Summary: 2 VERIFIED, 0 FAILED out of 2 receipt(s)
Ledger check: PASS — 2 receipts, no sequence gaps.
UDS Package CR status: Ready
```

### Validation (pre-PR)

```bash
bash tests/uds-package-validation.sh
```

Checks: YAML syntax → helm lint → kubectl dry-run → UDS validate → honesty markers.

### Reset between runs

```bash
uds run demo:reset
```

---

## UDS Package CR — what it does

The `uds-package.yaml` instructs UDS Core's Pepr operator to:

1. **SSO**: Register a Keycloak OIDC client `szl-receipts` with redirect URI `https://receipts.uds.dev/oauth2/callback`. Inject the `authservice` sidecar on pods matching `app: szl-receipts-server`. Access restricted to groups `/UDS Core/Admin` and `/szl/receipts`.

2. **Expose**: Create an Istio VirtualService via the UDS tenant gateway, making the receipts server accessible at `https://receipts.<domain>` without modifying the Istio Gateway CRs directly.

3. **Allow**: Generate Istio AuthorizationPolicies and supplement with K8s NetworkPolicies to allow:
   - Egress to OTel collector on port 4317 (OTLP/gRPC)
   - Egress to Keycloak on port 8080 (SSO token validation)
   - Ingress from Pepr webhook on port 8443 (receipt POST)
   - Ingress from Prometheus on port 8443 (metrics scrape)

4. **Monitor**: Register a Prometheus scrape target at `/metrics` on port 8443, scraped every 30 seconds.

---

## Honesty boundaries — STAGED items

These items are explicitly incomplete and require named founder actions before they are operational. **This PR does not claim they are complete.**

### STAGED: FA-001 — Container image not yet pushed

**Status:** Image placeholder only  
**Detail:** `ghcr.io/szl-holdings/vessels:uds-v0.3.0` is referenced in production image configuration but has NOT been pushed. The Zarf package currently bundles `docker.io/library/python:3.12-slim` as the base image.  
**Prerequisite:** Founder action FA-001: push `ghcr.io/szl-holdings/vessels:uds-v0.3.0` after vessels CI pipeline produces the image.  
**Impact:** Bundle deploys successfully with python:3.12-slim. Production air-gap bundle will need the `vessels` image.

### STAGED: U5 — Cosign signing not provisioned

**Status:** CI stub only  
**Detail:** Cosign signing is configured in the CI workflow but org keys have not been provisioned. Running `cosign verify` on the Zarf package or UDS bundle artifact will fail.  
**Prerequisite:** Founder approval U5: provision org cosign key pair, add public key to GHCR org, configure COSIGN_PRIVATE_KEY in Actions secrets.  
**Impact:** Bundle deploys and runs correctly. Supply chain attestation is incomplete.

### STAGED: FA-002 — Keycloak SSO requires core-slim-dev

**Status:** Package CR wired, but SSO non-functional without Keycloak  
**Detail:** The `sso:` block in `uds-package.yaml` and Keycloak egress NetworkPolicy are correct, but Keycloak is only available after `core-slim-dev` is deployed. If szl-receipts is deployed standalone (without the bundle), SSO calls will fail.  
**Prerequisite:** Deploy via `uds-bundle.yaml` which ensures correct layer order (init → core-slim-dev → szl-receipts).  
**Impact:** Receipts API works without SSO. The `/oauth2/callback` endpoint is unreachable until core-slim-dev is running.

---

## What this work is NOT

Per Doctrine v6:

- **Not catalog acceptance.** Andrew Greene's Option A endorsement (2026-05-22) authorizes operating within UDS licensing. This work meets catalog-grade technical requirements but does not claim or imply Defense Unicorns catalog acceptance.
- **Not a replacement for uds-core security policies.** The NetworkPolicy and PSS manifests are defense-in-depth supplements, not alternatives to Istio AuthorizationPolicies or Pepr policies generated by uds-core.
- **Not a modification of uds-core.** The receipts server is a separate workload with zero AGPL entanglement. All SZL code is Apache-2.0.
- **Not production-hardened.** This is Warhacker demo-grade. Production readiness requires: Ed25519 signing keys, HA mode (replicas ≥ 2), persistent storage, and DoD ATF assessment.

---

## File map (repo structure)

```
szl-uds-deployment/
├── charts/
│   └── szl-receipts/
│       ├── Chart.yaml                    ← existing (v0.1.0, unchanged)
│       ├── values.yaml                   ← existing (unchanged)
│       └── templates/
│           ├── configmap.yaml            ← existing
│           ├── deployment.yaml           ← existing
│           ├── ingress.yaml              ← existing
│           ├── service.yaml              ← existing
│           ├── uds-package.yaml          ← NEW (this PR)
│           ├── networkpolicy.yaml        ← NEW (this PR)
│           ├── servicemonitor.yaml       ← NEW (this PR)
│           └── podsecuritystandard.yaml  ← NEW (this PR)
├── docs/
│   └── WARHACKER_DEMO.md                ← existing (unchanged)
├── tasks.yaml                            ← UPDATED (was v0.1.0, now v0.3.1 w/ demo:*)
├── uds-bundle.yaml                       ← UPDATED (was v0.1.0, now v0.3.1)
├── zarf.yaml                             ← existing (unchanged)
└── tests/
    └── uds-package-validation.sh         ← NEW (this PR)
```

---

## Related issues / context

- `a11oy#94` — UDS frontier gap map (Cursor output) — proxying to `szl-uds-deployment` per directive
- `uds-mesh#46` — BFT single-signer caveat in uds-mesh README
- `.github#85` — Plotly inline for offline demo
- **Warhacker:** June 16-20, San Diego — live k3d cluster demo

---

## Commit sign-off

All commits in this PR are `-s` signed-off per SZL doctrine.

```bash
git commit -s -m "feat(uds): catalog-grade Package CR, NetworkPolicy, ServiceMonitor, PSS, tasks v0.3.1"
```

---

*Doctrine v6 strict | Apache-2.0 | Audit: 2026-05-29 evening*  
*Sources: [UDS Docs](https://uds.defenseunicorns.com/docs/) | [uds-core](https://github.com/defenseunicorns/uds-core) | [uds-cli](https://github.com/defenseunicorns/uds-cli)*
