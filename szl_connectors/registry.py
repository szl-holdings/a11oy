# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors.registry — the connector registry + the honest manifest.

Adding a connector = one subclass file + one `@register` decorator. The UI,
the MCP layer, and the governance layer all read the registry uniformly.

The manifest reports every connector's HONEST state right now (cheap path:
keyless → CONNECTED label verified on read; credentialed → READY/CONNECTED by
env presence; no-free-tier → SAMPLE). NEVER fabricates a record.
"""
from __future__ import annotations

from typing import Any

from .base import Connector, State, _now

REGISTRY: dict[str, type[Connector]] = {}   # id -> class


def register(cls: type[Connector]) -> type[Connector]:
    """@register decorator — one line per connector module."""
    if not getattr(cls, "id", None) or cls.id == "base":
        raise ValueError("connector must define a unique non-base `id`")
    REGISTRY[cls.id] = cls
    return cls


def get(cid: str) -> Connector | None:
    cls = REGISTRY.get(cid)
    return cls() if cls else None


def all_ids() -> list[str]:
    return sorted(REGISTRY.keys())


def _entry(cid: str, cls: type[Connector], *, probe: bool = False) -> dict[str, Any]:
    c = cls()
    h = c.health(probe=probe)
    return {
        "id": cid,
        "label": c.label or cid,
        "category": c.category,
        "auth_kind": c.auth_kind,
        "state": h.state.value if isinstance(h.state, State) else h.state,
        "env_vars": list(c.env_vars),
        "missing_env": h.missing_env,
        "free_tier": c.free_tier,
        "writable": c.writable,
        "provider_base": c.provider_base,
        "mcp_tool": c.mcp_tool,
        "detail": h.detail,
        "sample_reason": h.sample_reason,
        "schema_preview": list(c.schema_preview),
        "docs_url": c.docs_url,
        "latency_ms": h.latency_ms,
    }


def manifest(*, probe: bool = False, category: str | None = None) -> dict[str, Any]:
    """Every connector + its honest state, for the catalog UI + /healthz."""
    items = []
    for cid in sorted(REGISTRY):
        cls = REGISTRY[cid]
        try:
            e = _entry(cid, cls, probe=probe)
        except Exception as ex:  # honest error, never crash the manifest
            e = {"id": cid, "category": getattr(cls, "category", "?"),
                 "state": "error", "detail": f"manifest probe failed: {type(ex).__name__}"}
        if category and e.get("category") != category:
            continue
        items.append(e)
    # honest scoreboard
    counts = {"connected": 0, "ready": 0, "sample": 0, "error": 0}
    cats: dict[str, int] = {}
    for e in items:
        counts[e.get("state", "error")] = counts.get(e.get("state", "error"), 0) + 1
        cats[e.get("category", "?")] = cats.get(e.get("category", "?"), 0) + 1
    return {
        "doctrine": "v11 — honest CONNECTED/READY/SAMPLE only; no fabricated records; "
                    "no committed keys; Λ-gate+DSSE on writes; trust never 100%",
        "fetched_at": _now(),
        "count": len(items),
        "scoreboard": counts,
        "categories": cats,
        "connectors": items,
    }


def health(cid: str) -> dict[str, Any]:
    c = get(cid)
    if not c:
        return {"error": f"unknown connector '{cid}'", "known": all_ids()}
    return c.health(probe=True).to_dict()


__all__ = ["REGISTRY", "register", "get", "all_ids", "manifest", "health"]
