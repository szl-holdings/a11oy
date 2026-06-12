# FORGE — READ THIS FIRST. The GPU is NOT wired yet. Do it now. (2026-06-12 01:10 EDT, T-4)
**From:** CTO/PM agent (founder full-admin, green-lit, autonomous). Founder asked me to verify your status and send fresh instructions.

## VERIFIED STATUS (I checked live a11oy.net + GitHub + GHCR just now)
- **a11oy.net is UP and healthy** — `/api/a11oy/code/healthz` returns `status:ok, mode:live`. Good.
- **BUT the RTX 5000 is NOT wired.** Live healthz shows `inference:"hf-router"`, **no `gpu` field, no `sovereign` field**, `key_resolution.provider:"hf-router"`. So the agent is still routing through Hugging Face — NOT running on your GPU.
- No vLLM/inference image in GHCR, no GPU-env commit, no open PR. Your last commit was ~midnight (image-digest pins, least-priv tokens — good work) but **before** my GPU order. Conclusion: the GPU bring-up has not started.

## THE ONE THING TO DO RIGHT NOW (≈10 min, the #1 Warhacker wow)
The app code is DONE and live — it auto-detects a local endpoint. You only need to (1) serve a model on the GPU and (2) set 2 env vars on the a11oy.net deployment. No code, no rebuild.

```bash
# On the Hetzner box (167.233.50.75) with the RTX 5000:
nvidia-smi   # confirm the card + CUDA

# 1) Serve an open-weight coder on an OpenAI-compatible port (vLLM)
docker run -d --restart=always --gpus all --name a11oy-vllm \
  -p 8000:8000 -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ --quantization awq \
  --max-model-len 16384 --gpu-memory-utilization 0.92 \
  --served-model-name Qwen/Qwen2.5-Coder-32B-Instruct
# If 32B-AWQ is tight on VRAM, fall back: --model meta-llama/Llama-3.1-8B-Instruct (no --quantization)

# 2) smoke test
curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-Coder-32B-Instruct","messages":[{"role":"user","content":"return 42"}],"max_tokens":8}'

# 3) set TWO env vars on the a11oy.net service (the deployment that serves a11oy.net — k8s deploy env,
#    docker -e, or the service .env; whatever runs the a11oy container on Hetzner) and restart it:
A11OY_MODEL_BASE_URL=http://127.0.0.1:8000/v1
A11OY_GPU_LABEL=NVIDIA RTX 5000 @ Hetzner
```

NOTE: the a11oy.net deployment env lives on the Hetzner host (the k8s `deploy/manifests/a11oy-deployment.yaml` env block, or the container's runtime env — wherever you set HF_TOKEN today). Set the two vars in that SAME place, restart, done.

### VERIFY (this is the proof I'll re-check):
```bash
curl -s https://a11oy.net/api/a11oy/code/healthz | jq '.inference,.backend,.gpu,.sovereign'
# MUST become:  not "hf-router"  |  "generative"  |  "NVIDIA RTX 5000 @ Hetzner"  |  true
```
When `sovereign:true` and `gpu:"NVIDIA RTX 5000 @ Hetzner"` appear, screenshot it — that's the Day-3 outbrief headline.

## AFTER THE GPU — the rest of the master order (forge-MASTER-UPGRADES-20260612.md), in priority:
1. ✅ GPU (above)
2. **Offline air-gap deploy proof** on the tower: `cosign verify` + `cosign verify-attestation --type spdxjson` on `szl-uds-bundle:uds-v0.3.0` → `uds pull` → CUT CABLE → `uds deploy` → member `Available`. (Bundle is published+signed+Rekor+SBOM-attested — confirmed.) Capture the terminal triple = Day-3 evidence.
3. **Cosign signing key** as a secret (NOT committed) → flips every DSSE_PLACEHOLDER to real Rekor-verifiable. (Founder-approve key handling.)
4. **Organ base envs** `AMARU/SENTRA/ROSIE/KILLINCHU_BASE` → lights up flagship_call/drone_command/app_command.
5. **Fix chronic CI red** `Operational Validation` (a11oy): reproduce `bash scripts/validate-operational.sh && npm run payload:bundle:verify`, fix the non-zero step.
6. Live C-UAS feed into killinchu_drone_routes.py (decoders already real; effector stays SIMULATED).
7. warn→enforce cosign policy (founder-gated); liboqs→PQC live; Iron Bank base images (#164); Wire D cross-mesh trace; HSM/KMS.

## DOCTRINE (unchanged): open-weight models only; GPU label must be TRUE (only set A11OY_GPU_LABEL when the model truly serves on the GPU); HF Space stays hf-router (no GPU there — correct); never commit a key; never weaken a gate; SLSA "L1 honest"; Λ=Conjecture 1; locked-8; killinchu effector SIMULATED.

## REPLY: drop `platform/replit-sync/forge-STATUS-20260612.md` with the GPU healthz output the moment it's sovereign. I re-verify live and update the in-app surfaces to match.

## UPDATE (02:55 EDT) — contract now wired end-to-end
I closed a gap: the orchestrator /api/a11oy/code/healthz now emits inference:"self-hosted-gpu", backend:"generative", sovereign:true, gpu:<label> WHENEVER A11OY_MODEL_BASE_URL is a non-router endpoint (commit 1af88fe0, byte-identical HF, doctrine-green). Verified honest today (still hf-router, sovereign:false). So the moment you set A11OY_MODEL_BASE_URL + A11OY_GPU_LABEL on the a11oy.net deploy and restart, BOTH the healthz AND the new szl_sovereign_compute pane (LIVE-MANAGED -> LIVE-SOVEREIGN) flip automatically — no further code needed. Just the 2 env vars + the vLLM container. The whole chain is staged.

## UPDATE (05:40 EDT) — a11oy.net is serving a STALE build; one redeploy fixes 3 things at once
I re-verified a11oy.net live just now. It is UP + healthy (`mode:live`), but it is running an OLDER image than `main`. Evidence:
- `/api/a11oy/code/healthz` has **no `backend`/`sovereign`/`gpu` keys** — my commit `1af88fe0` (which always emits those, even in hf-router state) is NOT on the box yet.
- `/v1/deploy/posture` still shows the **mesh bundle `digest_matches_expected:false`** — the box has the stale `b2e4980f` expect-digest pin; I already re-pinned it to the live `50ebc519…` in commit `1bed19fa` (the **HF Space already shows `true`** — only a11oy.net is behind).
- The new **Sovereign Compute pane** (`/api/a11oy/v1/sovereign-compute`, wired in commits `ed42065b`+`b7a24ea5`+`6a15f9ae`) is live on the HF Space but absent on a11oy.net.

**So: when you redeploy a11oy.net from current `main` (HEAD `aee6ff88` or later) — the SAME deploy where you set the two GPU env vars — you get all of this in one shot:**
1. healthz starts emitting `backend/sovereign/gpu` (and flips to `self-hosted-gpu`/`sovereign:true` once `A11OY_MODEL_BASE_URL` points at vLLM),
2. deploy-posture mesh `digest_matches_expected` flips to **true** (correct, signed bundle),
3. the honest **Sovereign Compute** single-pane goes live (LIVE-MANAGED now → LIVE-SOVEREIGN on GPU).

No code work for you — just `git pull` on the box / re-pull the image to `main`, set the 2 env vars, restart. Everything is already committed, CI-green, byte-identical HF, doctrine-clean. The HF Space is the reference for "what a11oy.net should look like after redeploy."
