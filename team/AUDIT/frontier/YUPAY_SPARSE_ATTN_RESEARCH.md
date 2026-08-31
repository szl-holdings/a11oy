# YUPAY_SPARSE_ATTN_RESEARCH.md — OUR own efficient-attention path for SZL-Nemo

> **Lane:** Frontier / model-efficiency research (ROADMAP, box-gated).
> **What this is:** a research note studying the published **MiniMax Sparse
> Attention (MSA)** paper (`huggingface.co/papers/2606.13392`) as INSPIRATION, and
> outlining **OUR OWN** efficient-attention path for **SZL-Nemo** on the clean OPEN
> **Qwen3-32B (Apache-2.0)** base. This is NOT a model build. No training, no weight
> modification, and no M3 anything happens in this repo or in the a11oy/killinchu
> Spaces. The actual box-side work is gated to the Forge order
> `FORGE_YUPAY_SPARSE_ATTN.md`.
>
> **Doctrine v11 contract upheld:** locked=8 @ kernel `c7c0ba17`; Λ = Conjecture 1
> (OPEN, advisory floor < 1.0); SLSA L1 honest / L2–L3 roadmap; 0 runtime CDN; 0
> visible codenames; signed receipts on every decision; benchmark numbers never
> fabricated; additive-only.
> **NO M3 WEIGHTS / NO M3 DERIVATIVE** — see §5.

---

## 0. TL;DR

The MiniMax Sparse Attention paper shows that, at long context, you do not need
dense all-pairs attention: you can **score key-value blocks**, select a
**group-specific top-k** subset per attention group, and run **exact block-sparse
attention** over only the selected blocks — keeping the softmax exact while
narrowing *where* it runs. The published figures are large (≈28.4× per-token
attention-compute reduction at 1M context; ≈14.2× prefill / ≈7.6× decode wall-clock
on H800).

We take this as a **published idea**, not as code or weights to copy. SZL-Nemo's
efficient-attention path will be OUR OWN implementation of a *family* of
block-sparse / selective attention on top of the **Qwen3-32B Apache-2.0** base,
governed and signed like everything else. We never base SZL-Nemo on M3, never ship
an M3 derivative, and never download/serve M3 weights (defense-license +
sovereignty; see §5).

---

## 1. What the MiniMax Sparse Attention paper actually describes (cited)

Source: *MiniMax Sparse Attention*, Lai et al., 2026-06-12,
`https://huggingface.co/papers/2606.13392`.

- **Architecture:** blockwise sparse attention built on **Grouped-Query Attention
  (GQA)**.
- **Index Branch (lightweight):** scores key-value blocks and independently selects
  a **top-k subset for each GQA group**, enabling group-specific sparse retrieval
  while keeping block-level execution.
- **Main Branch:** performs **exact block-sparse attention** over only the selected
  blocks (softmax stays exact; only the *set of attended blocks* is reduced).
- **Execution co-design:** GPU path uses **exp-free top-k selection** and a
  **KV-outer sparse attention** layout to keep tensor-core utilization high under
  block-granular access.
- **Reported scale/results:** demonstrated on a 109B-param natively-multimodal
  model; **≈28.4×** attention-compute reduction at 1M context; **≈14.2×** prefill /
  **≈7.6×** decode speedups on H800. (Reported by the authors; treated by us as the
  *target regime*, not a number we restate as our own.)

> Honest framing: these are the paper's numbers on the paper's model. They are NOT
> SZL numbers and will never be presented as such. Any SZL figure is MEASURED on
> SZL's own runs or labeled MODELED/ROADMAP.

---

## 2. Why this matters for SZL-Nemo (the 8GB Blackwell brain + air-gap)

SZL-Nemo is OUR governed model on an OPEN base (default Qwen3-32B, Apache-2.0),
targeting on-device / air-gapped sovereign deployment (the Warhacker tower; UDS
Core / SIPR). The binding constraint there is **KV-cache memory and long-context
latency**, not raw FLOPs. A selective/block-sparse attention path is the
highest-leverage efficiency lever for:

- holding a **larger governed KB** in-context alongside WAQAY's compressed index;
- running **long audit tasks** (the YUPAY use case — read a whole codebase in
  context) without dense-attention blow-up;
- keeping decode latency bounded on an 8GB-class device.

This is a natural complement to WAQAY (compressed *storage*) — sparse attention is
compressed *compute over context*.

---

## 3. OUR own path (design sketch — NOT a build; ROADMAP)

We implement OUR OWN efficient-attention family on the Qwen3-32B Apache base. The
*idea* is borrowed (block selection + exact sparse main branch); the *code* is ours,
clean-room, in our own training/inference stack. Candidate stages, each box-gated:

1. **Stage A — measurement harness (no model change).** Instrument Qwen3-32B
   attention to record per-head/per-block attention mass on SZL audit/eval tasks.
   Output: an honest profile of how concentrated attention actually is on our
   workloads. (MEASURED on the box; nothing shipped to the Spaces.)
2. **Stage B — block-sparse main branch (ours).** Implement a block-sparse
   attention kernel path over Qwen3's existing GQA grouping, selecting a top-k block
   subset per group from a lightweight index score. Keep softmax exact. Validate
   parity against dense attention on held-out tasks (recall of the dense top-k
   blocks is a MODELED bound, surfaced honestly — never claimed lossless).
3. **Stage C — governed wrapper + receipts.** Wrap inference so each long-context
   run emits a DSSE-signed receipt recording the attention budget used (blocks
   attended / total), the parity bound, and the Λ-advisory score. This is the
   governed difference even at the kernel layer.
4. **Stage D — energy/latency ledger.** Tie measured prefill/decode latency and
   energy into `szl_energy_ledger` so the efficiency claim is MEASURED, signed, and
   reproducible — never a restated paper number.

**Explicit non-goals / gates:**
- We do NOT modify or train a model in this repo or in the Spaces. Stages A–D are
  box-side, gated by the Forge order.
- We do NOT vendor the MiniMax MSA kernel code as our implementation. We may read it
  as a published reference, but our kernel is clean-room and Apache/our-own-licensed.
- Recall of dense behavior under sparsity is a **MODELED bound**, never "lossless".
- SZL-Nemo's base stays **Qwen3-32B Apache-2.0**. Never from-scratch. Never an M3
  derivative.

---

## 4. How this connects to YUPAY (the harness)

YUPAY (the served audit harness, `szl_yupay.py`) is the *evaluation surface* for
this research: once Stage B lands on the box, a real SZL-Nemo run can be wired into
YUPAY's harness so its audit row flips from **MODELED** to **MEASURED**, with the
attention budget recorded in the same signed comparison receipt. Until then,
SZL-Nemo's YUPAY row is honestly labeled MODELED/ROADMAP.

---

## 5. NO M3 WEIGHTS / NO M3 DERIVATIVE (defense-license + sovereignty) — hard gate

MiniMax M3 is open-weight, BUT:
- its open-weight **license restricts military/defense use**; and
- MiniMax is **PRC-based**, subject to the **PRC National Intelligence Law**.

SZL Holdings demonstrates at the **Defense Unicorns Warhacker** event. Therefore, as
a permanent doctrine gate:
- SZL-Nemo is **NEVER** based on M3 and SZL **NEVER** ships an M3 derivative;
- SZL **NEVER** downloads, serves, or ingests M3 weights;
- we take ONLY the **published sparse-attention technique** (a citable idea) and the
  **audit methodology** (a citable idea), applied to OUR own OPEN Qwen3-32B Apache
  base.

The paper is cited as inspiration. The implementation is ours.

---

## 6. Provenance & citation

- **Inspiration (technique):** *MiniMax Sparse Attention*, Lai et al., 2026-06-12,
  `https://huggingface.co/papers/2606.13392`. Cited; not affiliated; not endorsed.
- **Inspiration (methodology):** Kilo Code / André Lindenberg, "We Audited the Same
  Codebase with Claude Opus 4.8 and MiniMax M3", `https://blog.kilo.ai/p/we-audited-the-same-codebase-with`, 2026-06-05.
- **Our base:** Qwen3-32B (Apache-2.0), `https://huggingface.co/Qwen/Qwen3-32B`.
- **Our harness:** `szl_yupay.py` (this repo, byte-identical on a11oy + killinchu).
- **Box-side work order:** `team/AUDIT/frontier/FORGE_YUPAY_SPARSE_ATTN.md`.

**Signed-off-by: Yachay <yachay@szlholdings.ai>**
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
