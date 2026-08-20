# What is honest right now — Doctrine v11

**lutar-lean @ tag `lutar-v18.0.0` / c7c0ba17:**

- **749 declarations · 14 unique axioms (15 raw, 1 dup) · 163 tracked sorries** (112 baseline + 51 Putnam). `lake build` clean.
- **Λ uniqueness is a Conjecture**, not a closed theorem — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
- **Wires:** Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are **LIVE on main**; Wire D (W3C traceparent across the mesh) is **NOT YET IMPLEMENTED**.
- **SLSA: L1 (honest)** — previously mis-claimed as L3; corrected in platform PR #235.
- **Receipts:** DSSE envelopes ship from the amaru tick endpoint today; Sigstore CI signing is **PENDING** — signature fields labeled "PLACEHOLDER — signing not yet wired into CI".
- **Axioms:** A2 = `IsHomogeneous` (positive homogeneity deg 1); A4 = `IsBounded` (bounded by max axis). v3 Zenodo proofs (10.5281/zenodo.19983066) do NOT carry over to current A2/A4.
- Aligned with **EU AI Act Article 12** + **NIST AI RMF (MANAGE)**.
