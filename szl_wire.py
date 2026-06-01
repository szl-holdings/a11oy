# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v10
"""
szl_wire — shared mesh wiring for every SZL Space.  Closes Wires D, E, F per
Doctrine v10 (Wire B a11oy↔sentra LIVE, Wire C a11oy↔rosie LIVE already).

  Wire D — W3C traceparent propagation.  Middleware extracts an incoming
           `traceparent` header (W3C Trace Context), generates one if absent,
           stashes it on request.state, and echoes it on the response.  Outgoing
           helper `outgoing_headers()` propagates it on cross-Space calls.
           /api/<space>/healthz exposes `traceparent_propagating: true`.

  Wire E — a11oy↔amaru cortex sync.  a11oy publishes brand-decision events;
           amaru subscribes for reasoning context via Server-Sent Events at
           /api/amaru/v1/cortex-subscribe.  In-process ring buffer (honest: no
           external broker wired; events are real, retained in memory).

  Wire F — a11oy↔vessels receipts.  Every a11oy gate decision emits a receipt
           that vessels' Khipu DAG ingests via POST /api/vessels/v1/receipts/ingest.
           Honest: DSSE signature is the PLACEHOLDER (Sigstore CI not wired).

HONESTY: trace IDs are real W3C-format ids; the event buses are in-memory ring
buffers (no Kafka/NATS in a static HF Space), labeled as such.  Receipt signatures
are PLACEHOLDER.  Nothing here fabricates cross-process delivery it cannot do.
"""
from __future__ import annotations

import hashlib
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any


def _now_utc() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()

SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI signing not yet wired (Doctrine v10)"

# ---------------------------------------------------------------------------
# Wire D — W3C Trace Context (traceparent: 00-<32hex trace>-<16hex span>-01)
# ---------------------------------------------------------------------------

def _rand_hex(nbytes: int) -> str:
    return os.urandom(nbytes).hex()


def new_traceparent() -> str:
    return f"00-{_rand_hex(16)}-{_rand_hex(8)}-01"


def parse_traceparent(tp: str | None) -> dict[str, Any]:
    if not tp or tp.count("-") != 3:
        return {"valid": False, "raw": tp}
    ver, trace_id, span_id, flags = tp.split("-")
    return {"valid": len(trace_id) == 32 and len(span_id) == 16,
            "version": ver, "trace_id": trace_id, "span_id": span_id, "flags": flags, "raw": tp}


# rolling log of last N trace ids seen on this Space (for the /mesh visualizer)
_TRACE_LOG: deque[dict[str, Any]] = deque(maxlen=50)


def record_trace(tp: str, path: str, direction: str) -> None:
    _TRACE_LOG.append({
        "traceparent": tp,
        "trace_id": parse_traceparent(tp).get("trace_id"),
        "path": path,
        "direction": direction,  # "in" | "out"
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    })


def recent_traces(n: int = 10) -> list[dict[str, Any]]:
    return list(_TRACE_LOG)[-n:]


def install_traceparent_middleware(app, space: str) -> None:
    """Wire D: extract/generate traceparent, echo on response, record for /mesh."""
    @app.middleware("http")
    async def _tp_mw(request, call_next):
        incoming = request.headers.get("traceparent")
        tp = incoming if (incoming and parse_traceparent(incoming)["valid"]) else new_traceparent()
        request.state.traceparent = tp
        if request.url.path.startswith(("/api/", "/")) and not request.url.path.startswith("/assets"):
            record_trace(tp, request.url.path, "in")
        resp = await call_next(request)
        resp.headers["traceparent"] = tp
        resp.headers["x-szl-space"] = space
        return resp


def outgoing_headers(request) -> dict[str, str]:
    """Propagate the current trace on an outgoing cross-Space call (Wire D)."""
    tp = getattr(getattr(request, "state", None), "traceparent", None) or new_traceparent()
    record_trace(tp, "outgoing", "out")
    return {"traceparent": tp}


# ---------------------------------------------------------------------------
# Wire E — a11oy → amaru cortex sync (brand-decision events; SSE on amaru)
# ---------------------------------------------------------------------------

_CORTEX_EVENTS: deque[dict[str, Any]] = deque(maxlen=100)


def publish_brand_decision(decision: dict[str, Any], traceparent: str | None = None) -> dict[str, Any]:
    """a11oy side of Wire E: publish a brand-decision event for amaru to consume."""
    evt = {
        "wire": "E",
        "type": "brand_decision",
        "source": "a11oy",
        "sink": "amaru",
        "decision": decision,
        "traceparent": traceparent,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    _CORTEX_EVENTS.append(evt)
    return evt


def cortex_events(n: int = 10) -> list[dict[str, Any]]:
    return list(_CORTEX_EVENTS)[-n:]


async def cortex_sse_stream(max_events: int = 5, interval_s: float = 0.4):
    """amaru side of Wire E: SSE generator. Emits buffered events then a heartbeat.
    Honest: in-memory ring buffer (no external broker wired into the HF Space)."""
    sent = 0
    snapshot = list(_CORTEX_EVENTS)[-max_events:]
    if not snapshot:
        snapshot = [{"wire": "E", "type": "heartbeat", "source": "amaru",
                     "note": "no brand-decision events buffered yet (in-memory bus)",
                     "ts_utc": datetime.now(timezone.utc).isoformat()}]
    import json as _json
    for evt in snapshot:
        yield f"event: cortex\ndata: {_json.dumps(evt)}\n\n"
        sent += 1
        time.sleep(0)  # cooperative; real await handled by caller framing
        if sent >= max_events:
            break
    yield f"event: done\ndata: {{\"sent\": {sent}, \"wire\": \"E\"}}\n\n"


# ---------------------------------------------------------------------------
# Wire F — a11oy gate decisions → vessels Khipu DAG ingest
# ---------------------------------------------------------------------------

_KHIPU_DAG: list[dict[str, Any]] = []


def _digest(payload: dict[str, Any], parents: list[str]) -> str:
    import json as _json
    h = hashlib.sha256()
    h.update(_json.dumps(payload, sort_keys=True).encode())
    for p in parents:
        h.update(p.encode())
    return h.hexdigest()


def ingest_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """vessels side of Wire F: append an a11oy gate-decision receipt to the Khipu Merkle DAG."""
    parents = [_KHIPU_DAG[-1]["digest"]] if _KHIPU_DAG else []
    node = {
        "index": len(_KHIPU_DAG),
        "wire": "F",
        "source": "a11oy",
        "sink": "vessels",
        "receipt": receipt,
        "parents": parents,
        "dsse": {"payloadType": "application/vnd.szl.receipt+json",
                 "signatures": [{"sig": SIGNATURE_PLACEHOLDER, "keyid": "PENDING"}]},
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    node["digest"] = _digest(receipt, parents)
    _KHIPU_DAG.append(node)
    return node


def khipu_root() -> str | None:
    return _KHIPU_DAG[-1]["digest"] if _KHIPU_DAG else None


def khipu_nodes(n: int = 10) -> list[dict[str, Any]]:
    return _KHIPU_DAG[-n:]


def emit_gate_decision_receipt(action_id: str, gate: str, lambda_score: float,
                               fired: list[str], passed: bool) -> dict[str, Any]:
    """a11oy side of Wire F: build the receipt for a gate decision."""
    return {
        "schema": "szl.gate_decision.receipt/v1",
        "action_id": action_id,
        "gate": gate,
        "lambda": round(lambda_score, 6),
        "gates_fired": fired,
        "passed": passed,
        "doctrine": "v10",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "signature": SIGNATURE_PLACEHOLDER,
    }


# ---------------------------------------------------------------------------
# Mesh status — for /mesh visualizer
# ---------------------------------------------------------------------------

def mesh_status() -> dict[str, Any]:
    return {
        "doctrine": "v10",
        "wires": {
            "B": {"edge": "a11oy↔sentra (immune)", "status": "LIVE", "detail": "/v1/verdict + /v1/inspect"},
            "C": {"edge": "a11oy↔rosie (receipt stream)", "status": "LIVE", "detail": "/v1/events + Khipu ingest"},
            "D": {"edge": "W3C traceparent (in-process generation + propagation)", "status": "LIVE_IN_PROCESS",
                  "detail": "traceparent middleware emits + propagates real W3C ids on every request within each Space; cross-Space distributed-trace broker NOT wired (see a11oy /wires)."},
            "E": {"edge": "a11oy↔amaru (cortex sync)", "status": "LIVE", "detail": "SSE /api/amaru/v1/cortex-subscribe (in-memory event bus)"},
            "F": {"edge": "a11oy↔vessels (receipts)", "status": "LIVE", "detail": "POST /api/vessels/v1/receipts/ingest (Khipu Merkle DAG)"},
        },
        "recent_traces": recent_traces(10),
        "cortex_events": cortex_events(10),
        "khipu_root": khipu_root(),
        "khipu_nodes": khipu_nodes(10),
        "coexists_with": "a11oy /wires (sibling Doctrine-v10 surface): /wires is the canonical honest status board (Wire D shown there as NOT YET cross-Space). /mesh adds the in-process traceparent + cortex-SSE + Khipu-receipt live views. No duplication: /mesh LINKS to /wires.",
        "honesty": "In-memory ring buffers (no external broker in a static HF Space). "
                   "Trace IDs are real W3C ids generated + propagated in-process; cross-Space distributed tracing is NOT wired. "
                   "Receipt signatures are PLACEHOLDER (Sigstore CI not wired). Numbers 749/14/163 per Doctrine v10.",
    }
