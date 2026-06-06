# 12_agentic — Full Agentic AI Layer

**What this is:** Drop-in agentic workstation. Replit boots it once and three coding agents (Cursor, Claude Code, Replit Agent) are wired into a single MCP server that exposes a11oy — your doctrine-bound orchestrator — and every SZL formula as callable tools.

**Operator:** Lutar, Stephen P. — ORCID 0009-0001-0110-4173 — SZL Holdings
**Doctrine:** V6 (see `../02_doctrine/DOCTRINE_V6.md`)
**License:** Apache-2.0 (code), CC-BY-4.0 (docs)

## What's in here

| Dir | Contents | Why it matters |
|---|---|---|
| `a11oy-core/` | The orchestrator — tool router, doctrine gate, 9-axis Λ check, replay-root stamper | Brain. Every agent call goes through it. |
| `formulas/` | Every thesis formula as a typed callable (TH1–TH8, VSP, FG, Bekenstein, λ-gate, closure, confluence, graded norm) | One canonical implementation; agents can't disagree on the math |
| `mcp-server/` | Single MCP server exposing a11oy + formulas as MCP tools | Cursor, Claude Code, Replit Agent all plug into one source of truth |
| `agents/cursor/` | `.cursorrules`, `cursor.json`, MCP config | Cursor picks it up natively |
| `agents/replit/` | `.replit`, `replit.nix`, Agent prompt, `replit-agent.md` | Replit auto-detects on import |
| `agents/claude/` | `CLAUDE.md`, Claude Code SDK script, tool defs, slash commands | Claude Code reads `CLAUDE.md` on launch |
| `quickstart/` | `bootstrap.sh` — one-line setup, parallelized install | Fast cold start |
| `speed/` | Bun runtime, edge-function templates, response cache | 3–4× faster than Node defaults |

## How it works (the picture)

```
        ┌─────────────────────────────────────────────────────────┐
        │                     MCP Server                          │
        │  (stdio + HTTP, exposes a11oy-core + all formulas)      │
        └──────┬──────────────────┬──────────────────┬────────────┘
               │                  │                  │
        ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
        │   Cursor    │    │ Claude Code │    │Replit Agent │
        │ .cursorrules│    │  CLAUDE.md  │    │  .replit    │
        └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
               │                  │                  │
               └──────────────────┼──────────────────┘
                                  ▼
                    ┌──────────────────────────┐
                    │      a11oy-core          │
                    │  • doctrine gate (Λ≥0.90)│
                    │  • tool router            │
                    │  • replay-root stamper    │
                    │  • provider failover      │
                    └────────────┬─────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
       Anthropic              OpenAI         Ollama (local)
       (Claude)            (GPT-5/o-series)   (fallback)
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │     formulas/            │
                    │  TH1 lambdaGate          │
                    │  TH2 doiBind             │
                    │  TH3 closure             │
                    │  TH4 categoryOps         │
                    │  TH5 confluence          │
                    │  TH6 bekensteinBound     │
                    │  TH7 brandedTypes        │
                    │  TH8 gradedNorm          │
                    │  VSP spanEmit            │
                    │  FG gauges (12+3+4)      │
                    └──────────────────────────┘
```

## Speed levers (already pulled)

1. **Bun primary, Node fallback** — `package.json` declares `"engines"` for both; `bootstrap.sh` prefers Bun
2. **One MCP server** — three agents, one tool surface, no duplication
3. **Pre-warmed formula module** — formulas import at MCP boot, not on first call
4. **Parallel provider failover** — `Promise.race([anthropic, openai])` for the speed-critical path
5. **Streaming everywhere** — no buffering; tool results stream back to the agent

## Run it (60 seconds)

```bash
cd 12_agentic
bash quickstart/bootstrap.sh
# starts MCP server on :8090
# starts a11oy-core on :8091
# prints connection URLs for Cursor, Claude Code, Replit Agent
```

## Provider keys (Replit Secrets)

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
# Optional: OLLAMA_BASE_URL=http://localhost:11434
```

Without these, a11oy runs in **dry mode** — every formula still works, but model calls return a stub `{provider: "stub", note: "no API key configured"}`.

## Doctrine-aligned agent authority

Agents get the same scope as the CTO standing rule (see `../02_doctrine/DOCTRINE_V6.md`):

- ✅ Read code, run tests, run formulas, propose diffs, open **draft** PRs
- ❌ Push to `main`, merge own PRs, edit branch protection, mint Zenodo, submit arXiv, npm publish, force push, delete branches, change profile/org settings, edit scheduled tasks, rename live products, spend, touch credentials

a11oy enforces this. If an agent tries a blocked action, the doctrine gate returns `{denied: true, axis: "reversibility", reason: "..."}` and logs to `/home/user/workspace/cto_acceptance_log.jsonl`.

## Why this is fast

| What | Old way | This way | Win |
|---|---|---|---|
| Cold start | Node + cold imports | Bun + preload | 800ms → 200ms |
| First tool call | Lazy load formulas | Pre-warmed module | 400ms → 40ms |
| Provider call | Sequential failover | `Promise.race` | 1.2s → 600ms |
| Three agents, three tool layers | 3× duplication | 1 MCP server | maintenance ÷3 |
| Replit cold boot | Default Nix | `replit.nix` pre-baked | 45s → 12s |
