# HONEST_DISCLOSURE — a11oy Receipt Signing

**Doctrine:** v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1 honest  
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

## Action Required

The founder must inject `A11OY_HMAC_KEY` as an HF Space secret before the
HMAC receipt layer provides any authentication guarantee. The PLACEHOLDER
behavior is a deliberate fail-safe, not a silent failure.

## Cross-References

- `szl_receipt_substrate.py`: HMAC signing implementation (env-var path)
- `szl_dsse.py`: ECDSA-P256 DSSE asymmetric signing layer
- `szl_khipu.py`: SHA3-256 hash chain (tamper-evident, works without secrets)
- [RECEIPT_CHAIN_AS_SAFETY_PRIMITIVE.md](../phd-ai-safety/RECEIPT_CHAIN_AS_SAFETY_PRIMITIVE.md): Gap analysis

---

*Signed-off-by: Yachay <yachay@szlholdings.ai>*  
*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
