# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
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

  DSSE + COSIGN (signed provenance, SLSA L1 honest; L2 roadmap via Wire D) — REAL, replaces PLACEHOLDER:
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
  * SLSA self-claim is L1 honest (signing live); L2 (hardened build-service provenance) is roadmap via Wire D, NOT yet claimed; L3 NOT claimed.
"""
from __future__ import annotations

import asyncio
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

import szl_dsse

DOCTRINE = "v11"
SLSA_LEVEL = "L1"

# Honest cited provenance for the Provenance board / Khipu ledger tabs: REAL
# in-tree lutar-lean theorems (kernel-verified in szl-holdings/lutar-lean) +
# public standards / arXiv. PROVEN entries only; no Conjecture upgrades.
_LUTAR_REPO = "https://github.com/szl-holdings/lutar-lean"
CITATIONS = [
    {"claim": "Merkle-DAG provenance build", "status": "PROVEN",
     "lutar_theorem": "Lutar.DPI.MerkleDAGBuild",
     "lutar_url": _LUTAR_REPO + "/blob/main/Lutar/DPI/MerkleDAGBuild.lean",
     "standard": "RFC 6962 Merkle transparency; Sigstore Rekor (Apache-2.0)", "arxiv": "RFC 6962"},
    {"claim": "DPI / provenance soundness", "status": "PROVEN",
     "lutar_theorem": "Lutar.DPI.TH6_DPI_Soundness",
     "lutar_url": _LUTAR_REPO + "/blob/main/Lutar/DPI/TH6_DPI_Soundness.lean",
     "standard": "in-toto/DSSE; SLSA provenance framework", "arxiv": "arXiv:2406.10109"},
    {"claim": "Composition soundness (W3C trace continuity)", "status": "PROVEN",
     "lutar_theorem": "Lutar.Composition.TH1_Composition",
     "lutar_url": _LUTAR_REPO + "/tree/main/Lutar/Composition",
     "standard": "W3C Trace Context (traceparent)", "arxiv": "arXiv:2406.10109"},
]
CITATION_NOTE = ("Provenance/ledger tabs cite real in-tree lutar-lean theorems plus the public "
                 "standard / arXiv they map to. All cited entries are kernel-verified (PROVEN).")

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
    valid = (ver == "00" and len(trace_id) == 32 and len(span_id) == 16 and flags in {"00", "01"}
             and set(trace_id) <= hexset and set(span_id) <= hexset
             and trace_id != "0" * 32 and span_id != "0" * 16)
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


_WIRE_D_TARGET_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A Wire-D probe never follows a target-controlled redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _wire_d_target_policy(raw_url: str, allowed_hosts: set[str]) -> dict[str, Any]:
    """Validate one operator-declared peer without exposing its URL publicly."""
    try:
        parsed = urlsplit(str(raw_url).strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("scheme must be http or https")
        if parsed.username or parsed.password:
            raise ValueError("credentials in target URL are forbidden")
        if parsed.query or parsed.fragment:
            raise ValueError("query and fragment are forbidden")
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host or host not in allowed_hosts:
            raise ValueError("host is not in A11OY_WIRE_D_ALLOWED_HOSTS")
        if not parsed.path.startswith("/api/"):
            raise ValueError("target path must be an /api/ route")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not 1 <= int(port) <= 65535:
            raise ValueError("port is outside 1..65535")
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
        if not addresses:
            raise ValueError("target host did not resolve")
        for raw_address in addresses:
            address = ipaddress.ip_address(raw_address)
            if address.is_unspecified or address.is_multicast or address.is_reserved or address.is_link_local:
                raise ValueError("target resolves to a forbidden address class")
        canonical = parsed.geturl()
        return {
            "allowed": True,
            "url": canonical,
            "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
            "scheme": parsed.scheme,
            "path": parsed.path,
        }
    except (OSError, TypeError, ValueError) as exc:
        return {
            "allowed": False,
            "url": None,
            "fingerprint": None,
            "reason": str(exc)[:160],
        }


def _wire_d_targets_from_env() -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """Load a closed target-name registry; request bodies never supply URLs."""
    raw = os.environ.get("A11OY_WIRE_D_TARGETS", "").strip()
    allowed_hosts = {
        host.strip().lower().rstrip(".")
        for host in os.environ.get("A11OY_WIRE_D_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    if not raw:
        return {}, []
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}, [{"target": "(registry)", "reason": "A11OY_WIRE_D_TARGETS is invalid JSON"}]
    if not isinstance(decoded, dict):
        return {}, [{"target": "(registry)", "reason": "target registry must be a JSON object"}]
    targets: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []
    for raw_name, raw_url in decoded.items():
        name = str(raw_name).strip().lower()
        if not _WIRE_D_TARGET_RE.fullmatch(name):
            rejected.append({"target": name[:32] or "(empty)", "reason": "invalid target name"})
            continue
        policy = _wire_d_target_policy(str(raw_url), allowed_hosts)
        if policy["allowed"]:
            targets[name] = policy
        else:
            rejected.append({"target": name, "reason": str(policy["reason"])})
    return targets, rejected


def _wire_d_http_hop(target: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """Execute one bounded HTTP hop and require W3C trace-id continuity."""
    request = urllib.request.Request(
        target["url"],
        method="GET",
        headers={
            "Accept": "application/json",
            "traceparent": headers["traceparent"],
            **({"tracestate": headers["tracestate"]} if headers.get("tracestate") else {}),
            "X-SZL-Wire-D-Probe": "1",
        },
    )
    started = time.perf_counter_ns()
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(request, timeout=3.0)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        response.read(4096)
        status_code = int(response.status)
        echoed = response.headers.get("traceparent")
        target_space = response.headers.get("x-szl-space")
    latency_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    sent_parsed = parse_traceparent(headers["traceparent"])
    echo_parsed = parse_traceparent(echoed)
    continuity = bool(
        sent_parsed.get("valid")
        and echo_parsed.get("valid")
        and sent_parsed["trace_id"] == echo_parsed["trace_id"]
    )
    return {
        "state": "MEASURED" if 200 <= status_code < 300 and continuity else "CONFLICT",
        "http_status": status_code,
        "latency_ms": latency_ms,
        "traceparent_sent": headers["traceparent"],
        "traceparent_echoed": echoed,
        "trace_id_continuity": continuity,
        "target_space": str(target_space or "UNREPORTED")[:64],
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
    wire_d_targets, wire_d_rejections = _wire_d_targets_from_env()
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

    def wire_d_receipts() -> list[dict[str, Any]]:
        return [
            node
            for node in dag.recent(50)
            if node.get("receipt", {}).get("schema") == "szl.wire_d.hop_receipt/v1"
        ]

    def wire_d_status_payload() -> dict[str, Any]:
        receipts = wire_d_receipts()
        measured = [
            node for node in receipts
            if node["receipt"].get("state") == "MEASURED"
            and node["receipt"].get("trace_id_continuity") is True
        ]
        conflicts = [node for node in receipts if node["receipt"].get("state") != "MEASURED"]
        if receipts:
            state = "MEASURED" if receipts[-1]["receipt"].get("state") == "MEASURED" else "DEGRADED"
        elif wire_d_targets:
            state = "READY_UNMEASURED"
        else:
            state = "UNCONFIGURED"
        return {
            "wire": "D",
            "state": state,
            "scope": "cross-mesh W3C traceparent hop plus Khipu receipt",
            "targets": [
                {
                    "target": name,
                    "state": "CONFIGURED",
                    "endpoint_fingerprint": policy["fingerprint"],
                    "scheme": policy["scheme"],
                }
                for name, policy in sorted(wire_d_targets.items())
            ],
            "rejected_targets": wire_d_rejections,
            "measured_hops": len(measured),
            "conflicted_or_unavailable_hops": len(conflicts),
            "recent": [
                {
                    "digest": node["digest"],
                    "signed": node["signed"],
                    "state": node["receipt"].get("state"),
                    "target": node["receipt"].get("target"),
                    "target_space": node["receipt"].get("target_space"),
                    "http_status": node["receipt"].get("http_status"),
                    "latency_ms": node["receipt"].get("latency_ms"),
                    "trace_id_continuity": node["receipt"].get("trace_id_continuity"),
                    "ts_utc": node["receipt"].get("ts_utc"),
                }
                for node in receipts[-10:]
            ],
            "anatomy": {
                "current": "v5",
                "v6": "NOT_CLAIMED",
                "yuyay_contract": "yuyay_v3 canonical 13-axis contract preserved; transport probe does not score it",
            },
            "receipt_minted_on_get": False,
            "honesty": (
                "MEASURED requires a real configured HTTP peer to echo a valid traceparent "
                "with the same trace-id. READY_UNMEASURED is configuration, not evidence."
            ),
        }

    app.state.szl_outgoing_headers = outgoing_headers
    app.state.szl_emit_signed_receipt = emit_signed_receipt
    app.state.szl_khipu_dag = dag
    app.state.szl_trace = tstate

    @app.get(f"{base}/v1/wire-d/status")
    async def wire_d_probe_status() -> JSONResponse:
        """Read the bounded cross-mesh evidence ledger; this GET mints nothing."""
        return JSONResponse(wire_d_status_payload())

    @app.post(f"{base}/v1/wire-d/probe")
    async def wire_d_probe(request: Request) -> JSONResponse:
        """Execute one allowlisted HTTP hop and receipt the observed continuity."""
        try:
            body = await request.json()
        except (TypeError, ValueError):
            return JSONResponse({"state": "DENIED", "reason": "invalid JSON body"}, status_code=400)
        target_name = str(body.get("target", "")).strip().lower() if isinstance(body, dict) else ""
        target = wire_d_targets.get(target_name)
        if target is None:
            return JSONResponse(
                {
                    "state": "DENIED",
                    "reason": "target is not in the closed Wire-D registry",
                    "configured_targets": sorted(wire_d_targets),
                },
                status_code=422,
            )
        headers = outgoing_headers(request, target_name)
        try:
            result = await asyncio.to_thread(_wire_d_http_hop, target, headers)
        except (OSError, TimeoutError, http.client.HTTPException, urllib.error.URLError) as exc:
            result = {
                "state": "UNAVAILABLE",
                "http_status": None,
                "latency_ms": None,
                "traceparent_sent": headers["traceparent"],
                "traceparent_echoed": None,
                "trace_id_continuity": False,
                "target_space": "UNREPORTED",
                "error_type": type(exc).__name__,
            }
        receipt = {
            "schema": "szl.wire_d.hop_receipt/v1",
            "wire": "D",
            "source_space": space,
            "target": target_name,
            "target_endpoint_fingerprint": target["fingerprint"],
            **result,
        }
        node = emit_signed_receipt(receipt, request)
        payload = {
            **result,
            "target": target_name,
            "target_endpoint_fingerprint": target["fingerprint"],
            "receipt_digest": node["digest"],
            "receipt_signed": node["signed"],
            "receipt_keyid": node["keyid"],
            "anatomy_version": "v5 current; v6 not claimed",
        }
        return JSONResponse(payload, status_code=200 if result["state"] == "MEASURED" else 502)

    # ---- /wires/D : trace volume + active spans ----
    @app.get(f"{base}/wires/D")
    async def wire_d_status(request: Request) -> JSONResponse:
        snap = tstate.snapshot()
        cross_mesh = wire_d_status_payload()
        return JSONResponse({
            "wire": "D",
            "name": "W3C traceparent \u2014 trace continuity",
            "space": space,
            "status": cross_mesh["state"],
            "spec": "https://www.w3.org/TR/trace-context/",
            "format": "00-<32hex trace-id>-<16hex span-id>-<2hex flags>",
            "current_request_traceparent": getattr(request.state, "traceparent", None),
            "current_request_tracestate": getattr(request.state, "tracestate", None),
            **snap,
            "cross_space": cross_mesh,
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
            "citations": CITATIONS, "citation_note": CITATION_NOTE,
            "anchor_health_at": f"/api/{space}/uds/v1/rekor/health",
            "honesty": ("DSSE signatures are REAL ECDSA-P256-SHA256 cosign sigs when the "
                        "SZL_COSIGN_PRIVATE_PEM runtime secret is present (else UNSIGNED, labelled). "
                        "DAG is in-memory per Space (non-persistent across restart). SLSA L1 honest; L2 roadmap via Wire D "
                        "(signed provenance) — NOT L3 (no hardened CI yet)."),
        })

    # ---- /provenance : combined honest board for this Space ----
    @app.get(f"{base}/provenance")
    async def provenance_board() -> JSONResponse:
        cross_mesh = wire_d_status_payload()
        return JSONResponse({
            "space": space, "doctrine": DOCTRINE, "slsa": SLSA_LEVEL,
            "wire_D": {"status": cross_mesh["state"], "name": "W3C traceparent trace continuity",
                       "endpoint": f"{base}/wires/D",
                       "cross_mesh_evidence": f"{base}/v1/wire-d/status"},
            "khipu_dsse": {"signing_available": szl_dsse.signing_available(),
                           "keyid": szl_dsse.KEYID,
                           "payloadType": szl_dsse.KHIPU_PAYLOAD_TYPE,
                           "verify_endpoint": f"{base}/khipu/verify",
                           "pub_key_url": szl_dsse.PUB_KEY_URL},
            "slsa_note": ("L1 honest: the deployed image is cosign-signed and publicly "
                          "verifiable (Rekor). L2 = an isolated, attested build-service "
                          "PROVENANCE for the deployed image, verifiable downstream — roadmap "
                          "via Wire D, NOT yet claimed (GHCR shows the cosign-signed image only). "
                          "L3 = a hardened, isolated build pipeline (UDS Core), also not in place. "
                          "Honestly L1; L2/L3 not claimed."),
            "self_attesting": "every sign/verify op emits its own DSSE-signed Khipu receipt.",
            "citations": CITATIONS, "citation_note": CITATION_NOTE,
            "anchor_health_at": f"/api/{space}/uds/v1/rekor/health",
        })

    return {"space": space, "wire_D": wire_d_status_payload()["state"], "slsa": SLSA_LEVEL,
            "signing_available": szl_dsse.signing_available(),
            "endpoints": [f"{base}/wires/D", f"{base}/khipu/verify",
                          f"{base}/khipu/sign", f"{base}/khipu/ledger", f"{base}/provenance",
                          f"{base}/v1/wire-d/status", f"{base}/v1/wire-d/probe"]}
