# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Real stdio MCP protocol test.

Spawns `python -m rosie.mcp_server` as a child process (exactly how an MCP host
launches it) and drives the real stdio JSON-RPC 2.0 wire: initialize →
tools/list → tools/call. Asserts the spec-shaped envelopes.

Also unit-tests the in-process `handle_message` dispatcher so the protocol logic
is covered even without a subprocess.

Run:  pytest -q tests/test_mcp_stdio.py
Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
import json
import os
import subprocess
import sys

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)

from rosie.mcp_server import handle_message, PROTOCOL_VERSION  # noqa: E402
from rosie.tool_router import TOOL_CATALOG                     # noqa: E402

EXPECTED_TOOLS = {t["name"] for t in TOOL_CATALOG}


# ── in-process protocol unit tests ────────────────────────────────────────────

def test_initialize_envelope():
    resp = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": PROTOCOL_VERSION}})
    assert resp["jsonrpc"] == "2.0" and resp["id"] == 1
    assert resp["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert resp["result"]["serverInfo"]["name"] == "rosie"
    assert "Conjecture 1" in resp["result"]["serverInfo"]["lambda"]


def test_tools_list_has_12_tools():
    resp = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) == 12
    assert {t["name"] for t in tools} == EXPECTED_TOOLS
    for t in tools:
        assert "description" in t and "inputSchema" in t


def test_initialized_notification_is_silent():
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_tool_is_error():
    resp = handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                           "params": {"name": "nope", "arguments": {}}})
    assert "error" in resp


def test_unknown_method_is_error():
    resp = handle_message({"jsonrpc": "2.0", "id": 4, "method": "frobnicate"})
    assert resp["error"]["code"] == -32601


# ── real subprocess over stdio ────────────────────────────────────────────────

def _drive_subprocess(messages):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.abspath(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    # Force the hand-written stdio path so the test is deterministic regardless
    # of whether the optional `mcp` SDK is installed in CI.
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; from rosie.mcp_server import _run_stdio; _run_stdio()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env)
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    out, err = proc.communicate(payload, timeout=60)
    lines = [json.loads(l) for l in out.splitlines() if l.strip()]
    return lines, err


def test_stdio_subprocess_initialize_and_list():
    lines, err = _drive_subprocess([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ])
    # notification produces no line -> 2 responses for 2 requests
    assert len(lines) == 2, f"stderr: {err}"
    assert lines[0]["result"]["serverInfo"]["name"] == "rosie"
    assert len(lines[1]["result"]["tools"]) == 12


def test_stdio_subprocess_tools_call_envelope():
    # workflow_start is safety-critical -> goes through the BFT quorum gate.
    # With no network the organs are unreachable, so the REAL result is an
    # honest isError=true envelope (quorum denied / unreachable) — NOT a fake ok.
    lines, err = _drive_subprocess([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "mesh_inspect", "arguments": {}}},
    ])
    assert len(lines) == 2, f"stderr: {err}"
    res = lines[1]["result"]
    assert "content" in res and res["content"][0]["type"] == "text"
    assert "isError" in res  # honest success/failure flag present
    # the content is the real router result JSON
    inner = json.loads(res["content"][0]["text"])
    assert inner["tool"] == "mesh_inspect"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
