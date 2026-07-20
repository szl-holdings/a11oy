#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
"""Pure, bounded decomposition of paired observations under an involution.

Taxonomy home: provenance / EvidenceOS analysis.

This module is a clean-room systems adaptation of a general symmetry idea used in
the cited transport study.  It copies no article prose, figure, or implementation.
The caller declares a permutation ``P`` and supplies a left observation ``x`` and
an observation ``y`` collected on the transformed surface.  With the convention
``(P v)[i] = v[P[i]]`` and a required involution ``P(P(i)) = i``, the probe aligns
the transformed observation and computes::

    y_aligned = P^-1 y
    S = (x + y_aligned) / 2
    A = (x - y_aligned) / 2

The algebraic reconstruction identities are labelled PROVEN.  A concrete result
is MODELED because it is derived from caller-supplied observations, not measured
by this module.  The motivating experimental findings remain REPORTED.

Primary-source citations:
  * https://doi.org/10.1038/s41467-026-75369-y
  * https://doi.org/10.5281/zenodo.17050703

The probe is deliberately pure: it performs no file or network I/O, emits no
signature, writes no receipt, and invokes no effector.
"""

import hashlib
import json
import math
import numbers
from collections.abc import Sequence


SCHEMA = "szl.evidenceos.involution-probe.v1"
MAX_DIMENSION = 4096
MAX_ABS_VALUE = 1.0e12
MAX_PAIR_ID_BYTES = 256

LABEL_PROVEN = "PROVEN"
LABEL_MODELED = "MODELED"
LABEL_REPORTED = "REPORTED"

VERDICT_DECOMPOSED = "DECOMPOSED"
VERDICT_REFUSED = "REFUSED"

ARTICLE_DOI = "10.1038/s41467-026-75369-y"
DATA_CODE_DOI = "10.5281/zenodo.17050703"

_CITATIONS = (
    {
        "kind": "article",
        "doi": ARTICLE_DOI,
        "url": "https://doi.org/" + ARTICLE_DOI,
        "evidence_label": LABEL_REPORTED,
    },
    {
        "kind": "data-and-code",
        "doi": DATA_CODE_DOI,
        "url": "https://doi.org/" + DATA_CODE_DOI,
        "evidence_label": LABEL_REPORTED,
    },
)


class _Refusal(ValueError):
    """Internal, bounded validation refusal converted to a public result."""

    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _canonical_for_digest(value):
    """Return a JSON-safe projection with platform-stable finite-float encoding."""
    if isinstance(value, float):
        # Validation guarantees finiteness.  Normalizing negative zero prevents two
        # numerically identical decompositions from receiving different digests.
        normalized = 0.0 if value == 0.0 else value
        return {"float_hex": normalized.hex()}
    if isinstance(value, dict):
        return {str(key): _canonical_for_digest(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical_for_digest(item) for item in value]
    return value


def _stable_digest(payload: dict) -> str:
    canonical = json.dumps(
        _canonical_for_digest(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utf8_size(value: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise _Refusal("PAIR_ID_INVALID", "pair_id must be valid UTF-8 text") from exc


def _validate_pair_id(pair_id) -> str:
    if not isinstance(pair_id, str) or not pair_id.strip():
        raise _Refusal("PAIR_ID_REQUIRED", "pair_id must be a non-blank string")
    if _utf8_size(pair_id) > MAX_PAIR_ID_BYTES:
        raise _Refusal("PAIR_ID_TOO_LARGE", "pair_id exceeds the byte bound")
    return pair_id


def _as_bounded_vector(name: str, value) -> tuple[float, ...]:
    if value is None:
        raise _Refusal("PAIR_MISSING", f"{name} is required")
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise _Refusal("VECTOR_INVALID", f"{name} must be a finite numeric sequence")
    size = len(value)
    if size < 1 or size > MAX_DIMENSION:
        raise _Refusal("DIMENSION_OUT_OF_BOUNDS", f"{name} dimension is outside bounds")

    out: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, numbers.Real):
            raise _Refusal("VECTOR_INVALID", f"{name} contains a non-real value")
        number = float(item)
        if not math.isfinite(number):
            raise _Refusal("VECTOR_NONFINITE", f"{name} contains a non-finite value")
        if abs(number) > MAX_ABS_VALUE:
            raise _Refusal("VALUE_OUT_OF_BOUNDS", f"{name} exceeds the magnitude bound")
        out.append(0.0 if number == 0.0 else number)
    return tuple(out)


def _as_involution(permutation, dimension: int) -> tuple[int, ...]:
    if permutation is None:
        raise _Refusal("PERMUTATION_REQUIRED", "a declared permutation is required")
    if (isinstance(permutation, (str, bytes, bytearray))
            or not isinstance(permutation, Sequence)):
        raise _Refusal("PERMUTATION_INVALID", "permutation must be an integer sequence")
    if len(permutation) != dimension:
        raise _Refusal("DIMENSION_MISMATCH", "permutation and vectors must share a dimension")
    if any(isinstance(index, bool) or not isinstance(index, int)
           for index in permutation):
        raise _Refusal("PERMUTATION_INVALID", "permutation indices must be integers")

    result = tuple(permutation)
    if any(index < 0 or index >= dimension for index in result):
        raise _Refusal("PERMUTATION_OUT_OF_RANGE", "permutation index is outside the vector")
    if len(set(result)) != dimension:
        raise _Refusal("PERMUTATION_NOT_BIJECTIVE", "permutation must be bijective")
    if any(result[result[index]] != index for index in range(dimension)):
        raise _Refusal("PERMUTATION_NOT_INVOLUTION", "declared permutation does not satisfy P^2=I")
    return result


def _apply_permutation(vector: tuple[float, ...], permutation: tuple[int, ...]) -> tuple[float, ...]:
    return tuple(vector[index] for index in permutation)


def _linf(values) -> float:
    return max((abs(value) for value in values), default=0.0)


def _labels() -> dict:
    return {
        "algebraic_contract": LABEL_PROVEN,
        "computed_observation": LABEL_MODELED,
        "external_findings": LABEL_REPORTED,
        "note": (
            "PROVEN is limited to the finite-vector identities checked here; "
            "MODELED is a deterministic transform of caller-supplied observations; "
            "REPORTED identifies claims made by the cited primary sources."
        ),
        "adds_to_locked_8": 0,
    }


def _refusal(pair_id, code: str, reason: str) -> dict:
    safe_pair_id = None
    if isinstance(pair_id, str):
        try:
            if _utf8_size(pair_id) <= MAX_PAIR_ID_BYTES:
                safe_pair_id = pair_id
        except _Refusal:
            pass
    core = {
        "schema": SCHEMA,
        "ok": False,
        "verdict": VERDICT_REFUSED,
        "pair_id": safe_pair_id,
        "refusal": {"code": code, "reason": reason},
        "labels": _labels(),
        "citations": [dict(citation) for citation in _CITATIONS],
    }
    core["digest"] = {
        "algorithm": "sha256",
        "stable_content_sha256": _stable_digest(core),
        "signed": False,
    }
    return core


def evaluate_involution_pair(*, pair_id, left_observation, transformed_observation,
                             permutation) -> dict:
    """Validate and decompose one declared involution pair.

    Returns a deterministic ``DECOMPOSED`` result or a deterministic ``REFUSED``
    result for an incomplete, unbounded, non-finite, mismatched, non-bijective, or
    non-involutive input.  Programmer faults are not hidden by a broad exception.
    """
    try:
        validated_pair_id = _validate_pair_id(pair_id)
        left = _as_bounded_vector("left_observation", left_observation)
        transformed = _as_bounded_vector("transformed_observation", transformed_observation)
        if len(left) != len(transformed):
            raise _Refusal("PAIR_DIMENSION_MISMATCH", "paired vectors must share a dimension")
        involution = _as_involution(permutation, len(left))
    except _Refusal as refusal:
        return _refusal(pair_id, refusal.code, refusal.reason)

    # P^-1 is P because validation established P^2=I.
    aligned = _apply_permutation(transformed, involution)
    symmetric = tuple((a + b) / 2.0 for a, b in zip(left, aligned))
    antisymmetric = tuple((a - b) / 2.0 for a, b in zip(left, aligned))

    reconstructed_left = tuple(s + a for s, a in zip(symmetric, antisymmetric))
    reconstructed_aligned = tuple(s - a for s, a in zip(symmetric, antisymmetric))
    reconstructed_transformed = _apply_permutation(reconstructed_aligned, involution)

    permutation_closure_residual = max(
        (abs(involution[involution[index]] - index) for index in range(len(involution))),
        default=0,
    )
    reconstruction_residual = _linf(
        [actual - reconstructed for actual, reconstructed in zip(left, reconstructed_left)]
        + [actual - reconstructed
           for actual, reconstructed in zip(transformed, reconstructed_transformed)]
    )
    paired_delta = _linf(a - b for a, b in zip(left, aligned))

    input_contract = {
        "pair_id": validated_pair_id,
        "dimension": len(left),
        "permutation": list(involution),
        "left_observation": list(left),
        "transformed_observation": list(transformed),
        "permutation_convention": "(P v)[i] = v[P[i]]",
    }
    result_core = {
        "schema": SCHEMA,
        "ok": True,
        "verdict": VERDICT_DECOMPOSED,
        "pair_id": validated_pair_id,
        "bounds": {
            "max_dimension": MAX_DIMENSION,
            "max_abs_value": MAX_ABS_VALUE,
            "max_pair_id_bytes": MAX_PAIR_ID_BYTES,
        },
        "contract": {
            "permutation_convention": "(P v)[i] = v[P[i]]",
            "requires_involution": True,
            "aligned_transformed": "P^-1(transformed_observation)",
            "symmetric": "(left + aligned_transformed) / 2",
            "antisymmetric": "(left - aligned_transformed) / 2",
        },
        "input": {
            "dimension": len(left),
            "permutation": list(involution),
        },
        "decomposition": {
            "aligned_transformed": list(aligned),
            "symmetric": list(symmetric),
            "antisymmetric": list(antisymmetric),
        },
        "closure": {
            "permutation_squared_identity": permutation_closure_residual == 0,
            "permutation_closure_residual": permutation_closure_residual,
            "pair_reconstruction_residual_linf": reconstruction_residual,
            "paired_delta_linf": paired_delta,
        },
        "labels": _labels(),
        "citations": [dict(citation) for citation in _CITATIONS],
        "effects": {
            "writes": 0,
            "signatures": 0,
            "effectors": 0,
            "network_calls": 0,
        },
    }
    result_core["digests"] = {
        "algorithm": "sha256",
        "input_sha256": _stable_digest({"schema": SCHEMA, "input": input_contract}),
        "result_sha256": _stable_digest(result_core),
        "signed": False,
    }
    return result_core


__all__ = [
    "ARTICLE_DOI",
    "DATA_CODE_DOI",
    "LABEL_MODELED",
    "LABEL_PROVEN",
    "LABEL_REPORTED",
    "MAX_ABS_VALUE",
    "MAX_DIMENSION",
    "MAX_PAIR_ID_BYTES",
    "SCHEMA",
    "VERDICT_DECOMPOSED",
    "VERDICT_REFUSED",
    "evaluate_involution_pair",
]


def register(app, ns="a11oy"):
    """Register the read-only contract view and bounded evaluation endpoint."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    base = "/api/%s/v1/evidenceos/involution" % ns

    def _json_response(body, status_code=200):
        response = JSONResponse(body, status_code=status_code)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get(base + "/info")
    async def _involution_info():  # noqa: ANN202
        return _json_response({
            "schema": SCHEMA,
            "service_state": "LIVE",
            "effectors": 0,
            "writes": 0,
            "max_dimension": MAX_DIMENSION,
            "permutation_contract": "(P v)[i] = v[P[i]] and P^2 = I",
            "labels": _labels(),
            "citations": [dict(citation) for citation in _CITATIONS],
            "receipt_policy": "pure computation; content digest returned; no state write and no signature minted",
        })

    @app.post(base + "/evaluate")
    async def _involution_evaluate(request: Request):  # noqa: ANN202
        raw = await request.body()
        if len(raw) > 200_000:
            return _json_response({"ok": False, "verdict": VERDICT_REFUSED,
                                   "refusal": {"code": "BODY_TOO_LARGE", "reason": "request exceeds 200000 bytes"}},
                                  status_code=413)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _json_response({"ok": False, "verdict": VERDICT_REFUSED,
                                   "refusal": {"code": "INVALID_JSON", "reason": "request body must be JSON"}},
                                  status_code=400)
        if not isinstance(body, dict):
            return _json_response({"ok": False, "verdict": VERDICT_REFUSED,
                                   "refusal": {"code": "INVALID_BODY", "reason": "request body must be an object"}},
                                  status_code=400)
        allowed = {"pair_id", "left_observation", "transformed_observation", "permutation"}
        unknown = sorted(str(key) for key in body if key not in allowed)
        if unknown:
            return _json_response({"ok": False, "verdict": VERDICT_REFUSED,
                                   "refusal": {"code": "UNKNOWN_FIELDS", "reason": "unexpected fields", "fields": unknown}},
                                  status_code=400)
        result = evaluate_involution_pair(
            pair_id=body.get("pair_id"),
            left_observation=body.get("left_observation"),
            transformed_observation=body.get("transformed_observation"),
            permutation=body.get("permutation"),
        )
        return _json_response(result, status_code=200 if result["ok"] else 422)

    return {"ok": True, "routes": [base + "/info", base + "/evaluate"]}


__all__.append("register")
