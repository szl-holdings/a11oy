#!/usr/bin/env python3
"""Network-free proof that superseded A11oy HF one-shots stay retired."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = (
    ".github/workflows/deploy-verify-brain-now.yml",
    ".github/workflows/deploy-verify-canonical-a11oy-now.yml",
)
CANONICAL_SYNC = ".github/workflows/hf-sync.yml"
LEGACY_SHA_SYNC = ".github/workflows/hf-git-sha-sync.yml"


def _trigger_section(workflow: str) -> str:
    return workflow.split("permissions:", 1)[0]


def _has_automatic_push(workflow: str) -> bool:
    return "\n  push:" in _trigger_section(workflow)


def _binds_szl_git_sha(workflow: str) -> bool:
    return (
        "source-revision-variable: SZL_GIT_SHA" in workflow
        or (
            "add_space_variable" in workflow
            and '"SZL_GIT_SHA"' in workflow
        )
    )


def test_superseded_one_shots_are_absent():
    for relative in RETIRED:
        assert not (ROOT / relative).exists(), relative


def test_hf_sync_is_the_permanent_source_derived_authority():
    workflow = (ROOT / CANONICAL_SYNC).read_text(encoding="utf-8")
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


def test_canonical_sync_is_the_only_automatic_source_binding_owner():
    legacy = (ROOT / LEGACY_SHA_SYNC).read_text(encoding="utf-8")
    assert "workflow_dispatch: {}" in _trigger_section(legacy)
    assert not _has_automatic_push(legacy)
    assert _binds_szl_git_sha(legacy)
    assert "if: github.ref == 'refs/heads/main'" in legacy

    automatic_owners = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = path.read_text(encoding="utf-8")
        if _has_automatic_push(workflow) and _binds_szl_git_sha(workflow):
            automatic_owners.append(path.relative_to(ROOT).as_posix())

    assert automatic_owners == [CANONICAL_SYNC]


def main() -> int:
    test_superseded_one_shots_are_absent()
    test_hf_sync_is_the_permanent_source_derived_authority()
    test_canonical_sync_is_the_only_automatic_source_binding_owner()
    print("A11oy HF one-shot retirement contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
