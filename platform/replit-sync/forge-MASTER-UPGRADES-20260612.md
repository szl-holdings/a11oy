# FORGE MASTER ORDER — Upgrades & Wiring to wow Warhacker (T-4)
**From:** CTO/PM agent (founder green-lit, autonomous) · **To:** Forge · June 12 2026, ~1:00 AM EDT.
**Context:** Full read-only recon of a11oy + killinchu + szl-uds-deployment is done (see `team/RECON_GAP_INVENTORY.md`). Headline: **the estate is code-complete and unusually clean — ZERO TODO/FIXME in app/deploy source, all 18 agent tools are REAL (none faked), every "gap" is a deliberately honest label enforced by guards.** So the remaining wins are **wiring credentials/feeds/cluster + one GPU bring-up** — NOT writing missing code. This is the prioritized list of what I need from you, ranked by Warhacker demo impact. Items are independent; do as many as you can.

---

## TIER 1 — DO THESE FIRST (each is a huge visible jump for little effort)

### 1. Bring a11oy-Code ALIVE on the RTX 5000 (already ordered — `forge-GPU-a11oy-code-ALIVE-20260611-night.md`)
- vLLM serving `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ` (or Llama-3.1-8B unquantized) on the GPU, OpenAI-compatible.
- On the **a11oy.net (Hetzner) deployment** set: `A11OY_MODEL_BASE_URL=http://127.0.0.1:8000/v1` + `A11OY_GPU_LABEL=NVIDIA RTX 5000 @ Hetzner`. Restart.
- Verify: `curl https://a11oy.net/api/a11oy/code/healthz | jq '.inference,.backend,.gpu,.sovereign'` → expect NOT "hf-router", `backend:"generative"`, `gpu:"NVIDIA RTX 5000 @ Hetzner"`, `sovereign:true`.
- **The engine GPU-label code is already shipped & live (commit `63fca023`/`f691f8a7`, byte-identical).** This is pure ops + 2 env vars.
- *Impact:* sovereign local-GPU governed agent = the literal cloud→edge story. **#1 wow.**

### 2. Set an inference credential on the a11oy HF Space (if you want the HF Space agent live too)
- Any one of `A11OY_CODE_LLM_KEY` / `OPENROUTER_API_KEY` / `HF_TOKEN` (HF_TOKEN is already present → Space already reports `mode: live`, streams Llama-3.3-70B — verified). So this is DONE for HF; the GPU item above is the sovereign upgrade. No action unless you want a specific provider.

### 3. Wire the cosign / ECDSA signing key → flip every DSSE_PLACEHOLDER to a real, Rekor-verifiable signature
- Inject `SZL_COSIGN_PRIVATE_KEY_PEM` (a11oy receipts) and/or `COSIGN_ECDSA_KEY` (UDS `operator/receipts/checksums.txt`) into the Space/Hetzner env + CI.
- Affects: `a11oy_code.py`, `szl_brain.py:195`, `a11oy_v4_hickok.py`, `a11oy_vertical_feeds.py`, `a11oy_warhacker_obs.py`, UDS `operator/receipts/*`.
- *Impact:* "tamper-evident" → **non-repudiable**. Every receipt becomes cosign+Rekor verifiable on screen. **HARD-LIMIT: this is a signed-artifact/key op — founder must approve the key handling. Do NOT commit the key; inject as a secret only.**

### 4. Set the flagship/app-command base envs → lights up ~5 cross-organ agent tools
- `AMARU_BASE`, `SENTRA_BASE`, `ROSIE_BASE`, `KILLINCHU_BASE` on the a11oy deployment.
- Activates `flagship_call`, `drone_command`, `app_command` (today they return honest `gap:true`).
- *Impact:* live cross-organ orchestration on the command bus — the agent can actually drive the mesh.

### 5. Provide a gh credential in the a11oy Space → enables `github_read_file/open_issue/open_pr`
- A scoped GitHub token as a Space secret (read + issues + PR on szl-holdings).
- *Impact:* live demo of the agent reading a repo and opening a **2-person-gated** PR/issue end-to-end.

---

## TIER 2 — CLUSTER PROOFS & POLICY TEETH (run on the tower, capture green for the outbrief)

### 6. The offline air-gap deploy proof (already ordered — `forge-OFFLINE-DEPLOY-PROOF-20260611-night.md`)
- `cosign verify` + `cosign verify-attestation --type spdxjson` on `szl-uds-bundle:uds-v0.3.0` (Rekor already logged — confirmed), then `uds pull` → CUT THE CABLE → `uds deploy` → member `Available`. Capture the terminal triple. **#1 Day-3 evidence clip.**

### 7. Run the cluster proofs via workflow_dispatch and capture green
- `Prove Bundle Install` (organ=all), `Prove Organs`, `test-install`, `test-upgrade`, `a11oy-sso-login-proof` (issue #76).
- These are dispatch/nightly-only (skipped on PR) and have never had a green CI run — they need real cluster + Sigstore TUF egress the GitHub runner lacks. Run them on the tower; a fresh manual green proves real install+upgrade+SSO on demand.

### 8. Flip UDS cosign policy `mode: warn → enforce`
- Per `UDS_DEPLOY_RUNBOOK.md:88` — dry-run on a scratch ns, confirm green dress rehearsal, then flip.
- *Impact:* real admission-control teeth (blocks unsigned), not advisory warnings. **HARD-LIMIT: warn→enforce is a gated transition — confirm with founder before flipping in any prod-facing ns.**

### 9. Fix the two pre-existing CI reds (from prior order)
- `Operational Validation` (a11oy) — chronic red since ≥2026-06-09; reproduce `bash scripts/validate-operational.sh && npm run payload:bundle:verify` locally, fix the non-zero step (likely a node/pnpm build artifact). It's path-gated + not a required check, but clearing it makes the CI board all-green for judges.
- `Prove Bundle Install`/`Prove Organs` — see #7 (env, not defect).

---

## TIER 3 — LIVE-DATA UPGRADES (turn SAMPLE/MOCK into live intelligence)

### 10. Wire a real C-UAS sensor/telemetry feed into `killinchu_drone_routes.py`
- Today friendly positions + threat tracks are MOCK/synthetic (honestly labeled). The protocol decoders (Remote-ID ASTM F3411-22a, ADS-B via pyModeS, MAVLink via pymavlink) are **already real** — this is a feed connection, not a rewrite. Keep the effector SIMULATED (doctrine).
- *Impact:* the flagship counter-UAS board goes live.

### 11. Swap killinchu maritime AIS sample-replay + sample OFAC list for live feeds (`killinchu_v3.py`)
- Live AIS (e.g. an AIS provider key) + real OFAC SDN / UN / EU sanctions lists.
- *Impact:* maritime/sanctions view becomes live intelligence instead of replay.

### 12. Wire a real metric stream into `a11oy_wireA_metrics.py` (conformal coverage demo on sample residuals today).

---

## TIER 4 — SUPPLY-CHAIN HARDENING (post-Warhacker fast-follow, but start now if time)

### 13. Add `liboqs`/`oqs-python` to the a11oy + killinchu image → flips PQC (ML-DSA/ML-KEM/SLH-DSA) `ROADMAP → LIVE` hybrid signing (`a11oy_amaru_feeds.py`). Never fabricates a PQC sig today; adding the lib makes it real.
### 14. Migrate base images to Iron Bank `registry1.dso.mil/ironbank/...` (issue #164) → unblocks the FedRAMP/CMMC pre-work and IL-5/IL-6 suitability.
### 15. Implement Wire D (cross-mesh `traceparent` propagation) — `traceparent` is in-process only today (`YACHAY_SYSTEM_PROMPT.md:57`). This is the one genuine missing code feature; it needs ≥2 organs running to be meaningful (mesh/Hetzner context), so it's yours, not an in-Space edit. End-to-end distributed trace across organs = a strong observability story.
### 16. HSM/KMS for key custody (`KEY_CUSTODY_RUNBOOK.md:31`) — the remaining gap to DoD-deployable key handling.
### 17. Flux wrapper for the szl chart (killinchu `big_bang_inventory.json` roadmap) + in-cluster mTLS (STATUS.md v0.5.0).

---

## DOCTRINE (every item honors)
locked-proven = EXACTLY 8; Λ = Conjecture 1; Khipu = Conjecture 2; SLSA never bare L3/FedRAMP/IronBank/CMMC/ATO without "roadmap" on-line (SLSA "L1 honest" is the standing claim); no user-visible codenames (organ names amaru/sentra/rosie/killinchu in member/alias context are fine); trust never 100%; 0 runtime CDN; no fabricated data (keep SAMPLE/SIMULATED/PROXY labels until the real feed is wired); killinchu effector stays SIMULATED; GitHub↔HF byte-identical on shared modules; ast.parse before push; **NEVER commit a key**; never weaken a gate.

## WHAT I'VE ALREADY DONE (so you don't redo it)
- uds-v0.3.0 unified bundle: published + cosign-signed + Rekor-logged + SBOM-attested; in-app Deploy Posture surfaces it live (digest-matched, all 3 bundles).
- a11oy-Code GPU-label engine shipped byte-identical both apps; HF Space agent already `mode: live` (Llama-3.3-70B, real governed loop w/ PURIQ gate verified denying an unsafe shell_exec).
- All doctrine/drift/CI green; 46 shared modules byte-identical; 3 Spaces RUNNING; killinchu honest-count 5→8 fixed; deploy badges PENDING→PUBLISHED+SIGNED.

## REPORT BACK
For each item you complete, drop a one-line status in `platform/replit-sync/forge-STATUS-<date>.md` with the verify command output (esp. the GPU healthz `sovereign:true` and the offline-deploy `cosign verify` PASS + `Available`). I'll re-verify live and update the in-app surfaces to match.
