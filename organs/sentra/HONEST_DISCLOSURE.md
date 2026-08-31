# What is honest right now — Doctrine v10

**lutar-lean @ tag `lutar-v18.0.0` / c7c0ba17:**

- **749 declarations · 14 unique axioms (15 raw, 1 dup) · 163 tracked sorries** (112 baseline + 51 Putnam). `lake build` clean.
- **Λ uniqueness is a Conjecture**, not a closed theorem — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
- **Wires:** Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are **LIVE on main**; Wire D (W3C traceparent across the mesh) is **NOT YET IMPLEMENTED**.
- **SLSA: L1 (honest)** — previously mis-claimed as L3; corrected in platform PR #235.
- **Receipts:** DSSE envelopes ship from the amaru tick endpoint today; Sigstore CI signing is **PENDING** — signature fields labeled "PLACEHOLDER — signing not yet wired into CI".
- **Axioms:** A2 = `IsHomogeneous` (positive homogeneity deg 1); A4 = `IsBounded` (bounded by max axis). v3 Zenodo proofs (10.5281/zenodo.19983066) do NOT carry over to current A2/A4.
- Aligned with **EU AI Act Article 12** + **NIST AI RMF (MANAGE)**.

---

## Immune Gate — Current Implementation (June 2026)

### sentra immune v1 ( and )

sentra immune v1 uses a 6-pattern keyword allowlist (DROP TABLE, rm -rf, <script, eval(, subprocess, ../../etc) with known bypasses. **Do not rely on v1 for production deny-by-default.**

Specifically, v1:
- Is **NOT** deny-by-default — all inputs not matching 6 patterns are allowed through
- Is **NOT** an 8-gate architecture — the UI description is aspirational product roadmap
- Is **trivially bypassed** by uppercase variants (), base64 encoding, Unicode normalization, or any threat not in the 6-pattern list
- Has no entropy check, no action schema validation, no replay protection, no payload digest verification

This gap was identified in the June 2026 PhD AI Safety audit and is documented here per the honesty doctrine.

### sentra immune v2 ()

sentra immune v2 is in pilot — real 8 gates per the [AI Safety 7-day fix plan](https://github.com/szl-holdings/sentra/blob/main/HONEST_DISCLOSURE.md):

| Gate | Name | Description |
|---|---|---|
| G1 | Size guard | Reject payloads > 500 KB |
| G2 | Structural integrity | JSON dict shape validation (depth, key count) |
| G3 | Recursive pattern scan | Threat patterns across all string fields |
| G4 | Base64 decode-and-rescan | Detect encoded bypass attempts (embedded in G3) |
| G5 | Entropy check | Flag high-entropy strings (potential exfil payloads) |
| G6 | Action schema validation | Known action vocab only — deny-by-default |
| G7 | Payload digest verification | SHA3-256 content-addressed integrity (if digest provided) |
| G8 | Auth claim + rate limit + replay | Nonce window + token bucket; DSSE format check |

**Honest v2 limitations:**
- G8 authorization claim: validates format only; full Sigstore/DSSE verification is pending (CI not yet wired — PLACEHOLDER)
- Rate-limit and nonce store are in-memory per-process; reset on container restart
- v2 is pilot — not yet the production gate for all mesh traffic
- v1 route is preserved unchanged (ADDITIVE)

Source:  · Doctrine v11 LOCKED 749/14/163 · SLSA L1 honest
