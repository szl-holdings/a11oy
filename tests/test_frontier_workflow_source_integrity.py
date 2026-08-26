"""Regression coverage for protected Frontier workflow source constants."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIR_SCRIPT = ROOT / "ops/frontier/v16_7/apply_current_main_repairs.py"
SOURCE_TEST = ROOT / "ops/frontier/v16_7/test_frontier_v16_7_terminal_truth.py"
CONTRACT = ROOT / "ops/frontier/v16_7/SOLO_EXECUTION_CONTRACT.json"
WORKFLOWS = (
    ROOT / ".github/workflows/frontier-solo-qualification.yml",
    ROOT / ".github/workflows/frontier-v16-7-exact-source-builder.yml",
)
SOLO_WORKFLOW = WORKFLOWS[0]
BUILDER_WORKFLOW = WORKFLOWS[1]
INTEGRITY_WORKFLOW = ROOT / ".github/workflows/frontier-source-integrity.yml"
PROTECTION_DOC = ROOT / ".github/BRANCH_PROTECTION.md"
ORPHAN_DIGEST_LINE = re.compile(
    r"^[ \t]*\$[0-9a-fA-F]+[ \t]*$", re.MULTILINE
)
SOLO_HANDLER_REQUIREMENTS = {
    "verify_protected_material": (
        'test "$observed_repair_digest" = "$REPAIR_SCRIPT_SHA256"',
        'test "$contract_digest" = "$CONTRACT_SHA256"',
    ),
    "validate_pull_request": (
        'verify_protected_material "$base_sha"',
        'test "$test_digest" = "$SOURCE_TEST_SHA256"',
    ),
    "validate_merge_group": (
        'verify_protected_material "$base_sha"',
        'test "$test_digest" = "$SOURCE_TEST_SHA256"',
    ),
}
BUILDER_HANDLER_REQUIREMENTS = (
    'test "$contract" = "$CONTRACT_SHA256"',
    'test "$(sha256sum "$repair_script" | awk \'{print $1}\')" = '
    '"$REPAIR_SCRIPT_SHA256"',
    'test "$(sha256sum "$source_test" | awk \'{print $1}\')" = '
    '"$SOURCE_TEST_SHA256"',
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shell_function(source: str, name: str) -> str:
    match = re.search(
        rf"^          {re.escape(name)}\(\) \{{\n"
        rf"(?P<body>.*?)"
        rf"^          \}}$",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, name
    return match.group("body")


def _named_step(source: str, name: str) -> str:
    match = re.search(
        rf"^      - name: {re.escape(name)}$\n"
        rf"(?P<body>.*?)"
        rf"(?=^      - name: |\Z)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, name
    return match.group("body")


def _assert_exact_requirements(scope: str, requirements: tuple[str, ...]) -> None:
    for requirement in requirements:
        assert scope.count(requirement) == 1, requirement


def test_orphan_digest_detection_rejects_indentation() -> None:
    for indentation in ("", "  ", "\t"):
        source = f"{indentation}${'0' * 64}\n"
        assert ORPHAN_DIGEST_LINE.search(source)


def test_frontier_workflows_bind_all_protected_inputs() -> None:
    expected = {
        "CONTRACT": _digest(CONTRACT),
        "REPAIR_SCRIPT": _digest(REPAIR_SCRIPT),
        "SOURCE_TEST": _digest(SOURCE_TEST),
    }

    for workflow in WORKFLOWS:
        source = workflow.read_text(encoding="utf-8")
        for name, digest in expected.items():
            matches = re.findall(
                rf"^      {name}_SHA256: ([0-9a-f]{{64}})$",
                source,
                re.MULTILINE,
            )
            assert matches == [digest], (workflow, name)
        assert ORPHAN_DIGEST_LINE.search(source) is None, workflow

    solo_source = SOLO_WORKFLOW.read_text(encoding="utf-8")
    for handler, requirements in SOLO_HANDLER_REQUIREMENTS.items():
        _assert_exact_requirements(_shell_function(solo_source, handler), requirements)

    builder_source = BUILDER_WORKFLOW.read_text(encoding="utf-8")
    builder_handler = _named_step(
        builder_source,
        "Create one exact GitHub-signed Frontier source commit",
    )
    _assert_exact_requirements(builder_handler, BUILDER_HANDLER_REQUIREMENTS)


def test_contract_embedded_source_digests_match_protected_inputs() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = contract["source"]

    assert source["repair_oracle"] == {
        "path": "ops/frontier/v16_7/apply_current_main_repairs.py",
        "sha256": _digest(REPAIR_SCRIPT),
    }
    assert source["regression"] == {
        "protected_template_path": (
            "ops/frontier/v16_7/test_frontier_v16_7_terminal_truth.py"
        ),
        "source_path": "tests/test_frontier_v16_7_terminal_truth.py",
        "sha256": _digest(SOURCE_TEST),
    }


def test_integrity_regression_uses_protected_validator_and_candidate_data() -> None:
    source = INTEGRITY_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in source
    assert "merge_group:" in source
    assert "pull_request_target:" not in source
    assert "permissions:\n  contents: read" in source
    assert "CANDIDATE_SHA:" in source
    assert "github.event.merge_group.head_sha" in source
    assert "CANDIDATE_REPOSITORY:" in source
    assert "path: protected-validator" in source
    assert "path: candidate" in source
    assert "repository: ${{ job.workflow_repository }}" in source
    assert "ref: ${{ job.workflow_sha }}" in source
    assert "ref: ${{ env.CANDIDATE_SHA }}" in source
    assert "repository: ${{ env.CANDIDATE_REPOSITORY }}" in source
    assert source.count("persist-credentials: false") == 2
    assert 'current="${current}/${part}"' in source
    assert 'test ! -L "$current"' in source
    assert 'cmp -s "candidate/${rel}" "protected-validator/${rel}"' in source
    assert "source-integrity.yml\n          tests/test_frontier" in source
    assert 'cp -- "candidate/${rel}" "protected-validator/${rel}"' in source
    assert "working-directory: protected-validator" in source
    assert "python -I -B tests/test_frontier_workflow_source_integrity.py" in source
    assert "pip install" not in source
    assert "pytest" not in source
    run_block = source.split("run: |", maxsplit=1)[1]
    assert "python candidate/" not in run_block
    assert "cd candidate" not in run_block


def test_required_workflow_handoff_covers_frontier_integrity() -> None:
    source = PROTECTION_DOC.read_text(encoding="utf-8")

    assert "Require workflows to pass before merging" in source
    assert ".github/workflows/frontier-source-integrity.yml" in source
    assert "Protected Frontier source-pin integrity" in source
    assert "ordinary required status context" in source
    assert "cannot certify its own newly introduced workflow" in source


def main() -> None:
    """Run the protected validator without pytest or repository plugin loading."""
    test_orphan_digest_detection_rejects_indentation()
    test_frontier_workflows_bind_all_protected_inputs()
    test_contract_embedded_source_digests_match_protected_inputs()
    test_integrity_regression_uses_protected_validator_and_candidate_data()
    test_required_workflow_handoff_covers_frontier_integrity()


if __name__ == "__main__":
    main()
