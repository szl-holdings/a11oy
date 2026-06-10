# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
a11oy_mcp_client — Streamable-HTTP MCP client to the live ``hatun-mcp`` server.

SHARED module: deployed BYTE-IDENTICAL on a11oy and killinchu (additive).

The canonical MCP backend for a11oy Code's governed tools is the live, operational
``hatun-mcp`` server (Streamable HTTP):

    https://szlholdings-hatun-mcp.hf.space/mcp

It speaks the official Model-Context-Protocol JSON-RPC 2.0 contract over a single
HTTP POST endpoint (the "Streamable HTTP" transport): ``initialize`` →
``tools/list`` → ``tools/call``.  Each ``tools/call`` returns a DSSE-signed
governance receipt (PURIQ 7-step contract).  This client:

  * lists the live tool surface (49 tools as of the 2026-06-03 probe),
  * calls a tool by name with JSON arguments,
  * surfaces the returned Khipu receipt hash so the agent loop can chain it.

HONESTY (Doctrine v11, Zero-Bandaid Law):
  * If the MCP endpoint is paused / unreachable, this returns a LABELED honest
    error — never a mock tool result.  ``ok=False`` with ``honest_error``.
  * No credential is required to *read* the public hatun-mcp surface; calls that
    the server itself gates (state-changing tools) return the server's own
    governance verdict verbatim.  We never fabricate a verdict.
  * This is SZL's own original client code.  The MCP wire format is the open
    JSON-RPC 2.0 / MCP spec (https://modelcontextprotocol.io), not proprietary code.

Pattern attribution (fashion-thinking, reimplemented originally):
  * Anthropic Claude tool-use loop (https://platform.claude.com/docs/en/agents-and-tools/tool-use/build-a-tool-using-agent)
  * OpenAI Agents SDK agent loop (https://openai.github.io/openai-agents-python/agents/)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

try:
    import httpx  # already a dependency of the orchestrator
except Exception:  # pragma: no cover - httpx is in-image
    httpx = None  # type: ignore

# Canonical live endpoint (overridable by env for a private mirror / local test).
HATUN_MCP_URL = os.environ.get(
    "HATUN_MCP_URL", "https://szlholdings-hatun-mcp.hf.space/mcp"
)
PROTOCOL_VERSION = "2025-06-18"  # MCP Streamable-HTTP protocol revision we negotiate
CLIENT_INFO = {"name": "a11oy-code", "version": "1.0.0"}
_DEFAULT_TIMEOUT = float(os.environ.get("HATUN_MCP_TIMEOUT", "60"))


class McpHonestError(RuntimeError):
    """Raised when the MCP endpoint is unreachable or returns a transport error.

    The caller is expected to surface this as a LABELED honest error, never to
    fabricate a tool result in its place (Zero-Bandaid Law)."""


def _headers(session_id: str | None = None) -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        # Streamable HTTP requires the client to accept BOTH json and SSE.
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def _parse_streamable(resp: "httpx.Response") -> dict[str, Any]:
    """Parse a Streamable-HTTP response. The server may return a single JSON
    object OR an SSE stream of ``data:`` lines; we accept both and return the
    LAST JSON-RPC result/response object found.  No fabrication — if nothing
    parses, we raise an honest error."""
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        last: dict[str, Any] | None = None
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if not chunk:
                    continue
                try:
                    last = json.loads(chunk)
                except Exception:
                    continue
        if last is None:
            raise McpHonestError("MCP SSE response carried no parseable JSON-RPC object")
        return last
    # plain JSON
    try:
        return resp.json()
    except Exception as exc:
        raise McpHonestError(f"MCP response not JSON ({ctype}): {resp.text[:200]!r}") from exc


class HatunMcpClient:
    """Minimal synchronous Streamable-HTTP MCP client for hatun-mcp.

    Lifecycle: ``initialize`` (negotiates a session id) → ``list_tools`` →
    ``call_tool``.  Reuses one ``httpx.Client`` and the negotiated session id.
    Stateless callers can use the module-level convenience functions instead.
    """

    def __init__(self, url: str | None = None, timeout: float = _DEFAULT_TIMEOUT) -> None:
        if httpx is None:  # pragma: no cover
            raise McpHonestError("httpx is not available in this runtime")
        self.url = url or HATUN_MCP_URL
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._session_id: str | None = None
        self._initialized = False
        self._rpc_id = 0

    # -- JSON-RPC plumbing ------------------------------------------------- #
    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _rpc(self, method: str, params: dict[str, Any] | None = None,
             notify: bool = False) -> dict[str, Any] | None:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self._next_id()
        try:
            resp = self._client.post(self.url, headers=_headers(self._session_id), json=body)
        except Exception as exc:
            raise McpHonestError(f"MCP transport error contacting {self.url}: {exc}") from exc
        # capture/refresh the session id the server may assign on initialize
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
        if sid:
            self._session_id = sid
        if resp.status_code >= 400:
            raise McpHonestError(
                f"MCP endpoint {self.url} returned HTTP {resp.status_code}: "
                f"{resp.text[:200]!r} (endpoint may be paused — honest error, no mock)"
            )
        if notify:
            return None
        obj = _parse_streamable(resp)
        if isinstance(obj, dict) and obj.get("error"):
            err = obj["error"]
            raise McpHonestError(f"MCP JSON-RPC error: {err.get('message')} ({err.get('code')})")
        return obj

    # -- MCP methods ------------------------------------------------------- #
    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {"already": True, "session_id": self._session_id}
        out = self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        })
        # MCP requires a notifications/initialized after a successful initialize.
        try:
            self._rpc("notifications/initialized", {}, notify=True)
        except Exception:
            pass  # best-effort; some servers do not require it
        self._initialized = True
        return (out or {}).get("result", out or {})

    def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        out = self._rpc("tools/list", {})
        result = (out or {}).get("result", {}) if out else {}
        return result.get("tools", []) if isinstance(result, dict) else []

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a hatun-mcp tool. Returns the server's content + any DSSE receipt
        verbatim.  The server enforces its own PURIQ gate; we do NOT second-guess
        or fabricate its verdict."""
        if not self._initialized:
            self.initialize()
        out = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        result = (out or {}).get("result", {}) if out else {}
        # Normalize: MCP returns {content:[{type,text|json}], isError, ...}
        content = result.get("content", []) if isinstance(result, dict) else []
        text_parts: list[str] = []
        struct: Any = result.get("structuredContent") if isinstance(result, dict) else None
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text" and isinstance(c.get("text"), str):
                    text_parts.append(c["text"])
        receipt_hash = None
        # Try to surface a DSSE/Khipu receipt hash if the tool returned one.
        probe = struct if isinstance(struct, dict) else None
        if probe is None and text_parts:
            try:
                probe = json.loads(text_parts[0])
            except Exception:
                probe = None
        if isinstance(probe, dict):
            receipt_hash = (
                probe.get("receipt_hash")
                or probe.get("khipu_hash")
                or (probe.get("receipt") or {}).get("hash")
                or (probe.get("dsse") or {}).get("_pae_sha256")
            )
        return {
            "ok": not (isinstance(result, dict) and result.get("isError")),
            "tool": name,
            "content_text": "\n".join(text_parts) if text_parts else None,
            "structured": struct,
            "receipt_hash": receipt_hash,
            "session_id": self._session_id,
            "raw_result": result,
        }

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Module-level convenience wrappers (one-shot; open + close a client).
# Each returns an honest {ok, ...} dict and NEVER raises into the agent loop —
# transport failures become labeled honest errors.
# --------------------------------------------------------------------------- #
def list_tools(url: str | None = None) -> dict[str, Any]:
    t0 = time.time()
    try:
        cli = HatunMcpClient(url)
        tools = cli.list_tools()
        cli.close()
        return {
            "ok": True, "endpoint": url or HATUN_MCP_URL,
            "tool_count": len(tools),
            "tools": [{"name": t.get("name"), "description": (t.get("description") or "")[:160]}
                      for t in tools],
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except McpHonestError as exc:
        return {"ok": False, "honest_error": str(exc), "endpoint": url or HATUN_MCP_URL,
                "note": "hatun-mcp unreachable — honest error, no fabricated tool list."}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "honest_error": f"{type(exc).__name__}: {exc}",
                "endpoint": url or HATUN_MCP_URL}


def call_tool(name: str, arguments: dict[str, Any] | None = None,
              url: str | None = None) -> dict[str, Any]:
    t0 = time.time()
    try:
        cli = HatunMcpClient(url)
        out = cli.call_tool(name, arguments)
        cli.close()
        out["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return out
    except McpHonestError as exc:
        return {"ok": False, "tool": name, "honest_error": str(exc),
                "endpoint": url or HATUN_MCP_URL,
                "note": "hatun-mcp call failed — honest error, no fabricated result."}
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "tool": name, "honest_error": f"{type(exc).__name__}: {exc}"}


def verify_receipt(receipt_hash: str, url: str | None = None) -> dict[str, Any]:
    """Verify a Khipu receipt hash via hatun-mcp ``szl_khipu_verify``."""
    return call_tool("szl_khipu_verify", {"receipt_hash": receipt_hash}, url=url)


if __name__ == "__main__":  # honest self-probe (no fabrication)
    import sys
    print(json.dumps(list_tools(), indent=2)[:4000], file=sys.stderr)
