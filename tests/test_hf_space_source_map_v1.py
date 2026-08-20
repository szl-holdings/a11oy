from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_hf_space_source_map_v1.py"
SPEC = importlib.util.spec_from_file_location("hf_space_source_map_v1", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _repo(full_name: str):
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "default_branch": "main",
        "archived": False,
        "disabled": False,
        "visibility": "public",
        "pushed_at": "2026-08-17T00:00:00Z",
    }


def test_front_matter_and_explicit_repo_extraction() -> None:
    readme = """---
sdk: docker
source_repo: https://github.com/szl-holdings/example-space
---
See [source](https://github.com/szl-holdings/example-space/tree/main).
Ignore https://github.com/other/example.
"""
    front = MODULE.parse_front_matter(readme)
    assert front["sdk"] == "docker"
    assert MODULE.extract_explicit_github_repositories(readme, front) == [
        "szl-holdings/example-space"
    ]


def test_exact_explicit_mapping() -> None:
    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/example-space",
        ["szl-holdings/example-space"],
        lambda name: _repo(name),
    )
    assert mapping["state"] == "EXACT"
    assert mapping["canonical"]["full_name"] == "szl-holdings/example-space"


def test_missing_explicit_mapping_is_divergent() -> None:
    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/example-space",
        ["szl-holdings/missing"],
        lambda name: None,
    )
    assert mapping["state"] == "DIVERGENT"
    assert mapping["canonical"] is None
    assert mapping["missing_candidates"] == ["szl-holdings/missing"]


def test_unique_normalized_name_match_is_inferred() -> None:
    def resolver(name: str):
        return _repo("szl-holdings/example-space") if name.lower() == "szl-holdings/example-space" else None

    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/Example_Space",
        [],
        resolver,
    )
    assert mapping["state"] == "INFERRED"
    assert mapping["evidence"] == "NORMALIZED_NAME_MATCH"


def test_multiple_name_matches_are_divergent() -> None:
    existing = {
        "szl-holdings/szl-example": _repo("szl-holdings/szl-example"),
        "szl-holdings/example": _repo("szl-holdings/example"),
    }
    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/szl-example",
        [],
        lambda name: existing.get(name.lower()),
    )
    assert mapping["state"] == "DIVERGENT"
    assert len(mapping["candidates"]) == 2


def test_unavailable_mapping_is_never_guessed() -> None:
    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/no-source",
        [],
        lambda name: None,
    )
    assert mapping["state"] == "UNAVAILABLE"
    assert mapping["canonical"] is None


def test_build_source_map_is_deterministic_and_bounded() -> None:
    records = [
        {
            "id": "SZLHOLDINGS/example-space",
            "sha": "a" * 40,
            "sdk": "docker",
            "runtime": {"stage": "RUNNING", "sha": "a" * 40},
        },
        {
            "id": "SZLHOLDINGS/unresolved",
            "sha": "b" * 40,
            "sdk": "static",
            "runtime": {"stage": "PAUSED", "sha": "b" * 40},
        },
    ]

    def readme(space_id: str):
        if space_id.endswith("example-space"):
            return (
                200,
                "---\nsource_repo: https://github.com/szl-holdings/example-space\n---\n",
                "https://example/readme",
            )
        return 404, "", "https://example/missing"

    def resolver(name: str):
        return _repo(name) if name.lower() == "szl-holdings/example-space" else None

    def workflows(name: str):
        assert name == "szl-holdings/example-space"
        return {
            "state": "OBSERVED",
            "paths": [".github/workflows/hf-sync.yml"],
            "candidate_count": 1,
            "single_writer_candidate": True,
        }

    first = MODULE.build_source_map(records, readme, resolver, workflows)
    second = MODULE.build_source_map(records, readme, resolver, workflows)
    assert first == second
    assert first["remote_mutation"] is False
    assert first["summary"]["spaces_observed"] == 2
    assert first["summary"]["mapping_states"] == {"EXACT": 1, "UNAVAILABLE": 1}
    assert first["summary"]["exact_or_inferred_sources"] == 1
    assert first["summary"]["blocked_source_mappings"] == 1
    exact = first["spaces"][0]
    assert exact["source_mapping"]["canonical"]["full_name"] == "szl-holdings/example-space"
    assert exact["workflow_candidates"]["single_writer_candidate"] is True


def test_workflow_listing_filters_non_deployment_files(monkeypatch) -> None:
    payload = [
        {"type": "file", "path": ".github/workflows/tests.yml", "name": "tests.yml"},
        {"type": "file", "path": ".github/workflows/hf-sync.yml", "name": "hf-sync.yml"},
        {"type": "file", "path": ".github/workflows/release-publish.yml", "name": "release-publish.yml"},
    ]
    monkeypatch.setattr(MODULE, "_safe_request_json", lambda url, github=False: (200, payload))
    result = MODULE.list_workflow_candidates("szl-holdings/example")
    assert result["paths"] == [
        ".github/workflows/hf-sync.yml",
        ".github/workflows/release-publish.yml",
    ]
    assert result["single_writer_candidate"] is False
