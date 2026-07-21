# SPDX-License-Identifier: Apache-2.0
"""Adversarial contract tests for the bounded One Lathe snapshot generator."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lathe_snapshot.py"
SCHEMA_PATH = ROOT / "schemas" / "lathe" / "program-snapshot.v1.schema.json"
ARTIFACT_PATH = ROOT / "artifacts" / "lathe" / "program-snapshot.v1.json"

SPEC = importlib.util.spec_from_file_location("lathe_snapshot", SCRIPT)
assert SPEC and SPEC.loader
lathe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lathe)


def _source(locator: str = "docs/ecosystem-registry.json") -> dict:
    return {"type": "FILE", "locator": locator}


def _coverage(record_id: str, *, expected: int | None = 1) -> dict:
    return {
        "bounded": True,
        "discoveryMode": "EXPLICIT_INPUT_SET",
        "scope": f"Explicitly named evidence for {record_id}",
        "bounds": [f"record:{record_id}"],
        "included": [record_id],
        "excluded": [],
        "missing": [],
        "expectedCount": expected,
        "observedCount": 1,
        "complete": expected == 1,
    }


def _record(record_id: str = "a11oy-repository") -> dict:
    evidence_id = f"{record_id}.identity.evidence"
    return {
        "recordId": record_id,
        "assetType": "REPOSITORY",
        "source": _source(),
        "revision": "git:0123456789abcdef",
        "collectedAt": "2026-07-18T12:00:00Z",
        "coverage": _coverage(record_id),
        "maturity": "MODELED",
        "operationalState": "NOT_EVALUATED",
        "evidenceState": "PARTIAL",
        "promotionEligible": False,
        "evidence": [
            {
                "evidenceId": evidence_id,
                "propertyKind": "IDENTITY",
                "kind": "SOURCE_FILE",
                "source": _source(),
                "revision": "git:0123456789abcdef",
                "collectedAt": "2026-07-18T12:00:00Z",
                "admissionState": "PARTIAL",
                "digest": "sha256:" + "a" * 64,
                "summary": "The named repository record exists in the bounded input.",
            }
        ],
        "claims": [
            {
                "claimId": f"{record_id}.identity.claim",
                "propertyKind": "IDENTITY",
                "propertyName": "bounded identity",
                "assertion": "The record identifies only the explicitly supplied source.",
                "maturity": "MODELED",
                "operationalState": "NOT_EVALUATED",
                "evidenceState": "PARTIAL",
                "source": _source(),
                "revision": "git:0123456789abcdef",
                "collectedAt": "2026-07-18T12:00:00Z",
                "coverage": _coverage(record_id),
                "evidenceIds": [evidence_id],
                "freshness": {
                    "evaluatedAt": "2026-07-18T12:00:00Z",
                    "maxAgeSeconds": 3600,
                    "status": "UNKNOWN",
                },
                "promotionEligible": False,
                "blockers": ["Runtime behavior was not evaluated."],
            }
        ],
        "blockers": ["Runtime behavior was not evaluated."],
        "risks": ["A source record is not evidence of live operation."],
    }


def _manifest(records: list[dict] | None = None) -> dict:
    records = records if records is not None else [_record()]
    ids = [record["recordId"] for record in records]
    return {
        "schemaVersion": "szl.lathe.input.v1",
        "programId": "szl-one-lathe-frontier-program",
        "snapshotId": "one-lathe-2026-07-18",
        "generatedAt": "2026-07-18T12:30:00Z",
        "generator": {
            "name": "szl-one-lathe-snapshot",
            "version": "1",
            "source": "scripts/lathe_snapshot.py",
            "revision": "git:0123456789abcdef",
        },
        "source": _source("manifest/one-lathe-input.json"),
        "revision": "git:0123456789abcdef",
        "collectedAt": "2026-07-18T12:00:00Z",
        "coverage": {
            "bounded": True,
            "discoveryMode": "EXPLICIT_INPUT_SET",
            "scope": "Only explicitly named One Lathe evidence records",
            "bounds": ["manifest:one-lathe-input"],
            "included": sorted(ids),
            "excluded": [],
            "missing": [],
            "expectedCount": len(records),
            "observedCount": len(records),
            "complete": True,
        },
        "maturity": "MODELED",
        "operationalState": "NOT_EVALUATED",
        "evidenceState": "PARTIAL",
        "promotionEligible": False,
        "records": records,
        "risks": ["The snapshot does not establish manufacturing safety or operation."],
        "blockers": ["Independent runtime and safety verification is absent."],
        "approvalDecision": {
            "decision": "NOT_EVALUATED",
            "scope": "Candidate snapshot generation only",
            "actor": "operator-declaration",
            "decidedAt": "2026-07-18T12:00:00Z",
            "source": _source("manifest/approval.json"),
            "revision": "declaration:1",
        },
        "receiptBinding": {
            "state": "NOT_EVALUATED",
            "blockers": ["No independently verified receipt binding exists."],
        },
    }


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_snapshot(snapshot: dict) -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(snapshot),
        key=lambda error: list(error.absolute_path),
    )
    assert not errors, "\n".join(
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    )


def _digest_body(snapshot: dict) -> dict:
    return {
        key: value
        for key, value in snapshot.items()
        if key not in {"generatedAt", "digest"}
    }


def test_schema_is_strict_draft_2020_12() -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schemaVersion"]["const"] == "szl.lathe.snapshot.v1"


def test_committed_candidate_is_schema_valid_digest_bound_and_not_promotable() -> None:
    snapshot = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    _validate_snapshot(snapshot)
    assert snapshot["digest"] == lathe.canonical_digest(_digest_body(snapshot))
    assert snapshot["promotionEligible"] is False
    assert snapshot["approvalDecision"]["decision"] == "NOT_EVALUATED"
    assert snapshot["receiptBinding"]["state"] == "NOT_EVALUATED"
    assert len(snapshot["records"]) == 7


def test_cli_output_is_byte_deterministic_schema_valid_and_digest_bound(
    tmp_path: Path,
) -> None:
    # Deliberately reverse input order; the emitted records must normalize by ID.
    manifest = _manifest([_record("z-record"), _record("a-record")])
    source = _write_json(tmp_path / "manifest.json", manifest)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    for output in (first, second):
        result = _run("--input", source, "--output", output)
        assert result.returncode == 0, result.stderr

    assert first.read_bytes() == second.read_bytes()
    snapshot = json.loads(first.read_text(encoding="utf-8"))
    _validate_snapshot(snapshot)
    assert [record["recordId"] for record in snapshot["records"]] == [
        "a-record",
        "z-record",
    ]
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", snapshot["digest"])
    assert snapshot["digest"] == lathe.canonical_digest(_digest_body(snapshot))


def test_digest_exposes_tampering_and_bad_evidence_digest_is_rejected(
    tmp_path: Path,
) -> None:
    snapshot = lathe.build_snapshot(_manifest())
    original_digest = snapshot["digest"]
    tampered = copy.deepcopy(snapshot)
    tampered["records"][0]["revision"] = "git:tampered"
    assert lathe.canonical_digest(_digest_body(tampered)) != original_digest

    manifest = _manifest()
    manifest["records"][0]["evidence"][0]["digest"] = "sha256:not-a-digest"
    source = _write_json(tmp_path / "bad-digest.json", manifest)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "digest" in result.stderr


def test_unbounded_discovery_and_oversize_input_fail_closed(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["coverage"]["bounded"] = False
    source = _write_json(tmp_path / "unbounded.json", manifest)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "unbounded discovery is forbidden" in result.stderr

    bounded = _write_json(tmp_path / "bounded.json", _manifest())
    too_large = _run("--input", bounded, "--max-bytes", 64)
    assert too_large.returncode != 0
    assert "limit" in too_large.stderr


@pytest.mark.parametrize(
    "missing_path",
    ["record-source", "record-evidence", "evidence-source", "claim-evidence-ids"],
)
def test_missing_provenance_fails_closed(tmp_path: Path, missing_path: str) -> None:
    manifest = _manifest()
    record = manifest["records"][0]
    if missing_path == "record-source":
        record.pop("source")
    elif missing_path == "record-evidence":
        record["evidence"] = []
    elif missing_path == "evidence-source":
        record["evidence"][0].pop("source")
    else:
        record["claims"][0]["evidenceIds"] = []
    source = _write_json(tmp_path / f"{missing_path}.json", manifest)
    output = tmp_path / "must-not-exist.json"

    result = _run("--input", source, "--output", output)

    assert result.returncode != 0
    assert not output.exists()


def test_stale_evidence_requires_and_preserves_stale_null_state(tmp_path: Path) -> None:
    invalid = _manifest()
    claim = invalid["records"][0]["claims"][0]
    claim["freshness"]["status"] = "STALE"
    invalid_path = _write_json(tmp_path / "invalid-stale.json", invalid)
    result = _run("--input", invalid_path)
    assert result.returncode != 0
    assert "stale freshness requires" in result.stderr

    valid = _manifest()
    valid.update(
        operationalState="STALE_EVIDENCE",
        evidenceState="STALE",
        promotionEligible=False,
        blockers=["Top-level evidence is stale."],
    )
    record = valid["records"][0]
    record.update(
        operationalState="STALE_EVIDENCE",
        evidenceState="STALE",
        promotionEligible=False,
        blockers=["Record evidence is stale."],
    )
    record["evidence"][0]["admissionState"] = "STALE"
    claim = record["claims"][0]
    claim.update(
        operationalState="STALE_EVIDENCE",
        evidenceState="STALE",
        promotionEligible=False,
        blockers=["Claim evidence is stale."],
    )
    claim["freshness"]["status"] = "STALE"
    source = _write_json(tmp_path / "valid-stale.json", valid)
    output = tmp_path / "stale-snapshot.json"

    result = _run("--input", source, "--output", output)
    assert result.returncode == 0, result.stderr
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    _validate_snapshot(snapshot)
    assert snapshot["operationalState"] == "STALE_EVIDENCE"
    assert snapshot["evidenceState"] == "STALE"
    assert snapshot["promotionEligible"] is False
    assert snapshot["records"][0]["claims"][0]["freshness"]["status"] == "STALE"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maturity", None),
        ("maturity", "VERIFIED"),
        ("operationalState", None),
        ("operationalState", "OPERATIONAL"),
        ("evidenceState", None),
    ],
)
def test_invalid_maturity_and_null_states_fail_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    manifest = _manifest()
    manifest[field] = value
    source = _write_json(tmp_path / f"invalid-{field}.json", manifest)
    result = _run("--input", source)
    assert result.returncode != 0
    assert field in result.stderr


def test_null_state_and_bad_evidence_can_never_be_promotion_eligible(
    tmp_path: Path,
) -> None:
    cases: list[dict] = []

    root_null = _manifest()
    root_null["promotionEligible"] = True
    cases.append(root_null)

    record_null = _manifest()
    record_null["records"][0]["promotionEligible"] = True
    cases.append(record_null)

    claim_null = _manifest()
    claim_null["records"][0]["claims"][0]["promotionEligible"] = True
    cases.append(claim_null)

    sufficient_null = _manifest()
    sufficient_null["evidenceState"] = "SUFFICIENT"
    cases.append(sufficient_null)

    absent_promoted = _manifest()
    absent_promoted.update(
        operationalState="AVAILABLE",
        evidenceState="ABSENT",
        promotionEligible=True,
        blockers=[],
    )
    cases.append(absent_promoted)

    for index, manifest in enumerate(cases):
        source = _write_json(tmp_path / f"promotion-{index}.json", manifest)
        result = _run("--input", source)
        assert result.returncode != 0, f"case {index} unexpectedly admitted"


def test_duplicate_record_evidence_and_claim_ids_fail_closed(tmp_path: Path) -> None:
    duplicate_records = _manifest([_record("same-record"), _record("same-record")])
    source = _write_json(tmp_path / "duplicate-records.json", duplicate_records)
    assert _run("--input", source).returncode != 0

    duplicate_evidence = _manifest()
    evidence = duplicate_evidence["records"][0]["evidence"][0]
    duplicate_evidence["records"][0]["evidence"].append(copy.deepcopy(evidence))
    source = _write_json(tmp_path / "duplicate-evidence.json", duplicate_evidence)
    assert _run("--input", source).returncode != 0

    duplicate_claims = _manifest()
    claim = duplicate_claims["records"][0]["claims"][0]
    duplicate_claims["records"][0]["claims"].append(copy.deepcopy(claim))
    source = _write_json(tmp_path / "duplicate-claims.json", duplicate_claims)
    assert _run("--input", source).returncode != 0


def test_property_mismatched_or_unknown_evidence_reference_fails_closed(
    tmp_path: Path,
) -> None:
    mismatch = _manifest()
    mismatch["records"][0]["evidence"][0]["propertyKind"] = "PROVENANCE"
    source = _write_json(tmp_path / "mismatch.json", mismatch)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "property-kind mismatch" in result.stderr

    unknown = _manifest()
    unknown["records"][0]["claims"][0]["evidenceIds"] = ["unknown-evidence"]
    source = _write_json(tmp_path / "unknown-evidence.json", unknown)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "unknown evidence IDs" in result.stderr


def test_malformed_json_secret_fields_and_unknown_fields_fail_closed(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schemaVersion":', encoding="utf-8")
    output = tmp_path / "snapshot.json"
    result = _run("--input", malformed, "--output", output)
    assert result.returncode != 0
    assert "invalid JSON" in result.stderr
    assert not output.exists()

    secret_value = "must-not-appear-in-errors"
    secret = _manifest()
    secret["apiKey"] = secret_value
    source = _write_json(tmp_path / "secret.json", secret)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "secret-bearing fields are forbidden" in result.stderr
    assert secret_value not in result.stdout + result.stderr

    unknown = _manifest()
    unknown["quietlyAccepted"] = True
    source = _write_json(tmp_path / "unknown.json", unknown)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "unknown fields" in result.stderr


def test_proven_claim_is_limited_to_formal_property(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["records"][0]["claims"][0]["maturity"] = "PROVEN"
    source = _write_json(tmp_path / "inflated-proof.json", manifest)
    result = _run("--input", source)
    assert result.returncode != 0
    assert "PROVEN is valid only for FORMAL_PROPERTY" in result.stderr


@pytest.mark.parametrize("verification_state", ["FAILED", "NOT_EVALUATED"])
def test_unverified_bound_receipt_cannot_make_root_promotion_eligible(
    verification_state: str,
) -> None:
    snapshot = lathe.build_snapshot(_manifest())
    snapshot.update(
        operationalState="AVAILABLE",
        evidenceState="SUFFICIENT",
        promotionEligible=True,
        blockers=[],
    )
    snapshot["approvalDecision"]["decision"] = "APPROVED"
    snapshot["receiptBinding"] = {
        "state": "BOUND",
        "snapshotDigest": "sha256:" + "a" * 64,
        "receiptDigest": "sha256:" + "b" * 64,
        "source": _source("attestations/lathe/receipt.dsse.json"),
        "revision": "rekor:1",
        "collectedAt": "2026-07-18T12:00:00Z",
        "verificationState": verification_state,
    }

    errors = list(
        Draft202012Validator(
            _load_schema(), format_checker=FormatChecker()
        ).iter_errors(snapshot)
    )
    assert any(
        list(error.absolute_path) == ["promotionEligible"] for error in errors
    )
