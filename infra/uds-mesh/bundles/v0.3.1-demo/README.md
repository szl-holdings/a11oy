# SZL UDS demo bundle — v0.3.1-demo

> **rosie is the operator console. a11oy is the policy substrate. amaru, sentra, and vessels are the organs.**
> This bundle ships the one piece of that anatomy that is real and deployable today — the `szl-receipts` governance receipt service — and is honest about the rest being roadmap.

## What this bundle deploys

| Layer | Package | Source |
|-------|---------|--------|
| 1 | `init` | `ghcr.io/defenseunicorns/packages/init:v0.77.0` (Zarf v0.77.0) |
| 2 | `core-slim-dev` | `ghcr.io/defenseunicorns/packages/uds/core:0.34.0-slim-dev` (Istio + Pepr + Keycloak + Prometheus) |
| 3 | `szl-receipts` | `szl-holdings/szl-uds-deployment` → `packages/szl-receipts` (DSSE receipt service) |

`szl-receipts` is the only SZL workload with a correct UDS `Package` CR (SSO/authservice selector, Istio tenant expose, NetworkPolicy allow-rules, OTLP egress) and a real chart + images. It deploys on uds-core slim-dev.

## Why this replaced `bundles/v0.3.1/`

The previous `bundles/v0.3.1/uds-bundle.yaml` referenced **six packages that do not exist** (composition-runtime, scitt-adapter, policy-gate, a15-homology, xoshiro-prng, k10v2-replay) under the **wrong org** `ghcr.io/szl/packages/...` (SZL's org is `szl-holdings`). `uds create` against it fails on the first package pull. It is deleted in this PR.

## What is NOT in this bundle (and why)

The five module packages — **rosie** (operator console), **a11oy** (policy substrate), **amaru** (memory), **sentra** (immune), **vessels** (deployment fabric) — each now have a `zarf-build-and-sign.yml` build path (separate per-module PRs), but they are **not** in this bundle because:

1. **No published images** — all five GHCR images returned `403` on 2026-05-30 (not pushed).
2. **No UDS `Package` CR** — each ships raw `Deployment`+`Service`+`Namespace`, so uds-core's default-deny network policy would block them. They would run un-meshed.
3. **No interconnect** — the modules do not call each other: no service discovery, no mTLS, no orchestrator endpoint. Calling five isolated deployments a "mesh" would be inaccurate.

Wiring them into a real interconnect (a11oy as orchestrator, Package CRs, Istio sidecars, `PeerAuthentication: STRICT`, AuthorizationPolicies, Kubernetes-DNS discovery) is the **v0.4.0 roadmap** — see [`docs/roadmap/MESH_INTERCONNECT.md`](../../docs/roadmap/MESH_INTERCONNECT.md).

## Build / deploy / verify

```bash
# Build (uds-cli v0.31.0). Until szl-receipts is published to GHCR, build from a
# local checkout by swapping the szl-receipts repository+ref for a path: ref.
uds create bundles/v0.3.1-demo --confirm

# Deploy onto a slim-dev cluster
uds deploy uds-bundle-szl-receipts-demo-amd64-0.3.1.tar.zst --confirm

# Inspect
uds inspect uds-bundle-szl-receipts-demo-amd64-0.3.1.tar.zst
```

## Staged / honesty markers

- `szl-receipts:0.3.1` image not yet on GHCR (`403`); build from a local `path:` ref until published.
- Bundle cosign signing pending org key provisioning.
- Receipt chain currently in an `emptyDir` on a single replica (not durable); HMAC uses a demo key. Both are documented limitations, not production posture.

## References

- UDS bundle schema — defenseunicorns/uds-cli: https://github.com/defenseunicorns/uds-cli
- UDS Core releases: https://github.com/defenseunicorns/uds-core/releases
- Zarf v0.77.0: https://docs.zarf.dev/
- szl-receipts package: https://github.com/szl-holdings/szl-uds-deployment
