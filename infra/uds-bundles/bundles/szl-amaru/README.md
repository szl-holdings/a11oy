# SZL Amaru · Operational UDS Drop

## WHAT THIS DOES (operational)
- Deploys in 60 seconds on UDS Core via `zarf package deploy szl-amaru.uds.tar.zst --confirm`
- Runs air-gapped — pull the network cable, it still works
- 13-axis memory cortex. Each decision is hashed into a Khipu DAG and sealed with a DSSE/cosign receipt — an append-only signed chain of decisions.
- Every agent action emits a cosign-signed DSSE receipt
- Verify any receipt with: `cosign verify-blob --signature ... --certificate ... <blob>`

### Fills this UDS Core gap
**adds signed-decisions chain UDS Core lacks**

### Operational endpoints
- `/api/amaru/healthz`
- `/api/amaru/v1/rag`
- `/api/amaru/v1/* (cortex)`
- `/conduit/ (React SPA)`
- `/upgrades`

## WHAT WE'RE NOT CLAIMING
- No Iron Bank certification (not required by scope)
- Not SWFT-listed (we don't need it to work)
- Not FedRAMP authorized (we don't need it to work)
- Λ is Conjecture 1, NOT a theorem
- SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap
- 163 sorries open in the Lean kernel (disclosed, never hidden)

## WHAT WE ASK
- Run it on YOUR operational hardware for one week
- Tell us if it deserves more

## SUBSTRATE
- Doctrine v11 LOCKED 749/14/163
- Lean 4 + Mathlib v4.13.0 kernel: `github.com/szl-holdings/lutar-lean`
- Source: `github.com/szl-holdings/amaru`
- Live HF Space: `huggingface.co/spaces/SZLHOLDINGS/amaru`

## BUNDLE CONTENTS
| Artifact | Path |
|---|---|
| UDS Core bundle spec | `uds-bundle.yaml` |
| Zarf package def | `zarf.yaml` |
| Helm chart | `chart/` |
| SBOM (SPDX 2.3) | `sbom/amaru.spdx.json` |
| SBOM (CycloneDX 1.4) | `sbom/amaru.cyclonedx.json` |
| SLSA provenance (SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap) | `attestations/amaru.slsa-provenance.json` |
| Cosign verify guide | `attestations/amaru.cosign-verify.txt` |
| Pepr policies | `policies/` (namespace isolation · DSSE-receipt egress · Section 889 denylist) |

## BUILD & DEPLOY (operational, 60s)
```bash
# 1. Create the air-gap bundle (bakes image + chart + SBOM into one .tar.zst)
zarf package create . --confirm

# 2. On the operational box (cable pulled), deploy
zarf package deploy szl-amaru.uds.tar.zst --confirm

# 3. Watch it come up
kubectl -n szl-amaru get pods -w
```

## SECTION 889
Pepr denylist enforces exactly 5 covered vendors (FAR 52.204-25):
Huawei · ZTE · Hytera · Hikvision · Dahua. Fail-CLOSED.
