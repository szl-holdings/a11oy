# Third-Party Notices — SZL Holdings Flagships
**Doctrine v11 LOCKED 749/14/163 | SLSA L1 honest | Generated: 2026-06-03**

This file contains notices for third-party libraries used by SZL Holdings flagships.

## Python Dependencies

### FastAPI
- **License:** MIT
- **Source:** https://github.com/tiangolo/fastapi
- **Usage:** API framework for all 5 flagships

### Gradio
- **License:** Apache-2.0
- **Source:** https://github.com/gradio-app/gradio
- **Usage:** UI framework for HuggingFace Spaces

### Uvicorn
- **License:** BSD-3-Clause
- **Source:** https://github.com/encode/uvicorn
- **Usage:** ASGI server

### httpx
- **License:** BSD-3-Clause
- **Source:** https://github.com/encode/httpx
- **Usage:** HTTP client for inter-flagship calls

### huggingface_hub
- **License:** Apache-2.0
- **Source:** https://github.com/huggingface/huggingface_hub
- **Usage:** HuggingFace API access

## Infrastructure Components

### UDS Core (Defense Unicorns)
- **License:** Apache-2.0
- **Source:** https://github.com/defenseunicorns/uds-core
- **Usage:** Kubernetes security baseline (UDS deployment)

### Zarf (Defense Unicorns)
- **License:** Apache-2.0  
- **Source:** https://github.com/zarf-dev/zarf
- **Usage:** Airgap packaging

### Pepr (Defense Unicorns)
- **License:** Apache-2.0
- **Source:** https://github.com/defenseunicorns/pepr
- **Usage:** Kubernetes admission webhook

## Mathematical Libraries

### Lean 4 (Lean FRO / Microsoft Research)
- **License:** Apache-2.0
- **Source:** https://github.com/leanprover/lean4
- **Usage:** Formal verification substrate (lutar-lean)

### Mathlib4
- **License:** Apache-2.0
- **Source:** https://github.com/leanprover-community/mathlib4
- **Usage:** Mathematical library for Lean 4

## Frontend Routing Visualization (clean-room — concept attribution)

The a11oy console `llm` tab (`console/static/viz/router/`) implements a
**graph-based LLM router** visualization. The implementation is **clean-room**:
no third-party source code is copied or bundled. The design follows the published
*concept* of edge-weighted query/task↔model routing graphs introduced by the
following open projects, attributed here in good faith:

### GraphRouter
- **License:** MIT
- **Source:** https://github.com/ulab-uiuc/GraphRouter
- **Usage (concept only):** graph-based, inductive LLM routing over query/task/model nodes — inspiration for the bipartite affinity-graph layout and edge weighting. No code copied.

### Router-R1
- **License:** Apache-2.0
- **Source:** https://github.com/ulab-uiuc/Router-R1
- **Usage (concept only):** treating routing as a multi-round reasoning graph — inspiration for the per-task fan-out / top-K edge selection. No code copied.

### LLMRouter
- **License:** MIT
- **Source:** https://github.com/lm-sys/RouteLLM
- **Usage (concept only):** cost/quality trade-off across a model pool — inspiration for the transparent quality×ctx×cost×license edge-affinity weight. No code copied.

All edge-affinity scores are heuristic, computed locally from public model-card
features (declared benchmark/context/license), and are labelled in-UI as
heuristic (not measured online benchmarks). No routing data is fabricated.

### three.js
- **License:** MIT
- **Source:** https://github.com/mrdoob/three.js
- **Usage:** 3D rendering for the routing-graph and other console viz pages (r171).

### uPlot (Leon Sorokin)
- **License:** MIT (© 2022 Leon Sorokin)
- **Source:** https://github.com/leeoniya/uPlot (v1.6.32)
- **Usage:** Streaming watts line chart on the `/energy-ops` Live Energy Dashboard.
  Vendored 0-CDN at `static-vendor/uPlot.iife.min.js` + `.css`, served from
  `/vendor/uPlot.iife.min.js`. Full MIT text in `static-vendor/LICENSE.uplot`.

## Governed Vector Index (WAQAY) — studied open work, made ours (attribution required)

WAQAY (Quechua: *to keep / guard / store*) is SZL Holdings' own governed,
air-gapped, DSSE-signed quantized vector index (`szl_waqay.py`). It was built by
**studying** the following MIT / open work and **re-implementing the approach** in
pure Python — we do **not** vendor or copy the upstream crate. Attribution is
required by the MIT license and is given here in full.

### turbovec (Ryan Codrai)
- **License:** MIT
- **Copyright:** © 2026 Ryan Codrai
- **Source:** https://github.com/RyanCodrai/turbovec
- **What we studied:** the Rust+Python vector-index architecture — a
  data-oblivious quantizer with **no codebook training** and **no train phase**
  (online ingest); the Lloyd-Max codebook fit analytically to the Beta marginal
  induced by a random orthogonal rotation; RaBitQ-style per-vector length
  renormalization; bit-packed 2/4-bit codes.
- **What we built (OURS):** a clean-room **pure-NumPy** re-implementation of the
  *approach* (`szl_waqay.py`). We add the governed difference — every index build
  and every retrieval emits a **DSSE-signed provenance receipt** and passes the
  **Restraint gate**. We do **not** ship the Rust crate, and we do **not** claim
  to match its SIMD throughput: our perf figures are labeled **MODELED/ROADMAP**.
  Compression is **MEASURED**; recall is a **MODELED bound** (never claimed perfect).

### TurboQuant (Google Research)
- **Attribution:** the data-oblivious quantization *approach* originates with
  Google Research's TurboQuant work (normalize → random orthogonal rotation →
  analytic Lloyd-Max codebook on the Beta((d-1)/2,(d-1)/2) marginal → bit-pack →
  per-vector scale). WAQAY implements this approach independently in NumPy.
- **Honesty:** we attribute the approach; we make no claim of affiliation with or
  endorsement by Google Research.

**Honest perf labeling (Doctrine v11, Zero-Bandaid Law):** WAQAY is a pure-Python
governed index *inspired by* TurboQuant. It does **not** claim to beat FAISS or to
match the Rust SIMD original. Compression ratios shown are MEASURED on the actual
bytes stored; recall is a MODELED design bound surfaced honestly (trust ceiling
< 1.0 — never perfect).


## Governed Multi-Model Audit Harness (YUPAY) — studied open work, made ours (attribution required)

YUPAY (Quechua: *to count / to reckon / to audit*) is SZL Holdings' own governed
multi-model **audit harness**. It runs the SAME audit task through MULTIPLE of OUR
OWN governed open models, scores each on **issues-found / tokens / cost / latency**,
and emits ONE **DSSE-signed comparison receipt** with a **Restraint verdict**. The
signed multi-model comparison is the governed difference. Implemented in
`szl_yupay.py`.

### Kilo Code / André Lindenberg — audit methodology (INSPIRATION only)
- **Source:** https://blog.kilo.ai/p/we-audited-the-same-codebase-with
  ("We Audited the Same Codebase with Claude Opus 4.8 and MiniMax M3", 2026-06-05).
- **What we studied:** the AUDIT METHODOLOGY — give every model the *identical*
  audit task on a planted-bug codebase, then track issues-found, tokens, cost, and
  time per run, and reason about cost-per-issue rather than naming a single winner.
- **What we built (OURS):** `szl_yupay.py` runs that methodology over OUR OWN
  governed open models (SZL-Nemo on a Qwen3-32B Apache-2.0 base; the HF-router
  models a11oy already declares; mesh models when wired) on OUR OWN harness, and
  **signs** the comparison (DSSE) plus attaches a Restraint verdict. We adopt the
  methodology only; we make no claim of affiliation with or endorsement by Kilo
  Code or André Lindenberg.
- **Honest labeling (Doctrine v11, Zero-Bandaid Law):** no API key is wired in the
  HF Space, so in-Space rows are **MODELED** (issues from the published benchmark;
  cost = MODELED tokens × **published per-token rates, cited**). A row is
  **MEASURED** only when a real run happens in-process. Unreachable models are
  labeled **ROADMAP**. We never fabricate a benchmark.

### MiniMax Sparse Attention paper (INSPIRATION only — NOT a model build)
- **Source:** https://huggingface.co/papers/2606.13392 ("MiniMax Sparse Attention",
  Lai et al., 2026-06-12) — blockwise sparse attention on Grouped-Query Attention
  with group-specific top-k block selection and an exact-softmax main branch.
- **What we take:** the *published technique* as INSPIRATION for OUR OWN
  efficient-attention research path for SZL-Nemo on the clean OPEN Qwen3-32B
  (Apache-2.0) base. See `team/AUDIT/frontier/YUPAY_SPARSE_ATTN_RESEARCH.md` and the
  box-gated Forge order `team/AUDIT/frontier/FORGE_YUPAY_SPARSE_ATTN.md`. YUPAY
  itself trains/serves NO model.

### NO M3 WEIGHTS / NO M3 DERIVATIVE (defense-license + sovereignty)
MiniMax M3 is open-weight, but its license **restricts military/defense use** and
MiniMax is **PRC-based** (subject to the PRC National Intelligence Law). SZL
Holdings demonstrates at the **Defense Unicorns Warhacker** event. Therefore SZL
Holdings:
- **NEVER** bases SZL-Nemo on M3 and **NEVER** ships an M3 derivative;
- **NEVER** downloads, serves, or ingests M3 weights;
- takes ONLY the open AUDIT METHODOLOGY and the published sparse-attention
  TECHNIQUE (as inspiration) — applied to OUR own open Qwen3-32B Apache base.

In YUPAY, MiniMax M3 appears solely as a **non-participating reference row** labeled
**EXCLUDED-BY-DOCTRINE** — never run, never scored as if run. Reference figures
shown (e.g. 13/17 issues at ~$0.07 from the Kilo writeup) are context only.

**SZL-Nemo provenance:** SZL-Nemo is OUR governed model built **on an OPEN base**
(default **Qwen3-32B, Apache-2.0**), never trained from scratch, never an M3
derivative. Our contribution is the governed-MoE domain-expert router and the
governed wrapper — not the base weights.

### deck.gl
- **License:** MIT (Copyright © Urban Computing Foundation / Open Visualization Foundation)
- **Source:** https://github.com/visgl/deck.gl (v9.0.38)
- **Usage:** Vendored 0-CDN at `static/3d/vendor/deck.gl/dist.min.js` (MIT LICENSE
  committed alongside) for the holographic estate's geospatial energy/estate
  surfaces. The energy surface additionally re-implements the deck.gl *visual
  techniques* (GPUGridLayer / ColumnLayer / ArcLayer) in pure three.js inside the
  shell-owned scene graph to share one GL canvas; 0 runtime CDN either way.

## Section 889 Declaration

SZL Holdings does NOT use equipment or services from:
- Huawei Technologies Company
- ZTE Corporation
- Hytera Communications
- Hangzhou Hikvision Digital Technology Company
- Dahua Technology Company

This notice is provided in compliance with Section 889 of the 2019 NDAA.

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
