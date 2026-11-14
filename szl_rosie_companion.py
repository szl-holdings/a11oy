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
  - Receipts are explicitly UNSIGNED (Sigstore keyless CI not yet wired).
  - Cross-flagship HTTP calls are REAL; when Rosie is unreachable (HF Space cold/sleeping)
    the shadow returns a clearly-labelled local stub (`stub=True`) — never fabricated as live.
  - The 162-endpoint claim refers to the CLOUD Rosie; a flagship reaches the
    `/v1/brain/jack-<flagship>` family + the brain-jack mesh, not all 162 locally.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

DOCTRINE = "v11"
WIRE = "I"  # Rosie-companion-wire (this library defines Wire I)
ROSIE_BASE_URL = os.environ.get("ROSIE_BASE_URL", "https://szlholdings-rosie.hf.space")

_SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_SCHEMAS = frozenset({
    "szl.rosie_companion.receipt/v1",
    "szl.brain_jack.receipt/v1",
})
_RECEIPT_PAYLOAD_TYPES = {
    "szl.rosie_companion.receipt/v1":
        "application/vnd.szl.rosie_companion.receipt+json",
    "szl.brain_jack.receipt/v1":
        "application/vnd.szl.brain_jack.receipt+json",
}
_DIGEST_EXCLUDED_FIELDS = frozenset({
    "node_digest",
    "dsse",
    "signature",
    "signature_status",
})

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
    node_digest = _canonical_receipt_digest(body)
    body["node_digest"] = node_digest
    body.update(_unsigned_attestation(
        "application/vnd.szl.rosie_companion.receipt+json"
    ))
    return body


def _canonical_receipt_digest(body: dict[str, Any]) -> str:
    """Return the v1 canonical digest, rejecting values outside strict JSON."""
    encoded = json.dumps(body, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unsigned_attestation(payload_type: str,
                          status: str = "UNSIGNED") -> dict[str, Any]:
    """Describe the absent signer without placing fake data in a signature slot."""
    return {
        "dsse": {
            "payloadType": payload_type,
            "signatures": [],
        },
        "signature": None,
        "signature_status": status,
    }


def _normalise_json_object(value: Any) -> Optional[dict[str, Any]]:
    """Return an isolated JSON object or None when the value is malformed."""
    if not isinstance(value, dict):
        return None
    try:
        encoded = json.dumps(value, sort_keys=True, allow_nan=False)
        normalised = json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None
    if not isinstance(normalised, dict) or normalised != value:
        return None
    return normalised


def _signature_present(receipt: dict[str, Any]) -> bool:
    signature = receipt.get("signature")
    if signature not in (None, ""):
        return True
    declared_status = receipt.get("signature_status")
    if (isinstance(declared_status, str) and declared_status
            not in {"", "UNSIGNED", "UNVERIFIED"}):
        return True
    dsse = receipt.get("dsse")
    if not isinstance(dsse, dict):
        return False
    signatures = dsse.get("signatures")
    return signatures not in (None, [])


def _finite_score(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _common_receipt_fields_valid(receipt: dict[str, Any]) -> bool:
    axis_scores = receipt.get("axis_scores")
    fields_valid = bool(
        receipt.get("doctrine") == DOCTRINE
        and isinstance(receipt.get("ts_utc"), str)
        and receipt["ts_utc"].strip()
        and _finite_score(receipt.get("lambda_signal"))
        and 0.0 <= float(receipt["lambda_signal"]) <= 1.0
        and isinstance(axis_scores, list)
        and all(_finite_score(score) for score in axis_scores)
        and all(0.0 <= float(score) <= 1.0 for score in axis_scores)
        and (receipt.get("traceparent") is None
             or isinstance(receipt.get("traceparent"), str))
    )
    if not fields_valid:
        return False
    return math.isclose(
        float(receipt["lambda_signal"]),
        lambda_signal(axis_scores),
        rel_tol=0.0,
        abs_tol=5e-7,
    )


def _receipt_binding_valid(receipt: dict[str, Any], *, role: str,
                           flagship: str,
                           traceparent: Optional[str]) -> bool:
    if not _common_receipt_fields_valid(receipt):
        return False
    schema = receipt.get("schema")
    if role == "flagship":
        return bool(
            schema == "szl.rosie_companion.receipt/v1"
            and receipt.get("wire") == WIRE
            and receipt.get("flagship") == flagship
            and receipt.get("flagship_organ")
                == FLAGSHIPS.get(flagship, {}).get("organ", "unknown")
            and receipt.get("rosie_endpoint")
                == f"/api/rosie/v1/brain/jack-{flagship}"
            and isinstance(receipt.get("op"), str)
            and bool(receipt["op"].strip())
            and isinstance(receipt.get("query_preview"), str)
        )
    if role == "rosie":
        return bool(
            schema == "szl.brain_jack.receipt/v1"
            and receipt.get("wire") == "G"
            and receipt.get("space") == "rosie"
            and receipt.get("organ") == "nervous"
            and receipt.get("src_space") == flagship
            and receipt.get("traceparent") == traceparent
        )
    return False


def _inspect_receipt(receipt: Any, *, role: str, flagship: str,
                     traceparent: Optional[str]) -> tuple[
                         Optional[dict[str, Any]], dict[str, Any]
                     ]:
    """Validate receipt shape and body digest without claiming signature trust."""
    evidence: dict[str, Any] = {
        "observed": receipt is not None,
        "shape_valid": False,
        "schema_valid": False,
        "binding_valid": False,
        "digest_present": False,
        "digest_verified": False,
        "signature_present": False,
        "signature_verified": False,
        "accepted_as_digest_leaf": False,
        "claimed_digest": None,
        "verified_digest": None,
        "status": "NOT_OBSERVED" if receipt is None else "MALFORMED_RECEIPT",
    }
    normalised = _normalise_json_object(receipt)
    if normalised is None or not normalised:
        return normalised, evidence

    evidence["shape_valid"] = True
    evidence["signature_present"] = _signature_present(normalised)
    schema = normalised.get("schema")
    evidence["schema_valid"] = (
        isinstance(schema, str) and schema in _RECEIPT_SCHEMAS
    )
    if not evidence["schema_valid"]:
        evidence["status"] = "INVALID_SCHEMA"
        return normalised, evidence
    evidence["binding_valid"] = _receipt_binding_valid(
        normalised, role=role, flagship=flagship, traceparent=traceparent
    )
    if not evidence["binding_valid"]:
        evidence["status"] = "INVALID_BINDING"
        return normalised, evidence

    claimed_digest = normalised.get("node_digest")
    evidence["digest_present"] = claimed_digest is not None
    if not isinstance(claimed_digest, str) or not _SHA256_HEX.fullmatch(claimed_digest):
        evidence["status"] = (
            "MISSING_DIGEST" if claimed_digest is None else "MALFORMED_DIGEST"
        )
        return normalised, evidence
    evidence["claimed_digest"] = claimed_digest

    digest_body = {
        key: value for key, value in normalised.items()
        if key not in _DIGEST_EXCLUDED_FIELDS
    }
    try:
        expected_digest = _canonical_receipt_digest(digest_body)
    except (TypeError, ValueError, OverflowError, RecursionError):
        evidence["status"] = "MALFORMED_RECEIPT"
        return normalised, evidence
    if not hmac.compare_digest(claimed_digest, expected_digest):
        evidence["status"] = "DIGEST_MISMATCH"
        return normalised, evidence

    evidence["digest_verified"] = True
    evidence["accepted_as_digest_leaf"] = True
    evidence["verified_digest"] = claimed_digest
    evidence["status"] = (
        "DIGEST_VERIFIED_SIGNATURE_UNVERIFIED"
        if evidence["signature_present"]
        else "DIGEST_VERIFIED_UNSIGNED"
    )
    return normalised, evidence


def _retained_receipt(receipt: Optional[dict[str, Any]],
                      evidence: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Keep verified or known-schema legacy evidence; reject malformed claims."""
    if (not evidence["shape_valid"] or not evidence["schema_valid"]
            or not evidence["binding_valid"]):
        return None
    if evidence["status"] in {"MALFORMED_DIGEST", "DIGEST_MISMATCH"}:
        return None
    assert receipt is not None
    retained = dict(receipt)
    payload_type = _RECEIPT_PAYLOAD_TYPES[retained["schema"]]
    attestation_status = (
        "UNVERIFIED" if evidence["signature_present"] else "UNSIGNED"
    )
    retained.update(_unsigned_attestation(payload_type, attestation_status))
    return retained


def cross_link_receipt(flagship: str, rosie_receipt: Any,
                       companion_receipt: dict[str, Any]) -> dict[str, Any]:
    """Build the Khipu CROSS-LINK receipt that ties together the full hop:

        flagship -> Rosie -> response -> flagship

    Links the local companion receipt (flagship side) with the brain-jack receipt
    Rosie returned (Rosie side) under a single Merkle root. This is THE artifact the
    task requires: a recorded cross-flagship reasoning link.
    """
    companion, companion_evidence = _inspect_receipt(
        companion_receipt,
        role="flagship",
        flagship=flagship,
        traceparent=(companion_receipt.get("traceparent")
                     if isinstance(companion_receipt, dict) else None),
    )
    expected_traceparent = (
        companion.get("traceparent") if companion is not None else None
    )
    rosie, rosie_evidence = _inspect_receipt(
        rosie_receipt,
        role="rosie",
        flagship=flagship,
        traceparent=expected_traceparent,
    )
    companion = _retained_receipt(companion, companion_evidence)
    rosie = _retained_receipt(rosie, rosie_evidence)
    leaves = [
        evidence["verified_digest"]
        for evidence in (companion_evidence, rosie_evidence)
        if evidence["digest_verified"]
    ]
    root = _merkle_root(leaves)
    digest_verified = bool(
        companion_evidence["digest_verified"]
        and rosie_evidence["digest_verified"]
    )
    signature_verified = bool(
        companion_evidence["signature_verified"]
        and rosie_evidence["signature_verified"]
    )
    cross_link = {
        "schema": "szl.rosie_companion.cross_link/v1",
        "wire": WIRE,
        "doctrine": DOCTRINE,
        "chain": [
            {"hop": "flagship->rosie", "flagship": flagship,
             "receipt_digest": companion_evidence["verified_digest"],
             "claimed_receipt_digest": companion_evidence["claimed_digest"]},
            {"hop": "rosie->response", "flagship": "rosie",
             "receipt_digest": rosie_evidence["verified_digest"],
             "claimed_receipt_digest": rosie_evidence["claimed_digest"]},
            {"hop": "response->flagship", "flagship": flagship,
             "khipu_root": root},
        ],
        "khipu_root": root,
        "validated_leaf_digests": leaves,
        "hop_count": 1,
        "flagship_receipt": companion,
        "rosie_receipt": rosie,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "chain_observed": rosie_evidence["observed"],
        "all_hops_observed": rosie_evidence["observed"],
        "flagship_digest_verified": companion_evidence["digest_verified"],
        "rosie_digest_verified": rosie_evidence["digest_verified"],
        "digest_verified": digest_verified,
        "signature_verified": signature_verified,
        "chain_verified": bool(digest_verified and signature_verified),
        "verification": {
            "flagship_receipt": companion_evidence,
            "rosie_receipt": rosie_evidence,
        },
        "honesty": (
            "chain_observed records receipt presence. digest_verified requires "
            "canonical body digests for both receipts. signature_verified requires "
            "cryptographic verification; this companion has no configured verifier."
        ),
    }
    cross_link.update(_unsigned_attestation(
        "application/vnd.szl.rosie_companion.cross_link+json"
    ))
    return cross_link


def _extend_cross_link(parent: dict[str, Any],
                       child: dict[str, Any]) -> dict[str, Any]:
    """Extend a recursive reasoning chain without changing either hop's roles."""
    leaves = list(parent.get("validated_leaf_digests", []))
    leaves.extend(child.get("validated_leaf_digests", []))
    root = _merkle_root(leaves)
    parent["validated_leaf_digests"] = leaves
    parent["khipu_root"] = root
    parent["chain"][2]["khipu_root"] = root
    parent["hop_count"] = int(parent.get("hop_count", 1)) + int(
        child.get("hop_count", 1)
    )
    parent["all_hops_observed"] = bool(
        parent.get("all_hops_observed")
        and child.get("all_hops_observed")
    )
    parent["digest_verified"] = bool(
        parent.get("digest_verified") and child.get("digest_verified")
    )
    parent["signature_verified"] = bool(
        parent.get("signature_verified") and child.get("signature_verified")
    )
    parent["chain_verified"] = bool(
        parent["digest_verified"] and parent["signature_verified"]
    )
    parent["next_hop"] = child
    return parent


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
        raw_rosie_receipt = None if stub else rosie_json.get("lambda_receipt")
        xlink = cross_link_receipt(
            self.flagship, raw_rosie_receipt, companion_receipt
        )
        rosie_receipt = xlink["rosie_receipt"]
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

    def evolve(
        self,
        strategy: dict[str, Any],
        approvers: Optional[list[str]] = None,
        traceparent: Optional[str] = None,
    ) -> EvolveProposal:
        """Return a proposal only; typed approver names never authorize it.

        This companion has no trusted identity-verification boundary. A separate
        flagship gate must verify two independent signed approvals before execution.
        """
        claimed_approvers = sorted(
            {str(value).strip() for value in (approvers or []) if str(value).strip()}
        )
        axis_scores = strategy.get("axis_scores")
        query = "EVOLVE strategy proposal: " + json.dumps(
            strategy, sort_keys=True, default=str
        )[:800]
        rosie_json, stub, err = self._call_rosie_jack(
            "evolve", query, axis_scores, traceparent, payload_extra=strategy
        )
        L = rosie_json.get("lambda_signal", lambda_signal(axis_scores))
        gate_status = "AWAITING_VERIFIED_2P_YUYAY"
        companion_receipt = make_khipu_receipt(
            self.flagship,
            "evolve",
            query,
            axis_scores,
            traceparent,
            extra={
                "strategy": strategy,
                "approver_claims": claimed_approvers,
                "verified_approvers": [],
                "typed_names_authorize": False,
                "two_person_gate": gate_status,
            },
        )
        raw_rosie_receipt = None if stub else rosie_json.get("lambda_receipt")
        xlink = cross_link_receipt(
            self.flagship, raw_rosie_receipt, companion_receipt
        )
        rosie_receipt = xlink["rosie_receipt"]
        return EvolveProposal(
            flagship=self.flagship,
            proposed_strategy=strategy,
            rationale=rosie_json.get("response_text", ""),
            lambda_signal=L,
            requires_two_person_gate=True,
            gate_status=gate_status,
            approvers=[],
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
            # Re-root over validated leaves while preserving each hop's receipt roles.
            resp.cross_link = _extend_cross_link(
                resp.cross_link, child.cross_link
            )
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

