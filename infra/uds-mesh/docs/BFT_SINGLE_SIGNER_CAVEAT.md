# uds-mesh — BFT Single-Signer Caveat

**Repo:** `szl-holdings/uds-mesh`
**Document:** Architecture caveat — BFT quorum vs. single-signer implementation
**Doctrine:** v7 (strict) — no theater, honest STAGED labels
**Date:** 2026-05-30

---

## Summary

The current `uds-mesh` capstone tag is signed with a **single org dev key**.  
This is a **single-signer** implementation, not a Byzantine Fault Tolerant (BFT) multi-signer quorum.

---

## What Is Implemented (Honest)

| Mechanism | Status | Notes |
|---|---|---|
| Single org-dev-key signature on capstone tag | ✓ DONE | `uds-v0.3.0` tag signed |
| DSSE body/signature separation | ✓ DONE | PR #43 merged |
| PQC dual-sign (Dilithium + Ed25519) | ✓ DONE | `governance-receipts-pqc.ts` (PR #49) |
| SCITT-Rekor notarization | PARTIAL | scitt-adapter in bundle spec; Rekor wired partially |
| BFT 2-of-3 multi-signer quorum | NOT YET | Architecture task — see roadmap below |

---

## What Is NOT Implemented (Honest)

The README and release notes do **not** claim BFT multi-signer quorum. This document makes that explicit:

1. **Single signer**: The capstone tag (`uds-v0.3.0`) is signed by exactly one key (org dev key). A single compromised key could produce a fraudulent capstone.

2. **No threshold scheme**: There is no t-of-n threshold signature scheme, no Shamir secret sharing, and no multi-party signing ceremony implemented in this repo.

3. **Rekor live integration**: The SCITT adapter is in the bundle spec but Rekor integration is partial — not yet live-notarizing every commit.

---

## Why This Matters

In a BFT system, an attacker would need to compromise `t` out of `n` signers to forge a receipt. With a single signer, the security model degrades to: *trust this one key*.

For the current use case (internal governed AI platform, pre-Series A), single-signer is acceptable. For production external trust, multi-signer BFT is required.

---

## Roadmap to BFT

| Milestone | Description | Stage |
|---|---|---|
| `uds-v0.3.1` | Document caveat explicitly (this file) | ✓ DONE (this PR) |
| `uds-v0.3.1` | Add skeleton 2-of-3 verifier spec | Engineering |
| `uds-v0.4.0` | Implement 2-of-3 Ed25519 multi-sig skeleton | Engineering |
| `uds-v1.0.0` | Full BFT quorum with Rekor + SCITT live | Roadmap |

---

## Cross-References

- PR #46 — original caveat PR (closed; content landed here in `docs/UDS_v0.3.1_RELEASE_PLAN.md`)
- `docs/UDS_v0.3.1_RELEASE_PLAN.md` — BFT Single-Signer Caveat section
- `governance-receipts-pqc.ts` — PQC dual-sign implementation (Dilithium + Ed25519)
- `formula_receipts.py` — DSSE receipt layer (single-signer)

---

*Doctrine v7 strict — STAGED items clearly labeled — no security theater*
