# SZL Killinchu · Operational UDS Drop

## WHAT THIS DOES (operational)
- Deploys in 60 seconds on UDS Core via `zarf package deploy szl-killinchu.uds.tar.zst --confirm`
- Runs air-gapped — pull the network cable, it still works
- Counter-UAS defensive application. Decodes ADS-B (pyModeS) + MAVLink (pymavlink) drone telemetry, scores threats through the defensive-only Λ-gate, signs verdicts with post-quantum ML-DSA-65.
- Every agent action emits a cosign-signed DSSE receipt
- Verify any receipt with: `cosign verify-blob --signature ... --certificate ... <blob>`

### Fills this UDS Core gap
**the mission-ready defensive application on top of UDS Core**

### Operational endpoints
- `/api/killinchu/healthz`
- `/api/killinchu/v1/* (protocol decoders: pyModeS ADS-B, pymavlink)`
- `counter-UAS Λ-gate`
- `/khipu/sign?mode={pqc,hybrid} (ML-DSA-65 FIPS 204)`
- `/api/vessels/* (preserved aliases)`

## WHAT WE'RE NOT CLAIMING
- No Iron Bank certification (not required by scope)
- Not SWFT-listed (we don't need it to work)
- Not FedRAMP authorized (we don't need it to work)
- Λ is Conjecture 1, NOT a theorem
- SLSA L1 + L2 (provenance attestation verifies via cosign verify-attestation); L3 not claimed
- 163 sorries open in the Lean kernel (disclosed, never hidden)

## WHAT WE ASK
- Run it on YOUR operational hardware for one week
- Tell us if it deserves more

## SUBSTRATE
- Doctrine v11 LOCKED 749/14/163
- Lean 4 + Mathlib v4.13.0 kernel: `github.com/szl-holdings/lutar-lean`
- Source: `github.com/szl-holdings/killinchu`
- Live HF Space: `huggingface.co/spaces/SZLHOLDINGS/killinchu`

## BUNDLE CONTENTS
| Artifact | Path |
|---|---|
| UDS Core bundle spec | `uds-bundle.yaml` |
| Zarf package def | `zarf.yaml` |
| Helm chart | `chart/` |
| SBOM (SPDX 2.3) | `sbom/killinchu.spdx.json` |
| SBOM (CycloneDX 1.4) | `sbom/killinchu.cyclonedx.json` |
| SLSA provenance (L1+L2) | `attestations/killinchu.slsa-provenance.json` |
| Cosign verify guide | `attestations/killinchu.cosign-verify.txt` |
| Pepr policies | `policies/` (namespace isolation · DSSE-receipt egress · Section 889 denylist) |

## BUILD & DEPLOY (operational, 60s)
```bash
# 1. Create the air-gap bundle (bakes image + chart + SBOM into one .tar.zst)
zarf package create . --confirm

# 2. On the operational box (cable pulled), deploy
zarf package deploy szl-killinchu.uds.tar.zst --confirm

# 3. Watch it come up
kubectl -n szl-killinchu get pods -w
```

## SECTION 889
Pepr denylist enforces exactly 5 covered vendors (FAR 52.204-25):
Huawei · ZTE · Hytera · Hikvision · Dahua. Fail-CLOSED.
