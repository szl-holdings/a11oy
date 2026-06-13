# FORGE — CODE IS DONE. The serving-path rewire (#324) is shipped + live. ONLY the box step remains. 2026-06-12 21:48 EDT.
An Opus 4.8 dev just WIRED the real serving path (no bandaid). a11oy main HEAD = 730dc929 (blob 91a7fb28), deployed byte-identical to the HF Space (oid match), ast.parse-clean, verified live with NO regression (HF Space stays honest: sovereign:false / hf-router, router turns work, Khipu chain_verified:true).

## WHAT THE CODE NOW DOES (so you don't have to touch app code)
- `_serving_base()` returns the LOCAL endpoint (is_local=True) the instant `A11OY_MODEL_BASE_URL` is a non-router URL AND it actually answers; else the HF Router. The SERVING path and the REPORTED posture both derive from the SAME reachability probe, so sovereign:true <=> turns are truly served on the GPU. No overclaim is possible anymore.
- `_call_model` + `_call_model_stream` POST to that resolved base; `_inference_headers(is_local)` skips the HF bearer for a local endpoint; a tier->local-model map (env-overridable) translates ids to your served tags; cost_usd stays 0 on local turns.
- Router fallback preserved: local-set-but-unreachable serves via router + honestly reports sovereign:false (this is why HF Spaces stay honest).

## THEREFORE — the ONLY remaining action is on the BOX (sudo-gated, yours):
1. Serve an open-weight model on the betterwithage GPU, OpenAI-compatible:
   - Ollama: `ollama pull qwen2.5-coder:7b` (code) + keep `llama3.1:8b` (general); `curl -s http://127.0.0.1:11434/v1/models` must list them.
   - or vLLM: `docker run -d --restart=always --gpus all -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface vllm/vllm-openai:latest --model Qwen/Qwen2.5-Coder-7B-Instruct --max-model-len 16384 --served-model-name qwen2.5-coder-7b`; `curl -s http://127.0.0.1:8000/v1/models`.
2. Set on the a11oy.net deploy env (.env / compose / systemd EnvironmentFile):
   `A11OY_MODEL_BASE_URL=http://127.0.0.1:11434/v1`   (vLLM: http://127.0.0.1:8000/v1)
   `A11OY_GPU_LABEL="NVIDIA RTX 5000 @ Hetzner (betterwithage)"`
   (optional exact tags) `A11OY_LOCAL_CODE_MODEL=qwen2.5-coder:7b`  `A11OY_LOCAL_GENERAL_MODEL=llama3.1:8b`
3. `sudo a11oy-rebuild`   <-- the only sudo step; CI/agent cannot do this.

## PROVE (paste into forge-STATUS):
`curl -s https://a11oy.net/api/a11oy/code/healthz | jq '.sovereign,.inference,.gpu,.key_resolution.base_url,.key_resolution.env_used'`
REQUIRED: sovereign=true, inference="self-hosted-gpu", base_url = the LOCAL endpoint (NOT router.huggingface.co), env_used != "HF_TOKEN".
AND one `/api/a11oy/code/chat/stream` turn: event:route model = your local tag, NO cost_usd.

If the model server isn't reachable when you rebuild, the app will (correctly) stay sovereign:false and serve via the router — so make `curl /v1/models` succeed BEFORE the rebuild.

## #323 while on the box: `systemctl status a11oy-autodeploy.timer`; `sudo /usr/local/bin/a11oy-autodeploy-check; echo exit=$?`; commit the real `a11oy-rebuild` to `ops/a11oy-rebuild`.

INVARIANTS: open-weight only; GPU label ONLY when it truly serves; no cost on local turns; locked=8; Λ=Conjecture 1; never commit a key; never weaken a gate; cosign/Rekor/warn->enforce = founder approval only. REPLY via platform/replit-sync/forge-STATUS-20260612.md.
