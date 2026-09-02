# Hugging Face State-of-the-Art Adoption Plan — 2026-09-02

Status: RESEARCHED / ADOPTION PLAN / NO MODEL CLAIMS WITHOUT EVIDENCE

This document converts the current Hugging Face frontier into an A11oy/SZL implementation program. It is intentionally evidence-first: no model is called "best" for an SZL workload until the workload-specific benchmark suite proves it.

## 1. Inference substrate — move forward, not sideways

Hugging Face now documents Text Generation Inference (TGI) as maintenance-mode and explicitly recommends vLLM, SGLang, llama.cpp, or MLX for future optimized serving. Transformers v5 also exposes `transformers serve`, continuous batching, paged attention, specialized kernels, and an OpenAI-compatible server. The July 2026 Transformers-backed vLLM path is reported by Hugging Face as reaching native-speed performance across many architectures.

SZL action:
- Keep TGI only as a compatibility lane; do not make it the strategic default.
- Standardize production GPU serving on vLLM first, SGLang as the second engine, llama.cpp/MLX for sovereign local/on-device lanes.
- Add an engine capability registry to A11oy with: model, engine, quantization, context, tool-calling, multimodal, structured-output, throughput, p50/p95 latency, VRAM/RAM, and provenance.
- Require an engine benchmark receipt before production promotion.
- Add `transformers serve` as the low-friction evaluation and moderate-load reference lane.

## 2. Agentic intelligence — coding and long-horizon control

Current Hugging Face frontier candidates include:
- DeepSeek-V4: 1M-token context, explicit tool-call schema, interleaved thinking across tool calls, and an architecture designed around long-context agent workloads.
- Qwen3-Coder-Next: 80B total / 3B active, 256K context, coding-agent orientation, tool use, recovery from failures, and local-development focus.
- smolagents: lightweight code-agent/tool-calling framework and successor to `transformers.agents`.

SZL action:
- Build an A11oy model router with four governed classes: planner, coder, verifier, and lightweight local executor.
- Benchmark DeepSeek-V4 and the current Qwen coder family against the existing SZL coding-agent tasks instead of replacing models by popularity.
- Use smolagents only behind A11oy policy, sandbox, approval, receipt, and tool allowlist boundaries.
- Preserve fail-closed human approval for mutations, financial actions, security control changes, and external side effects.

## 3. Multimodal command layer

Gemma 4 is a major 2026 open multimodal family on Hugging Face, including image, audio, video, object/GUI understanding, function calling, on-device paths, TRL fine-tuning, llama.cpp and MLX support. The current Hub also shows Qwen 3.x/3.8 multimodal families among heavily used/trending models.

SZL action:
- Add governed image/document/audio/video intake contracts to A11oy.
- Use multimodal models for Terra property packets, Vessels visual evidence, Aegis imagery/screens, PRISM legal exhibits, and Lyte dashboard/screenshots.
- Require modality provenance, capture timestamp, source hash, confidence and model/version in every generated conclusion.
- Never allow a vision model output to become an action without a verifier or deterministic policy gate.

## 4. Retrieval — upgrade from single-vector-only RAG

Sentence Transformers 5.4 added multimodal embedding and reranking across text, images, audio and video. Hugging Face's August 2026 multi-vector/late-interaction support preserves token-level vectors and MaxSim scoring; this is especially strong for visual document retrieval and can avoid OCR-first pipelines. Ettin rerankers were released as state-of-the-art-at-size rerankers in May 2026.

SZL action:
- Create a three-lane retrieval fabric:
  1. sparse/BM25 lexical retrieval,
  2. dense single-vector embedding retrieval,
  3. multi-vector late-interaction retrieval.
- Add cross-encoder reranking after first-stage retrieval.
- Benchmark Qwen3-VL-Embedding-class multimodal retrieval, Ettin-class rerankers, and current text embedding baselines on SZL domain corpora.
- Add Matryoshka embedding tests for lower-cost truncated vectors where quality remains above the workload threshold.
- Log query, candidate set, reranker scores, final evidence set and citation provenance into the Proof Chain.

## 5. Speech / voice

Cohere Transcribe 03-2026 is a 2B Apache-2.0 ASR model reported as #1 on the Hugging Face Open ASR Leaderboard at release, with 14 enterprise-focused languages and strong throughput. The 2026 speech frontier increasingly treats speech as a first-class modality rather than only ASR -> LLM -> TTS cascades.

SZL action:
- Add ASR bakeoff lanes: Cohere Transcribe, current Whisper-family baseline, Qwen ASR, and any existing SZL speech stack.
- Evaluate WER, domain-name accuracy, speaker/noise robustness, real-time factor, GPU/CPU cost and timestamp quality.
- Keep TTS and speech-to-speech behind explicit disclosure that generated audio is synthetic.
- Store transcript/source-audio hashes and model receipts for legal, maritime, defense, and investor-demo use.

## 6. Generative media

Diffusers remains the common Hugging Face image/video generation layer; FLUX-family support includes quantization and caching paths for memory/performance optimization. The current Hub is also showing active image-to-video and text-to-video families.

SZL action:
- Treat generative media as a design/simulation lane, not as operational evidence.
- Watermark or metadata-label generated visuals as synthetic.
- Use generated media for UI concepts, product visualization, simulation and investor demos; never mix it into an evidence corpus without a synthetic flag.

## 7. Training and post-training

Transformers v5 is the model-definition center of gravity; TRL remains the preferred Hugging Face post-training layer. Multimodal Sentence Transformers now supports direct training/fine-tuning for multimodal embedding and reranking models.

SZL action:
- Standardize recipes as reproducible manifests: base model revision, dataset revision, tokenizer revision, exact package lock, GPU type, seed, training args, eval suite, license and output checksum.
- Prefer adapters/LoRA and task-specific post-training before full-model training unless the benchmark proves a full retrain is justified.
- Every trained model needs a model card with intended use, prohibited use, data lineage, benchmark table, limitations, license and reproducibility recipe.

## 8. A11oy "Genius-Made" quality bar

Every model, kernel, Space, dataset and collection must pass the same promotion contract:

1. **Purpose** — one sentence naming the user problem.
2. **Evidence** — benchmark against at least one strong public baseline.
3. **Economics** — latency, throughput, memory, and estimated cost per workload unit.
4. **Safety/governance** — tool permissions, policy, refusal/abstention, audit trail, secrets boundary.
5. **UX** — mobile/desktop, keyboard, reduced-motion, loading/error/empty states, copy that explains what the system can and cannot do.
6. **Reproducibility** — immutable model/dataset/code revisions and dependency lock.
7. **Observability** — health, readiness, telemetry, error taxonomy, drift and quality regression metrics.
8. **Proof Chain** — model/version, inputs or hashes, evidence citations, confidence, decision, approvals, action, result.
9. **No overclaim** — EXPERIMENTAL / BENCHMARKED / PRODUCTION-QUALIFIED are separate states.
10. **Rollback** — deterministic rollback target and promotion receipt.

## 9. Implementation waves

### Wave A — inference modernization
- Introduce `model-engine-registry.json`.
- Add vLLM/SGLang/llama.cpp/MLX capability probes.
- Mark TGI compatibility-only in new architecture docs.
- Add benchmark receipt schema.

### Wave B — retrieval frontier
- Add dense + sparse + multi-vector retrieve/rerank pipeline.
- Add multimodal document/page retrieval benchmark.
- Add citation/evidence-chain capture.

### Wave C — agent frontier
- Planner/coder/verifier/local-executor router.
- Qwen coder + DeepSeek long-context bakeoff.
- smolagents adapter behind A11oy tool policy and sandbox.

### Wave D — multimodal and speech
- Image/audio/video evidence ingestion.
- Gemma/Qwen multimodal bakeoff.
- ASR leaderboard-backed evaluation suite.

### Wave E — Hugging Face organization polish
- Every SZLHOLDINGS model: complete model card + benchmark + license + intended use + limitations.
- Every dataset: dataset card + schema + provenance + PII/security review + sample viewer.
- Every Space: mobile-first UX + clear demo path + health/readiness + source revision + model revision + screenshot + accessibility checks.
- Every collection: organized by vertical and maturity state rather than asset type alone.

## 10. Promotion rule

No frontier model is adopted because it is trending. A model enters the A11oy estate only when:

`quality_delta > 0 AND governance_pass = true AND reproducibility_pass = true AND cost_within_budget = true`

The winning model may differ by vertical and by workload. The architecture therefore remains model-agnostic and evidence-driven.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
