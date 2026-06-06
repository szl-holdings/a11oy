# SZL Mesh Deploy Guide

**Bundle:** `szl-mesh:0.4.0` (current published OCI; also tagged `v0.4.0`/`latest`). Legacy alias: `szl-uds-bundle:uds-v0.2.x`.  
**Repo:** `szl-holdings/uds-bundles`  
**Updated:** 2026-06-05  
**Doctrine:** v11 LOCKED 749/14/163 · SLSA L1 + L2 (organ images, `.att` = slsa.dev/provenance/v0.2); bundle cosign-**signed** (build-provenance attestation NOT yet earned on the bundle) · Λ = Conjecture 1  
**Signed-off-by:** stephenlutar2-hash \<stephenlutar2@gmail.com\>

---

## What This Bundle Does

The `szl-mesh:0.4.0` bundle (legacy alias `szl-uds-bundle`) deploys **5 flagship organs** of the SZL governed-AI substrate into any UDS Core cluster. These organs run as independent, airgap-safe Kubernetes workloads. Together they implement the Cannonico answer: a permanent, tamper-evident record of AI decisions and counter-UAS actions.

| Organ | What It Does | Port |
|-------|-------------|------|
| **szl-a11oy** | Governance policy gate + DSSE receipt substrate. Every agent action emits a Khipu receipt; `receipts.in ≡ receipts.out` audit-fiber continuity. | 8080 |
| **szl-sentra** | 8-gate fail-CLOSED immune screen. Deny-by-default; signed ALLOW/DENY verdicts. | 8080 |
| **szl-amaru** | 13-axis memory cortex. Every decision hashed into a Khipu DAG with DSSE/cosign receipt. | 8080 |
| **szl-rosie** | Operator console. Human-in-the-loop confirmation, receipt review, mesh health. | 7860 |
| **szl-killinchu** | Counter-UAS organ. Decodes ADS-B/MAVLink/OpenDroneID, scores threats through the 13-axis Λ-gate, signs every interdiction verdict. | 7860 |

---

## Prerequisites

The bundle deploys **into an existing UDS Core cluster**. It does NOT bring its own cluster.

1. **UDS Core v1.x running** — Istio (ambient or sidecar), Pepr UDS Operator, Keycloak, Prometheus must be up.
2. **uds-cli v0.32.0** installed on the deploy machine (bundles Zarf v0.77.0):

```bash
UDS_VERSION="v0.32.0"
curl -sLo /usr/local/bin/uds \
  "https://github.com/defenseunicorns/uds-cli/releases/download/${UDS_VERSION}/uds-cli_${UDS_VERSION}_Linux_amd64"
chmod +x /usr/local/bin/uds
uds version       # → v0.32.0
uds zarf version  # → v0.77.0
```

3. **kubectl** with cluster access.
4. **Cluster must NOT use namespaces** `szl-a11oy`, `szl-sentra`, `szl-amaru`, `szl-rosie`, `szl-killinchu` already. These will be created by the deploy.

---

## Deploy Commands

### Option A — USB Tarball (Airgap / Warhacker San Diego)

The canonical Warhacker deploy. The tarball contains all 5 organ images baked in — no external network pull at deploy time.

```bash
# If the tarball from CI is named uds-bundle-szl-uds-bundle-amd64-0.2.1.tar.zst,
# rename for cleanliness (both names work):
mv uds-bundle-szl-uds-bundle-amd64-0.2.1.tar.zst szl-uds-bundle-uds-v0.2.1.tar.zst

# Deploy into the existing UDS Core cluster:
uds-cli bundle deploy szl-uds-bundle-uds-v0.2.1.tar.zst --confirm
```

### Option B — OCI Pull (Internet Available)

```bash
uds deploy oci://ghcr.io/szl-holdings/szl-mesh:0.4.0 --confirm
```

---

## Deploy Order

The bundle deploys organs in this order (defined in `uds-bundle.yaml`):

```
1. szl-a11oy     ← governance gate; must be first (other organs depend on its receipt substrate)
2. szl-sentra    ← policy immune system
3. szl-amaru     ← memory cortex
4. szl-rosie     ← operator console
5. szl-killinchu ← counter-UAS (last; depends on policy verdicts from sentra)
```

---

## Verify After Deploy

```bash
# 1. Check all 5 namespaces exist
kubectl get namespaces | grep szl-

# 2. Wait for all deployments to be Available
for ns in szl-a11oy szl-sentra szl-amaru szl-rosie szl-killinchu; do
  echo "=== $ns ==="
  kubectl wait --for=condition=Available deploy -n $ns --all --timeout=120s
done

# 3. Check UDS Package CRs reconciled by UDS Operator
kubectl get packages -A | grep szl-

# 4. Health checks
kubectl port-forward -n szl-a11oy svc/a11oy 8080:8080 &
curl -sf http://localhost:8080/api/a11oy/healthz && echo "a11oy OK"
kill %1

kubectl port-forward -n szl-killinchu svc/killinchu 7860:7860 &
curl -sf http://localhost:7860/api/killinchu/healthz && echo "killinchu OK"
kill %1

# 5. Verify cosign signature (supply chain proof)
cosign verify ghcr.io/szl-holdings/szl-mesh:0.4.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
# Expected: Verified OK

# NOTE: the BUNDLE itself is cosign-SIGNED but does NOT yet carry a GitHub build-provenance
# attestation (the CI attest step needs org-level attestations:write). Verify the SIGNATURE
# (above) for the bundle; the slsa.dev/provenance/v0.2 ATTESTATIONS live on the 5 ORGAN IMAGES:
#   cosign verify-attestation --type slsaprovenance ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
#     --certificate-identity-regexp='^https://github.com/szl-holdings/' \
#     --certificate-oidc-issuer='https://token.actions.githubusercontent.com'
```

---

## Airgap Notes

- All 5 organ images are baked into the `.tar.zst` at CI create time — no external pull at deploy time.
- Zarf rewrites image refs from `ghcr.io/szl-holdings/...` to the Zarf internal registry before pods start.
- Cosign signature verification (`cosign verify`) DOES require internet access (Rekor transparency log). In full airgap, skip the verify step or pre-cache the Rekor entry.
- NTP/clock sync: cosign timestamp validation can fail if the cluster clock is skewed by more than ~5 minutes. Validate time sync before deploy in airgap:

```bash
# On cluster nodes, ensure clock is within 5 minutes of actual time:
timedatectl status | grep "NTP synchronized"
# or manually: date -u
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ImagePullBackOff` on any organ | Zarf internal registry not running (Zarf init not done) | Run `uds zarf package deploy oci://defenseunicorns/uds-k3d:0.14.0 --confirm` or ensure UDS Core was deployed first |
| UDS Package CR stuck in `Pending` | Pepr UDS Operator not running | `kubectl get pods -n pepr-system` — ensure all pods Running |
| `Connection refused` on health check | Pod not yet Ready (rosie/killinchu load models at startup) | Wait 60–120s and retry |
| `certificate verify failed` on cosign | Clock skew or no internet for Rekor | Check NTP sync; in airgap, skip verify or pre-cache |
| Keycloak SSO not provisioned | `keycloak` namespace missing from UDS Core install | Ensure UDS Core was installed with SSO component; `kubectl get ns keycloak` |
| `szl-receipts` allow rules fail | `szl-receipts-server` not deployed (deferred from bundle) | Expected — UDS Package CR has allow rules to `szl-receipts` namespace; the allow rule is permissive (no traffic flows if namespace absent) |

---

## What Is NOT In This Bundle

- **szl-receipts** (DSSE receipt server) — deferred; requires `szl-receipts-server` image to be public. See `bundles/szl-receipts/README.md`.
- **Mesh interconnect** (Istio mTLS between organs, AuthorizationPolicies) — v0.5.0 roadmap.
- **phawaq** (vessels/drone) organ — no GHCR image yet; v0.5.0.

---

## Honesty Doctrine

- Organs = SLSA **L1 + L2** — every organ image is cosign keyless-signed (L1) and carries a `slsa.dev/provenance/v0.2` DSSE attestation `.att` referrer that verifies via `cosign verify-attestation --type slsaprovenance` (L2). The mesh bundle is cosign-**signed** (`.sig` present, `cosign verify` PASSES); the GitHub build-provenance **attestation on the bundle is NOT yet earned** (the CI `attest-build-provenance` step requires org-level `attestations: write`). **L3 is NOT claimed.**
- Λ = **Conjecture 1** (NEVER a theorem).
- **No Iron Bank** — organ images are not in Iron Bank registry.
- **No FedRAMP / CMMC**.
- Section 889 = exactly 5 vendors: Huawei, ZTE, Hytera, Hikvision, Dahua.
