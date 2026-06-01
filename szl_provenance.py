# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by Yachay (CTO) — Provenance Hardening layer.
"""
szl_provenance — ADDITIVE mesh provenance layer for every SZL Space.

Closes two honest-ceiling gaps from session canon:

  WIRE D (W3C Trace Context, trace continuity)  — REAL, per the W3C spec
    (https://www.w3.org/TR/trace-context/):
      * traceparent = 00-<32hex trace-id>-<16hex parent-id>-<2hex flags>
      * On INBOUND: extract a valid incoming traceparent (preserve trace-id),
        else mint a fresh one. Mint a NEW server span-id for THIS hop (the
        spec's default "update parent-id" mutation) and remember the inbound
        parent so we can chain.
      * tracestate is parsed, preserved, and our own `szl` entry is written to
        the LEFT (per spec mutation rules), recording this Space's span.
      * On OUTBOUND cross-Space calls, `outgoing_headers()` propagates the
        SAME trace-id with a fresh child span + updated tracestate so the
        trace is continuous across Spaces (trace continuity wire).
      * Every Khipu receipt now carries the W3C `traceparent` of its origin span.
      * /api/<space>/wires/D  — current trace volume + active spans on this Space.

  DSSE + COSIGN (signed provenance, SLSA L2) — REAL, replaces PLACEHOLDER:
      * Every Khipu receipt is signed with a DSSE envelope using the SZLHOLDINGS
        Cosign key (szl_dsse.sign_khipu_receipt). payloadType =
        "application/vnd.szl.khipu+json"; signatures=[{sig,keyid:szlholdings-cosign}].
      * /api/<space>/khipu/verify — validates a DSSE envelope (or {receipt,dsse})
        against the published cosign.pub.
      * /api/<space>/khipu/sign   — sign an arbitrary receipt (demo/smoke).
      * The signing system signs itself: every sign/verify op emits its own
        Khipu receipt into the DAG (self-attesting provenance).

HONESTY:
  * Trace IDs are real W3C ids, generated + propagated + CHAINED across Spaces
    via header propagation (no external collector required — the trace context
    itself is the continuity mechanism the spec defines).
  * Signatures are REAL ECDSA-P256-SHA256 cosign sigs when the
    SZL_COSIGN_PRIVATE_PEM runtime secret is present; if absent, receipts are
    emitted UNSIGNED and clearly labelled (never faked).
  * Khipu DAG is in-memory per Space (additive, non-persistent across restart) —
    same honest ceiling as before; now SIGNED.
  * SLSA self-claim is L2 (signed provenance), NOT L3 (no hardened CI yet).
"""
from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

import szl_dsse

DOCTRINE = "v12"
SLSA_LEVEL = "L2"

# ---------------------------------------------------------------------------
# Wire D — W3C Trace Context
# ---------------------------------------------------------------------------

def _rand_hex(nbytes: int) -> str:
    return os.urandom(nbytes).hex()


def new_trace_id() -> str:
    tid = _rand_hex(16)
    return tid if tid != "0" * 32 else _rand_hex(16)


def new_span_id() -> str:
    sid = _rand_hex(8)
    return sid if sid != "0" * 16 else _rand_hex(8)


def new_traceparent() -> str:
    return f"00-{new_trace_id()}-{new_span_id()}-01"


def parse_traceparent(tp: str | None) -> dict[str, Any]:
    if not tp or tp.count("-") != 3:
        return {"valid": False, "raw": tp}
    ver, trace_id, span_id, flags = tp.split("-")
    hexset = set("0123456789abcdef")
    valid = (len(ver) == 2 and len(trace_id) == 32 and len(span_id) == 16 and len(flags) == 2
             and set(trace_id) <= hexset and set(span_id) <= hexset
             and trace_id != "0" * 32 and span_id != "0" * 16 and ver != "ff")
    return {"valid": valid, "version": ver, "trace_id": trace_id,
            "parent_id": span_id, "span_id": span_id, "flags": flags, "raw": tp}


def parse_tracestate(ts: str | None) -> list[tuple[str, str]]:
    """Parse tracestate into ordered (key, value) list-members (max 32)."""
    out: list[tuple[str, str]] = []
    if not ts:
        return out
    for member in ts.split(","):
        member = member.strip()
        if not member or "=" not in member:
            continue
        k, _, v = member.partition("=")
        out.append((k.strip(), v.strip()))
        if len(out) >= 32:
            break
    return out


def mutate_tracestate(existing: list[tuple[str, str]], span_id: str) -> str:
    """Per W3C: write our `szl` entry to the LEFT, preserve other entries' order,
    drop any prior `szl` entry (overwrite-on-reentry rule)."""
    kept = [(k, v) for (k, v) in existing if k != "szl"]
    members = [("szl", span_id)] + kept
    members = members[:32]
    return ",".join(f"{k}={v}" for k, v in members)


class _TraceState:
    """Per-Space in-memory trace ledger (Wire D trace continuity)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.log: deque[dict[str, Any]] = deque(maxlen=200)
        self.active_spans: dict[str, dict[str, Any]] = {}  # span_id -> meta
        self.trace_volume = 0  # total spans observed since boot
        self.traces_seen: set[str] = set()

    def record_inbound(self, trace_id: str, span_id: str, parent_inbound: str | None,
                       path: str) -> None:
        with self.lock:
            self.trace_volume += 1
            self.traces_seen.add(trace_id)
            self.active_spans[span_id] = {
                "span_id": span_id, "trace_id": trace_id,
                "inbound_parent": parent_inbound, "path": path,
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "direction": "in",
            }
            self.log.append({"trace_id": trace_id, "span_id": span_id,
                             "parent": parent_inbound, "path": path, "dir": "in",
                             "ts_utc": datetime.now(timezone.utc).isoformat()})
            # bound active span set
            if len(self.active_spans) > 200:
                for k in list(self.active_spans)[:50]:
                    self.active_spans.pop(k, None)

    def record_outbound(self, trace_id: str, span_id: str, parent: str, target: str) -> None:
        with self.lock:
            self.trace_volume += 1
            self.log.append({"trace_id": trace_id, "span_id": span_id, "parent": parent,
                             "target": target, "dir": "out",
                             "ts_utc": datetime.now(timezone.utc).isoformat()})

    def end_span(self, span_id: str) -> None:
        with self.lock:
            self.active_spans.pop(span_id, None)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "trace_volume": self.trace_volume,
                "distinct_traces": len(self.traces_seen),
                "active_span_count": len(self.active_spans),
                "active_spans": list(self.active_spans.values())[-25:],
                "recent": list(self.log)[-25:],
            }


# ---------------------------------------------------------------------------
# Khipu DAG (DSSE-signed)
# ---------------------------------------------------------------------------

class _KhipuDAG:
    def __init__(self, space: str) -> None:
        self.space = space
        self.lock = threading.Lock()
        self.nodes: list[dict[str, Any]] = []

    def _digest(self, payload_b: bytes, parents: list[str]) -> str:
        import hashlib
        h = hashlib.sha256()
        h.update(payload_b)
        for p in parents:
            h.update(p.encode())
        return h.hexdigest()

    def append_signed(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Sign the receipt with DSSE+Cosign and append as a Merkle DAG node."""
        env = szl_dsse.sign_payload(receipt, szl_dsse.KHIPU_PAYLOAD_TYPE)
        body = szl_dsse.canonical_json(receipt)
        with self.lock:
            parents = [self.nodes[-1]["digest"]] if self.nodes else []
            node = {
                "index": len(self.nodes),
                "space": self.space,
                "wire": "F",
                "receipt": receipt,
                "dsse": env,
                "parents": parents,
                "signed": env.get("signed", False),
                "keyid": (env["signatures"][0]["keyid"] if env.get("signatures") else None),
                "slsa": SLSA_LEVEL,
                "doctrine": DOCTRINE,
                "ts_utc": datetime.now(timezone.utc).isoformat(),
            }
            node["digest"] = self._digest(body, parents)
            self.nodes.append(node)
            return node

    def root(self) -> str | None:
        with self.lock:
            return self.nodes[-1]["digest"] if self.nodes else None

    def recent(self, n: int = 10) -> list[dict[str, Any]]:
        with self.lock:
            return self.nodes[-n:]


# ---------------------------------------------------------------------------
# Public registration
# ---------------------------------------------------------------------------

def register_provenance(app, space: str) -> dict[str, Any]:
    """ADDITIVE: install Wire D middleware + /wires/D + /khipu/{sign,verify,ledger}.

    Returns a status dict. Wrapped by callers in try/except so a failure can
    never take down the existing app."""
    tstate = _TraceState()
    dag = _KhipuDAG(space)
    base = f"/api/{space}"

    # ---- Wire D middleware: extract/mint traceparent, mint server span, echo ----
    @app.middleware("http")
    async def _wire_d_mw(request: Request, call_next):  # noqa: ANN001
        incoming = request.headers.get("traceparent")
        parsed = parse_traceparent(incoming)
        ts_in = parse_tracestate(request.headers.get("tracestate"))
        if parsed.get("valid"):
            trace_id = parsed["trace_id"]
            inbound_parent = parsed["parent_id"]
        else:
            trace_id = new_trace_id()
            inbound_parent = None
            ts_in = []  # invalid traceparent => discard tracestate (per spec)
        server_span = new_span_id()  # this Space's span for THIS request (mutate parent-id)
        tp = f"00-{trace_id}-{server_span}-01"
        ts_out = mutate_tracestate(ts_in, server_span)
        # stash for outgoing propagation + receipt stamping
        request.state.traceparent = tp
        request.state.trace_id = trace_id
        request.state.span_id = server_span
        request.state.inbound_parent = inbound_parent
        request.state.tracestate = ts_out
        path = request.url.path
        if not path.startswith("/assets"):
            tstate.record_inbound(trace_id, server_span, inbound_parent, path)
        resp = await call_next(request)
        tstate.end_span(server_span)
        resp.headers["traceparent"] = tp
        if ts_out:
            resp.headers["tracestate"] = ts_out
        resp.headers["x-szl-space"] = space
        resp.headers["x-szl-wire-d"] = "LIVE"
        return resp

    # ---- helpers exposed on app.state for the host app to use ----
    def outgoing_headers(request, target_space: str | None = None) -> dict[str, str]:
        """Propagate the trace to a cross-Space call (Wire D continuity).
        Mints a fresh CHILD span for the outbound hop, preserves trace-id +
        tracestate so the receiving Space continues the same trace."""
        st = getattr(request, "state", None)
        trace_id = getattr(st, "trace_id", None) or new_trace_id()
        child = new_span_id()
        ts = getattr(st, "tracestate", "") or ""
        ts_members = parse_tracestate(ts)
        ts_out = mutate_tracestate(ts_members, child)
        tp = f"00-{trace_id}-{child}-01"
        tstate.record_outbound(trace_id, child, getattr(st, "span_id", None) or "", target_space or "peer")
        hdrs = {"traceparent": tp}
        if ts_out:
            hdrs["tracestate"] = ts_out
        return hdrs

    def receipt_trace_fields(request) -> dict[str, Any]:
        """The W3C trace fields to stamp onto a Khipu receipt (origin span)."""
        st = getattr(request, "state", None)
        return {
            "traceparent": getattr(st, "traceparent", None) or new_traceparent(),
            "trace_id": getattr(st, "trace_id", None),
            "span_id": getattr(st, "span_id", None),
            "wire_d": "LIVE",
        }

    def emit_signed_receipt(receipt: dict[str, Any], request=None) -> dict[str, Any]:
        """Stamp Wire D trace fields + DSSE-sign + append to the Khipu DAG."""
        r = dict(receipt)
        r.setdefault("space", space)
        r.setdefault("doctrine", DOCTRINE)
        r.setdefault("slsa", SLSA_LEVEL)
        r.setdefault("ts_utc", datetime.now(timezone.utc).isoformat())
        if request is not None:
            r.update(receipt_trace_fields(request))
        else:
            r.setdefault("traceparent", new_traceparent())
        return dag.append_signed(r)

    app.state.szl_outgoing_headers = outgoing_headers
    app.state.szl_emit_signed_receipt = emit_signed_receipt
    app.state.szl_khipu_dag = dag
    app.state.szl_trace = tstate

    # ---- /wires/D : trace volume + active spans ----
    @app.get(f"{base}/wires/D")
    async def wire_d_status(request: Request) -> JSONResponse:
        snap = tstate.snapshot()
        return JSONResponse({
            "wire": "D",
            "name": "W3C traceparent \u2014 trace continuity",
            "space": space,
            "status": "LIVE",
            "spec": "https://www.w3.org/TR/trace-context/",
            "format": "00-<32hex trace-id>-<16hex span-id>-<2hex flags>",
            "current_request_traceparent": getattr(request.state, "traceparent", None),
            "current_request_tracestate": getattr(request.state, "tracestate", None),
            **snap,
            "cross_space": ("Trace continuity is propagated via the traceparent + tracestate "
                            "headers on cross-Space calls (preserve trace-id, mint child span, "
                            "rewrite tracestate left-most). Every Khipu receipt carries the "
                            "origin span's traceparent."),
            "doctrine": DOCTRINE,
        })

    # ---- /khipu/verify : validate a DSSE signature against cosign.pub ----
    @app.post(f"{base}/khipu/verify")
    async def khipu_verify(request: Request) -> JSONResponse:  # noqa: ANN001
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"verified": False, "reason": "invalid JSON body"}, status_code=400)
        # Accept either a raw DSSE envelope or {receipt, dsse}
        env = payload.get("dsse") if isinstance(payload, dict) and "dsse" in payload else payload
        verdict = szl_dsse.verify_envelope(env if isinstance(env, dict) else {})
        # the verifier signs itself (self-attesting): emit a Khipu receipt of the verify op
        node = emit_signed_receipt({
            "schema": "szl.khipu.verify_op/v1",
            "op": "khipu/verify",
            "verified": verdict.get("verified"),
            "keyid_expected": szl_dsse.KEYID,
        }, request)
        return JSONResponse({**verdict, "verify_receipt_digest": node["digest"],
                             "verify_receipt_signed": node["signed"], "space": space})

    # ---- /khipu/sign : sign an arbitrary receipt (smoke / demo) ----
    @app.post(f"{base}/khipu/sign")
    async def khipu_sign(request: Request) -> JSONResponse:  # noqa: ANN001
        try:
            body = await request.json()
        except Exception:
            body = {}
        receipt = body.get("receipt", body) if isinstance(body, dict) else {}
        if not isinstance(receipt, dict) or not receipt:
            receipt = {"schema": "szl.khipu.demo/v1", "note": "empty body — demo receipt"}
        node = emit_signed_receipt(receipt, request)
        return JSONResponse({
            "space": space, "digest": node["digest"], "index": node["index"],
            "signed": node["signed"], "keyid": node["keyid"], "slsa": SLSA_LEVEL,
            "dsse": node["dsse"], "traceparent": node["receipt"].get("traceparent"),
            "verify_at": f"{base}/khipu/verify",
        })

    # ---- /khipu/ledger : the signed Khipu DAG ----
    @app.get(f"{base}/khipu/ledger")
    async def khipu_ledger() -> JSONResponse:
        nodes = dag.recent(20)
        return JSONResponse({
            "space": space, "khipu_root": dag.root(), "count": len(dag.nodes),
            "signing_available": szl_dsse.signing_available(),
            "keyid": szl_dsse.KEYID, "slsa": SLSA_LEVEL, "doctrine": DOCTRINE,
            "pub_fingerprint_sha256": szl_dsse.public_key_fingerprint(),
            "verify_key_url": szl_dsse.PUB_KEY_URL,
            "nodes": nodes,
            "honesty": ("DSSE signatures are REAL ECDSA-P256-SHA256 cosign sigs when the "
                        "SZL_COSIGN_PRIVATE_PEM runtime secret is present (else UNSIGNED, labelled). "
                        "DAG is in-memory per Space (non-persistent across restart). SLSA L2 "
                        "(signed provenance) — NOT L3 (no hardened CI yet)."),
        })

    # ---- /provenance : combined honest board for this Space ----
    @app.get(f"{base}/provenance")
    async def provenance_board() -> JSONResponse:
        return JSONResponse({
            "space": space, "doctrine": DOCTRINE, "slsa": SLSA_LEVEL,
            "wire_D": {"status": "LIVE", "name": "W3C traceparent trace continuity",
                       "endpoint": f"{base}/wires/D"},
            "khipu_dsse": {"signing_available": szl_dsse.signing_available(),
                           "keyid": szl_dsse.KEYID,
                           "payloadType": szl_dsse.KHIPU_PAYLOAD_TYPE,
                           "verify_endpoint": f"{base}/khipu/verify",
                           "pub_key_url": szl_dsse.PUB_KEY_URL},
            "slsa_note": ("L2 = signed provenance via DSSE+Cosign (now real). L3 would require "
                          "a hardened, isolated build pipeline (UDS Core) which is NOT yet in place — "
                          "honestly L2, not L3."),
            "self_attesting": "every sign/verify op emits its own DSSE-signed Khipu receipt.",
        })

    return {"space": space, "wire_D": "LIVE", "slsa": SLSA_LEVEL,
            "signing_available": szl_dsse.signing_available(),
            "endpoints": [f"{base}/wires/D", f"{base}/khipu/verify",
                          f"{base}/khipu/sign", f"{base}/khipu/ledger", f"{base}/provenance"]}
