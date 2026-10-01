#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pinned, read-only public projection of retained Frontier Steward evidence.

Only a measured, public-only deterministic observation is publishable. This
module has no provider, database, signing, receipt-writing, or network adapter.
Hashes disclose local unsigned integrity, never independent witness authority.
The caller owns source verification and publication; this is not an executor.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "szl.frontier-steward.public/v1"
SOURCE_REPOSITORY = "szl-holdings/szl-estate-os"
PUBLIC_FILENAME = "steward-public.json"
MAX_AGE_SECONDS = 7200
MAX_BYTES = 262144
MAX_DEPTH = 12
MAX_NODES = 10000
SOURCE_SCOPES = {
    "github": "PUBLIC_ONLY", "huggingface": "PUBLIC_ONLY",
    "domains": "PUBLIC_NETWORK",
}
_HEX40 = re.compile(r"[a-f0-9]{40}\Z")
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
_SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,})\b|"
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----)|"
    r"(?:\b(?:authorization|api[_ -]?key|password|access[_ -]?token|secret)\s*[:=])",
    re.IGNORECASE,
)
_PATH_OR_MARKUP = re.compile(
    r"(?:[A-Za-z]:[\\/])|(?:\\\\[^\s]+)|"
    r"(?:^|\s)/(?:[^\s/]+/)+[^\s]*|(?:<\s*/?\s*[A-Za-z!])|"
    r"(?:https?://[^\s/]*@)|(?:\bfile://)|(?:\bjavascript:)",
    re.IGNORECASE,
)
_PUBLIC_PROPOSAL_KEYS = {
    "title", "objective", "hypothesis", "tests", "success_metrics", "stop_conditions",
}
# The deployed reader has no dependency on provider code. This conservative
# public-text boundary parallels the canonical producer policy without loading
# its network/model implementation. The builder additionally checks the full
# source proposal with the canonical producer policy before selecting fields.
_UNSAFE_PUBLIC = tuple(re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in (
    r"\b(?:bypass|disable|evade|remove|weaken)\b.{0,100}\b(?:safety|guardrail|policy|approval|protection|control)\b|\b(?:safety|guardrail|policy|approval|protection|control)\b.{0,100}\b(?:bypass|disable|evade|remove|weaken)\b",
    r"\b(?:pathogen|toxin|gene[ -]?drive|virulence|pathogenic[ -]?plasmid)\b.{0,120}\b(?:produce|production|engineer|enhance|mutate|mutagenesis|synthesize|optimi[sz]e|scale|deploy|operationali[sz]e)\b|\b(?:produce|production|engineer|enhance|mutate|mutagenesis|synthesize|optimi[sz]e|scale|deploy|operationali[sz]e)\b.{0,120}\b(?:pathogen|toxin|gene[ -]?drive|virulence|pathogenic[ -]?plasmid)\b",
    r"\b(?:deploy|build|write|weaponize|operationali[sz]e)\b.{0,100}\b(?:malware|ransomware|credential[ -]?stealer|botnet|rootkit|exploit[ -]?chain)\b",
    r"\b(?:exfiltrat|steal|dump|harvest)\w*\b.{0,80}\b(?:secret|token|credential|cookie|private[ -]?key|identity)\w*\b",
    r"\b(?:fabricat\w*|forge(?:d|s|ry)?|forging|fake(?:d|s)?|faking|invent(?:ed|ing|s|ion)?)\b.{0,80}\b(?:evidence|receipt|signature|approval|review|test|provenance)\w*\b",
    r"\b(?:force[ -]?push|self[ -]?approve|disable[ -]?logging|delete[ -]?audit|tamper[ -]?with[ -]?receipt)\b",
))


def _unsafe(text: str) -> bool:
    return any(pattern.search(text) for pattern in _UNSAFE_PUBLIC)


class PublicProjectionError(ValueError):
    """Fail-closed error with a stable code, not a raw private input value."""


def _fail(code: str) -> None:
    raise PublicProjectionError(code)


def _closed(value: Any, keys: set[str], code: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _fail(code)
    return value


def _timestamp(value: Any) -> dt.datetime:
    if type(value) is not str or not _TIME.fullmatch(value):
        _fail("INVALID_TIME")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            _fail("INVALID_TIME")
        return parsed.astimezone(dt.timezone.utc)
    except (ValueError, OverflowError):
        _fail("INVALID_TIME")


def _now(value: Any) -> dt.datetime:
    if value is None:
        return dt.datetime.now(dt.timezone.utc)
    if type(value) is str:
        return _timestamp(value)
    if type(value) is not dt.datetime or value.utcoffset() is None:
        _fail("INVALID_CLOCK")
    return value.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _text(value: Any, limit: int = 2000) -> str:
    if type(value) is not str or not value.strip() or len(value) > limit:
        _fail("INVALID_PUBLIC_TEXT")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        _fail("INVALID_PUBLIC_TEXT")
    if _SECRET.search(value) or _PATH_OR_MARKUP.search(value):
        _fail("NONPUBLIC_TEXT")
    if _unsafe(value):
        _fail("UNSAFE_PUBLIC_TEXT")
    return value


def _bounded_tree(value: Any) -> None:
    """Reject recursion, unsupported Python objects and unbounded input first."""
    stack = [(value, 0)]
    seen: set[int] = set()
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            _fail("JSON_LIMIT_EXCEEDED")
        kind = type(item)
        if kind in (dict, list):
            if id(item) in seen:
                _fail("JSON_SHARED_OR_CYCLIC_CONTAINER")
            seen.add(id(item))
            children = item.values() if kind is dict else item
            if kind is dict and any(type(key) is not str for key in item):
                _fail("INVALID_JSON_KEY")
            stack.extend((child, depth + 1) for child in children)
        elif kind is str:
            if len(item) > MAX_BYTES:
                _fail("JSON_LIMIT_EXCEEDED")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in item):
                _fail("INVALID_UNICODE")
        elif kind is int:
            if not -(10 ** 18) < item < 10 ** 18:
                _fail("JSON_NUMBER_OUT_OF_RANGE")
        elif kind is float:
            if not math.isfinite(item) or abs(item) >= 10 ** 18:
                _fail("JSON_NUMBER_OUT_OF_RANGE")
        elif kind not in (bool, type(None)):
            _fail("INVALID_JSON_VALUE")


def _hash(value: Any, *, prefix: bool = False) -> str:
    if type(value) is not str:
        _fail("INVALID_HASH")
    candidate = value[7:] if prefix and value.startswith("sha256:") else value
    if (prefix and not value.startswith("sha256:")) or not _HEX64.fullmatch(candidate):
        _fail("INVALID_HASH")
    return value


def _identifier(value: Any, pattern: str) -> str:
    if type(value) is not str or not re.fullmatch(pattern, value):
        _fail("INVALID_EVIDENCE_ID")
    return value


def _source_reports(value: Any) -> list[dict[str, str]]:
    if type(value) is not list or len(value) != len(SOURCE_SCOPES):
        _fail("NONPUBLIC_SOURCE_SCOPE")
    found: dict[str, dict[str, str]] = {}
    for item in value:
        report = _closed(item, {"source", "status", "scope"}, "INVALID_SOURCE_REPORT")
        source = report["source"]
        if type(source) is not str or source not in SOURCE_SCOPES or source in found:
            _fail("NONPUBLIC_SOURCE_SCOPE")
        if report["status"] != "MEASURED" or report["scope"] != SOURCE_SCOPES[source]:
            _fail("NONPUBLIC_SOURCE_SCOPE")
        found[source] = {"source": source, "status": "MEASURED", "scope": SOURCE_SCOPES[source]}
    return [found[source] for source in SOURCE_SCOPES]


def _proposal(value: Any, *, closed: bool) -> dict[str, Any]:
    if type(value) is not dict:
        _fail("INVALID_PROPOSAL")
    if closed:
        _closed(value, _PUBLIC_PROPOSAL_KEYS, "INVALID_PROPOSAL_FIELDS")
    elif not _PUBLIC_PROPOSAL_KEYS <= set(value):
        _fail("INVALID_PROPOSAL_FIELDS")
    result = {key: _text(value[key], 300 if key == "title" else 2000)
              for key in ("title", "objective", "hypothesis")}
    for key in ("tests", "success_metrics", "stop_conditions"):
        items = value[key]
        if type(items) is not list or not 1 <= len(items) <= 12:
            _fail("INVALID_PROPOSAL_LIST")
        result[key] = [_text(item, 1000) for item in items]
    # The scanner must cover cross-field instruction phrases, too.
    combined = " ".join(str(item) for item in result.values())
    if _unsafe(combined):
        _fail("UNSAFE_PUBLIC_TEXT")
    return result


def build_public_projection(
    status_payload: Any, *, producer_revision: str, now: Any = None,
) -> dict[str, Any]:
    """Allowlist an actual readback; privileged scope is rejected before text.

    This function cannot prove the authenticity of a caller-supplied Python
    object. The export workflow must obtain it from load_steward_status after
    read-only byte/receipt checks. The consumer separately pins producer source
    and complete artifact bytes; these are not a substitute for signatures.
    """
    if type(producer_revision) is not str or not _HEX40.fullmatch(producer_revision):
        _fail("INVALID_SOURCE_REVISION")
    clock = _now(now)
    _bounded_tree(status_payload)
    if type(status_payload) is not dict or status_payload.get("schema_version") != "szl.frontier-steward.status/v1":
        _fail("INVALID_STATUS")
    if status_payload.get("mutation_policy") != "PROPOSAL_ONLY":
        _fail("INVALID_MUTATION_POLICY")
    latest = status_payload.get("latest_plan")
    if type(latest) is not dict:
        _fail("INVALID_STATUS")
    evidence = latest.get("evidence_snapshot")
    if type(evidence) is not dict:
        _fail("INVALID_EVIDENCE")
    # Scope rejection must happen before any proposal or raw private diagnostic
    # value can enter a public projection or error string.
    sources = _source_reports(evidence.get("source_reports"))
    if (latest.get("state") != "RECORDED" or latest.get("recorded") is not True
            or latest.get("evidence_current") is not True
            or latest.get("evidence_fresh") is not True
            or latest.get("is_latest_recorded_plan") is not True
            or latest.get("plan_status") != "PROPOSED"):
        _fail("PLAN_NOT_CURRENT_RECORDED")
    validation = latest.get("validation")
    if (type(validation) is not dict or validation.get("valid") is not True
            or validation.get("status") != "PASS" or validation.get("errors") != []
            or validation.get("plan_id") != latest.get("plan_id")
            or validation.get("proposal_digest") != latest.get("proposal_digest")):
        _fail("PLAN_VALIDATION_FAILED")
    binding = latest.get("audit_receipt_binding")
    if type(binding) is not dict or binding.get("valid") is not True or binding.get("state") != "BOUND":
        _fail("AUDIT_RECEIPT_NOT_BOUND")
    if (evidence.get("audit_status") != "MEASURED"
            or evidence.get("receipt_chain_valid") is not True
            or evidence.get("receipt_chain_state") != "CHAIN_VALID_UNSIGNED"
            or evidence.get("audit_receipt_binding_valid") is not True
            or evidence.get("audit_receipt_binding_state") != "BOUND"
            or evidence.get("eligible_for_planning") is not True
            or evidence.get("planning_blockers") != []
            or evidence.get("audit_time_state") != "CURRENT"
            or evidence.get("fresh_for_planning") is not True
            or evidence.get("complete_file_audit_claimed") is not False):
        _fail("INVALID_EVIDENCE")
    chain = latest.get("receipt_chain")
    if (type(chain) is not dict or chain.get("chain_valid") is not True
            or chain.get("status") != "CHAIN_VALID_UNSIGNED" or chain.get("errors") != []
            or type(chain.get("receipt_count")) is not int
            or not 2 <= chain["receipt_count"] <= 1000000
            or type(chain.get("unsigned_count")) is not int
            or not 2 <= chain["unsigned_count"] <= chain["receipt_count"]
            or chain.get("verified_signature_count") != 0
            or type(chain.get("verified_signature_count")) is not int
            or latest.get("signature_status") != "UNSIGNED"):
        _fail("INVALID_UNSIGNED_RECEIPT_CHAIN")
    model = latest.get("model")
    if (type(model) is not dict or model.get("adapter") != "deterministic"
            or model.get("runtime") != "NO_MODEL_CALL" or model.get("invoked") is not False
            or model.get("production_allowed") is not False
            or model.get("run_status") != "NOT_INVOKED"
            or model.get("secret_isolation_state") != "NO_MODEL_CALL"
            or model.get("identity_state") != "UNAVAILABLE"
            or any(model.get(key) is not None for key in (
                "requested_model", "resolved_model", "prompt_sha256", "response_sha256",
                "access_program_requested", "access_program_observed",
            ))):
        _fail("PROVIDER_NOT_PUBLIC_APPROVED")
    policy = latest.get("policy")
    if (type(policy) is not dict or policy.get("decision") != "ALLOW_PROPOSAL"
            or policy.get("violations") != [] or policy.get("denial_is_absorbing") is not True
            or policy.get("post_model_validation") != "PASS"
            or policy.get("error") is not None or policy.get("validation_errors") != []):
        _fail("PLAN_POLICY_FAILED")
    observed = _timestamp(evidence.get("audit_completed_at"))
    if observed > clock:
        _fail("FUTURE_EVIDENCE")
    expires = observed + dt.timedelta(seconds=MAX_AGE_SECONDS)
    stale = clock > expires
    raw_proposals = latest.get("proposals")
    if type(raw_proposals) is not list or not 1 <= len(raw_proposals) <= 8:
        _fail("INVALID_PROPOSALS")
    # Inspect every active field of the source proposal; omitted instructions
    # cannot be laundered by selecting only a harmless-looking title.
    from frontier_steward import evaluate_safety
    for item in raw_proposals:
        if type(item) is not dict:
            _fail("INVALID_PROPOSAL")
        text = " ".join(str(value) for key, value in item.items() if key != "denied_effects")
        if evaluate_safety(text).violations:
            _fail("UNSAFE_SOURCE_PROPOSAL")
    proposals = [_proposal(item, closed=False) for item in raw_proposals]
    payload = {
        "schema_version": SCHEMA_VERSION, "state": "STALE" if stale else "CURRENT",
        "scope": "PUBLIC_READ_ONLY",
        "source": {"repository": SOURCE_REPOSITORY, "revision": producer_revision},
        "projected_at": _iso(clock),
        "freshness": {"max_age_seconds": MAX_AGE_SECONDS, "valid_until": _iso(expires)},
        "plan": {
            "id": _identifier(latest.get("plan_id"), r"steward-plan-[a-f0-9]{24}"),
            "digest": _hash(latest.get("proposal_digest"), prefix=True),
            "artifact_sha256": _hash(latest.get("artifact_sha256")),
            "receipt_id": _identifier(latest.get("receipt_id"), r"receipt-[a-f0-9]{32}"),
            "receipt_hash": _hash(latest.get("receipt_hash")), "status": "PROPOSED",
        },
        "audit": {
            "id": _identifier(evidence.get("audit_id"), r"audit-[a-f0-9]{32}"),
            "observed_at": _iso(observed), "receipt_hash": _hash(evidence.get("audit_receipt_hash")),
            "sources": sources,
        },
        "integrity": {
            "kind": "UNSIGNED_HASH_CHAIN", "chain_valid": True,
            "latest_hash": _hash(chain.get("latest_hash")),
            "signature_status": "UNSIGNED", "independent_witness": False,
        },
        "provider": {"adapter": "deterministic", "runtime": "NO_MODEL_CALL", "model_invoked": False},
        "production_ready": False, "mutation_policy": "PROPOSAL_ONLY",
        "proposals": [] if stale else proposals,
    }
    result = validate_public_projection(payload, expected_source_revision=producer_revision, now=clock)
    if not result["valid"]:
        _fail(result["errors"][0])
    return result["projection"]


def _validate(payload: Any, expected_source_revision: Any, clock: dt.datetime) -> dict[str, Any]:
    _bounded_tree(payload)
    _closed(payload, {
        "schema_version", "state", "scope", "source", "projected_at", "freshness", "plan",
        "audit", "integrity", "provider", "production_ready", "mutation_policy", "proposals",
    }, "INVALID_PUBLIC_FIELDS")
    if (payload["schema_version"] != SCHEMA_VERSION or payload["scope"] != "PUBLIC_READ_ONLY"
            or payload["state"] not in ("CURRENT", "STALE")
            or payload["production_ready"] is not False or payload["mutation_policy"] != "PROPOSAL_ONLY"):
        _fail("INVALID_PUBLIC_BOUNDARY")
    source = _closed(payload["source"], {"repository", "revision"}, "INVALID_SOURCE_FIELDS")
    if source["repository"] != SOURCE_REPOSITORY or type(source["revision"]) is not str or not _HEX40.fullmatch(source["revision"]):
        _fail("INVALID_SOURCE_REVISION")
    if expected_source_revision is not None:
        if type(expected_source_revision) is not str or not _HEX40.fullmatch(expected_source_revision):
            _fail("INVALID_SOURCE_PIN")
        if source["revision"] != expected_source_revision:
            _fail("SOURCE_REVISION_MISMATCH")
    freshness = _closed(payload["freshness"], {"max_age_seconds", "valid_until"}, "INVALID_FRESHNESS_FIELDS")
    if type(freshness["max_age_seconds"]) is not int or freshness["max_age_seconds"] != MAX_AGE_SECONDS:
        _fail("INVALID_FRESHNESS_BOUND")
    plan = _closed(payload["plan"], {"id", "digest", "artifact_sha256", "receipt_id", "receipt_hash", "status"}, "INVALID_PLAN_FIELDS")
    _identifier(plan["id"], r"steward-plan-[a-f0-9]{24}")
    _identifier(plan["receipt_id"], r"receipt-[a-f0-9]{32}")
    _hash(plan["digest"], prefix=True)
    _hash(plan["artifact_sha256"])
    _hash(plan["receipt_hash"])
    if plan["status"] != "PROPOSED":
        _fail("INVALID_PLAN_STATE")
    audit = _closed(payload["audit"], {"id", "observed_at", "receipt_hash", "sources"}, "INVALID_AUDIT_FIELDS")
    _identifier(audit["id"], r"audit-[a-f0-9]{32}")
    _hash(audit["receipt_hash"])
    sources = _source_reports(audit["sources"])
    integrity = _closed(payload["integrity"], {"kind", "chain_valid", "latest_hash", "signature_status", "independent_witness"}, "INVALID_INTEGRITY_FIELDS")
    if (integrity["kind"] != "UNSIGNED_HASH_CHAIN" or integrity["chain_valid"] is not True
            or integrity["signature_status"] != "UNSIGNED" or integrity["independent_witness"] is not False):
        _fail("INVALID_UNSIGNED_INTEGRITY")
    _hash(integrity["latest_hash"])
    provider = _closed(payload["provider"], {"adapter", "runtime", "model_invoked"}, "INVALID_PROVIDER_FIELDS")
    if provider != {"adapter": "deterministic", "runtime": "NO_MODEL_CALL", "model_invoked": False} or provider["model_invoked"] is not False:
        _fail("PROVIDER_NOT_PUBLIC_APPROVED")
    observed = _timestamp(audit["observed_at"])
    projected = _timestamp(payload["projected_at"])
    expires = _timestamp(freshness["valid_until"])
    if observed > clock or projected > clock:
        _fail("FUTURE_EVIDENCE")
    if projected < observed or expires != observed + dt.timedelta(seconds=MAX_AGE_SECONDS):
        _fail("INCONSISTENT_EVIDENCE_TIME")
    if type(payload["proposals"]) is not list or len(payload["proposals"]) > 8:
        _fail("INVALID_PROPOSALS")
    proposals = [_proposal(item, closed=True) for item in payload["proposals"]]
    if payload["state"] == "STALE" and proposals:
        _fail("STALE_PROPOSALS_FORBIDDEN")
    if payload["state"] == "CURRENT" and (not proposals or projected > expires):
        _fail("INVALID_CURRENT_PROJECTION")
    if len(json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")) > MAX_BYTES:
        _fail("JSON_LIMIT_EXCEEDED")
    result = copy.deepcopy(payload)
    result["audit"]["sources"] = sources
    if payload["state"] == "STALE" or clock > expires:
        result["state"] = "STALE"
        result["proposals"] = []
    return result


def validate_public_projection(
    payload: Any, *, expected_source_revision: str | None = None, now: Any = None,
) -> dict[str, Any]:
    """Return a sanitized view. A stale view has no current proposals.

    `valid` means the bounded public contract passed, not production readiness
    or witness verification. Consumers must use `projection`, not the original
    input, and must additionally pin complete artifact bytes when loading.
    """
    try:
        projection = _validate(payload, expected_source_revision, _now(now))
        return {"valid": True, "state": projection["state"], "errors": [], "projection": projection}
    except (PublicProjectionError, ValueError, TypeError, OverflowError, RecursionError):
        # Only our stable error codes are public; never echo private paths or
        # proposal values, including exceptions raised by malformed objects.
        import sys
        error = sys.exc_info()[1]
        code = str(error) if type(error) is PublicProjectionError else "INVALID_PUBLIC_PROJECTION"
        return {"valid": False, "state": "INVALID", "errors": [code], "projection": None}


def _strict_json(content: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                _fail("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(_: str) -> None:
        _fail("NONFINITE_JSON_NUMBER")

    def integer(value: str) -> int:
        if len(value.lstrip("-")) > 18:
            _fail("JSON_NUMBER_OUT_OF_RANGE")
        return int(value)

    def floating(value: str) -> float:
        number = float(value)
        if not math.isfinite(number) or abs(number) >= 10 ** 18:
            _fail("JSON_NUMBER_OUT_OF_RANGE")
        return number

    try:
        result = json.loads(content.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=constant, parse_int=integer, parse_float=floating)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        _fail("INVALID_PUBLIC_JSON")
    _bounded_tree(result)
    return result


def _safe_path(path: Any, allowed_directory: Any) -> Path:
    # The directory is supplied only by the trusted application configuration,
    # never a URL parameter. Default to this installed module's directory.
    supplied = Path(path)
    allowed = Path(__file__).absolute().parent if allowed_directory is None else Path(allowed_directory)
    if (not supplied.is_absolute() or not allowed.is_absolute()
            or supplied.name != PUBLIC_FILENAME or ".." in supplied.parts
            or ".." in allowed.parts or supplied.parent != allowed):
        _fail("PUBLIC_PATH_NOT_ALLOWED")
    for candidate in reversed((supplied, *supplied.parents)):
        info = candidate.lstat()
        # Windows junctions/reparse points are not reliably is_symlink().
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            _fail("PUBLIC_PATH_LINK_FORBIDDEN")
    if not stat.S_ISREG(supplied.lstat().st_mode):
        _fail("PUBLIC_PATH_NOT_REGULAR")
    return supplied


def load_public_projection(
    path: str | Path, *, expected_source_revision: str, expected_sha256: str,
    now: Any = None, allowed_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Read only a fixed filename in a trusted directory, with both pins.

    No missing-artifact fallback and no writes. The caller must not derive the
    pins or allowed directory from the artifact or a request. Default directory
    is the installed module's directory; a deployment may explicitly configure
    its fixed packaged evidence directory. Errors contain no local paths.
    """
    descriptor: int | None = None
    try:
        if type(expected_source_revision) is not str or not _HEX40.fullmatch(expected_source_revision):
            _fail("INVALID_SOURCE_PIN")
        _hash(expected_sha256)
        safe = _safe_path(path, allowed_directory)
        before = safe.lstat()
        descriptor = os.open(safe, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_dev != before.st_dev
                or opened.st_ino != before.st_ino or opened.st_size > MAX_BYTES):
            _fail("PUBLIC_ARTIFACT_CHANGED_OR_OVERSIZED")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            content = handle.read(MAX_BYTES + 1)
        after = safe.lstat()
        _safe_path(safe, allowed_directory)
        if (len(content) > MAX_BYTES or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            _fail("PUBLIC_ARTIFACT_CHANGED_OR_OVERSIZED")
        if hashlib.sha256(content).hexdigest() != expected_sha256:
            _fail("PUBLIC_ARTIFACT_HASH_MISMATCH")
        payload = _strict_json(content)
        return validate_public_projection(payload, expected_source_revision=expected_source_revision, now=now)
    except (OSError, PublicProjectionError, ValueError, TypeError, OverflowError, RecursionError):
        import sys
        error = sys.exc_info()[1]
        code = str(error) if type(error) is PublicProjectionError else "PUBLIC_ARTIFACT_UNAVAILABLE"
        state = "UNAVAILABLE" if isinstance(error, OSError) else "INVALID"
        return {"valid": False, "state": state, "errors": [code], "projection": None}
    finally:
        if descriptor is not None:
            os.close(descriptor)


__all__ = [
    "SCHEMA_VERSION", "SOURCE_REPOSITORY", "PUBLIC_FILENAME", "MAX_AGE_SECONDS",
    "PublicProjectionError", "build_public_projection", "validate_public_projection",
    "load_public_projection",
]
