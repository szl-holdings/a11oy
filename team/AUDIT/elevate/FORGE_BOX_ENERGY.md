<!-- VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — replit-sync/FORGE_BOX_ENERGY_v2.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
# FORGE_BOX_ENERGY.md — Sovereign GPU box order (Lane C: Sovereign Inference + Energy)

> **FOUNDER-APPROVAL-GATED.** The sovereign GPU box (a-11-oy.com; Hetzner, RTX 5000,
> `betterwithage`; vLLM/Ollama behind Tailscale) is dispatched ONLY via the Forge.
> Dev C does **NOT** ssh into or modify the box. This file is the exact, copy-pasteable
> set of commands/config the **CTO compiles into the Forge order**. Nothing here runs
> until the founder approves and the Forge applies it.
>
> **Honesty contract (doctrine v11):** the app side (`szl_energy_sovereign.py`) reads
> these metrics **only via the live `gpu_reachable` probe** and labels everything
> `MEASURED` (real fresh on-box exporter sample) or `ROADMAP` (not emitting yet). It
> **never fabricates** a sovereign/energy number. Applying this order is what flips the
> panels from `ROADMAP → MEASURED`.

---

## 0. Prerequisites (already-shipped sovereign flip — context only)

The box already knows how to flip `sovereign:true` by setting these **a11oy Space
secrets** (per `LAPTOP_HANDOFF_sovereign_flip.md`). This order ADDS the energy/metrics
wiring on top of that flip:

```
A11OY_MODEL_BASE_URL   = http://127.0.0.1:8000/v1     # vLLM OpenAI-compatible (or :11434/v1 Ollama)
A11OY_GPU_LABEL        = RTX-5000-betterwithage
A11OY_LOCAL_CODE_MODEL = qwen2.5-coder:7b
A11OY_LOCAL_GENERAL_MODEL = llama3.1:8b
A11OY_GPU_TOKEN        = <vllm-api-key>               # if vLLM started with --api-key
```

> The app only claims `sovereign:true` when `A11OY_MODEL_BASE_URL` is a non-router
> endpoint **and** its `/models` actually answers (`_local_endpoint_reachable`). That is
> the single honesty gate; the energy panels key off the same probe.

---

## 1. (#1 Tier-1) J/token instrumentation — `nvidia-smi power.draw → vLLM /metrics`

The app computes `J/token = ΣJ / Σgenerated_tokens` from the on-box exporter
(`E_token = P_GPU · T_forward / N_tokens` — Watt-Counts arXiv:2604.09048,
Energy-per-Token arXiv:2603.20224, Where-Do-Joules-Go arXiv:2601.22076). The box must
expose a **cumulative GPU energy (joules)** counter and an instantaneous **power.draw**
gauge that the app scrapes alongside vLLM's token counters.

### 1a. Energy exporter sidecar (integrates `nvidia-smi power.draw` into joules)

Create `/opt/a11oy/gpu_energy_exporter.py` (pure stdlib; integrates power → joules):

```python
#!/usr/bin/env python3
# /opt/a11oy/gpu_energy_exporter.py — exposes cumulative GPU joules + watts as Prometheus
# text on :9402/metrics. Integrates nvidia-smi power.draw (W) over wall-clock to joules.
import http.server, subprocess, threading, time

_state = {"joules_total": 0.0, "power_w": 0.0, "last": time.time()}

def _poll():
    while True:
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                timeout=4).decode().strip().splitlines()
            w = sum(float(x) for x in out if x.strip())  # sum across GPUs
            now = time.time()
            dt = max(0.0, now - _state["last"])
            _state["joules_total"] += w * dt      # P·Δt = Joules
            _state["power_w"] = w
            _state["last"] = now
        except Exception:
            pass
        time.sleep(1.0)

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            "# HELP a11oy_gpu_energy_joules_total Cumulative GPU energy (J), power.draw integrated.\n"
            "# TYPE a11oy_gpu_energy_joules_total counter\n"
            f"a11oy_gpu_energy_joules_total {_state['joules_total']:.3f}\n"
            "# HELP a11oy_gpu_power_watts Instantaneous GPU power draw (W).\n"
            "# TYPE a11oy_gpu_power_watts gauge\n"
            f"a11oy_gpu_power_watts {_state['power_w']:.3f}\n"
        ).encode()
        self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    threading.Thread(target=_poll, daemon=True).start()
    http.server.HTTPServer(("0.0.0.0", 9402), H).serve_forever()
```

Run it as a service:

```bash
sudo tee /etc/systemd/system/a11oy-gpu-energy.service >/dev/null <<'UNIT'
[Unit]
Description=a11oy GPU energy exporter (power.draw -> joules)
After=network.target
[Service]
ExecStart=/usr/bin/python3 /opt/a11oy/gpu_energy_exporter.py
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable --now a11oy-gpu-energy.service
curl -s http://127.0.0.1:9402/metrics   # verify: a11oy_gpu_energy_joules_total + a11oy_gpu_power_watts
```

### 1b. Point the app at the exporter (so `/metrics` carries energy + token counters)

The app reads the **vLLM** `/metrics` for token counters and the **energy exporter** for
joules/watts. Wire both into one scrape surface — set the metrics URL the app probes and
ensure the energy lines are merged (vLLM is on :8000, the exporter on :9402). Set the
a11oy Space secret so the app scrapes the **combined** Prometheus surface:

```
A11OY_VLLM_METRICS_URL = http://127.0.0.1:9402/combined_metrics   # see 1c (merge), or :8000/metrics if you concatenate
```

> If you prefer a single endpoint, run a tiny merge proxy that concatenates
> `:8000/metrics` (vLLM tokens) + `:9402/metrics` (energy). The app's parser sums by
> metric name, so a concatenation of both Prometheus texts is sufficient.

### 1c. (optional) one-line merge proxy

```bash
# /opt/a11oy/metrics_merge.py — serves :9403/metrics = vLLM tokens + GPU energy concatenated.
python3 - <<'PY'
import http.server, urllib.request
def grab(u):
    try:
        return urllib.request.urlopen(u, timeout=2).read().decode()
    except Exception:
        return ""
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (grab("http://127.0.0.1:8000/metrics") + "\n" +
                grab("http://127.0.0.1:9402/metrics")).encode()
        self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
        self.wfile.write(body)
    def log_message(self,*a): pass
http.server.HTTPServer(("0.0.0.0",9403),H).serve_forever()
PY
# then set: A11OY_VLLM_METRICS_URL = http://127.0.0.1:9403/metrics
```

**Result when applied:** `/api/a11oy/v1/energy/jtoken` flips `ROADMAP → MEASURED`, and
**every signed turn receipt** gains a real `joules_consumed` + `carbon_g_co2eq`
(`energy_label:"MEASURED"`, `joules_honesty:"measured"`).

---

## 2. (#2 Tier-1) Speculative decoding — vLLM `--speculative-model`

Start vLLM with the draft model so it emits speculative-decode counters + throughput:

```bash
# Qwen2.5-Coder-1.5B drafts for the 7B/32B target. Emits tokens/s + accept-rate counters.
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --speculative-model Qwen/Qwen2.5-Coder-1.5B-Instruct \
  --num-speculative-tokens 4 \
  --port 8000 \
  --disable-log-requests \
  --api-key "$A11OY_GPU_TOKEN"
```

vLLM then exports (read by `/api/a11oy/v1/energy/throughput`):

- `vllm:avg_generation_throughput_toks_per_s` — tokens/s WITH spec decoding
- `vllm:spec_decode_num_accepted_tokens_total` / `vllm:spec_decode_num_draft_tokens_total`
  → empirical acceptance rate **α = accepted / drafted**

The app derives `tokens/s WITHOUT = with / S`, where the research speedup model is
**S = (k+1) / (k·(1−α)+1)**; e.g. k=4, α=0.8 → S ≈ 2.78×. With α MEASURED the panel
shows the real with-vs-without delta; until then α is ILLUSTRATIVE (α=0.8).

---

## 3. (#3) LMCache KV-cache offload — TTFT before/after

Enable prefix caching + LMCache KV offload so repeated prompt prefixes skip prefill:

```bash
pip install lmcache
# vLLM v1 prefix caching (GPU) — emits prefix-cache hit/query counters:
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --enable-prefix-caching \
  --kv-transfer-config '{"kv_connector":"LMCacheConnectorV1","kv_role":"kv_both"}' \
  --port 8000 --api-key "$A11OY_GPU_TOKEN"

# LMCache CPU/disk offload tier (extends KV cache beyond GPU HBM):
export LMCACHE_CHUNK_SIZE=256
export LMCACHE_LOCAL_CPU=True
export LMCACHE_MAX_LOCAL_CPU_SIZE=40        # GiB CPU KV pool
export LMCACHE_LOCAL_DISK="file:///var/lib/lmcache"
export LMCACHE_MAX_LOCAL_DISK_SIZE=200      # GiB disk KV pool
```

Exports read by `/api/a11oy/v1/energy/kvcache`:
`vllm:prefix_cache_hits_total`, `vllm:prefix_cache_queries_total`,
`vllm:time_to_first_token_seconds_sum` → TTFT before (cold) vs after (warm reuse).
Ref: github.com/LMCache/LMCache.

---

## 4. (#4) LiteLLM gateway — unified endpoint + budget + cloud fallback

Front Ollama + vLLM with a budget-enforcing OpenAI-compatible proxy that falls back to
the HF Router on GPU OOM / 5xx:

```bash
pip install 'litellm[proxy]'
cat > /opt/a11oy/litellm_config.yaml <<'YAML'
model_list:
  - model_name: local-coder
    litellm_params:
      model: openai/Qwen/Qwen2.5-Coder-7B-Instruct
      api_base: http://127.0.0.1:8000/v1
      api_key: os.environ/A11OY_GPU_TOKEN
  - model_name: local-general
    litellm_params:
      model: ollama/llama3.1:8b
      api_base: http://127.0.0.1:11434
  - model_name: cloud-fallback           # used on GPU OOM / 5xx
    litellm_params:
      model: huggingface/Qwen/Qwen2.5-Coder-32B-Instruct
      api_base: https://router.huggingface.co/v1
      api_key: os.environ/HF_TOKEN
litellm_settings:
  fallbacks: [{"local-coder": ["cloud-fallback"]}, {"local-general": ["cloud-fallback"]}]
  max_budget: 50                          # USD hard cap (budget enforcement)
  budget_duration: 30d
router_settings:
  routing_strategy: usage-based-routing-v2
  allowed_fails: 2
YAML
litellm --config /opt/a11oy/litellm_config.yaml --port 4000
```

Then set the a11oy Space secret so the app reports the gateway LIVE:

```
A11OY_LITELLM_BASE_URL  = http://127.0.0.1:4000
A11OY_LITELLM_BUDGET_USD = 50
```

`/api/a11oy/v1/energy/gateway` flips `ROADMAP → MEASURED` once the proxy answers
`/health`. Ref: github.com/BerriAI/litellm.

---

## 5. (#5) RouteLLM Thompson-sampling router — Beta posteriors per model

Route easy prompts → local 7B, hard → 32B/cloud, learning per-model Beta(α,β) posteriors
(α = accepted routes, β = failures); pick `argmax θ_k`, θ_k ~ Beta(α_k, β_k).

```bash
pip install routellm
# Calibrate the router thresholds on a labeled set (one-time), then serve:
python -m routellm.openai_server \
  --routers mf \
  --strong-model Qwen/Qwen2.5-Coder-32B-Instruct \
  --weak-model   Qwen/Qwen2.5-Coder-7B-Instruct \
  --config /opt/a11oy/routellm_config.yaml \
  --port 6060
```

The app already exposes the Thompson posteriors at `/api/a11oy/v1/energy/router`. To make
them MEASURED, have the gateway/router POST each route outcome back to the app process via
`szl_energy_sovereign.record_route_outcome(model_key, success)` (in-process) — or set the
router to log outcomes to a file the app tails. Until real traffic records outcomes the
posteriors stay at the Beta(1,1) prior (honest ROADMAP). Ref: github.com/lm-sys/routellm.

---

## 6. (#6) Carbon-Aware SDK batch scheduling — low-carbon windows

Defer non-urgent batch inference to the greenest grid window; log `carbon_g_co2eq` per job:

```bash
# Carbon-Aware SDK WebApi (Green Software Foundation) — returns marginal carbon forecast.
docker run -d --name carbon-aware -p 5073:80 \
  -e DataSources__EmissionsDataSource=WattTime \
  -e DataSources__Configurations__WattTime__Username="$WATTTIME_USER" \
  -e DataSources__Configurations__WattTime__Password="$WATTTIME_PASS" \
  ghcr.io/green-software-foundation/carbon-aware-sdk:latest

# Query the best window for a region before dispatching a batch job:
curl "http://127.0.0.1:5073/emissions/forecasts/current?location=DE&windowSize=30"
```

Then set the a11oy Space secret so the carbon panel + per-receipt carbon go LIVE:

```
A11OY_GRID_CARBON_G_PER_KWH = <current gCO2eq/kWh from the SDK forecast>   # or wire a refresher
```

`/api/a11oy/v1/energy/carbon` flips its intensity label `SAMPLE → LIVE`, and
`carbon_g_co2eq` in each receipt becomes a real figure (J/token × intensity). Ref:
github.com/Green-Software-Foundation/carbon-aware-sdk.

---

## 7. Verification checklist (run after the Forge applies this order)

```bash
# 1. Sovereign + metrics reachable from the app process:
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/code/healthz | python3 -m json.tool | grep -E 'sovereign|inference'
# expect: "sovereign": true, "inference": "self-hosted-gpu"

# 2. J/token MEASURED:
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/energy/jtoken | python3 -m json.tool
# expect: "label": "MEASURED", a real "joules_per_token", "joules_honesty": "measured"

# 3. Throughput / KV-cache / gateway / router / carbon panels:
for p in throughput kvcache gateway router carbon sovereign; do
  echo "== $p =="; curl -s "https://szlholdings-a11oy.hf.space/api/a11oy/v1/energy/$p" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("label") or d.get("summary"))'
done

# 4. A signed turn receipt carries a real joules figure:
#    drive one governed turn, then read the khipu energy.receipt — expect joules_consumed != null.
```

---

## Honesty invariants the box order MUST preserve (doctrine v11)

- `sovereign:true` ONLY with a live `_local_endpoint_reachable()` /models probe — never a bare env flag.
- `joules_honesty:"measured"` ONLY with a **fresh real** NVML/exporter sample (≤120 s) — `szl_joules_truth` decides, nothing else.
- No meter → no number: every absent metric stays `ROADMAP`/`None`, never fabricated.
- Open-weight models only; **never commit a key** (all keys are Space secrets / `os.environ`).
- Effectors stay SIMULATED; 0 visible codenames; SLSA reads L1 honest / L2 attested / L3 roadmap (never bare L3).

---

### Sources
- J/token energy: Watt-Counts — https://arxiv.org/abs/2604.09048 ; Energy-per-Token — https://arxiv.org/abs/2603.20224 ; Where-Do-Joules-Go — https://arxiv.org/abs/2601.22076
- Speculative decoding (vLLM): https://docs.vllm.ai/en/latest/features/spec_decode.html
- LMCache: https://github.com/LMCache/LMCache
- LiteLLM: https://github.com/BerriAI/litellm
- RouteLLM: https://github.com/lm-sys/routellm
- Carbon-Aware SDK: https://github.com/Green-Software-Foundation/carbon-aware-sdk
