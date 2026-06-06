# FOUNDER DEPLOY QUICKSTART — SZL UDS Bundles

**Date:** 2026-06-01 · **Author:** Yachay (SZL CTO) · **License:** Apache-2.0
**Doctrine v11 LOCKED:** 749/14/163 · 13-axis yuyay_v3 · replay `bacf5443…631fc5`

This is the one-page runbook to turn the **staged** bundles into **real, signed,
airgap-deployable** artifacts on any host where docker is up and the binaries load.

## 0. Prereqs (all confirmed present on disk; need a healthy build host)
```bash
docker info            # daemon must be UP
zarf version           # v0.51.0 ok
cosign version         # Sigstore v2
syft version; kind version; helm version; kubectl version --client
export COSIGN_PASSWORD=""   # SZL key passphrase is empty
```
Get the sources (either is fine — identical content):
```bash
# A) GitHub
gh repo clone szl-holdings/uds-bundles && cd uds-bundles/uds-bundles
# B) Hugging Face
huggingface-cli download SZLHOLDINGS/uds-bundles-v1 --repo-type dataset --local-dir uds && cd uds/uds_productionization
```

## 1. Build images + Zarf packages + SBOM + SIGN + verify (one command)
```bash
COSIGN_KEY=/path/to/.secret/cosign_signing_key.key \
COSIGN_PUB=/path/to/.secret/cosign_signing_key.pub \
bash build_sign_all.sh 2>&1 | tee BUILD_RUN.log
```
Produces in `artifacts/`:
- `zarf-package-<name>-amd64-0.3.1.tar.zst` × 5  (REAL Zarf packages)
- `<flagship>.uds.sig` × 5  (cosign signatures, offline)
- `<flagship>.sbom.spdx.json` × 5  (syft SBOM)
- `SHA256SUMS.txt`  (sha256 of every artifact)
The script also runs `cosign verify-blob` (→ *Verified OK*) and `zarf package inspect`
on each — that is your signature + inspect proof.

## 2. Deploy under real UDS Core (production)
```bash
# Install UDS Core (slim dev or full) per https://uds.defenseunicorns.com/
uds deploy k3d-core-slim-dev:0.41.0 --confirm     # or full core bundle
# Deploy each flagship bundle in mesh order:
for f in a11oy amaru sentra killinchu rosie; do
  ( cd PER_BUNDLE/$f && uds create . --confirm && \
    uds deploy uds-bundle-$f-amd64-0.3.1.tar.zst --confirm )
done
# Or the combined bundle:
( cd PER_BUNDLE/szl-crew-full-stack && uds create . --confirm && \
  uds deploy uds-bundle-szl-crew-amd64-0.3.1.tar.zst --confirm )
```

## 3. Airgap test (kind, no internet at deploy)
```bash
bash airgap_test.sh 2>&1 | tee AIRGAP_RUN.log
# Expect: rollout Available + /healthz 200 for all 5; mesh smoke a11oy->...->rosie GREEN.
```

## 4. Push images to GHCR (founder/CI action — needs write:packages)
The sandbox token lacks `write:packages`, so do this from CI or a PAT-scoped shell:
```bash
echo $GHCR_PAT | docker login ghcr.io -u <user> --password-stdin
for f in a11oy amaru sentra killinchu rosie; do
  docker push ghcr.io/szl-holdings/$f:uds-v0.3.1
  cosign sign --key $COSIGN_KEY --tlog-upload=false --yes ghcr.io/szl-holdings/$f:uds-v0.3.1
  cosign attest --predicate artifacts/$f.sbom.spdx.json --type spdxjson \
    --key $COSIGN_KEY --tlog-upload=false --yes ghcr.io/szl-holdings/$f:uds-v0.3.1
done
```
After GHCR push, flip the per-bundle `uds-bundle.yaml` package entry from
`path: .` to `repository: ghcr.io/szl-holdings/packages/<pkg>` + `ref: 0.3.1`.

## Endpoints per flagship (smoke targets)
| Flagship | Health | Identity | Mesh probe |
|---|---|---|---|
| a11oy | /api/a11oy/healthz | /api/a11oy/v1/identity | /api/a11oy/v1/mesh |
| amaru | /api/amaru/healthz | /api/amaru/v1/identity | /api/amaru/v1/mesh |
| sentra | /api/sentra/healthz | /api/sentra/v1/identity | /api/sentra/v1/mesh |
| killinchu | /killinchu/healthz | /killinchu/identity | /killinchu/mesh |
| rosie | /api/rosie/healthz | /api/rosie/v1/identity | / (console) |

— Yachay, 2026-06-01. Real, signed, airgap-deployable once run on a healthy host.
