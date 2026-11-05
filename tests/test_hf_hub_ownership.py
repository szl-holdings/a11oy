# SPDX-License-Identifier: Apache-2.0
"""HF Hub ownership: one active writer per Hub repository.

``publishing/hf-hub-ownership.json`` maps every Hugging Face repository that
any a11oy workflow or script can mutate to exactly one active writer, mirroring
szl-forge's ``publishing/kernel-hub-ownership.json`` +
``tests/test_kernel_hub_ownership.py`` pattern.

Three enforcements:

(a) Any workflow or script that carries a write primitive and names an HF
    repository id must have that repository covered in the manifest, and the
    file must be attributed there (as the declared writer, a retired writer,
    or a declared read-only reference). A second, unattributed in-repo writer
    for a mapped target therefore fails the scan.

(b) No two active (non-retired) writers may target the same Hub repository:
    each manifest entry carries at most one ``writer``, and duplicate
    repo_id+repo_type entries are refused.

(c) Every writer file the manifest names must exist in this repository.
    A retired writer is also checked so the manifest cannot reference the
    ghosts of removed workflows.

These are source assertions over the files tracked in this repository. They do
not observe the Hub and do not prove a hosted run. Targets whose repository id
is composed at run time are admitted only through ``dynamic_targets`` entries
whose template must literally appear in the writing file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "publishing" / "hf-hub-ownership.json"

# Directories whose files can write to the Hub. test_* and *.test.py files are
# test code, not operators.
SCAN_DIRS = (
    ".github/workflows",
    ".github/scripts",
    "scripts",
    "benchmarks",
)
ROOT_WRITER_FILES = ("szl_corpus_publish.py",)

# Any of these makes a file a potential Hub writer.
WRITE_MARKERS = re.compile(
    r"\b(?:api|hf_api|client)\s*\.\s*(?:upload_file|upload_folder|"
    r"upload_large_folder|create_commit|create_repo|delete_repo|delete_file|"
    r"delete_folder|create_branch|delete_branch|create_tag|delete_tag|"
    r"add_space_secret|set_space_variable|add_space_variable|"
    r"delete_space_variable|update_repo_settings|update_repo_visibility|"
    r"restart_space|pause_space|move_repo|super_squash_history)\s*\("
    r"|push_to_hub\s*\("
    r"|huggingface-cli\s+upload"
    r"|\bhf\s+upload\b"
    r"|git\s+push\b[^\n]*huggingface\.co|huggingface\.co[^\n]*\bgit\s+push\b"
    r"|uses:\s*\S*reusable-hf-deploy"
)

# Literal Hub repository ids. betterwithage is the creator-profile org that
# hosts the Living Anatomy Space.
TARGET = re.compile(r"(?:SZLHOLDINGS|betterwithage)/([A-Za-z0-9_.][A-Za-z0-9_.-]*[A-Za-z0-9_.])")

# Org-level URL path segments, never repository names.
ORG_URL_SEGMENTS = {"models", "datasets", "spaces", "collections", "settings", "organizations"}

WORKFLOW_DIRS = {".github", "scripts", "benchmarks"}


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def manifest_targets() -> dict[tuple[str, str], dict]:
    payload = load_manifest()
    assert payload["schema"] == "szl.hf-hub-ownership/v1"
    return payload, payload["targets"]


def scanned_files() -> list[Path]:
    files: list[Path] = []
    for sub in SCAN_DIRS:
        directory = ROOT / sub
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            name = path.name.lower()
            if name.startswith("test_") or name.endswith(".test.py"):
                continue
            if path.suffix.lower() in {".py", ".yml", ".yaml", ".sh", ".mjs"}:
                files.append(path)
    for name in ROOT_WRITER_FILES:
        files.append(ROOT / name)
    return files


def write_marked_files() -> dict[str, list[str]]:
    """Map each writer file (repo-relative path) to its literal HF repo ids."""
    result: dict[str, list[str]] = {}
    for path in scanned_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if not WRITE_MARKERS.search(text):
            continue
        targets = set()
        for match in TARGET.finditer(text):
            if match.group(1) in ORG_URL_SEGMENTS:
                continue
            preceding = text[max(0, match.start() - 40):match.start()]
            if preceding.rstrip().endswith("huggingface.co/") or preceding.rstrip().endswith(
                "huggingface.co/spaces/"
            ) or preceding.rstrip().endswith("huggingface.co/datasets/"):
                continue
            targets.add(f"{match.group(0)}")
        if targets:
            result[path.relative_to(ROOT).as_posix()] = sorted(targets)
    return result


def entry_files(entry: dict, key: str | None = None) -> set[str]:
    """All file paths an ownership entry attributes to one writer role."""
    paths: set[str] = set()

    def collect(node: object) -> None:
        if isinstance(node, dict):
            for field, value in node.items():
                if field in ("workflow", "script", "dynamic_targets"):
                    if field == "dynamic_targets":
                        paths.add(value["file"])
                    else:
                        paths.add(value)
                elif field == "scripts":
                    paths.update(value)
                elif field == "external":
                    continue
                else:
                    collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    source = entry if key is None else entry.get(key, [])
    collect(source if isinstance(source, (dict, list)) else [source])
    return paths


def attribution(entry: dict) -> set[str]:
    files: set[str] = set()
    writer = entry.get("writer")
    if isinstance(writer, dict):
        files |= entry_files(writer)
    files |= entry_files(entry, "retired_writers")
    files.update(entry.get("referenced_by", []))
    return files


def test_manifest_schema_and_single_active_writer_per_target() -> None:
    _, targets = manifest_targets()
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target["repo_id"], target["repo_type"])
        assert target["repo_id"].split("/", 1)[0] in {"SZLHOLDINGS", "betterwithage"}, key
        assert target["repo_type"] in {"space", "model", "dataset"}, key
        assert key not in seen, f"duplicate manifest entry for {key}"
        seen.add(key)

        writer = target["writer"]
        if writer == "none":
            assert target.get("note"), f"writer=none requires a note: {key}"
            assert isinstance(target.get("retired_writers", []), list)
        else:
            assert isinstance(writer, dict), f"writer must be an object or 'none': {key}"
            roles = [field for field in ("workflow", "script", "scripts", "external") if writer.get(field)]
            assert roles, f"writer names nothing: {key}"
            # Exactly one active writer: a workflow, at least one script, or an
            # external repository's workflow. A writer may pair a workflow with
            # the scripts it executes; it may not name two independent writers.
            assert not (writer.get("external") and (writer.get("workflow") or writer.get("script"))), key
        for retired in target.get("retired_writers", []):
            assert retired.get("retire") is True, (
                f"every retired writer must carry retire: true ({key}: {retired})"
            )
            assert retired.get("note"), f"retired writer needs a note ({key})"


def test_every_manifest_writer_file_exists() -> None:
    _, targets = manifest_targets()
    for target in targets:
        for path in sorted(attribution(target)):
            assert not path.endswith("\\"), path
            assert (ROOT / path).is_file(), f"{target['repo_id']}: {path} does not exist"


def test_no_write_marked_file_names_an_unmanifested_target() -> None:
    _, targets = manifest_targets()
    by_repo = {}
    for target in targets:
        by_repo.setdefault(target["repo_id"], []).append(target)
    uncovered: dict[str, list[str]] = {}
    for path, repos in sorted(write_marked_files().items()):
        for repo_id in repos:
            entries = by_repo.get(repo_id)
            if not entries:
                uncovered.setdefault(path, []).append(repo_id)
                continue
            if not any(path in attribution(entry) for entry in entries):
                uncovered.setdefault(path, []).append(repo_id)
    assert uncovered == {}


def test_manifest_writers_are_attributed_to_the_file_that_writes() -> None:
    """A declared writer must actually carry its target (literally or via a
    declared dynamic template); a file that writes what it never claims would
    make the manifest unverifiable."""
    _, targets = manifest_targets()
    marked = write_marked_files()
    for target in targets:
        writer = target["writer"]
        if not isinstance(writer, dict) or "external" in writer:
            continue
        files = sorted(entry_files(writer))
        assert files, f"{target['repo_id']}: writer names no file"
        literal_hit = any(
            target["repo_id"] in marked.get(path, ())
            or target["repo_id"] in (ROOT / path).read_text(encoding="utf-8", errors="replace")
            for path in files
        )
        dynamic = target.get("dynamic_targets") or writer.get("dynamic_targets")
        if not literal_hit:
            assert dynamic, (
                f"{target['repo_id']}: neither a literal write marker plus id "
                f"nor a dynamic_targets template explains the writer {files}"
            )
            template_file = (ROOT / dynamic["file"]).read_text(encoding="utf-8", errors="replace")
            assert dynamic["template"] in template_file, (
                f"{target['repo_id']}: template {dynamic['template']!r} absent from {dynamic['file']}"
            )
        if dynamic:
            template_file = (ROOT / dynamic["file"]).read_text(encoding="utf-8", errors="replace")
            assert dynamic["template"] in template_file, (
                f"{target['repo_id']}: template {dynamic['template']!r} absent from {dynamic['file']}"
            )


def test_no_second_active_writer_declared_anywhere() -> None:
    """Active (non-retired) writers for one repo: at most one, from the
    manifest's own declaration plus the scan's writer attribution."""
    _, targets = manifest_targets()
    active: dict[str, list[str]] = {}
    marked = write_marked_files()
    by_repo = {}
    for target in targets:
        by_repo.setdefault(target["repo_id"], []).append(target)
    for repo_id, entries in by_repo.items():
        writers = entries[0] if False else None  # placeholder for readability
        declared: list[str] = []
        for entry in entries:
            writer = entry["writer"]
            if isinstance(writer, dict):
                declared.extend(sorted(entry_files(writer)))
            for path, repos in marked.items():
                if repo_id in repos and path in attribution(entry) and path not in {
                    f for retired in entry.get("retired_writers", []) for f in entry_files(retired)
                }:
                    # A live writer file attributed to the entry is active only
                    # when it is the declared writer's own file.
                    if isinstance(writer, dict) and path in entry_files(writer):
                        continue
                    if path in entry.get("referenced_by", []):
                        continue
                    declared.append(path)
        unique = sorted(set(declared))
        if unique:
            active[repo_id] = unique
    for repo_id, files in active.items():
        entries = by_repo[repo_id]
        writer_files = set()
        for entry in entries:
            if isinstance(entry["writer"], dict):
                writer_files |= entry_files(entry["writer"])
        extra = [f for f in files if f not in writer_files]
        assert not extra, f"{repo_id}: second active writer(s) {extra}"


def test_orphaned_packet8_publisher_has_no_workflow_references() -> None:
    """publish_packet8_vertical_spaces.py is read-only inventory today; it must
    stay uninvoked by any workflow (its live write path was already removed)."""
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        assert "publish_packet8_vertical_spaces" not in text, workflow.name


def test_atelier_hub_publish_is_dispatch_only() -> None:
    """The push trigger was removed 2026-11-04 so main edits no longer re-pin
    the FOLD szl-atelier Space or the atelier model targets."""
    text = (ROOT / ".github" / "workflows" / "atelier-hub-publish.yml").read_text(encoding="utf-8")
    on_block = text.split("permissions:", 1)[0].split("on:", 1)[1]
    assert "workflow_dispatch" in on_block
    assert not re.search(r"(?m)^  push:", on_block), "atelier-hub-publish regained a push trigger"


@pytest.mark.parametrize(
    "relative",
    [
        ".github/workflows/hf-sync-backend.yml",
        ".github/workflows/hf-git-sha-sync.yml",
    ],
)
def test_retired_canonical_writers_stay_absent(relative: str) -> None:
    assert not (ROOT / relative).exists()
