# MCP Integration — Claude Desktop & Cursor

The **Hatun-MCP** server exposes **16 SZL tools** under PURIQ governance (Yuyay-13 gate, Khipu
receipts, DSSE-signed) over **Streamable HTTP + SSE**. Protocol version `2025-03-26`,
server `hatun-mcp`. Doctrine v11 · Apache-2.0.

Live endpoint: `https://szlholdings-a11oy.hf.space/mcp/`

> **Two gotchas** (root-caused during Warhacker prep):
> 1. The URL **must end with a trailing slash**: `/mcp/` (not `/mcp`).
> 2. The `Accept` header must include **both** `application/json` and `text/event-stream`.

---

## Claude Desktop

Claude Desktop reads `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add the SZL server. For remote Streamable-HTTP servers, use the `mcp-remote` bridge:

```json
{
  "mcpServers": {
    "szl-hatun": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://szlholdings-a11oy.hf.space/mcp/",
        "--header",
        "Accept: application/json, text/event-stream"
      ]
    }
  }
}
```

A drop-in copy of this is in [`EXAMPLES/mcp_claude_config.json`](./EXAMPLES/mcp_claude_config.json).
Restart Claude Desktop; you should see the SZL tools in the tools menu.

## Cursor

Cursor supports MCP via **Settings → MCP → Add new server**. Use the same `mcp-remote` command, or
point Cursor's `~/.cursor/mcp.json` at:

```json
{
  "mcpServers": {
    "szl-hatun": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://szlholdings-a11oy.hf.space/mcp/",
               "--header", "Accept: application/json, text/event-stream"]
    }
  }
}
```

## Verify it works from the CLI

```bash
# 1) initialize
curl -s https://szlholdings-a11oy.hf.space/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"cli","version":"0.1"}}}'

# 2) list the 16 tools
curl -s https://szlholdings-a11oy.hf.space/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Expect server `hatun-mcp`, protocol `2025-03-26`, and **exactly 16 tools**.

## What the tools do

The 16 tools span: DSSE signing & verification, Khipu chain operations, PURIQ master-formula
evaluation, Yuyay-13 gate scoring, Unay memory recall, doctrine-number lookup, and policy-gate
checks. Every tool call is governed (deny-by-default) and emits a signed receipt — so an MCP client
gets the same provenance guarantees as a direct HTTP caller.

## Security notes

- The public demo endpoint is rate-limited. For production, request an API key via the customer
  portal and pass it as a bearer header.
- All tool invocations are recorded on the Khipu Merkle DAG (tamper-evident; EU AI Act Art. 12).

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
