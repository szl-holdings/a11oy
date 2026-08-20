# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
import szl_public_claim_manifest as pcm
from scripts import check_public_claim_manifest as cli
from scripts import verify_public_claim_github_job as github_verify


AS_OF = "2026-07-18T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(root: Path, *, maturity: str = "MEASURED", kind: str = "TEST_RECEIPT") -> dict:
    evidence = root / "evidence.txt"
    command = ["python", "-m", "pytest", "-q", "tests/test_claim_rupture_gate.py"]
    if kind == "TEST_RECEIPT":
        evidence.write_text(json.dumps({
            "schema_version": "test-receipt.v1",
            "subject": "Focused source contract",
            "repository": "szl-holdings/a11oy",
            "source_revision": "122ae740",
            "workflow": "Claim Compiler contract",
            "job": "bounded route and core contract",
            "source_url": "workflow:claim-compiler",
            "completed_at": AS_OF,
            "command": command,
            "tests_passed": 1,
            "warnings": 0,
            "exit_code": 0,
            "conclusion": "SUCCESS",
            "signed": False,
            "attests_truth": False,
            "scope": "Records the cited test result only.",
        }, sort_keys=True), encoding="utf-8")
    else:
        evidence.write_text("bounded evidence\n", encoding="utf-8")
    return {
        "schema_version": "1.0.0",
        "manifest_id": "integrity-control",
        "revision": "122ae740",
        "generated_at": AS_OF,
        "claims": [
            {
                "claim_id": "claim-bound",
                "assertion": "The checked source contract is bounded.",
                "maturity": maturity,
                "scope": "Source-tree contract only; not a live-service assertion.",
                "owner": {
                    "owner_id": "szl-holdings:a11oy",
                    "accountability_scope": "EvidenceOS Claim Compiler",
                },
                "consumers": ["ci", "integrity-control"],
                "source": {"repository": "szl-holdings/a11oy", "revision": "122ae740"},
                "evidence": [
                    {
                        "evidence_id": "focused-test-receipt",
                        "path": "evidence.txt",
                        "content_sha256": _sha(evidence),
                        "collected_at": AS_OF,
                        "max_age_seconds": 60,
                        "kind": kind,
                        "verification_ref": "workflow:claim-compiler",
                    }
                ],
                "reproduction_argv": command,
            }
        ],
    }


def _evaluate(root: Path, manifest: dict, *, as_of: str = AS_OF):
    return pcm.evaluate_public_claim_manifest(manifest, as_of=as_of, repository_root=root)


def test_current_manifest_passes_with_zero_effectors(tmp_path):
    report = _evaluate(tmp_path, _manifest(tmp_path))
    assert report["passes"] is True
    assert report["outcome"] == "PASS"
    assert report["decision_state"] == "PROPOSAL_ONLY"
    assert report["effectors_enabled"] == 0
    assert report["freshness_counts"] == {
        "CURRENT": 1, "STALE": 0, "MISSING": 0, "UNKNOWN": 0, "NOT_EVALUATED": 0,
    }
    assert report["receipt"]["signed"] is False
    assert report["receipt"]["attests_truth"] is False


def test_stale_boundary_is_current_and_plus_one_is_stale(tmp_path):
    manifest = _manifest(tmp_path)
    boundary = _evaluate(tmp_path, manifest, as_of="2026-07-18T12:01:00Z")
    assert boundary["claims"][0]["evidence"][0]["freshness_state"] == "CURRENT"
    stale = _evaluate(tmp_path, manifest, as_of="2026-07-18T12:01:01Z")
    assert stale["passes"] is False
    assert stale["claims"][0]["evidence"][0]["freshness_state"] == "STALE"
    assert "FRESHNESS_SLA_EXCEEDED" in stale["claims"][0]["violations"]


def test_fractional_second_past_freshness_boundary_is_stale(tmp_path):
    manifest = _manifest(tmp_path)
    report = _evaluate(
        tmp_path,
        manifest,
        as_of="2026-07-18T12:01:00.000001Z",
    )
    evidence = report["claims"][0]["evidence"][0]
    assert evidence["freshness_state"] == "STALE"
    assert evidence["age_seconds"] == 61
    assert "FRESHNESS_SLA_EXCEEDED" in evidence["violations"]


def test_future_collection_timestamp_fails_closed(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["claims"][0]["evidence"][0]["collected_at"] = "2026-07-18T12:00:01Z"
    report = _evaluate(tmp_path, manifest)
    evidence = report["claims"][0]["evidence"][0]
    assert report["passes"] is False
    assert evidence["freshness_state"] == "UNKNOWN"
    assert evidence["violations"] == ["FUTURE_COLLECTION_TIMESTAMP"]


def test_fractional_future_timestamp_is_not_truncated(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["claims"][0]["evidence"][0]["collected_at"] = "2026-07-18T12:00:00.000001Z"
    report = _evaluate(tmp_path, manifest)
    assert report["claims"][0]["evidence"][0]["violations"] == ["FUTURE_COLLECTION_TIMESTAMP"]

    manifest = _manifest(tmp_path)
    manifest["generated_at"] = "2026-07-18T12:00:00.000001Z"
    assert _evaluate(tmp_path, manifest)["manifest_violations"] == ["FUTURE_MANIFEST_TIMESTAMP"]


def test_future_manifest_timestamp_fails_closed(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["generated_at"] = "2026-07-18T12:00:01Z"
    report = _evaluate(tmp_path, manifest)
    assert report["passes"] is False
    assert report["manifest_violations"] == ["FUTURE_MANIFEST_TIMESTAMP"]


@pytest.mark.parametrize("timestamp", ["2026-07-18T12:00:00", "not-a-time", "2026-07-18 12:00:00Z"])
def test_non_utc_or_malformed_timestamps_are_contract_refusals(tmp_path, timestamp):
    manifest = _manifest(tmp_path)
    manifest["generated_at"] = timestamp
    with pytest.raises(pcm.PublicClaimContractError):
        _evaluate(tmp_path, manifest)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-07-18T12:00:00.1234567Z",
        "2026-07-18T12:00:00.12345678Z",
    ],
)
def test_more_than_six_fractional_timestamp_digits_are_refused(tmp_path, timestamp):
    manifest = _manifest(tmp_path)
    manifest["generated_at"] = timestamp
    with pytest.raises(pcm.PublicClaimContractError, match="RFC 3339"):
        _evaluate(tmp_path, manifest)


def test_missing_and_digest_mismatch_are_distinct_fail_closed_states(tmp_path):
    manifest = _manifest(tmp_path)
    (tmp_path / "evidence.txt").unlink()
    missing = _evaluate(tmp_path, manifest)
    assert missing["claims"][0]["evidence"][0]["freshness_state"] == "MISSING"

    (tmp_path / "evidence.txt").write_text("changed\n", encoding="utf-8")
    mismatch = _evaluate(tmp_path, manifest)
    evidence = mismatch["claims"][0]["evidence"][0]
    assert evidence["freshness_state"] == "UNKNOWN"
    assert "CONTENT_DIGEST_MISMATCH" in evidence["violations"]


def test_repository_not_supplied_is_not_evaluated(tmp_path):
    report = pcm.evaluate_public_claim_manifest(_manifest(tmp_path), as_of=AS_OF)
    assert report["passes"] is False
    assert report["freshness_counts"]["NOT_EVALUATED"] == 1
    assert "REPOSITORY_NOT_EVALUATED" in report["claims"][0]["violations"]


def test_future_evidence_is_refused_even_without_repository_access(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["claims"][0]["evidence"][0]["collected_at"] = "2026-07-18T12:00:01Z"
    report = pcm.evaluate_public_claim_manifest(manifest, as_of=AS_OF)
    row = report["claims"][0]["evidence"][0]
    assert row["freshness_state"] == "UNKNOWN"
    assert row["violations"] == ["FUTURE_COLLECTION_TIMESTAMP"]


def test_maturity_inflation_is_refused(tmp_path):
    report = _evaluate(tmp_path, _manifest(tmp_path, maturity="PROVEN", kind="TEST_RECEIPT"))
    assert report["passes"] is False
    assert report["claims"][0]["violations"] == ["MATURITY_EVIDENCE_MISMATCH"]


def test_valid_cross_bound_test_receipt_supports_measured_claim(tmp_path):
    report = _evaluate(tmp_path, _manifest(tmp_path))
    assert report["passes"] is True
    assert report["claims"][0]["maturity"] == "MEASURED"


@pytest.mark.parametrize(
    ("maturity", "kind"),
    [
        ("PROVEN", "FORMAL_PROOF"),
        ("MEASURED", "MEASUREMENT_RECEIPT"),
        ("MODELED", "MODEL_OUTPUT"),
        ("CONJECTURE", "CONJECTURE_RECORD"),
        ("CONJECTURE", "SOURCE_RECORD"),
        ("OPEN", "OPEN_ISSUE"),
    ],
)
def test_unimplemented_evidence_validators_fail_closed(tmp_path, maturity, kind):
    report = _evaluate(tmp_path, _manifest(tmp_path, maturity=maturity, kind=kind))
    assert report["passes"] is False
    assert "EVIDENCE_KIND_VALIDATOR_UNAVAILABLE" in report["claims"][0]["violations"]


def test_arbitrary_bytes_cannot_self_attest_as_a_test_receipt(tmp_path):
    manifest = _manifest(tmp_path)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("not a receipt", encoding="utf-8")
    manifest["claims"][0]["evidence"][0]["content_sha256"] = _sha(evidence)
    report = _evaluate(tmp_path, manifest)
    assert report["passes"] is False
    assert "EVIDENCE_CONTRACT_INVALID" in report["claims"][0]["violations"]


def test_reproduction_argv_binding_has_no_whitespace_collision(tmp_path):
    manifest = _manifest(tmp_path)
    evidence = tmp_path / "evidence.txt"
    receipt = json.loads(evidence.read_text(encoding="utf-8"))
    receipt["command"] = ["python -m", "pytest"]
    evidence.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    manifest["claims"][0]["evidence"][0]["content_sha256"] = _sha(evidence)
    manifest["claims"][0]["reproduction_argv"] = ["python", "-m pytest"]
    report = _evaluate(tmp_path, manifest)
    assert report["passes"] is False
    assert "EVIDENCE_CONTRACT_BINDING_MISMATCH" in report["claims"][0]["violations"]


def test_identifier_collisions_use_trim_unicode_nfc_and_casefold(tmp_path):
    manifest = _manifest(tmp_path)
    duplicate = copy.deepcopy(manifest["claims"][0])
    manifest["claims"][0]["claim_id"] = "Claim-\u00c9"
    duplicate["claim_id"] = " claim-e\u0301 "
    duplicate["evidence"][0]["evidence_id"] = "other-evidence"
    manifest["claims"].append(duplicate)
    with pytest.raises(pcm.PublicClaimContractError, match="claim_id values must be unique"):
        pcm.parse_public_claim_manifest(manifest)


def test_evidence_ids_are_globally_unique_after_normalization(tmp_path):
    manifest = _manifest(tmp_path)
    duplicate = copy.deepcopy(manifest["claims"][0])
    duplicate["claim_id"] = "other-claim"
    duplicate["evidence"][0]["evidence_id"] = " FOCUSED-TEST-RECEIPT "
    manifest["claims"].append(duplicate)
    with pytest.raises(pcm.PublicClaimContractError, match="evidence_id values must be globally unique"):
        pcm.parse_public_claim_manifest(manifest)


@pytest.mark.parametrize(
    "unsafe",
    ["../outside.txt", "/etc/passwd", "C:/secret.txt", "dir/C:/secret.txt", "dir/D:/x", "dir\\file.txt", "dir/CON.txt", "dir/name. "],
)
def test_unsafe_paths_are_rejected_before_repository_access(tmp_path, unsafe):
    manifest = _manifest(tmp_path)
    manifest["claims"][0]["evidence"][0]["path"] = unsafe
    with pytest.raises(pcm.PublicClaimContractError, match="repository-relative|drive|Windows|reserved"):
        pcm.parse_public_claim_manifest(manifest)


def test_symlink_escape_is_refused_when_supported(tmp_path):
    outside = tmp_path.parent / "outside-public-claim.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    manifest = _manifest(tmp_path)
    evidence = manifest["claims"][0]["evidence"][0]
    evidence["path"] = "link.txt"
    evidence["content_sha256"] = _sha(outside)
    report = _evaluate(tmp_path, manifest)
    row = report["claims"][0]["evidence"][0]
    assert row["freshness_state"] == "UNKNOWN"
    assert row["violations"] == ["PATH_ESCAPES_REPOSITORY"]


def test_oversized_evidence_is_not_hashed(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(pcm, "MAX_EVIDENCE_BYTES", 4)
    report = _evaluate(tmp_path, manifest)
    row = report["claims"][0]["evidence"][0]
    assert row["freshness_state"] == "UNKNOWN"
    assert row["observed_content_sha256"] is None
    assert row["violations"] == ["EVIDENCE_TOO_LARGE"]


def test_unknown_fields_and_collection_amplification_are_refused(tmp_path):
    manifest = _manifest(tmp_path)
    manifest["autonomous"] = True
    with pytest.raises(pcm.PublicClaimContractError, match="unknown field"):
        pcm.parse_public_claim_manifest(manifest)
    manifest.pop("autonomous")
    manifest["claims"] = [copy.deepcopy(manifest["claims"][0]) for _ in range(65)]
    with pytest.raises(pcm.PublicClaimContractError, match="at most 64"):
        pcm.parse_public_claim_manifest(manifest)


def test_strict_json_rejects_duplicate_keys_at_any_depth():
    with pytest.raises(pcm.PublicClaimContractError, match="duplicate JSON key"):
        pcm.strict_json_loads('{"manifest_id":"a","nested":{"x":1,"x":2}}')


@pytest.mark.parametrize(
    "payload",
    ['{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}', '{"value":1e309}'],
)
def test_strict_json_rejects_non_finite_numbers(payload):
    with pytest.raises(pcm.PublicClaimContractError, match="finite|non-standard"):
        pcm.strict_json_loads(payload)


def test_strict_json_rejects_integers_outside_signed_64_bit_range():
    with pytest.raises(pcm.PublicClaimContractError, match="signed 64-bit"):
        pcm.strict_json_loads('{"value":' + ("9" * 5000) + "}")


def test_parser_returns_detached_canonical_copy(tmp_path):
    manifest = _manifest(tmp_path)
    parsed = pcm.parse_public_claim_manifest(manifest)
    manifest["claims"][0]["assertion"] = "mutated"
    assert parsed["claims"][0]["assertion"] == "The checked source contract is bounded."


def test_claim_and_evidence_order_do_not_change_deterministic_receipt(tmp_path):
    manifest = _manifest(tmp_path)
    second = copy.deepcopy(manifest["claims"][0])
    second["claim_id"] = "a-claim"
    second["evidence"][0]["evidence_id"] = "a-evidence"
    manifest["claims"].append(second)
    first = _evaluate(tmp_path, manifest)
    reordered = copy.deepcopy(manifest)
    reordered["claims"].reverse()
    second_report = _evaluate(tmp_path, reordered)
    assert first == second_report
    assert first["receipt"]["content_sha256"] == second_report["receipt"]["content_sha256"]


def test_receipt_changes_when_bound_evidence_changes(tmp_path):
    manifest = _manifest(tmp_path)
    first = _evaluate(tmp_path, manifest)["receipt"]["content_sha256"]
    manifest["claims"][0]["assertion"] = "A different source-scoped assertion."
    second = _evaluate(tmp_path, manifest)["receipt"]["content_sha256"]
    assert first != second


def test_manifest_content_digest_is_stable_across_evaluation_times(tmp_path):
    manifest = _manifest(tmp_path)
    first = _evaluate(tmp_path, manifest, as_of=AS_OF)
    second = _evaluate(tmp_path, manifest, as_of="2026-07-18T12:00:30Z")
    assert first["manifest_content_sha256"] == second["manifest_content_sha256"]
    assert first["receipt"]["content_sha256"] != second["receipt"]["content_sha256"]


def test_manifest_and_report_schemas_pin_runtime_bounds():
    root = Path(__file__).resolve().parents[1]
    manifest_schema = json.loads(
        (root / "schemas/evidenceos/public-claim-manifest.v1.schema.json").read_text(encoding="utf-8")
    )
    report_schema = json.loads(
        (root / "schemas/evidenceos/public-claim-report.v1.schema.json").read_text(encoding="utf-8")
    )
    assert manifest_schema["properties"]["claims"]["maxItems"] == pcm.MAX_CLAIMS
    assert manifest_schema["$defs"]["claim"]["properties"]["evidence"]["maxItems"] == pcm.MAX_EVIDENCE_PER_CLAIM
    assert manifest_schema["$defs"]["evidence"]["properties"]["max_age_seconds"]["maximum"] == pcm.MAX_MAX_AGE_SECONDS
    assert "{1,6}" in manifest_schema["$defs"]["utcTimestamp"]["pattern"]
    assert report_schema["properties"]["decision_state"]["const"] == "PROPOSAL_ONLY"
    assert report_schema["properties"]["effectors_enabled"]["const"] == 0
    assert "manifest_content_sha256" in report_schema["required"]


def test_real_source_scoped_manifest_and_report_match_reviewed_contracts():
    root = Path(__file__).resolve().parents[1]
    manifest = pcm.strict_json_loads(
        (root / "artifacts/evidenceos/manifests/integrity-control.public-claim-manifest.v1.json")
        .read_text(encoding="utf-8")
    )
    manifest_schema = json.loads(
        (root / "schemas/evidenceos/public-claim-manifest.v1.schema.json").read_text(encoding="utf-8")
    )
    report_schema = json.loads(
        (root / "schemas/evidenceos/public-claim-report.v1.schema.json").read_text(encoding="utf-8")
    )
    report = pcm.evaluate_public_claim_manifest(
        manifest,
        as_of="2026-07-18T16:00:00Z",
        repository_root=root,
    )
    Draft202012Validator.check_schema(manifest_schema)
    Draft202012Validator.check_schema(report_schema)
    Draft202012Validator(manifest_schema).validate(manifest)
    Draft202012Validator(report_schema).validate(report)
    assert manifest_schema["properties"]["schema_version"]["const"] == manifest["schema_version"]
    assert report_schema["properties"]["module"]["const"] == report["module"]
    assert report_schema["properties"]["decision_state"]["const"] == report["decision_state"]
    assert report["passes"] is True
    assert report["claims"][0]["scope"].startswith("The cited GitHub Actions test job only")


def test_cli_exits_zero_only_for_a_passing_manifest(tmp_path):
    manifest = _manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert cli.main([
        "--manifest", str(manifest_path),
        "--repository-root", str(tmp_path),
        "--as-of", AS_OF,
        "--report", str(report_path),
    ]) == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["outcome"] == "PASS"

    assert cli.main([
        "--manifest", str(manifest_path),
        "--repository-root", str(tmp_path),
        "--as-of", "2026-07-18T12:01:01Z",
    ]) == 1


def test_cli_refuses_oversized_manifest_before_json_decode(tmp_path, monkeypatch):
    path = tmp_path / "oversized.json"
    path.write_text("{" + ("x" * 32), encoding="utf-8")
    monkeypatch.setattr(cli, "MAX_MANIFEST_BYTES", 4)
    with pytest.raises(pcm.PublicClaimContractError, match="exceeds"):
        cli.load_manifest(path)


def test_cli_refuses_huge_integer_without_an_unhandled_exception(tmp_path, capsys):
    manifest_path = tmp_path / "huge-integer.json"
    manifest_path.write_text('{"value":' + ("9" * 5000) + "}", encoding="utf-8")
    assert cli.main([
        "--manifest", str(manifest_path),
        "--repository-root", str(tmp_path),
        "--as-of", AS_OF,
    ]) == 2
    assert "REFUSE" in capsys.readouterr().err


def _github_bound_manifest(root: Path) -> tuple[dict, Path]:
    manifest = _manifest(root)
    evidence = manifest["claims"][0]["evidence"][0]
    evidence["verification_ref"] = (
        "https://github.com/szl-holdings/a11oy/actions/runs/7/job/42"
    )
    receipt_path = root / evidence["path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["source_url"] = evidence["verification_ref"]
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    evidence["content_sha256"] = _sha(receipt_path)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest, manifest_path


def _trusted_github_api(url: str) -> dict:
    if url.endswith("/actions/jobs/42"):
        return {
            "id": 42,
            "run_id": 7,
            "html_url": "https://github.com/szl-holdings/a11oy/actions/runs/7/job/42",
            "head_sha": "122ae740",
            "status": "completed",
            "conclusion": "success",
            "name": "bounded route and core contract",
            "completed_at": AS_OF,
        }
    if url.endswith("/actions/runs/7"):
        return {
            "id": 7,
            "html_url": "https://github.com/szl-holdings/a11oy/actions/runs/7",
            "head_sha": "122ae740",
            "status": "completed",
            "conclusion": "success",
            "name": "Claim Compiler contract",
        }
    raise AssertionError(f"unexpected API URL: {url}")


def test_trusted_github_job_metadata_accepts_exact_cross_binding(tmp_path):
    _, manifest_path = _github_bound_manifest(tmp_path)
    report = github_verify.verify_manifest_github_jobs(
        manifest_path=manifest_path,
        repository_root=tmp_path,
        expected_repository="szl-holdings/a11oy",
        api_get=_trusted_github_api,
    )
    assert report["verified_receipt_count"] == 1
    assert report["verifications"][0]["job_id"] == 42


def test_editing_and_rehashing_timestamp_cannot_renew_trusted_job(tmp_path):
    manifest, manifest_path = _github_bound_manifest(tmp_path)
    evidence = manifest["claims"][0]["evidence"][0]
    receipt_path = tmp_path / evidence["path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["completed_at"] = "2026-07-18T12:00:01Z"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    evidence["collected_at"] = receipt["completed_at"]
    evidence["content_sha256"] = _sha(receipt_path)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(pcm.PublicClaimContractError, match="job completion time"):
        github_verify.verify_manifest_github_jobs(
            manifest_path=manifest_path,
            repository_root=tmp_path,
            expected_repository="szl-holdings/a11oy",
            api_get=_trusted_github_api,
        )


def test_ci_covers_module_schemas_manifest_receipt_and_real_validation():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/public-claim-integrity.yml").read_text(encoding="utf-8")
    compiler = (root / ".github/workflows/claim-compiler.yml").read_text(encoding="utf-8")
    for expected in (
        "szl_public_claim_manifest.py",
        "schemas/evidenceos/public-claim-*.v1.schema.json",
        "scripts/verify_public_claim_github_job.py",
        "artifacts/evidenceos/manifests/**",
        "artifacts/evidenceos/receipts/**",
        "tests/test_public_claim_manifest.py",
        ".github/requirements/ci-core.txt",
        ".github/requirements/ci-core.in",
        ".github/workflows/release.yml",
    ):
        assert expected in workflow
        assert expected in compiler
    assert "--manifest artifacts/evidenceos/manifests/integrity-control.public-claim-manifest.v1.json" in workflow
    assert 'test "${#MANIFESTS[@]}" -eq 1' in workflow
    assert "find artifacts/evidenceos/manifests -type f -name '*.json' -print0" in workflow
    assert "find artifacts/evidenceos/manifests -mindepth 1 -type l" in workflow
    assert "Draft202012Validator(report_schema).validate(report)" in workflow
    assert "--require-hashes -r .github/requirements/ci-core.txt" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert "branches: [main, agent/evidenceos-claim-wave36]" in workflow
    assert "branches: [main, agent/evidenceos-claim-wave36]" in compiler
    assert "actions: read" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "--expected-repository \"${{ github.repository }}\"" in workflow
    assert "public-claim-github-verification.json" in workflow


def test_release_waits_for_public_claim_gate():
    root = Path(__file__).resolve().parents[1]
    release = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/public-claim-integrity.yml" in release
    assert "needs: [provider-gate, public-claim-gate]" in release
    assert "types: [published]" in release
    assert "types: [created]" not in release
