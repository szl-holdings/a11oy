# MCP Integration — Claude Desktop & Cursor

The SZL MCP tools run under PURIQ governance (Yuyay-13 gate, Khipu receipts, DSSE-signed).
Doctrine v11 · Apache-2.0.

> **Request contract.** `GET /mcp/` returns the runtime JSON catalog and does not mint a receipt.
> `POST /mcp/` is JSON-RPC (`initialize`, `tools/list`, `tools/call`). `policy_check` returns a
> gate verdict and does not mint a receipt. `sign_receipt` requires the operator bearer.
>
> `POST /api/a11oy/v1/mcp/call` is a different, operator-only REST surface. Without
> `Authorization: Bearer <operator credential>` it returns HTTP 401 and does not run the tool.
> The body fields are `name` and `arguments`. `lambda_score` also requires a non-empty `axes` list.
> ```bash
> curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/tools
> curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/call \
>   -H 'content-type: application/json' \
>   -H "authorization: Bearer $A11OY_CODE_ADMIN_KEY" \
>   -d '{"name":"lambda_score","arguments":{"axes":[0.5,0.5]}}'
> ```
> Tool counts are the counts in those responses. Do not advertise a fixed catalog size.

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

# operator REST call. Anonymous requests are HTTP 401. tool/args is not the schema.
curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/mcp/call \
  -H 'content-type: application/json' \
  -H "authorization: Bearer $A11OY_CODE_ADMIN_KEY" \
  -d '{"name":"lambda_score","arguments":{"axes":[0.5,0.5]}}' | python3 -m json.tool
```

The REST catalog and the JSON-RPC catalog are different lists. Read each response for its count.

### JSON-RPC `/mcp/` 

`GET /mcp/` is JSON. `POST /mcp/` runs the method below. A payment header is not read by this
handler and is not a receipt.

```bash
curl -s https://szlholdings-a11oy.hf.space/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"policy_check","arguments":{"severity":"low","confidence":0.9,"reversible":true}}}'
```

## What the tools do

`policy_check` returns a deny-by-default gate verdict and does not mint a receipt. `sign_receipt`
signs a caller-supplied payload only after the operator bearer check. A tool call is not itself
a payment settlement.

## Security notes

- `POST /api/a11oy/v1/mcp/call` and JSON-RPC `sign_receipt` require the operator credential.
  An invited tester does not receive that credential.
- Origin handlers on `/mcp/` do not accept a payment header as authorization. Edge payment
  challenges are a separate control.

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
