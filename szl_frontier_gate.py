# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1. Trust ceiling 0.97 is policy.
"""szl_frontier_gate.py — fail-closed advisory isolation for frontier proposals.

This is not AGI, not a production publisher, and not Hatun.
A retrieved instruction, formula, receipt, or HTTP 200 cannot grant ALLOW.
Missing children cannot be folded into ALL_DONE.
Private sources that are not bound force ABSTAIN.

Stdlib only. Register additively; never replace existing routes.
"""
from __future__ import annotations

from typing import Any, Mapping

TRUST_CEILING = 0.97
KERNEL_CUTOFF = "2026-09-13"
LOCKED_FORMULAS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
CONJECTURE_1 = "Λ uniqueness remains Conjecture 1 — advisory, never a theorem."

_PRIVATE_HINTS = (
    "private memory",
    "private source",
    "tenant secret",
    "my private",
    "cross-tenant",
)


def clamp_trust(value: Any) -> dict[str, Any]:
    """F19: 0.97 is policy. Never render 1.0 as a LIVE quality score."""
    try:
        asked = float(value)
    except (TypeError, ValueError):
        return {
            "asked": value,
            "admitted": TRUST_CEILING,
            "kind": "policy",
            "honesty": "HOLD",
            "reason": "unparseable trust request — policy ceiling applied",
        }
    if asked > TRUST_CEILING:
        return {
            "asked": asked,
            "admitted": TRUST_CEILING,
            "kind": "policy",
            "honesty": "HOLD",
            "reason": "clamped — never 1.0, never a measured LIVE score",
        }
    if asked < 0:
        return {
            "asked": asked,
            "admitted": 0.0,
            "kind": "policy",
            "honesty": "HOLD",
            "reason": "negative trust is not evidence",
        }
    return {
        "asked": asked,
        "admitted": asked,
        "kind": "policy",
        "honesty": "SOFTWARE",
        "reason": "at or below ceiling",
    }


def bind_count(raw: Any) -> dict[str, Any]:
    """Zero stays zero. HTTP 200 is not a count."""
    if raw is None:
        return {"kind": "unknown", "value": None, "reason": "missing"}
    if isinstance(raw, bool):
        return {"kind": "invalid", "value": None, "reason": "boolean is not a count"}
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw < 0 or raw != int(raw):
            return {"kind": "invalid", "value": None, "reason": "count must be a whole non-negative integer"}
        value = int(raw)
        return {"kind": "zero" if value == 0 else "count", "value": value}
    return {"kind": "invalid", "value": None, "reason": "unparseable count"}


def never_live_from_http(status: Any) -> dict[str, Any]:
    if status == 200:
        return {
            "http": 200,
            "live": False,
            "honesty": "SNAPSHOT",
            "reason": "HTTP 200 is reachability, not LIVE",
        }
    return {
        "http": status,
        "live": False,
        "honesty": "UNAVAILABLE",
        "reason": "non-200 cannot grant LIVE",
    }


def estate_gate(children: Mapping[str, str] | None) -> dict[str, Any]:
    """Full-estate gate. Skipped or failed children forbid ALL_DONE."""
    kids = dict(children or {})
    if not kids:
        return {
            "verdict": "HOLD",
            "all_done": False,
            "reason": "empty child set is not ALL_DONE",
            "failed_or_skipped": [],
        }
    bad = [
        name
        for name, state in kids.items()
        if state not in {"EXECUTED_PASS", "NOT_APPLICABLE", "VERIFIED_REUSE"}
    ]
    if bad:
        return {
            "verdict": "HOLD",
            "all_done": False,
            "reason": f"{len(bad)} required children unexecuted or failed",
            "failed_or_skipped": bad,
        }
    return {
        "verdict": "SCOPED_PASS",
        "all_done": False,
        "reason": "scoped children passed — full-estate ALL_DONE still requires independent proof projection",
        "failed_or_skipped": [],
    }


def retrieve_or_abstain(query: str, passages: list[Mapping[str, Any]] | None, *, tenant: str = "public") -> dict[str, Any]:
    """Authorization before rank. Private sources that are not bound abstain."""
    q = (query or "").strip()
    docs = list(passages or [])
    lowered = q.lower()
    if tenant and tenant != "public":
        return {
            "abstain": True,
            "reason": "PRIVATE_SOURCE_NOT_BOUND",
            "hits": [],
            "backend": "none",
        }
    if any(hint in lowered for hint in _PRIVATE_HINTS):
        return {
            "abstain": True,
            "reason": "PRIVATE_SOURCE_NOT_BOUND",
            "hits": [],
            "backend": "none",
        }
    if not docs:
        return {
            "abstain": True,
            "reason": "no authorized public passages",
            "hits": [],
            "backend": "none",
        }
    ranked = [d for d in docs if d.get("visibility", "public") == "public" and not d.get("revoked")]
    if not ranked:
        return {
            "abstain": True,
            "reason": "authorized corpus empty after revoke/scope",
            "hits": [],
            "backend": "none",
        }
    return {
        "abstain": False,
        "reason": None,
        "hits": ranked[:12],
        "backend": "SOFTWARE-sparse",
        "public_cap": 12,
    }


def decide(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Hatun-shaped isolation. Retrieved 'approved' is not ALLOW."""
    action = str(proposal.get("action") or "")
    source = str(proposal.get("source") or "")
    if action.upper() == "ALLOW" or proposal.get("retrieved_approved") is True:
        return {
            "decision": "BLOCKED",
            "honesty": "SOFTWARE",
            "reason": "F22 advisory isolation — a retrieved instruction is not Hatun ALLOW",
            "conjecture": CONJECTURE_1,
            "trust": clamp_trust(proposal.get("trust", 1.0)),
        }
    if source in {"receipt", "formula", "model", "http"}:
        return {
            "decision": "BLOCKED",
            "honesty": "SOFTWARE",
            "reason": f"{source} cannot grant consequential execution",
            "conjecture": CONJECTURE_1,
            "trust": clamp_trust(proposal.get("trust", TRUST_CEILING)),
        }
    return {
        "decision": "HOLD",
        "honesty": "HOLD",
        "reason": "human Hatun review required",
        "conjecture": CONJECTURE_1,
        "trust": clamp_trust(proposal.get("trust", TRUST_CEILING)),
    }


def frontier_status(children: Mapping[str, str] | None = None) -> dict[str, Any]:
    return {
        "schema": "szl.frontier_gate/v1",
        "agi_claim": False,
        "lambda": "Conjecture 1",
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
        "estate_gate": estate_gate(children),
        "compiled_kernel": {
            "honesty": "UNAVAILABLE",
            "v1": "missing",
            "cutoff": KERNEL_CUTOFF,
            "overdue": True,
        },
        "locked_formula_ids": list(LOCKED_FORMULAS),
        "note": "This module is SOFTWARE. It does not load compiled kernels, mint signatures, or publish Spaces.",
    }


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    """Additive FastAPI routes. Missing FastAPI is a no-op, not a crash."""
    report = {"ok": False, "registered": []}
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        return report

    base = f"/api/{ns}/v1/frontier"

    @app.get(f"{base}/status")
    async def _status():
        body = frontier_status(
            {
                "console_journey": "NOT_EXECUTED",
                "lyte_runtime": "NOT_EXECUTED",
                "kernel_v1": "UNAVAILABLE",
                "brain_private": "UNAVAILABLE",
                "minicpm": "EXECUTED_FAIL",
            }
        )
        return JSONResponse(body)

    @app.post(f"{base}/decide")
    async def _decide(payload: dict[str, Any] | None = None):
        return JSONResponse(decide(payload or {}))

    @app.post(f"{base}/retrieve")
    async def _retrieve(payload: dict[str, Any] | None = None):
        data = payload or {}
        return JSONResponse(
            retrieve_or_abstain(
                str(data.get("query") or ""),
                list(data.get("passages") or []),
                tenant=str(data.get("tenant") or "public"),
            )
        )

    report["ok"] = True
    report["registered"] = [f"{base}/status", f"{base}/decide", f"{base}/retrieve"]
    return report


if __name__ == "__main__":
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, ok))
        print(("PASS" if ok else "FAIL"), name)

    t = clamp_trust(1.0)
    check("clamp_1.0", t["admitted"] == TRUST_CEILING and t["honesty"] == "HOLD")
    check("zero_stays_zero", bind_count(0) == {"kind": "zero", "value": 0})
    check("http_200_not_live", never_live_from_http(200)["live"] is False)
    g = estate_gate({"core": "NOT_EXECUTED", "proof": "EXECUTED_PASS"})
    check("no_all_done_over_skip", g["all_done"] is False and g["verdict"] == "HOLD")
    r = retrieve_or_abstain("What is my private memory?", [{"visibility": "public"}])
    check("private_abstain", r["abstain"] is True and r["reason"] == "PRIVATE_SOURCE_NOT_BOUND")
    d = decide({"action": "ALLOW", "retrieved_approved": True, "trust": 1.0})
    check("allow_blocked", d["decision"] == "BLOCKED")
    s = frontier_status()
    check("not_agi", s["agi_claim"] is False)
    failed = [n for n, ok in checks if not ok]
    print({"ok": not failed, "checks": len(checks), "failed": failed})
    raise SystemExit(1 if failed else 0)
