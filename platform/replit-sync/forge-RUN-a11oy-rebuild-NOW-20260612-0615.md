# FORGE — THE FLIP IS GATED ON `a11oy-rebuild` ON THE BOX. (2026-06-12 06:15 EDT)
**From:** CTO/PM agent (founder gave explicit green light to flip; I do NOT have on-box sudo — this step is yours by design.)

## ROOT CAUSE (verified live just now via independent browser fetch)
a-11-oy.com `/api/a11oy/code/healthz` STILL reports:
- `inference: "hf-router"`, `key_resolution.base_url: "https://router.huggingface.co/v1"`, `env_used: "HF_TOKEN"`
- NO `backend`/`sovereign`/`gpu` keys at all
- `/api/a11oy/v1/sovereign-compute` → **404**

That means **a-11-oy.com is running a STALE image** that predates the GPU-detection code. Per `hetzner-currency.yml`'s own header: the Hetzner box "is rebuilt only by a **sudo-gated `a11oy-rebuild` on the box**" and "the remedy ... is sudo-gated and **cannot run from CI**." So neither CI nor I can trigger it. **Only you (on the box) can.**

## THE EXACT SEQUENCE TO FLIP (on the Hetzner box, 167.233.50.75)
```bash
# 0) confirm the card
nvidia-smi

# 1) serve an open-weight coder on the GPU (OpenAI-compatible :8000)
docker run -d --restart=always --gpus all --name a11oy-vllm \
  -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ --quantization awq \
  --max-model-len 16384 --gpu-memory-utilization 0.92 \
  --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct
# fallback if VRAM tight: --model meta-llama/Llama-3.1-8B-Instruct (drop --quantization)

# 2) smoke the GPU endpoint
curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-Coder-32B-Instruct","messages":[{"role":"user","content":"return 42"}],"max_tokens":8}'

# 3) set the TWO env vars where the a11oy container reads HF_TOKEN today
#    (same .env / k8s deploy env / docker -e), then:
export A11OY_MODEL_BASE_URL=http://127.0.0.1:8000/v1
export A11OY_GPU_LABEL="NVIDIA RTX 5000 @ Hetzner"

# 4) ***THE STEP THAT'S MISSING***: pull current main + rebuild the box image so the
#    GPU-detection code (commits 63fca023/f691f8a7 engine, 1af88fe0 healthz,
#    ed42065b/b7a24ea5/6a15f9ae sovereign pane, 1bed19fa digest pin) is in the
#    RUNNING image. Setting env vars alone is NOT enough — the stale image has no
#    sovereign code to react to them.
sudo a11oy-rebuild        # the sudo-gated box rebuild from main
```

## VERIFY (the proof — must all flip):
```bash
curl -s https://a-11-oy.com/api/a11oy/code/healthz | jq '.inference,.backend,.gpu,.sovereign,.key_resolution.base_url'
# EXPECT: "self-hosted-gpu" | "generative" | "NVIDIA RTX 5000 @ Hetzner" | true | "http://127.0.0.1:8000/v1"
curl -s https://a-11-oy.com/api/a11oy/v1/sovereign-compute | jq '.sovereign_any, .capabilities[].tier'
# EXPECT: true ... "LIVE-SOVEREIGN"
curl -s https://a-11-oy.com/v1/deploy/posture | jq '.bundles[]|{key,digest_matches_expected}'
# EXPECT: mesh digest_matches_expected now true (the rebuild brings commit 1bed19fa)
```
When sovereign:true + gpu label appear, the */15min watch cron auto-detects it, runs a governed proof turn, notifies the founder, and self-deletes. Screenshot the jq output = Day-3 outbrief headline.

## WHY THIS IS THE WHOLE BALLGAME
One `a11oy-rebuild` (with the 2 env vars + vLLM up) flips ALL of it at once: sovereign healthz, the Sovereign Compute pane (LIVE-MANAGED→LIVE-SOVEREIGN), AND the deploy-posture mesh digest. Everything is already committed, CI-green, byte-identical on HF, doctrine-clean. The HF Space is the reference for exactly what a-11-oy.com will look like post-rebuild.

DOCTRINE (unchanged): open-weight only; set A11OY_GPU_LABEL only when the model TRULY serves on the GPU; HF Space stays hf-router (correct — no GPU there); never commit a key; never weaken a gate; SLSA L1 honest; Λ=Conjecture 1; locked-8.

REPLY: drop forge-STATUS-20260612.md with the post-rebuild healthz the moment it's sovereign.
