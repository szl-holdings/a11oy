"""Regression coverage for protected Frontier workflow source constants."""

from __future__ import annotations

import hashlib
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
