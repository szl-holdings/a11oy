# DEPLOY_RUNBOOK.md — SZL Operational UDS Drops

**Doctrine v11 LOCKED 749/14/163**
Operational tone: deploy in 60s, pull the cable, it works. No booth, no compliance pageantry.

> **Not** Iron Bank certified · **Not** SWFT-listed · **Not** FedRAMP authorized — we don't need any of them for it to work.
> Λ is **Conjecture 1**, not a theorem. SLSA **L1 + L2** (organ provenance attestations verify via `cosign verify-attestation`); **L3 not claimed**. 163 sorries open in the Lean kernel (disclosed).

## Bundle release — v0.2.0 (Fleet-native)

All 5 bundles are now **v0.2.0**, targeting **Unified Defense Stack (UDS) Core v1.5.0** and
**Zarf v0.77.0** (keyless sign + offline verify). "UDS" expands to **Unified Defense Stack**
throughout (UDS Core renamed it; see uds-core README). Each `uds-bundle.yaml` now declares
Fleet/DDIL edge metadata (`fleet-deployable`, `deployable-to-edge`, `ddil-ok`, `min-ram-gb=4`)
so a bundle drops into the **Mission Applications tier of a UDS System Image** and runs on a
4 GB tactical-edge node.

- UDS Fleet (Package → Deploy → Manage): https://defenseunicorns.com/products/uds-fleet/
- UDS Core v1.5.0: https://github.com/defenseunicorns/uds-core/releases/tag/v1.5.0
- Zarf v0.77.0: https://github.com/zarf-dev/zarf/releases/tag/v0.77.0
- Tactical Edge (4 GB floor): https://uds.defenseunicorns.com/tactical-edge-deployments/overview/

**Fleet signs the package; we sign the decision.** This bundle adds the governed, signed
*decision* layer Fleet doesn't — built on the same substrate (Zarf, Pepr admission, the
`uds.dev/v1alpha1` Package CRD).

## K8s-native hardening (additive, alongside Pepr)

Each bundle now also ships upstream-K8s-native gates **beside** the existing Pepr `Package` policies
(UDS Core compatibility preserved):

- **PSA `restricted`** namespace labels (`pod-security.kubernetes.io/enforce: restricted`, pinned
  `enforce-version: v1.36`) — our STIG `securityContext` already satisfies it.
- **ValidatingAdmissionPolicy `szl-lambda-gate`** (K8s VAP GA v1.30, in-API-server, `failurePolicy: Fail`),
  shipped in **Audit** mode; promote to **Deny** after a green dress rehearsal.
- **sigstore `ClusterImagePolicy`** (policy-controller v0.15.1) requiring a cosign signature on every
  `ghcr.io/szl-holdings` image; shipped in `mode: warn`.
- **Cilium L7 `CiliumNetworkPolicy`** template, gated on `networkPolicy.cilium`, pinning DSSE-receipt
  egress to the KhipuReceipt POST path (Cilium edges only).
- **SLSA provenance** annotated to spec **v1.2** — level **stays L1 (honest)**; no L2 claim — deferred
  `slsa-verifier` is green.

The SZL governance overlay is also expressed as first-class CRDs under `crds/`
(`LambdaGate`, `KhipuReceipt`, `DoctrineLock`) — a **design** built on Apache-2.0/MIT upstreams,
not yet a live claim. See `crds/README.md`.

Verification gates (every claim backed by a live command, per NO HALLUCINATION):
```bash
zarf package verify szl-<flagship>-v0.2.0.tar.zst \
  --certificate-identity "<CI workflow identity>" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"   # Zarf v0.77.0 offline verify
kubectl get lambdagates,doctrinelocks -A          # governance overlay (once operator deployed)
kubectl get khipureceipts -n szl-<flagship>       # signed decision receipts as cluster state
```

---

## The 5 bundles (each fills a UDS Core gap)

| Bundle | Operationally does | UDS Core gap it fills |
|---|---|---|
| `szl-a11oy.uds.tar.zst` | Governance + policy overlay + agentic /code | governance layer |
| `szl-sentra.uds.tar.zst` | 8-gate immune system + verdict pipeline (fail-CLOSED) | defensive screen |
| `szl-amaru.uds.tar.zst` | Cortex memory + DSSE receipts + Khipu DAG | signed-decisions chain |
| `szl-rosie.uds.tar.zst` | Operator console + decision approval gates | human-in-loop layer |
| `szl-killinchu.uds.tar.zst` | Counter-UAS + Λ-gate + defensive scope | mission-ready application |

---

## Prerequisites (the box in the room)
- A UDS Core / k3s cluster (the NVIDIA 4060 Ti tower works fine — CPU-only images, GPU optional)
- `zarf` v0.77.0+ and `uds` v0.27+ on the box (Zarf v0.77.0 = keyless sign + offline `zarf package verify`)
- The bundle tarballs on a USB stick (air-gap: no registry pull needed at deploy time)
- The published cosign public key: `bundles/v0.1.0/cosign_signing_key.pub`

## Build the bundles (once, on a connected box)
```bash
# Per bundle — bakes image + chart + SBOM + attestations into one air-gap tarball
cd szl-<flagship>
zarf package create . --confirm
# Output: zarf-package-szl-<flagship>-amd64-0.1.0.tar.zst
mv zarf-package-szl-<flagship>-amd64-0.1.0.tar.zst szl-<flagship>.uds.tar.zst
# Sign it (private key from HF Space secret COSIGN_PRIVATE_KEY)
cosign sign-blob --key $COSIGN_PRIVATE_KEY szl-<flagship>.uds.tar.zst > szl-<flagship>.uds.sig
```
Copy the `.uds.tar.zst` + `.sig` files to the USB stick.

## Verify before deploy (on the air-gapped box)
```bash
cosign verify-blob \
  --key cosign_signing_key.pub \
  --signature szl-<flagship>.uds.sig \
  szl-<flagship>.uds.tar.zst
```

---

## Scenario A — Immune-screen drop only (sentra), ~60s
Goal: stand up the fail-CLOSED defensive screen alone. Smallest possible footprint.
```bash
zarf package deploy szl-sentra.uds.tar.zst --confirm
kubectl -n szl-sentra get pods -w           # wait for Running
# Smoke test the 8-gate verdict pipeline
kubectl -n szl-sentra port-forward svc/sentra 8080:8080 &
curl -s localhost:8080/healthz
curl -s localhost:8080/api/sentra/v1/gates  # lists all 8 immune gates
curl -s -XPOST localhost:8080/api/sentra/v1/verdict -d '{"signal":"demo"}'
```
**Pull the network cable now.** Re-run the verdict call — it still returns a verdict.
Default verdict on gate error is **DENY** (fail-CLOSED).

## Scenario B — Immune + signed receipts (sentra + amaru), ~2 min
Goal: every verdict gets sealed into an append-only signed Khipu DAG.
```bash
zarf package deploy szl-sentra.uds.tar.zst --confirm
zarf package deploy szl-amaru.uds.tar.zst  --confirm
kubectl -n szl-sentra get pods -w
kubectl -n szl-amaru  get pods -w
# Generate a verdict, then verify its DSSE receipt off the Khipu chain
kubectl -n szl-amaru port-forward svc/amaru 8081:8080 &
curl -s localhost:8081/api/amaru/healthz
# Each decision -> Khipu DAG node + cosign DSSE receipt:
cosign verify-blob --key cosign_signing_key.pub \
  --signature <receipt>.sig --certificate <receipt>.pem <receipt>.blob
```

## Scenario C — Full mesh (all 5), ~3-4 min
Goal: governance + immune + signed memory + human-in-loop + counter-UAS application.
```bash
for b in sentra amaru a11oy rosie killinchu; do
  zarf package deploy szl-$b.uds.tar.zst --confirm
done
kubectl get pods -A | grep szl-
# Surfaces:
#   a11oy     :8080  /api/a11oy/healthz        governance + /code
#   sentra    :8080  /healthz                  immune verdict pipeline
#   amaru     :8080  /api/amaru/healthz        Khipu DAG + DSSE receipts
#   rosie     :7860  /                         operator console + approval gates
#   killinchu :7860  /api/killinchu/healthz    counter-UAS Λ-gate
```
**Pull the cable.** The whole mesh keeps serving — no egress dependency.
Rosie's console shows pending decisions; an operator approves/denies; the verdict
is screened by sentra, sealed by amaru, and (for counter-UAS) acted by killinchu.

---

## Teardown
```bash
for b in killinchu rosie a11oy amaru sentra; do
  uds zarf package remove szl-$b --confirm 2>/dev/null || zarf package remove szl-$b --confirm
done
```

## The ask
Run it on **your** operational hardware for one week. Tell us if it deserves more.

---
*Author: Yachay <yachay@szlholdings.dev> (DCO signed). Doctrine v11 LOCKED 749/14/163.*
