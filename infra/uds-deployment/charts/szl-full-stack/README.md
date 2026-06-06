# szl-full-stack Helm Chart

**Version:** 0.3.1
**Doctrine:** v6 (strict) — honest STAGED labels on all pending components

This Helm umbrella chart composes the full SZL Holdings stack:

| Sub-chart | Component | Status |
|-----------|-----------|--------|
| `szl-receipts` | Pepr policy webhook + receipt server | Available |
| `a11oy-runtime` | L1–L7 receipt chain, 5 anchor formula gates | [STAGED: awaiting FA-001] |
| `sentra-gates` | Fail-closed safety gate, L7 forecast | [STAGED: awaiting FA-001] |
| `amaru-attestation` | KL drift receipts, formula_witness emitter | [STAGED: awaiting FA-001] |
| `rosie-replay` | Decision fabric, receipt dashboard | [STAGED: awaiting FA-001] |

---

## Prerequisites

- Kubernetes 1.28+
- Helm 3.12+
- UDS CLI 0.15+
- `uds-core` slim-dev or full deployed in cluster
- k3d (for local dev) or a UDS-managed cluster (for production)

---

## Installation

### Minimum working install (receipts only)

```bash
helm upgrade --install szl-full-stack ./charts/szl-full-stack \
  --namespace szl-system \
  --create-namespace \
  --set 'a11oy-runtime.enabled=false' \
  --set 'sentra-gates.enabled=false' \
  --set 'amaru-attestation.enabled=false' \
  --set 'rosie-replay.enabled=false'
```

### Full stack install (after FA-001 completed)

```bash
helm upgrade --install szl-full-stack ./charts/szl-full-stack \
  --namespace szl-system \
  --create-namespace \
  --set 'a11oy-runtime.enabled=true' \
  --set 'sentra-gates.enabled=true' \
  --set 'amaru-attestation.enabled=true' \
  --set 'rosie-replay.enabled=true'
```

### Using values file

```bash
helm upgrade --install szl-full-stack ./charts/szl-full-stack \
  --namespace szl-system \
  --create-namespace \
  --values my-override-values.yaml
```

---

## Verify Deployment

```bash
# Check pods
kubectl get pods -A -l szl.holdings/doctrine-version=v6

# Check receipt dashboard
kubectl port-forward svc/szl-receipts-server 8443:8443 -n szl-receipts &
curl http://localhost:8443/health

# Trigger a receipt
kubectl run test-workload --image=nginx --restart=Never -n default
curl -s http://localhost:8443/receipts | python3 -m json.tool
```

---

## Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `global.imageRegistry` | `ghcr.io/szl-holdings` | Container registry |
| `global.releaseVersion` | `0.3.1` | Release version label |
| `szl-receipts.enabled` | `true` | Enable receipt server + Pepr webhook |
| `szl-receipts.receipts.signingMode` | `demo` | `demo` (HMAC) or `production` (Ed25519, requires FA-001) |
| `a11oy-runtime.enabled` | `false` | [STAGED] Enable a11oy runtime |
| `a11oy-runtime.gates.strictMode` | `true` | Strict mode for all 5 anchor formula gates |
| `sentra-gates.enabled` | `false` | [STAGED] Enable sentra safety gate + forecast |
| `sentra-gates.gate.failClosed` | `true` | Fail closed on gate error |
| `amaru-attestation.enabled` | `false` | [STAGED] Enable amaru witness emitter |
| `amaru-attestation.witness.klDriftThreshold` | `0.05` | KL drift detection threshold |
| `rosie-replay.enabled` | `false` | [STAGED] Enable rosie dashboard + replay engine |
| `rosie-replay.decision.mandatoryWitness` | `true` | ROSIE-V1: require witness on every decision |

---

## Doctrine Compliance

```bash
# Verify no banned superlatives in deployed manifests
helm get manifest szl-full-stack | grep -E \
  "fully compliant|production-ready|enterprise-grade|catalog accepted|officially endorsed"
# Expected: no output
```

---

## What This Chart Is NOT

- Not a UDS Catalog submission (see `catalog-submission/README.md`)
- Not an endorsement by Defense Unicorns as their product
- Not a trademark non-objection
- SZL UDS = Unified Decision Span ≠ Defense Unicorns' Unified Defense Stack (formerly Unicorn Delivery Service, rebranded 2026-06-02)

---

## FA-001 Founder Action Required

The following chart dependencies will fail until a founder completes FA-001:
- Push containers to `ghcr.io/szl-holdings/` for a11oy, sentra, amaru, rosie
- Run `cosign sign-blob` on all tarballs with org dev key
- Upload signed assets to GitHub releases `uds-v0.3.1`

See `docs/OPERATOR_QUICKSTART.md` for full FA-001 checklist.

---

*Generated: 2026-05-29 | charts/szl-full-stack/README.md | Doctrine v6 strict*
