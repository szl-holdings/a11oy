<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
-->

# SOVEREIGN_REMOTE.md — Tailscale-aware sovereign remote access + multi-node routing

**Wave N, Dev 3.** How to expose an Ollama model on your own metal (Tower / OMEN
RTX 4060 Ti) over your Tailscale tailnet and wire a11oy to route to it
**own-metal-first**, honestly, across **multiple** sovereign nodes.

Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, never a theorem) · honest labels
only (`LIVE` / `UNAVAILABLE`). a11oy **probes each node with a short timeout** and
reports a per-node reachability matrix; it routes to the **first reachable
own-metal node** and falls through to free/paid **only when NO sovereign node is
reachable**. It **NEVER fabricates** reachability, a model list, or a response.

---

## 0. The mesh model

| Env var | Role | Example |
| --- | --- | --- |
| `SZL_LOCAL_LLM_URL` | **PRIMARY** own-metal node (tried first; defaults to `http://localhost:11434/v1` when unset) | `http://tower.tailnet:11434/v1` |
| `SZL_SOVEREIGN_NODES` | Comma list of **additional** tailnet nodes | `http://omen.tailnet:11434/v1,http://hetzner.tailnet:11434/v1` |
| `SZL_LOCAL_LLM_MODEL` | Tag the node serves (optional) | `llama3.1:8b` |
| `SZL_SOVEREIGN_PROBE_TIMEOUT` | Per-node probe timeout, seconds (default `2.5`) | `2.5` |

**Own-metal-first** = the PRIMARY node is probed before any `SZL_SOVEREIGN_NODES`
entry, and entries are probed in the order you list them. The first node that
answers a real 2xx JSON response **this request** is selected.

---

## 1. Tower side — expose the model on the tailnet

The Tower/OMEN box (RTX 4060 Ti) runs Ollama. By default Ollama binds
`127.0.0.1:11434` and is **not** reachable from other machines. Bind it to all
interfaces so Tailscale can reach it, per the
[Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.md):

### 1a. Set `OLLAMA_HOST=0.0.0.0:11434` (Linux / systemd)

```bash
# 1) Edit the Ollama systemd unit
sudo systemctl edit ollama.service

# 2) Add under [Service]:
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"

# 3) Reload + restart
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

macOS / Windows: quit Ollama, set the environment variable `OLLAMA_HOST` to
`0.0.0.0:11434`, and relaunch (see the same FAQ). Foreground alternative on any
OS: `OLLAMA_HOST=0.0.0.0:11434 ollama serve`.

### 1b. Pull the model you want to serve

```bash
ollama pull llama3.1:8b        # matches SZL_LOCAL_LLM_MODEL default
ollama list                    # confirm the tag is present
```

### 1c. Join the tailnet (Tailscale)

Install Tailscale and bring the box onto your tailnet, per the
[Tailscale quickstart](https://tailscale.com/kb/1017/install):

```bash
curl -fsSL https://tailscale.com/install.sh | sh    # Linux install
sudo tailscale up                                    # authenticate this node
tailscale ip -4                                      # this node's 100.x.y.z tailnet IP
tailscale status                                     # see peers + MagicDNS names
```

With [MagicDNS](https://tailscale.com/kb/1081/magicdns) enabled, the box is
reachable as `http://<hostname>.<tailnet>.ts.net:11434` (or use the `100.x.y.z`
tailnet IP directly). Ollama serves the OpenAI-compatible API under `/v1`, so the
base URL to hand a11oy is e.g. `http://tower.tailnet:11434/v1`.

> **Security note:** `0.0.0.0` binds all interfaces. Keep the box off the public
> internet — Tailscale gives you a private, WireGuard-encrypted tailnet so only
> your own devices can reach port `11434`. Do **not** port-forward `11434` on your
> router. Prefer restricting reachability with
> [Tailscale ACLs](https://tailscale.com/kb/1018/acls).

### 1d. Verify from another tailnet device

```bash
# ollama-native liveness (a11oy probes this first)
curl http://tower.tailnet:11434/api/tags

# OpenAI-compatible liveness (a11oy probes this second)
curl http://tower.tailnet:11434/v1/models
```

A real 2xx JSON response here is exactly what a11oy needs to mark the node
`reachable: true`. If this fails, a11oy will honestly report the node
`reachable: false` — it will **not** fabricate liveness.

---

## 2. Laptop side — env to set so a11oy routes own-metal-first

Set these on the machine (or HF Space) running a11oy's `serve.py`:

```bash
# PRIMARY own-metal node (tried first) — use the tailnet name or 100.x IP
export SZL_LOCAL_LLM_URL="http://tower.tailnet:11434/v1"

# Additional tailnet nodes, comma-separated, probed in this order after primary
export SZL_SOVEREIGN_NODES="http://omen.tailnet:11434/v1,http://hetzner.tailnet:11434/v1"

# Optional: the exact model tag the node serves (default llama3.1:8b)
export SZL_LOCAL_LLM_MODEL="llama3.1:8b"

# Optional: shorten/lengthen the honest per-node probe timeout (default 2.5s)
export SZL_SOVEREIGN_PROBE_TIMEOUT="2.5"
```

Then confirm the mesh from a11oy:

```bash
# Per-node reachability matrix (own-metal-first)
curl http://localhost:7860/api/a11oy/v1/llm/sovereign/health | jq

# Router key/liveness posture (pass ?probe=1 to ping the mesh)
curl "http://localhost:7860/api/a11oy/v1/llm/router/status?probe=1" | jq .sovereign_mesh
```

---

## 3. How routing behaves (honest)

- **≥1 sovereign node reachable** → a11oy routes to the **first reachable node**
  (own-metal-first) and returns a **REAL** local generation.
  `sovereign_status: "LIVE"`.
- **A node is reachable at probe but fails to generate** → honest `HONEST STUB`
  (tier selection + Λ-receipt still real).
- **NO sovereign node reachable** → `sovereign_status: "UNAVAILABLE"`; the router
  **falls through to free/paid** and says so. No fabrication.

### `/api/a11oy/v1/llm/sovereign/health` — reachability-matrix shape

```jsonc
{
  "sovereign_status": "LIVE" | "UNAVAILABLE",   // honest label
  "own_metal_first": true,
  "fallthrough_to_cloud": false,                // true iff no node reachable
  "env_vars": { "primary": "SZL_LOCAL_LLM_URL", "nodes": "SZL_SOVEREIGN_NODES" },
  "node_count": 2,
  "reachable_count": 1,
  "any_reachable": true,
  "selected_node": { "base_url": "http://tower.tailnet:11434/v1",
                     "role": "primary", "index": 0,
                     "api_style": "openai /v1", "served_models": ["llama3.1:8b"] },
  "mesh": {
    "env": { "primary_env": "SZL_LOCAL_LLM_URL", "nodes_env": "SZL_SOVEREIGN_NODES" },
    "node_count": 2, "reachable_count": 1, "any_reachable": true,
    "primary_base_url": "http://tower.tailnet:11434/v1",
    "selected": { "base_url": "...", "role": "primary", "index": 0 },
    "nodes": [
      { "index": 0, "base_url": "http://tower.tailnet:11434/v1", "role": "primary",
        "reachable": true,  "api_style": "openai /v1",
        "served_models": ["llama3.1:8b"], "probed": [ /* per-URL probe log */ ],
        "error": null, "note": "node live ..." },
      { "index": 1, "base_url": "http://hetzner.tailnet:11434/v1", "role": "mesh",
        "reachable": false, "api_style": null, "served_models": [],
        "probed": [ /* per-URL probe log */ ],
        "error": "node unreachable: <short reason>", "note": "... honest stub ..." }
    ],
    "note": "1/2 sovereign node(s) reachable THIS request; own-metal-first selected ..."
  },
  "doctrine": "v11",
  "conjecture_note": "Λ = Conjecture 1 — advisory, never a theorem."
}
```

When nothing answers (the default localhost primary is unreachable, or every
configured node is down), every `reachable` is `false`, `sovereign_status` is
`"UNAVAILABLE"`, `selected_node` is `null`, and `fallthrough_to_cloud` is `true`
— the router then routes to free/paid. Nothing is ever fabricated.

---

## Sources (real)

- Ollama FAQ — exposing the server on the network (`OLLAMA_HOST=0.0.0.0:11434`),
  systemd steps, and `OLLAMA_ORIGINS`:
  https://github.com/ollama/ollama/blob/main/docs/faq.md
- Ollama OpenAI-compatible API (`/v1/models`, `/v1/chat/completions`):
  https://github.com/ollama/ollama/blob/main/docs/openai.md
- Tailscale install / quickstart: https://tailscale.com/kb/1017/install
- Tailscale MagicDNS: https://tailscale.com/kb/1081/magicdns
- Tailscale ACLs: https://tailscale.com/kb/1018/acls
