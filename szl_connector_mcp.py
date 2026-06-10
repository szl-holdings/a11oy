# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connector_mcp — MCP tool surface for the Enterprise Connector framework.

Exposes THREE governed tools to Chaski / the a11oy agent loop:

  szl_connector_health(connector_id)        → honest health (CONNECTED/READY/SAMPLE/ERROR)
  szl_connector_read(connector_id, limit, q) → live records | READY (no creds) | SAMPLE
  szl_connector_write(connector_id, action)  → Λ-gated + DSSE-receipted write (state-changing)

These are ADDITIVE. `TOOL_SCHEMAS` is the OpenAI-style function-tool list to be
merged into a11oy_code_orchestrator.TOOL_SCHEMAS; `dispatch(name, args)` is the
handler to be called from `_dispatch_tool`. `STATE_CHANGING` names the write tool
so the orchestrator's reversibility gate engages (2-person/quorum).

DOCTRINE: never fabricates a record; write() is Λ-gated (Λ≠1.0) + DSSE-receipted;
receipts carry credential FINGERPRINT hashes only (never the key value).
"""
from __future__ import annotations

from typing import Any

import szl_connectors as sc

# ── OpenAI-style function-tool schemas (merge into orchestrator TOOL_SCHEMAS) ──
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "szl_connector_health",
        "description": ("Honest health of an enterprise connector (CRM/ERP/identity/"
                        "comms/ITSM/warehouse/storage/observability/data-source). Returns "
                        "state CONNECTED (live)/READY (set the named secrets)/SAMPLE (no "
                        "free tier)/ERROR — plus the exact env-var secret names. NEVER fabricates."),
        "parameters": {"type": "object", "properties": {
            "connector_id": {"type": "string", "description": "e.g. salesforce, nvd_cve, odoo, okta"}},
            "required": ["connector_id"]}}},
    {"type": "function", "function": {
        "name": "szl_connector_read",
        "description": ("Read records from an enterprise connector. CONNECTED → live "
                        "provider records; READY → [] + 'provide credentials' + exact secret "
                        "names; SAMPLE → labelled fixture (no free tier). NEVER fabricates a record."),
        "parameters": {"type": "object", "properties": {
            "connector_id": {"type": "string"},
            "limit": {"type": "integer", "default": 12},
            "q": {"type": "string", "description": "optional query/keyword"}},
            "required": ["connector_id"]}}},
    {"type": "function", "function": {
        "name": "szl_connector_write",
        "description": ("Write to an enterprise connector (create/update). STATE-CHANGING: "
                        "Λ-gated (Λ never 1.0) + DSSE/Khipu-receipted; requires quorum for "
                        "state-changing actions. Blocked (with an honest receipt) when no "
                        "credentials are present or the gate denies."),
        "parameters": {"type": "object", "properties": {
            "connector_id": {"type": "string"},
            "action": {"type": "object", "description":
                       "{method:create|update, object, values:{...}, quorum_present:[...]}"}},
            "required": ["connector_id", "action"]}}},
]

# the orchestrator's reversibility gate should treat write as state-changing
STATE_CHANGING = {"szl_connector_write"}

TOOL_NAMES = {"szl_connector_health", "szl_connector_read", "szl_connector_write"}


def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Handler for the three connector tools. Returns JSON-serialisable dicts.

    Call this from a11oy_code_orchestrator._dispatch_tool:
        if name in szl_connector_mcp.TOOL_NAMES:
            return szl_connector_mcp.dispatch(name, args)
    """
    cid = args.get("connector_id", "")
    if name == "szl_connector_health":
        return sc.health(cid)

    if name == "szl_connector_read":
        c = sc.get(cid)
        if not c:
            return {"error": f"unknown connector '{cid}'", "known": sc.all_ids()}
        query = {"limit": max(1, min(int(args.get("limit", 12)), 50))}
        if args.get("q"):
            query["q"] = args["q"]
        try:
            return c.read(query).to_dict()
        except Exception as e:
            return {"connector_id": cid, "state": "error", "records": [], "live": False,
                    "note": f"read failed: {type(e).__name__}: {e}"}

    if name == "szl_connector_write":
        c = sc.get(cid)
        if not c:
            return {"error": f"unknown connector '{cid}'", "known": sc.all_ids()}
        if not getattr(c, "writable", False):
            return {"connector_id": cid, "ok": False, "detail": "connector is read-only"}
        try:
            return c.write(args.get("action") or {}).to_dict()
        except Exception as e:
            return {"connector_id": cid, "ok": False, "state": "error",
                    "detail": f"write failed: {type(e).__name__}: {e}"}

    raise ValueError(f"unknown connector tool {name}")


def writable_connectors() -> list[str]:
    """The connector ids that expose a Λ-gated write()."""
    out = []
    for cid in sc.all_ids():
        cls = sc.REGISTRY.get(cid)
        if cls and getattr(cls, "writable", False):
            out.append(cid)
    return out


__all__ = ["TOOL_SCHEMAS", "STATE_CHANGING", "TOOL_NAMES", "dispatch", "writable_connectors"]

# Doctrine v11 LOCKED — 749/14/163 — Λ = Conjecture 1 · honest states · no fabricated records ·
# write Λ-gated + DSSE-receipted · credential fingerprints only.
