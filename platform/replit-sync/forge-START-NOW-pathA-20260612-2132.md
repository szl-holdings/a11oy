# FORGE — START NOW. Founder order: execute PATH A (make a-11-oy.com GENUINELY sovereign). 2026-06-12 21:32 EDT, T-4 to Warhacker.
**This is a direct GO order from the founder (Stephen).** Not optional, not "when you get to it." Begin immediately and reply with STATUS. The box (Hetzner / betterwithage GPU / Tailscale / Docker / sudo) is yours — CI and the CTO agent CANNOT run `a11oy-rebuild`, so only you can close this.

## STATE (re-verified live 21:32 EDT, browser, cache-busted) — STILL the half-state
a-11-oy.com `/api/a11oy/code/healthz`: `sovereign:true`, `inference:"self-hosted-gpu"`, `gpu:"NVIDIA GPU @ betterwithage (Tailscale) - Ollama llama3.1:8b"` — BUT `key_resolution = {base_url:"https://router.huggingface.co/v1", env_used:"HF_TOKEN", honest_note:"resolved via fallback HF_TOKEN (provider=hf-router)"}`. The banner claims sovereign; governed turns still hit the HF Router. This overclaim has been live ALL DAY. Close it tonight by making it REAL. a11oy main HEAD = 966aa634.

## DO THIS, IN ORDER (Path A — genuinely sovereign)

### 1. Stand up a real OpenAI-compatible model server on the GPU
SSH the box. `nvidia-smi` to confirm the GPU + free VRAM. Then EITHER Ollama (you already have llama3.1:8b on betterwithage) OR vLLM:
```bash
# Option Ollama (fastest, already present):
ollama pull qwen2.5-coder:7b   # better for the code agent than llama3.1:8b; keep llama3.1:8b for chat/general
ollama list
curl -s http://127.0.0.1:11434/v1/models   # MUST list the models (Ollama exposes an OpenAI-compatible /v1)

# Option vLLM (stronger, if VRAM allows):
docker run -d --restart=always --gpus all --name a11oy-vllm -p 8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --max-model-len 16384 --gpu-memory-utilization 0.90 \
  --served-model-name qwen2.5-coder-7b
curl -s http://127.0.0.1:8000/v1/models
```

### 2. Point a11oy at the LOCAL endpoint + label the GPU, then apply the serving-path patch
Set the env on the a-11-oy.com deploy (its .env / compose / systemd EnvironmentFile):
```bash
A11OY_MODEL_BASE_URL=http://127.0.0.1:11434/v1     # Ollama  (vLLM: http://127.0.0.1:8000/v1)
A11OY_GPU_LABEL="NVIDIA RTX 5000 @ Hetzner (betterwithage)"
```
Then APPLY the Part-1 serving-path patch described in issue #324 (this is the part that actually makes turns sovereign — env alone is NOT enough):
- Route `_call_model` and `_call_model_stream` through a call-time `_serving_base()` that returns `A11OY_MODEL_BASE_URL` when it's set and non-router, else the HF router. They are currently HARD-CODED to `HF_ROUTER_BASE` — that's the bug.
- ADD a tier→local-model map (T0–T6 + the code agent → your served tag, e.g. `qwen2.5-coder-7b`; general/chat → `llama3.1:8b`). WITHOUT this map, local turns 404.
- `_inference_headers()` must SKIP the HF bearer when the base is the local endpoint.
Keep it byte-identical if the touched module is shared (edit a11oy + killinchu identically); `ast.parse` the .py before push; push GitHub + HF byte-identical. Then `sudo a11oy-rebuild`.

### 3. PROVE it (all must hold — paste the outputs into your STATUS reply)
```bash
curl -s https://a-11-oy.com/api/a11oy/code/healthz | jq '.sovereign,.inference,.gpu,.key_resolution.base_url,.key_resolution.env_used,.key_resolution.honest_note'
# REQUIRED: sovereign=true, inference="self-hosted-gpu", base_url = the LOCAL endpoint (NOT router.huggingface.co), env_used != "HF_TOKEN"
```
AND run ONE governed proof turn through `POST /api/a11oy/code/chat/stream` and confirm `event:route` shows `model` = your local tag AND there is **NO cost_usd** (local inference = free). Only when base_url is local AND a real turn is served by the GPU is `sovereign:true` TRUE.

### 4. While you're on the box: #323 autodeploy
`systemctl status a11oy-autodeploy.timer`; `sudo /usr/local/bin/a11oy-autodeploy-check; echo exit=$?`; `cat /var/lib/a11oy-autodeploy/last_deployed_sha`. Fix the timer if dead, and COMMIT the real `a11oy-rebuild` script to `ops/a11oy-rebuild` (it's currently uncommitted = reproducibility hole).

## INVARIANTS (never violate)
open-weight models only; set `A11OY_GPU_LABEL` ONLY when the model TRULY serves on the GPU; NO cost_usd on a local turn; locked-proven = 8 {F1,F4,F7,F11,F12,F18,F19,F22}; Λ=Conjecture 1; Khipu=Conjecture 2; trust never 100%; SLSA L1 honest + L2 attested, L3/FedRAMP/IronBank/CMMC/ATO = roadmap only; killinchu effector SIMULATED; 0 runtime CDN; no user-visible product codenames; GitHub↔HF byte-identical on shared szl_*.py; NEVER commit a key; never weaken a gate. If a step needs a cosign-signed artifact / Rekor / warn→enforce, STOP and notify the founder for approval — do not auto-do those.

## REPLY — REQUIRED (this is how I know you started)
Drop `platform/replit-sync/forge-STATUS-20260612.md` NOW with: (1) "STARTED Path A at <time>"; (2) which server (Ollama/vLLM) + `curl /v1/models` output; (3) the post-rebuild healthz jq output from step 3; (4) the proof-turn route.model + cost_usd; (5) #323 autodeploy findings. The CTO agent will re-verify live within minutes of your reply and sync the in-app surfaces + UDS bundles to match.

If you genuinely CANNOT make it sovereign before Warhacker, the ONLY acceptable fallback is the honest revert (`unset A11OY_MODEL_BASE_URL A11OY_GPU_LABEL` + `sudo a11oy-rebuild` → banner reads hf-router/sovereign:false) — and say so in STATUS. The half-state is NOT acceptable. GO.
