#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate one deterministic, bounded SZL One Lathe snapshot.

The generator accepts exactly one explicit JSON manifest. It does not crawl the
filesystem, call a network API, launch subprocesses, read environment variables,
or inspect credential stores. It validates every admitted source, record,
evidence item, and property claim before atomically writing a snapshot.

Input uses the output contract from
``schemas/lathe/program-snapshot.v1.schema.json`` with these two differences:

* ``schemaVersion`` is ``szl.lathe.input.v1``;
* ``digest`` is absent because the generator computes it.

``generatedAt`` and all collection timestamps are caller-supplied fixed inputs.
The canonical digest excludes ``generatedAt`` and ``digest`` as required by the
One Lathe specification. Candidate generation accepts only an unbound
``receiptBinding``; binding is a separate independently verified write action.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


INPUT_SCHEMA = "szl.lathe.input.v1"
OUTPUT_SCHEMA = "szl.lathe.snapshot.v1"
PROGRAM_ID = "szl-one-lathe-frontier-program"
GENERATOR_NAME = "szl-one-lathe-snapshot"
GENERATOR_VERSION = "1"

DEFAULT_MAX_BYTES = 8 * 1024 * 1024
HARD_MAX_BYTES = 16 * 1024 * 1024
HARD_MAX_RECORDS = 50_000
HARD_MAX_NESTED_ITEMS = 50_000
MAX_STRING_LENGTH = 8_192

MATURITY_STATES = frozenset({"PROVEN", "MEASURED", "MODELED", "CONJECTURE", "OPEN"})
NULL_OPERATIONAL_STATES = frozenset(
    {
        "UNKNOWN",
        "NOT_EVALUATED",
        "UNAVAILABLE",
        "OFFLINE_UNTIL_KEYED",
        "QUARANTINED",
        "STALE_EVIDENCE",
    }
)
OPERATIONAL_STATES = NULL_OPERATIONAL_STATES | frozenset(
    {"AVAILABLE", "DEGRADED", "BLOCKED", "FAILED"}
)
EVIDENCE_STATES = frozenset(
    {"SUFFICIENT", "PARTIAL", "ABSENT", "CONFLICTING", "STALE", "INADMISSIBLE"}
)
EVIDENCE_ADMISSION_STATES = frozenset(
    {"ADMISSIBLE", "PARTIAL", "ABSENT", "CONFLICTING", "STALE", "INADMISSIBLE"}
)
NON_SUFFICIENT_EVIDENCE_STATES = EVIDENCE_STATES - {"SUFFICIENT"}

SOURCE_TYPES = frozenset(
    {
        "FILE",
        "GIT",
        "GITHUB_API",
        "HUGGING_FACE_API",
        "HTTP",
        "RUNTIME_PROBE",
        "RECEIPT",
        "MANUAL_DECLARATION",
        "OTHER",
    }
)
DISCOVERY_MODES = frozenset({"EXPLICIT_INPUT_SET", "BOUNDED_MANIFEST", "BOUNDED_QUERY"})
ASSET_TYPES = frozenset(
    {
        "REPOSITORY",
        "FILE",
        "RECEIPT",
        "BRAIN_SOURCE",
        "FORMULA_REGISTRY",
        "FORMAL_PROOF_LINK",
        "NUMERICAL_ENGINE",
        "INFERENCE_ARTIFACT",
        "HUGGING_FACE_ASSET",
        "DEPLOYMENT",
        "OTHER",
    }
)
PROPERTY_KINDS = frozenset(
    {
        "IDENTITY",
        "PROVENANCE",
        "FORMAL_PROPERTY",
        "RUNTIME_HEALTH",
        "LICENSING",
        "SECURITY",
        "FRESHNESS",
        "DEPLOYMENT",
        "LIVE_VERIFICATION",
        "PERFORMANCE",
        "DATA_RIGHTS",
        "MODEL_QUALIFICATION",
        "COVERAGE",
        "OTHER",
    }
)
EVIDENCE_KINDS = frozenset(
    {
        "FORMAL_PROOF",
        "TEST_RESULT",
        "RUNTIME_PROBE",
        "BENCHMARK_RECEIPT",
        "DSSE_RECEIPT",
        "SOURCE_FILE",
        "API_RESPONSE",
        "LICENSE_RECORD",
        "DATASET_RECORD",
        "DEPLOYMENT_RECORD",
        "MANUAL_DECLARATION",
        "OTHER",
    }
)
FRESHNESS_STATES = frozenset({"FRESH", "STALE", "UNKNOWN"})
APPROVAL_DECISIONS = frozenset({"APPROVED", "REJECTED", "DEFERRED", "NOT_EVALUATED"})

_ROOT_FIELDS = frozenset(
    {
        "schemaVersion",
        "programId",
        "snapshotId",
        "generatedAt",
        "generator",
        "source",
        "revision",
        "collectedAt",
        "coverage",
        "maturity",
        "operationalState",
        "evidenceState",
        "promotionEligible",
        "records",
        "risks",
        "blockers",
        "approvalDecision",
        "receiptBinding",
    }
)
_GENERATOR_FIELDS = frozenset({"name", "version", "source", "revision"})
_SOURCE_FIELDS = frozenset({"type", "locator"})
_COVERAGE_FIELDS = frozenset(
    {
        "bounded",
        "discoveryMode",
        "scope",
        "bounds",
        "included",
        "excluded",
        "missing",
        "expectedCount",
        "observedCount",
        "complete",
    }
)
_EVIDENCE_FIELDS = frozenset(
    {
        "evidenceId",
        "propertyKind",
        "kind",
        "source",
        "revision",
        "collectedAt",
        "admissionState",
        "digest",
        "summary",
    }
)
_FRESHNESS_FIELDS = frozenset({"evaluatedAt", "maxAgeSeconds", "status"})
_CLAIM_FIELDS = frozenset(
    {
        "claimId",
        "propertyKind",
        "propertyName",
        "assertion",
        "maturity",
        "operationalState",
        "evidenceState",
        "source",
        "revision",
        "collectedAt",
        "coverage",
        "evidenceIds",
        "freshness",
        "promotionEligible",
        "blockers",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "recordId",
        "assetType",
        "source",
        "revision",
        "collectedAt",
        "coverage",
        "maturity",
        "operationalState",
        "evidenceState",
        "promotionEligible",
        "evidence",
        "claims",
        "blockers",
        "risks",
    }
)
_APPROVAL_FIELDS = frozenset({"decision", "scope", "actor", "decidedAt", "source", "revision"})
_UNBOUND_RECEIPT_FIELDS = frozenset({"state", "blockers"})

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE_KEYS = frozenset(
    {
        "accesstoken",
        "apikey",
        "authorization",
        "bearertoken",
        "clientsecret",
        "cookie",
        "credential",
        "credentials",
        "hftoken",
        "password",
        "privatekey",
        "refreshtoken",
        "secret",
        "secretref",
        "signingkey",
        "token",
    }
)


class LatheSnapshotError(ValueError):
    """A manifest violates the bounded One Lathe snapshot contract."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes used by the snapshot digest."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON object keys instead of silently taking the last."""

    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise LatheSnapshotError(f"duplicate JSON object key {key!r} is forbidden")
        value[key] = child
    return value


def _fail(path: str, message: str) -> LatheSnapshotError:
    return LatheSnapshotError(f"{path}: {message}")


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _reject_sensitive_keys(value: Any, path: str = "$") -> None:
    """Refuse secret-bearing fields without echoing or serializing their values."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if _normalized_key(key_text) in _SENSITIVE_KEYS:
                raise _fail(f"{path}.{key_text}", "secret-bearing fields are forbidden")
            _reject_sensitive_keys(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive_keys(child, f"{path}[{index}]")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise _fail(path, "must be a JSON object with string keys")
    return value


def _exact(value: Mapping[str, Any], fields: frozenset[str], path: str) -> None:
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        raise _fail(path, f"unknown fields: {', '.join(unknown)}")
    if missing:
        raise _fail(path, f"missing fields: {', '.join(missing)}")


def _text(value: Any, path: str, *, maximum: int = MAX_STRING_LENGTH) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise _fail(path, "must be a non-empty string without surrounding whitespace")
    if len(value) > maximum:
        raise _fail(path, f"must contain at most {maximum} characters")
    return value


def _identifier(value: Any, path: str) -> str:
    result = _text(value, path, maximum=200)
    if not _ID_RE.fullmatch(result):
        raise _fail(path, "must match ^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    return result


def _enum(value: Any, allowed: frozenset[str], path: str) -> str:
    result = _text(value, path)
    if result not in allowed:
        raise _fail(path, f"must be one of: {', '.join(sorted(allowed))}")
    return result


def _timestamp(value: Any, path: str) -> str:
    result = _text(value, path)
    candidate = result[:-1] + "+00:00" if result.endswith("Z") else result
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise _fail(path, "must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _fail(path, "must include a UTC offset")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _integer(value: Any, path: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail(path, "must be a non-negative integer" + (" or null" if nullable else ""))
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise _fail(path, "must be a boolean")
    return value


def _string_array(value: Any, path: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise _fail(path, "must be a JSON array")
    if nonempty and not value:
        raise _fail(path, "must contain at least one value")
    if len(value) > HARD_MAX_NESTED_ITEMS:
        raise _fail(path, f"exceeds item limit {HARD_MAX_NESTED_ITEMS}")
    result = [_text(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if len(result) != len(set(result)):
        raise _fail(path, "values must be unique")
    return sorted(result)


def _source(value: Any, path: str) -> dict[str, Any]:
    source = _object(value, path)
    _exact(source, _SOURCE_FIELDS, path)
    source_type = _enum(source["type"], SOURCE_TYPES, f"{path}.type")
    locator = _text(source["locator"], f"{path}.locator", maximum=2048)

    parsed = urlsplit(locator)
    if parsed.scheme:
        if parsed.scheme != "https" or not parsed.netloc:
            raise _fail(f"{path}.locator", "URL locators must use https")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise _fail(
                f"{path}.locator",
                "URL locators may not contain credentials, query strings, or fragments",
            )
    else:
        if PurePosixPath(locator).is_absolute() or PureWindowsPath(locator).is_absolute():
            raise _fail(f"{path}.locator", "file locators must be repository-relative")
        if ".." in PurePosixPath(locator.replace("\\", "/")).parts:
            raise _fail(f"{path}.locator", "file locators may not traverse parent directories")
    return {"type": source_type, "locator": locator}


def _coverage(value: Any, path: str, *, compute_observed: int | None = None) -> dict[str, Any]:
    coverage = _object(value, path)
    _exact(coverage, _COVERAGE_FIELDS, path)
    bounded = _boolean(coverage["bounded"], f"{path}.bounded")
    if not bounded:
        raise _fail(f"{path}.bounded", "unbounded discovery is forbidden")
    expected = _integer(coverage["expectedCount"], f"{path}.expectedCount", nullable=True)
    observed = _integer(coverage["observedCount"], f"{path}.observedCount")
    assert observed is not None
    if compute_observed is not None:
        observed = compute_observed
    bounds = _string_array(coverage["bounds"], f"{path}.bounds", nonempty=True)
    included = _string_array(coverage["included"], f"{path}.included")
    excluded = _string_array(coverage["excluded"], f"{path}.excluded")
    missing = _string_array(coverage["missing"], f"{path}.missing")
    complete = expected is not None and expected == observed and not missing
    return {
        "bounded": True,
        "discoveryMode": _enum(
            coverage["discoveryMode"], DISCOVERY_MODES, f"{path}.discoveryMode"
        ),
        "scope": _text(coverage["scope"], f"{path}.scope"),
        "bounds": bounds,
        "included": included,
        "excluded": excluded,
        "missing": missing,
        "expectedCount": expected,
        "observedCount": observed,
        "complete": complete,
    }


def _enforce_state_invariants(
    *,
    operational_state: str,
    evidence_state: str,
    promotion_eligible: bool,
    blockers: Sequence[str],
    path: str,
) -> None:
    if promotion_eligible and evidence_state != "SUFFICIENT":
        raise _fail(path, "promotion eligibility requires SUFFICIENT evidence")
    if operational_state in NULL_OPERATIONAL_STATES:
        if promotion_eligible:
            raise _fail(path, "a null operational state cannot be promotion eligible")
        if evidence_state not in NON_SUFFICIENT_EVIDENCE_STATES:
            raise _fail(path, "a null operational state cannot use SUFFICIENT evidence")
        if not blockers:
            raise _fail(path, "a null operational state requires at least one blocker")
    if evidence_state in {"ABSENT", "CONFLICTING", "STALE", "INADMISSIBLE"} and promotion_eligible:
        raise _fail(path, f"{evidence_state} evidence cannot be promotion eligible")


def _evidence(value: Any, path: str) -> dict[str, Any]:
    evidence = _object(value, path)
    required = _EVIDENCE_FIELDS - {"digest"}
    unknown = sorted(set(evidence) - _EVIDENCE_FIELDS)
    missing = sorted(required - set(evidence))
    if unknown:
        raise _fail(path, f"unknown fields: {', '.join(unknown)}")
    if missing:
        raise _fail(path, f"missing fields: {', '.join(missing)}")
    digest = evidence.get("digest")
    if digest is not None and (not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest)):
        raise _fail(f"{path}.digest", "must be sha256:<64 lowercase hex characters>")
    return {
        "evidenceId": _identifier(evidence["evidenceId"], f"{path}.evidenceId"),
        "propertyKind": _enum(evidence["propertyKind"], PROPERTY_KINDS, f"{path}.propertyKind"),
        "kind": _enum(evidence["kind"], EVIDENCE_KINDS, f"{path}.kind"),
        "source": _source(evidence["source"], f"{path}.source"),
        "revision": _text(evidence["revision"], f"{path}.revision", maximum=512),
        "collectedAt": _timestamp(evidence["collectedAt"], f"{path}.collectedAt"),
        "admissionState": _enum(
            evidence["admissionState"], EVIDENCE_ADMISSION_STATES, f"{path}.admissionState"
        ),
        **({"digest": digest} if digest is not None else {}),
        "summary": _text(evidence["summary"], f"{path}.summary"),
    }


def _freshness(value: Any, path: str) -> dict[str, Any]:
    freshness = _object(value, path)
    _exact(freshness, _FRESHNESS_FIELDS, path)
    return {
        "evaluatedAt": _timestamp(freshness["evaluatedAt"], f"{path}.evaluatedAt"),
        "maxAgeSeconds": _integer(freshness["maxAgeSeconds"], f"{path}.maxAgeSeconds"),
        "status": _enum(freshness["status"], FRESHNESS_STATES, f"{path}.status"),
    }


def _claim(value: Any, path: str) -> dict[str, Any]:
    claim = _object(value, path)
    _exact(claim, _CLAIM_FIELDS, path)
    property_kind = _enum(claim["propertyKind"], PROPERTY_KINDS, f"{path}.propertyKind")
    maturity = _enum(claim["maturity"], MATURITY_STATES, f"{path}.maturity")
    operational_state = _enum(
        claim["operationalState"], OPERATIONAL_STATES, f"{path}.operationalState"
    )
    evidence_state = _enum(claim["evidenceState"], EVIDENCE_STATES, f"{path}.evidenceState")
    promotion_eligible = _boolean(claim["promotionEligible"], f"{path}.promotionEligible")
    blockers = _string_array(claim["blockers"], f"{path}.blockers")
    freshness = _freshness(claim["freshness"], f"{path}.freshness")
    if maturity == "PROVEN" and property_kind != "FORMAL_PROPERTY":
        raise _fail(path, "PROVEN is valid only for FORMAL_PROPERTY claims")
    if freshness["status"] == "STALE":
        if operational_state != "STALE_EVIDENCE" or evidence_state != "STALE" or promotion_eligible:
            raise _fail(path, "stale freshness requires STALE_EVIDENCE, STALE, and ineligible")
    _enforce_state_invariants(
        operational_state=operational_state,
        evidence_state=evidence_state,
        promotion_eligible=promotion_eligible,
        blockers=blockers,
        path=path,
    )
    return {
        "claimId": _identifier(claim["claimId"], f"{path}.claimId"),
        "propertyKind": property_kind,
        "propertyName": _text(claim["propertyName"], f"{path}.propertyName"),
        "assertion": _text(claim["assertion"], f"{path}.assertion"),
        "maturity": maturity,
        "operationalState": operational_state,
        "evidenceState": evidence_state,
        "source": _source(claim["source"], f"{path}.source"),
        "revision": _text(claim["revision"], f"{path}.revision", maximum=512),
        "collectedAt": _timestamp(claim["collectedAt"], f"{path}.collectedAt"),
        "coverage": _coverage(claim["coverage"], f"{path}.coverage"),
        "evidenceIds": _string_array(
            claim["evidenceIds"], f"{path}.evidenceIds", nonempty=True
        ),
        "freshness": freshness,
        "promotionEligible": promotion_eligible,
        "blockers": blockers,
    }


def _record(value: Any, path: str) -> dict[str, Any]:
    record = _object(value, path)
    _exact(record, _RECORD_FIELDS, path)
    evidence_raw = record["evidence"]
    claims_raw = record["claims"]
    if not isinstance(evidence_raw, list) or not evidence_raw:
        raise _fail(f"{path}.evidence", "must be a non-empty JSON array")
    if not isinstance(claims_raw, list) or not claims_raw:
        raise _fail(f"{path}.claims", "must be a non-empty JSON array")
    if len(evidence_raw) + len(claims_raw) > HARD_MAX_NESTED_ITEMS:
        raise _fail(path, f"evidence and claims exceed item limit {HARD_MAX_NESTED_ITEMS}")
    evidence = [_evidence(item, f"{path}.evidence[{index}]") for index, item in enumerate(evidence_raw)]
    claims = [_claim(item, f"{path}.claims[{index}]") for index, item in enumerate(claims_raw)]
    evidence_ids = [item["evidenceId"] for item in evidence]
    claim_ids = [item["claimId"] for item in claims]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise _fail(f"{path}.evidence", "evidenceId values must be unique")
    if len(claim_ids) != len(set(claim_ids)):
        raise _fail(f"{path}.claims", "claimId values must be unique")
    admitted = set(evidence_ids)
    for claim in claims:
        unknown = sorted(set(claim["evidenceIds"]) - admitted)
        if unknown:
            raise _fail(
                f"{path}.claims.{claim['claimId']}.evidenceIds",
                f"unknown evidence IDs: {', '.join(unknown)}",
            )
        mismatched = sorted(
            evidence_item["evidenceId"]
            for evidence_item in evidence
            if evidence_item["evidenceId"] in claim["evidenceIds"]
            and evidence_item["propertyKind"] != claim["propertyKind"]
        )
        if mismatched:
            raise _fail(
                f"{path}.claims.{claim['claimId']}",
                f"property-kind mismatch for evidence: {', '.join(mismatched)}",
            )

    maturity = _enum(record["maturity"], MATURITY_STATES, f"{path}.maturity")
    operational_state = _enum(
        record["operationalState"], OPERATIONAL_STATES, f"{path}.operationalState"
    )
    evidence_state = _enum(record["evidenceState"], EVIDENCE_STATES, f"{path}.evidenceState")
    promotion_eligible = _boolean(record["promotionEligible"], f"{path}.promotionEligible")
    blockers = _string_array(record["blockers"], f"{path}.blockers")
    _enforce_state_invariants(
        operational_state=operational_state,
        evidence_state=evidence_state,
        promotion_eligible=promotion_eligible,
        blockers=blockers,
        path=path,
    )
    return {
        "recordId": _identifier(record["recordId"], f"{path}.recordId"),
        "assetType": _enum(record["assetType"], ASSET_TYPES, f"{path}.assetType"),
        "source": _source(record["source"], f"{path}.source"),
        "revision": _text(record["revision"], f"{path}.revision", maximum=512),
        "collectedAt": _timestamp(record["collectedAt"], f"{path}.collectedAt"),
        "coverage": _coverage(record["coverage"], f"{path}.coverage"),
        "maturity": maturity,
        "operationalState": operational_state,
        "evidenceState": evidence_state,
        "promotionEligible": promotion_eligible,
        "evidence": sorted(evidence, key=lambda item: item["evidenceId"]),
        "claims": sorted(claims, key=lambda item: item["claimId"]),
        "blockers": blockers,
        "risks": _string_array(record["risks"], f"{path}.risks"),
    }


def _generator(value: Any, path: str) -> dict[str, Any]:
    generator = _object(value, path)
    _exact(generator, _GENERATOR_FIELDS, path)
    name = _text(generator["name"], f"{path}.name")
    version = _text(generator["version"], f"{path}.version")
    if name != GENERATOR_NAME or version != GENERATOR_VERSION:
        raise _fail(path, f"must identify {GENERATOR_NAME} version {GENERATOR_VERSION}")
    return {
        "name": name,
        "version": version,
        "source": _text(generator["source"], f"{path}.source"),
        "revision": _text(generator["revision"], f"{path}.revision", maximum=512),
    }


def _approval(value: Any, path: str) -> dict[str, Any]:
    approval = _object(value, path)
    _exact(approval, _APPROVAL_FIELDS, path)
    return {
        "decision": _enum(approval["decision"], APPROVAL_DECISIONS, f"{path}.decision"),
        "scope": _text(approval["scope"], f"{path}.scope"),
        "actor": _text(approval["actor"], f"{path}.actor"),
        "decidedAt": _timestamp(approval["decidedAt"], f"{path}.decidedAt"),
        "source": _source(approval["source"], f"{path}.source"),
        "revision": _text(approval["revision"], f"{path}.revision", maximum=512),
    }


def _unbound_receipt(value: Any, path: str) -> dict[str, Any]:
    binding = _object(value, path)
    _exact(binding, _UNBOUND_RECEIPT_FIELDS, path)
    state = _enum(binding["state"], NULL_OPERATIONAL_STATES, f"{path}.state")
    blockers = _string_array(binding["blockers"], f"{path}.blockers", nonempty=True)
    return {"state": state, "blockers": blockers}


def validate_input_manifest(value: Any, origin: str = "<input>") -> dict[str, Any]:
    """Validate and canonically normalize one explicit bounded input manifest."""

    _reject_sensitive_keys(value)
    manifest = _object(value, origin)
    _exact(manifest, _ROOT_FIELDS, origin)
    if manifest["schemaVersion"] != INPUT_SCHEMA:
        raise _fail(f"{origin}.schemaVersion", f"must equal {INPUT_SCHEMA!r}")
    if manifest["programId"] != PROGRAM_ID:
        raise _fail(f"{origin}.programId", f"must equal {PROGRAM_ID!r}")
    records_raw = manifest["records"]
    if not isinstance(records_raw, list) or not records_raw:
        raise _fail(f"{origin}.records", "must be a non-empty JSON array")
    if len(records_raw) > HARD_MAX_RECORDS:
        raise _fail(f"{origin}.records", f"exceeds record limit {HARD_MAX_RECORDS}")
    records = [_record(item, f"{origin}.records[{index}]") for index, item in enumerate(records_raw)]
    record_ids = [record["recordId"] for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise _fail(f"{origin}.records", "recordId values must be unique")

    maturity = _enum(manifest["maturity"], MATURITY_STATES, f"{origin}.maturity")
    operational_state = _enum(
        manifest["operationalState"], OPERATIONAL_STATES, f"{origin}.operationalState"
    )
    evidence_state = _enum(
        manifest["evidenceState"], EVIDENCE_STATES, f"{origin}.evidenceState"
    )
    promotion_eligible = _boolean(
        manifest["promotionEligible"], f"{origin}.promotionEligible"
    )
    blockers = _string_array(manifest["blockers"], f"{origin}.blockers")
    _enforce_state_invariants(
        operational_state=operational_state,
        evidence_state=evidence_state,
        promotion_eligible=promotion_eligible,
        blockers=blockers,
        path=origin,
    )
    # Candidate generation admits only an unbound receipt state. Therefore the
    # candidate cannot itself be eligible for promotion, even if every local
    # record is eligible. Receipt binding and promotion are separate governed
    # write actions performed after independent byte verification.
    approval = _approval(manifest["approvalDecision"], f"{origin}.approvalDecision")
    # Keep the approval rule explicit even though candidate snapshots are also
    # refused below for having no receipt binding.
    if promotion_eligible and approval["decision"] != "APPROVED":
        raise _fail(f"{origin}.approvalDecision", "promotion eligibility requires APPROVED")
    if promotion_eligible:
        raise _fail(
            f"{origin}.promotionEligible",
            "candidate snapshots with an unbound receipt must not be promotion eligible",
        )
    return {
        "schemaVersion": INPUT_SCHEMA,
        "programId": PROGRAM_ID,
        "snapshotId": _identifier(manifest["snapshotId"], f"{origin}.snapshotId"),
        "generatedAt": _timestamp(manifest["generatedAt"], f"{origin}.generatedAt"),
        "generator": _generator(manifest["generator"], f"{origin}.generator"),
        "source": _source(manifest["source"], f"{origin}.source"),
        "revision": _text(manifest["revision"], f"{origin}.revision", maximum=512),
        "collectedAt": _timestamp(manifest["collectedAt"], f"{origin}.collectedAt"),
        "coverage": _coverage(
            manifest["coverage"], f"{origin}.coverage", compute_observed=len(records)
        ),
        "maturity": maturity,
        "operationalState": operational_state,
        "evidenceState": evidence_state,
        "promotionEligible": promotion_eligible,
        "records": sorted(records, key=lambda item: item["recordId"]),
        "risks": _string_array(manifest["risks"], f"{origin}.risks"),
        "blockers": blockers,
        "approvalDecision": approval,
        "receiptBinding": _unbound_receipt(
            manifest["receiptBinding"], f"{origin}.receiptBinding"
        ),
    }


def build_snapshot(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return schema-exact output and its canonical ``sha256:`` digest."""

    normalized = validate_input_manifest(dict(manifest))
    snapshot = {**normalized, "schemaVersion": OUTPUT_SCHEMA}
    digest_input = {
        key: value for key, value in snapshot.items() if key not in {"generatedAt", "digest"}
    }
    snapshot["digest"] = canonical_digest(digest_input)
    # Preserve schema property order for readable output. Canonical digesting is
    # sort-key based and is therefore independent of insertion order.
    output_order = (
        "schemaVersion",
        "programId",
        "snapshotId",
        "generatedAt",
        "digest",
        "generator",
        "source",
        "revision",
        "collectedAt",
        "coverage",
        "maturity",
        "operationalState",
        "evidenceState",
        "promotionEligible",
        "records",
        "risks",
        "blockers",
        "approvalDecision",
        "receiptBinding",
    )
    return {key: snapshot[key] for key in output_order}


def load_manifest(path: Path, *, max_bytes: int) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        path_state = os.lstat(path)
        if stat.S_ISLNK(path_state.st_mode):
            raise LatheSnapshotError(f"{path}: symbolic links are not accepted")
        if not stat.S_ISREG(before.st_mode):
            raise LatheSnapshotError(f"{path}: must be a regular file")
        if (before.st_dev, before.st_ino) != (path_state.st_dev, path_state.st_ino):
            raise LatheSnapshotError(f"{path}: path identity changed during open")
        if before.st_size > max_bytes:
            raise LatheSnapshotError(
                f"{path}: file is {before.st_size} bytes; limit is {max_bytes}"
            )
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            raw = handle.read(max_bytes + 1)
            after = os.fstat(handle.fileno())
        if len(raw) > max_bytes:
            raise LatheSnapshotError(f"{path}: content exceeds limit {max_bytes}")
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or len(raw) != after.st_size
        ):
            raise LatheSnapshotError(f"{path}: file changed while it was being read")
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                LatheSnapshotError(f"{path}: non-finite JSON value {token!r} is forbidden")
            ),
        )
    except UnicodeDecodeError as exc:
        raise LatheSnapshotError(f"{path}: must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise LatheSnapshotError(
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except RecursionError as exc:
        raise LatheSnapshotError(f"{path}: JSON nesting is too deep") from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise LatheSnapshotError(f"{path}: symbolic links are not accepted") from exc
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return validate_input_manifest(value, path.name)


def _bounded_bytes(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max-bytes must be an integer") from exc
    if parsed < 1 or parsed > HARD_MAX_BYTES:
        raise argparse.ArgumentTypeError(f"max-bytes must be between 1 and {HARD_MAX_BYTES}")
    return parsed


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="MANIFEST.json",
        help="One explicit bounded szl.lathe.input.v1 manifest",
    )
    parser.add_argument(
        "--output",
        default="-",
        metavar="SNAPSHOT.json",
        help="Atomic snapshot destination, or - for stdout",
    )
    parser.add_argument(
        "--max-bytes",
        type=_bounded_bytes,
        default=DEFAULT_MAX_BYTES,
        help="Maximum admitted input bytes",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    input_path = Path(args.input)
    output_path = None if args.output == "-" else Path(args.output)
    try:
        if output_path is not None and input_path.resolve(strict=True) == output_path.resolve(strict=False):
            raise LatheSnapshotError("output path may not overwrite the input manifest")
        manifest = load_manifest(input_path, max_bytes=args.max_bytes)
        snapshot = build_snapshot(manifest)
        rendered = json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        payload = rendered.encode("utf-8")
        if output_path is None:
            sys.stdout.buffer.write(payload)
        else:
            _atomic_write(output_path, payload)
    except (LatheSnapshotError, OSError) as exc:
        print(f"lathe snapshot refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
