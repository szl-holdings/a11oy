#!/usr/bin/env python3
"""Network-free proof that superseded A11oy HF one-shots stay retired."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = (
    ".github/workflows/deploy-verify-brain-now.yml",
    ".github/workflows/deploy-verify-canonical-a11oy-now.yml",
)


def test_superseded_one_shots_are_absent():
    for relative in RETIRED:
        assert not (ROOT / relative).exists(), relative


def test_hf_sync_is_the_permanent_source_derived_authority():
    workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
    required = (
        "name: Sync and Relock Canonical Hugging Face Space",
        "branches: [main]",
        "workflow_dispatch: {}",
        "reusable-hf-deploy.yml@",
        "source-revision-variable: SZL_GIT_SHA",
        "source-revision-probe-path: /api/build-info",
        "canonical-a11oy-relock",
        "verify_canonical_a11oy.py",
        "hf-module-drift.yml",
    )
    for marker in required:
        assert marker in workflow, marker

    trigger_prefix = workflow.split("permissions:", 1)[0]
    assert "paths:" not in trigger_prefix
    assert "5b0d3818cf5780092dc1ffd78731707a1ebbcce9" not in workflow


def main() -> int:
    test_superseded_one_shots_are_absent()
    test_hf_sync_is_the_permanent_source_derived_authority()
    print("A11oy HF one-shot retirement contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
