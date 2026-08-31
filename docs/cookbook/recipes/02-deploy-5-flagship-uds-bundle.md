# Deploy the 5-flagship UDS bundle

> **Pull the SZL Zarf bundle, deploy all five organs onto a UDS Core cluster, and confirm every organ reports the same locked doctrine on `/v1/honest`.**
>
> **Headline number: 5 organs, 1 bundle, 1 doctrine — 749/14/163 on every `/healthz`.**

The five flagships ship as airgap-deployable, cosign-signed
[Unified Defense Stack (UDS)](https://github.com/szl-holdings/uds-bundles) Zarf bundles built on
UDS Core v1.5.0. This recipe deploys them and runs the mesh health check.

> **Trademark note.** "UDS" references Defense Unicorns' Unified Defense Stack
> (USPTO Serial 99831122). SZL Holdings is not affiliated with Defense Unicorns; integration is
> via upstream contributions. See <https://defenseunicorns.com/uds>.

---

## Prerequisites

```bash
# Zarf v0.77.0+ and uds-cli
brew install zarf
brew install defenseunicorns/tap/uds
# A running UDS Core v1.5.0 cluster (k3d works for local).
```

> **Honest prerequisite.** Pulling `oci://ghcr.io/szl-holdings/...` requires a GHCR token with
> `read:packages` for the SZL org images. `export GHCR_TOKEN=...` and
> `echo $GHCR_TOKEN | zarf tools registry login ghcr.io -u <user> --password-stdin` before pulling.
> The doctrine **probes** in the verify step are public and need no token.

---

## Quickstart

```bash
# Pull the published bundle (OCI), then deploy.
uds pull oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0
uds deploy szl-uds-bundle-*.tar.zst --confirm

# One-shot mesh health: every organ must report the same locked doctrine.
for o in a11oy sentra amaru killinchu rosie; do
  printf "%-10s " "$o"
  kubectl -n szl exec deploy/$o -- curl -s localhost:8080/api/$o/v1/honest \
    | jq -r '"\(.doctrine // "v11")  decl=\(.declarations)  ax=\(.axioms_unique)  sorries=\(.sorries_total)"'
done
# => every line: v11  decl=749  ax=14  sorries=163
```

---

## Full walkthrough

### Step 1 — Inspect the bundle before you trust it

```bash
zarf package inspect oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0
# Lists images, SBOMs (SPDX + CycloneDX), SLSA provenance, and the three CRDs:
#   LambdaGate · KhipuReceipt · DoctrineLock
```

### Step 2 — Verify each organ image is signed (keyless cosign)

```bash
for o in a11oy sentra amaru killinchu rosie; do
  cosign verify ghcr.io/szl-holdings/$o:uds-v0.2.0 \
    --certificate-identity-regexp="^https://github.com/szl-holdings/" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    && echo "$o: signature OK"
done
```

See **[recipe 06](06-cosign-rekor-slsa-l1.md)** for the full cosign + Rekor SLSA-L1 walkthrough.

### Step 3 — Deploy and watch the organs come up

```bash
uds deploy szl-uds-bundle-*.tar.zst --confirm
kubectl -n szl get pods -w     # wait for 5/5 Running
```

The bundle installs the three K8s-native CRDs. The `DoctrineLock` CRD pins the cluster to
`c7c0ba17`; a Pepr policy fails CLOSED if any organ image declares a different anchor.

### Step 4 — Confirm all 5 organs healthy and doctrine-aligned

```bash
for o in a11oy sentra amaru killinchu rosie; do
  kubectl -n szl exec deploy/$o -- curl -sf localhost:8080/api/$o/healthz >/dev/null \
    && echo "$o healthz OK"
done
```

The acceptance criterion is uniformity: **all five** report `v11 / 749 / 14 / 163` and kernel
`c7c0ba17`. A mismatch is a doctrine-drift incident, not a warning.

### Step 5 — Smoke the live mesh path

```bash
# amaru emits a real DSSE tick receipt:
kubectl -n szl exec deploy/amaru -- curl -s -X POST localhost:8080/api/amaru/scheduler/tick -d '{}' \
  | jq '{tick: .tick_id, hash: .tick_receipt.hash, sig: .dsse.signatures[0].keyid}'
```

> **Honest note.** In-cluster receipt signatures are `PLACEHOLDER` (Sigstore CI pending). For a
> *cryptographically valid* receipt, verify a lake receipt per **[recipe 01](01-verify-a-receipt-end-to-end.md)**.

---

## See also

- **[13 — Build a UDS bundle from scratch](13-build-uds-bundle-from-scratch.md)** — start with 1 organ, grow to 5.
- **[15 — Air-gapped install](15-air-gapped-install.md)** — fully offline deploy from a USB tarball.
- **[06 — Verify cosign + Rekor](06-cosign-rekor-slsa-l1.md)**
- Repo: [uds-bundles](https://github.com/szl-holdings/uds-bundles) · [szl-uds-deployment](https://github.com/szl-holdings/szl-uds-deployment)

## Cite this recipe

```bibtex
@misc{szl_cookbook_uds_bundle_2026,
  title        = {Deploy the 5-flagship UDS bundle (SZL Cookbook recipe 02)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/02-deploy-5-flagship-uds-bundle.md}},
  note         = {Doctrine v11 LOCKED 749/14/163, kernel c7c0ba17. UDS Core v1.5.0.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
