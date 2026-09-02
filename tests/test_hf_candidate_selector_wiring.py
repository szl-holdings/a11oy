# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-module-drift.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _active_source() -> str:
    return "\n".join(
        line for line in _source().splitlines() if not line.lstrip().startswith("#")
    )


def _repository_job() -> str:
    return _source().split("\n  hf-repository-parity:", 1)[1]


def test_unmerged_candidate_is_not_compared_with_the_deployed_hub() -> None:
    active = _active_source()
    repository = _repository_job()

    assert "select_hf_candidate_admission.py" not in active
    assert "github.event.pull_request.head.sha" not in repository
    assert 'BASE_REF' not in repository
    assert '--base-ref' not in repository
    assert "if: github.event_name != 'pull_request'" in repository


def test_pull_request_executes_only_the_protected_base_verifier() -> None:
    source = _source()
    pr_job = source.split("\n  hf-runtime-live:", 1)[0]

    assert "baseline/.github/scripts/verify_hf_repository_parity.py" in pr_job
    assert (
        "path: baseline\n"
        "          ref: ${{ github.event.pull_request.base.sha }}\n"
        "          persist-credentials: false"
    ) in pr_job
    assert "SOURCE_REF: ${{ github.event.pull_request.base.sha }}" in pr_job
    assert "github.event.pull_request.head.sha" not in pr_job


def test_post_deployment_parity_binds_exact_protected_main() -> None:
    repository = _repository_job()
    for token in (
        "path: source",
        "ref: ${{ github.sha }}",
        "SOURCE_REF: ${{ github.sha }}",
        "source/.github/scripts/verify_hf_repository_parity.py",
        '--tools-script tools/.github/scripts/hf_module_drift_check.py',
        '--github-repo "$GITHUB_REPOSITORY"',
        '--github-ref "$SOURCE_REF"',
        '--hf-repo SZLHOLDINGS/a11oy',
        '--report-out hf-post-deployment-repository-parity.out.json',
        "name: hf-post-deployment-repository-parity",
    ):
        assert token in repository


def test_lifecycle_jobs_retain_least_privilege_and_immutable_tools_pin() -> None:
    source = _source()
    assert "permissions:\n  contents: read" in source
    assert source.count("repository: szl-holdings/.github") == 2
    assert source.count("ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054") == 2
    assert source.count("persist-credentials: false") >= 4
    assert "secrets." not in source
    assert "HF_TOKEN" not in source


def test_historical_selector_is_documentation_only() -> None:
    source = _source()
    active = _active_source()
    assert "select_hf_candidate_admission.py" in source
    assert "select_hf_candidate_admission.py" not in active
    assert "historical selector" in source
