# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-module-drift.yml"


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_candidate_admission_executes_only_the_protected_base_selector() -> None:
    source = _source()
    selector = "baseline/.github/scripts/select_hf_candidate_admission.py"
    direct_controller = "baseline/.github/scripts/verify_hf_candidate_admission.py"

    assert source.count(selector) == 1
    assert direct_controller not in source
    assert (
        "path: baseline\n"
        "          ref: ${{ github.event.pull_request.base.sha }}\n"
        "          persist-credentials: false"
    ) in source
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in source


def test_candidate_sha_remains_inert_input_with_exact_identity_binding() -> None:
    source = _source()
    assert "BASE_REF: ${{ github.event.pull_request.base.sha }}" in source
    assert "SOURCE_REF: ${{ github.event.pull_request.head.sha }}" in source
    for argument in (
        '--tools-script tools/.github/scripts/hf_module_drift_check.py',
        '--github-repo "$GITHUB_REPOSITORY"',
        '--base-ref "$BASE_REF"',
        '--github-ref "$SOURCE_REF"',
        '--hf-repo SZLHOLDINGS/a11oy',
        '--report-out hf-repository-parity.out.json',
    ):
        assert argument in source


def test_candidate_job_retains_least_privilege_and_immutable_tools_pin() -> None:
    source = _source()
    assert "permissions:\n  contents: read" in source
    assert source.count("repository: szl-holdings/.github") == 2
    assert source.count("ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054") == 2
    assert source.count("persist-credentials: false") >= 4
