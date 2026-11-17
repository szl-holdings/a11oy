#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Content-free receipt observations; no signing, persistence or admission.

Taxonomy: services/observability. W3C context is supplied by our middleware.
Deterministic hashes use Python JSON (sorted keys, compact UTF-8, no NaN);
this profile is neither RFC 8785 canonicalization nor authentication.
Prior art: https://www.w3.org/TR/trace-context/
"""
import hashlib
import json
import re

from .middleware import parse_traceparent

SCHEMA = "szl.trace.receipt-observation/v1"
CHECKS = (
    "receipt_digest_match",
    "model_digest_match",
    "source_revision_match",
    "nemo_pre_allow",
    "nemo_text_allow",
    "nemo_post_allow",
    "unsigned_receipt_declared",
    "proposal_only",
)
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


def _unit_interval(value):
    # Check range before float conversion: huge ints must HOLD, not overflow.
    return type(value) in (int, float) and 0 <= value <= 1


def gated_minimum(scores, *, required_checks, threshold=1.0):
    """Bounded structural diagnostic only; never an action/release decision.

    Missing/extra checks, invalid policy and nonfinite/coerced scores HOLD.
    No invalid values or caller-provided key names are echoed in diagnostics.
    """
    result = {
        "schema": "szl.trace.diagnostic-minimum/v1",
        "decision": "HOLD",
        "scope": "STRUCTURAL_DIAGNOSTIC_ONLY",
        "authority": "NONE",
        "minimum": None,
        "threshold": None,
        "coverage": {"required": 0, "observed": 0},
        "reason_codes": [],
    }
    if not _unit_interval(threshold):
        result["reason_codes"] = ["INVALID_THRESHOLD"]
        return result
    result["threshold"] = float(threshold)
    if (
        type(required_checks) not in (list, tuple, set, frozenset)
        or not 1 <= len(required_checks) <= 32
        or any(type(key) is not str or not _NAME.fullmatch(key) for key in required_checks)
        or len(set(required_checks)) != len(required_checks)
    ):
        result["reason_codes"] = ["INVALID_REQUIRED_CHECKS"]
        return result
    expected = set(required_checks)
    result["coverage"]["required"] = len(expected)
    if (
        type(scores) is not dict
        or len(scores) > 32
        or any(type(key) is not str or not _NAME.fullmatch(key) for key in scores)
    ):
        result["reason_codes"] = ["INVALID_SCORES"]
        return result
    supplied = set(scores)
    result["coverage"]["observed"] = len(expected.intersection(supplied))
    reasons = result["reason_codes"]
    if expected - supplied:
        reasons.append("MISSING_REQUIRED_CHECK")
    if supplied - expected:
        reasons.append("UNEXPECTED_CHECK")
    values = [scores[key] for key in expected if key in scores]
    if any(not _unit_interval(value) for value in values):
        reasons.append("INVALID_SCORE")
    if reasons:
        return result
    result["minimum"] = float(min(values))
    if result["minimum"] < result["threshold"]:
        reasons.append("BELOW_THRESHOLD")
    else:
        result["decision"] = "PASS"
    return result


def unavailable_observation():
    """Fixed diagnostic for an observation failure; never echo exceptions."""
    return {
        "schema": SCHEMA,
        "state": "UNAVAILABLE",
        "authority": "NONE",
        "delivery": "RESPONSE_SIDECAR_ONLY",
        "reason_codes": ["OBSERVATION_UNAVAILABLE"],
    }


def receipt_observation(
    *, traceparent, receipt_sha256, model_sha256, source_revision, checks
):
    """Observe host-computed receipt consistency on the current server span.

    The request route supplies CHECKS after inference has passed existing gates.
    A PASS is structural consistency, not signature/proof verification.
    Collector delivery is not inferred from exporter configuration.
    """
    result = unavailable_observation()
    diagnostic = gated_minimum(checks, required_checks=CHECKS)
    result["diagnostic"] = diagnostic
    if diagnostic["decision"] != "PASS":
        result["reason_codes"] = ["STRUCTURAL_CONSISTENCY_HOLD"]
        return result
    context = parse_traceparent(traceparent)
    if context is None:
        result["reason_codes"] = ["TRACE_CONTEXT_UNAVAILABLE"]
        return result
    if any(
        type(value) is not str or not pattern.fullmatch(value)
        for value, pattern in (
            (receipt_sha256, _SHA256),
            (model_sha256, _SHA256),
            (source_revision, _REVISION),
        )
    ):
        result["reason_codes"] = ["INVALID_IDENTITY"]
        return result
    event = {
        "schema": SCHEMA,
        "state": "OBSERVED",
        "operation": "governed_inference_proposal",
        "authority": "NONE",
        "signature_status": "UNSIGNED_DERIVED_OBSERVATION",
        "persistence": "RESPONSE_ONLY",
        "delivery": "RESPONSE_SIDECAR_ONLY",
        "collector_delivery": "UNVERIFIED",
        "trace_context_source": "SERVER_MIDDLEWARE",
        "trace_id": context["trace_id"],
        "span_id": context["parent_id"],
        "trace_flags": context["flags"],
        "receipt_sha256": receipt_sha256,
        "model_sha256": model_sha256,
        "source_revision": source_revision,
        "diagnostic": diagnostic,
    }
    encoded = json.dumps(
        event, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    event["observation_sha256"] = hashlib.sha256(encoded).hexdigest()
    return event
