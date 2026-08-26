"""Regressions for the protected Frontier source-pin candidate validator."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/validate_frontier_source_pin_candidate.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_frontier_source_pin_candidate",
    SCRIPT,
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

AUTHORITY_WORKFLOW = ROOT / ".github/workflows/frontier-source-pin-authority.yml"
PROTECTION_DOC = ROOT / ".github/BRANCH_PROTECTION.md"
COPY_PATHS = tuple(validator.APPROVED_CANDIDATE_SHA256) + tuple(
    validator.PROTECTED_INPUT_SHA256
)


def _copy_tree(destination: Path) -> None:
    for relative in COPY_PATHS:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)


def _approved_candidate(candidate: Path) -> None:
    contract_path = candidate / validator.CONTRACT
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["source"]["repair_oracle"]["sha256"] = (
        validator.PROTECTED_INPUT_SHA256[validator.REPAIR_SCRIPT]
    )
    contract["source"]["regression"]["sha256"] = (
        validator.PROTECTED_INPUT_SHA256[validator.SOURCE_TEST]
    )
    contract_path.write_text(
        json.dumps(contract, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    contract_digest = validator.APPROVED_CANDIDATE_SHA256[validator.CONTRACT]

    for relative in (validator.SOLO_WORKFLOW, validator.BUILDER_WORKFLOW):
        path = candidate / relative
        source = path.read_text(encoding="utf-8")
        source = source.replace(
            "      CONTRACT_SHA256: "
            "bb8c1a3f10ab92219df04f991d32f651db31f27650a0a4d602016c65b88a21ae",
            "      CONTRACT_SHA256: " + contract_digest,
            1,
        )
        source = source.replace(
            "$1003b709612d1d59fe0ce3b6316cd4a33273c5bd35237530c50e1f329f4ef0e59",
            "      REPAIR_SCRIPT_SHA256: "
            + validator.PROTECTED_INPUT_SHA256[validator.REPAIR_SCRIPT],
            1,
        )
        source = source.replace(
            "      SOURCE_TEST_SHA256: "
            "4b8572c9381d0fedd0113f800c8f1bdfecbf84503bc565cbe053a982d4073b1f",
            "      SOURCE_TEST_SHA256: "
            + validator.PROTECTED_INPUT_SHA256[validator.SOURCE_TEST],
            1,
        )
        path.write_text(source, encoding="utf-8", newline="\n")

    solo_path = candidate / validator.SOLO_WORKFLOW
    solo = solo_path.read_text(encoding="utf-8")
    old = """            if grep -Fxq \"$test_rel\" \"$matched_changed\"; then
              test \"$head_test_present\" -eq 1
              test_digest=\"$(sha256sum \"$work/head/$test_rel\" | awk '{print $1}')\"
              test \"$test_digest\" = \"$SOURCE_TEST_SHA256\"
              if [ \"$base_test_present\" -eq 0 ] || ! cmp -s \"$work/base/$test_rel\" \"$work/head/$test_rel\"; then
                queue_effective_changes=$((queue_effective_changes + 1))
              fi
            else
              test \"$base_test_present\" -eq \"$head_test_present\"
              if [ \"$base_test_present\" -eq 1 ] && ! cmp -s \"$work/base/$test_rel\" \"$work/head/$test_rel\"; then
                echo \"Another queued change modified the unmanaged Frontier regression test\" >&2
                exit 1
              fi
              if [ \"$head_test_present\" -eq 1 ]; then
                test_digest=\"$(sha256sum \"$work/head/$test_rel\" | awk '{print $1}')\"
              fi
            fi
"""
    new = """            if grep -Fxq \"$test_rel\" \"$matched_changed\"; then
              test \"$head_test_present\" -eq 1
              if [ \"$base_test_present\" -eq 0 ] || ! cmp -s \"$work/base/$test_rel\" \"$work/head/$test_rel\"; then
                queue_effective_changes=$((queue_effective_changes + 1))
              fi
            else
              test \"$base_test_present\" -eq \"$head_test_present\"
              if [ \"$base_test_present\" -eq 1 ] && ! cmp -s \"$work/base/$test_rel\" \"$work/head/$test_rel\"; then
                echo \"Another queued change modified the unmanaged Frontier regression test\" >&2
                exit 1
              fi
            fi
            if [ \"$head_test_present\" -eq 1 ]; then
              test_digest=\"$(sha256sum \"$work/head/$test_rel\" | awk '{print $1}')\"
              test \"$test_digest\" = \"$SOURCE_TEST_SHA256\"
            fi
"""
    assert solo.count(old) == 1
    solo_path.write_text(solo.replace(old, new), encoding="utf-8", newline="\n")


def test_unchanged_guarded_files_are_not_applicable(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)
    report = validator.validate(protected, candidate, ["README.md"])
    assert report["status"] == "NOT_APPLICABLE"
    assert report["repository_changed_paths"] == ["README.md"]
    assert report["candidate_payload_checkout_code_executed"] is False


def test_exact_atomic_repair_is_admitted(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)
    _approved_candidate(candidate)
    approved_paths = sorted(validator.APPROVED_CANDIDATE_SHA256)
    report = validator.validate(protected, candidate, approved_paths)
    assert report["status"] == "PASS"
    assert report["changed_paths"] == approved_paths
    assert report["repository_changed_paths"] == approved_paths


def test_approved_fixture_matches_full_file_digests(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    _copy_tree(candidate)
    _approved_candidate(candidate)
    observed = {
        path: validator._sha256((candidate / path).read_bytes())
        for path in validator.APPROVED_CANDIDATE_SHA256
    }
    assert observed == validator.APPROVED_CANDIDATE_SHA256


def test_partial_or_tampered_repair_fails_closed(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)
    _approved_candidate(candidate)
    (candidate / validator.CONTRACT).write_bytes(
        (protected / validator.CONTRACT).read_bytes()
    )
    try:
        validator.validate(protected, candidate)
    except validator.ValidationError as exc:
        assert "complete repository diff" in str(exc)
    else:
        raise AssertionError("partial repair was admitted")

    _copy_tree(candidate)
    _approved_candidate(candidate)
    workflow = candidate / validator.SOLO_WORKFLOW
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            'test "$test_digest" = "$SOURCE_TEST_SHA256"',
            ': \'test "$test_digest" = "$SOURCE_TEST_SHA256"\'',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    try:
        validator.validate(protected, candidate)
    except validator.ValidationError as exc:
        assert "approved exact repair" in str(exc)
    else:
        raise AssertionError("non-executing digest comparison was admitted")


def test_extra_path_or_rename_away_fails_closed(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)
    _approved_candidate(candidate)
    approved_paths = sorted(validator.APPROVED_CANDIDATE_SHA256)

    try:
        validator.validate(protected, candidate, approved_paths + ["README.md"])
    except validator.ValidationError as exc:
        assert "complete repository diff" in str(exc)
    else:
        raise AssertionError("extra changed path was admitted")

    (candidate / validator.SOLO_WORKFLOW).unlink()
    try:
        validator.validate(protected, candidate, approved_paths)
    except validator.ValidationError as exc:
        assert "required regular file is missing" in str(exc)
    else:
        raise AssertionError("rename-away of guarded workflow was admitted")


def test_changed_path_file_is_nul_bound_and_unique(tmp_path: Path) -> None:
    changed = tmp_path / "changed"
    changed.write_bytes(b"README.md\0README.md\0")
    try:
        validator._read_changed_paths(changed)
    except validator.ValidationError as exc:
        assert "duplicates" in str(exc)
    else:
        raise AssertionError("duplicate changed paths were admitted")


def test_sensitive_tree_only_changes_fail_closed(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)

    for relative, expected in (
        (
            validator.SOLO_WORKFLOW,
            "reported guarded tree change has unchanged raw blob bytes",
        ),
        (validator.REPAIR_SCRIPT, "protected input tree changed"),
    ):
        try:
            validator.validate(protected, candidate, [relative])
        except validator.ValidationError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"tree-only change was admitted: {relative}")


def test_report_identity_is_exact() -> None:
    sha = "a" * 40
    identity = validator._validate_identity(
        workflow_repository=validator.REPOSITORY,
        workflow_ref=validator.WORKFLOW_REF,
        workflow_file_path=validator.WORKFLOW_FILE_PATH,
        workflow_sha=sha,
        repository=validator.REPOSITORY,
        protected_base_sha=sha,
        candidate_sha="c" * 40,
    )
    assert identity["authority_state"] == "PROTECTED_REQUIRED"
    assert identity["workflow_sha"] == sha
    try:
        validator._validate_identity(
            workflow_repository=validator.REPOSITORY,
            workflow_ref=validator.WORKFLOW_REF,
            workflow_file_path=validator.WORKFLOW_FILE_PATH,
            workflow_sha=sha.upper(),
            repository=validator.REPOSITORY,
            protected_base_sha=sha,
            candidate_sha="c" * 40,
        )
    except validator.ValidationError as exc:
        assert "exact lowercase Git SHA" in str(exc)
    else:
        raise AssertionError("noncanonical workflow SHA was admitted")


def test_failure_report_retains_validated_identity(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)
    changed_input = candidate / validator.REPAIR_SCRIPT
    changed_input.write_bytes(changed_input.read_bytes() + b"\n")
    changed_paths = tmp_path / "changed-paths"
    changed_paths.write_bytes((validator.REPAIR_SCRIPT + "\0").encode("utf-8"))
    report_path = tmp_path / "report.json"
    sha = "a" * 40

    result = validator.main(
        [
            "--protected-root",
            str(protected),
            "--candidate-root",
            str(candidate),
            "--changed-paths-file",
            str(changed_paths),
            "--workflow-repository",
            validator.REPOSITORY,
            "--workflow-ref",
            validator.WORKFLOW_REF,
            "--workflow-file-path",
            validator.WORKFLOW_FILE_PATH,
            "--workflow-sha",
            sha,
            "--repository",
            validator.REPOSITORY,
            "--protected-base-sha",
            sha,
            "--candidate-sha",
            "b" * 40,
            "--report",
            str(report_path),
        ]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result == 1
    assert report["status"] == "FAIL"
    assert report["identity"]["authority_state"] == "PROTECTED_REQUIRED"
    assert report["candidate_payload_checkout_code_executed"] is False


def test_candidate_cannot_rotate_protected_inputs(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    candidate = tmp_path / "candidate"
    _copy_tree(protected)
    _copy_tree(candidate)
    path = candidate / validator.REPAIR_SCRIPT
    path.write_bytes(path.read_bytes() + b"\n")
    try:
        validator.validate(protected, candidate)
    except validator.ValidationError as exc:
        assert "candidate changed protected input" in str(exc)
    else:
        raise AssertionError("candidate-controlled repair oracle was admitted")


def test_authority_workflow_executes_only_protected_stdlib_code() -> None:
    source = AUTHORITY_WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in source
    assert "branches-ignore:" in source
    assert '- "**"' in source
    assert "merge_group:" not in source
    assert "github.event.pull_request.base.sha" in source
    assert "github.event.pull_request.head.sha" in source
    assert "pull_request_target:" not in source
    assert "permissions:\n  contents: read" in source
    assert "ADVISORY_UNTRUSTED" in source
    assert "echo 'ADVISORY_UNTRUSTED:" in source
    assert "prior PASS invalidated" in source
    protected_ref_condition = (
        "job.workflow_ref == "
        "'szl-holdings/a11oy/.github/workflows/frontier-source-pin-authority.yml@refs/heads/main'"
    )
    assert source.count(protected_ref_condition) == 7
    assert "repository: ${{ job.workflow_repository }}" in source
    assert "ref: ${{ job.workflow_sha }}" in source
    assert 'test "$WORKFLOW_REPOSITORY" = "szl-holdings/a11oy"' in source
    assert 'test "$WORKFLOW_SHA" = "$PROTECTED_BASE_SHA"' in source
    assert (
        'test "$WORKFLOW_FILE_PATH" = '
        '".github/workflows/frontier-source-pin-authority.yml"'
        in source
    )
    assert 'test "$(git -C protected-validator rev-parse HEAD)" = "$WORKFLOW_SHA"' in source
    assert "path: protected-validator" in source
    assert "path: protected-base" in source
    assert "path: candidate" in source
    assert source.count("persist-credentials: false") == 3
    assert "git -C \"$repo\" ls-tree" in source
    assert 'test "$mode" = "100644"' in source
    assert source.count("|| return 1") == 4
    assert source.count("cat-file blob") == 4
    assert 'test "$candidate_entry" = "$authority_entry"' in source
    assert 'test "$candidate_entry" = "$base_entry"' in source
    assert "working-directory: protected-validator" in source
    assert 'test "$CANDIDATE_REPOSITORY" = "$GITHUB_REPOSITORY"' in source
    assert "git -C candidate merge-base --is-ancestor" in source
    assert "git -C candidate diff --name-only -z --no-renames" in source
    assert source.count("ls-remote origin refs/heads/main") == 2
    assert (
        "python -I -B .github/scripts/validate_frontier_source_pin_candidate.py"
        in source
    )
    assert "--changed-paths-file frontier-source-pin.changed-paths" in source
    assert '--workflow-ref "$WORKFLOW_REF"' in source
    assert '--workflow-sha "$WORKFLOW_SHA"' in source
    assert (
        "if test -f protected-validator/frontier-source-pin-authority.json" in source
    )
    assert '--protected-base-sha "$PROTECTED_BASE_SHA"' in source
    assert '--candidate-sha "$CANDIDATE_SHA"' in source
    assert "pip install" not in source
    assert "pytest" not in source
    run_block = source.split("run: |", maxsplit=1)[1]
    assert "python candidate/" not in run_block
    assert "cd candidate" not in run_block


def test_protection_handoff_is_explicit_and_truthful() -> None:
    source = PROTECTION_DOC.read_text(encoding="utf-8")
    assert "frontier-source-pin-authority.yml" in source
    assert "Protected Frontier source-pin authority" in source
    assert "cannot certify its own newly introduced workflow" in source
    assert "Require workflows to pass before merging" in source
