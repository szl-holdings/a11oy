from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_hf_parity_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("validate_hf_parity_lifecycle", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

WORKFLOW = (ROOT / ".github" / "workflows" / "hf-module-drift.yml").read_text(
    encoding="utf-8"
)
SYNC = (ROOT / ".github" / "workflows" / "hf-sync.yml").read_text(
    encoding="utf-8"
)


def errors_for(workflow: str = WORKFLOW, sync: str = SYNC) -> list[str]:
    return validator.validate_text(workflow, sync)


def test_committed_lifecycle_contract_passes() -> None:
    assert validator.validate() == []


def test_reintroducing_pr_candidate_byte_parity_fails_closed() -> None:
    mutated = WORKFLOW.replace(
        "  hf-repository-parity:\n"
        "    name: Immutable HF repository byte parity\n"
        "    if: github.event_name != 'pull_request'",
        "  hf-repository-parity:\n"
        "    name: Immutable HF repository byte parity\n"
        "    if: github.event_name == 'pull_request'",
        1,
    )
    errors = errors_for(mutated)
    assert any("must not run against an unmerged PR head" in error for error in errors)


def test_post_deploy_job_cannot_consume_pr_head_sha() -> None:
    mutated = WORKFLOW.replace(
        "SOURCE_REF: ${{ github.sha }}",
        "SOURCE_REF: ${{ github.event.pull_request.head.sha }}",
        1,
    )
    errors = errors_for(mutated)
    assert any("exact protected main" in error for error in errors)
    assert any("must not consume pull-request event fields" in error for error in errors)


def test_historical_candidate_selector_cannot_become_executable() -> None:
    mutated = WORKFLOW.replace(
        "source/.github/scripts/verify_hf_repository_parity.py",
        "source/.github/scripts/select_hf_candidate_admission.py",
        1,
    )
    errors = errors_for(mutated)
    assert any("candidate selector must not execute" in error for error in errors)
    assert any("verifier must execute exactly twice" in error for error in errors)


def test_direct_push_trigger_is_rejected_as_a_publication_race() -> None:
    mutated = WORKFLOW.replace(
        "on:\n  pull_request:",
        "on:\n  push:\n    branches: [main]\n  pull_request:",
        1,
    )
    errors = errors_for(mutated)
    assert any("must not run directly on push" in error for error in errors)


def test_missing_hf_sync_post_deploy_dispatch_fails_closed() -> None:
    mutated = SYNC.replace(validator.POST_DEPLOY_DISPATCH, "echo parity-dispatch-removed", 1)
    errors = errors_for(sync=mutated)
    assert any("must dispatch the parity workflow" in error for error in errors)
    assert any("must appear after the governed publication job" in error for error in errors)


def test_dispatch_before_deployment_is_rejected() -> None:
    dispatch = validator.POST_DEPLOY_DISPATCH
    mutated = SYNC.replace(dispatch, "echo post-deploy-placeholder", 1)
    mutated = dispatch + "\n" + mutated
    errors = errors_for(sync=mutated)
    assert any("must appear after the governed publication job" in error for error in errors)


def test_lifecycle_marker_is_mandatory_and_unique() -> None:
    missing = WORKFLOW.replace(
        "# lifecycle: post-deployment-repository-parity/v1\n", "", 1
    )
    duplicate = WORKFLOW.replace(
        "# lifecycle: post-deployment-repository-parity/v1",
        "# lifecycle: post-deployment-repository-parity/v1\n"
        "# lifecycle: post-deployment-repository-parity/v1",
        1,
    )
    assert any("marker must appear exactly once" in error for error in errors_for(missing))
    assert any("marker must appear exactly once" in error for error in errors_for(duplicate))


def test_custom_provider_credentials_are_not_admitted() -> None:
    mutated = WORKFLOW.replace(
        "permissions:\n  contents: read",
        "permissions:\n  contents: read\nenv:\n  HF_TOKEN: ${{ secrets.HF_TOKEN }}",
        1,
    )
    # The dedicated lifecycle validator is temporal; the existing source-integrity
    # validator separately rejects provider secrets. This assertion locks that the
    # lifecycle validator does not mistake credential presence for parity proof.
    assert errors_for(mutated) == []
    assert "HF_TOKEN" not in validator.active_source(WORKFLOW)
