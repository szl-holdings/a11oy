# FORGE_YUPAY_SPARSE_ATTN.md — Forge order: OUR own efficient-attention for SZL-Nemo

> **Lane:** Forge / box-side model work (GPU tower). **STATUS: ROADMAP / ORDER —
> NOT executed in this repo or in the a11oy/killinchu HF Spaces.**
> **What this is:** the work order for the box-side (RTX 4060 Ti tower / Warhacker
> rig) implementation of OUR OWN block-sparse / selective attention path for
> **SZL-Nemo** on the OPEN **Qwen3-32B (Apache-2.0)** base. Inspired by the published
> MiniMax Sparse Attention paper (`huggingface.co/papers/2606.13392`); implemented
> clean-room as ours. The research rationale lives in
> `YUPAY_SPARSE_ATTN_RESEARCH.md`.
>
> **Doctrine v11 contract:** locked=8 @ `c7c0ba17`; Λ = Conjecture 1 (OPEN); SLSA
> L1 honest / L2–L3 roadmap; signed receipts; benchmarks never fabricated;
> additive-only. **NO M3 WEIGHTS / NO M3 DERIVATIVE** (defense-license +
> sovereignty). SZL-Nemo base stays Qwen3-32B Apache; never from-scratch.

---

## 0. Hard gates (must hold for the WHOLE order)

- [ ] **G1 — No model build in the web repos.** Nothing in this order runs in
  `szl-holdings/a11oy`, `szl-holdings/killinchu`, or their HF Spaces. Box-only.
- [ ] **G2 — No M3.** No M3 weights downloaded, served, ingested, fine-tuned, or
  derived. The MiniMax MSA kernel may be *read* as a published reference; OUR
  kernel is clean-room. SZL-Nemo base = Qwen3-32B Apache-2.0.
- [ ] **G3 — Honest labels.** Every efficiency/latency/recall figure is MEASURED on
  the box or labeled MODELED/ROADMAP. The paper's numbers are never restated as
  ours. Sparse-vs-dense recall is a MODELED bound, never "lossless".
- [ ] **G4 — Signed.** Every box run emits a DSSE-signed receipt (same cosign key
  family as `szl_dsse`) recording config, attention budget, parity bound, Λ score.
- [ ] **G5 — Air-gap clean.** Build is reproducible offline; no runtime CDN; no key
  committed.

---

## 1. Deliverables (box-side, gated)

### Forge-A — Attention-mass measurement harness (no model change)
- Instrument Qwen3-32B attention on SZL audit/eval tasks; record per-head /
  per-block attention mass.
- **Output:** `szl_nemo_attn_profile.json` (MEASURED on box) + a signed receipt.
- **Acceptance:** profile reproducible; figures labeled MEASURED; receipt verifies.

### Forge-B — Block-sparse main branch (OURS, clean-room)
- Implement a top-k **per-GQA-group block selection** (lightweight index score) +
  an **exact block-sparse** main-branch kernel over Qwen3's existing GQA grouping.
  Softmax stays exact; only the attended-block set is reduced.
- **Output:** an `szl_nemo` inference path with a `--attn=block-sparse` flag and a
  parity test vs dense attention on held-out tasks.
- **Acceptance:** parity bound MEASURED + labeled MODELED-bound for general inputs;
  no quality regression beyond the stated bound on the SZL eval set; receipt signed.

### Forge-C — Governed wrapper + energy/latency ledger
- Wrap long-context inference so each run emits a DSSE receipt (blocks attended /
  total, parity bound, Λ-advisory) and feeds `szl_energy_ledger`.
- **Output:** signed per-run receipts; a MEASURED prefill/decode latency + energy
  table for SZL-Nemo block-sparse vs dense on the box.
- **Acceptance:** all figures MEASURED + signed; reproducible; honest deltas (no
  borrowed paper multipliers).

### Forge-D — Wire SZL-Nemo into YUPAY as MEASURED (closes the loop)
- Once Forge-B/C are stable, expose a box-side SZL-Nemo audit endpoint so
  `szl_yupay.py`'s harness can run a REAL audit and flip the SZL-Nemo row from
  **MODELED** to **MEASURED**, with the attention budget recorded in the same
  signed comparison receipt.
- **Acceptance:** YUPAY shows a MEASURED SZL-Nemo row sourced from the box; the
  comparison receipt records real token usage + attention budget; M3 stays
  EXCLUDED-BY-DOCTRINE.

---

## 2. Explicit non-goals
- Not a from-scratch model. Not an M3 derivative. Not a vendored MSA kernel.
- Not deployed to the web Spaces (they stay the governed *evaluation surface* only).
- Not a claim to match the paper's 28.4×/14.2×/7.6× — those are the paper's, on the
  paper's model; SZL reports only SZL-MEASURED deltas.

---

## 3. Provenance & citation
- **Inspiration:** *MiniMax Sparse Attention*, Lai et al., 2026-06-12,
  `https://huggingface.co/papers/2606.13392` (cited; not affiliated; not endorsed).
- **Base:** Qwen3-32B (Apache-2.0), `https://huggingface.co/Qwen/Qwen3-32B`.
- **Harness it feeds:** `szl_yupay.py` (a11oy + killinchu).
- **Rationale:** `team/AUDIT/frontier/YUPAY_SPARSE_ATTN_RESEARCH.md`.

**Signed-off-by: Yachay <yachay@szlholdings.ai>**
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
