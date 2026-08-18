#!/usr/bin/env python3
"""Temporary exact applicator for the HF candidate-controller wiring branch."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/hf-module-drift.yml"
VALIDATOR = ROOT / "scripts/validate_frontdoor_source_integrity.py"
TESTS = ROOT / "scripts/test_frontdoor_source_integrity.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_candidate_block(text: str, old: str, new: str, label: str) -> str:
    marker = "  hf-repository-parity:\n"
    if text.count(marker) != 1:
        raise RuntimeError(f"{label}: candidate job marker is not unique")
    prefix, candidate = text.split(marker, 1)
    candidate = replace_once(candidate, old, new, label)
    return prefix + marker + candidate


def patch_workflow() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    text = patch_candidate_block(
        text,
        "baseline/.github/scripts/verify_hf_repository_parity.py",
        "baseline/.github/scripts/verify_hf_candidate_admission.py",
        "workflow candidate controller",
    )
    WORKFLOW.write_text(text, encoding="utf-8")


def patch_validator() -> None:
    text = VALIDATOR.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    "verify_hf_repository_parity.py",\n'
        '    "reusable-hf-module-drift-check.yml@",',
        '    "verify_hf_repository_parity.py",\n'
        '    "verify_hf_candidate_admission.py",\n'
        '    "reusable-hf-module-drift-check.yml@",',
        "required controller token",
    )
    text = replace_once(
        text,
        'CANDIDATE_INVOCATION = (\n'
        '    f"{PYTHON_EXECUTABLE} baseline/.github/scripts/verify_hf_repository_parity.py"\n'
        ')',
        'CANDIDATE_INVOCATION = (\n'
        '    f"{PYTHON_EXECUTABLE} baseline/.github/scripts/verify_hf_candidate_admission.py"\n'
        ')',
        "candidate invocation",
    )
    text = replace_once(
        text,
        '    command = [\n'
        '        PYTHON_EXECUTABLE,\n'
        '        f"{checkout}/.github/scripts/verify_hf_repository_parity.py",\n'
        '        "--tools-script",',
        '    script = (\n'
        '        "verify_hf_candidate_admission.py"\n'
        '        if candidate\n'
        '        else "verify_hf_repository_parity.py"\n'
        '    )\n'
        '    command = [\n'
        '        PYTHON_EXECUTABLE,\n'
        '        f"{checkout}/.github/scripts/{script}",\n'
        '        "--tools-script",',
        "role-specific expected command",
    )
    text = replace_once(
        text,
        'errors.append("candidate job must invoke the protected-base wrapper exactly once")',
        'errors.append(\n'
        '            "candidate job must invoke the protected-base admission controller "\n'
        '            "exactly once"\n'
        '        )',
        "candidate controller error",
    )
    VALIDATOR.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    text = patch_candidate_block(
        text,
        "baseline/.github/scripts/verify_hf_repository_parity.py",
        "baseline/.github/scripts/verify_hf_candidate_admission.py",
        "fixture candidate controller",
    )
    insertion = '''    def test_candidate_requires_base_controlled_admission_controller(self) -> None:\n        temp, root = self.make_fixture()\n        with temp:\n            workflow = VALID_WORKFLOW.replace(\n                "baseline/.github/scripts/verify_hf_candidate_admission.py",\n                "baseline/.github/scripts/verify_hf_repository_parity.py",\n                1,\n            )\n            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")\n            self.assertTrue(\n                any(\n                    "admission controller" in error\n                    or "canonical parity command" in error\n                    for error in validator.validate(root)\n                )\n            )\n\n    def test_protected_base_requires_repository_parity_verifier(self) -> None:\n        temp, root = self.make_fixture()\n        with temp:\n            workflow = VALID_WORKFLOW.replace(\n                "baseline/.github/scripts/verify_hf_repository_parity.py",\n                "baseline/.github/scripts/verify_hf_candidate_admission.py",\n                1,\n            )\n            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")\n            self.assertTrue(\n                any(\n                    "baseline wrapper" in error\n                    or "canonical parity command" in error\n                    for error in validator.validate(root)\n                )\n            )\n\n    def test_candidate_controller_must_execute_from_protected_base_checkout(self) -> None:\n        temp, root = self.make_fixture()\n        with temp:\n            workflow = VALID_WORKFLOW.replace(\n                "baseline/.github/scripts/verify_hf_candidate_admission.py",\n                "candidate/.github/scripts/verify_hf_candidate_admission.py",\n                1,\n            )\n            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")\n            self.assertTrue(\n                any(\n                    "admission controller" in error\n                    or "canonical parity command" in error\n                    for error in validator.validate(root)\n                )\n            )\n\n'''
    text = replace_once(
        text,
        "    def test_bom_fails(self) -> None:\n",
        insertion + "    def test_bom_fails(self) -> None:\n",
        "role-separation tests",
    )
    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_workflow()
    patch_validator()
    patch_tests()


if __name__ == "__main__":
    main()
