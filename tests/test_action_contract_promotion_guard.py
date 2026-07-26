from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "action-contract-promotion-guard.yml"
PROTECTION_DOC = ROOT / ".github" / "BRANCH_PROTECTION.md"
QUALIFICATION_JOB = "Action-contract promotion qualification"


def test_ruleset_source_uses_protected_validator_and_untrusted_candidate_data() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in text
    assert "merge_group:" in text
    assert "pull_request_target:" not in text
    assert "permissions:\n  contents: read" in text
    assert f"name: {QUALIFICATION_JOB}" in text
    assert "Immutable protected-base validator" not in text
    assert "PROTECTED_BASE_SHA:" in text
    assert "github.event.merge_group.base_sha" in text
    assert "CANDIDATE_SHA:" in text
    assert "github.sha" in text
    assert "CANDIDATE_REPOSITORY:" in text
    assert "ref: ${{ env.PROTECTED_BASE_SHA }}" in text
    assert "ref: ${{ env.CANDIDATE_SHA }}" in text
    assert "repository: ${{ env.CANDIDATE_REPOSITORY }}" in text
    assert "persist-credentials: false" in text
    assert 'test ! -L "${candidate_manifest}"' in text
    assert (
        'cp -- "${candidate_manifest}" '
        '"protected-base/docs/action-contract-manifest.json"' in text
    )
    assert "python3 scripts/validate_action_contract_manifest.py" in text
    assert '--runtime-root "${GITHUB_WORKSPACE}/candidate"' in text


def test_ruleset_runs_only_protected_suite_code_against_candidate_root() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    run_block = text.split("run: |", maxsplit=1)[1]
    assert "candidate/scripts/" not in run_block
    assert "cd candidate" not in run_block
    assert "python3 candidate/" not in run_block
    assert "python3 scripts/validate_action_contract_manifest.py" in run_block
    assert '--runtime-root "${GITHUB_WORKSPACE}/candidate"' in run_block


def test_required_workflow_handoff_is_explicit_and_base_fresh() -> None:
    text = PROTECTION_DOC.read_text(encoding="utf-8")

    assert "Require workflows to pass before merging" in text
    assert "szl-holdings/a11oy" in text
    assert ".github/workflows/action-contract-promotion-guard.yml" in text
    assert "strict_required_status_checks_policy=true" in text
    assert "merge_group" in text
    assert QUALIFICATION_JOB in text
    assert "ordinary required status context" in text
    assert "Immutable protected-base validator" not in text
    assert "series-a-default-branch" in text
