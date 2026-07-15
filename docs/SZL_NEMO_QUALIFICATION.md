# SZL-Nemo Qualification Record

Status as measured on 2026-07-15: **runtime-qualified recipe; not fine-tuned; model quality unverified**.

## Artifact identity

- Hub recipe: <https://huggingface.co/SZLHOLDINGS/szl-nemo>
- Upstream base: `nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16`
- Local upstream tag: `nemotron-3-nano:4b`
- Exact upstream Ollama manifest: `6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197`
- Derived recipe tag: `szl-nemo:latest`
- Measured derived manifest: `0d7777be553e3a9000b0a6d266936184f64cef1d5e567a85b74c418cf79d8c27`
- Shared model layer: `sha256:527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970`
- Shared NVIDIA license layer: `sha256:355e036064fa9b3a96ce0cdbb69abe54f5c7ce0b6aa2c7d5f8ec8580b011c20e`
- Runtime format: GGUF, `nemotron_h`, 4.0B, Q4_K_M.

The Hub repository is a configuration recipe. It does not contain SZL adapter or
weight files. NVIDIA owns the base weights; the governing upstream license is the
NVIDIA Open Model License, not Apache-2.0. Redistribution must preserve the
upstream agreement and its required notice. This is an engineering record, not
legal advice.

## Measured live receipt

The current API was restarted from this source and a bounded execution through
`POST /api/a11oy/v1/nemo/infer` loaded and served `szl-nemo:latest` on the laptop
RTX 5050:

- runtime state: `READY`
- observed model: `szl-nemo:latest`
- response SHA-256: `e6657e265847329832cf83c325a2daf55ed6f6171fbbb34e7a03bdd7a87a18d4`
- measured generation latency: `847.435 ms`
- model load duration: `244,613,800 ns`
- evaluation duration: `474,549,000 ns`
- evaluation count: `35`
- result label: `ANSWERED_UNVERIFIED`
- receipt PAE SHA-256: `a0946e5bbcfb000adc9dee8d34ec6eb33619a6c426e24b31c26faab84675f729`
- receipt signature: independently verified ECDSA-P256-SHA256
- signing scope: `PROCESS_BOOT_EPHEMERAL`; the key is not an organization identity

The live call exposed and repaired an adapter defect specific to reasoning models:
Ollama placed the bounded output in its separate `thinking` field and exhausted the
budget before emitting `response`. The public execution contract now explicitly
uses `think:false`, continues to reject empty responses, and has a regression test.

The answer correctly identified NVIDIA Nemotron 3 Nano, attributed the upstream
weights to NVIDIA, and stated that SZL did not fine-tune them. The privacy-safe
record is `attestations/szl-nemo-live-2026-07-15.json`. This proves one signed local
API load-and-generate path. It does not establish general quality, safety,
reproducibility, or training.

## Compatibility boundary

The existing local LoRA at
`work/szl-forge/szl-forge-main/szl-adapter-v2/adapter_model.safetensors`
targets `unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit` (`Qwen2`, vocabulary 151,936).
Nemotron uses `nemotron_h` with vocabulary 131,072. The Qwen adapter is therefore
not an SZL-Nemo adapter and must never be renamed, merged into, or advertised as
one.

## Remaining promotion blockers

1. Runtime code verifies the exact upstream manifest and existence of the derived
   tag. Promotion should also bind the derived manifest's model and license layers
   to the expected upstream layers, as this record did manually.
2. The live receipt uses a process-boot-ephemeral key. Organization-identity or
   transparency-log publication remains absent.
3. No latency distribution, energy, safety, tool-use, refusal, citation, or
   preregistered held-out task-evaluation suite exists yet.
4. No Nemotron-compatible adapter, trainer state, admitted training dataset,
   training receipt, or independent post-training evaluation exists.
5. The Hub card should expose explicit `base_model` metadata and preserve the
   NVIDIA license/notice lineage. The recipe and any future trained candidate
   should be versioned as distinct artifacts.

## Safest qualification sequence

1. Synchronize identity and license language across code, API, UI, notices, Hub,
   and release manifests; make the offline regression suite green.
2. Restart the API and verify the runtime-bound card, diagnostics, and fail-closed
   inference route live.
3. Emit signed receipts for exact manifests/layers, cold and warm loads, restart
   persistence, latency/VRAM/energy, and deterministic failure cases.
4. Run a preregistered held-out evaluation and publish failures as well as passes.
5. If fine-tuning is justified, create a separate immutable Nemotron training
   contract pinned to the exact base revision and tokenizer; admit only licensed,
   provenance-complete rows; then load-test and evaluate the resulting adapter.
6. Promote a versioned trained candidate only after independent base/license,
   adapter-load, held-out-eval, served-tag, and signed-receipt gates all pass.
