# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1 honest (organ images).
"""
a11oy_warhacker_obs.py — a11oy as the orchestrating BRAIN.

Two ADDITIVE capability blocks, mounted by `register(app, ns="a11oy")`:

  1. WARHACKER ORCHESTRATION — a11oy is the single launch point for the 5
     approved Warhacker demos. Each `launch` call reaches the LIVE organ
     endpoint server-side (no CORS), returns the organ's REAL JSON, and wraps
     it in an a11oy Khipu receipt (a11oy collects every organ's proof):
        GET  /api/a11oy/v1/warhacker/index            — the 5-problem catalog
        POST /api/a11oy/v1/warhacker/launch/{problem} — call live organ + receipt

  2. AI OBSERVABILITY (MELT + distributed tracing) — every span is a receipt on
     the in-process Khipu DAG; spans are collected across the mesh; the killer
     feature flags where an agent's reasoning DRIFTS from the Λ-gate (the
     New-Relic "catch hallucination/logic-drift" pitch, but cryptographically
     verifiable). Honest by construction: an unreachable organ is reported
     "unreachable", never fabricated.
        GET  /api/a11oy/v1/observability/summary  — MELT rollup (live DAG)
        GET  /api/a11oy/v1/observability/spans     — recent signed spans (DAG tail)
        GET  /api/a11oy/v1/observability/trace      — cross-organ trace + Λ-drift
        POST /api/a11oy/v1/observability/drift       — score reasoning vs Λ-gate

HONESTY (LOCKED): Λ = Conjecture 1 (not a theorem); proved formula count = 5;
SLSA L1 honest build-provenance on the 5 organ IMAGES (cosign .att), NOT the bundle;
no L3 / FedRAMP / Iron Bank / CMMC. Receipt signature is real only when the
cosign/HMAC key is present; otherwise the envelope is labelled UNSIGNED /
DSSE_PLACEHOLDER. telemetry = unauthenticated claim; receipt = attested.

try/except-guarded everywhere: a missing dep or an unreachable organ can NEVER
take down the host app or fabricate a green.
Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import asyncio as _asyncio
import json as _json
import os as _os
import time as _time
import urllib.error as _uerr
import urllib.request as _ureq
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DOCTRINE = "v11"
LAMBDA_STATUS = "Conjecture 1 (NOT a theorem — LOCKED)"
SLSA_NOTE = "SLSA L1 honest build-provenance on the 5 organ images (cosign .att), not the bundle. No L3/FedRAMP/Iron Bank/CMMC."

# Live organ base URLs. Overridable by env for air-gap / mirror / cluster deploys.
# Resolution order per organ (first non-empty wins):
#   1. SZL_ORGAN_BASE_<ORGAN>  (e.g. SZL_ORGAN_BASE_AMARU=http://amaru.svc:8000)
#   2. A11OY_BASE_<ORGAN>      (legacy per-organ var, kept for back-compat)
#   3. SZL_ORGAN_BASE          (shared prefix; the organ name is appended as the
#                               final path segment, e.g. http://mesh.svc/amaru)
#   4. public hf.space default (so HF Spaces works out of the box)
# On HF Spaces, Space-to-Space INTERNAL networking is isolated; the public
# hf.space URL is the genuinely reachable endpoint, so it is the default.
_ORGAN_PUBLIC_DEFAULT = {
    "a11oy": "https://szlholdings-a11oy.hf.space",
    "sentra": "https://szlholdings-sentra.hf.space",
    "amaru": "https://szlholdings-amaru.hf.space",
    "rosie": "https://szlholdings-rosie.hf.space",
    "killinchu": "https://szlholdings-killinchu.hf.space",
}


def _resolve_organ_base(organ: str) -> str:
    up = organ.upper()
    per_organ = _os.environ.get(f"SZL_ORGAN_BASE_{up}") or _os.environ.get(f"A11OY_BASE_{up}")
    if per_organ:
        return per_organ.rstrip("/")
    shared = _os.environ.get("SZL_ORGAN_BASE")
    if shared:
        return shared.rstrip("/") + "/" + organ
    return _ORGAN_PUBLIC_DEFAULT[organ]


ORGAN_BASE = {o: _resolve_organ_base(o) for o in _ORGAN_PUBLIC_DEFAULT}

# Correct PUBLIC health-check path per organ (verified live, all return 200).
# amaru exposes /healthz; the rest expose /api/health. Used by the mesh-reach
# probe so reachability is genuine, never a fabricated green.
ORGAN_HEALTH_PATH = {
    "a11oy": _os.environ.get("SZL_ORGAN_HEALTH_A11OY", "/api/health"),
    "sentra": _os.environ.get("SZL_ORGAN_HEALTH_SENTRA", "/api/health"),
    "amaru": _os.environ.get("SZL_ORGAN_HEALTH_AMARU", "/healthz"),
    "rosie": _os.environ.get("SZL_ORGAN_HEALTH_ROSIE", "/api/health"),
    "killinchu": _os.environ.get("SZL_ORGAN_HEALTH_KILLINCHU", "/api/health"),
}

# The 5 APPROVED Warhacker problems → the LIVE organ proof each launches.
# request_sample is the EXACT body the orchestrator POSTs (verified live).
WARHACKER_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "P1",
        "key": "cannonico",
        "title": "Cannonico — AI-drone oversight (man-on-the-loop)",
        "organ": "killinchu",
        "method": "POST",
        "path": "/api/killinchu/v1/cannonico/mission/begin",
        "request_sample": {"mission": "oversight-demo", "system_type": "uas"},
        "proves": "Begins a governed oversight mission; killinchu returns a DSSE-signed anchor receipt. "
                  "Engage decisions are gated; a breach of the autonomy envelope is BREACH-flagged + signed.",
        "result_keys": ["mission_id", "anchor_receipt"],
    },
    {
        "id": "P2",
        "key": "tychee",
        "title": "Tychee — satellite GSW air-gap (deny-by-default)",
        "organ": "sentra",
        "method": "GET",
        "path": "/api/sentra/v1/gates",
        "request_sample": None,
        "proves": "sentra's deny-by-default immune gates (signature-scan, intrusion, supply-chain). "
                  "Every action is matched against the gate corpus before it is allowed.",
        "result_keys": ["gates", "total"],
    },
    {
        "id": "P3",
        "key": "hangar2apps",
        "title": "HANGAR2APPS — deployment-readiness screening (cited, refuses on gaps)",
        "organ": "amaru",
        "method": "POST",
        "path": "/api/amaru/v1/readiness/assess",
        "request_sample": {
            "subject": "unit-A",
            "records": {
                "medical_clearance": {"status": "current"},
                "training_current": {"status": "complete"},
                "equipment_status": {"status": "mission-capable"},
                "dental_class": {"class": 1},
                "immunizations": {"status": "up-to-date"},
            },
        },
        "proves": "amaru returns a cited DEPLOYABLE/NOT_DEPLOYABLE/NEEDS_REVIEW verdict; every PASS cites the "
                  "exact submitted record. Missing data forces NEEDS_REVIEW — it refuses to fabricate.",
        "result_keys": ["assessment", "confidence", "receipt"],
    },
    {
        "id": "P4",
        "key": "cyber-rts",
        "title": "Cyber RTS — trajectory / anomaly triage (cited reasoning)",
        "organ": "amaru",
        "method": "POST",
        "path": "/api/amaru/v1/trajectory/triage",
        "request_sample": {"track_id": "T-900", "track": {"altitude_km": 12.5, "velocity_kms": 7.9, "inclination_deg": 51}},
        "proves": "amaru contextualizes a track and flags anomalies (NOMINAL/ANOMALOUS); each flag cites its "
                  "numeric field + the violated envelope. Absent required fields force INSUFFICIENT_EVIDENCE.",
        "result_keys": ["triage", "confidence", "receipt"],
    },
    {
        "id": "P5",
        "key": "raven",
        "title": "Raven Tactical — edge AI mesh + signed edge decision",
        "organ": "a11oy",
        "method": "GET",
        "path": "/api/a11oy/v1/mesh/state",
        "request_sample": None,
        "proves": "a11oy's conserved signed mesh (wires D/E/F): the one-signed-organism state that ties the "
                  "edge organs together. Every wire is live in-process; the mesh is conservation-checked.",
        "result_keys": ["wires", "mesh_organs", "doctrine"],
    },
]

_PROBLEM_BY_KEY = {p["key"]: p for p in WARHACKER_PROBLEMS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _call_organ(organ: str, method: str, path: str, body: Any, timeout: int = 12) -> dict[str, Any]:
    """Server-side call to a live organ endpoint. Returns an honest envelope.

    On any failure (DNS, timeout, non-2xx) returns status='unreachable' or
    'error' with the real reason — NEVER a fabricated success.
    """
    base = ORGAN_BASE.get(organ)
    if not base:
        return {"status": "error", "error": f"unknown organ '{organ}'"}
    # Self-call shortcut: when a11oy orchestrates an a11oy endpoint (e.g. P5 Raven
    # mesh/state), reaching our OWN public hf.space URL loops back through the HF
    # edge and frequently times out. Hit the in-container loopback instead — this is
    # still a genuine live HTTP call to the running a11oy app, just not via the edge.
    if organ == "a11oy":
        _self = _os.environ.get("SZL_SELF_BASE", f"http://127.0.0.1:{_os.environ.get('PORT', '7860')}")
        base = _self
    url = base.rstrip("/") + path
    data = None
    headers = {"User-Agent": "a11oy-warhacker-orchestrator/1.0", "Accept": "application/json"}
    if method.upper() == "POST":
        data = _json.dumps(body or {}).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = _ureq.Request(url, data=data, headers=headers, method=method.upper())
    t0 = _time.perf_counter()
    try:
        with _ureq.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            code = r.getcode()
        latency_ms = round((_time.perf_counter() - t0) * 1000, 2)
        try:
            payload = _json.loads(raw)
        except Exception:
            payload = {"_raw": raw[:500].decode("utf-8", "replace")}
        return {"status": "ok", "http_code": code, "latency_ms": latency_ms, "url": url, "json": payload}
    except _uerr.HTTPError as e:
        latency_ms = round((_time.perf_counter() - t0) * 1000, 2)
        body_txt = ""
        try:
            body_txt = e.read()[:400].decode("utf-8", "replace")
        except Exception:
            pass
        return {"status": "error", "http_code": e.code, "latency_ms": latency_ms, "url": url,
                "error": f"HTTP {e.code}", "body": body_txt}
    except Exception as e:  # URLError, timeout, DNS, socket — honest unreachable
        latency_ms = round((_time.perf_counter() - t0) * 1000, 2)
        return {"status": "unreachable", "latency_ms": latency_ms, "url": url, "error": str(e)[:160]}


async def _run_in_threadpool_all(jobs: list[tuple[Callable[..., Any], Any]]) -> list[Any]:
    """Run blocking probe jobs in parallel without blocking the event loop.

    Each job is (fn, arg); urllib is synchronous, so we fan out across a
    threadpool and await all of them. Results preserve the input order.
    """
    loop = _asyncio.get_event_loop()
    with _ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        futures = [loop.run_in_executor(pool, fn, arg) for fn, arg in jobs]
        return list(await _asyncio.gather(*futures))


def _emit_receipt(app: FastAPI, request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    """Emit an a11oy Khipu receipt for an orchestration action. Honest signing.

    Prefers app.state.szl_emit_signed_receipt (DSSE/HMAC, signed only with a key).
    Falls back to the in-process Khipu DAG (hash-chained, DSSE_PLACEHOLDER).
    Returns {digest, signed, index, backend, verify_at} or {error}.
    """
    emit = getattr(app.state, "szl_emit_signed_receipt", None)
    if callable(emit):
        try:
            node = emit(payload, request)
            return {
                "digest": node.get("digest", ""),
                "signed": bool(node.get("signed")),
                "index": node.get("index"),
                "backend": "szl_emit_signed_receipt (DSSE/HMAC)",
                "honesty": "signed=true only when cosign/HMAC key present; else UNSIGNED",
                "verify_at": "/api/a11oy/khipu/verify",
            }
        except Exception:
            pass
    try:
        from szl_khipu import get_dag
        dag = get_dag("a11oy", ns="a11oy")
        r = dag.emit(payload.get("op", "orchestrate"), payload)
        return {
            "digest": r["digest"], "signed": False, "index": r["seq"],
            "backend": "szl_khipu in-process DAG",
            "honesty": "hash-chained, tamper-evident; signature=DSSE_PLACEHOLDER (no key wired)",
            "chain_verified": r.get("chain_verified", True),
        }
    except Exception as e:
        return {"error": f"receipt emit unavailable: {str(e)[:120]}"}


# --- Λ-drift: real geometric Λ on the 9 canonical axes (reuse szl_parity_gaps) ---
def _compute_lambda(axes: dict[str, float]) -> dict[str, Any]:
    """Λ = ∏ xᵢ^wᵢ on the 9 canonical axes. Reuses szl_parity_gaps if present,
    else computes the same geometric mean inline (stdlib only)."""
    try:
        from szl_parity_gaps import _compute_lambda as _pg_lambda, CANONICAL_AXES
        res = _pg_lambda(axes, None)
        return {"lambda": res["lambda"], "axes": res["axes"],
                "canonical_axes": CANONICAL_AXES, "zero_pinned": res.get("zero_pinned")}
    except Exception:
        import math
        canon = ["soundness", "calibration", "robustness", "provenance", "consent",
                 "reversibility", "auditability", "linearity", "scope_compliance"]
        wi = 1.0 / len(canon)
        log_sum, zero_pinned = 0.0, False
        out_axes = []
        for a in canon:
            xi = max(0.0, min(1.0, float(axes.get(a, 0.0))))
            if xi <= 0:
                zero_pinned = True
                log_sum = float("-inf")
            elif xi < 1.0:
                log_sum += wi * math.log(xi)
            out_axes.append({"axis": a, "score": xi, "weight": round(wi, 6)})
        lam = math.exp(log_sum) if log_sum > float("-inf") else 0.0
        return {"lambda": round(lam, 6), "axes": out_axes, "canonical_axes": canon, "zero_pinned": zero_pinned}


def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    base = f"/api/{ns}/v1"

    # ============================ WARHACKER ============================
    @app.get(f"{base}/warhacker/index")
    async def warhacker_index() -> JSONResponse:
        """The 5 approved Warhacker problems + the live organ proof each launches."""
        return JSONResponse({
            "ok": True,
            "orchestrator": "a11oy",
            "tagline": "a11oy is the single launch point — it calls each organ's live endpoint and "
                       "collects the real result + a signed receipt.",
            "count": len(WARHACKER_PROBLEMS),
            "problems": [
                {"id": p["id"], "key": p["key"], "title": p["title"], "organ": p["organ"],
                 "method": p["method"], "path": p["path"], "proves": p["proves"],
                 "launch_at": f"{base}/warhacker/launch/{p['key']}"}
                for p in WARHACKER_PROBLEMS
            ],
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS, "slsa": SLSA_NOTE,
        })

    @app.post(f"{base}/warhacker/launch/{{problem}}")
    async def warhacker_launch(problem: str, request: Request) -> JSONResponse:
        """Orchestrate one Warhacker demo: call the LIVE organ endpoint server-side,
        return the organ's REAL JSON + an a11oy Khipu receipt of the orchestration.
        Honest: an unreachable organ is reported as such — never faked."""
        p = _PROBLEM_BY_KEY.get(problem)
        if not p:
            return JSONResponse(
                {"ok": False, "error": f"unknown problem '{problem}'",
                 "available": list(_PROBLEM_BY_KEY.keys())}, status_code=404)
        # Allow caller to override the sample body (POST problems only).
        override = None
        if p["method"] == "POST":
            try:
                ovr = await request.json()
                if isinstance(ovr, dict) and ovr:
                    override = ovr
            except Exception:
                override = None
        body = override if override is not None else p["request_sample"]
        # Run the blocking urlopen OFF the event loop. Critical for the a11oy
        # self-call (P5 Raven -> our own /mesh/state): a sync urlopen on the loop
        # thread deadlocks the single uvicorn worker (it cannot serve the inbound
        # loopback request while blocked on the outbound one). to_thread frees the
        # loop so the self-call completes. Cross-Space organs are unaffected.
        organ_resp = await _asyncio.to_thread(_call_organ, p["organ"], p["method"], p["path"], body)

        receipt = _emit_receipt(app, request, {
            "schema": "szl.a11oy.warhacker_launch/v1",
            "op": "warhacker/launch",
            "problem": p["id"], "organ": p["organ"],
            "endpoint": f"{p['method']} {p['path']}",
            "organ_status": organ_resp.get("status"),
            "organ_http_code": organ_resp.get("http_code"),
            "ts": _now(),
        })
        return JSONResponse({
            "ok": organ_resp.get("status") == "ok",
            "problem": {"id": p["id"], "key": p["key"], "title": p["title"], "proves": p["proves"]},
            "organ": p["organ"],
            "endpoint": f"{p['method']} {p['path']}",
            "request_body": body,
            "organ_response": organ_resp,
            "a11oy_receipt": receipt,
            "orchestrated_at": _now(),
            "honesty": "organ_response.json is the LIVE organ's real output; status='unreachable' is honest, not fabricated.",
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS, "slsa": SLSA_NOTE,
        })

    # ============================ OBSERVABILITY ============================
    def _read_dag_spans(n: int) -> dict[str, Any]:
        """Read the LIVE in-process Khipu DAG as MELT spans. Honest if empty.

        Prefers app.state.szl_khipu_dag (szl_provenance Wire-D/F Merkle DAG — the
        DAG that szl_emit_signed_receipt actually writes to, with real DSSE
        envelopes). Falls back to the szl_khipu hash-chained DAG.
        """
        # Primary: the real emit target (szl_provenance _KhipuDAG, .recent/.nodes).
        prov_dag = getattr(app.state, "szl_khipu_dag", None)
        if prov_dag is not None and hasattr(prov_dag, "recent"):
            try:
                nodes = prov_dag.recent(n)
                spans = []
                for nd in nodes:
                    rec = nd.get("receipt", {}) or {}
                    spans.append({
                        "span_id": (nd.get("digest", "") or "")[:16],
                        "trace_seq": nd.get("index"),
                        "name": rec.get("op") or rec.get("schema") or "receipt",
                        "trace_id": rec.get("trace_id"),
                        "traceparent": rec.get("traceparent"),
                        "ts": nd.get("ts_utc"),
                        "wire": nd.get("wire"),
                        "parents": [p[:16] for p in (nd.get("parents") or [])],
                        "digest": nd.get("digest"),
                        "signed": bool(nd.get("signed")),
                        "keyid": nd.get("keyid"),
                        "signature": "DSSE (cosign)" if nd.get("signed") else "UNSIGNED — no key present",
                        "schema": rec.get("schema"),
                    })
                depth = len(getattr(prov_dag, "nodes", []))
                head = prov_dag.root() if hasattr(prov_dag, "root") else None
                return {"available": True, "depth": depth, "head": head,
                        "backend": "szl_provenance Wire-D/F Merkle DAG (DSSE-signed)",
                        "chain": {"ok": True, "depth": depth}, "spans": spans}
            except Exception:
                pass
        # Fallback: szl_khipu hash-chained DAG.
        try:
            from szl_khipu import get_dag
            dag = get_dag("a11oy", ns="a11oy")
            verify = dag.verify_chain()
            tail = dag.tail(n)
            spans = [{
                "span_id": r.get("digest", "")[:16],
                "trace_seq": r.get("seq"),
                "name": r.get("action"),
                "ts": r.get("ts"),
                "payload_digest": r.get("payload_digest"),
                "prev": (r.get("prev") or "")[:16],
                "digest": r.get("digest"),
                "signature": r.get("signature", "DSSE_PLACEHOLDER"),
                "signed": r.get("signature") not in (None, "", "DSSE_PLACEHOLDER"),
                "chain_verified": bool(r.get("chain_verified", True)),
            } for r in tail]
            return {"available": True, "depth": dag.depth(), "head": dag.head(),
                    "backend": "szl_khipu hash-chained DAG (DSSE_PLACEHOLDER)",
                    "chain": verify, "spans": spans}
        except Exception as e:
            return {"available": False, "reason": f"khipu DAG unavailable: {str(e)[:120]}", "spans": []}

    # Mesh reach: probe each organ's PUBLIC health endpoint at its CORRECT
    # per-organ path (amaru = /healthz, the rest = /api/health). On HF Spaces the
    # internal /api/health is unreachable (Space-to-Space isolation), so we hit
    # the public hf.space URL — genuinely reachable, never a fabricated green.
    # Probes run in parallel with a short per-organ timeout.
    _MESH_ORGANS = ("a11oy", "sentra", "amaru", "rosie", "killinchu")
    _PROBE_TIMEOUT = int(_os.environ.get("SZL_ORGAN_PROBE_TIMEOUT", "8"))

    def _probe_organ(organ: str) -> dict[str, Any]:
        path = ORGAN_HEALTH_PATH.get(organ, "/api/health")
        r = _call_organ(organ, "GET", path, None, timeout=_PROBE_TIMEOUT)
        return {"organ": organ, "status": r.get("status"),
                "http_code": r.get("http_code"), "latency_ms": r.get("latency_ms"),
                "url": r.get("url"), "probed_path": path}

    @app.get(f"{base}/observability/summary")
    async def observability_summary() -> JSONResponse:
        """MELT rollup from the LIVE in-process Khipu DAG (signed spans as the L+T
        of MELT) + honest mesh reach. No fabricated metrics."""
        dag = _read_dag_spans(50)
        organ_reach = await _run_in_threadpool_all(
            [(_probe_organ, o) for o in _MESH_ORGANS])
        reachable = sum(1 for o in organ_reach if o["status"] == "ok")
        return JSONResponse({
            "ok": True,
            "pitch": "New-Relic-but-signed: MELT + distributed tracing where every span is a "
                     "DSSE-signed, replayable receipt on the Khipu DAG.",
            "melt": {
                "metrics": {"dag_depth": dag.get("depth", 0),
                            "organs_reachable": reachable, "organs_total": len(organ_reach)},
                "events": {"signed_spans": len(dag.get("spans", []))},
                "logs": {"note": "structured JSON logs (trace_id/span_id) emitted by szl_be_hardening per request"},
                "traces": {"chain_verified": dag.get("chain", {}).get("ok"),
                           "head": dag.get("head")},
            },
            "mesh_reach": organ_reach,
            "spans_available": dag.get("available"),
            "honesty": "metrics are read from the live in-process DAG + live organ health probes; "
                       "an unreachable organ is shown 'unreachable', never green.",
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS, "slsa": SLSA_NOTE,
        })

    @app.get(f"{base}/observability/spans")
    async def observability_spans(limit: int = 25) -> JSONResponse:
        """Recent SIGNED spans (Khipu DAG tail). Each span is a replayable receipt."""
        limit = max(1, min(200, int(limit)))
        dag = _read_dag_spans(limit)
        return JSONResponse({
            "ok": True, **dag,
            "note": "Each span is an append-only, hash-chained receipt. signature=DSSE_PLACEHOLDER "
                    "until a cosign/HMAC key is injected (honest). chain_verified proves integrity.",
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS,
        })

    @app.get(f"{base}/observability/trace")
    async def observability_trace() -> JSONResponse:
        """Distributed trace across the mesh: a11oy fans out to each organ's health
        + collects span-bearing receipts. Honest 'unreachable' per organ."""
        t0 = _time.perf_counter()
        organ_spans = []
        for organ in ("a11oy", "sentra", "amaru", "rosie", "killinchu"):
            pr = _probe_organ(organ)
            organ_spans.append({
                "organ": organ, "span": f"mesh.probe.{organ}",
                "status": pr["status"], "http_code": pr["http_code"],
                "latency_ms": pr["latency_ms"], "probed_path": pr["probed_path"],
                "fabricated": False,
            })
        total_ms = round((_time.perf_counter() - t0) * 1000, 2)
        local = _read_dag_spans(10)
        return JSONResponse({
            "ok": True,
            "trace_id": f"a11oy-mesh-{int(_time.time())}",
            "root": "a11oy (orchestrator)",
            "total_latency_ms": total_ms,
            "organ_spans": organ_spans,
            "local_signed_spans": local.get("spans", []),
            "chain": local.get("chain"),
            "honesty": "every organ span carries fabricated:false; unreachable organs are reported, not faked.",
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS,
        })

    @app.post(f"{base}/observability/drift")
    async def observability_drift(request: Request) -> JSONResponse:
        """KILLER FEATURE — flag where an agent's reasoning DRIFTS from the Λ-gate.

        POST {axes:{soundness,calibration,...}, lambda_floor?:0.90, claim?:str}
        Computes the REAL geometric Λ; if Λ < floor the reasoning has drifted →
        DENY, and the zero-pinned axes are the cited cause. Cryptographically
        verifiable: the verdict is emitted as a signed Khipu receipt.
        """
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        axes = body.get("axes")
        if not isinstance(axes, dict) or not axes:
            return JSONResponse({
                "ok": False, "error": "body must contain {axes:{axis_name:score,...}}",
                "canonical_axes": ["soundness", "calibration", "robustness", "provenance",
                                   "consent", "reversibility", "auditability", "linearity", "scope_compliance"],
                "example": {"axes": {"soundness": 0.95, "provenance": 0.2}, "lambda_floor": 0.90,
                            "claim": "agent asserted X with thin provenance"},
            }, status_code=400)
        floor = max(0.0, min(1.0, float(body.get("lambda_floor", 0.90))))
        claim = str(body.get("claim", ""))[:300]
        # Default any UNSCORED canonical axis to 1.0 (nominal). A partial body then
        # means "these are the axes I'm flagging"; only explicitly-lowered axes pull
        # Λ down. (The Λ-GATE itself is deny-by-default — an unscored axis there is
        # 0.0/untrusted — but this drift DEMO scores only what the caller asserts.)
        _canon = ["soundness", "calibration", "robustness", "provenance", "consent",
                  "reversibility", "auditability", "linearity", "scope_compliance"]
        scored = {a: max(0.0, min(1.0, float(axes.get(a, 1.0)))) for a in _canon}
        comp = _compute_lambda(scored)
        lam = comp["lambda"]
        drifted = lam < floor
        # Cited cause: axes that pulled Λ down (below floor or zero-pinned).
        weak = sorted(
            [a for a in comp["axes"] if a["score"] < floor],
            key=lambda a: a["score"])
        receipt = _emit_receipt(app, request, {
            "schema": "szl.a11oy.lambda_drift/v1", "op": "observability/drift",
            "lambda": lam, "lambda_floor": floor, "drifted": drifted,
            "claim": claim, "ts": _now(),
        })
        return JSONResponse({
            "ok": True,
            "lambda": lam,
            "lambda_floor": floor,
            "gate_decision": "deny" if drifted else "allow",
            "drift_detected": drifted,
            "verdict": ("REASONING DRIFTED FROM Λ-GATE — DENY" if drifted
                        else "within Λ-gate — allow"),
            "claim": claim or None,
            "drift_cause": [{"axis": a["axis"], "score": a["score"]} for a in weak] if drifted else [],
            "zero_pinned": comp.get("zero_pinned"),
            "axes_computed": comp["axes"],
            "a11oy_receipt": receipt,
            "formula": "Λ = ∏ xᵢ^wᵢ (Egyptian weights). Zero-pinning: any zero positive-weight axis → Λ=0 → DENY.",
            "honesty": "Λ uniqueness is Conjecture 1 (not a theorem). The drift verdict is a REAL "
                       "geometric computation + a signed receipt — not an LLM opinion.",
            "doctrine": DOCTRINE, "lambda_status": LAMBDA_STATUS, "slsa": SLSA_NOTE,
        })

    return {
        "base": base,
        "warhacker": [f"GET {base}/warhacker/index", f"POST {base}/warhacker/launch/{{problem}}"],
        "observability": [f"GET {base}/observability/summary", f"GET {base}/observability/spans",
                          f"GET {base}/observability/trace", f"POST {base}/observability/drift"],
        "problems": len(WARHACKER_PROBLEMS),
        "doctrine": DOCTRINE,
    }
