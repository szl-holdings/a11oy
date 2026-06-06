# MCP Integration — Claude Desktop & Cursor

The SZL MCP tools run under PURIQ governance (Yuyay-13 gate, Khipu receipts, DSSE-signed).
Doctrine v11 · Apache-2.0.

> **⚠️ LIVE STATUS (honest).** The **Streamable-HTTP JSON-RPC transport at `/mcp/` is roadmap —
> NOT yet live.** On the deployed a11oy Space, `POST /mcp/` (`initialize` / `tools/list`) returns
> **HTTP 405 Method Not Allowed**, and `GET /mcp/` serves an HTML landing page. The `mcp-remote`
> bridge configs below therefore will **not** connect yet — they are provided for when the JSON-RPC
> transport ships.
>
> **What works today** is the REST MCP surface on a11oy:
> ```bash
> curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/tools   # JSON tool catalog (4 tools)
> curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/call \
>   -H 'content-type: application/json' \
>   -d '{"tool":"lambda_score","args":{}}'
> ```
> The catalog currently exposes **4 governed tools** (e.g. `a11oy_gate`, `lambda_score`). The
> "16-tool Hatun-MCP" is the planned JSON-RPC surface — do not demo a 16-tool MCP as live.

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

## Verify the LIVE MCP surface from the CLI

The REST surface below is live and verifiable right now:

```bash
# list the governed tools (live — JSON catalog)
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/tools | python3 -m json.tool

# call a tool (live — returns a governed result + doctrine block)
curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/call \
  -H 'content-type: application/json' \
  -d '{"tool":"lambda_score","args":{}}' | python3 -m json.tool
```

Expect a catalog of **4 tools** today (`a11oy_gate`, `lambda_score`, …) — not 16.

### JSON-RPC `/mcp/` transport (roadmap — currently 405)

The following commands describe the *planned* Streamable-HTTP JSON-RPC transport. **They return
HTTP 405 on the deployed Space today** and are documented for when that transport ships:

```bash
# (roadmap) initialize
curl -s https://szlholdings-a11oy.hf.space/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"cli","version":"0.1"}}}'
# (roadmap) tools/list
curl -s https://szlholdings-a11oy.hf.space/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

## What the tools do

The governed tools span: DSSE signing & verification, Khipu chain operations, PURIQ master-formula
evaluation, Yuyay-13 gate scoring, Unay memory recall, doctrine-number lookup, and policy-gate
checks. Every tool call is governed (deny-by-default) and emits a signed receipt — so an MCP client
gets the same provenance guarantees as a direct HTTP caller.

## Security notes

- The public demo endpoint is rate-limited. For production, request an API key via the customer
  portal and pass it as a bearer header.
- All tool invocations are recorded on the Khipu Merkle DAG (tamper-evident; EU AI Act Art. 12).

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
