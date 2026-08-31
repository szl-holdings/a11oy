# A11oy Evidence Kernel

The Brain is an evidence system, not one overloaded foundation model.

Its operational shape has three independent layers:

1. **Temporal evidence graph** — source URI, content hash, license/admission state,
   capture time, validity window, provenance episode, and explicit conflict edges.
2. **Semantic navigator** — a small embedding/reranking model that proposes relevant
   nodes and paths. Its scores are `MODELED`; it cannot declare a fact true or override
   an abstention.
3. **Proof-carrying retrieval kernel** — hybrid lexical, semantic, and graph retrieval;
   fixed fusion; evidence-span assembly; freshness, contradiction, provenance, and
   uncertainty gates; then a DSSE receipt binding every exact artifact and verdict.

## Local semantic path

`szl_brain_api` now supports two real local semantic runtimes:

- Ollama's batched `/api/embed` endpoint, with the legacy per-text endpoint retained as
  an explicit compatibility fallback.
- A local-files-only Hugging Face Transformers encoder configured through
  `SZL_BRAIN_EMBED_PATH`. No model is downloaded by the serving process.

For an exact, reproducible local model identity set:

```text
SZL_BRAIN_EMBED_PATH=<local snapshot directory>
SZL_BRAIN_EMBED_MODEL_ID=BAAI/bge-small-en-v1.5
SZL_BRAIN_EMBED_REVISION=5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
SZL_BRAIN_EMBED_DEVICE=cuda
SZL_BRAIN_EMBED_BATCH=64
SZL_BRAIN_EMBED_POOLING=cls
```

Pooling is explicit because model families differ. BGE-small uses `cls`; the official
Qwen3 Embedding recipe uses `last-token`. An unsupported pooling value refuses to load
instead of silently producing the wrong vector representation.

The index status reports the model identifier, upstream revision, a SHA-256 digest of
the exact local model/tokenizer artifacts, vector dimension, and active backend. If
either semantic runtime fails, the Brain visibly falls back to the deterministic hash
proxy; it never presents that proxy as a real semantic model.

## Current measured boundary

The local 9,464-node graph built with the pinned BGE encoder and returned a real query
result. The receipt is in
`attestations/brain-semantic-index-local-2026-07-21.json`.

The same corpus was also built with the pinned `Qwen/Qwen3-Embedding-0.6B`
challenger using explicit last-token pooling. Its receipt is in
`attestations/brain-semantic-index-qwen-challenger-local-2026-07-21.json`.

| Candidate | Dimension | Full build | Decision |
| --- | ---: | ---: | --- |
| BAAI BGE small v1.5 | 384 | 51.671 s | Current local baseline |
| Qwen3 Embedding 0.6B | 1,024 | 67.179 s | Challenger only |

Both candidates returned `surface:governedrag` first for the same probe. That single
probe cannot select a winner. BGE remains the baseline because it completed the full
build faster. These end-to-end times include hashing every file in each exact local
model snapshot. Qwen may be promoted only after the frozen evaluation set shows a
material retrieval-quality gain at an acceptable latency and memory cost.

## Bounded Qwen3 reranker

An explicit `/api/<ns>/v1/brain/search-reranked` route can load a pinned local
`Qwen/Qwen3-Reranker-0.6B` snapshot and rescore at most 50 hybrid-retrieval
candidates. It never changes the existing `/search` ranking silently. When the model
is absent or fails, the reranked route returns `UNAVAILABLE` instead of returning the
base order under a reranker label.

The first integrated local run used BGE retrieval over all 9,464 nodes, sent the top
20 candidates to the Qwen3 reranker, and completed the second stage in 1.484 seconds.
`surface:governedrag` remained first with a modeled relevance probability of 0.928711.
The exact receipt is in `attestations/brain-qwen3-reranker-local-2026-07-21.json`.
This establishes runtime operability, not quality superiority.

The matching WSL training environment is isolated from the serving environment and
contains Unsloth 2026.7.4, PyTorch 2.10.0 with CUDA 12.8, Transformers 5.5.0, and
bitsandbytes 0.49.2. It detected the RTX 5050 successfully. It is ready for a bounded
QLoRA experiment only after admitted training pairs and an untouched test split exist.

This closes the hash-embedding runtime gap only. It does **not** make the current query
`TRUSTWORTHY`: freshness still requires real source timestamps, contradiction requires
claim-level conflict evidence, and uncertainty requires held-out calibration. Those
components remain fail-closed.

## Release gate

Do not promote a Brain navigator/kernel until a frozen, rights-cleared evaluation set
reports retrieval Recall@k, nDCG@10 and MRR; citation precision/recall; contradiction
precision/recall; timestamp coverage; calibration and selective risk; and cold/warm
latency. Required ablations are lexical, dense, graph, hybrid, reranker, temporal,
contradiction, and calibrated abstention.

Unsloth may be used later to fine-tune an embedding or reranking candidate, but only on
admitted positive/negative pairs with a held-out split. A training run cannot repair
freshness, provenance, contradiction, or rights failures in the source graph.
