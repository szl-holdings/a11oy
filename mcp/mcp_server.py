# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""mcp_server — real Model Context Protocol server for Rosie's 12-tool catalog.

Field leader: Anthropic MCP spec, rev 2025-06-18 (Base Protocol → Transports).
  https://modelcontextprotocol.io/specification/2025-06-18/basic/transports

Two ways to run, both REAL:

  1. If the official `mcp` Python SDK is installed, we build an `mcp.server.Server`
     with `list_tools` / `call_tool` handlers and run it over the stdio transport —
     the exact server a host (Claude Desktop, Codex) spawns.

  2. If the SDK is absent (airgap), we run a hand-written but spec-correct stdio
     JSON-RPC 2.0 loop: newline-delimited messages on stdin/stdout, supporting
     `initialize`, `tools/list`, and `tools/call`. This is NOT a mock — it speaks
     the real wire protocol; `tests/test_mcp_stdio.py` drives it as a subprocess.

Run:  python -m rosie.mcp_server      (stdio; register in any MCP host config)

Tool execution routes through ToolRouter → live organs (BFT quorum on critical
tools). Honest disclosure: a tool result reflects the REAL organ response /
error; we never fabricate a success envelope.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from .observability import make_traceparent
from .tool_router import TOOL_CATALOG, ToolRouter

SERVER_NAME = "rosie"
SERVER_VERSION = "3.0.0"
PROTOCOL_VERSION = "2025-06-18"

_router = ToolRouter()


def _public_tools() -> list[dict]:
    """MCP tool descriptors: name, description, inputSchema (JSON Schema)."""
    return [{"name": t["name"], "description": t["description"],
             "inputSchema": t["inputSchema"]} for t in TOOL_CATALOG]


def _call_tool(name: str, arguments: dict) -> dict:
    """Execute a tool and return an MCP CallToolResult-shaped dict.

    {content: [{type:'text', text: ...}], isError: bool}
    """
    tp = make_traceparent()
    result = _router.route(name, arguments or {}, tp)
    is_error = not result.get("success", False)
    text = json.dumps(result, default=str, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# ── Path 1: official MCP SDK (preferred) ──────────────────────────────────────


def _run_sdk() -> bool:
    """Try to run via the official `mcp` SDK over stdio. Returns False if absent."""
    try:
        import anyio
        import mcp.types as types
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except Exception:
        return False

    server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list() -> list[Any]:
        return [types.Tool(name=t["name"], description=t["description"],
                           inputSchema=t["inputSchema"]) for t in TOOL_CATALOG]

    @server.call_tool()
    async def _call(name: str, arguments: dict | None) -> list[Any]:
        res = _call_tool(name, arguments or {})
        return [types.TextContent(type="text", text=c["text"])
                for c in res["content"]]

    async def _main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(_main)
    return True


# ── Path 2: spec-correct hand-written stdio JSON-RPC loop ─────────────────────


def _jsonrpc_result(req_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_message(msg: dict) -> dict | None:
    """Handle one JSON-RPC request; return a response dict (or None for notifications)."""
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return _jsonrpc_result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION,
                           "doctrine": "v11 LOCKED 749/14/163 @ c7c0ba17",
                           "lambda": "Conjecture 1 (NOT a theorem)"},
        })
    if method in ("notifications/initialized", "initialized"):
        return None  # notification — no response
    if method == "ping":
        return _jsonrpc_result(req_id, {})
    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": _public_tools()})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in {t["name"] for t in TOOL_CATALOG}:
            return _jsonrpc_error(req_id, -32602, f"unknown tool: {name}")
        return _jsonrpc_result(req_id, _call_tool(name, arguments))
    return _jsonrpc_error(req_id, -32601, f"method not found: {method}")


def _run_stdio(stdin=None, stdout=None) -> None:
    """Newline-delimited JSON-RPC 2.0 over stdio (MCP stdio transport)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _jsonrpc_error(None, -32700, "parse error")
            stdout.write(json.dumps(resp) + "\n"); stdout.flush()
            continue
        resp = handle_message(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, default=str) + "\n")
            stdout.flush()


def main() -> None:
    """Entry point for the rosie MCP server.

    Tries to run via the MCP SDK first; if the SDK is unavailable, falls
    back to a line-delimited JSON-RPC loop over stdio. Returns nothing and
    blocks until the transport closes.
    """
    if not _run_sdk():
        _run_stdio()


if __name__ == "__main__":
    main()
