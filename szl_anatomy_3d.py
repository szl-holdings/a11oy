# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Exactly eight locked formulas; Λ is Conjecture 1.
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""Read-only 3D anatomy observations and explicitly admitted sample actions.

Taxonomy: services/provenance. Public reads never evaluate, sign, append, seed a
chain, resolve a private key, or call another service. Geometry and historical
formula metadata are MODELED; they do not establish operational readiness.

The two existing POSTs retain their sample/advisory math behind the operator
gate. Their bounded last-observation cache is process-local, expires after 60
seconds, and is neither a persistent store nor execution authority. Three.js
r128 remains locally vendored under its existing MIT license.
"""

import copy
import hashlib
import importlib
import json
import math
import re
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional

try:
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
except ImportError:  # Pure projection helpers remain importable without FastAPI.
    Request = HTMLResponse = JSONResponse = FileResponse = Response = None

# Dependencies with signing or initialization effects are loaded only by writes.
_V4 = _DSSE = _KHIPU = _SF = None

LEAN_COMMIT = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371"
ZENODO = "https://doi.org/10.5281/zenodo.20162352"
DOCTRINE = {
    "version": "v11", "state": "LOCKED", "locked_formula_count": 8,
    "locked_formula_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "lambda": "Conjecture 1 (NOT a theorem)",
    "historical_snapshot": {"counts": "749/14/163", "lean_commit": LEAN_COMMIT},
}
THREE_SRC = "/anatomy-three.min.js"
OBSERVATION_SCHEMA = "szl.anatomy.observation/v1"
OBSERVATION_TTL_SECONDS = 60
MAX_OBSERVATION_NAMESPACES = 8
MAX_OBSERVATION_BYTES = 16384
MAX_REQUEST_BYTES = 16384
MAX_ROUTES = 16
MAX_CHAIN_RECORDS = 60
MAX_TRACE_RECORDS = 20
_NAMESPACE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _write_dependency(name: str, override: Any) -> Any:
    if override is not None:
        return override
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _sign(receipt: Dict[str, Any], neuro=None) -> Dict[str, Any]:
    signer = _write_dependency("szl_dsse", _DSSE)
    if signer is not None:
        try:
            return signer.sign_khipu_receipt(receipt, neuro or [])
        except Exception:
            pass
    return {"receipt": receipt, "dsse": {"signatures": [], "signed": False},
            "signature_status": "UNSIGNED"}


def _khipu_emit(action: str, payload: Dict[str, Any], ns="a11oy", organ="anatomy") -> dict:
    khipu = _write_dependency("szl_khipu", _KHIPU)
    if khipu is not None:
        try:
            return khipu.get_dag(organ, ns).emit(action, payload)
        except Exception:
            pass
    return {"available": False, "reason": "CHAIN_UNAVAILABLE", "seq": None,
            "digest": None, "prev": None, "chain_verified": False, "signature": None}


def _finite(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _utc_at(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _projection(ns: str, kind: str, state="UNAVAILABLE", reason="NO_OBSERVATION",
                evidence_class="UNAVAILABLE", data=None, observed_at=None,
                age_seconds=None, **metadata) -> dict:
    out = {
        "schema": OBSERVATION_SCHEMA, "ns": ns, "kind": kind, "mode": "READ_ONLY",
        "state": state, "reason": reason, "evidence_class": evidence_class,
        "observed_at": observed_at, "age_seconds": age_seconds,
        "max_age_seconds": OBSERVATION_TTL_SECONDS,
        "storage_writes": 0, "receipt_minted_on_get": False,
        "model_invoked": False, "execution_performed": False,
        "execution_authorized": False,
        "source_revision": None, "runtime_boot_id": None,
        "identity_binding": "NOT_ESTABLISHED",
        "signature_verified": False, "signature_verification": "NOT_PERFORMED",
        "receipt_signature_status": "NOT_ESTABLISHED", "signature_count": 0,
        "receipt_sha256": None, "chain_verified": False,
        "chain_integrity": {"state": "NOT_ESTABLISHED", "scope": "NONE",
                            "checked_records": 0, "prefix_verified": False},
        "joules_measured": None, "energy_label": "UNAVAILABLE",
        "data_scope": "PROCESS_LOCAL_NONAUTHORITATIVE", "bounded": True,
        "data": data,
    }
    out.update(metadata)
    return out


def _receipt_metadata(result: dict) -> dict:
    wrapper = result.get("receipt")
    if not isinstance(wrapper, dict):
        return {}
    try:
        raw = json.dumps(wrapper, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
        if len(raw) > 65536:
            return {}
        dsse = wrapper.get("dsse")
        signatures = dsse.get("signatures", []) if isinstance(dsse, dict) else []
        valid = isinstance(signatures, list) and len(signatures) <= 16 and all(
            isinstance(row, dict) and isinstance(row.get("sig"), str)
            and 0 < len(row["sig"]) <= 8192 for row in signatures)
        count = len(signatures) if valid else 0
        return {"receipt_sha256": hashlib.sha256(raw).hexdigest(),
                "signature_count": count,
                "receipt_signature_status": ("NOT_ESTABLISHED" if not valid else
                                             "UNVERIFIED" if count else "UNSIGNED")}
    except (TypeError, ValueError, RecursionError):
        return {}


def _remember_observation(ns: str, kind: str, result: dict) -> None:
    """A write-side summary, never called by GET or used as authority."""
    if not _NAMESPACE.fullmatch(ns) or kind not in {"heart", "wires"}:
        raise ValueError("invalid observation slot")
    if kind == "heart":
        data = {"lambda_aggregate": result["lambda_aggregate"],
                "passing": result["passing"],
                "axes": [{key: row.get(key) for key in
                          ("axis", "score", "floor", "evaluator", "verdict")}
                         for row in result["axes"]]}
    else:
        routes = [{"tier": f"sample-route-{index + 1}",
                   **{key: row[key] for key in ("energy", "latency_ms", "admissible") if key in row}}
                  for index, row in enumerate(result["routes"])]
        selected = next((index for index, row in enumerate(result["routes"])
                         if row == result["chosen"]), None)
        data = {"routes": routes, "chosen": routes[selected] if selected is not None else None,
                "routing_performed": False, "energy_cost_scope": "ADVISORY_INPUT"}
    item = {"data": data, "evidence_class": result["evidence_class"],
            "recorded_monotonic": time.monotonic(), "observed_at": _utc_at(time.time()),
            "receipt_metadata": _receipt_metadata(result)}
    raw = json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise ValueError("observation exceeds bound")
    frozen = json.loads(raw)
    with _CACHE_LOCK:
        slots = _CACHE.setdefault(ns, {})
        slots[kind] = frozen
        _CACHE.move_to_end(ns)
        while len(_CACHE) > MAX_OBSERVATION_NAMESPACES:
            _CACHE.popitem(last=False)


def _cached_observation(ns: str, kind: str) -> dict:
    with _CACHE_LOCK:
        item = copy.deepcopy(_CACHE.get(ns, {}).get(kind))
    if item is None:
        return _projection(ns, kind, reason="NO_AUTHORIZED_OBSERVATION")
    age = time.monotonic() - item["recorded_monotonic"]
    if not _finite(age) or age < 0:
        return _projection(ns, kind, reason="OBSERVATION_CLOCK_UNAVAILABLE")
    age = round(age, 6)
    if age > OBSERVATION_TTL_SECONDS:
        return _projection(ns, kind, state="STALE", reason="OBSERVATION_EXPIRED",
                           evidence_class=item["evidence_class"],
                           observed_at=item["observed_at"], age_seconds=age)
    return _projection(ns, kind, state="OBSERVED", reason="AUTHORIZED_SAMPLE_OBSERVED",
                       evidence_class=item["evidence_class"], data=item["data"],
                       observed_at=item["observed_at"], age_seconds=age,
                       **item["receipt_metadata"])


def _validate_action(kind: str, body: Any) -> dict:
    if not isinstance(body, dict):
        raise ValueError("JSON object required")
    if kind == "heart":
        if set(body) - {"scores"}:
            raise ValueError("unknown vote field")
        scores = body.get("scores", {})
        allowed = {axis["axis"] for axis in YUYAY_13}
        if not isinstance(scores, dict) or set(scores) - allowed:
            raise ValueError("invalid score axes")
        if any(not _finite(v) or not 0 <= v <= 1 for v in scores.values()):
            raise ValueError("scores must be finite within [0,1]")
        return copy.deepcopy(body)
    if set(body) - {"routes", "energy_budget"}:
        raise ValueError("unknown routing field")
    budget = body.get("energy_budget", 1.0)
    if not _finite(budget) or not 0 <= budget <= 1e12:
        raise ValueError("invalid advisory budget")
    routes = body.get("routes")
    if "routes" in body:
        if not isinstance(routes, list) or not 1 <= len(routes) <= MAX_ROUTES:
            raise ValueError("invalid route count")
        names = set()
        for row in routes:
            if not isinstance(row, dict) or set(row) - {"tier", "energy", "latency_ms", "admissible"}:
                raise ValueError("invalid route fields")
            tier = row.get("tier")
            if not isinstance(tier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}", tier):
                raise ValueError("invalid route identifier")
            if tier in names:
                raise ValueError("duplicate route identifier")
            names.add(tier)
            for name in ("energy", "latency_ms"):
                if name in row and (not _finite(row[name]) or not 0 <= row[name] <= 1e12):
                    raise ValueError("invalid advisory route cost")
            if "energy" not in row or ("admissible" in row and type(row["admissible"]) is not bool):
                raise ValueError("invalid route admission field")
    return copy.deepcopy(body)


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON field")
        out[key] = value
    return out


def _invalid_constant(value):
    raise ValueError("nonfinite JSON value")


async def _action_body(request: Request, kind: str) -> dict:
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_REQUEST_BYTES:
            raise ValueError("request exceeds bound")
        raw.extend(chunk)
    body = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_invalid_constant)
    return _validate_action(kind, body)


def _operator_refusal(request: Request, action: str):
    try:
        from szl_operator_auth import operator_refusal
        return operator_refusal(request, action)
    except Exception:
        return JSONResponse({"ok": False, "status": "BLOCKED",
                             "reason": "OPERATOR_AUTH_UNAVAILABLE"}, status_code=401)


# ── 13 Yuyay axes — canonical Lutar yuyay_v3 (replay bacf5443…631fc5) ─────────
# Each axis names a witness formula; floors from szl_formulas.axis_floors():
# 2 sacred (>=0.95) + 7 structural (>=0.90) + 4 introspection (>=0.90).
YUYAY_13 = [
    {"axis": "sound",              "band": "sacred",        "floor": 0.95, "slug": None,
     "lean": "soundnessAxiom", "leanStatus": "axiom", "id": "A11", "status": "ts-only", "doi": None},
    {"axis": "moral",             "band": "sacred",        "floor": 0.95, "slug": None,
     "lean": "moralGroundingFloor", "leanStatus": "axiom", "id": "A2", "status": "ts-only", "doi": None},
    {"axis": "measurability",     "band": "structural",    "floor": 0.90, "slug": None,
     "lean": "measurabilityHonestyFloor", "leanStatus": "axiom", "id": "A3", "status": "ts-only", "doi": None},
    {"axis": "dual-witness",      "band": "structural",    "floor": 0.90, "slug": "dual-witness-disjointness",
     "lean": "dualWitnessDisjointness", "leanStatus": "theorem", "id": "A4", "status": "live", "doi": None},
    {"axis": "deterministic-replay", "band": "structural", "floor": 0.90, "slug": "deterministic-replay",
     "lean": "deterministicReplay", "leanStatus": "theorem", "id": "A5", "status": "live", "doi": None},
    {"axis": "hash-chain",        "band": "structural",    "floor": 0.90, "slug": "hash-chain-integrity",
     "lean": "hashChainIntegrity", "leanStatus": "theorem", "id": "A6", "status": "live", "doi": None},
    {"axis": "bekenstein",        "band": "structural",    "floor": 0.90, "slug": None,
     "lean": "bekensteinBound", "leanStatus": "theorem", "id": "A7", "status": "ts-only",
     "doi": "10.1103/PhysRevD.23.287"},
    {"axis": "robustness",        "band": "structural",    "floor": 0.90, "slug": "adversarial-robustness",
     "lean": "robustness_preserved_by_composition", "leanStatus": "theorem", "id": "TH8", "status": "live", "doi": None},
    {"axis": "false-position",    "band": "structural",    "floor": 0.90, "slug": "false-position",
     "lean": "false_position_correct", "leanStatus": "theorem", "id": "Rhind", "status": "live", "doi": None},
    {"axis": "liu-hui",           "band": "introspection", "floor": 0.90, "slug": "liu-hui-pi",
     "lean": "sideSquared_bounds", "leanStatus": "axiom", "id": "Liu Hui", "status": "live", "doi": None},
    {"axis": "madhava",           "band": "introspection", "floor": 0.90, "slug": "madhava-bound",
     "lean": "madhavaRemainderBound_nonneg", "leanStatus": "theorem", "id": "Mādhava", "status": "live", "doi": None},
    {"axis": "summation",         "band": "introspection", "floor": 0.90, "slug": "summation-invariant",
     "lean": "khipuReceipt_checksum_invariant", "leanStatus": "theorem", "id": "Khipu", "status": "live", "doi": None},
    {"axis": "internal-feedback", "band": "introspection", "floor": 0.90, "slug": None,
     "lean": "internal_feedback_integrity", "leanStatus": "theorem", "id": "A37", "status": "ts-only",
     "doi": "10.1016/j.neuron.2011.01.019"},
]

# Anchor-formula metadata for the per-anatomy formula cards (Lean + DOI + status).
ANCHORS: Dict[str, List[Dict[str, Any]]] = {
    "yuyay-13":      [{"id": a["id"], "name": a["axis"], "lean": a["lean"],
                       "leanStatus": a["leanStatus"], "status": a["status"],
                       "severity": "enforced" if a["band"] != "introspection" else "advisory",
                       "doi": a["doi"], "axis": "YUYAY"} for a in YUYAY_13],
    "khipu-chain": [
        {"id": "A6", "name": "HashChainIntegrity", "lean": "hashChainIntegrity", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "hash-chain-integrity", "axis": "YAWAR", "doi": None},
        {"id": "A1", "name": "SummationInvariant", "lean": "khipuReceipt_checksum_invariant", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "summation-invariant", "axis": "YAWAR", "doi": None},
        {"id": "A4", "name": "DualWitnessDisjointness", "lean": "dualWitnessDisjointness", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "dual-witness-disjointness", "axis": "YAWAR", "doi": None},
    ],
    "immune": [
        {"id": "A14", "name": "HALOY", "lean": "haloy_halt_on_lambda", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "SENTRA", "doi": None},
        {"id": "A7", "name": "BekensteinBound", "lean": "bekensteinBound", "leanStatus": "theorem",
         "status": "ts-only", "severity": "advisory", "axis": "SENTRA", "doi": "10.1103/PhysRevD.23.287"},
        {"id": "A2", "name": "MoralGroundingFloor", "lean": "moralGroundingFloor", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "YUYAY", "doi": None},
        {"id": "A3", "name": "MeasurabilityHonestyFloor", "lean": "measurabilityHonestyFloor", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "YUYAY", "doi": None},
        {"id": "A5", "name": "DeterministicReplay", "lean": "deterministicReplay", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "deterministic-replay", "axis": "UNAY", "doi": None},
        {"id": "A8", "name": "FalsePosition", "lean": "false_position_correct", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "false-position", "axis": "YUYAY", "doi": None},
        {"id": "A9", "name": "LiuHuiPi", "lean": "sideSquared_bounds", "leanStatus": "axiom",
         "status": "live", "severity": "advisory", "slug": "liu-hui-pi", "axis": "SUMAQ", "doi": None},
        {"id": "A10", "name": "MadhavaBound", "lean": "madhavaRemainderBound_nonneg", "leanStatus": "theorem",
         "status": "live", "severity": "enforced", "slug": "madhava-bound", "axis": "SUMAQ", "doi": None},
    ],
    "lambda-spine": [
        {"id": "A12", "name": "LambdaConvergence", "lean": "lambdaConvergence_conjecture", "leanStatus": "conjecture",
         "status": "ts-only", "severity": "advisory", "axis": "LAMBDA",
         "note": "Λ Conjecture 1 — NOT a discharged theorem.", "doi": None},
        {"id": "A11", "name": "SoundnessAxiom", "lean": "soundnessAxiom", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "LAMBDA", "doi": None},
    ],
    "wires": [
        {"id": "A13", "name": "KallpaEnergyAxis", "lean": "kallpaEnergyAxis", "leanStatus": "axiom",
         "status": "ts-only", "severity": "enforced", "axis": "KALLPA", "doi": None},
    ],
    "nervous": [
        {"id": "OTel", "name": "Observability (no anchor)", "lean": "—", "leanStatus": "infrastructure",
         "status": "live", "severity": "advisory", "axis": "VSP", "doi": None},
    ],
}

# Brain (Amaru) anchors referenced by the composed body view (built on amaru by sibling agent).
BRAIN_ANCHORS = [
    {"id": "A36", "name": "DualStreamRoutingAxiom", "lean": "dualStreamRoutingAxiom",
     "leanStatus": "axiom", "status": "ts-only", "severity": "advisory", "axis": "AMARU", "doi": "10.1038/nrn2113"},
    {"id": "A37", "name": "InternalFeedbackIntegrity", "lean": "internal_feedback_integrity",
     "leanStatus": "theorem", "status": "ts-only", "severity": "enforced", "axis": "AMARU",
     "doi": "10.1016/j.neuron.2011.01.019"},
    {"id": "A38", "name": "HierarchicalLinearizationRoundTrip", "lean": "hierarchicalLinearizationRoundTrip",
     "leanStatus": "axiom", "status": "ts-only", "severity": "advisory", "axis": "AMARU",
     "doi": "Hickok 2025 (10.1162/jocn_a_02143)"},
]




def yuyay_13_vote(opts: Dict[str, Any], ns: str = "a11oy") -> Dict[str, Any]:
    """Explicit write: evaluate fixed samples/advisory scores and receipt the result.

    Sample ALLOW contributes 1.0 and DENY contributes below-floor, preserving the
    existing math. The aggregate is advisory and never execution admission.
    """
    opts = _validate_action("heart", opts)
    v4 = _write_dependency("a11oy_v4_formulas", _V4)
    sf = _write_dependency("szl_formulas", _SF)
    scores = opts.get("scores") or {}
    axis_results: List[Dict[str, Any]] = []
    floors = sf.axis_floors() if (sf and hasattr(sf, "axis_floors")) else [0.95, 0.95] + [0.90] * 11
    if not isinstance(floors, (list, tuple)) or len(floors) != 13 or any(not _finite(x) or not 0 <= x <= 1 for x in floors):
        raise ValueError("invalid sample floors")
    lam_inputs: List[float] = []
    for i, a in enumerate(YUYAY_13):
        floor = floors[i] if i < len(floors) else a["floor"]
        entry = {"axis": a["axis"], "band": a["band"], "floor": floor,
                 "lean": a["lean"], "leanStatus": a["leanStatus"], "id": a["id"],
                 "status": a["status"], "doi": a["doi"]}
        if a["status"] == "live" and a.get("slug") and v4 is not None:
            sample = None
            try:
                rec = v4._BY_SLUG.get(a["slug"]) if hasattr(v4, "_BY_SLUG") else None
                sample = (rec or {}).get("sample")
                cfg = (rec or {}).get("config")
                res = v4.evaluate(a["slug"], sample or {}, cfg)
                verdict = res.get("verdict") if res.get("verdict") in {"ALLOW", "DENY"} else None
                score = 1.0 if verdict == "ALLOW" else max(0.0, floor - 0.15)
                entry.update({"evaluator": "sample", "slug": a["slug"], "verdict": verdict,
                              "score": round(score, 4),
                              "signature_verification": "NOT_PERFORMED"})
            except Exception:
                entry.update({"evaluator": "unavailable", "error": "SAMPLE_EVALUATOR_UNAVAILABLE",
                              "score": float(scores.get(a["axis"], floor))})
        else:
            # ts-only / no live evaluator — HONEST: not run, advisory score from caller (default floor)
            entry.update({"evaluator": "advisory",
                          "score": float(scores.get(a["axis"], floor)),
                          "note": "ts-only — not evaluated by a live Python gate; advisory."})
        lam_inputs.append(entry["score"])
        axis_results.append(entry)

    lam = round(min(lam_inputs), 6) if lam_inputs else 0.0
    passing = all(r["score"] >= r["floor"] for r in axis_results)
    body = {
        "protocol": "a11oy", "anatomy": "heart", "organ_name": "Yuyay-v3 (13-axis)",
        "tool_name": "anatomy.yuyay13.vote", "event_type": "YUYAY13_VOTE",
        "axis_count": 13, "lambda_aggregate": lam,
        "lambda_status": "Conjecture 1 (NOT a theorem)", "passing": passing,
        "axes": axis_results, "actor_id": "NOT_ESTABLISHED", "actor_role": "OPERATOR_GATE_ADMITTED",
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT,
        "evidence_class": "SAMPLE", "input_scope": "ADVISORY_SCORES_AND_EVALUATOR_SAMPLES",
        "execution_authorized": False, "execution_performed": False,
        "joules_measured": None, "energy_label": "UNAVAILABLE",
    }
    rec = _khipu_emit("yuyay13.vote", body, ns=ns, organ="yuyay")
    signed = _sign({**body, "chain": {"seq": rec.get("seq"), "digest": rec.get("digest"), "prev": rec.get("prev")}})
    return {"ok": True, "anatomy": "heart", "lambda_aggregate": lam, "passing": passing,
            "axes": axis_results, "receipt": signed, "chain_receipt": rec,
            "evidence_class": "SAMPLE", "execution_authorized": False,
            "execution_performed": False, "signature_verified": False,
            "signature_verification": "NOT_PERFORMED", "joules_measured": None,
            "energy_label": "UNAVAILABLE"}

def orchestrate_routing(opts: Dict[str, Any], ns: str = "a11oy") -> Dict[str, Any]:
    """Receipt a sample minimum-cost choice; no provider routing or energy probe."""
    opts = _validate_action("wires", opts)
    routes = opts.get("routes") or [
        {"tier": "ollama-local", "energy": 0.10, "latency_ms": 120, "admissible": True},
        {"tier": "mistral", "energy": 0.35, "latency_ms": 240, "admissible": True},
        {"tier": "anthropic-opus", "energy": 0.95, "latency_ms": 900, "admissible": True},
    ]
    budget = float(opts.get("energy_budget", 1.0))
    admissible = [r for r in routes if r.get("admissible", True) and float(r.get("energy", 1)) <= budget]
    chosen = min(admissible, key=lambda r: float(r.get("energy", 1))) if admissible else None
    body = {
        "protocol": "a11oy", "anatomy": "wires", "organ_name": "Kallpa (energy routing)",
        "tool_name": "anatomy.kallpa.routing", "event_type": "KALLPA_ROUTE",
        "anchor": {"id": "A13", "name": "KallpaEnergyAxis", "lean": "kallpaEnergyAxis",
                   "leanStatus": "axiom", "status": "ts-only", "severity": "enforced", "axis": "KALLPA"},
        "energy_budget": budget, "routes": routes, "chosen": chosen,
        "rationale": (f"Sample choice '{chosen['tier']}' (advisory cost {chosen['energy']} ≤ budget {budget}); no route executed."
                      if chosen else "No admissible route within energy budget — HALT."),
        "actor_id": "NOT_ESTABLISHED", "actor_role": "OPERATOR_GATE_ADMITTED",
        "doctrine": DOCTRINE, "lean_commit": LEAN_COMMIT,
        "evidence_class": "SAMPLE", "admission_scope": "CALLER_ASSERTED_SAMPLE_FILTER",
        "execution_authorized": False, "execution_performed": False,
        "joules_measured": None, "energy_label": "UNAVAILABLE",
    }
    rec = _khipu_emit("kallpa.routing", body, ns=ns, organ="kallpa")
    signed = _sign({**body, "chain": {"seq": rec.get("seq"), "digest": rec.get("digest")}})
    return {"ok": True, "anatomy": "wires", "chosen": chosen, "routes": routes,
            "receipt": signed, "chain_receipt": rec, "evidence_class": "SAMPLE",
            "execution_authorized": False, "execution_performed": False,
            "signature_verified": False, "signature_verification": "NOT_PERFORMED",
            "joules_measured": None, "energy_label": "UNAVAILABLE"}

def yuyay_observation(ns: str = "a11oy") -> dict:
    return _cached_observation(ns, "heart")


def routing_observation(ns: str = "a11oy") -> dict:
    return _cached_observation(ns, "wires")


def lambda_convergence(ns: str = "a11oy") -> dict:
    vote = yuyay_observation(ns)
    data = None
    if vote["state"] == "OBSERVED":
        running, series = 1.0, []
        for axis in vote["data"]["axes"]:
            running = min(running, axis["score"])
            series.append(round(running, 6))
        data = {"lambda": vote["data"]["lambda_aggregate"], "convergence_series": series,
                "claim_status": "Conjecture 1 (NOT a theorem); sample calculation only",
                "parent_receipt_sha256": vote["receipt_sha256"]}
    return _projection(ns, "skeleton", state=vote["state"], reason=vote["reason"],
                       evidence_class=vote["evidence_class"], data=data,
                       observed_at=vote["observed_at"], age_seconds=vote["age_seconds"])


def _existing_chain_rows(ns: str, organ: str) -> tuple:
    """Peek the existing in-memory DAG under its locks; never create a DAG."""
    module = _KHIPU if _KHIPU is not None else sys.modules.get("szl_khipu")
    if module is None:
        return None, None
    registry, registry_lock = getattr(module, "_REGISTRY", None), getattr(module, "_REG_LOCK", None)
    if not isinstance(registry, dict) or registry_lock is None:
        return None, None
    with registry_lock:
        dag = registry.get(f"{ns}/{organ}")
    if dag is None:
        return None, None
    lock, chain = getattr(dag, "_lock", None), getattr(dag, "_chain", None)
    if lock is None or not isinstance(chain, list):
        raise ValueError("chain shape unavailable")
    fields = ("organ", "ns", "seq", "action", "payload_digest", "ts", "prev", "digest")
    with lock:
        total = len(chain)
        rows = []
        for row in chain[-MAX_CHAIN_RECORDS:]:
            if not isinstance(row, dict) or any(key not in row for key in fields):
                raise ValueError("invalid retained record")
            # Only scalar hash inputs are admitted; no payload or signature body.
            copied = {key: row[key] for key in fields}
            if any(type(v) not in (str, int, float) for v in copied.values()):
                raise ValueError("invalid retained record scalar")
            rows.append(copied)
    return rows, total


def khipu_chain(ns: str = "a11oy", since: float = 0.0, organ: str = "yuyay") -> dict:
    if not _finite(since) or since < 0:
        return _projection(ns, "blood", reason="INVALID_SINCE")
    if organ not in {"yuyay", "kallpa", "anatomy"}:
        return _projection(ns, "blood", reason="INVALID_CHAIN_ORGAN")
    try:
        rows, total = _existing_chain_rows(ns, organ)
        if not rows:
            return _projection(ns, "blood", reason="NO_CHAIN_RECORDS")
        for row in rows:
            if (row["organ"] != organ or row["ns"] != ns
                    or type(row["seq"]) is not int or row["seq"] < 0
                    or not _finite(row["ts"]) or row["ts"] < 0
                    or not isinstance(row["action"], str) or not 1 <= len(row["action"]) <= 120
                    or any(not isinstance(row[key], str) or not _DIGEST.fullmatch(row[key])
                           for key in ("payload_digest", "prev", "digest"))):
                raise ValueError("invalid retained record")
        now = time.time()
        if any(row["ts"] > now for row in rows):
            return _projection(ns, "blood", reason="CHAIN_CLOCK_UNAVAILABLE")
        age = now - rows[-1]["ts"]
        observed_at = _utc_at(rows[-1]["ts"])
        if age > OBSERVATION_TTL_SECONDS:
            return _projection(ns, "blood", state="STALE", reason="CHAIN_OBSERVATION_EXPIRED",
                               observed_at=observed_at, age_seconds=round(age, 6))
        integrity = True
        for index, row in enumerate(rows):
            inputs = {key: row[key] for key in
                      ("organ", "ns", "seq", "action", "payload_digest", "ts", "prev")}
            actual = hashlib.sha3_256(json.dumps(inputs, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            integrity = integrity and actual == row["digest"]
            if index:
                prior = rows[index - 1]
                integrity = integrity and row["prev"] == prior["digest"] and row["seq"] == prior["seq"] + 1
            elif row["seq"] == 0:
                integrity = integrity and row["prev"] == "0" * 64
        prefix_verified = rows[0]["seq"] == 0 and len(rows) == total
        visible = [row for row in rows if row["ts"] >= since]
        if not visible:
            return _projection(ns, "blood", reason="NO_CHAIN_RECORDS_IN_WINDOW")
        return _projection(
            ns, "blood", state="OBSERVED", reason="PROCESS_LOCAL_HASH_RECORDS",
            evidence_class="SAMPLE", observed_at=observed_at, age_seconds=round(age, 6),
            data={"organ": organ, "pendants": visible, "depth": total, "returned_records": len(visible),
                  "head": rows[-1]["digest"], "truncated": total > len(rows)},
            data_scope="PROCESS_LOCAL_HASH_CHAIN",
            chain_verified=bool(integrity and prefix_verified),
            chain_integrity={"state": "VERIFIED" if integrity else "INVALID",
                             "scope": "RETAINED_SUFFIX", "checked_records": len(rows),
                             "prefix_verified": bool(integrity and prefix_verified)},
        )
    except Exception:
        return _projection(ns, "blood", reason="CHAIN_READ_UNAVAILABLE")


def spans_recent(ns: str = "a11oy") -> dict:
    # recent_traces is a pure, bounded public summary of the already-loaded ring.
    # It has no namespace binding and provides no receipt or effect verification.
    module = sys.modules.get("szl_observability")
    reader = getattr(module, "recent_traces", None) if module is not None else None
    if not callable(reader):
        return _projection(ns, "nervous", reason="TRACE_COLLECTOR_UNAVAILABLE")
    try:
        rows = reader(limit=MAX_TRACE_RECORDS, slowest_first=False)
        if not isinstance(rows, list) or len(rows) > MAX_TRACE_RECORDS:
            raise ValueError("invalid trace summary")
        if not rows:
            return _projection(ns, "nervous", reason="NO_TRACE_OBSERVATIONS")
        now, recent, ages, expired = time.time(), [], [], 0
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid trace")
            trace_id, started = row.get("trace_id"), row.get("started_at")
            if (not isinstance(trace_id, str) or not 1 <= len(trace_id) <= 128
                    or not isinstance(started, str) or len(started) > 64):
                raise ValueError("invalid trace identity")
            timestamp = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("trace timezone required")
            age = now - timestamp.timestamp()
            if not _finite(age) or age < 0:
                return _projection(ns, "nervous", reason="TRACE_CLOCK_UNAVAILABLE")
            duration, count, status = row.get("duration_ms"), row.get("span_count"), row.get("status")
            if (duration is not None and (not _finite(duration) or not 0 <= duration <= 1e12)
                    or type(count) is not int or not 0 <= count <= 512
                    or status not in {"OK", "ERROR", "TIMEOUT"}):
                raise ValueError("invalid trace metadata")
            if age > OBSERVATION_TTL_SECONDS:
                expired += 1
                continue
            trace_ref = hashlib.sha256(("szl.anatomy.trace-ref/v1\0" + trace_id).encode("utf-8")).hexdigest()
            recent.append({"trace_ref": trace_ref, "name": "Process trace summary",
                           "started_at": _utc_at(timestamp.timestamp()),
                           "duration_ms": duration, "span_count": count, "status": status})
            ages.append(age)
        if not recent:
            return _projection(ns, "nervous", state="STALE", reason="TRACE_OBSERVATIONS_EXPIRED")
        oldest = max(ages)
        return _projection(
            ns, "nervous", state="OBSERVED", reason="TRACE_SUMMARIES_ONLY",
            evidence_class="SAMPLE", observed_at=_utc_at(now - oldest), age_seconds=round(oldest, 6),
            data_scope="PROCESS_WIDE_NOT_NAMESPACE_BOUND",
            data={"traces": recent, "trace_count": len(recent), "expired_rows": expired,
                  "span_count": None, "correlation_only": True},
        )
    except Exception:
        return _projection(ns, "nervous", reason="TRACE_READ_UNAVAILABLE")


def immune_observation(ns: str = "a11oy") -> dict:
    return _projection(ns, "immune", state="MODELED", reason="DECLARED_GATE_GEOMETRY_ONLY",
                       evidence_class="MODELED", data={"gate_count": len(ANCHORS["immune"]),
                                                        "gate_observations": [],
                                                        "cross_organ_probe_performed": False})


def body_composed(ns: str = "a11oy") -> dict:
    chain_reads = [khipu_chain(ns, organ=organ) for organ in ("yuyay", "kallpa")]
    blood = next((item for item in chain_reads if item["state"] == "OBSERVED"),
                 next((item for item in chain_reads if item["state"] == "STALE"), chain_reads[0]))
    observations = [yuyay_observation(ns), blood, immune_observation(ns),
                    lambda_convergence(ns), spans_recent(ns), routing_observation(ns)]
    rows = [{"anatomy": "brain", "state": "MODELED", "evidence_class": "MODELED",
             "reason": "DECLARED_GEOMETRY_ONLY", "execution_authorized": False,
             "signature_verified": False}]
    rows.extend({"anatomy": item["kind"], "state": item["state"],
                 "evidence_class": item["evidence_class"], "reason": item["reason"],
                 "execution_authorized": False, "signature_verified": False}
                for item in observations)
    available = [item for item in observations if item["state"] == "OBSERVED"]
    state = "OBSERVED" if available else "STALE" if any(item["state"] == "STALE" for item in observations) else "UNAVAILABLE"
    age = max(item["age_seconds"] for item in available) if available else None
    oldest = min(item["observed_at"] for item in available) if available else None
    return _projection(
        ns, "body", state=state, reason="PARTIAL_OBSERVATIONS_NOT_OPERATIONAL_READINESS",
        evidence_class="SAMPLE" if available else "UNAVAILABLE",
        observed_at=oldest, age_seconds=age,
        data={"anatomies": rows, "anatomy_count": len(rows),
              "observed_count": len(available), "operational_readiness": "NOT_ESTABLISHED",
              "doctrine": copy.deepcopy(DOCTRINE)},
    )


def _palette() -> Dict[str, str]:
    # Existing scene colors are retained; new status UI uses served Kanchay tokens.
    return {"heart": "0x36d399", "blood": "0xf06b6b", "immune": "0xe0457b",
            "skeleton": "0xeef2f7", "nervous": "0x4aa3ff", "wires": "0x34e7e4",
            "brain": "0xffcf5a"}


_NAV = [
    ("body-3d", "Body · observations"), ("yuyay-13", "Heart · sample scores"),
    ("khipu-chain-3d", "Blood · hash records"), ("immune-3d", "Immune · declared gates"),
    ("lambda-spine-3d", "Skeleton · sample convergence"),
    ("nervous-3d", "Nervous · trace summaries"), ("wires-3d", "Wires · sample routing"),
    ("holographic#brain", "Brain evidence"),
]


def _shell(title: str, subtitle: str, anatomy_js: str) -> str:
    template = r'''<!doctype html><html lang="en" data-surface="dark"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · SZL Anatomy 3D</title>
<!-- SPDX-License-Identifier: Apache-2.0 · © 2026 SZL Holdings.
     Three.js r128 is locally vendored under its retained MIT license. -->
<link rel="stylesheet" href="/assets/szl/szl-design-system.css">
<style>
*{box-sizing:border-box} html,body{margin:0;min-height:100%;background:var(--bg);color:var(--text);font-family:var(--font-body)}
#c{position:fixed;inset:0;width:100vw;height:100vh;display:block}
header{position:relative;z-index:6;padding:18px 22px;background:var(--surface);border-bottom:1px solid var(--border)}
h1{font-size:20px;margin:0 0 6px} .sub{font-size:13px;color:var(--text-sub);max-width:100ch}
nav{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:10px} nav a,.doi a{color:var(--link)}
#observation{position:relative;z-index:6;margin:16px 22px;padding:12px 16px;max-width:720px;background:var(--surface);border:1px solid var(--border);border-radius:10px}
#fstat{font-weight:600;overflow-wrap:anywhere} #evidence-detail{color:var(--text-sub);font-size:13px;margin:8px 0 0;white-space:pre-wrap;overflow-wrap:anywhere}
#card{position:fixed;right:18px;bottom:80px;width:min(360px,calc(100vw - 36px));max-height:50vh;overflow:auto;z-index:8;display:none;background:var(--surface-raised);color:var(--text);border:1px solid var(--border);border-radius:10px;padding:16px}
#card.open{display:block} #card h3{margin:0 0 8px;font-size:16px} #card p{margin:7px 0;font-size:13px;overflow-wrap:anywhere}
#card pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:var(--font-mono);font-size:11px;color:var(--text-sub)}
#palette{position:fixed;inset:0;z-index:20;display:none;background:var(--bg-deep)} #palette.open{display:block}
#palette .box{margin:12vh auto;width:min(520px,92vw);background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}
#palq{width:100%;background:var(--surface-alt);color:var(--text);padding:10px;border:1px solid var(--border)}
.item{display:block;width:100%;text-align:left;padding:10px;background:var(--surface);color:var(--text);border:0;cursor:pointer}.item.sel{background:var(--surface-raised)}
footer{position:fixed;bottom:0;left:0;right:0;padding:10px 22px;z-index:6;background:var(--surface);color:var(--text-sub);font-size:11px;display:flex;flex-wrap:wrap;gap:8px 18px;border-top:1px solid var(--border)}
@media(max-width:700px){header{padding:12px}h1{font-size:17px}#observation{margin:10px 12px}footer{padding:8px 12px}nav{font-size:12px}}
</style></head><body>
<canvas id="c" aria-label="Modeled anatomy geometry; runtime observations are in the text panel"></canvas>
<header><h1>__TITLE__</h1><div class="sub">__SUBTITLE__</div>
<div class="sub">Geometry is MODELED. Rotation is decorative, not execution or measured activity. Click a shape for its evidence card. Ctrl/⌘ K opens navigation.</div>
<nav aria-label="Anatomy views">__NAV_LINKS__</nav></header>
<section id="observation" aria-live="polite"><div id="fstat">UNAVAILABLE · observation not read</div><p id="evidence-detail">No execution authority or signature verification is established.</p></section>
<aside id="card" aria-label="Evidence card"></aside>
<div id="palette"><div class="box"><input id="palq" aria-label="Find an anatomy view" placeholder="Find an anatomy view"><div id="palist"></div></div></div>
<footer><span>Doctrine v11 LOCKED · exactly 8 locked formulas</span><span>Λ: Conjecture 1 (NOT a theorem)</span><span>Historical snapshot: 749/14/163 · not current proof counts</span><span>Signature verification: NOT PERFORMED</span></footer>
<script src="__THREE_SRC__"></script><script>
"use strict";
const NAV=__NAV_JSON__;
const $=s=>document.querySelector(s);
function setStat(text){const el=$("#fstat");if(el)el.textContent=String(text);}
function setDetail(text){const el=$("#evidence-detail");if(el)el.textContent=String(text);}
function textElement(tag,text){const el=document.createElement(tag);el.textContent=String(text);return el;}
function showCard(f,extra){
  const card=$("#card");card.replaceChildren();
  const field=(key,fallback="—")=>f&&typeof f[key]==="string"?f[key]:fallback;
  card.appendChild(textElement("h3",field("name",field("axis","Evidence"))));
  card.appendChild(textElement("p","ID: "+field("id")+" · "+field("status","MODELED")));
  card.appendChild(textElement("p","Historical formula metadata: "+field("leanStatus")+" · "+field("lean")));
  card.appendChild(textElement("p",field("note","Formula metadata and geometry do not establish runtime readiness.")));
  const doi=field("doi","").replace(/^https:\/\/doi[.]org\//,"");
  if(/^10[.][0-9]{4,9}\/[A-Za-z0-9][A-Za-z0-9._;()/:+-]{0,199}$/.test(doi)){
    const link=document.createElement("a");link.href="https://doi.org/"+doi;
    link.target="_blank";link.rel="noopener noreferrer";link.textContent="DOI: "+doi;
    const row=document.createElement("p");row.className="doi";row.appendChild(link);card.appendChild(row);
  }
  if(extra!==undefined&&extra!==null)card.appendChild(textElement("pre",typeof extra==="string"?extra:JSON.stringify(extra,null,2)));
  card.classList.add("open");
}
let palSel=0;
function renderPal(filter=""){
  const list=$("#palist");list.replaceChildren();
  const items=NAV.filter(n=>n.label.toLowerCase().includes(filter.toLowerCase()));
  items.forEach((n,i)=>{const item=textElement("button",n.label);item.type="button";item.className="item"+(i===palSel?" sel":"");item.onclick=()=>{location.href="/"+n.slug;};list.appendChild(item);});
  return items;
}
function closePal(){$("#palette").classList.remove("open");}
document.addEventListener("keydown",event=>{
  if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){event.preventDefault();$("#palette").classList.add("open");$("#palq").value="";palSel=0;renderPal();$("#palq").focus();}
  else if(event.key==="Escape"){closePal();$("#card").classList.remove("open");}
  else if($("#palette").classList.contains("open")){
    const items=renderPal($("#palq").value);
    if(event.key==="ArrowDown"){palSel=Math.min(palSel+1,items.length-1);renderPal($("#palq").value);}
    else if(event.key==="ArrowUp"){palSel=Math.max(0,palSel-1);renderPal($("#palq").value);}
    else if(event.key==="Enter"&&items[palSel])location.href="/"+items[palSel].slug;
  }
});
$("#palq").addEventListener("input",event=>{palSel=0;renderPal(event.target.value);});
const cv=$("#c");
const renderer=new THREE.WebGLRenderer({canvas:cv,antialias:true,alpha:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(58,1,0.1,4000);camera.position.set(0,0,300);
scene.add(new THREE.AmbientLight(0xffffff,0.85));
const light=new THREE.PointLight(0xffffff,1.1);light.position.set(120,160,200);scene.add(light);
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),pickable=[];
const observationGroup=new THREE.Group();scene.add(observationGroup);
function resize(){renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();}
window.addEventListener("resize",resize);
cv.addEventListener("click",event=>{
  mouse.x=(event.clientX/innerWidth)*2-1;mouse.y=-(event.clientY/innerHeight)*2+1;
  ray.setFromCamera(mouse,camera);const hit=ray.intersectObjects(pickable,true)[0];
  if(hit){let object=hit.object;while(object&&!object.userData.formula)object=object.parent;if(object)showCard(object.userData.formula,object.userData.extra);}
});
function clearObservation(message="UNAVAILABLE · reading observation"){
  while(observationGroup.children.length){const child=observationGroup.children[0];observationGroup.remove(child);
    child.traverse(object=>{if(object.geometry)object.geometry.dispose();if(object.material){const materials=Array.isArray(object.material)?object.material:[object.material];materials.forEach(material=>material.dispose());}});}
  for(let i=pickable.length-1;i>=0;i--)if(pickable[i].userData.observation)pickable.splice(i,1);
  $("#card").classList.remove("open");$("#card").replaceChildren();setStat(message);
  setDetail("No current observation is displayed. Execution authority and signature verification are not established.");
}
__ANATOMY_JS__
resize();
const reducedMotion=window.matchMedia("(prefers-reduced-motion: reduce)");
(function animate(){requestAnimationFrame(animate);if(!document.hidden&&!reducedMotion.matches)scene.rotation.y=Math.sin(performance.now()/18000)*0.2;renderer.render(scene,camera);})();
</script></body></html>'''
    navigation = "".join('<a href="/' + escape(slug, quote=True) + '">' + escape(label) + '</a>'
                         for slug, label in _NAV)
    replacements = {"__TITLE__": escape(title), "__SUBTITLE__": escape(subtitle),
                    "__NAV_LINKS__": navigation, "__NAV_JSON__": json.dumps(
                        [{"slug": slug, "label": label} for slug, label in _NAV]),
                    "__THREE_SRC__": THREE_SRC, "__ANATOMY_JS__": anatomy_js}
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def _observation_page(ns: str, kind: str, title: str, endpoint: str, anchors: list) -> str:
    script = r'''
const NS=__NS__,KIND=__KIND__,ENDPOINT=__ENDPOINT__,ANCHORS=__ANCHORS__;
let selectedChainOrgan="yuyay";
const COLORS={heart:0x36d399,blood:0xf06b6b,immune:0xe0457b,skeleton:0xeef2f7,nervous:0x4aa3ff,wires:0x34e7e4,brain:0xffcf5a};
const STATES=["OBSERVED","STALE","UNAVAILABLE","MODELED"];
const AXES=["sound","moral","measurability","dual-witness","deterministic-replay","hash-chain","bekenstein","robustness","false-position","liu-hui","madhava","summation","internal-feedback"];
const object=value=>value!==null&&typeof value==="object"&&!Array.isArray(value);
const number=value=>typeof value==="number"&&Number.isFinite(value);
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const text=(value,max=120)=>typeof value==="string"&&value.length<=max;
const digest=value=>typeof value==="string"&&/^[0-9a-f]{64}$/.test(value);
const signatureDigest=value=>value===null||digest(value);
const state=value=>STATES.includes(value);
const date=value=>typeof value==="string"&&value.length<=64&&Number.isFinite(Date.parse(value))&&/(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(value);
const axis=row=>object(row)&&AXES.includes(row.axis)&&number(row.score)&&row.score>=0&&row.score<=1&&number(row.floor)&&row.floor>=0&&row.floor<=1&&["sample","advisory","unavailable"].includes(row.evaluator)&&(row.verdict===null||["ALLOW","DENY"].includes(row.verdict));
function validRoute(row){return object(row)&&text(row.tier,80)&&row.tier.length>0&&number(row.energy)&&row.energy>=0&&(!("latency_ms" in row)||(number(row.latency_ms)&&row.latency_ms>=0))&&(!("admissible" in row)||typeof row.admissible==="boolean");}
function validData(data){
  if(!object(data))return false;
  if(KIND==="heart")return number(data.lambda_aggregate)&&data.lambda_aggregate>=0&&data.lambda_aggregate<=1&&typeof data.passing==="boolean"&&Array.isArray(data.axes)&&data.axes.length===13&&data.axes.every((row,i)=>axis(row)&&row.axis===AXES[i]);
  if(KIND==="skeleton")return number(data.lambda)&&data.lambda>=0&&data.lambda<=1&&Array.isArray(data.convergence_series)&&data.convergence_series.length===13&&data.convergence_series.every(value=>number(value)&&value>=0&&value<=1)&&text(data.claim_status,200)&&signatureDigest(data.parent_receipt_sha256);
  if(KIND==="immune")return data.gate_count===8&&Array.isArray(data.gate_observations)&&data.gate_observations.length===0&&data.cross_organ_probe_performed===false;
  if(KIND==="blood")return Array.isArray(data.pendants)&&data.pendants.length>0&&data.pendants.length<=60&&integer(data.depth)&&data.depth>=data.pendants.length&&data.returned_records===data.pendants.length&&digest(data.head)&&typeof data.truncated==="boolean"&&["yuyay","kallpa","anatomy"].includes(data.organ)&&data.organ===selectedChainOrgan&&data.pendants.every(row=>object(row)&&row.organ===data.organ&&row.ns===NS&&integer(row.seq)&&text(row.action)&&number(row.ts)&&row.ts>=0&&digest(row.digest)&&digest(row.prev)&&digest(row.payload_digest));
  if(KIND==="nervous")return Array.isArray(data.traces)&&data.traces.length>0&&data.traces.length<=20&&data.trace_count===data.traces.length&&integer(data.expired_rows)&&data.expired_rows<=20&&data.span_count===null&&data.correlation_only===true&&data.traces.every(row=>object(row)&&digest(row.trace_ref)&&row.name==="Process trace summary"&&date(row.started_at)&&(row.duration_ms===null||(number(row.duration_ms)&&row.duration_ms>=0))&&integer(row.span_count)&&row.span_count<=512&&["OK","ERROR","TIMEOUT"].includes(row.status));
  if(KIND==="wires")return data.routing_performed===false&&data.energy_cost_scope==="ADVISORY_INPUT"&&Array.isArray(data.routes)&&data.routes.length>0&&data.routes.length<=16&&data.routes.every(validRoute)&&new Set(data.routes.map(row=>row.tier)).size===data.routes.length&&(data.chosen===null||(validRoute(data.chosen)&&data.routes.some(row=>row.tier===data.chosen.tier&&row.energy===data.chosen.energy)));
  if(KIND==="body"){
    const organs=["brain","heart","blood","immune","skeleton","nervous","wires"];
    return Array.isArray(data.anatomies)&&data.anatomies.length===7&&new Set(data.anatomies.map(row=>row.anatomy)).size===7&&data.anatomy_count===7&&integer(data.observed_count)&&data.observed_count<=6&&data.observed_count===data.anatomies.filter(row=>row.state==="OBSERVED").length&&data.operational_readiness==="NOT_ESTABLISHED"&&data.anatomies.every(row=>object(row)&&organs.includes(row.anatomy)&&state(row.state)&&["SAMPLE","MODELED","UNAVAILABLE"].includes(row.evidence_class)&&text(row.reason,160)&&row.execution_authorized===false&&row.signature_verified===false)&&object(data.doctrine)&&data.doctrine.locked_formula_count===8;
  }
  return false;
}
function validObservation(value){
  if(!object(value)||value.schema!=="szl.anatomy.observation/v1"||value.ns!==NS||value.kind!==KIND||value.mode!=="READ_ONLY"||!state(value.state)||!["SAMPLE","MODELED","UNAVAILABLE"].includes(value.evidence_class)||!text(value.reason,160)||value.max_age_seconds!==60||value.storage_writes!==0||value.receipt_minted_on_get!==false||value.model_invoked!==false||value.execution_performed!==false||value.execution_authorized!==false||value.source_revision!==null||value.runtime_boot_id!==null||value.identity_binding!=="NOT_ESTABLISHED"||value.signature_verified!==false||value.signature_verification!=="NOT_PERFORMED"||!["NOT_ESTABLISHED","UNVERIFIED","UNSIGNED"].includes(value.receipt_signature_status)||!integer(value.signature_count)||value.signature_count>16||!signatureDigest(value.receipt_sha256)||value.joules_measured!==null||value.energy_label!=="UNAVAILABLE"||value.bounded!==true||!["PROCESS_LOCAL_NONAUTHORITATIVE","PROCESS_LOCAL_HASH_CHAIN","PROCESS_WIDE_NOT_NAMESPACE_BOUND"].includes(value.data_scope))return false;
  const chain=value.chain_integrity;
  if(!object(chain)||!["NOT_ESTABLISHED","VERIFIED","INVALID"].includes(chain.state)||!["NONE","RETAINED_SUFFIX"].includes(chain.scope)||!integer(chain.checked_records)||chain.checked_records>60||typeof chain.prefix_verified!=="boolean"||typeof value.chain_verified!=="boolean"||(value.chain_verified&&(chain.state!=="VERIFIED"||chain.checked_records===0||!chain.prefix_verified)))return false;
  if(value.age_seconds!==null&&(!number(value.age_seconds)||value.age_seconds<0))return false;
  if(value.observed_at!==null&&!date(value.observed_at))return false;
  if(value.state==="OBSERVED"){
    const wallAge=Date.now()-Date.parse(value.observed_at);
    return value.evidence_class==="SAMPLE"&&date(value.observed_at)&&number(value.age_seconds)&&value.age_seconds<=60&&wallAge>=-5000&&wallAge<=65000&&validData(value.data);
  }
  if(value.state==="MODELED")return KIND==="immune"&&value.evidence_class==="MODELED"&&validData(value.data);
  return value.data===null||(KIND==="body"&&validData(value.data));
}
function meshAt(position,color,formula,extra,observed=false,geometry=null){
  const mesh=new THREE.Mesh(geometry||new THREE.SphereGeometry(8,18,18),new THREE.MeshStandardMaterial({color,roughness:0.65,transparent:!observed,opacity:observed?0.9:0.32}));
  mesh.position.set(...position);mesh.userData.formula=formula;mesh.userData.extra=extra;mesh.userData.observation=observed;
  (observed?observationGroup:scene).add(mesh);pickable.push(mesh);return mesh;
}
function modelCard(anchor,name){return {id:anchor&&anchor.id||"model",name,lean:anchor&&anchor.lean||"—",leanStatus:anchor&&anchor.leanStatus||"infrastructure",doi:anchor&&anchor.doi||null,status:"MODELED",note:"Historical formula metadata. Geometry and motion are not live evidence or an execution grant."};}
function ringPosition(index,count,radius=78){const angle=index/count*Math.PI*2;return [Math.cos(angle)*radius,Math.sin(angle)*radius*0.8,0];}
const BODY_POS={brain:[0,100,0],heart:[0,35,0],blood:[-65,0,0],immune:[65,0,0],skeleton:[0,-30,0],nervous:[-50,-75,0],wires:[50,-75,0]};
if(KIND==="heart"||KIND==="immune"){
  ANCHORS.forEach((anchor,index)=>meshAt(ringPosition(index,ANCHORS.length),COLORS[KIND],modelCard(anchor,anchor.name+" · declared metadata"),null,false));
  if(KIND==="immune"){const torso=meshAt([0,0,-20],COLORS.immune,modelCard(null,"Modeled immune silhouette"),null,false,new THREE.SphereGeometry(45,24,24));torso.scale.set(0.9,1.6,0.5);}
}else if(KIND==="skeleton"){
  AXES.forEach((name,index)=>{const mesh=meshAt([0,90-index*15,0],COLORS.skeleton,modelCard(ANCHORS[0],name+" · modeled axis"),null,false,new THREE.TorusGeometry(9,3,10,20));mesh.rotation.x=Math.PI/2;});
}else if(KIND==="body"){
  Object.entries(BODY_POS).forEach(([name,position])=>meshAt(position,COLORS[name],modelCard(null,name+" · modeled anatomy"),null,false,new THREE.IcosahedronGeometry(16,1)));
}
function evidenceCard(name,id){return {id:id||"observation",name,status:"OBSERVED · SAMPLE",lean:"—",leanStatus:"not evaluated",note:"Observed metadata only. Signature verification was not performed; execution authority is not established."};}
function connectPositions(positions){for(let i=1;i<positions.length;i++){const geometry=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...positions[i-1]),new THREE.Vector3(...positions[i])]);observationGroup.add(new THREE.Line(geometry,new THREE.LineBasicMaterial({color:COLORS[KIND]||COLORS.nervous})));}}
function renderObservation(value){
  const data=value.data;setStat(value.state+" · "+value.evidence_class+" · "+value.reason);
  if(value.state==="MODELED"){setDetail("Eight declared gate shapes. No gate evaluation or cross-organ request was performed.");return;}
  const suffix="\nSignature verification: NOT PERFORMED. Execution authority: NOT ESTABLISHED.";
  if(KIND==="heart"){
    data.axes.forEach((row,index)=>meshAt(ringPosition(index,13,90),COLORS.heart,evidenceCard(row.axis,"sample axis"),row,true,new THREE.SphereGeometry(3+row.score*5,16,16)));
    setDetail("Sample Λ: "+data.lambda_aggregate+" · sample floors "+(data.passing?"satisfied":"not satisfied")+suffix);
  }else if(KIND==="skeleton"){
    data.convergence_series.forEach((score,index)=>meshAt([24,90-index*15,0],COLORS.skeleton,evidenceCard(AXES[index],"sample convergence"),{score,claim:data.claim_status},true));
    setDetail("Sample Λ: "+data.lambda+" · "+data.claim_status+suffix);
  }else if(KIND==="blood"){
    const positions=data.pendants.map((row,index)=>{const position=ringPosition(index,data.pendants.length,85);meshAt(position,COLORS.blood,evidenceCard(row.action,"hash record"),row,true,new THREE.TorusKnotGeometry(5,1.6,32,6));return position;});connectPositions(positions);
    setDetail("Chain: "+data.organ+" · hash records: "+data.returned_records+" · retained suffix integrity: "+value.chain_integrity.state+" · prefix verified: "+value.chain_integrity.prefix_verified+suffix);
  }else if(KIND==="nervous"){
    const positions=data.traces.map((row,index)=>{const position=ringPosition(index,data.traces.length,85);meshAt(position,COLORS.nervous,evidenceCard(row.name,"trace-ref "+row.trace_ref.slice(0,12)),row,true);return position;});connectPositions(positions);
    setDetail("Trace summaries: "+data.trace_count+" · process-wide, not namespace-bound. Opaque trace references correlate observations; raw names and IDs are withheld. They do not verify completion."+suffix);
  }else if(KIND==="wires"){
    const positions=data.routes.map((row,index)=>{const position=[(index-(data.routes.length-1)/2)*40,0,0];meshAt(position,COLORS.wires,evidenceCard(row.tier,"sample route"),row,true,new THREE.BoxGeometry(18,18,18));return position;});connectPositions(positions);
    setDetail("Sample choice: "+(data.chosen?data.chosen.tier:"none")+". No routing was performed. Measured joules: UNAVAILABLE."+suffix);
  }else if(KIND==="body"){
    data.anatomies.filter(row=>row.state==="OBSERVED").forEach(row=>meshAt(BODY_POS[row.anatomy],COLORS[row.anatomy],evidenceCard(row.anatomy,"partial observation"),row,true));
    setDetail("Partial observations: "+data.observed_count+" of "+data.anatomy_count+" anatomies. Operational readiness: NOT ESTABLISHED."+suffix);
  }
}
async function readBoundedJSON(response){
  if(!response.ok||!(response.headers.get("content-type")||"").toLowerCase().includes("application/json"))throw new Error("unavailable response");
  const advertised=response.headers.get("content-length");if(advertised!==null&&Number(advertised)>65536)throw new Error("response too large");
  const reader=response.body.getReader(),chunks=[];let size=0;
  while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>65536){await reader.cancel();throw new Error("response too large");}chunks.push(part.value);}
  const joined=new Uint8Array(size);let offset=0;chunks.forEach(chunk=>{joined.set(chunk,offset);offset+=chunk.length;});
  return JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(joined));
}
let requestEpoch=0,activeRequest=null,expiryTimer=null;
async function poll(){
  const requestStarted=performance.now();
  const epoch=++requestEpoch;if(activeRequest)activeRequest.abort();if(expiryTimer)clearTimeout(expiryTimer);
  clearObservation();const controller=new AbortController();activeRequest=controller;
  const deadline=setTimeout(()=>controller.abort(),5000);
  try{
    const readEndpoint=KIND==="blood"?ENDPOINT+"?organ="+encodeURIComponent(selectedChainOrgan):ENDPOINT;
    const response=await fetch(readEndpoint,{method:"GET",mode:"same-origin",credentials:"omit",cache:"no-store",redirect:"error",headers:{Accept:"application/json"},signal:controller.signal});
    const value=await readBoundedJSON(response);if(epoch!==requestEpoch)return;
    if(!validObservation(value))throw new Error("invalid observation contract");
    if(value.state!=="OBSERVED"&&value.state!=="MODELED"){clearObservation(value.state+" · "+value.reason);return;}
    const effectiveAge=value.state==="OBSERVED"?Math.max(value.age_seconds+(performance.now()-requestStarted)/1000,Math.max(0,(Date.now()-Date.parse(value.observed_at))/1000)):0;
    if(value.state==="OBSERVED"&&effectiveAge>=60){clearObservation("STALE · observation expired in transit");return;}
    renderObservation(value);
    if(value.state==="OBSERVED")expiryTimer=setTimeout(()=>clearObservation("STALE · observation expired"),Math.max(0,(60-effectiveAge)*1000));
  }catch(error){if(epoch===requestEpoch)clearObservation("UNAVAILABLE · observation read or schema validation failed");}
  finally{clearTimeout(deadline);if(epoch===requestEpoch)activeRequest=null;}
}
if(KIND==="blood"){const label=textElement("label","Chain scope: ");const selector=document.createElement("select");selector.id="chain-organ";selector.setAttribute("aria-label","Observed hash chain");for(const name of ["yuyay","kallpa","anatomy"]){const option=textElement("option",name);option.value=name;selector.appendChild(option);}selector.addEventListener("change",()=>{selectedChainOrgan=selector.value;poll();});label.appendChild(selector);$("#observation").appendChild(label);}
let pollTimer=null;
function stopPolling(){++requestEpoch;if(activeRequest)activeRequest.abort();activeRequest=null;if(pollTimer!==null)clearInterval(pollTimer);pollTimer=null;if(expiryTimer)clearTimeout(expiryTimer);expiryTimer=null;clearObservation("UNAVAILABLE · page inactive");}
function startPolling(){if(pollTimer!==null||document.hidden)return;poll();pollTimer=setInterval(poll,15000);}
window.addEventListener("pagehide",stopPolling);
window.addEventListener("pageshow",event=>{if(event.persisted)startPolling();});
document.addEventListener("visibilitychange",()=>{if(document.hidden)stopPolling();else startPolling();});
startPolling();
'''
    for key, value in {"__NS__": ns, "__KIND__": kind, "__ENDPOINT__": endpoint,
                       "__ANCHORS__": anchors}.items():
        script = script.replace(key, json.dumps(value).replace("<", "\\u003c"))
    return _shell(title, "Read-only observations · " + endpoint, script)


def _page_yuyay13(ns: str) -> str:
    return _observation_page(ns, "heart", "Heart — Yuyay-13",
                             f"/api/{ns}/v4/yuyay-13/vote", ANCHORS["yuyay-13"])


def _page_khipu_chain(ns: str) -> str:
    return _observation_page(ns, "blood", "Blood — Yawar hash records",
                             f"/api/{ns}/v4/khipu/chain", ANCHORS["khipu-chain"])


def _page_immune(ns: str) -> str:
    return _observation_page(ns, "immune", "Immune — declared HuKLLA gates",
                             f"/api/{ns}/v4/immune/observation", ANCHORS["immune"])


def _page_lambda_spine(ns: str) -> str:
    return _observation_page(ns, "skeleton", "Skeleton — Λ sample convergence",
                             f"/api/{ns}/v4/lambda/convergence", ANCHORS["lambda-spine"])


def _page_nervous(ns: str) -> str:
    return _observation_page(ns, "nervous", "Nervous — trace summaries",
                             f"/api/{ns}/v4/spans/recent", ANCHORS["nervous"])


def _page_wires(ns: str) -> str:
    return _observation_page(ns, "wires", "Wires — advisory routing samples",
                             f"/api/{ns}/v4/orchestrate/routing", ANCHORS["wires"])


def _page_body(ns: str) -> str:
    return _observation_page(ns, "body", "Body — bounded anatomy observations",
                             f"/api/{ns}/v4/body/composed", BRAIN_ANCHORS)


def _read_response(payload: dict, status_code: int = 200):
    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store"})


async def _run_action(request: Request, ns: str, kind: str):
    refusal = _operator_refusal(request, "Anatomy sample observation")
    if refusal is not None:
        return refusal
    try:
        body = await _action_body(request, kind)
    except (ValueError, UnicodeError, RecursionError):
        return JSONResponse({"ok": False, "status": "INVALID_INPUT",
                             "reason": "BOUNDED_FINITE_SAMPLE_REQUIRED"}, status_code=400)
    try:
        result = yuyay_13_vote(body, ns=ns) if kind == "heart" else orchestrate_routing(body, ns=ns)
    except Exception:
        return JSONResponse({"ok": False, "status": "UNAVAILABLE",
                             "reason": "SAMPLE_ACTION_FAILED", "retry_authorized": False}, status_code=503)
    try:
        _remember_observation(ns, kind, result)
        result["observation_cache"] = "PROCESS_LOCAL_NONAUTHORITATIVE"
    except Exception:
        # A cache failure must not turn an already-attempted action into a retry.
        result["observation_cache"] = "UNAVAILABLE"
    return _read_response(result)


def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    if not isinstance(ns, str) or not _NAMESPACE.fullmatch(ns):
        raise ValueError("invalid anatomy namespace")
    base = f"/api/{ns}/v4"
    paths: List[str] = []

    @app.get("/yuyay-13", response_class=HTMLResponse)
    async def _p_yuyay():
        return HTMLResponse(_page_yuyay13(ns), headers={"Cache-Control": "no-store"})
    paths.append("/yuyay-13")

    @app.get("/khipu-chain-3d", response_class=HTMLResponse)
    async def _p_khipu():
        return HTMLResponse(_page_khipu_chain(ns), headers={"Cache-Control": "no-store"})
    paths.append("/khipu-chain-3d")

    @app.get("/immune-3d", response_class=HTMLResponse)
    async def _p_immune():
        return HTMLResponse(_page_immune(ns), headers={"Cache-Control": "no-store"})
    paths.append("/immune-3d")

    @app.get("/lambda-spine-3d", response_class=HTMLResponse)
    async def _p_spine():
        return HTMLResponse(_page_lambda_spine(ns), headers={"Cache-Control": "no-store"})
    paths.append("/lambda-spine-3d")

    @app.get("/nervous-3d", response_class=HTMLResponse)
    async def _p_nervous():
        return HTMLResponse(_page_nervous(ns), headers={"Cache-Control": "no-store"})
    paths.append("/nervous-3d")

    @app.get("/wires-3d", response_class=HTMLResponse)
    async def _p_wires():
        return HTMLResponse(_page_wires(ns), headers={"Cache-Control": "no-store"})
    paths.append("/wires-3d")

    @app.get("/body-3d", response_class=HTMLResponse)
    async def _p_body():
        return HTMLResponse(_page_body(ns), headers={"Cache-Control": "no-store"})
    paths.append("/body-3d")

    @app.get("/body-3d-v6")
    async def _p_body_v6():
        from starlette.responses import RedirectResponse
        return RedirectResponse("/holographic#brainreranker", status_code=307)
    paths.append("/body-3d-v6")

    @app.post(f"{base}/yuyay-13/vote")
    async def _e_yuyay(req: Request):
        return await _run_action(req, ns, "heart")

    @app.api_route(f"{base}/yuyay-13/vote", methods=["GET", "HEAD"])
    async def _o_yuyay():
        return _read_response(yuyay_observation(ns))
    paths.append(f"{base}/yuyay-13/vote")

    @app.api_route(f"{base}/lambda/convergence", methods=["GET", "HEAD"])
    async def _e_lambda():
        return _read_response(lambda_convergence(ns))
    paths.append(f"{base}/lambda/convergence")

    @app.api_route(f"{base}/khipu/chain", methods=["GET", "HEAD"])
    async def _e_khipu(since: float = 0.0, organ: str = "yuyay"):
        payload = khipu_chain(ns, since, organ)
        return _read_response(payload, status_code=400 if payload["reason"].startswith("INVALID_") else 200)
    paths.append(f"{base}/khipu/chain")

    @app.api_route(f"{base}/spans/recent", methods=["GET", "HEAD"])
    async def _e_spans():
        return _read_response(spans_recent(ns))
    paths.append(f"{base}/spans/recent")

    @app.api_route(f"{base}/immune/observation", methods=["GET", "HEAD"])
    async def _o_immune():
        return _read_response(immune_observation(ns))
    paths.append(f"{base}/immune/observation")

    @app.post(f"{base}/orchestrate/routing")
    async def _e_routing(req: Request):
        return await _run_action(req, ns, "wires")

    @app.api_route(f"{base}/orchestrate/routing", methods=["GET", "HEAD"])
    async def _o_routing():
        return _read_response(routing_observation(ns))
    paths.append(f"{base}/orchestrate/routing")

    @app.api_route(f"{base}/body/composed", methods=["GET", "HEAD"])
    async def _e_body():
        return _read_response(body_composed(ns))
    paths.append(f"{base}/body/composed")

    @app.get("/anatomy-three.min.js")
    async def _three():
        from pathlib import Path
        for candidate in ("/app/static-vendor/three.min.js", "static-vendor/three.min.js",
                          "/app/web/three.min.js", "web/three.min.js"):
            if Path(candidate).exists():
                return FileResponse(candidate, media_type="application/javascript")
        return Response("// local Three.js vendor unavailable", media_type="application/javascript", status_code=404)
    paths.append("/anatomy-three.min.js")
    return {"registered": True, "ns": ns, "paths": paths,
            "read_schema": OBSERVATION_SCHEMA, "signature_verification": "NOT_PERFORMED"}


if __name__ == "__main__":
    print(json.dumps(body_composed(), indent=2))
