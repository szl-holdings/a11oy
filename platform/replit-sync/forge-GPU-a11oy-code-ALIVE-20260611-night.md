# FORGE ORDER — Bring a11oy-Code ALIVE on the Hetzner NVIDIA RTX 5000 (sovereign local inference)
**From:** CTO/PM agent (founder green-lit, autonomous) · **To:** Forge · June 11 2026, ~11:45 PM EDT, T-5.
**Founder:** "I hooked my GPU to Hetzner, it has an NVIDIA 5000 — let's wow the world, get a11oy-Code alive."

## The wow: a11oy-Code (Chaski) running on OUR OWN GPU, sovereign, no third-party router
Today a11oy-Code's healthz reports `"inference":"hf-router"` — it routes through Hugging Face's hosted router. With the RTX 5000 on Hetzner we flip it to a **local open-weight model served on our hardware**: provably sovereign, air-gap-capable, no data leaving the box. The engine is ALREADY built for this — it's purely an ops/config task on the Hetzner host. No app code change needed for the inference path (I already shipped the honest GPU-label surfacing below).

## What I already shipped this session (live, byte-identical both apps, Spaces restarted)
`a11oy_code_engine.py` (a11oy `63fca023` / killinchu `f691f8a7`, identical blob `59be8cb1`, HF mirrored, RUNNING): added optional **`A11OY_GPU_LABEL`** env. When a local (non-router) `A11OY_MODEL_BASE_URL` is configured AND `A11OY_GPU_LABEL` is set, `_backend_label()` / healthz proudly + honestly report e.g. *"local open-weight model on NVIDIA RTX 5000 @ Hetzner (sovereign) — no third-party router."* Additive display only; if no local endpoint is set, the label is ignored and nothing is fabricated.

The engine's existing priority ladder (unchanged, already correct):
1. `A11OY_LOCAL_MODEL_CMD` → plugged-in local model (highest)
2. `A11OY_MODEL_BASE_URL` (non-router) → **local Hetzner GPU endpoint** ← this is the one to set
3. HF router (only if token present, disclosed)
4. deterministic retrieval-grounded backend (honest fallback)

## FORGE — do this on the Hetzner box (167.233.50.75) with the RTX 5000
The RTX 5000 (≈32 GB VRAM) comfortably serves the engine's primary roster model **Qwen2.5-Coder-32B-Instruct** quantized, or Llama-3.1-8B unquantized for max speed. Recommend vLLM (best throughput, OpenAI-compatible) — Ollama is the simpler fallback.

### Option A (recommended) — vLLM, OpenAI-compatible, GPU
```bash
# 0. confirm GPU: nvidia-smi  (expect RTX 5000, CUDA present)
# 1. serve Qwen2.5-Coder-32B (AWQ 4-bit fits ~32GB) on an OpenAI-compatible port
docker run -d --restart=always --gpus all --name a11oy-vllm \
  -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
  --quantization awq --max-model-len 16384 --gpu-memory-utilization 0.92 \
  --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct
# (if 32B-AWQ is tight, fall back to meta-llama/Llama-3.1-8B-Instruct unquantized — also in the roster)
# 2. smoke test the endpoint:
curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-Coder-32B-Instruct","messages":[{"role":"user","content":"return the number 42"}],"max_tokens":16}'
```

### Option B (fallback) — Ollama (registry already expects `http://localhost:11434`)
```bash
docker run -d --restart=always --gpus all -p 11434:11434 --name a11oy-ollama ollama/ollama
docker exec a11oy-ollama ollama pull qwen2.5-coder:32b
# Ollama exposes an OpenAI-compatible path at http://localhost:11434/v1
```

### THEN — point the a11oy.net deployment at it (the env wiring is the whole job)
On the Hetzner a11oy container/pod env (NOT the HF Space — the Space can't reach the private GPU, it stays on router, which is correct):
```
A11OY_MODEL_BASE_URL=http://127.0.0.1:8000/v1     # vLLM  (or http://127.0.0.1:11434/v1 for Ollama)
A11OY_GPU_LABEL=NVIDIA RTX 5000 @ Hetzner
# (optional) A11OY_LOCAL_MODEL_CMD only if you front it with a CLI rather than an HTTP endpoint
```
Restart the a11oy.net service. Then verify:
```
curl -s https://a11oy.net/api/a11oy/code/healthz | jq '.inference, .backend, .gpu, .sovereign'
# expect: inference no longer "hf-router"; backend "generative"; gpu "NVIDIA RTX 5000 @ Hetzner"; sovereign true
```
Run one real governed turn through `/api/a11oy/code/run` and confirm the receipt shows the local model + a real completion (not the deterministic fallback).

## DOCTRINE (honor exactly)
- Open-weight models ONLY (no GPT/Claude/Gemini). Qwen/Llama/DeepSeek are fine and already in the roster.
- The GPU label must be TRUE — only set `A11OY_GPU_LABEL` when the model is actually served on that GPU. Never label sovereign/local if it's still routing.
- HF Space stays on hf-router (honest — it has no GPU); only a11oy.net (Hetzner) goes sovereign-local. The healthz on each will honestly differ.
- Trust never 100%; Λ=Conjecture 1; locked-proven=8; killinchu effector SIMULATED; no fabricated output (the engine already refuses to fake generative text — keep that).
- Don't commit any key. The model endpoint is localhost-only on the box; don't expose port 8000/11434 publicly.

## WHY THIS WINS WARHACKER
"Our governed AI agent runs a 32B open-weight coder on our own NVIDIA RTX 5000 at the edge — sovereign, air-gap-capable, every turn sealed in a signed Khipu receipt, gated by the P1-P6 loop and Λ-score, with zero data leaving the box." That's the cloud→edge story made literally true on real hardware, paired with the published+signed UDS bundle (uds-v0.3.0) and the L6 chain-of-title. Capture a healthz screenshot showing `gpu: NVIDIA RTX 5000 @ Hetzner, sovereign: true` for the Day-3 outbrief.
