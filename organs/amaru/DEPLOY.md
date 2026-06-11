# Amaru — Deploy Guide

**Doctrine v11 LOCKED** · 749/14/163 · Λ = Conjecture 1 (NOT a theorem)
**SLSA L1 honest** (cosign-signed GHCR image; L2 build-provenance attestation is roadmap via Wire D — NOT yet earned: `cosign verify-attestation --type slsaprovenance` returns "no matching attestations")
Not claimed: L3, FedRAMP, Iron Bank, CMMC.

---

## 1. Quick UDS Bundle Deploy (Warhacker)

```bash
# Full mesh bundle (a11oy + sentra + amaru + rosie + killinchu)
uds-cli bundle deploy szl-mesh-v0.4.0.tar.zst --confirm
```

This deploys all 5 flagships into the `szl-mesh:v0.4.0` bundle running in
Defense Unicorns' existing UDS Core cluster. No BYOC tower required.

---

## 2. Standalone Amaru Zarf Package

```bash
# Build
zarf package create deploy/ --confirm

# Deploy (standalone)
zarf package deploy zarf-package-amaru-amd64-uds-v0.2.0.tar.zst --confirm
```

Image: `ghcr.io/szl-holdings/amaru:uds-v0.2.0` (public GHCR)

---

## 3. SLSA L1 Verification (L2 attestation roadmap — not yet earned)

```bash
# Verify cosign signature on the GHCR image
cosign verify ghcr.io/szl-holdings/amaru:uds-v0.2.0 \
  --certificate-identity-regexp='https://github.com/szl-holdings/amaru/.*' \
  --certificate-oidc-issuer='https://token.actions.githubusercontent.com'

# Verify SLSA provenance attestation
cosign verify-attestation ghcr.io/szl-holdings/amaru:uds-v0.2.0 \
  --type slsaprovenance \
  --certificate-identity-regexp='https://github.com/szl-holdings/amaru/.*' \
  --certificate-oidc-issuer='https://token.actions.githubusercontent.com'
```

Rekor logIndex: 1713162450 (bundle :0.4.0)

---

## 4. Post-Deploy Verification

```bash
BASE=https://szlholdings-amaru.hf.space  # or your UDS ingress

# Health
curl $BASE/healthz

# Cited answer
curl -X POST $BASE/api/amaru/v1/reason \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the PAC-Bayes bound?","citations":["https://arxiv.org/abs/2309.11495"]}'

# Confidence scorer
curl -X POST $BASE/api/amaru/v1/confidence \
  -H "Content-Type: application/json" \
  -d '{"question":"PAC-Bayes?","answer":"See https://arxiv.org/abs/2309.11495"}'

# Retrieval eval
curl -X POST $BASE/api/amaru/v1/eval \
  -H "Content-Type: application/json" \
  -d '{"question":"PAC-Bayes","answer":"bound","chunks":["PAC-Bayes theorem bounds generalization error"]}'

# Formula registry
curl $BASE/api/amaru/v1/formulas/index

# LLM models (a11oy-parity roster)
curl $BASE/api/amaru/v1/llm/models

# Parity matrix
curl $BASE/api/amaru/v1/parity

# 13-tab cortex console
open $BASE/cortex-console
```

---

## 5. UDS Mesh Invariant

Receipt continuity: `receipts.in ≡ receipts.out`

Wire E (cortex-subscribe SSE) streams brand-decision events from a11oy to amaru.
Wire F (receipts/ingest) ingests gate-decision receipts into the Khipu Merkle DAG.
Cross-Space OTLP broker is roadmap (documented in `org_roadmap_synthesis.md`).

---

## 6. Honesty Doctrine

| Claim | Status |
|-------|--------|
| SLSA L1 | ✅ Met — cosign-signed GHCR image, Rekor-logged (verify via `cosign verify`) |
| SLSA L2 | ⬜ Roadmap via Wire D — NOT yet earned (`cosign verify-attestation --type slsaprovenance` returns "no matching attestations") |
| SLSA L3 | ❌ Not claimed |
| FedRAMP | ❌ Not claimed |
| Iron Bank | ❌ Not claimed |
| CMMC | ❌ Not claimed |
| Λ = Theorem | ❌ Conjecture 1 only (open CAUCHY_ND sorry) |
| Λ = Conjecture 1 | ✅ Honest |
| 749/14/163 @ c7c0ba17 | ✅ Locked |
| PROVED = {F1,F4,F7,F11,F12,F18,F19,F22} | ✅ Canonical |
| F23 = Conjecture 1 | ✅ Open bounty, NOT a theorem |

Doctrine v11 LOCKED. HONESTY OVER CHECKLIST.

Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
