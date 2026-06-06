# What is honest right now — Doctrine v10

**lutar-lean @ tag `lutar-v18.0.0` / c7c0ba17:**

- **749 declarations · 14 unique axioms (15 raw, 1 dup) · 163 tracked sorries** (112 baseline + 51 Putnam). `lake build` clean.
- **Λ uniqueness is a Conjecture**, not a closed theorem — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
- **Wires:** Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are **LIVE on main**; Wire D (W3C traceparent across the mesh) is **NOT YET IMPLEMENTED**.
- **SLSA: L1 (honest)** — previously mis-claimed as L3; corrected in platform PR #235.
- **Receipts:** DSSE envelopes ship from the amaru tick endpoint today; Sigstore CI signing is **PENDING** — signatures labeled "PLACEHOLDER — signing not yet wired into CI".
- **Axioms:** A2 = `IsHomogeneous` (positive homogeneity deg 1); A4 = `IsBounded` (bounded by max axis). v3 Zenodo proofs (10.5281/zenodo.19983066) do NOT carry over.
- Aligned with **EU AI Act Article 12** + **NIST AI RMF (MANAGE)**.

---

## HMAC Receipt Verification (added 2026-06-03)

rosie receipt verification uses HMAC-SHA256 with a key loaded from the
`ROSIE_HMAC_KEY` environment variable (HF Space secret).

**Without the secret, verification is INFORMATIONAL ONLY (PLACEHOLDER mode).**

Specifically:
- If `ROSIE_HMAC_KEY` is set: `DEV_HMAC_KEY` is loaded from the env var.
  Verification proves "signed by someone holding the injected key."
- If `ROSIE_HMAC_KEY` is **not** set: `DEV_HMAC_KEY = b""` (empty placeholder).
  `verify_envelope()` returns `TAMPERED` with an explicit PLACEHOLDER message.
  No receipt can be declared `VALID` without the key — this is fail-closed.

**Previous state (fixed):** The key `b"szl-amaru-dev-hmac-key-v1-not-for-production"`
was hardcoded in public source. Anyone reading the repo could forge receipts that
passed rosie's verifier. This was identified by PhD AI Safety audit
(PER_FLAGSHIP_SAFETY_AUDIT.md §4) and is now corrected.

## Shared-Key Requirement — CRITICAL

> **HMAC is a symmetric shared-secret scheme.** The signer (a11oy) and the
> verifier (rosie) MUST use the **same secret value**.

The environment variable names differ by design for per-repo clarity:
- a11oy uses `A11OY_HMAC_KEY`
- rosie uses `ROSIE_HMAC_KEY`

**However, the VALUES injected into both variables MUST be identical** — the
same 32+ byte secret, injected into each HF Space independently.

A mismatch means **rosie will mark every real a11oy receipt as TAMPERED**, even
though the receipts are cryptographically correct. There is no error message
that distinguishes a key mismatch from genuine tampering — both produce the same
`TAMPERED` verdict from the verifier.

### Deployment Checklist

1. Generate a single strong secret: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. Inject the **same value** as `A11OY_HMAC_KEY` into the a11oy HF Space secrets.
3. Inject the **same value** as `ROSIE_HMAC_KEY` into the rosie HF Space secrets.
4. Rotate both simultaneously if the key is ever compromised.

### UI Banner

The Receipt Verifier tab in the Gradio UI displays:

> ⚠️ **Receipts verified with HMAC — shared-key scheme.** `ROSIE_HMAC_KEY`
> (rosie) and `A11OY_HMAC_KEY` (a11oy) must hold the **same secret value**.
> If `ROSIE_HMAC_KEY` is PLACEHOLDER or mismatches, all real a11oy receipts
> will appear TAMPERED. Inject matching keys into both HF Spaces.

### Action Required

The founder must inject `ROSIE_HMAC_KEY` (rosie) and `A11OY_HMAC_KEY` (a11oy)
as HF Space secrets **with the same value**. Until then, the verifier operates
in PLACEHOLDER mode (fail-closed: no false VALID verdicts).

### Files Changed

- `src/console/receipt_verifier.py` — env-var key lookup + PLACEHOLDER guard
- `app.py` — env-var key lookup + UI banner on Receipt Verifier tab (updated: shared-key warning)

### Cross-References

- [PER_FLAGSHIP_SAFETY_AUDIT.md §4](../phd-ai-safety/PER_FLAGSHIP_SAFETY_AUDIT.md)
- [RECEIPT_CHAIN_AS_SAFETY_PRIMITIVE.md](../phd-ai-safety/RECEIPT_CHAIN_AS_SAFETY_PRIMITIVE.md)
- [a11oy HONEST_DISCLOSURE.md](https://github.com/szl-holdings/a11oy/blob/main/HONEST_DISCLOSURE.md): Signer-side disclosure

---

*Signed-off-by: Yachay <yachay@szlholdings.ai>*  
*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
