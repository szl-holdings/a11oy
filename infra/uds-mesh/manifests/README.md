# Mesh deployment manifests (WU-2)

Real, offline-validatable Kubernetes/Istio surface for the UDS mesh, landed in the
**canonical home `szl-holdings/uds-mesh`** per **ADR-0001** (Canonical Home for the
UDS Mesh, ACCEPTED 2026-06-03).

## What's here

| Path | Purpose |
|------|---------|
| `istio/peer-authentication.yaml` | `PeerAuthentication` **STRICT** mTLS, one per organ namespace (a11oy, sentra, amaru, killinchu, rosie) |
| `istio/destination-rule.yaml` | `DestinationRule` pinning **ISTIO_MUTUAL** TLS to the mesh OTLP collector and organ services |
| `otel/collector.yaml` | OpenTelemetry Collector: **OTLP gRPC receiver (4317)** + HTTP (4318) → `memory_limiter`/`batch` → **OTLP exporter pipeline** forwarding to the vsp-otel Λ-gate verifier |

## HONESTY OVER CHECKLIST

- **No live cluster in CI.** These manifests are validated **offline** only. The mesh
  is not deployed by this PR; live Istio/k8s wiring is a disclosed boundary.
- The collector forwards to `vsp-otel-collector.szl-mesh.svc...:4318`, which is the
  Λ-gate exporter from **vsp-otel PR #61** (`feat/real-otlp-exporter`). Cross-repo
  composition, not a reimplementation.
- Section 889 vendor list unchanged: {Huawei, ZTE, Hytera, Hikvision, Dahua}. No
  Iron Bank / FedRAMP / CMMC L2+ / SWFT / Mission Owner claims. SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap only.

## Offline validation

Native k8s objects (the collector) validate against the bundled schema:

```bash
kubeconform -strict -summary manifests/otel/collector.yaml
# Summary: 3 resources found - Valid: 3, Invalid: 0
```

Istio CRs need the Istio CRD schemas (not bundled in kubeconform by default):

```bash
# Option A: kubeconform with the Istio schema location
kubeconform -strict -summary \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/istio/istio/master/manifests/charts/base/crds/{{ .ResourceKind }}.json' \
  manifests/istio/*.yaml

# Option B: client-side dry-run against a cluster that has the Istio CRDs installed
kubectl apply --dry-run=client -f manifests/istio/ -f manifests/otel/
```

CI runs `pytest tests/test_manifests.py`, which asserts the YAML parses and carries
the security invariants (STRICT mTLS on all 5 organs, ISTIO_MUTUAL, OTLP gRPC
receiver, forwarding exporter pipeline) without needing a cluster.

---

*See `ADR_UDS_MESH_HOME.md` (ADR-0001). License: Apache-2.0.*

Doctrine v11 — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (never a theorem).

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
