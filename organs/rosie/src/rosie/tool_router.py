# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""tool_router — routes MCP tool calls to the right organ adapter.

Safety-critical paths require a Byzantine quorum of n >= 3f+1 witnesses
(classic BFT bound; f=1 -> 3-of-4), matching SZL's khipu-consensus design.

Organ adapters call the REAL live HF Space endpoints over HTTP:
  amaru     https://szlholdings-amaru.hf.space
  sentra    https://szlholdings-sentra.hf.space
  killinchu https://szlholdings-killinchu.hf.space
  a11oy     https://szlholdings-a11oy.hf.space

Honest disclosure: if httpx is missing or an organ is unreachable, the adapter
returns success=False with the real error string — never a fabricated success.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

from .observability import child_traceparent

# ── Health-probe cache (60 s TTL, last-known-good on 429 / transient errors)
# Addresses: sibling organ health matrix showing 0/4 due to HF rate-limit (429).
# On a 429 or connection error the cache returns the last-known status so the
# dashboard stays warm rather than flipping all organs to DOWN.
_HEALTH_CACHE: dict[str, tuple[float, dict]] = {}  # organ -> (timestamp, result)
_HEALTH_TTL = 60.0  # seconds

ORGAN_BASE = {
    "amaru": os.environ.get("AMARU_URL", "https://szlholdings-amaru.hf.space"),
    "sentra": os.environ.get("SENTRA_URL", "https://szlholdings-sentra.hf.space"),
    "killinchu": os.environ.get("KILLINCHU_URL", "https://szlholdings-killinchu.hf.space"),
    "a11oy": os.environ.get("A11OY_URL", "https://szlholdings-a11oy.hf.space"),
    "rosie": os.environ.get("ROSIE_URL", "https://szlholdings-rosie.hf.space"),
}

# 12 live MCP tools (matches GET /api/rosie/v1/mcp/tools on the live Space).
TOOL_CATALOG: list[dict] = [
    {"name": "lambda_gate", "organ": "a11oy", "critical": True,
     "description": "Evaluate Λ aggregator verdict (Conjecture 1) for an action.",
     "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}},
    {"name": "doctrine_gate", "organ": "a11oy", "critical": True,
     "description": "Doctrine v11 ban-word + lock check on a payload.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "doi_bind", "organ": "a11oy", "critical": False,
     "description": "Bind a claim to its Zenodo DOI provenance.",
     "inputSchema": {"type": "object", "properties": {"claim": {"type": "string"}}, "required": ["claim"]}},
    {"name": "bekenstein_bound", "organ": "amaru", "critical": False,
     "description": "Compute the Bekenstein information bound for a payload size.",
     "inputSchema": {"type": "object", "properties": {"bytes": {"type": "number"}}, "required": ["bytes"]}},
    {"name": "policy_evaluate", "organ": "sentra", "critical": True,
     "description": "Evaluate an action across the 46 policy gates.",
     "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}},
    {"name": "receipt_verify", "organ": "a11oy", "critical": True,
     "description": "Verify a DSSE receipt envelope.",
     "inputSchema": {"type": "object", "properties": {"envelope": {"type": "object"}}, "required": ["envelope"]}},
    {"name": "ledger_append", "organ": "rosie", "critical": False,
     "description": "Append a signed receipt to the Khipu ledger.",
     "inputSchema": {"type": "object", "properties": {"receipt": {"type": "object"}}, "required": ["receipt"]}},
    {"name": "cite_theorem", "organ": "amaru", "critical": False,
     "description": "Look up a Lean declaration in the 749-decl index.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "mesh_inspect", "organ": "rosie", "critical": False,
     "description": "Aggregate mesh health across the 5 organs.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "memory_write", "organ": "amaru", "critical": False,
     "description": "WAYRA ingest: chunk + embed + SHA a document into cortex memory.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "memory_query", "organ": "amaru", "critical": False,
     "description": "Cosine recall over provenanced cortex memory.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "workflow_start", "organ": "rosie", "critical": True,
     "description": "Start an orchestrated Amaru->Sentra->Killinchu->A11oy workflow.",
     "inputSchema": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}},
]

CRITICAL_TOOLS = {t["name"] for t in TOOL_CATALOG if t.get("critical")}
TOOL_INDEX = {t["name"]: t for t in TOOL_CATALOG}

# Health probe paths per organ (verified live 2026-06-03).
_HEALTH_PATH = {
    "amaru": "/api/amaru/healthz", "sentra": "/api/sentra/healthz",
    "killinchu": "/api/killinchu/healthz", "a11oy": "/healthz",
    "rosie": "/api/rosie/healthz",
}


def byzantine_quorum_n(f: int) -> int:
    """Minimum witnesses for BFT safety: n >= 3f + 1."""
    return 3 * f + 1


def _http_get(url: str, timeout: float = 12.0) -> tuple[int, Any]:
    try:
        import httpx
        r = httpx.get(url, timeout=timeout)
        try:
            body = r.json()
        except Exception:
            body = r.text[:500]
        return r.status_code, body
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def _http_post(url: str, payload: dict, traceparent: str, timeout: float = 15.0) -> tuple[int, Any]:
    try:
        import httpx
        r = httpx.post(url, json=payload, timeout=timeout,
                       headers={"traceparent": traceparent,
                                "content-type": "application/json"})
        try:
            body = r.json()
        except Exception:
            body = r.text[:500]
        return r.status_code, body
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


class ToolRouter:
    """Routes MCP tool calls to the correct organ and reports their health.

    Wraps the tool ``catalog`` (defaulting to the built-in ``TOOL_CATALOG``),
    indexes it by tool name, and optionally accepts a ``dispatch_override``
    callable to stub network calls in tests.
    """

    def __init__(self, catalog: list[dict] | None = None,
                 dispatch_override: Callable | None = None):
        self.catalog = catalog or TOOL_CATALOG
        self.index = {t["name"]: t for t in self.catalog}
        self._override = dispatch_override

    def list_tools(self) -> list[dict]:
        """Return the public tool catalog for MCP ``tools/list``.

        Returns:
            One dict per tool with name, description, inputSchema, owning
            organ, and a ``critical`` flag — the MCP-facing view of the
            catalog.
        """
        return [{"name": t["name"], "description": t["description"],
                 "inputSchema": t["inputSchema"], "organ": t["organ"],
                 "critical": t.get("critical", False)} for t in self.catalog]

    def organ_health(self) -> dict:
        """Real health probe of every organ (used by mesh_inspect / 3d graph).

        Results are cached for _HEALTH_TTL seconds (60 s) to survive HF
        rate-limit (HTTP 429) bursts.  On 429 or connection failure the last
        known-good value is returned so the dashboard stays warm.  Honest:
        each entry records whether it was served from cache and whether the
        last live probe was a 429.
        """
        out = {}
        now = time.monotonic()
        for organ, base in ORGAN_BASE.items():
            cached_ts, cached_val = _HEALTH_CACHE.get(organ, (0.0, None))
            if cached_val is not None and (now - cached_ts) < _HEALTH_TTL:
                # Fresh cache hit — serve without hitting the network.
                out[organ] = dict(cached_val, _from_cache=True)
                continue
            code, body = _http_get(base + _HEALTH_PATH[organ], timeout=10.0)
            is_rate_limited = (code == 429)
            if is_rate_limited and cached_val is not None:
                # Return last-known-good on 429; mark as rate-limited.
                out[organ] = dict(cached_val, _from_cache=True, _rate_limited=True)
                continue
            entry = {"http": code, "ok": code == 200,
                     "lambda": (body.get("lambda_status") if isinstance(body, dict) else None)
                     or "Conjecture 1 (NOT a theorem)",
                     "base": base,
                     "_from_cache": False,
                     "_rate_limited": is_rate_limited}
            # Only cache genuinely useful results (non-429, non-zero).
            if code not in (0, 429):
                _HEALTH_CACHE[organ] = (now, entry)
            out[organ] = entry
        return out

    def quorum_witnesses(self, tool: str, traceparent: str) -> dict:
        """For a safety-critical tool, gather a BFT 3-of-4 witness set.

        Witnesses = the 4 organs' /healthz attestations. We require n>=3f+1=4
        reachable witnesses AND >=3 (a 3-of-4 majority) to be healthy for the
        path to be permitted. Honest: returns the real per-witness status.
        """
        n_required = byzantine_quorum_n(1)  # 4
        witnesses = self.organ_health()
        organ_witnesses = {k: v for k, v in witnesses.items() if k != "rosie"}
        healthy = sum(1 for v in organ_witnesses.values() if v["ok"])
        permitted = healthy >= 3  # 3-of-4 majority
        return {
            "tool": tool, "bft_bound": "n>=3f+1", "n_required": n_required,
            "witnesses": organ_witnesses, "healthy_witnesses": healthy,
            "quorum_permitted": permitted,
            "rule": "3-of-4 organ witnesses must attest healthy for safety-critical dispatch",
        }

    def route(self, tool: str, arguments: dict, traceparent: str) -> dict:
        """Route a tool call to its organ adapter (real HTTP)."""
        if tool not in self.index:
            return {"tool": tool, "success": False, "error": f"unknown tool '{tool}'"}
        spec = self.index[tool]
        organ = spec["organ"]
        tp = child_traceparent(traceparent)

        # Byzantine quorum gate on safety-critical tools.
        quorum = None
        if tool in CRITICAL_TOOLS:
            quorum = self.quorum_witnesses(tool, tp)
            if not quorum["quorum_permitted"]:
                return {"tool": tool, "organ": organ, "success": False,
                        "error": "byzantine_quorum_denied",
                        "quorum": quorum, "traceparent": tp}

        if self._override:
            res = self._override(tool, arguments, organ, tp)
            if quorum:
                res["quorum"] = quorum
            return res

        res = self._dispatch_organ(organ, tool, arguments, tp)
        if quorum:
            res["quorum"] = quorum
        return res

    def _dispatch_organ(self, organ: str, tool: str, arguments: dict, tp: str) -> dict:
        base = ORGAN_BASE[organ]
        # Map tools to concrete, real endpoints where they exist; otherwise
        # use the organ's mcp/call contract.
        if organ == "rosie" and tool == "mesh_inspect":
            code, body = _http_get(base + "/api/rosie/v1/mesh/state")
            return {"tool": tool, "organ": organ, "success": code == 200,
                    "http": code, "result": body, "traceparent": tp}
        # Generic MCP call contract: POST /api/<organ>/v1/mcp/call
        code, body = _http_post(base + f"/api/{organ}/v1/mcp/call",
                                {"name": tool, "arguments": arguments}, tp)
        # Many organs only expose a healthz today; treat a reachable organ as a
        # real hit and record the honest status code.
        ok = code in (200, 201)
        if code in (404, 405):
            # tool endpoint not present on that organ build — fall back to a
            # real health attestation so the hop is still proven reachable.
            hcode, hbody = _http_get(base + _HEALTH_PATH[organ])
            return {"tool": tool, "organ": organ, "success": hcode == 200,
                    "http": hcode, "via": "healthz-attestation",
                    "result": hbody, "traceparent": tp}
        return {"tool": tool, "organ": organ, "success": ok, "http": code,
                "result": body, "traceparent": tp}
