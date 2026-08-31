# ⚡ FORGE / REPLIT — DO THIS NOW (founder asked twice). 1 command flips it. (2026-06-12 07:01 EDT)

The founder believes the GPU is flipped. **It is NOT** — I verified a-11-oy.com 4× (sandbox + browser, cache-busted):
`inference:"hf-router"`, `env_used:"HF_TOKEN"`, `base_url:router.huggingface.co`, NO sovereign/gpu fields,
`/api/a11oy/v1/sovereign-compute` → `{"error":"not found"}`. So the box is on the STALE image and the
GPU env vars are NOT set. I (the CTO agent) have NO sudo on the box — `a11oy-rebuild` is sudo-gated and
cannot run from CI or from me. **Only you/the box can do this.**

## RUN THIS ON THE HETZNER BOX (167.233.50.75) — that's the whole job:
```bash
nvidia-smi  # confirm RTX 5000

# vLLM on the GPU (OpenAI-compatible :8000)
docker run -d --restart=always --gpus all --name a11oy-vllm \
  -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ --quantization awq \
  --max-model-len 16384 --gpu-memory-utilization 0.92 \
  --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct
# VRAM tight? fallback: --model meta-llama/Llama-3.1-8B-Instruct (no --quantization)

curl -s localhost:8000/v1/models   # must list the model

# the 2 env vars where a11oy reads HF_TOKEN today, then the sudo rebuild:
export A11OY_MODEL_BASE_URL=http://127.0.0.1:8000/v1
export A11OY_GPU_LABEL="NVIDIA RTX 5000 @ Hetzner"
sudo a11oy-rebuild
```

## PROOF (all must flip):
```bash
curl -s https://a-11-oy.com/api/a11oy/code/healthz | jq '.inference,.backend,.gpu,.sovereign,.key_resolution.base_url'
# WANT: "self-hosted-gpu" "generative" "NVIDIA RTX 5000 @ Hetzner" true "http://127.0.0.1:8000/v1"
```
The */15min watch cron auto-detects sovereign:true, runs a governed proof turn, notifies the founder, self-deletes.

ALL CODE IS READY (verified on main): orchestrator _sovereign_inference_state (line 102, wired to healthz 1310),
engine GPU-label (467-565), Sovereign Compute pane registered in serve.py + COPY'd in Dockerfile. Setting the 2
env vars + `sudo a11oy-rebuild` is the ENTIRE remaining action. Reply: drop forge-STATUS-20260612.md with the
post-rebuild healthz.

DOCTRINE: open-weight only; set A11OY_GPU_LABEL only when the model TRULY serves on the GPU; never commit a key.
