# a11oy 🔬 — governed agentic execution across **749 declarations · 14 axioms · 46 policy gates**
> Policy + receipt substrate: every action signed, every decision gated, every receipt verifiable.

[Live Space](https://szlholdings-a11oy.hf.space) · [Docs](https://docs.szlholdings.com/flagships/a11oy) · [Verify](#verify-in-2-minutes) · [API](#api-surface) · [Doctrine](#doctrine) · [Citation](#citation)

![doctrine-v11](https://img.shields.io/badge/doctrine-v11%20LOCKED-0B1F3A) ![SLSA-L1-L2](https://img.shields.io/badge/SLSA-L1%20%2B%20L2%20attested-2C5F2D) ![DCO](https://img.shields.io/badge/DCO-required-555) ![CI](https://img.shields.io/badge/CI-green-2C5F2D) ![Scorecard](https://img.shields.io/badge/OpenSSF-Scorecard-informational) ![License](https://img.shields.io/badge/license-Apache--2.0-blue)

> **Honest status line:** Doctrine v11 · 749 / 14 / 163 · Λ = **Conjecture 1** (NOT a theorem) · SLSA **L1 (honest) + L2 build provenance attested** · Apache-2.0.

## Live
- **Space:** https://szlholdings-a11oy.hf.space
- **Docs:** https://docs.szlholdings.com/flagships/a11oy
- **Release:** [v1.0.0](https://github.com/szl-holdings/a11oy/releases/tag/v1.0.0)

## What it does
- **Policy + receipt substrate** — `/v1/policy/evaluate`, `/v1/verify`, `/v1/ledger`: one hash-chained substrate, deny by default.
- **Honest disclosure endpoint** — `/v1/honest` reports the live doctrine posture (749/14/163, Λ = Conjecture 1, SLSA L1 + L2).
- **Brand-orchestration gates** — governed-loop primitive with deterministic replay and hard-stop validators.

## Verify (in 2 minutes)
<a id="verify-in-2-minutes"></a>

```bash
# 1. Confirm the live doctrine posture on the running Space.
#    (Live-verified: this field is present in /v1/honest for a11oy.)
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest | jq .kernel_commit
# => "c7c0ba17"

# 2. Verify the signed UDS container artifact (cosign keyless OIDC).
#    Match the tag to the latest release asset; signing is keyless via the
#    GitHub Actions OIDC issuer.
cosign verify ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# 3. Inspect the public transparency-log entry for this image (Sigstore Rekor).
#    Image digest: sha256:7301a4…ab88
#    Rekor log index: 1710355173
rekor-cli get --log-index 1710355173
# Or open in a browser: https://search.sigstore.dev/?logIndex=1710355173
```

> Honest note: DSSE/Sigstore CI signing is being wired (receipt signatures are
> labelled `PLACEHOLDER` until CI signing lands). The `/v1/honest` check above is
> the authoritative live doctrine probe.

**Public proof:** cosign keyless cert (Fulcio) + Rekor transparency log entry
[`#1710355173`](https://search.sigstore.dev/?logIndex=1710355173) for image `ghcr.io/szl-holdings/a11oy:uds-v0.2.0` (`sha256:7301a4…ab88`).

## Architecture

```mermaid
flowchart LR
  Op[Operator] --> A[a11oy substrate]
  A -->|policy/evaluate| G[Λ-gate]
  G -->|verdict| L[(Proof ledger)]
  L -->|hash-chain| R[Receipt]
  A -->|verify| R
```

## API surface

| Endpoint | Method | Description |
|---|---|---|
| `/api/a11oy/healthz` | GET | Liveness probe |
| `/api/a11oy/readyz` | GET | Readiness probe |
| `/api/a11oy/v1/honest` | GET | Doctrine disclosure (JSON) |
| `/api/a11oy/v1/version` | GET | Build + version metadata |
| `/api/a11oy/v1/ledger` | GET | Proof ledger |
| `/api/a11oy/v1/verify` | POST | Chain verification |
| `/api/a11oy/v1/policy/evaluate` | POST | Policy gate |

The full, canonical endpoint list is on the [docs site](https://docs.szlholdings.com/flagships/a11oy) and the [API reference](https://docs.szlholdings.com/api/).

## Doctrine
- **Doctrine v11 LOCKED** — 749/14/163 · kernel `c7c0ba17` (never bumped)
- **Λ = Conjecture 1** (NOT a theorem) — depends on the open CAUCHY_ND sorry + a missing symmetry axiom
- **SLSA L1 + L2 build provenance attested** · **Section 889 = exactly 5 vendors** (Huawei, ZTE, Hytera, Hikvision, Dahua)
- No Iron Bank / FedRAMP / CMMC / SWFT / Mission Owner claims

## License + DOI

- **License:** Apache-2.0 (OSS across all SZL Holdings repos).
- **Concept DOI:** [`10.5281/zenodo.20434276`](https://doi.org/10.5281/zenodo.20434276) — cite the archived release on Zenodo.

## Citation

```bibtex
@software{szl_a11oy_2026,
  author    = {Lutar, Stephen P.},
  title     = {a11oy: Governed agentic execution fabric},
  year      = {2026},
  publisher = {SZL Holdings},
  version   = {v1.0.0},
  url       = {https://github.com/szl-holdings/a11oy},
  doi       = {10.5281/zenodo.20434276},
  note      = {Doctrine v11 LOCKED 749/14/163, kernel c7c0ba17}
}
```

## SLSA L2 build provenance (verify)

Every `ghcr.io/szl-holdings/a11oy` image ships a signed in-toto **SLSA provenance v1**
attestation (`actions/attest-build-provenance@v2`), discoverable on the public Sigstore
Rekor transparency log and pushed to the registry alongside the image.

```bash
# Resolve the image digest, then verify provenance against the source repo:
slsa-verifier verify-image \
  ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --source-uri github.com/szl-holdings/a11oy \
  --source-tag main

# Or with GitHub's native tooling:
gh attestation verify oci://ghcr.io/szl-holdings/a11oy:uds-v0.2.0 --owner szl-holdings
```

SLSA L2 = hosted build platform (GitHub Actions) + signed provenance available to consumers.
L3 is **not** claimed (requires a hardened, isolated build environment).

## Try it

```bash
# Live, no install — probe the running Space:
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest | jq .

# Sovereign / air-gapped — run the signed container locally:
docker run --rm -p 7860:7860 ghcr.io/szl-holdings/a11oy:uds-v0.2.0
#   → open http://localhost:7860  ·  GET /api/a11oy/v1/honest  ·  GET /api/health
```

## Where a11oy runs

| Surface | Where | Role |
|---|---|---|
| Live demo | [szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space) | Docker HF Space (SPA + `/api/a11oy/*` + `/honest`) |
| Signed image | `ghcr.io/szl-holdings/a11oy:uds-v0.2.0` | GHCR, SLSA L2 attested · cosign keyless |
| Air-gap bundle | `artifacts/a11oy-uds/` (UDS / Zarf) | Sovereign deploy, offline-verifiable |
| Archived release | [Zenodo `10.5281/zenodo.20434276`](https://doi.org/10.5281/zenodo.20434276) | Citable concept DOI |

## Built with / learned from

We cite who we learned from. a11oy's **publication shell** — number-in-the-hook,
above-the-fold quickstart, always-on BibTeX, signed-release discipline — adapts patterns
from [The Well](https://github.com/PolymathicAI/the_well) and [Walrus](https://github.com/PolymathicAI/walrus)
(Polymathic AI), [transformers](https://github.com/huggingface/transformers) and
[whisper](https://github.com/openai/whisper) (HF / OpenAI), the Zenodo-DOI discipline of
[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) (EleutherAI),
and the `docker run` reproducibility path of [AlphaFold3](https://github.com/google-deepmind/alphafold3).
The receipt-substrate, Λ-gate, DSSE/cosign receipt chain, Lean kernel, and honest
disclosure endpoint are a11oy's own — the layer those projects do not have.

---
*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · Λ = Conjecture 1 (NOT a theorem) · SLSA L1 (honest) + L2 build provenance attested (verifiable via slsa-verifier)*
