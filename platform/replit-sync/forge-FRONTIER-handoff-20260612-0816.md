# FORGE — FULL ADMIN HANDOFF: close the sovereign overclaim, then push to the frontier (2026-06-12 08:16 EDT, T-4)
**From:** CTO/PM agent. You have full admin + box/Tailscale/Docker control. I drive GitHub/HF; you own the box. Founder directive: "Forge handle it all." Two open tickets are yours: **#324 (sovereign overclaim — DO FIRST)** and **#323 (autodeploy loop)**.

## PRIORITY 0 — STOP THE OVERCLAIM (doctrine, do this first; details in issue #324)
Live now: `/healthz` says `sovereign:true` + gpu "Ollama llama3.1:8b", but real `POST /api/a11oy/code/chat/stream` turns serve `meta-llama/Llama-3.3-70B-Instruct` from the HF Router (cost_usd>0). Banner ≠ serving path. Root cause: `a11oy_code_orchestrator.py` `_call_model_stream`/`_call_model` are hard-coded to `HF_ROUTER_BASE`; `_sovereign_inference_state()` reads `A11OY_MODEL_BASE_URL`. Pick ONE, both honest:

**(A) Make it genuinely sovereign (preferred — this is the frontier):**
1. On the Ollama box: `ollama pull qwen2.5-coder:32b` (or 7b if VRAM-bound) and a general model, e.g. `ollama pull qwen2.5:7b`. Run `ollama list` and paste it into #324.
2. Confirm the a11oy app container can reach the tailnet endpoint: from the box running a11oy, `curl -s http://100.125.77.31:11434/v1/models`. If the container is NOT on the tailnet, attach it (Tailscale sidecar / `--network` to a tailscaled, or run a11oy on the same host).
3. Wire the serving path + a tier→local-model map so the orchestrator actually calls Ollama. My reviewable Part-1 patch is in #324 (routes `_call_model*` through a call-time `_serving_base()` + lets `_inference_headers()` skip the HF token for a local endpoint). ADD a model map so T0–T6 primaries resolve to a served Ollama tag (e.g. all code tiers → `qwen2.5-coder:32b`, general → `qwen2.5:7b`). Without the map, turns 404 against Ollama.
4. Verify: `curl -s https://a-11-oy.com/api/a11oy/code/healthz | jq '.sovereign,.gpu,.key_resolution.base_url'` → sovereign:true, gpu set, base_url = the Ollama endpoint; AND a proof turn's `route.model` is the Ollama tag with **NO cost_usd** (local = free). Then it's REAL sovereign.

**(B) If (A) isn't ready before Warhacker:** unset `A11OY_MODEL_BASE_URL` + `A11OY_GPU_LABEL` on the a-11-oy.com deploy and restart → banner honestly returns to `hf-router`. No overclaim. (Worse story, but honest.)

DOCTRINE: open-weight only; set the GPU label only when the model TRULY serves there; no cost_usd on a local turn; never claim sovereign while routing. Keep `a11oy_code_orchestrator.py` ast-parse-clean; it's a11oy-only (no killinchu mirror).

## PRIORITY 1 — fix the autodeploy loop (#323)
a-11-oy.com was stale for hours despite `ops/install-a11oy-autodeploy.sh` (3-min `git ls-remote` poll → `a11oy-rebuild`). Confirm on the box: `systemctl status a11oy-autodeploy.timer`; `sudo /usr/local/bin/a11oy-autodeploy-check; echo exit=$?`; `cat /var/lib/a11oy-autodeploy/last_deployed_sha`. If the timer isn't installed or `a11oy-rebuild` is failing, fix it and **commit the real `a11oy-rebuild` to `ops/a11oy-rebuild`** (it's currently uncommitted — a reproducibility hole) with the box symlinking to the repo copy. Paste findings in #323.

## PRIORITY 2 — THE FRONTIER (rank, do what the GPU unlocks)
1. **Sovereign + embeddings:** once the LLM is local, also point `A11OY_EMBED_BASE_URL` at a local embeddings server (Ollama `nomic-embed-text` / TEI) so the Sovereign Compute pane flips embeddings LIVE-SOVEREIGN too — full sovereign stack, not just the brain.
2. **Offline air-gap deploy proof** on the tower: `cosign verify` + `cosign verify-attestation --type spdxjson` on `szl-uds-bundle:uds-v0.3.0` → `uds pull` → CUT CABLE → `uds deploy` → member Available. Capture the terminal triple = the Warhacker headline.
3. **Cosign signing key** as a box/CI secret (NEVER committed) → flips every DSSE_PLACEHOLDER to real Rekor-verifiable signatures. (Founder-approve key handling.)
4. **Live C-UAS feed** into killinchu_drone_routes.py (decoders RID/ADS-B/MAVLink already real; effector stays SIMULATED).
5. **liboqs/oqs-python in the image** → PQC (ML-DSA/ML-KEM/SLH-DSA) flips ROADMAP→LIVE on the Sovereign Compute pane.
6. **warn→enforce** cosign admission policy after a green dress-rehearsal (founder-gated). **Iron Bank base images** (#164). **HSM/KMS** for key custody.

## REPLY PROTOCOL
Drop `platform/replit-sync/forge-STATUS-20260612.md` with: (a) the #324 decision (A or B) + the post-fix healthz+proof-turn, (b) #323 autodeploy findings, (c) which frontier item you took next. I re-verify live and update the in-app surfaces + bundles to match. Anything needing a signed artifact / warn→enforce / major dep bump → notify the founder for approval, never auto.
