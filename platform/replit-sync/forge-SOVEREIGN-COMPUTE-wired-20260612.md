# Sovereign Compute pane is now WIRED + LIVE (no GPU dependency)

Date: 2026-06-12 ~07:15 UTC · by Perplexity Computer (autonomous, founder green-light)

## What I found
You added `szl_sovereign_compute.py` but it was never wired:
- It was **absent from every Dockerfile COPY line** (this Dockerfile never uses `COPY . .`), so `import szl_sovereign_compute` would fail at boot.
- It was **never registered** in serve.py, so `/sovereign-compute` fell through to the SPA shell (200 but generic) and `/api/a11oy/v1/sovereign-compute` 404'd.
- Its probes had two bugs: brain probed `/api/a11oy/v1/code/health` (doesn't exist — real route is `/api/a11oy/code/healthz`); and a synchronous urllib **loopback self-call from an async handler deadlocked** the single uvicorn worker -> both caps showed `UNREACHABLE / TimeoutError`.

## What I fixed (a11oy-only files; byte-identical GitHub + HF; doctrine-green)
1. **Dockerfile** (`6a15f9ae`): added `szl_sovereign_compute.py` to the per-file COPY.
2. **serve.py** (`ed42065b`): registered the module like every other organ + moved its 2 routes to the FRONT of `app.router.routes` (beats the SPA catch-all + Node proxy).
3. **szl_sovereign_compute.py** (`b7a24ea5`): probes now run **IN-PROCESS** — brain calls `a11oy_code_orchestrator._sovereign_inference_state()`, embeddings calls `szl_alloy_embed_fabric._embed_backend()` (HTTP loopback kept only as a fallback). No more self-HTTP deadlock.

## Live now (HONEST)
`GET https://szlholdings-a11oy.hf.space/api/a11oy/v1/sovereign-compute`:
- brain: **LIVE-MANAGED** (hf-router) · embeddings: **HONEST-STUB** (catalog-only)
- PQC / Iron Bank / Wire-D mesh: **ROADMAP** (labelled, not faked)
- summary: "MANAGED/STUB — not yet on our GPU", sovereign_any: false

## The auto-flip is staged end-to-end
The moment you bring up vLLM on the RTX 5000 and set on the a11oy.net deploy:
- `A11OY_MODEL_BASE_URL=http://127.0.0.1:8000/v1`
- `A11OY_GPU_LABEL=NVIDIA RTX 5000 @ Hetzner`
…then `_sovereign_inference_state()` emits `inference:self-hosted-gpu, sovereign:true, gpu:<label>`, and this pane **auto-flips brain -> LIVE-SOVEREIGN** with zero further code change. (Embeddings flip too if you also set `A11OY_EMBED_BASE_URL` to a self-hosted TEI/vLLM `/embeddings` endpoint.)

Also fixed: mesh bundle `expect_digest` in szl_warhacker_real.py was stale after the 05:25Z CI republish of uds-v0.3.0 — re-pinned to the live `sha256:50ebc519…0656a` (correctly .sig+.att signed). Deploy Posture now shows all 3 bundles `digest_matches_expected:true`.

Estate: CI all green, 3 Spaces RUNNING, 46 shared modules byte-identical.
