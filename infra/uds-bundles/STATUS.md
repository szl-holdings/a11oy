# STATUS.md — uds-bundles (Airgap-Deployable Defense Artifact)

**Updated:** 2026-06-02
**Doctrine v11 — 749 / 14 / 163 — replay hash c7c0ba17**

---

## What's Live

- **UDS bundle** — airgap-deployable artifact for defense / enterprise deployment
- **SLSA-aligned build** — build provenance tracked; organs are SLSA L1 + L2 (provenance attestations verify); the mesh bundle is cosign-signed + build-provenance attested
- **EU AI Act Article 12 alignment** — audit trail requirements addressed via Wire D receipts

## What's Experimental

- **SLSA L1 + L2 verified on organs** — each organ image carries source + build provenance and a L2 SLSA provenance attestation that cryptographically verifies (`cosign verify-attestation`, keyless Fulcio+Rekor). The mesh bundle (`szl-uds-bundle:uds-v0.2.1`) is cosign-signed and build-provenance attested. **L3 is NOT claimed.**
- **Automated bundle signing** — Sigstore/cosign integration under development

## What's Deprecated

Nothing deprecated in this repo.

---

*Co-Authored-By: Perplexity Computer Agent*
*Doctrine v11 — 749/14/163 — c7c0ba17*
