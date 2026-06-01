# SPDX-License-Identifier: Apache-2.0
# AUTO-FLATTENED single-file deployable of szl-rosie-companion v1.0.0 (Doctrine v11, Wire I)
# Source of truth: szl_rosie_companion/companion.py  ·  Signed: Yachay
# Drop into any flagship HF Space as szl_rosie_companion.py and: import szl_rosie_companion as rc
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
companion.py — RosieShadow: the per-flagship Rosie reasoning co-pilot.

This module is dependency-light by design (stdlib + optional httpx). It is meant to
be COPIED into each flagship's HF Space (as `szl_rosie_companion.py`) AND usable as a
real installable library. Every Rosie cross-flagship call emits a Khipu receipt.

HONESTY (Doctrine v10/v11 contract — verbatim, never hidden):
  - Receipt signatures are PLACEHOLDER (Sigstore keyless CI not yet wired).
  - Cross-flagship HTTP calls are REAL; when Rosie is unreachable (HF Space cold/sleeping)
    the shadow returns a clearly-labelled local stub (`stub=True`) — never fabricated as live.
  - The 162-endpoint claim refers to the CLOUD Rosie; a flagship reaches the
    `/v1/brain/jack-<flagship>` family + the brain-jack mesh, not all 162 locally.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

DOCTRINE = "v11"
WIRE = "I"  # Rosie-companion-wire (this library defines Wire I)
SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI signing not yet wired (Doctrine v10/v11)"
ROSIE_BASE_URL = os.environ.get("ROSIE_BASE_URL", "https://szlholdings-rosie.hf.space")

# Flagships that carry a Rosie-shadow. vessels is intentionally absent: it is
# legacy/collectioned (air-domain pivot moved to killinchu) — see task HARD RULES.
FLAGSHIPS: dict[str, dict[str, Any]] = {
    "a11oy":     {"organ": "gate",    "hf_url": "https://szlholdings-a11oy.hf.space"},
    "amaru":     {"organ": "cortex",  "hf_url": "https://szlholdings-amaru.hf.space"},
    "sentra":    {"organ": "immune",  "hf_url": "https://szlholdings-sentra.hf.space"},
    "killinchu": {"organ": "drone",   "hf_url": "https://szlholdings-killinchu.hf.space"},
    "rosie":     {"organ": "nervous", "hf_url": "https://szlholdings-rosie.hf.space"},
}

# 13-axis Yuyay canonical names (Doctrine v11, yuyay_v3) — identical to szl_jack.
AXIS_NAMES = [
    "truthfulness", "calibration", "transparency", "forthrightness",
    "non_deception", "non_manipulation", "autonomy_preservation",
    "harm_avoidance", "data_minimisation", "contestability",
    "accountability", "interoperability", "reversibility",
]


def lambda_signal(axis_scores: Optional[list[float]]) -> float:
    """13-axis weighted geometric mean (Doctrine v11 canonical λ_signal).

    Identical math to szl_jack.lambda_signal so cross-flagship λ values reconcile.
    """
    if not axis_scores:
        return 0.5
    n = min(13, len(axis_scores))
    clamped = [min(1.0, max(1e-9, float(x))) for x in axis_scores[:n]]
    while len(clamped) < 13:
        clamped.append(0.5)
    logmean = sum(math.log(x) for x in clamped) / 13
    return round(math.exp(logmean), 6)


# ---------------------------------------------------------------------------
# Khipu cross-flagship receipt — every Rosie call records the link
#   flagship -> Rosie -> response -> flagship
# ---------------------------------------------------------------------------

def make_khipu_receipt(flagship: str, op: str, query: str,
                       axis_scores: Optional[list[float]],
                       traceparent: Optional[str],
                       extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Mint a single Khipu pendant receipt for one Rosie cross-flagship call."""
    L = lambda_signal(axis_scores)
    body = {
        "schema": "szl.rosie_companion.receipt/v1",
        "wire": WIRE,
        "doctrine": DOCTRINE,
        "flagship": flagship,
        "flagship_organ": FLAGSHIPS.get(flagship, {}).get("organ", "unknown"),
        "rosie_endpoint": f"/api/rosie/v1/brain/jack-{flagship}",
        "op": op,
        "query_preview": (query or "")[:120],
        "lambda_signal": L,
        "axis_scores": axis_scores or [],
        "traceparent": traceparent,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        body["meta"] = extra
    # node digest = sha256 over canonical body (pendant value)
    node_digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    body["node_digest"] = node_digest
    body["dsse"] = {
        "payloadType": "application/vnd.szl.rosie_companion.receipt+json",
        "signatures": [{"sig": SIGNATURE_PLACEHOLDER, "keyid": "PENDING — Sigstore keyless not wired"}],
    }
    body["signature"] = SIGNATURE_PLACEHOLDER
    return body


def cross_link_receipt(flagship: str, rosie_receipt: Optional[dict[str, Any]],
                       companion_receipt: dict[str, Any]) -> dict[str, Any]:
    """Build the Khipu CROSS-LINK receipt that ties together the full hop:

        flagship -> Rosie -> response -> flagship

    Links the local companion receipt (flagship side) with the brain-jack receipt
    Rosie returned (Rosie side) under a single Merkle root. This is THE artifact the
    task requires: a recorded cross-flagship reasoning link.
    """
    leaves = [companion_receipt.get("node_digest", "")]
    if rosie_receipt:
        r_digest = rosie_receipt.get("node_digest")
        if not r_digest:
            r_digest = hashlib.sha256(
                json.dumps(rosie_receipt, sort_keys=True).encode()).hexdigest()
        leaves.append(r_digest)
    leaves = [x for x in leaves if x]
    root = _merkle_root(leaves)
    return {
        "schema": "szl.rosie_companion.cross_link/v1",
        "wire": WIRE,
        "doctrine": DOCTRINE,
        "chain": [
            {"hop": "flagship->rosie", "flagship": flagship,
             "receipt_digest": companion_receipt.get("node_digest")},
            {"hop": "rosie->response", "flagship": "rosie",
             "receipt_digest": (rosie_receipt or {}).get("node_digest")},
            {"hop": "response->flagship", "flagship": flagship,
             "khipu_root": root},
        ],
        "khipu_root": root,
        "flagship_receipt": companion_receipt,
        "rosie_receipt": rosie_receipt,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "chain_verified": bool(rosie_receipt is not None),
        "honesty": ("chain_verified=true only when Rosie returned a real receipt; "
                    "false means the Rosie hop was a local stub (Space unreachable)."),
        "signature": SIGNATURE_PLACEHOLDER,
    }


def _merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return hashlib.sha256(b"empty").hexdigest()
    layer = sorted(leaves)
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [hashlib.sha256((layer[i] + layer[i + 1]).encode()).hexdigest()
                 for i in range(0, len(layer), 2)]
    return layer[0]


# ---------------------------------------------------------------------------
# Response containers
# ---------------------------------------------------------------------------

class RosieUnavailable(RuntimeError):
    """Raised only when strict=True and Rosie cannot be reached."""


@dataclass
class RosieResponse:
    op: str
    flagship: str
    text: str
    lambda_signal: float
    rosie_receipt: Optional[dict[str, Any]]
    companion_receipt: dict[str, Any]
    cross_link: dict[str, Any]
    stub: bool = False
    error: Optional[str] = None
    traceparent: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["doctrine"] = DOCTRINE
        d["wire"] = WIRE
        return d


@dataclass
class EvolveProposal:
    flagship: str
    proposed_strategy: dict[str, Any]
    rationale: str
    lambda_signal: float
    requires_two_person_gate: bool
    gate_status: str            # honest: AWAITING_2ND_SIGNER until two approvers present
    approvers: list[str]
    rosie_receipt: Optional[dict[str, Any]]
    companion_receipt: dict[str, Any]
    cross_link: dict[str, Any]
    stub: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["doctrine"] = DOCTRINE
        d["wire"] = WIRE
        return d


# ---------------------------------------------------------------------------
# RosieShadow — the per-flagship co-pilot
# ---------------------------------------------------------------------------

class RosieShadow:
    """Per-flagship handle onto Rosie's reasoning surface.

    Usage (inside a flagship backend):
        shadow = RosieShadow("a11oy")
        resp = shadow.ponder({"state": "...", "axis_scores": [...]})
        # resp.text, resp.cross_link (Khipu), resp.rosie_receipt

    All methods are synchronous (use httpx sync client). The flagship route handler
    can call them directly or wrap in `asyncio.to_thread`.
    """

    def __init__(self, flagship_name: str, *,
                 rosie_base_url: Optional[str] = None,
                 timeout_s: float = 10.0,
                 strict: bool = False):
        if flagship_name not in FLAGSHIPS:
            # Allow unknown flagships but warn via organ='unknown' — never crash.
            FLAGSHIPS.setdefault(flagship_name, {"organ": "unknown", "hf_url": ""})
        self.flagship = flagship_name
        self.organ = FLAGSHIPS[flagship_name]["organ"]
        self.rosie_base_url = (rosie_base_url or ROSIE_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s
        self.strict = strict  # if True, raise RosieUnavailable instead of stubbing

    # --- the Rosie jack endpoint for THIS flagship --------------------------
    @property
    def jack_url(self) -> str:
        return f"{self.rosie_base_url}/api/rosie/v1/brain/jack-{self.flagship}"

    @property
    def brain_jack_url(self) -> str:
        return f"{self.rosie_base_url}/api/rosie/v1/brain/jack"

    # --- low-level: call Rosie's jack-<flagship> endpoint -------------------
    def _call_rosie_jack(self, op: str, query: str,
                         axis_scores: Optional[list[float]],
                         traceparent: Optional[str],
                         payload_extra: Optional[dict[str, Any]] = None
                         ) -> tuple[dict[str, Any], bool, Optional[str]]:
        """POST to Rosie's jack-<flagship> endpoint. Returns (rosie_json, stub, error).

        Falls back to the generic brain-jack mesh endpoint if jack-<flagship> 404s,
        then to a labelled local stub if Rosie is unreachable.
        """
        payload = {
            "src_space": self.flagship,
            "src_organ": self.organ,
            "op": op,
            "query": query,
            "axis_scores": axis_scores or [],
            "traceparent": traceparent,
        }
        if payload_extra:
            payload["context"] = payload_extra
        headers = {}
        if traceparent:
            headers["traceparent"] = traceparent
        # Prefer httpx if present; otherwise fall back to stdlib urllib so the
        # companion reaches Rosie in ANY flagship image (no new image dep needed).
        try:
            try:
                import httpx
                with httpx.Client(timeout=self.timeout_s) as client:
                    r = client.post(self.jack_url, json=payload, headers=headers)
                    if r.status_code == 404:
                        r = client.post(self.brain_jack_url, json=payload, headers=headers)
                    if r.status_code == 200:
                        return r.json(), False, None
                    raise ValueError(f"HTTP {r.status_code}")
            except ImportError:
                import json as _json, urllib.request as _u, urllib.error as _ue
                data = _json.dumps(payload).encode()
                for _url in (self.jack_url, self.brain_jack_url):
                    try:
                        _req = _u.Request(_url, data=data, headers=headers, method="POST")
                        with _u.urlopen(_req, timeout=self.timeout_s) as _resp:
                            if 200 <= getattr(_resp, "status", 200) < 300:
                                return _json.loads(_resp.read().decode()), False, None
                    except _ue.HTTPError as _he:
                        if _he.code == 404:
                            continue
                        raise
                raise ValueError("all jack endpoints failed")
        except Exception as e:  # unreachable / cold start / dep missing
            if self.strict:
                raise RosieUnavailable(str(e)) from e
            return self._local_stub(op, query, axis_scores, traceparent), True, str(e)

    def _local_stub(self, op: str, query: str,
                    axis_scores: Optional[list[float]],
                    traceparent: Optional[str]) -> dict[str, Any]:
        """Clearly-labelled offline stub (NEVER presented as a live Rosie answer)."""
        L = lambda_signal(axis_scores)
        return {
            "src_space": self.flagship,
            "response_organ": "nervous",
            "response_text": (
                f"[rosie-shadow STUB · {self.flagship}/{self.organ}] op={op}. "
                f"Query: '{(query or '')[:120]}'. λ={L:.4f}. "
                f"Rosie cloud unreachable — local heuristic shadow engaged "
                f"(co-pilot proposes; flagship + Yuyay gate decide)."),
            "lambda_signal": L,
            "lambda_receipt": None,
            "traceparent": traceparent,
            "stub": True,
        }

    def _wrap(self, op: str, query: str, axis_scores, traceparent,
              rosie_json: dict[str, Any], stub: bool, error: Optional[str],
              extra: Optional[dict[str, Any]] = None) -> RosieResponse:
        companion_receipt = make_khipu_receipt(
            self.flagship, op, query, axis_scores, traceparent, extra=extra)
        rosie_receipt = None if stub else rosie_json.get("lambda_receipt")
        xlink = cross_link_receipt(self.flagship, rosie_receipt, companion_receipt)
        return RosieResponse(
            op=op,
            flagship=self.flagship,
            text=rosie_json.get("response_text", ""),
            lambda_signal=rosie_json.get("lambda_signal", lambda_signal(axis_scores)),
            rosie_receipt=rosie_receipt,
            companion_receipt=companion_receipt,
            cross_link=xlink,
            stub=stub,
            error=error,
            traceparent=traceparent,
            extra=extra or {},
        )

    # ======================================================================
    # PUBLIC API
    # ======================================================================

    def ponder(self, context: dict[str, Any] | str,
               traceparent: Optional[str] = None) -> RosieResponse:
        """Rosie ponders the flagship's current state and returns insights.

        `context` is the PURIQ context x — a dict describing the flagship's situation
        (or a plain string). Pure read; emits no actuation. Always emits a Khipu receipt.
        """
        if isinstance(context, str):
            ctx = {"state": context}
            axis_scores = None
        else:
            ctx = dict(context)
            axis_scores = ctx.get("axis_scores")
        query = ("PONDER flagship state: " +
                 json.dumps(ctx, sort_keys=True, default=str)[:800])
        rosie_json, stub, err = self._call_rosie_jack(
            "ponder", query, axis_scores, traceparent, payload_extra=ctx)
        return self._wrap("ponder", query, axis_scores, traceparent,
                          rosie_json, stub, err, extra={"context": ctx})

    def synthesize(self, events: list[dict[str, Any]],
                   traceparent: Optional[str] = None) -> RosieResponse:
        """Rosie synthesizes insight from a sequence of Khipu receipts / events.

        `events` is an ordered list of Khipu receipts (or event dicts). Rosie reads the
        chain and returns a narrative synthesis. Emits a Khipu receipt linking the
        synthesis to its input chain (input_root recorded in meta).
        """
        digests = []
        for ev in events or []:
            d = ev.get("node_digest") if isinstance(ev, dict) else None
            if not d:
                d = hashlib.sha256(json.dumps(ev, sort_keys=True, default=str).encode()).hexdigest()
            digests.append(d)
        input_root = _merkle_root(digests)
        # derive axis scores from events if present (mean per axis), else None
        axis_scores = _mean_axis_from_events(events)
        query = (f"SYNTHESIZE {len(events or [])} Khipu events; input_root={input_root[:16]}; "
                 + json.dumps((events or [])[:5], sort_keys=True, default=str)[:600])
        rosie_json, stub, err = self._call_rosie_jack(
            "synthesize", query, axis_scores, traceparent,
            payload_extra={"n_events": len(events or []), "input_root": input_root})
        resp = self._wrap("synthesize", query, axis_scores, traceparent,
                          rosie_json, stub, err,
                          extra={"input_root": input_root, "n_events": len(events or [])})
        resp.extra["input_root"] = input_root
        return resp

    def evolve(self, strategy: dict[str, Any],
               approvers: Optional[list[str]] = None,
               traceparent: Optional[str] = None) -> EvolveProposal:
        """Rosie PROPOSES evolution of the flagship's strategy (ecosystem-evolve loop).

        2-PERSON YUYAY GATE REQUIRED (this can change flagship strategy). Rosie does
        NOT execute: it returns a PROPOSAL with gate_status. Execution requires two
        distinct approvers passed in `approvers` (>=2) AND the flagship's own gate.
        Always emits a Khipu receipt.
        """
        approvers = list(approvers or [])
        axis_scores = strategy.get("axis_scores")
        query = ("EVOLVE strategy proposal: " +
                 json.dumps(strategy, sort_keys=True, default=str)[:800])
        rosie_json, stub, err = self._call_rosie_jack(
            "evolve", query, axis_scores, traceparent, payload_extra=strategy)
        L = rosie_json.get("lambda_signal", lambda_signal(axis_scores))
        # Two-person Yuyay gate: require >=2 DISTINCT approvers to authorize.
        distinct = sorted(set(a for a in approvers if a))
        gate_ok = len(distinct) >= 2
        gate_status = "AUTHORIZED_2P_YUYAY" if gate_ok else "AWAITING_2ND_SIGNER"
        companion_receipt = make_khipu_receipt(
            self.flagship, "evolve", query, axis_scores, traceparent,
            extra={"strategy": strategy, "approvers": distinct,
                   "two_person_gate": gate_status})
        rosie_receipt = None if stub else rosie_json.get("lambda_receipt")
        xlink = cross_link_receipt(self.flagship, rosie_receipt, companion_receipt)
        return EvolveProposal(
            flagship=self.flagship,
            proposed_strategy=strategy,
            rationale=rosie_json.get("response_text", ""),
            lambda_signal=L,
            requires_two_person_gate=True,
            gate_status=gate_status,
            approvers=distinct,
            rosie_receipt=rosie_receipt,
            companion_receipt=companion_receipt,
            cross_link=xlink,
            stub=stub,
            error=err,
        )

    def brain_jack(self, query: str, depth: int = 1,
                   axis_scores: Optional[list[float]] = None,
                   traceparent: Optional[str] = None,
                   _current: int = 0) -> RosieResponse:
        """Rosie brain-jack reasoning with DEPTH-LIMITED recursion.

        depth=1 → single Rosie jack. depth>1 → Rosie's answer is fed back as the next
        query (chained reasoning), up to `depth` hops. Recursion is HARD-capped at 5 to
        respect the Bekenstein-bounded action space 𝒜 (Doctrine v11). Each hop emits a
        Khipu receipt; hops are chained into one cross-link.
        """
        depth = max(1, min(int(depth), 5))  # Bekenstein cap
        rosie_json, stub, err = self._call_rosie_jack(
            "brain_jack", query, axis_scores, traceparent)
        resp = self._wrap("brain_jack", query, axis_scores, traceparent,
                          rosie_json, stub, err,
                          extra={"depth": depth, "hop": _current + 1})
        if _current + 1 < depth and not stub:
            # Chain: feed Rosie's response back in as the next query.
            next_query = f"[depth {_current+2}/{depth}] reflect on: {resp.text[:400]}"
            child = self.brain_jack(next_query, depth=depth, axis_scores=axis_scores,
                                    traceparent=traceparent, _current=_current + 1)
            resp.extra["next_hop"] = child.to_dict()
            # re-root cross-link to include the child digest
            resp.cross_link = cross_link_receipt(
                self.flagship, child.companion_receipt, resp.companion_receipt)
        return resp


def _mean_axis_from_events(events: Optional[list[dict[str, Any]]]) -> Optional[list[float]]:
    if not events:
        return None
    cols: list[list[float]] = []
    for ev in events:
        if isinstance(ev, dict):
            ax = ev.get("axis_scores") or (ev.get("meta", {}) or {}).get("axis_scores")
            if ax:
                cols.append([float(x) for x in ax[:13]])
    if not cols:
        return None
    n = max(len(c) for c in cols)
    means = []
    for i in range(n):
        vals = [c[i] for c in cols if i < len(c)]
        means.append(sum(vals) / len(vals) if vals else 0.5)
    return means
