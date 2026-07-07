<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 - Doctrine v11
-->

# Sovereign Mesh Runbook — harness the 2-box GPU mesh behind ONE endpoint

**You are at the LAPTOP (`betterwithage`, RTX 5050) right now.** These are your hands —
the cloud agent cannot reach your LAN. Follow the PowerShell baby-steps in order.
Copy-paste one block at a time and read the "you should see" line before moving on.

**What we are building:** the cloud a11oy Space calls **ONE** endpoint
(`gateway.a-11-oy.com`, model `sovereign-llm`); a **LiteLLM** gateway load-balances
your two Windows GPU boxes (tower `omen` RTX 4060 Ti + this laptop `betterwithage`
RTX 5050), both running **Ollama**. Everything is durable (boot-persistent tasks) and
self-healing (restart policies + LiteLLM node cooldown). Cloudflare = public ingress,
Tailscale = private transport, Docker = the stateless sidecars only.

```
a11oy Space (cloud)
   |  HTTPS + Bearer + CF-Access-Client-*    (ONE endpoint)
   v
Cloudflare edge (Access service token)  ->  gateway.a-11-oy.com
   v  (cloudflared, outbound-only tunnel)
LiteLLM :4000  (model "sovereign-llm")
   |  Tailscale (private, tailnet-only :11434)
   +--> omen         Ollama  (llama3.1:8b)
   +--> betterwithage Ollama (glm-4.7-flash + the #789 energy probe)
```

> **HONESTY (Doctrine v11).** Nothing below "goes green" on faith. A node is only
> `wired`/`live` when a **real** call to it succeeds THIS request. Joules are
> **MEASURED** only from a real NVML delta (the #789 probe); otherwise the honest
> `MEASURED_SHARED_BOUNDED` / `UNAVAILABLE` empty-state stands. A truthful BLOCKED
> beats a fake green. **Ollama's `:11434` is never public.**

---

## 0. Prerequisites (one-time, on the laptop)

```powershell
# Confirm the driver + GPU are visible (native, no Docker).
nvidia-smi
# you should see: your RTX 5050 listed, a driver version (want 535+), and power draw.

# Confirm Ollama, Tailscale, cloudflared, python are installed.
ollama --version
tailscale version
cloudflared --version
python --version    # or: py --version
```

If `nvidia-smi` shows the GPU but `power.draw` is `N/A` (some laptop GPUs do), the
#789 probe will honestly emit `UNAVAILABLE` rather than a fake joule — that is fine,
the mesh still works, you just do not get MEASURED joules from this box.

---

## Step (a) — pull glm-4.7-flash + start the #789 energy probe on the laptop

```powershell
# 1. Pull the laptop's model.
ollama pull glm-4.7-flash

# 2. Make sure Ollama accepts the tunneled Host header + binds for the tailnet.
#    (These are the machine-level env the persist script sets; safe to set now.)
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS","*","Machine")
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST","0.0.0.0:11434","Machine")

# 3. Start the #789 per-inference energy probe in a LOOP (refreshes every 60s).
#    Writes ~/.a11oy_ollama_energy.json which omen_joule_exporter.py merges as models[].
$env:OLLAMA_MODEL = "glm-4.7-flash:latest"
python box-scripts\ollama_energy_probe.py --loop 60
# you should see: a line per cycle with joules + a VERBATIM label
#   (MEASURED_SHARED_BOUNDED by default; MEASURED only if you assert exclusivity;
#    UNAVAILABLE if NVML/power.draw cannot be read — never a fabricated number).
```

Leave that window running. (For the durable version, `box-scripts\laptop_persist.ps1`
registers Ollama + the exporter + the `laptop-szl` tunnel as AtStartup tasks — run it
**as Administrator** once you have verified the manual path works.)

> **Clean MEASURED (optional):** only if *nothing else* uses the GPU during the window:
> `$env:OLLAMA_GPU_EXCLUSIVE = "1"` before launching the probe. Otherwise keep the
> honest `MEASURED_SHARED_BOUNDED` upper bound — do not upgrade the label.

---

## Step (b) — start LiteLLM (the unified gateway)

Run LiteLLM on the **always-on** box. If the laptop is your always-on box for now,
run it here; normally it lives on `omen`. Two ways — pick ONE.

### (b-native) Native Python — simplest, no Docker/WSL2 (RECOMMENDED to start)

```powershell
pip install "litellm[proxy]"

# Bearer the Space must send (generate a real random key; keep it secret).
$env:LITELLM_MASTER_KEY   = "sk-REPLACE-with-a-real-random-key"
# The shared pool model (must fit BOTH cards for true load-balancing).
$env:SOVEREIGN_POOL_MODEL = "llama3.1:8b"
# Tailscale MagicDNS names (or 100.x IPs from `tailscale ip -4` on each box).
$env:OMEN_OLLAMA_URL      = "http://omen:11434"
$env:BWA_OLLAMA_URL       = "http://betterwithage:11434"
$env:OMEN_MODEL           = "llama3.1:8b"
$env:BWA_MODEL            = "glm-4.7-flash:latest"

litellm --config box-scripts\litellm_config.yaml --port 4000
# you should see: "Uvicorn running on http://0.0.0.0:4000".
```

Verify locally (new PowerShell window):

```powershell
curl.exe -s http://localhost:4000/health/liveliness
# you should see: {"status":"healthy"...}

curl.exe -s http://localhost:4000/v1/models -H "Authorization: Bearer $env:LITELLM_MASTER_KEY"
# you should see: sovereign-llm, omen-llama, betterwithage-glm in the list.

curl.exe -s http://localhost:4000/v1/chat/completions `
  -H "Authorization: Bearer $env:LITELLM_MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d '{"model":"sovereign-llm","messages":[{"role":"user","content":"say ok"}]}'
# you should see: a real completion (proves LiteLLM reached a live Ollama node).
```

### (b-docker) Containerized sidecars — Ollama STILL native

> **WSL2 GPU passthrough is fragile.** Only the *sidecars* go in Docker; Ollama and
> the #789 probe stay native (Step a). If `dcgm-exporter` cannot get the GPU, comment
> it out and rely on the native probe for joules — the meter path does not need it.

```powershell
# .env next to the compose file (NEVER commit it):
#   LITELLM_MASTER_KEY=sk-...      CF_TUNNEL_TOKEN_GPU=...(if using token mode)
#   OMEN_OLLAMA_URL=http://host.docker.internal:11434   (native Ollama on THIS box)
#   BWA_OLLAMA_URL=http://betterwithage:11434            (tailnet)
docker compose -f box-scripts\docker-compose.yml up -d litellm prometheus grafana
docker compose -f box-scripts\docker-compose.yml ps
# you should see: litellm (healthy). On the laptop, use docker-compose.laptop.yml
# which is telemetry-only (dcgm-exporter).
```

---

## Step (c) — verify meter2 `models[]` appears

The #789 probe (Step a) writes energy JSON; `omen_joule_exporter.py` (engine name
`betterwithage` on the laptop) merges it as top-level `models[]` and serves it on
`:9471`, tunneled as `meter2.a-11-oy.com`.

```powershell
# Local exporter (if not already running via laptop_persist.ps1):
$env:OMEN_ENGINE_NAME = "betterwithage"
python box-scripts\omen_joule_exporter.py     # serves 0.0.0.0:9471

# Local check:
curl.exe -s http://localhost:9471/ | python -m json.tool
# you should see: engines[] with engine "betterwithage" AND a top-level models[]
#   entry for glm-4.7-flash with joules_per_token + a VERBATIM label
#   (or an UNAVAILABLE null if NVML/power.draw is not readable — honest, not fake).

# Public check (through the laptop-szl tunnel):
curl.exe -s https://meter2.a-11-oy.com/ | python -m json.tool
# you should see: the same models[] payload.
```

If `models[]` is missing: the probe is not running (Step a) or the energy JSON is
stale (>300s, `OLLAMA_ENERGY_MAX_AGE_S`) → it is intentionally surfaced as
`UNAVAILABLE`, never a stale/fake number.

---

## Step (d) — point the Space at the LiteLLM gateway

Expose LiteLLM publicly as `gateway.a-11-oy.com` via cloudflared (see
`box-scripts/cloudflared_ingress.example.yml` — the real `~/.cloudflared/config.yml`
is on-box, not committed). Then set the **Space secrets**:

| Space secret | Value | Effect |
|---|---|---|
| `SZL_LOCAL_LLM_URL` | `https://gateway.a-11-oy.com` | Points the sovereign-local path at the gateway (single endpoint). |
| `A11OY_SOVEREIGN_GATEWAY_URL` | `https://gateway.a-11-oy.com` | *Preferred.* Takes precedence over `SZL_LOCAL_LLM_URL`; the brain/anatomy use the unified LiteLLM endpoint. **Unset ⇒ falls back to `SZL_LOCAL_LLM_URL` (unchanged).** |
| `A11OY_SOVEREIGN_GATEWAY_KEY` | your `LITELLM_MASTER_KEY` | Bearer sent to the gateway. Secret is never logged/returned. (Fallback name: `SZL_LOCAL_LLM_KEY`.) |
| `SZL_LOCAL_LLM_MODEL` | `sovereign-llm` | The model name LiteLLM load-balances across both nodes. |

> Only **one** of `A11OY_SOVEREIGN_GATEWAY_URL` / `SZL_LOCAL_LLM_URL` is required.
> Set the gateway one to prefer the unified endpoint; both unset ⇒ honest stub.
> If Cloudflare Access is in front, also set the Space's `CF-Access-Client-Id` /
> `CF-Access-Client-Secret` (service token) — layered auth (bearer **and** Access).

---

## Step (e) — verify the Space wired to the mesh

```powershell
# 1. Registry wired_count should increment (sovereign_local now wired).
curl.exe -s "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/registry?probe=1" | python -m json.tool
# you should see: wired_count >= 1, "sovereign_local" in wired_model_ids, and its
#   badge {wired:true, base_url: the gateway}. local_live:true ONLY if the node
#   answered THIS request.

# 2. Sovereign health: live + served models THIS request.
curl.exe -s "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/sovereign/health" | python -m json.tool
# you should see: env_present:true, live:true, served_models includes sovereign-llm.

# 3. Route a real prompt to the mesh.
curl.exe -s -X POST "https://szlholdings-a11oy.hf.space/api/a11oy/v1/llm/route" `
  -H "Content-Type: application/json" `
  -d '{"prompt":"one sentence: why sovereign inference matters","task_hint":"sovereign"}'
# you should see: routed_via "sovereign_local (...)", a REAL response, and a
#   lambda_receipt (Λ = Conjecture 1, advisory). If the node is down you get an
#   HONEST STUB — the tier selection + Λ + receipt are still real.
```

`/brain/ask` (Wave 1/2) then routes its grounded prompt to `sovereign-llm` through the
same gateway when `A11OY_SOVEREIGN_GATEWAY_URL` (or `SZL_LOCAL_LLM_URL`) is set;
otherwise it honestly returns the retrieved subgraph with "no local model wired".

---

## Security (Doctrine v11 — non-negotiable)

1. **Ollama is NEVER public.** `:11434` is served over the tailnet only. It is not in
   any cloudflared ingress rule. Ollama has no built-in auth — the network IS its auth.
2. **Layered auth on the ONE public endpoint** (`gateway.a-11-oy.com`):
   - **LiteLLM bearer** (`master_key`) required on every request, **and**
   - **Cloudflare Access service token** in front of the tunnel hostname, **and**
   - **Tailnet ACL** (`box-scripts/tailscale_acl.json`, deny-by-default): only
     `tag:llm-gateway` may reach `tag:llm-gpu:11434`. A leaked bearer alone, or a
     leaked Access token alone, is insufficient.
3. **Never use Tailscale Funnel** for Ollama (no funnel grant exists in the ACL).
4. **Pin image tags** on GPU-facing containers; do not auto-update them unattended.
5. **Never commit a key.** `LITELLM_MASTER_KEY`, tunnel tokens, and the gateway bearer
   live only in the shell/`.env`/Space secrets — never in the tree.

## Self-healing / durability

| Layer | Mechanism |
|---|---|
| Ollama (native Win) | `laptop_persist.ps1` / `omen_boot_persist.ps1` — AtStartup task, `RestartCount 999`, `-AllowStartIfOnBatteries`. |
| #789 probe + exporter | Same persist scripts (AtStartup, auto-restart). |
| Tailscale (Win) | "Run unattended" mode; Startup Type = Automatic. |
| cloudflared / litellm / prometheus / grafana / dcgm-exporter | `restart: unless-stopped` + healthchecks (docker-compose). |
| LiteLLM ↔ node failure | `cooldown_time: 30`, `num_retries: 2`, least-busy routing auto-skips a down node. |

## Native-Windows fallback (the honest default)

WSL2 GPU-in-Docker is fragile (driver-version sensitivity, "restart Docker Desktop
fully" gotchas, silent CPU fallback). So the **model-serving path stays native**:
run Ollama + the #789 probe natively (Steps a, c), and containerize only the
stateless sidecars (LiteLLM / Prometheus / Grafana / cloudflared / dcgm-exporter).
If `dcgm-exporter` cannot acquire the GPU in its container, drop it and rely on the
native NVML probe for MEASURED joules — the mesh and the meter both still work.

## Troubleshooting

- **`gpu2`/tunnel 403** → set `OLLAMA_ORIGINS=*` and `OLLAMA_HOST=0.0.0.0:11434` at
  machine level (Step a), then restart Ollama.
- **LiteLLM 401 from the Space** → the Space's `A11OY_SOVEREIGN_GATEWAY_KEY` (bearer)
  must equal `LITELLM_MASTER_KEY`; if Access is on, also send the CF service token.
- **`wired_count` did not increment** → `SZL_LOCAL_LLM_URL` / `A11OY_SOVEREIGN_GATEWAY_URL`
  not set as a Space secret, or the gateway is unreachable (honest stub — not a bug).
- **`models[]` missing on meter2** → the #789 probe is not looping, or the reading is
  stale/`UNAVAILABLE` (NVML/power.draw not readable). Honest empty-state, never faked.
</content>
