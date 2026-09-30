#!/usr/bin/env python3
"""Network-free proof that superseded A11oy HF one-shots stay retired."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RETIRED = (
    ".github/workflows/deploy-verify-brain-now.yml",
    ".github/workflows/deploy-verify-canonical-a11oy-now.yml",
)


def test_superseded_one_shots_are_absent():
    for relative in RETIRED:
        assert not (ROOT / relative).exists(), relative


def manual_dispatch_declared(workflow: str) -> bool:
    """Recognize an active trigger in this repository's two-space YAML style.

    Empty and expanded mappings both declare manual dispatch. Comments, job
    names, nested lookalikes and duplicate on/dispatch declarations do not.
    This is deliberately not a general YAML parser or an input authority check;
    executable plan-admission tests cover the expanded input contract.
    """
    lines = workflow.splitlines()
    starts = [i for i, line in enumerate(lines)
              if re.fullmatch(r"(?:on|\"on\"|'on'):[ \t]*(?:#.*)?", line)]
    if len(starts) != 1:
        return False
    matches = 0
    for line in lines[starts[0] + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        if re.fullmatch(r"  workflow_dispatch:[ \t]*(?:\{\}[ \t]*)?(?:#.*)?", line):
            matches += 1
    return matches == 1


def test_manual_dispatch_detects_only_active_trigger():
    cases = (
        ("on:\n  workflow_dispatch: {}\npermissions:\n", True),
        ('"on":\n  workflow_dispatch:\n    inputs:\n      repair:\n        type: boolean\n', True),
        ("on:\n  push:\n# workflow_dispatch: {}\n", False),
        ("on:\n  push:\njobs:\n  workflow_dispatch: {}\n", False),
        ("on:\n  push:\n    workflow_dispatch: {}\n", False),
        ("on:\n  workflow_dispatch: {}\non:\n  push:\n", False),
        ("on:\n  workflow_dispatch: {}\n  workflow_dispatch:\n", False),
    )
    for workflow, expected in cases:
        assert manual_dispatch_declared(workflow) is expected, workflow


def test_hf_sync_is_the_permanent_source_derived_authority():
    workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
    required = (
        "name: Sync and Relock Canonical Hugging Face Space",
        "branches: [main]",
        "reusable-hf-deploy.yml@",
        "source-revision-variable: SZL_GIT_SHA",
        "source-revision-probe-path: /api/build-info",
        "canonical-a11oy-relock",
        "verify_canonical_a11oy.py",
        "hf-module-drift.yml",
    )
    for marker in required:
        assert marker in workflow, marker

    assert manual_dispatch_declared(workflow), "active workflow_dispatch trigger required"

    trigger_prefix = workflow.split("permissions:", 1)[0]
    assert "paths:" not in trigger_prefix
    assert "5b0d3818cf5780092dc1ffd78731707a1ebbcce9" not in workflow


def main() -> int:
    test_manual_dispatch_detects_only_active_trigger()
    test_superseded_one_shots_are_absent()
    test_hf_sync_is_the_permanent_source_derived_authority()
    print("A11oy HF one-shot retirement contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
