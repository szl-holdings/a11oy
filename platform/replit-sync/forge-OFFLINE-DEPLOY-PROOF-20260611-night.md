# FORGE ORDER — Offline (air-gap) deploy proof for the signed UDS bundle
**From:** CTO/PM agent (founder green-lit, autonomous) · **To:** Forge · June 11 2026, ~11:25 PM EDT, T-5.
**Why this is the #1 Day-3 outbrief artifact:** Warhacker scores air-gap / cloud→edge deployability. We can already PROVE published + cosign-signed; the one honest gap our own UI names is "end-to-end offline deploy proven on the tower, not in this browser." Closing it is the strongest possible demo.

## What I already did this session (no action needed from you on these)
- Bumped `bundles/szl-uds-bundle/uds-bundle.yaml` → version **0.3.0**, aligned all 5 member refs to 0.3.0 (a11oy was already 0.3.0; sentra/amaru/killinchu/rosie 0.2.0→0.3.0). Static guards GREEN (commit `cf2a3d7c`).
- Cut git tag **`uds-v0.3.0`** → `UDS Bundle Publish` workflow ran **success**. The unified bundle is now PUBLISHED + cosign-SIGNED:
  - `oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.3.0` (also `:latest`), manifest **`sha256:b2e4980f24fa55a09332595def5cc4e63388bbbab27314915f393085ab9de4b5`**, `.sig` present.
- a11oy live **Deploy Posture** tab now points its "unified mesh bundle" entry at this signed `uds-v0.3.0` digest (digest-pinned; live GHCR match).
- Re-dispatched `Prove Bundle Install` (organ=all) against the published bundle (the earlier auto-run failed only due to a publish race — it ran before the bundle existed).

## What I need Forge to run on the tower (UDS/zarf toolchain + a real node)
This is environment-gated — it needs `uds`/`zarf`/`cosign` + a k3d/k3s node + a true network-cut, which a browser/cloud agent cannot do. Run it and capture the terminal output as the outbrief evidence clip:

1. **Pull + verify the SIGNED bundle (supply-chain gate a customer runs):**
   ```
   cosign verify \
     --certificate-identity-regexp="https://github.com/szl-holdings/.*" \
     --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
     oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.3.0
   uds pull oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.3.0
   ```
2. **CUT THE CABLE** (disable egress / pull the NIC) to prove true air-gap.
3. **Deploy offline from the local tarball** onto a clean k3d/k3s node:
   ```
   zarf init --confirm           # or your core-base bring-up
   uds deploy <local-bundle-tarball> --confirm
   ```
   Assert at least one member Deployment reaches `Available` with the cable still pulled.
4. **Capture:** the `cosign verify` PASS line, the `uds deploy` success, and `kubectl get deploy -A` showing Available — that triple is the Day-3 "signed bundle, pulled, verified, deployed with the cable pulled" proof.

## Honesty constraints (doctrine)
- Keep the honest framing: "individually deployable + pull + signature-verified," NOT "all five organs co-resident/boot together" (the constrained single node can't host all five — our doctrine already says this). Prove deployability + pull + signature, not co-residency.
- Don't claim SLSA L3/FedRAMP/IronBank/CMMC/ATO without "roadmap." Bundle provenance = the cosign signature (real); a separate bundle-level SLSA attestation is NOT claimed.
- If `Prove Bundle Install` (CI, k3d) is enough evidence on its own, capture that run's logs instead — but the cable-pulled tower run is the more convincing demo.

## Remaining founder-gated (still NOT auto-done)
- Rekor transparency-log explicit public-verify step in the proof.
- warn→enforce policy transition; MAJOR dep bumps.
