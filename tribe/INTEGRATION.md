# Tribe → a11oy Unification

This directory ports the **AlloyScape "tribe"** — a Node.js multi-agent system — into the
a11oy orchestrator, taking **only what helps a11oy innovate and evolve**. It is staged for
review and is **not wired into `main` and not deployed**.

## What the tribe contributes to a11oy

a11oy already has a Python orchestration core (`a11oy_agent_loop.py`,
`a11oy_active_flux_router.py`, `a11oy_code_engine.py`). The tribe adds four capabilities
a11oy does not have natively:

1. **Persona / "soul" layer** (`tribe-think/souls/*.system.md`) — 21 first-person agent
   personas (engineers, operators, analysts, researchers). Language-agnostic markdown that
   can drive any orchestrator, including a11oy's router.
2. **Shared tool-calling brain loop** (`tribe-think/think-agent.mjs` + `think-server.mjs`)
   — a compact, model-agnostic agent loop (Kimi/Groq/OpenAI fallback) with a shared,
   pluggable tool registry (`tribe-think/tools/`).
3. **Always-on daemon + autonomy loop** (`soul-daemon.mjs`, `tribe-loop.mjs`) — an
   idle-cheap "always listening" pattern (LLM only fires on real inbound work) and an
   autonomy-level loop, both directly relevant to a11oy's flux router evolving toward
   self-driving behaviour.
4. **Collaboration substrate** (`tribe-chat-api.mjs` lounge + `tribe-bus/server.mjs`) —
   a message bus + multi-agent "lounge" so agents can address one another.

## Suggested wiring into a11oy (not yet done — standing by)

- Treat `tribe/tribe-think/souls/*.system.md` as a persona catalogue for
  `a11oy_active_flux_router.py` (route a request → soul → brain loop).
- Expose the tool registry (`tribe/tribe-think/tools/`) to `a11oy_agent_loop.py` via a thin
  Node sidecar (`think-server.mjs` already serves this over HTTP), or reimplement the loop
  in Python using the souls + tool contracts here as the spec.
- Adopt `soul-daemon.mjs`'s idle-free pattern as the model for a11oy always-on organs.

## What was intentionally EXCLUDED (not innovation-relevant / operational / private)

- All operational data: chat logs, memory `*.jsonl` (incl. a 514 MB TRIBAL-CHAT.jsonl),
  `ORDERS*.json`, `pending-for-roza.json`, session/state JSON.
- `*.bak*`, `node_modules`, `*.age`, PDFs, raw chat transcripts.
- Runtime secrets (this tree loads them from the host `.env` at runtime; none are embedded).

## Runtime notes

- Node.js modules; `tribe-think/env-loader.mjs` expects host `.env` keys at run time.
- This is a **capability import for evaluation**, not an active service. Nothing here starts
  on its own and no HF Space rebuild is triggered by this branch.
