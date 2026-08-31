# Laptop-only local model wiring runbook (no tower)

Docs-only. This file adds no code and changes no runtime behaviour.

**Purpose.** Serve a model from the laptop alone, expose it over an HTTPS hostname with
Cloudflare Tunnel, put an auth check in front of it, and point the a11oy Space at it — so the
BRAIN / knowledge surfaces call a real local endpoint instead of reporting `UNAVAILABLE`.
OpenRouter is the cloud fallback and the distillation teacher.

**Scope note.** This wires the **BRAIN / knowledge / reasoning / receipt** models only. It is
**not** for the counter-UAS stack (targeting, detection, fusion, effector) and must not be used
to advance it. Nothing here touches branch protection, training pipelines, or CI gates.

---

## HONESTY BOX — read before you start

- Never write `MEASURED`, `LIVE`, or `wired` into a surface, a report, or a deck because the
  wiring is *planned*. A label is earned by a live response to *that* request.
- A sleeping, closed, or offline laptop is `UNAVAILABLE`. It is **not** "degraded but healthy",
  and it is **not** a cached number replayed as fresh. `UNAVAILABLE` is the correct, honest
  answer and the estate is designed to say it.
- Energy and fleet surfaces flip from `UNAVAILABLE` to `MEASURED` only when the tunnel is up
  **and** the Space variables point at it **and** the node answers. Any one of those missing
  means the honest label stays `UNAVAILABLE`.
- Model prose grounded on a real subgraph is `MODELED`, not `MEASURED`. Only physically read
  quantities (token counts from the server, joules from a meter) are `MEASURED`.
- An agent **cannot** set Hugging Face Space Variables or Secrets. Step 4 is yours to run.

---

## Step 0 — What you need on the laptop

- `ollama` (for pulled model tags) **or** `llama.cpp`'s `llama-server` (for a local GGUF).
- `cloudflared`.
- For the stable hostname path: control of the `a-11-oy.com` zone in Cloudflare.
- Optional: an OpenRouter API key for the cloud fallback / teacher role.

---

## Step 1 — Serve the model locally, bound to loopback

Pick **one** of the two servers.

**Option A — Ollama (pulled tags).**

```bash
ollama serve
# in a second shell, make sure the tag you intend to serve is present:
ollama pull qwen2.5:3b
ollama list
```

`ollama serve` listens on `http://127.0.0.1:11434` and exposes both its native API
(`/api/generate`, `/api/embed`) and an OpenAI-compatible API (`/v1/chat/completions`,
`/v1/models`). The a11oy call sites use both shapes, so keep both reachable.

**Option B — llama.cpp (serve our own GGUF, e.g. `SZL-Khipu-1.5B-GGUF`).**

```bash
llama-server -m /path/to/model.gguf --port 8080
```

`llama-server` exposes an OpenAI-compatible surface (`/v1/chat/completions`, `/v1/embeddings`,
`/v1/models`). Use this path when you want to serve a GGUF we trained ourselves rather than a
pulled Ollama tag. If you choose Option B, substitute `8080` for `11434` everywhere below.

**Do not widen the bind.**

```bash
# DO NOT DO THIS on a laptop you carry onto untrusted networks:
# export OLLAMA_HOST=0.0.0.0
```

Leave the server on `127.0.0.1`. The tunnel in Step 2 reaches it from the same machine over
loopback, so there is no reason to expose it to the LAN. Exposure is granted deliberately in
Step 2 and authenticated in Step 3, not by binding to every interface.

Sanity check before moving on:

```bash
curl -s http://127.0.0.1:11434/v1/models
```

---

## Step 2 — Expose it with Cloudflare Tunnel

`cloudflared` makes an outbound-only connection, so no port forwarding and no inbound firewall
hole. There are two honest options; they are not equivalent.

### Option 2a — Quick tunnel (random URL, for a first test only)

```bash
cloudflared tunnel --url http://localhost:11434 --http-host-header="localhost:11434"
```

This prints a random `https://<something>.trycloudflare.com` URL. The `--http-host-header` flag
is required because Ollama rejects requests carrying an unexpected `Host` header.

Honest limits: the hostname changes on every restart, there is no auth, and it is unsuitable as
the value of a Space variable you expect to stay valid. Use it to prove the path works, then
move to 2b.

### Option 2b — Named tunnel mapped to `gpu2.a-11-oy.com` (the stable path)

```bash
cloudflared tunnel login                  # browser: pick the a-11-oy.com zone
cloudflared tunnel create laptop-gpu2     # prints a TUNNEL-UUID and writes a credentials JSON
cloudflared tunnel route dns laptop-gpu2 gpu2.a-11-oy.com
```

Write `~/.cloudflared/config.yml`:

```yaml
tunnel: 00000000-0000-0000-0000-000000000000        # the UUID printed by `tunnel create`
credentials-file: /home/YOURUSER/.cloudflared/00000000-0000-0000-0000-000000000000.json

ingress:
  - hostname: gpu2.a-11-oy.com
    service: http://localhost:11434
    originRequest:
      httpHostHeader: "localhost:11434"
  - service: http_status:404                        # required catch-all, must be last
```

Run it:

```bash
cloudflared tunnel run laptop-gpu2
```

Notes that matter:

- Replace the UUID and the credentials path with the real values from `tunnel create`. Both must
  match or `cloudflared` refuses to start.
- The `http_status:404` catch-all rule is mandatory and must be the final ingress entry.
- `originRequest.httpHostHeader` is the config-file equivalent of the `--http-host-header` flag
  in Option 2a. Without it, Ollama answers with a host-check error rather than model output.
- For Option B (llama.cpp) the service becomes `http://localhost:8080` and the host header is
  `localhost:8080`.
- Keep the process running. When you close the lid, the hostname stops answering and the estate
  correctly reports `UNAVAILABLE`.

---

## Step 3 — Put auth in front of the endpoint

A named tunnel on a public hostname is reachable by anyone who learns the name. Add one of these
before you put the URL into a Space variable.

**Option 3a — Cloudflare Access (no code).** Add an Access application covering
`gpu2.a-11-oy.com` and use a **service token**. Callers then send
`CF-Access-Client-Id` and `CF-Access-Client-Secret`; everything else is rejected at Cloudflare's
edge before it reaches the laptop.

**Option 3b — A Worker that checks a shared secret header and proxies.** Route the public
hostname at the Worker and keep the tunnel on an internal hostname
(e.g. `gpu2-origin.a-11-oy.com`), so the tunnel is never called directly.

```js
// Worker: require a secret header, then proxy to the tunnel origin.
// Bind LOCAL_LLM_TOKEN and ORIGIN_HOST as Worker secrets/vars — never inline them.
export default {
  async fetch(request, env) {
    const presented = request.headers.get("x-szl-local-token") || "";
    const expected = env.LOCAL_LLM_TOKEN || "";
    // Constant-time-ish comparison; reject on any length or byte mismatch.
    if (!expected || presented.length !== expected.length) {
      return new Response("forbidden", { status: 403 });
    }
    let diff = 0;
    for (let i = 0; i < expected.length; i++) {
      diff |= presented.charCodeAt(i) ^ expected.charCodeAt(i);
    }
    if (diff !== 0) return new Response("forbidden", { status: 403 });

    const url = new URL(request.url);
    url.hostname = env.ORIGIN_HOST;           // e.g. "gpu2-origin.a-11-oy.com"
    const upstream = new Request(url, request);
    upstream.headers.delete("x-szl-local-token");   // do not forward the secret
    return fetch(upstream);
  },
};
```

Deploy with `wrangler deploy`, set the secret with
`wrangler secret put LOCAL_LLM_TOKEN`, and add a Worker route for `gpu2.a-11-oy.com/*`.

Honest limitation: a single shared header is a coarse control. It stops opportunistic traffic; it
is not per-caller identity, it has no revocation beyond rotating the value, and it gives no audit
trail per consumer. Cloudflare Access (3a) is the better choice when you need those.

Whichever option you pick, the a11oy caller must send the header. If the current call sites do
not attach a custom header, use Option 3a with Access, or leave the endpoint behind a hostname you
only enable while testing — do **not** publish an unauthenticated model endpoint and call it done.

---

## Step 4 — Wire the a11oy Space (YOUR steps — the agent cannot do these)

Set these in the Hugging Face Space **Settings → Variables and secrets**.

**Variables (non-secret):**

| Variable | Value | Why |
| --- | --- | --- |
| `SZL_LOCAL_LLM_URL` | `https://gpu2.a-11-oy.com` | Primary own-metal endpoint. Give the **bare origin with no trailing path**: different call sites append `/api/generate`, `/api/embed`, or `/v1/chat/completions` themselves. |
| `SZL_LOCAL_LLM_MODEL` | the served model name | Required alongside the URL. Without a model name the sovereign answer path returns `UNAVAILABLE` by design. |
| `A11OY_JPT_GPU_URLS` | `https://gpu2.a-11-oy.com` | Joules-per-token harness roster: which node to generate on. Comma-separated, positional. |
| `A11OY_JPT_MODELS` | the served model name | Positional match to `A11OY_JPT_GPU_URLS`. |
| `A11OY_JOULE_METER_URLS` | your meter URL, if one runs | **The positional roster form is only used when this is set.** With no meter URL the roster falls back to its defaults and your GPU/model overrides are ignored. |

Model name = exactly what the server reports. For Ollama it is the tag (`ollama list`, e.g.
`qwen2.5:3b`). For `llama-server` it is the id in `GET /v1/models`.

**Secret:**

| Secret | Value | Why |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | your OpenRouter key | Cloud fallback and distillation teacher. Set it as a **Secret**, never a Variable. |

**What actually flips the labels.** `MEASURED` / `LIVE` requires *all* of: the local server
running (Step 1), `cloudflared` running and the hostname resolving (Step 2), the variables above
pointing at it (Step 4), and the node answering the live probe. Joule figures additionally
require a real meter — a GPU URL alone gives token counts, not joules. Until every piece holds,
the estate reports `UNAVAILABLE`, which is the correct output, not a bug to paper over.

Restart the Space after changing variables so the new environment is picked up.

---

## Step 5 — OpenRouter as fallback and as teacher

OpenRouter is OpenAI-compatible, so it needs no new client shape.

- **Base URL:** `https://openrouter.ai/api/v1`
- **Chat endpoint:** `https://openrouter.ai/api/v1/chat/completions`
- **Model catalogue:** `https://openrouter.ai/api/v1/models`
- **Auth:** `Authorization: Bearer $OPENROUTER_API_KEY`

**As fallback.** Own metal is tried first. When `gpu2.a-11-oy.com` does not answer, an
OpenRouter-backed route can serve the request — but it must be labelled as the remote provider it
is, never as the sovereign local model. A fallback answer is not evidence that the laptop node was
up.

```bash
curl -s https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openrouter/auto","messages":[{"role":"user","content":"ping"}]}'
```

**As distillation teacher — BRAIN training only.** Use a frontier model through OpenRouter to
generate and critique candidate training data for the in-scope BRAIN lanes (knowledge,
governance, reasoning, receipt/citation behaviour), then train the student locally with QLoRA. Two
rules:

1. Every generated row is validated before it enters a training set. A smaller validated set beats
   a larger noisy one; unvalidated teacher output is not a dataset.
2. Teacher use is confined to BRAIN / knowledge models. It is **out of scope** for the counter-UAS
   stack, and no part of this runbook authorizes training there.

---

## Step 6 — Verification

Run these in order. Stop at the first failure and fix that layer rather than moving on.

```bash
# 1) local server answers on loopback
curl -s http://127.0.0.1:11434/v1/models

# 2) tunnel hostname answers, and lists the model you intend to serve
curl -s https://gpu2.a-11-oy.com/v1/models

# 2b) if you used the Worker/header auth of Step 3b
curl -s https://gpu2.a-11-oy.com/v1/models -H "x-szl-local-token: $LOCAL_LLM_TOKEN"

# 3) auth actually rejects an unauthenticated call (expect 403, not a model list)
curl -s -o /dev/null -w '%{http_code}\n' https://gpu2.a-11-oy.com/v1/models

# 4) a real generation round-trip through the tunnel
curl -s https://gpu2.a-11-oy.com/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:3b","prompt":"say ok","stream":false}'
```

Then check the estate's own view:

```bash
curl -s https://<your-space-host>/api/a11oy/v1/llm/sovereign/health
```

That endpoint reports per-node reachability from the Space's perspective. It is the authority on
whether the node is wired — not your local `curl`, and not your intent. If it says
`UNAVAILABLE`, the node is not wired, and no surface, report, or slide may claim otherwise.

Interpretation table:

| Observation | Honest reading |
| --- | --- |
| Step 1 passes, Step 2 fails | Tunnel or DNS problem. Node is `UNAVAILABLE`. |
| Step 2 returns a host-check error | Missing `httpHostHeader` / `--http-host-header`. |
| Step 3 returns a model list without a token | Endpoint is open. Fix auth before wiring it. |
| Sovereign health says `UNAVAILABLE` while local `curl` works | Space variables not set, or Space not restarted. |
| Laptop asleep | `UNAVAILABLE`. Not degraded-healthy, not cached-as-fresh. |

---

## Teardown

```bash
# stop the tunnel, then the model server
pkill -f "cloudflared tunnel run"
pkill -f "ollama serve"    # or: pkill -f llama-server
```

After teardown, clear or stop relying on `SZL_LOCAL_LLM_URL` / `A11OY_JPT_GPU_URLS` if you want
the surfaces to state plainly that no local node is configured, rather than that a configured node
is unreachable. Both readings are honest; pick the one that matches reality.

---

## Sources

- Ollama FAQ — host binding, `OLLAMA_HOST`, and the documented `cloudflared` flags:
  https://docs.ollama.com/faq
- Ollama OpenAI compatibility: https://docs.ollama.com/openai
- llama.cpp server (OpenAI-compatible endpoints for a GGUF):
  https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Cloudflare Tunnel — quick tunnels: https://developers.cloudflare.com/pages/how-to/preview-with-cloudflare-tunnel/
- Cloudflare Tunnel — local `config.yml` and ingress rules:
  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/configuration-file/
- Cloudflare Tunnel — `originRequest` (incl. `httpHostHeader`):
  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/cloudflared-parameters/origin-parameters/
- Cloudflare Access service tokens:
  https://developers.cloudflare.com/cloudflare-one/identity/service-tokens/
- Cloudflare Workers secrets and `wrangler secret`:
  https://developers.cloudflare.com/workers/configuration/secrets/
- OpenRouter API reference (OpenAI-compatible base URL):
  https://openrouter.ai/docs/api-reference/overview
- In-repo consumers of these variables: `szl_llm_registry.py`, `szl_governed_infer.py`,
  `szl_brain_api.py`, `szl_kc_jpt.py`, `SOVEREIGN_REMOTE.md`.
