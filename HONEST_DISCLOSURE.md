# HONEST_DISCLOSURE — a11oy Receipt Signing

**Doctrine:** v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap  
**Date:** 2026-06-03

## HMAC Receipt Signing

a11oy receipt signing uses HMAC-SHA256 with a key loaded from the `A11OY_HMAC_KEY`
environment variable (HF Space secret).

**Without the secret, signatures are PLACEHOLDER (non-repudiation=false).**

Specifically:
- If `A11OY_HMAC_KEY` is set: receipts are signed with HMAC-SHA256 under that key.
  This is a *symmetric* MAC — it proves "signed by someone holding the key," not
  non-repudiation. Non-repudiation requires asymmetric signing (ECDSA/DSSE);
  see `szl_dsse.py` for the asymmetric layer.
- If `A11OY_HMAC_KEY` is **not** set: the `sig` field in DSSE receipts is a
  `PLACEHOLDER:<sha256-of-PAE>` string, clearly labeled. The receipt chain
  integrity (SHA3-256 hash chain) is real and verifiable; only the HMAC
  authentication layer is absent.

## Why HMAC, not ECDSA?

The ECDSA layer (`szl_dsse.py`) requires `SZL_COSIGN_PRIVATE_PEM` and is the
production non-repudiation path. The HMAC layer in `szl_receipt_substrate.py`
is a lightweight gate-evaluation receipt for in-process threshold policy
verification — faster than asymmetric signing for the high-frequency policy
path.

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

## Action Required

The founder must inject `A11OY_HMAC_KEY` (a11oy) and `ROSIE_HMAC_KEY` (rosie)
as HF Space secrets **with the same value** before the HMAC receipt layer
provides any authentication guarantee. The PLACEHOLDER behavior is a deliberate
fail-safe, not a silent failure.

## Cross-References

- `szl_receipt_substrate.py`: HMAC signing implementation (env-var path)
- `szl_dsse.py`: ECDSA-P256 DSSE asymmetric signing layer
- `szl_khipu.py`: SHA3-256 hash chain (tamper-evident, works without secrets)
- [RECEIPT_CHAIN_AS_SAFETY_PRIMITIVE.md](../phd-ai-safety/RECEIPT_CHAIN_AS_SAFETY_PRIMITIVE.md): Gap analysis
- [rosie HONEST_DISCLOSURE.md](https://github.com/szl-holdings/rosie/blob/main/HONEST_DISCLOSURE.md): Verifier-side disclosure

---

*Signed-off-by: Yachay <yachay@szlholdings.ai>*  
*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
