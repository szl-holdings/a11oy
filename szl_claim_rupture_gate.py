#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""SZL Claim Rupture Gate -- fail-closed claim-integrity assessment.

This module is deliberately smaller than a fact-checker.  It does not browse, retrieve,
infer truth, resolve contradictions, or calculate semantic uncertainty.  It accepts
explicit claim atoms, evidence/provenance references, accountable consequence owners,
and *externally supplied* factuality/uncertainty signals.  It then applies a transparent,
deterministic rubric that decides whether a claim may be carried forward for human review.

The contract is honest by construction:

* raw prose atomization is STRUCTURAL-SPLIT-ONLY and must be human reviewed;
* a claimed evidence label is never upgraded;
* missing provenance, ownership, malformed signals, or contradictions fail closed;
* VERIFIED requires traceable verification for every evidence reference plus an external,
  traceable VERIFIED factuality signal;
* every result is PROPOSAL_ONLY with zero effectors;
* receipts are unsigned SHA-256 content digests, not signatures or truth certificates.

This adds no theorem and changes no locked formula.  It is pure Python stdlib and performs
no I/O, persistence, networking, authentication, signing, or mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence


VERIFIED = "VERIFIED"
SUPPORTED = "SUPPORTED"
UNCERTAIN = "UNCERTAIN"
REFUTED = "REFUTED"
UNKNOWN = "UNKNOWN"
CLAIM_STATES = (VERIFIED, SUPPORTED, UNCERTAIN, REFUTED, UNKNOWN)

PROPOSAL_ONLY = "PROPOSAL_ONLY"
NO_EFFECTORS = 0
SEMANTIC_UNCERTAINTY_ABSTAIN_THRESHOLD = 0.66
MODULE_ID = "szl-claim-rupture-gate"
CONTRACT_VERSION = "1.0.0"

# HTTP adapters may apply a smaller byte limit before decoding JSON.  These limits are
# the semantic contract after decoding: they bound every collection and string that the
# pure evaluator can traverse.  They are mirrored in schemas/evidenceos and pinned by
# tests so a route cannot silently accept more work than the core contract promises.
MAX_ATOMIZE_TEXT_CHARS = 32_768
MAX_ATOMIZE_CANDIDATES = 32
MAX_CLAIMS = 32
MAX_EVIDENCE_REFS_PER_CLAIM = 8
MAX_CONTRADICTIONS = 32
MAX_EXTERNAL_SIGNALS = 32
MAX_CLAIM_IDS_PER_CONTRADICTION = 32
MAX_ID_CHARS = 128
MAX_STATEMENT_CHARS = 4_096
MAX_REFERENCE_CHARS = 512
MAX_METHOD_CHARS = 256
MAX_ACCOUNTABILITY_SCOPE_CHARS = 1_024

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SPLIT_RE = re.compile(r"(?:\r?\n)+|(?<=[.!?;])\s+")


class ClaimContractError(ValueError):
    """A deterministic request-contract refusal.

    This is deliberately a ``ValueError`` so thin HTTP adapters can map it to 422
    without importing a web framework into this pure module.  It is not an epistemic
    claim verdict: structurally valid but incomplete evidence still reaches the gate and
    receives the appropriate RG-* abstention code.
    """


def _contract_error(path: str, message: str) -> ClaimContractError:
    return ClaimContractError(f"{path}: {message}")


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _contract_error(path, "must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extras = sorted(str(key) for key in value if not isinstance(key, str) or key not in allowed)
    if extras:
        raise _contract_error(path, f"unknown field(s): {', '.join(extras)}")


def _string(
    value: Any,
    path: str,
    *,
    maximum: int,
    nonblank: bool = False,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str):
        raise _contract_error(path, "must be a string")
    if len(value) > maximum:
        raise _contract_error(path, f"must be at most {maximum} characters")
    if nonblank and not value.strip():
        raise _contract_error(path, "must not be blank")
    if pattern is not None and not pattern.fullmatch(value):
        raise _contract_error(path, "has an invalid format")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise _contract_error(path, "must be a boolean")
    return value


def _number(value: Any, path: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _contract_error(path, "must be a number")
    normalized = float(value)
    if not minimum <= normalized <= maximum:
        raise _contract_error(path, f"must be between {minimum} and {maximum}")
    return normalized


def _array(value: Any, path: str, *, maximum: int) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise _contract_error(path, "must be an array")
    if len(value) > maximum:
        raise _contract_error(path, f"must contain at most {maximum} items")
    return value


def _optional_string(
    source: Mapping[str, Any],
    key: str,
    path: str,
    *,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str | None:
    if key not in source:
        return None
    return _string(source[key], f"{path}.{key}", maximum=maximum, pattern=pattern)


def _identifier(value: Any, path: str) -> str:
    """Return the canonical identifier used by all cross-record comparisons."""
    return _string(
        value,
        path,
        maximum=MAX_ID_CHARS,
        nonblank=True,
    ).strip()


def _parse_provenance(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(raw, {"source_id", "content_sha256", "receipt_ref"}, path)
    out: dict[str, Any] = {}
    source_id = _optional_string(raw, "source_id", path, maximum=MAX_REFERENCE_CHARS)
    digest = _optional_string(
        raw, "content_sha256", path, maximum=64, pattern=_SHA256_RE,
    )
    receipt_ref = _optional_string(raw, "receipt_ref", path, maximum=MAX_REFERENCE_CHARS)
    if source_id is not None:
        out["source_id"] = source_id
    if digest is not None:
        out["content_sha256"] = digest
    if receipt_ref is not None:
        out["receipt_ref"] = receipt_ref
    return out


def _parse_owner(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(raw, {"owner_id", "accountability_scope"}, path)
    out: dict[str, Any] = {}
    owner_id = _optional_string(raw, "owner_id", path, maximum=MAX_ID_CHARS)
    scope = _optional_string(
        raw, "accountability_scope", path, maximum=MAX_ACCOUNTABILITY_SCOPE_CHARS,
    )
    if owner_id is not None:
        out["owner_id"] = owner_id
    if scope is not None:
        out["accountability_scope"] = scope
    return out


def _parse_evidence(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(
        raw,
        {"reference_id", "evidence_state", "provenance", "verification_ref"},
        path,
    )
    out: dict[str, Any] = {}
    reference_id = _optional_string(raw, "reference_id", path, maximum=MAX_ID_CHARS)
    if reference_id is not None:
        out["reference_id"] = reference_id
    if "evidence_state" in raw:
        state = _string(raw["evidence_state"], f"{path}.evidence_state", maximum=16)
        if state not in CLAIM_STATES:
            raise _contract_error(f"{path}.evidence_state", "must be a known claim state")
        out["evidence_state"] = state
    if "provenance" in raw:
        out["provenance"] = _parse_provenance(raw["provenance"], f"{path}.provenance")
    verification_ref = _optional_string(
        raw, "verification_ref", path, maximum=MAX_REFERENCE_CHARS,
    )
    if verification_ref is not None:
        out["verification_ref"] = verification_ref
    return out


def _parse_claim(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(
        raw,
        {"claim_id", "statement", "atomic", "evidence_refs", "consequence_owner"},
        path,
    )
    out: dict[str, Any] = {}
    claim_id = _identifier(raw["claim_id"], f"{path}.claim_id") if "claim_id" in raw else None
    statement = _optional_string(raw, "statement", path, maximum=MAX_STATEMENT_CHARS)
    if claim_id is not None:
        out["claim_id"] = claim_id
    if statement is not None:
        out["statement"] = statement
    if "atomic" in raw:
        out["atomic"] = _boolean(raw["atomic"], f"{path}.atomic")
    if "evidence_refs" in raw:
        rows = _array(
            raw["evidence_refs"],
            f"{path}.evidence_refs",
            maximum=MAX_EVIDENCE_REFS_PER_CLAIM,
        )
        out["evidence_refs"] = [
            _parse_evidence(row, f"{path}.evidence_refs[{index}]")
            for index, row in enumerate(rows)
        ]
    if "consequence_owner" in raw:
        owner = raw["consequence_owner"]
        out["consequence_owner"] = (
            None if owner is None else _parse_owner(owner, f"{path}.consequence_owner")
        )
    return out


def _parse_semantic_signal(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(raw, {"value", "source_ref", "method"}, path)
    out: dict[str, Any] = {}
    if "value" in raw:
        out["value"] = _number(raw["value"], f"{path}.value", minimum=0.0, maximum=1.0)
    source_ref = _optional_string(raw, "source_ref", path, maximum=MAX_REFERENCE_CHARS)
    method = _optional_string(raw, "method", path, maximum=MAX_METHOD_CHARS)
    if source_ref is not None:
        out["source_ref"] = source_ref
    if method is not None:
        out["method"] = method
    return out


def _parse_factuality_signal(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(raw, {"state", "source_ref", "method"}, path)
    out: dict[str, Any] = {}
    if "state" in raw:
        state = _string(raw["state"], f"{path}.state", maximum=16)
        if state not in CLAIM_STATES:
            raise _contract_error(f"{path}.state", "must be a known claim state")
        out["state"] = state
    source_ref = _optional_string(raw, "source_ref", path, maximum=MAX_REFERENCE_CHARS)
    method = _optional_string(raw, "method", path, maximum=MAX_METHOD_CHARS)
    if source_ref is not None:
        out["source_ref"] = source_ref
    if method is not None:
        out["method"] = method
    return out


def _parse_signal_envelope(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(raw, {"semantic_uncertainty", "factuality"}, path)
    out: dict[str, Any] = {}
    if "semantic_uncertainty" in raw:
        out["semantic_uncertainty"] = _parse_semantic_signal(
            raw["semantic_uncertainty"], f"{path}.semantic_uncertainty",
        )
    if "factuality" in raw:
        out["factuality"] = _parse_factuality_signal(
            raw["factuality"], f"{path}.factuality",
        )
    return out


def _parse_contradiction(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    _exact_keys(
        raw,
        {"claim_ids", "status", "provenance", "refutes_claim_ids", "resolution_ref"},
        path,
    )
    out: dict[str, Any] = {}
    if "claim_ids" in raw:
        ids = _array(
            raw["claim_ids"], path + ".claim_ids", maximum=MAX_CLAIM_IDS_PER_CONTRADICTION,
        )
        parsed_ids = [
            _identifier(item, f"{path}.claim_ids[{index}]")
            for index, item in enumerate(ids)
        ]
        if len(set(parsed_ids)) != len(parsed_ids):
            raise _contract_error(path + ".claim_ids", "must not contain duplicates")
        out["claim_ids"] = parsed_ids
    if "status" in raw:
        status = _string(raw["status"], path + ".status", maximum=16)
        if status not in {"UNRESOLVED", "CONFIRMED", "RESOLVED"}:
            raise _contract_error(path + ".status", "must be UNRESOLVED, CONFIRMED, or RESOLVED")
        out["status"] = status
    if "provenance" in raw:
        out["provenance"] = _parse_provenance(raw["provenance"], path + ".provenance")
    if "refutes_claim_ids" in raw:
        ids = _array(
            raw["refutes_claim_ids"],
            path + ".refutes_claim_ids",
            maximum=MAX_CLAIM_IDS_PER_CONTRADICTION,
        )
        refutes = [
            _identifier(item, f"{path}.refutes_claim_ids[{index}]")
            for index, item in enumerate(ids)
        ]
        if len(set(refutes)) != len(refutes):
            raise _contract_error(path + ".refutes_claim_ids", "must not contain duplicates")
        out["refutes_claim_ids"] = refutes
    resolution_ref = _optional_string(
        raw, "resolution_ref", path, maximum=MAX_REFERENCE_CHARS,
    )
    if resolution_ref is not None:
        out["resolution_ref"] = resolution_ref
    return out


def parse_atomize_request(payload: Any) -> dict[str, str]:
    """Validate and normalize the structural atomization request envelope."""
    raw = _object(payload, "$atomize")
    _exact_keys(raw, {"text"}, "$atomize")
    if "text" not in raw:
        raise _contract_error("$atomize.text", "is required")
    text = _string(
        raw["text"],
        "$atomize.text",
        maximum=MAX_ATOMIZE_TEXT_CHARS,
        nonblank=True,
    )
    return {"text": text}


def parse_evaluate_request(payload: Any) -> dict[str, Any]:
    """Validate a bounded evaluation envelope without asserting evidence completeness.

    Missing provenance, ownership, evidence, or signal fields are deliberately accepted:
    they are epistemic failures that the RG rubric must expose as UNKNOWN/ABSTAIN.  Unknown
    fields, ambiguous identifiers, invalid types, and unbounded work are contract failures.
    """
    raw = _object(payload, "$evaluate")
    _exact_keys(raw, {"claims", "external_signals", "contradictions"}, "$evaluate")
    if "claims" not in raw:
        raise _contract_error("$evaluate.claims", "is required")
    claim_rows = _array(raw["claims"], "$evaluate.claims", maximum=MAX_CLAIMS)
    claims = [
        _parse_claim(row, f"$evaluate.claims[{index}]")
        for index, row in enumerate(claim_rows)
    ]

    explicit_ids = [claim["claim_id"] for claim in claims if "claim_id" in claim]
    if len(explicit_ids) != len(set(explicit_ids)):
        raise _contract_error("$evaluate.claims", "claim_id values must be unique")
    known_ids = set(explicit_ids)

    signal_rows: Mapping[str, Any] = {}
    if "external_signals" in raw:
        signal_rows = _object(raw["external_signals"], "$evaluate.external_signals")
        if len(signal_rows) > MAX_EXTERNAL_SIGNALS:
            raise _contract_error(
                "$evaluate.external_signals",
                f"must contain at most {MAX_EXTERNAL_SIGNALS} properties",
            )
    signals: dict[str, Any] = {}
    for claim_id, value in signal_rows.items():
        parsed_id = _identifier(claim_id, "$evaluate.external_signals.<claim_id>")
        if parsed_id in signals:
            raise _contract_error(
                "$evaluate.external_signals",
                f"keys collide after identifier normalization: {parsed_id}",
            )
        if parsed_id not in known_ids:
            raise _contract_error(
                f"$evaluate.external_signals.{parsed_id}",
                "does not reference an explicit claim_id",
            )
        signals[parsed_id] = _parse_signal_envelope(
            value, f"$evaluate.external_signals.{parsed_id}",
        )

    contradiction_rows: Sequence[Any] = []
    if "contradictions" in raw:
        contradiction_rows = _array(
            raw["contradictions"],
            "$evaluate.contradictions",
            maximum=MAX_CONTRADICTIONS,
        )
    contradictions = [
        _parse_contradiction(row, f"$evaluate.contradictions[{index}]")
        for index, row in enumerate(contradiction_rows)
    ]
    for index, contradiction in enumerate(contradictions):
        affected = set(contradiction.get("claim_ids", []))
        refuted = set(contradiction.get("refutes_claim_ids", []))
        unknown = (affected | refuted) - known_ids
        if unknown:
            raise _contract_error(
                f"$evaluate.contradictions[{index}]",
                f"unknown claim_id value(s): {', '.join(sorted(unknown))}",
            )
        outside = refuted - affected
        if outside:
            raise _contract_error(
                f"$evaluate.contradictions[{index}].refutes_claim_ids",
                "must be a subset of claim_ids",
            )

    return {
        "claims": claims,
        "external_signals": signals,
        "contradictions": contradictions,
    }


# Open, inspectable error/abstention rubric.  Codes are stable API data, not prose-only
# documentation.  Integrators may display them verbatim and tests pin their semantics.
ERROR_RUBRIC: dict[str, dict[str, Any]] = {
    "RG-001": {
        "condition": "missing or empty claim statement",
        "default_state": UNKNOWN,
        "abstain": True,
    },
    "RG-002": {
        "condition": "claim atom has not been explicitly reviewed as atomic",
        "default_state": UNKNOWN,
        "abstain": True,
    },
    "RG-003": {
        "condition": "no evidence reference supplied",
        "default_state": UNKNOWN,
        "abstain": True,
    },
    "RG-004": {
        "condition": "evidence reference lacks traceable provenance",
        "default_state": UNKNOWN,
        "abstain": True,
    },
    "RG-005": {
        "condition": "claim lacks an accountable consequence owner and scope",
        "default_state": UNKNOWN,
        "abstain": True,
    },
    "RG-006": {
        "condition": "unresolved or confirmed contradiction affects the claim",
        "default_state": UNCERTAIN,
        "abstain": True,
    },
    "RG-007": {
        "condition": "traceable evidence or factuality signal explicitly refutes claim",
        "default_state": REFUTED,
        "abstain": True,
    },
    "RG-008": {
        "condition": "external semantic-uncertainty or factuality signal is malformed or untraceable",
        "default_state": UNKNOWN,
        "abstain": True,
    },
    "RG-009": {
        "condition": "externally supplied semantic uncertainty meets abstention threshold",
        "default_state": UNCERTAIN,
        "abstain": True,
    },
    "RG-010": {
        "condition": "evidence is inconclusive or explicitly uncertain",
        "default_state": UNCERTAIN,
        "abstain": True,
    },
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _stable_claim_id(statement: str, index: int) -> str:
    # Missing caller IDs are not silently accepted.  This identifier merely lets the
    # rejection be addressed deterministically in the response.
    material = {"index": index, "statement": statement}
    return f"unidentified-{_digest(material)[:16]}"


def _provenance_complete(provenance: Any) -> bool:
    """Traceability minimum: source identity plus digest or immutable receipt reference.

    This validates shape only.  It does *not* dereference, replay, or cryptographically
    verify the asserted provenance.
    """
    if not isinstance(provenance, Mapping):
        return False
    if not _nonempty(provenance.get("source_id")):
        return False
    digest = provenance.get("content_sha256")
    receipt = provenance.get("receipt_ref")
    return bool((_nonempty(digest) and _SHA256_RE.fullmatch(digest.strip()))
                or _nonempty(receipt))


def _owner_complete(owner: Any) -> bool:
    return (isinstance(owner, Mapping)
            and _nonempty(owner.get("owner_id"))
            and _nonempty(owner.get("accountability_scope")))


def atomize_text(text: str) -> dict[str, Any]:
    """Produce deterministic *candidate* atoms from visible punctuation/newlines only.

    This is not semantic atomization.  Each candidate is ``atomic=False`` and therefore
    fails closed until a human explicitly reviews it and supplies evidence/ownership.
    """
    source = text if isinstance(text, str) else ""
    pieces = [p.strip(" \t-*\u2022") for p in _SPLIT_RE.split(source) if p.strip(" \t-*\u2022")]
    if len(pieces) > MAX_ATOMIZE_CANDIDATES:
        raise ClaimContractError(
            f"structural atomization produced more than {MAX_ATOMIZE_CANDIDATES} candidates"
        )
    atoms = []
    for index, statement in enumerate(pieces):
        atoms.append({
            "claim_id": f"candidate-{index + 1:04d}-{_digest(statement)[:12]}",
            "statement": statement,
            "atomic": False,
            "atomization_state": "STRUCTURAL-SPLIT-ONLY",
            "human_review_required": True,
            "evidence_refs": [],
            "consequence_owner": None,
        })
    return {
        "module": MODULE_ID,
        "contract_version": CONTRACT_VERSION,
        "method": "VISIBLE-PUNCTUATION-AND-NEWLINE-SPLIT",
        "semantic_atomization_computed": False,
        "decision_state": PROPOSAL_ONLY,
        "effectors_enabled": NO_EFFECTORS,
        "candidate_count": len(atoms),
        "atoms": atoms,
    }


def _validate_semantic_signal(signal: Any) -> tuple[dict[str, Any] | None, str | None]:
    if signal is None:
        return None, None
    if not isinstance(signal, Mapping):
        return None, "RG-008"
    value = signal.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, "RG-008"
    if not 0.0 <= float(value) <= 1.0:
        return None, "RG-008"
    if not _nonempty(signal.get("source_ref")) or not _nonempty(signal.get("method")):
        return None, "RG-008"
    return {
        "value": float(value),
        "source_ref": signal["source_ref"].strip(),
        "method": signal["method"].strip(),
        "computed_by_gate": False,
    }, None


def _validate_factuality_signal(signal: Any) -> tuple[dict[str, Any] | None, str | None]:
    if signal is None:
        return None, None
    if not isinstance(signal, Mapping):
        return None, "RG-008"
    state = str(signal.get("state", "")).strip().upper()
    if state not in CLAIM_STATES:
        return None, "RG-008"
    if not _nonempty(signal.get("source_ref")) or not _nonempty(signal.get("method")):
        return None, "RG-008"
    return {
        "state": state,
        "source_ref": signal["source_ref"].strip(),
        "method": signal["method"].strip(),
        "computed_by_gate": False,
    }, None


def _contradiction_effects(claim_ids: set[str], contradictions: Any) -> dict[str, list[dict[str, Any]]]:
    effects: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claim_ids}
    if contradictions is None:
        return effects
    if not isinstance(contradictions, Sequence) or isinstance(contradictions, (str, bytes)):
        for cid in effects:
            effects[cid].append({"status": "MALFORMED", "rubric_code": "RG-008"})
        return effects
    for raw in contradictions:
        if not isinstance(raw, Mapping):
            for cid in effects:
                effects[cid].append({"status": "MALFORMED", "rubric_code": "RG-008"})
            continue
        ids = raw.get("claim_ids")
        ids = [str(x) for x in ids] if isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)) else []
        status = str(raw.get("status", "UNRESOLVED")).strip().upper()
        traceable = _provenance_complete(raw.get("provenance"))
        refutes = raw.get("refutes_claim_ids")
        refutes = {str(x) for x in refutes} if isinstance(refutes, Sequence) and not isinstance(refutes, (str, bytes)) else set()
        for cid in set(ids) & claim_ids:
            if not traceable:
                effects[cid].append({"status": status, "rubric_code": "RG-004"})
            elif status in {"UNRESOLVED", "CONFIRMED"}:
                effects[cid].append({
                    "status": status,
                    "rubric_code": "RG-007" if cid in refutes else "RG-006",
                    "provenance_traceable": True,
                })
            elif status == "RESOLVED" and not _nonempty(raw.get("resolution_ref")):
                effects[cid].append({"status": status, "rubric_code": "RG-008"})
    return effects


def _base_evidence_state(evidence_refs: Any) -> tuple[str, list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    if not isinstance(evidence_refs, Sequence) or isinstance(evidence_refs, (str, bytes)) or not evidence_refs:
        return UNKNOWN, ["RG-003"], normalized

    states: list[str] = []
    for raw in evidence_refs:
        if not isinstance(raw, Mapping) or not _nonempty(raw.get("reference_id")):
            errors.append("RG-004")
            continue
        state = str(raw.get("evidence_state", UNKNOWN)).strip().upper()
        if state not in CLAIM_STATES:
            errors.append("RG-008")
            state = UNKNOWN
        provenance_ok = _provenance_complete(raw.get("provenance"))
        if not provenance_ok:
            errors.append("RG-004")
        verification_ref = raw.get("verification_ref")
        if state == VERIFIED and not _nonempty(verification_ref):
            # A bare VERIFIED string is not traceable verification.
            errors.append("RG-004")
        states.append(state)
        normalized.append({
            "reference_id": raw.get("reference_id"),
            "evidence_state": state,
            "provenance_traceable": provenance_ok,
            "verification_ref": verification_ref if _nonempty(verification_ref) else None,
        })

    if "RG-004" in errors or "RG-008" in errors or not normalized:
        return UNKNOWN, sorted(set(errors or ["RG-004"])), normalized
    if REFUTED in states:
        errors.append("RG-007")
        return REFUTED, sorted(set(errors)), normalized
    if UNKNOWN in states:
        return UNKNOWN, sorted(set(errors)), normalized
    if UNCERTAIN in states:
        errors.append("RG-010")
        return UNCERTAIN, sorted(set(errors)), normalized
    if all(s == VERIFIED for s in states):
        return VERIFIED, sorted(set(errors)), normalized
    return SUPPORTED, sorted(set(errors)), normalized


def _state_min(a: str, b: str) -> str:
    # Conservative partial order.  Explicit refutation dominates, then missing evidence,
    # then uncertainty; SUPPORTED and VERIFIED are successively stronger.
    rank = {REFUTED: 0, UNKNOWN: 1, UNCERTAIN: 2, SUPPORTED: 3, VERIFIED: 4}
    return a if rank[a] <= rank[b] else b


def _assess_atom(atom: Any, index: int, external: Any, contradictions: list[dict[str, Any]]) -> dict[str, Any]:
    raw = atom if isinstance(atom, Mapping) else {}
    statement = str(raw.get("statement", "")).strip()
    claim_id = str(raw.get("claim_id", "")).strip() or _stable_claim_id(statement, index)
    errors: list[str] = []

    if not statement:
        errors.append("RG-001")
    if raw.get("atomic") is not True:
        errors.append("RG-002")
    if not _owner_complete(raw.get("consequence_owner")):
        errors.append("RG-005")

    state, evidence_errors, evidence = _base_evidence_state(raw.get("evidence_refs"))
    errors.extend(evidence_errors)

    ext = external if isinstance(external, Mapping) else {}
    semantic, semantic_error = _validate_semantic_signal(ext.get("semantic_uncertainty"))
    factuality, factuality_error = _validate_factuality_signal(ext.get("factuality"))
    if semantic_error:
        errors.append(semantic_error)
        state = UNKNOWN
    if factuality_error:
        errors.append(factuality_error)
        state = UNKNOWN

    # Missing factuality never upgrades evidence.  Even completely VERIFIED evidence is
    # only SUPPORTED at the claim level without a traceable external factuality verdict.
    if factuality is None and state == VERIFIED:
        state = SUPPORTED
    elif factuality is not None:
        state = _state_min(state, factuality["state"])
        if factuality["state"] == REFUTED:
            errors.append("RG-007")
        elif factuality["state"] == UNCERTAIN:
            errors.append("RG-010")

    if semantic is not None and semantic["value"] >= SEMANTIC_UNCERTAINTY_ABSTAIN_THRESHOLD:
        if state not in {REFUTED, UNKNOWN}:
            state = UNCERTAIN
        errors.append("RG-009")

    for effect in contradictions:
        errors.append(effect["rubric_code"])
        if effect["rubric_code"] == "RG-007":
            state = REFUTED
        elif effect["rubric_code"] in {"RG-004", "RG-008"}:
            state = UNKNOWN
        elif state not in {REFUTED, UNKNOWN}:
            state = UNCERTAIN

    # Structural/ownership/provenance failures always fail closed to UNKNOWN, except an
    # explicit refutation which remains visible as the stronger negative verdict.
    if any(code in errors for code in {"RG-001", "RG-002", "RG-003", "RG-004", "RG-005", "RG-008"}):
        if state != REFUTED:
            state = UNKNOWN

    errors = sorted(set(errors))
    abstain = state in {UNCERTAIN, REFUTED, UNKNOWN} or any(ERROR_RUBRIC[c]["abstain"] for c in errors)
    return {
        "claim_id": claim_id,
        "statement": statement,
        "state": state,
        "abstain_required": abstain,
        "rubric_codes": errors,
        "evidence_refs": evidence,
        "consequence_owner": dict(raw.get("consequence_owner")) if _owner_complete(raw.get("consequence_owner")) else None,
        "external_signals": {
            "semantic_uncertainty": semantic,
            "factuality": factuality,
            "computed_by_gate": [],
        },
        "contradictions": contradictions,
        "decision_state": PROPOSAL_ONLY,
        "effectors_enabled": NO_EFFECTORS,
    }


def evaluate_claims(
    claims: Iterable[Mapping[str, Any]],
    *,
    external_signals: Mapping[str, Mapping[str, Any]] | None = None,
    contradictions: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess explicit claim atoms and return an unsigned, deterministic receipt.

    ``external_signals`` is keyed by claim_id.  Values are retained as externally supplied
    facts about the signal source; this gate never produces semantic/factuality scores.
    """
    materialized = list(claims) if not isinstance(claims, (str, bytes, Mapping)) else []
    ids = set()
    for index, raw in enumerate(materialized):
        if isinstance(raw, Mapping):
            statement = str(raw.get("statement", "")).strip()
            ids.add(str(raw.get("claim_id", "")).strip() or _stable_claim_id(statement, index))
    contradiction_map = _contradiction_effects(ids, contradictions)
    external_signals = external_signals if isinstance(external_signals, Mapping) else {}

    assessments = []
    for index, atom in enumerate(materialized):
        raw = atom if isinstance(atom, Mapping) else {}
        statement = str(raw.get("statement", "")).strip()
        claim_id = str(raw.get("claim_id", "")).strip() or _stable_claim_id(statement, index)
        assessments.append(_assess_atom(
            atom,
            index,
            external_signals.get(claim_id),
            contradiction_map.get(claim_id, []),
        ))

    counts = {state: sum(1 for row in assessments if row["state"] == state) for state in CLAIM_STATES}
    if not assessments:
        overall = UNKNOWN
        abstain = True
    else:
        overall = assessments[0]["state"]
        for row in assessments[1:]:
            overall = _state_min(overall, row["state"])
        abstain = any(row["abstain_required"] for row in assessments)

    core = {
        "module": MODULE_ID,
        "contract_version": CONTRACT_VERSION,
        "decision_state": PROPOSAL_ONLY,
        "effectors_enabled": NO_EFFECTORS,
        "overall_state": overall,
        "abstain_required": abstain,
        "gate_outcome": "ABSTAIN" if abstain else "EVIDENCE-COMPLETE-FOR-HUMAN-REVIEW",
        "claim_count": len(assessments),
        "state_counts": counts,
        "claims": assessments,
        "signal_contract": {
            "semantic_uncertainty": "EXTERNALLY-SUPPLIED-ONLY",
            "factuality": "EXTERNALLY-SUPPLIED-ONLY",
            "semantic_threshold": SEMANTIC_UNCERTAINTY_ABSTAIN_THRESHOLD,
            "computed_by_gate": [],
        },
        "honesty_invariants": {
            "no_truth_inference": True,
            "no_contradiction_resolution": True,
            "missing_provenance_fails_closed": True,
            "all_outputs_proposal_only": True,
            "effectors_are_zero": True,
        },
    }
    return {
        **core,
        "receipt": {
            "mode": "UNSIGNED-CONTENT-DIGEST",
            "algorithm": "sha256",
            "signed": False,
            "content_sha256": _digest(core),
            "attests_truth": False,
        },
    }


def info() -> dict[str, Any]:
    """Static contract description for a future additive API registration."""
    return {
        "module": MODULE_ID,
        "contract_version": CONTRACT_VERSION,
        "states": list(CLAIM_STATES),
        "decision_state": PROPOSAL_ONLY,
        "effectors_enabled": NO_EFFECTORS,
        "rubric": ERROR_RUBRIC,
        "intended_read_only_api": [
            {"method": "GET", "path": "/api/a11oy/v1/claim-integrity/info", "mutates": False},
            {"method": "POST", "path": "/api/a11oy/v1/claim-integrity/atomize", "mutates": False,
             "note": "computational read; emits candidates only"},
            {"method": "POST", "path": "/api/a11oy/v1/claim-integrity/evaluate", "mutates": False,
             "note": "computational read; unsigned digest only"},
        ],
        "not_implemented_here": ["HTTP registration", "persistence", "signing", "effectors"],
    }
