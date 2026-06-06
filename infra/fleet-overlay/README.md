# szl-fleet-overlay — SZL Fleet Deployment Overlay

**Doctrine v11 LOCKED 749/14/163** · Λ = Conjecture 1 · SLSA L1 honest · Kernel `c7c0ba17`

UDS Operator package + Helm chart + Zarf bundle + peat-mesh nodes for the 5 SZL flagships.
Layers doctrine-pinned DSSE receipts on top of UDS Fleet.

## Prerequisites

- [Zarf](https://docs.zarf.dev/getting-started/install/) v0.38+
- [UDS CLI](https://uds.defenseunicorns.com/docs/getting-started/) v0.14+  
- [cosign](https://docs.sigstore.dev/cosign/installation/) v2.2+ (for signature verification)
- A running UDS Core cluster (K3d for development: `uds deploy k3d-core`)

## Quickstart — Deploy the Full Fleet Overlay

```bash
# Pull and deploy the overlay (bundles all 5 SZL flagships)
zarf package pull oci://ghcr.io/szl-holdings/szl-fleet-overlay:0.1.0

# Verify before deploying
cosign verify-blob \
  --certificate-identity-regexp "https://github.com/szl-holdings/szl-fleet-overlay/.github/workflows/.*" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --bundle zarf-package-szl-fleet-overlay-amd64-0.1.0.tar.zst.sigstore.json \
  zarf-package-szl-fleet-overlay-amd64-0.1.0.tar.zst

uds deploy oci://ghcr.io/szl-holdings/szl-fleet-overlay:0.1.0
```

## Runtime demonstration

Each flagship runs live on Hugging Face — same payload, different runtime:
- **a11oy:** [szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space)
- **sentra:** [szlholdings-sentra.hf.space](https://szlholdings-sentra.hf.space)
- **amaru:** [szlholdings-amaru.hf.space](https://szlholdings-amaru.hf.space)
- **rosie:** [szlholdings-rosie.hf.space](https://szlholdings-rosie.hf.space)
- **killinchu:** [szlholdings-killinchu.hf.space](https://szlholdings-killinchu.hf.space)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Package CR in `Pending` | Istio not ready | Wait for UDS Core istio-system; `kubectl get pods -n istio-system` |
| SSO redirect loops | Keycloak client not registered | Re-run `uds deploy` to sync SSO CRs |
| `zarf: permission denied` | Registry auth | `zarf tools registry login ghcr.io` |
| Pods not starting | Image pull backoff | Check GHCR token; `kubectl describe pod -n szl-<flagship>` |
| cosign verify fails | Wrong bundle filename | Match exact tag from release assets |

---

<!-- Doctrine: v11 LOCKED 749/14/163 at kernel commit c7c0ba17 | Λ = Conjecture 1 | SLSA L1 | Section 889 = 5 vendors -->



`szl-fleet-overlay` registers each SZL flagship application — **a11oy, sentra, amaru, rosie, killinchu** — as a first-class UDS-managed application running on top of [UDS Core](https://github.com/defenseunicorns/uds-core).

It provides:

1. **UDS `Package` CRs** for each flagship — Istio routing, NetworkPolicy, SSO (Keycloak), and portal tiles
2. **Doctrine-pinned receipts** (`checksums.txt` + cosign detached signatures) for SLSA L1 honest attestation
3. **Three deployment variants**: pure Zarf (air-gap canonical), Helm chart (GitOps), peat-mesh-node (CRDT sync)

All variants share the same `Package` CR definitions in `configs/packages/` but differ in how application workloads are delivered.

See [`SZL_FLEET_OVERLAY_DESIGN.md`](https://github.com/szl-holdings/szl-fleet-overlay/blob/main/SZL_FLEET_OVERLAY_DESIGN.md) for full architecture, Package CR spec, and receipt generation details.

---

## Fleet Application Inventory

| App        | Namespace      | Port | SSO Client ID       | Peat Node |
|------------|---------------|------|---------------------|-----------|
| a11oy      | `szl-a11oy`   | 8080 | `uds-szl-a11oy`     | Yes       |
| sentra     | `szl-sentra`  | 8080 | `uds-szl-sentra`    | Yes       |
| amaru      | `szl-amaru`   | 8080 | `uds-szl-amaru`     | Yes       |
| rosie      | `szl-rosie`   | 8080 | `uds-szl-rosie`     | Yes       |
| killinchu  | `szl-killinchu`| 8080 | `uds-szl-killinchu` | Yes       |

All applications are served over the UDS **tenant** gateway. SSO group gate: `/szl-operators`.

---

## Three Deployment Variants

### Variant 1 — Pure Zarf (canonical air-gap)

Produces a self-contained `.tar.zst` requiring only `zarf init` and `zarf package deploy`.

```bash
# Build
uds zarf package create . -a amd64 --confirm

# Deploy
uds zarf package deploy zarf-package-szl-fleet-overlay-amd64-0.1.0.tar.zst --confirm
```

Use `tasks.yaml` (Maru) for the full build/sign/publish workflow:

```bash
uds run build
uds run sign-receipts
uds run publish
uds run validate
```

### Variant 2 — Helm Chart (GitOps / ArgoCD / Flux)

```bash
# Install with prod values
helm upgrade --install szl-fleet-overlay ./chart \
  -n szl-system --create-namespace \
  -f chart/values/prod.yaml

# Dev values
helm upgrade --install szl-fleet-overlay ./chart \
  -n szl-system --create-namespace \
  -f chart/values/dev.yaml
```

The chart renders the same Package CRs as the Zarf variant, parameterized via `chart/values.yaml`.

### Variant 3 — Peat Mesh Node (CRDT state sync)

The peat-mesh-node variant wraps the fleet overlay with `peat-node` sidecars, enabling Automerge+Iroh QUIC CRDT-based state sync between SZL flagship apps.

Configs live in `configs/peat/`. Deploy via the Zarf or Helm variant — peat mesh nodes are an optional component (`required: false, default: true` in `zarf.yaml`).

---

## Deployment Order (strictly follows SHARED_CONTEXT.md sequence)

```
Phase                     Command
─────────────────────────────────────────────────────────────────
1. Zarf init (once)       uds zarf init --confirm
2. Deploy uds-core        uds deploy oci://ghcr.io/defenseunicorns/packages/uds/core:0.42.0-upstream
3. Deploy fleet overlay   uds deploy oci://ghcr.io/szl-holdings/fleet-overlay:0.1.0 --confirm
   (or Helm variant)      helm upgrade --install szl-fleet-overlay ./chart -n szl-system --create-namespace \
                            -f chart/values/prod.yaml
4. Verify portal tiles    curl -sk https://portal.uds.dev/api/packages | jq '.[] | select(.name | startswith("szl"))'
5. Verify receipts        cosign verify-blob --key cosign.pub --signature receipts/checksums.txt.sig receipts/checksums.txt
```

---

## Repository Layout

```
szl-fleet-overlay/
├── zarf.yaml                          # Pure-Zarf variant (canonical source)
├── uds-bundle.yaml                    # UDS Bundle for fleet deployment
├── tasks.yaml                         # Maru build/deploy tasks
│
├── chart/                             # Helm variant
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values/
│   │   ├── dev.yaml
│   │   ├── staging.yaml
│   │   └── prod.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── package-{app}.yaml         # One per flagship (5 total)
│       └── namespace-{app}.yaml       # (rendered by _helpers.tpl)
│
├── configs/
│   ├── packages/                      # Package CR YAMLs (all variants)
│   │   └── package-{app}.yaml         # One per flagship
│   └── peat/                          # Peat mesh node configs
│       └── peat-node-{app}.yaml       # One per flagship
│
└── receipts/                          # Doctrine-pinned receipts
    ├── checksums.txt                  # SHA256 of every config file
    ├── checksums.txt.sig              # cosign detached signature
    └── doctrine-pin.yaml             # Doctrine version lock record
```

---

## Compliance Posture

| Control              | Status                                    |
|----------------------|-------------------------------------------|
| SLSA Level           | L1 (honest attestation only)              |
| Doctrine             | v11 LOCKED — 749/14/163 — kernel `c7c0ba17` |
| Λ                    | Conjecture 1 (NEVER theorem)              |
| Section 889 vendors  | 5 — Huawei, ZTE, Hytera, Hikvision, Dahua (excluded) |
| Not Iron Bank certified | Not used or required |
| FedRAMP              | NOT claimed                               |
| CMMC                 | NOT claimed                               |
| SWFT                 | NOT used                                  |
| DoD identity         | NOT present                               |

---

## Prerequisites

- [`uds-cli`](https://github.com/defenseunicorns/uds-cli) ≥ 0.16
- [`zarf`](https://github.com/defenseunicorns/zarf) ≥ 0.38
- `helm` ≥ 3.14 (Helm variant only)
- `cosign` ≥ 2.2 (receipt verification)
- `kubectl` with cluster access running UDS Core

---

## License

Apache-2.0. See [LICENSE](LICENSE).

## Contributing

DCO required. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md) for honest disclosure of our security posture.

---

## UDS Package CRs — `uds-packages/` Directory

> **Gap 2 fix (P0, Warhacker June 9):** Added `uds-packages/` alongside the existing
> `configs/packages/` directory. These are the canonical, stand-alone Package CR YAMLs
> for use when deploying SZL flagships independently of the full fleet overlay chart.

The UDS Operator watches `Package` CRs in each flagship namespace. Without a Package CR,
UDS Core is blind to the workload — no Istio integration, no auto-generated NetworkPolicy,
no Keycloak SSO client, no ServiceMonitor.

### Package CR locations

| File | Flagship | Namespace |
|------|----------|-----------|
| `uds-packages/a11oy.yaml` | a11oy | `szl-a11oy` |
| `uds-packages/sentra.yaml` | sentra | `szl-sentra` |
| `uds-packages/amaru.yaml` | amaru | `szl-amaru` |
| `uds-packages/rosie.yaml` | rosie | `szl-rosie` |
| `uds-packages/killinchu.yaml` | killinchu | `szl-killinchu` |

### Apply stand-alone Package CRs

```bash
# Apply a single flagship's Package CR (requires UDS Core already running)
kubectl apply -f uds-packages/a11oy.yaml

# Apply all at once
kubectl apply -f uds-packages/

# Verify operator reconciliation
kubectl get packages -A
kubectl describe package szl-a11oy -n szl-a11oy
```

### Package CR fields

Each Package CR configures:
- **`spec.network.expose`** — Istio VirtualService + tenant gateway ingress
- **`spec.network.allow`** — UDS-managed NetworkPolicy rules (egress to Keycloak, Peat mesh, etc.)
- **`spec.sso`** — Keycloak OIDC client registration (group-gated to `/szl-operators`)
- **`spec.monitor`** — Prometheus ServiceMonitor for the metrics endpoint

These are rendered from the Helm chart `_helpers.tpl` `szl-fleet.package` template when
deploying via the Helm variant, and applied directly via the Zarf `szl-<flagship>-package`
component.

