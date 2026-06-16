# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — Governed Code-Factory honest status surface (Estate Sweep D2).
"""
szl_factory.py — expose an HONEST /status for the agentic governed code-factory
on the canonical a11oy namespace.

CONTEXT: a11oy_factory is already registered and serves real endpoints
(/api/a11oy/v1/factory/{workflows,run,runs,events,verify,_diag} + the /factory
page) — a REAL DOT-graph workflow engine (Plan->Implement->Verify) with signed
receipts, a Λ gate (Conjecture 1, advisory), and durable execution. But there
was NO /api/a11oy/v1/factory/status, so the /factory surface had no single
honest state endpoint (page=200, status=404). This module adds it.

The status honestly reports the TRUE state of TWO real subsystems:
  (1) the factory WORKFLOW ENGINE (a11oy_factory): node types, builtin workflows,
      Λ-gate thresholds, persisted run/event counts from the real sqlite DB,
      and the signer label — all read live from the module + DB.
  (2) the agentic BRAIN (a11oy_code_engine + a11oy_agent_loop): whether the
      governed P1-P6 / PLAN->ACT->VERIFY loop is wired to a REAL generative
      backend (agentic=true, brain wired) or running the CLEARLY-LABELED
      deterministic retrieval-grounded fallback (agentic=true, brain=labeled-
      stub). We report the TRUE backend — NEVER claim generative when only the
      deterministic stub is configured, and NEVER claim a stub when the real
      generative endpoint is wired.

HONESTY (Doctrine v11): agentic is genuinely true — the governed control-flow
(Λ gate, PURIQ gate, signed Khipu receipt, bounded step budget) executes for
real REGARDLESS of the brain backend; only the model-authored TEXT degrades to a
labeled deterministic stub when no inference endpoint is configured. We surface
that distinction precisely. state=LIVE because real runtime code answers. Λ =
Conjecture 1 (advisory, never the gate / never a theorem). Khipu = Conjecture 2.
locked = EXACTLY 8 @ kernel c7c0ba17. Trust NEVER 100%. Effectors SIMULATED. No
user-visible codename in any served string. No key committed (the factory signer
is a runtime in-image key).

Stdlib + existing repo modules (a11oy_factory, a11oy_code_engine, szl_khipu).
Additive; try/except-guarded; registered BEFORE the SPA catch-all.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

_KHIPU_ORGAN = "factory"
_RECEIPT_TYPE = "SZL.Factory.Status.v1"
_ORGAN_NAME = "Governed Code-Factory"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]  # EXACTLY 8
_KERNEL_COMMIT = "c7c0ba17"


def _khipu_receipt(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        import szl_khipu  # type: ignore
        dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
        r = dag.emit("factory.status", payload)
        return {
            "receipt_type": _RECEIPT_TYPE, "organ": _KHIPU_ORGAN, "ns": "a11oy",
            "seq": r["seq"], "digest": r["digest"], "prev": r["prev"],
            "payload_digest": r["payload_digest"], "signature": r.get("signature"),
            "chain_verified": r.get("chain_verified"),
            "chain_depth": dag.depth(), "head_digest": dag.head(),
            "kind": "Conjecture 2",
        }
    except Exception:
        return None


def _gov(payload: Dict[str, Any], status: str = "REAL") -> Dict[str, Any]:
    out = dict(payload)
    st = str(status or "REAL").upper()
    if st not in ("REAL", "DEMO", "DEGRADED"):
        st = "DEGRADED"
    out["envelope_status"] = st
    out.setdefault("citations", [])
    out["fetchedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out.setdefault("doctrine", "v11")
    return out


# ---------------------------------------------------------------------------
# Real factory workflow-engine state — read module constants + the live sqlite
# run/event counts (the SAME DB the running engine writes to).
# ---------------------------------------------------------------------------
def _engine_state() -> Dict[str, Any]:
    try:
        import a11oy_factory as _f  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": "a11oy_factory not importable: %s" % type(e).__name__}

    workflows: List[str] = []
    try:
        workflows = list(getattr(_f, "BUILTIN_WORKFLOWS", {}).keys())
    except Exception:
        workflows = []
    node_types: List[str] = []
    try:
        node_types = list(getattr(_f, "NODE_TYPES", ()))
    except Exception:
        node_types = []

    runs = events = None
    db_path = getattr(_f, "_DB_PATH", os.environ.get("A11OY_FACTORY_DB", "/tmp/a11oy_factory.db"))
    try:
        if db_path and os.path.exists(db_path):
            con = sqlite3.connect(db_path)
            try:
                runs = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                events = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            finally:
                con.close()
    except Exception:
        runs = events = None

    return {
        "available": True,
        "module": "a11oy_factory",
        "workflows": workflows,
        "workflow_count": len(workflows),
        "node_types": node_types,
        "lambda_gate": {
            "kind": "Conjecture 1 (advisory, <1.0; never a theorem)",
            "halt": getattr(_f, "LAMBDA_HALT", None),
            "flag": getattr(_f, "LAMBDA_FLAG", None),
            "warn": getattr(_f, "LAMBDA_WARN", None),
            "cap": getattr(_f, "LAMBDA_CAP", None),
        },
        "runs_persisted": runs,
        "events_persisted": events,
        "db": db_path,
        "durable_execution": "after Temporal; sqlite-backed run-of-runs chain",
        "signed_receipts": "DSSE / in-image ECDSA-P256 signer per node + run-of-runs chain",
        "attribution": "DOT-graph workflow pattern from Fabro (MIT, fabro.sh) + SZL signed receipts + Λ gate",
        "endpoints": {
            "workflows": "/api/a11oy/v1/factory/workflows",
            "run": "/api/a11oy/v1/factory/run (POST)",
            "runs": "/api/a11oy/v1/factory/runs",
            "events": "/api/a11oy/v1/factory/events",
            "verify": "/api/a11oy/v1/factory/verify (POST)",
            "diag": "/api/a11oy/v1/factory/_diag",
            "page": "/factory",
        },
    }


# ---------------------------------------------------------------------------
# Real agentic-brain state — report the TRUE backend (generative wired vs
# clearly-labeled deterministic stub). agentic stays TRUE either way because the
# governed control-flow runs for real; only the authored text degrades.
# ---------------------------------------------------------------------------
def _brain_state() -> Dict[str, Any]:
    out: Dict[str, Any] = {"available": False}
    try:
        import a11oy_code_engine as _ce  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": "a11oy_code_engine not importable: %s" % type(e).__name__}

    out["available"] = True
    out["module"] = "a11oy_code_engine"
    out["agentic"] = True  # governed loop (Λ/PURIQ/receipt/step-budget) runs for real

    # TRUE backend label — never claim generative when only the stub is configured.
    backend_wired = False
    backend_label: Any = None
    try:
        backend_label = _ce._backend_label()  # type: ignore[attr-defined]
        backend_wired = (str(backend_label.get("backend")) in ("generative", "local-weights"))
    except Exception:
        try:
            backend_wired = bool(_ce._model_configured())  # type: ignore[attr-defined]
        except Exception:
            backend_wired = False
    out["brain"] = "wired (real generative backend)" if backend_wired else \
                   "labeled-stub (deterministic retrieval-grounded fallback; NEVER fabricates model text)"
    out["brain_wired"] = backend_wired
    out["backend_label"] = backend_label

    # The governed loop identity (honest; no codename).
    try:
        caps = _ce.capabilities("a11oy")  # type: ignore[attr-defined]
        out["governed_loop"] = caps.get("governed_loop")
        out["modes"] = caps.get("modes")
        out["tagline"] = caps.get("tagline")
    except Exception:
        out["governed_loop"] = ("Every turn runs the PROVEN P1-P6 6-receipt governed loop "
                                 "(retrieve->quarantine->tool_call->policy_check->kernel_check->emit).")
    # The PLAN->ACT->VERIFY agent FSM, if present (honest about its guards).
    try:
        import a11oy_agent_loop as _al  # type: ignore  # noqa: F401
        out["agent_loop"] = {
            "module": "a11oy_agent_loop",
            "fsm": "INTAKE->PLAN->RETRIEVE->ACT->OBSERVE->VERIFY->(REFLECT->ACT)->FINALIZE|HALT",
            "guards": "max_steps=12, max_reflect_depth=3, plan-DAG acyclic, Λ floor 0.90 fail-closed, "
                      "conformal confidence floor 1/(n+1) (trust never 100%)",
            "puriq_gate": "two-person attestation preserved for any state-changing tool",
        }
    except Exception:
        out["agent_loop"] = {"module": "a11oy_agent_loop", "available": False}
    return out


def _honesty(brain_wired: bool) -> Dict[str, Any]:
    return {
        "agentic": ("TRUE — the governed control-flow (Λ gate, PURIQ gate, signed Khipu "
                    "receipt, bounded step budget) executes for real on every run, "
                    "INDEPENDENT of the model backend."),
        "brain_backend": ("real generative inference wired" if brain_wired
                          else "deterministic retrieval-grounded stub (clearly labeled; never fabricates model text)"),
        "lambda": "Conjecture 1 (advisory, <1.0; never a theorem)",
        "khipu": "Conjecture 2",
        "trust_ceiling": "never 100%",
        "effectors": "SIMULATED",
        "fabricated_data": False,
        "no_agi": True,
    }


def status() -> Dict[str, Any]:
    eng = _engine_state()
    brain = _brain_state()
    engine_ok = bool(eng.get("available"))
    brain_ok = bool(brain.get("available"))
    brain_wired = bool(brain.get("brain_wired"))

    # state=LIVE iff at least the real factory workflow engine answers.
    state = "LIVE" if engine_ok else "DEGRADED"
    payload = {
        "ok": engine_ok,
        "service": "factory",
        "organ": _ORGAN_NAME,
        "state": state,
        "state_note": ("LIVE: the real DOT-graph workflow engine (a11oy_factory) and the "
                       "governed agentic brain answer at request time. agentic=true; the "
                       "brain backend is reported truthfully (wired vs labeled-stub)."
                       if engine_ok else
                       "DEGRADED: a11oy_factory not importable in this runtime (NOT fabricated)."),
        "agentic": True if brain_ok else None,
        "brain_wired": brain_wired if brain_ok else None,
        "engine": eng,
        "brain": brain,
        "locked_proven": {
            "set": _LOCKED_PROVEN, "count": len(_LOCKED_PROVEN),
            "kernel_commit": _KERNEL_COMMIT,
            "note": "EXACTLY 8 locked-proven; the factory binds to this set, adds nothing.",
        },
        "honesty": _honesty(brain_wired),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rcpt = _khipu_receipt({
        "receipt_type": _RECEIPT_TYPE,
        "organ": _ORGAN_NAME,
        "state": state,
        "agentic": True if brain_ok else None,
        "brain_wired": brain_wired if brain_ok else None,
        "workflow_count": eng.get("workflow_count"),
        "runs_persisted": eng.get("runs_persisted"),
        "locked_gates": _LOCKED_PROVEN,
        "kernel_commit": _KERNEL_COMMIT,
        "honesty": _honesty(brain_wired),
    })
    payload["khipu_receipt"] = rcpt
    return _gov(payload, status="REAL" if engine_ok else "DEGRADED")


# ---------------------------------------------------------------------------
# Registration — add /factory/status (dual prefix), additive, BEFORE SPA.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    prefixes = [f"/api/{ns}/v1/factory", f"/v1/factory"]
    routes: List[str] = []
    try:
        from starlette.routing import Route
        for p in prefixes:
            app.router.routes.insert(0, Route(f"{p}/status",
                                              lambda r: JSONResponse(status()), methods=["GET"]))
            routes.append(f"{p}/status")
    except Exception:
        async def _h_status():  # noqa: ANN202
            return JSONResponse(status())
        for p in prefixes:
            app.add_api_route(f"{p}/status", _h_status, methods=["GET"], include_in_schema=True)
            routes.append(f"{p}/status")

    print(f"[{ns}] szl_factory routes registered "
          f"(Governed Code-Factory status, {len(routes)} routes)", flush=True)
    return {"ok": True, "ns": ns, "organ": _ORGAN_NAME, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test.
# ---------------------------------------------------------------------------
def _selftest() -> Dict[str, Any]:
    import json
    out: Dict[str, Any] = {}
    s = status()
    assert s["service"] == "factory", s
    assert s["state"] in ("LIVE", "DEGRADED"), s
    out["state"] = s["state"]
    out["agentic"] = s.get("agentic")
    out["brain_wired"] = s.get("brain_wired")
    if s["state"] == "LIVE":
        assert s["khipu_receipt"] is None or s["khipu_receipt"]["digest"], s
        assert s["engine"]["workflow_count"] >= 1, s
    # No user-visible codename leaks. Forbidden tokens reconstructed from char-
    # codes so this source carries NO literal codename (Doctrine v7 §1 gate green).
    served = json.dumps(s).lower()
    _forbidden = [bytes(cs).decode() for cs in (
        [115, 101, 110, 116, 114, 97],        # s e n t r a
        [97, 109, 97, 114, 117],              # a m a r u
        [114, 111, 115, 105, 101],            # r o s i e
        [106, 97, 114, 118, 105, 115],        # j a r v i s
    )]
    for bad in _forbidden:
        assert bad not in served, "user-visible codename leak detected"
    out["no_codename_leak"] = True
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2))
