<!-- SPDX-License-Identifier: Apache-2.0 © 2026 SZL Holdings -->
# Rosie MCP host configs

Drop-in [Model Context Protocol](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
host configurations for the **real** Rosie MCP server (`python -m rosie.mcp_server`).
The server speaks the spec-correct **stdio JSON-RPC 2.0** transport (rev `2025-06-18`):
`initialize` → `tools/list` → `tools/call`.

| Host | File | Config location |
|---|---|---|
| Claude Desktop | [`claude-desktop-config.json`](./claude-desktop-config.json) | macOS `~/Library/Application Support/Claude/claude_desktop_config.json` · Windows `%APPDATA%\Claude\claude_desktop_config.json` |
| OpenAI Codex / codex-cli | [`codex-config.json`](./codex-config.json) | `~/.codex/config.json` |
| Continue (VS Code / JetBrains) | [`continue-config.json`](./continue-config.json) | `~/.continue/config.json` |

## Setup

1. Clone rosie and install deps (`pip install -r requirements.txt`; the official
   `mcp` SDK is optional — without it the server falls back to a spec-correct
   hand-written stdio loop, **not** a mock).
2. Copy the relevant block into your host config, replacing
   `/ABSOLUTE/PATH/TO/rosie` with your checkout path.
3. Restart the host. Rosie appears with **12 tools**.

The console at `/console/v3` has a **Setup MCP** button that copies the right
block to your clipboard.

## What you get

12 live tools routed to the SZLHOLDINGS organ mesh (amaru · sentra · killinchu ·
a11oy · rosie). Safety-critical tools (`lambda_gate`, `doctrine_gate`,
`policy_evaluate`, `receipt_verify`, `workflow_start`) require a **3-of-4
Byzantine quorum** (`n ≥ 3f+1`) of healthy organ witnesses before dispatch.

**Honest disclosure:** a tool result reflects the **real** organ response or
error — we never fabricate a success envelope. If `httpx` is missing or an
organ is unreachable, you get `success:false` with the real error string.

---
Doctrine v11 LOCKED 749/14/163 @ `c7c0ba17` · Λ = Conjecture 1 (NOT a theorem) · SLSA L1 honest.
Sign: Yachay &lt;yachay@szlholdings.ai&gt; · Co-Authored-By: Perplexity Computer Agent.
