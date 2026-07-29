#!/usr/bin/env python3
"""Network-free proof that superseded A11oy HF one-shots stay retired."""
import re
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


def _trigger_events(workflow: str) -> set[str]:
    """Return declared workflow events without a YAML parser dependency."""
    section = _trigger_section(workflow)
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "on:" and not line.lstrip().startswith("on:"):
            continue
        inline = line.split(":", 1)[1].strip()
        if inline:
            if inline.startswith("[") and inline.endswith("]"):
                return {
                    event.strip().strip("'\"")
                    for event in inline[1:-1].split(",")
                    if event.strip()
                }
            return {inline.strip("'\"")}

        events = set()
        for candidate in lines[index + 1 :]:
            if candidate and not candidate.startswith((" ", "\t")):
                break
            match = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_-]*):", candidate)
            if match:
                events.add(match.group(1))
        return events
    return set()


def _has_automatic_trigger(workflow: str) -> bool:
    return bool(_trigger_events(workflow) - {"workflow_dispatch"})


def _binds_szl_git_sha(workflow: str) -> bool:
    return (
        re.search(
            r"source-revision-variable:\s*['\"]?SZL_GIT_SHA['\"]?(?:\s|$)",
            workflow,
        )
        is not None
        or (
            "add_space_variable" in workflow
            and re.search(r"['\"]SZL_GIT_SHA['\"]", workflow) is not None
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
    assert not _has_automatic_trigger(legacy)
    assert _binds_szl_git_sha(legacy)
    assert "if: github.ref == 'refs/heads/main'" in legacy

    automatic_owners = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = path.read_text(encoding="utf-8")
        if _has_automatic_trigger(workflow) and _binds_szl_git_sha(workflow):
            automatic_owners.append(path.relative_to(ROOT).as_posix())

    assert automatic_owners == [CANONICAL_SYNC]


def test_automatic_trigger_and_binding_detection_are_fail_closed():
    assert not _has_automatic_trigger("on:\n  workflow_dispatch: {}\n")
    for event in ("push", "schedule", "workflow_run", "repository_dispatch"):
        workflow = f"on:\n  {event}: {{}}\n  workflow_dispatch: {{}}\n"
        assert _has_automatic_trigger(workflow), event
    assert _has_automatic_trigger("on: [workflow_dispatch, push]\n")

    for quote in ('"', "'"):
        workflow = (
            "on:\n  schedule: {}\n"
            "permissions:\n  contents: read\n"
            "run: |\n"
            "  api.add_space_variable("
            f"repo_id=space, key={quote}SZL_GIT_SHA{quote}, value=sha)\n"
        )
        assert _binds_szl_git_sha(workflow), quote


def main() -> int:
    test_superseded_one_shots_are_absent()
    test_hf_sync_is_the_permanent_source_derived_authority()
    test_canonical_sync_is_the_only_automatic_source_binding_owner()
    test_automatic_trigger_and_binding_detection_are_fail_closed()
    print("A11oy HF one-shot retirement contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
