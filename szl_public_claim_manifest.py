#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded, deterministic EvidenceOS public-claim manifest evaluation.

The evaluator verifies a deliberately small contract: reviewed claim metadata,
explicit repository-relative evidence paths, content digests, freshness policy,
and maturity/evidence-kind compatibility.  It does not crawl a repository,
interpret evidence, infer truth, execute reproduction commands, sign results,
or enable effectors.

Repository reads are optional and bounded.  Without an explicit repository
root every evidence item is reported ``NOT_EVALUATED``.  With a root, paths are
confined to that root, symlink escapes are refused, files larger than the fixed
limit are not hashed, and every non-current state fails closed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


MODULE_ID = "szl-public-claim-manifest"
SCHEMA_VERSION = "1.0.0"
PROPOSAL_ONLY = "PROPOSAL_ONLY"
NO_EFFECTORS = 0

MATURITY_CLASSES = ("PROVEN", "MEASURED", "MODELED", "CONJECTURE", "OPEN")
FRESHNESS_STATES = ("CURRENT", "STALE", "MISSING", "UNKNOWN", "NOT_EVALUATED")
EVIDENCE_KINDS = (
    "FORMAL_PROOF",
    "TEST_RECEIPT",
    "MEASUREMENT_RECEIPT",
    "MODEL_OUTPUT",
    "CONJECTURE_RECORD",
    "OPEN_ISSUE",
    "SOURCE_RECORD",
)

MAX_CLAIMS = 64
MAX_EVIDENCE_PER_CLAIM = 8
MAX_CONSUMERS_PER_CLAIM = 16
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_ID_CHARS = 128
MAX_ASSERTION_CHARS = 4096
MAX_REFERENCE_CHARS = 1024
MAX_SCOPE_CHARS = 1024
MAX_REPRODUCTION_ARGS = 32
MAX_REPRODUCTION_ARG_CHARS = 256
MAX_MAX_AGE_SECONDS = 31_536_000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
_MATURITY_KINDS = {
    "PROVEN": frozenset({"FORMAL_PROOF"}),
    "MEASURED": frozenset({"MEASUREMENT_RECEIPT", "TEST_RECEIPT"}),
    "MODELED": frozenset({"MODEL_OUTPUT"}),
    "CONJECTURE": frozenset({"CONJECTURE_RECORD", "SOURCE_RECORD"}),
    "OPEN": frozenset({"OPEN_ISSUE"}),
}
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class PublicClaimContractError(ValueError):
    """A deterministic structural refusal suitable for an HTTP 422 mapping."""


def _error(path: str, message: str) -> PublicClaimContractError:
    return PublicClaimContractError(f"{path}: {message}")


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(path, "must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extras = sorted(str(key) for key in value if not isinstance(key, str) or key not in allowed)
    if extras:
        raise _error(path, f"unknown field(s): {', '.join(extras)}")


def _string(value: Any, path: str, *, maximum: int, nonblank: bool = True) -> str:
    if not isinstance(value, str):
        raise _error(path, "must be a string")
    if len(value) > maximum:
        raise _error(path, f"must be at most {maximum} characters")
    normalized = value.strip()
    if nonblank and not normalized:
        raise _error(path, "must not be blank")
    return normalized


def _identifier(value: Any, path: str) -> str:
    normalized = _string(value, path, maximum=MAX_ID_CHARS)
    return unicodedata.normalize("NFC", normalized).casefold()


def _array(value: Any, path: str, *, maximum: int, nonempty: bool = False) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise _error(path, "must be an array")
    if nonempty and not value:
        raise _error(path, "must not be empty")
    if len(value) > maximum:
        raise _error(path, f"must contain at most {maximum} items")
    return value


def _timestamp(value: Any, path: str) -> tuple[str, datetime]:
    raw = _string(value, path, maximum=32)
    if not _UTC_TIMESTAMP_RE.fullmatch(raw):
        raise _error(path, "must be a UTC RFC 3339 timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError as exc:
        raise _error(path, "must be a valid RFC 3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise _error(path, "must use UTC")
    parsed = parsed.astimezone(timezone.utc)
    canonical = parsed.strftime("%Y-%m-%dT%H:%M:%S")
    if parsed.microsecond:
        canonical += "." + f"{parsed.microsecond:06d}".rstrip("0")
    return canonical + "Z", parsed


def _relative_path(value: Any, path: str) -> str:
    raw = _string(value, path, maximum=MAX_REFERENCE_CHARS)
    if "\\" in raw or "\x00" in raw:
        raise _error(path, "must use a safe POSIX repository-relative path")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise _error(path, "must be a safe repository-relative path")
    for part in candidate.parts:
        if ":" in part:
            raise _error(path, "must not contain a drive or URI scheme")
        if part.endswith((".", " ")):
            raise _error(path, "must not contain Windows-ambiguous path segments")
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise _error(path, "must not contain a reserved Windows device name")
    return candidate.as_posix()


def _parse_owner(value: Any, path: str) -> dict[str, str]:
    raw = _object(value, path)
    _exact_keys(raw, {"owner_id", "accountability_scope"}, path)
    for key in ("owner_id", "accountability_scope"):
        if key not in raw:
            raise _error(f"{path}.{key}", "is required")
    return {
        "owner_id": _identifier(raw["owner_id"], f"{path}.owner_id"),
        "accountability_scope": _string(
            raw["accountability_scope"], f"{path}.accountability_scope", maximum=MAX_SCOPE_CHARS,
        ),
    }


def _parse_source(value: Any, path: str) -> dict[str, str]:
    raw = _object(value, path)
    _exact_keys(raw, {"repository", "revision"}, path)
    for key in ("repository", "revision"):
        if key not in raw:
            raise _error(f"{path}.{key}", "is required")
    return {
        "repository": _string(raw["repository"], f"{path}.repository", maximum=MAX_REFERENCE_CHARS),
        "revision": _string(raw["revision"], f"{path}.revision", maximum=MAX_ID_CHARS),
    }


def _parse_evidence(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    allowed = {
        "evidence_id", "path", "content_sha256", "collected_at",
        "max_age_seconds", "kind", "verification_ref",
    }
    _exact_keys(raw, allowed, path)
    missing = sorted(allowed - set(raw))
    if missing:
        raise _error(path, f"missing required field(s): {', '.join(missing)}")

    digest = _string(raw["content_sha256"], f"{path}.content_sha256", maximum=64)
    if not _SHA256_RE.fullmatch(digest):
        raise _error(f"{path}.content_sha256", "must be 64 lowercase hexadecimal characters")
    max_age = raw["max_age_seconds"]
    if isinstance(max_age, bool) or not isinstance(max_age, int):
        raise _error(f"{path}.max_age_seconds", "must be an integer")
    if not 1 <= max_age <= MAX_MAX_AGE_SECONDS:
        raise _error(
            f"{path}.max_age_seconds",
            f"must be between 1 and {MAX_MAX_AGE_SECONDS}",
        )
    kind = _string(raw["kind"], f"{path}.kind", maximum=32).upper()
    if kind not in EVIDENCE_KINDS:
        raise _error(f"{path}.kind", "must be a known evidence kind")
    collected_at, _ = _timestamp(raw["collected_at"], f"{path}.collected_at")
    return {
        "evidence_id": _identifier(raw["evidence_id"], f"{path}.evidence_id"),
        "path": _relative_path(raw["path"], f"{path}.path"),
        "content_sha256": digest,
        "collected_at": collected_at,
        "max_age_seconds": max_age,
        "kind": kind,
        "verification_ref": _string(
            raw["verification_ref"], f"{path}.verification_ref", maximum=MAX_REFERENCE_CHARS,
        ),
    }


def _parse_claim(value: Any, path: str) -> dict[str, Any]:
    raw = _object(value, path)
    allowed = {
        "claim_id", "assertion", "maturity", "scope", "owner", "consumers",
        "source", "evidence", "reproduction_argv",
    }
    _exact_keys(raw, allowed, path)
    missing = sorted(allowed - set(raw))
    if missing:
        raise _error(path, f"missing required field(s): {', '.join(missing)}")
    maturity = _string(raw["maturity"], f"{path}.maturity", maximum=16).upper()
    if maturity not in MATURITY_CLASSES:
        raise _error(f"{path}.maturity", "must be a known maturity class")
    consumer_rows = _array(
        raw["consumers"], f"{path}.consumers", maximum=MAX_CONSUMERS_PER_CLAIM, nonempty=True,
    )
    consumers = [
        _identifier(item, f"{path}.consumers[{index}]")
        for index, item in enumerate(consumer_rows)
    ]
    if len(consumers) != len(set(consumers)):
        raise _error(f"{path}.consumers", "values must be unique after normalization")
    evidence_rows = _array(
        raw["evidence"], f"{path}.evidence", maximum=MAX_EVIDENCE_PER_CLAIM, nonempty=True,
    )
    return {
        "claim_id": _identifier(raw["claim_id"], f"{path}.claim_id"),
        "assertion": _string(raw["assertion"], f"{path}.assertion", maximum=MAX_ASSERTION_CHARS),
        "maturity": maturity,
        "scope": _string(raw["scope"], f"{path}.scope", maximum=MAX_SCOPE_CHARS),
        "owner": _parse_owner(raw["owner"], f"{path}.owner"),
        "consumers": sorted(consumers),
        "source": _parse_source(raw["source"], f"{path}.source"),
        "evidence": sorted(
            (
                _parse_evidence(row, f"{path}.evidence[{index}]")
                for index, row in enumerate(evidence_rows)
            ),
            key=lambda row: row["evidence_id"],
        ),
        "reproduction_argv": [
            _string(
                item,
                f"{path}.reproduction_argv[{index}]",
                maximum=MAX_REPRODUCTION_ARG_CHARS,
            )
            for index, item in enumerate(
                _array(
                    raw["reproduction_argv"],
                    f"{path}.reproduction_argv",
                    maximum=MAX_REPRODUCTION_ARGS,
                    nonempty=True,
                )
            )
        ],
    }


def parse_public_claim_manifest(payload: Any) -> dict[str, Any]:
    """Validate and canonicalize a bounded public-claim manifest."""
    raw = _object(payload, "$manifest")
    allowed = {"schema_version", "manifest_id", "revision", "generated_at", "claims"}
    _exact_keys(raw, allowed, "$manifest")
    missing = sorted(allowed - set(raw))
    if missing:
        raise _error("$manifest", f"missing required field(s): {', '.join(missing)}")
    version = _string(raw["schema_version"], "$manifest.schema_version", maximum=16)
    if version != SCHEMA_VERSION:
        raise _error("$manifest.schema_version", f"must equal {SCHEMA_VERSION}")
    generated_at, _ = _timestamp(raw["generated_at"], "$manifest.generated_at")
    claim_rows = _array(raw["claims"], "$manifest.claims", maximum=MAX_CLAIMS, nonempty=True)
    claims = sorted(
        (_parse_claim(row, f"$manifest.claims[{index}]") for index, row in enumerate(claim_rows)),
        key=lambda row: row["claim_id"],
    )

    claim_ids = [claim["claim_id"] for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise _error("$manifest.claims", "claim_id values must be unique after normalization")
    evidence_ids = [item["evidence_id"] for claim in claims for item in claim["evidence"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise _error("$manifest.claims", "evidence_id values must be globally unique after normalization")
    return {
        "schema_version": version,
        "manifest_id": _identifier(raw["manifest_id"], "$manifest.manifest_id"),
        "revision": _string(raw["revision"], "$manifest.revision", maximum=MAX_ID_CHARS),
        "generated_at": generated_at,
        "claims": claims,
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _read_bounded_file(path: Path) -> tuple[bytes | None, str | None]:
    try:
        if not path.is_file():
            return None, "EVIDENCE_MISSING"
        with path.open("rb") as handle:
            content = handle.read(MAX_EVIDENCE_BYTES + 1)
        if len(content) > MAX_EVIDENCE_BYTES:
            return None, "EVIDENCE_TOO_LARGE"
        return content, None
    except OSError:
        return None, "EVIDENCE_READ_ERROR"


def _validate_test_receipt(
    content: bytes,
    *,
    evidence: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> list[str]:
    try:
        receipt = strict_json_loads(content.decode("utf-8"))
        receipt = _object(receipt, "$test_receipt")
    except (UnicodeError, PublicClaimContractError):
        return ["EVIDENCE_CONTRACT_INVALID"]

    required = {
        "schema_version", "subject", "repository", "source_revision", "workflow",
        "job", "source_url", "completed_at", "command", "tests_passed", "warnings",
        "exit_code", "conclusion", "signed", "attests_truth", "scope",
    }
    if set(receipt) != required:
        return ["EVIDENCE_CONTRACT_INVALID"]
    try:
        completed_text, _ = _timestamp(receipt["completed_at"], "$test_receipt.completed_at")
        command = _array(receipt["command"], "$test_receipt.command", maximum=32, nonempty=True)
        command_argv = [
            _string(part, "$test_receipt.command[]", maximum=256) for part in command
        ]
    except PublicClaimContractError:
        return ["EVIDENCE_CONTRACT_INVALID"]

    integer_fields = ("tests_passed", "warnings", "exit_code")
    if any(isinstance(receipt[key], bool) or not isinstance(receipt[key], int) for key in integer_fields):
        return ["EVIDENCE_CONTRACT_INVALID"]
    if not isinstance(receipt["signed"], bool) or receipt["signed"] is not False:
        return ["EVIDENCE_CONTRACT_INVALID"]
    if not isinstance(receipt["attests_truth"], bool) or receipt["attests_truth"] is not False:
        return ["EVIDENCE_CONTRACT_INVALID"]

    expected = {
        "schema_version": "test-receipt.v1",
        "repository": claim["source"]["repository"],
        "source_revision": claim["source"]["revision"],
        "source_url": evidence["verification_ref"],
        "completed_at": evidence["collected_at"],
        "command_argv": claim["reproduction_argv"],
    }
    actual = {
        "schema_version": receipt["schema_version"],
        "repository": receipt["repository"],
        "source_revision": receipt["source_revision"],
        "source_url": receipt["source_url"],
        "completed_at": completed_text,
        "command_argv": command_argv,
    }
    if actual != expected:
        return ["EVIDENCE_CONTRACT_BINDING_MISMATCH"]
    if receipt["tests_passed"] < 1 or receipt["warnings"] < 0:
        return ["EVIDENCE_CONTRACT_INVALID"]
    if receipt["exit_code"] != 0 or receipt["conclusion"] != "SUCCESS":
        return ["EVIDENCE_CONTRACT_FAILED"]
    for key in ("subject", "workflow", "job", "scope"):
        if not isinstance(receipt[key], str) or not receipt[key].strip():
            return ["EVIDENCE_CONTRACT_INVALID"]
    return []


def _validate_evidence_contract(
    content: bytes,
    *,
    evidence: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> list[str]:
    if evidence["kind"] == "TEST_RECEIPT":
        return _validate_test_receipt(content, evidence=evidence, claim=claim)
    return ["EVIDENCE_KIND_VALIDATOR_UNAVAILABLE"]


def _evaluate_evidence(
    evidence: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    as_of: datetime,
    repository_root: Path | None,
) -> dict[str, Any]:
    violations: list[str] = []
    state = "NOT_EVALUATED"
    observed_digest: str | None = None
    collected_text, collected_at = _timestamp(evidence["collected_at"], "$evidence.collected_at")
    age_seconds = int((as_of - collected_at).total_seconds())

    if collected_at > as_of:
        state = "UNKNOWN"
        violations.append("FUTURE_COLLECTION_TIMESTAMP")
    elif repository_root is None:
        violations.append("REPOSITORY_NOT_EVALUATED")
    else:
        root = repository_root.resolve()
        candidate = (root / Path(*PurePosixPath(evidence["path"]).parts)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            state = "UNKNOWN"
            violations.append("PATH_ESCAPES_REPOSITORY")
        else:
            content, read_error = _read_bounded_file(candidate)
            if read_error == "EVIDENCE_MISSING":
                state = "MISSING"
                violations.append(read_error)
            elif read_error is not None:
                state = "UNKNOWN"
                violations.append(read_error)
            else:
                observed_digest = hashlib.sha256(content).hexdigest()
            if read_error is None and observed_digest != evidence["content_sha256"]:
                state = "UNKNOWN"
                violations.append("CONTENT_DIGEST_MISMATCH")
            elif read_error is None:
                contract_violations = _validate_evidence_contract(
                    content, evidence=evidence, claim=claim,
                )
                if contract_violations:
                    state = "UNKNOWN"
                    violations.extend(contract_violations)
                elif age_seconds <= evidence["max_age_seconds"]:
                    state = "CURRENT"
                else:
                    state = "STALE"
                    violations.append("FRESHNESS_SLA_EXCEEDED")

    return {
        "evidence_id": evidence["evidence_id"],
        "path": evidence["path"],
        "kind": evidence["kind"],
        "freshness_state": state,
        "collected_at": collected_text,
        "max_age_seconds": evidence["max_age_seconds"],
        "age_seconds": age_seconds,
        "expected_content_sha256": evidence["content_sha256"],
        "observed_content_sha256": observed_digest,
        "verification_ref": evidence["verification_ref"],
        "violations": violations,
    }


def evaluate_public_claim_manifest(
    payload: Any,
    *,
    as_of: str,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate an explicit manifest and emit an unsigned deterministic report."""
    manifest = parse_public_claim_manifest(payload)
    as_of_text, as_of_dt = _timestamp(as_of, "$as_of")
    generated_text, generated_dt = _timestamp(manifest["generated_at"], "$manifest.generated_at")
    root = Path(repository_root) if repository_root is not None else None

    manifest_violations: list[str] = []
    if generated_dt > as_of_dt:
        manifest_violations.append("FUTURE_MANIFEST_TIMESTAMP")

    claim_reports = []
    for claim in manifest["claims"]:
        evidence_reports = [
            _evaluate_evidence(item, claim=claim, as_of=as_of_dt, repository_root=root)
            for item in claim["evidence"]
        ]
        claim_violations = sorted({
            violation
            for item in evidence_reports
            for violation in item["violations"]
        })
        compatible_kinds = _MATURITY_KINDS[claim["maturity"]]
        if not any(item["kind"] in compatible_kinds for item in evidence_reports):
            claim_violations.append("MATURITY_EVIDENCE_MISMATCH")
        claim_violations = sorted(set(claim_violations))
        current = all(item["freshness_state"] == "CURRENT" for item in evidence_reports)
        claim_reports.append({
            "claim_id": claim["claim_id"],
            "assertion": claim["assertion"],
            "maturity": claim["maturity"],
            "scope": claim["scope"],
            "owner": claim["owner"],
            "consumers": claim["consumers"],
            "source": claim["source"],
            "reproduction_argv": claim["reproduction_argv"],
            "evidence": evidence_reports,
            "passes": current and not claim_violations,
            "violations": claim_violations,
        })

    passes = not manifest_violations and all(claim["passes"] for claim in claim_reports)
    freshness_counts = {
        state: sum(
            1
            for claim in claim_reports
            for evidence in claim["evidence"]
            if evidence["freshness_state"] == state
        )
        for state in FRESHNESS_STATES
    }
    core = {
        "module": MODULE_ID,
        "schema_version": SCHEMA_VERSION,
        "manifest_id": manifest["manifest_id"],
        "manifest_revision": manifest["revision"],
        "manifest_generated_at": generated_text,
        "manifest_content_sha256": _digest(manifest),
        "evaluated_as_of": as_of_text,
        "decision_state": PROPOSAL_ONLY,
        "effectors_enabled": NO_EFFECTORS,
        "claim_count": len(claim_reports),
        "freshness_counts": freshness_counts,
        "passes": passes,
        "outcome": "PASS" if passes else "REFUSE",
        "manifest_violations": manifest_violations,
        "claims": claim_reports,
        "honesty_invariants": {
            "explicit_paths_only": True,
            "repository_crawling": False,
            "reproduction_commands_executed": False,
            "truth_inference": False,
            "unsigned_report": True,
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


def strict_json_loads(text: str) -> Any:
    """Decode JSON while refusing duplicate object keys."""
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PublicClaimContractError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=pairs_hook)
    except json.JSONDecodeError as exc:
        raise PublicClaimContractError(f"invalid JSON: {exc.msg}") from exc
