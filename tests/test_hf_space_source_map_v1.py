from __future__ import annotations

import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_hf_space_source_map_v1.py"
SPEC = importlib.util.spec_from_file_location("hf_space_source_map_v1", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
COMMITTED_MAP = ROOT / "docs" / "huggingface-space-source-map-v1.json"


def _repo(full_name: str):
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "default_branch": "main",
        "default_branch_sha": "c" * 40,
        "archived": False,
        "disabled": False,
        "visibility": "public",
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


def test_space_readme_is_fetched_from_the_exact_repository_revision(monkeypatch) -> None:
    seen: list[str] = []

    def request(url: str):
        seen.append(url)
        return 200, b"# exact\n"

    monkeypatch.setattr(MODULE, "_safe_request_bytes", request)
    revision = "a" * 40
    status, text, url = MODULE.fetch_space_readme(
        "SZLHOLDINGS/example-space", revision
    )
    assert status == 200
    assert text == b"# exact\n"
    assert url == seen[0]
    assert f"/raw/{revision}/README.md" in url


def test_space_readme_rejects_a_mutable_revision() -> None:
    try:
        MODULE.fetch_space_readme("SZLHOLDINGS/example-space", "main")
    except MODULE.SourceMapError as error:
        assert "exact 40-character" in str(error)
    else:
        raise AssertionError("mutable Hugging Face revision was accepted")


def test_source_map_rejects_a_non_utf8_readme() -> None:
    records = [{"id": "SZLHOLDINGS/example-space", "sha": "a" * 40}]

    try:
        MODULE.build_source_map(
            records,
            lambda space_id, revision: (200, b"\xff", "https://example/readme"),
            lambda name: None,
            lambda name, revision: {"state": "UNAVAILABLE", "paths": []},
        )
    except MODULE.SourceMapError as error:
        assert "strict UTF-8" in str(error)
    else:
        raise AssertionError("invalid UTF-8 README bytes were normalized")


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


def test_divergent_candidates_omit_mutable_state_without_workflow_discovery() -> None:
    records = [{"id": "SZLHOLDINGS/example-space", "sha": "a" * 40}]
    repositories = {
        "szl-holdings/source-one",
        "szl-holdings/source-two",
    }

    def readme(space_id: str, revision: str):
        assert space_id == "SZLHOLDINGS/example-space"
        assert revision == "a" * 40
        return (
            200,
            b"https://github.com/szl-holdings/source-one\n"
            b"https://github.com/szl-holdings/source-two\n",
            "https://example/readme",
        )

    def resolver(name: str):
        return _repo(name) if name.lower() in repositories else None

    def binder(repository: dict[str, object]):
        raise AssertionError(
            f"divergent candidate must not be revision-bound: {repository}"
        )

    def workflows(name: str, revision: str):
        raise AssertionError(
            f"workflow discovery must stay blocked for {name}@{revision}"
        )

    payload = MODULE.build_source_map(
        records,
        readme,
        resolver,
        workflows,
        binder,
    )
    space = payload["spaces"][0]
    assert space["source_mapping"]["state"] == "DIVERGENT"
    assert space["source_mapping"]["canonical"] is None
    assert space["workflow_candidates"] == {
        "state": "BLOCKED_SOURCE_MAPPING",
        "paths": [],
    }
    assert space["source_mapping"]["candidates"] == [
        {
            "full_name": full_name,
            "html_url": f"https://github.com/{full_name}",
        }
        for full_name in sorted(repositories)
    ]


def test_divergent_candidate_identity_is_stable_across_branch_advances() -> None:
    records = [{"id": "SZLHOLDINGS/example-space", "sha": "a" * 40}]

    def readme(space_id: str, revision: str):
        return (
            200,
            b"https://github.com/szl-holdings/a11oy\n"
            b"https://github.com/szl-holdings/source-two\n",
            "https://example/readme",
        )

    def build(a11oy_revision: str, *, archived: bool):
        def resolver(name: str):
            repository = _repo(name)
            if name.lower() == "szl-holdings/a11oy":
                repository["default_branch_sha"] = a11oy_revision
                repository["archived"] = archived
            return repository

        def forbidden(*args):
            raise AssertionError(f"divergent branch state was inspected: {args}")

        return MODULE.build_source_map(
            records,
            readme,
            resolver,
            forbidden,
            forbidden,
        )

    before = build("1" * 40, archived=False)
    after = build("2" * 40, archived=True)
    assert before == after


def test_source_map_rejects_an_unbound_canonical_candidate() -> None:
    records = [{"id": "SZLHOLDINGS/example-space", "sha": "a" * 40}]

    def readme(space_id: str, revision: str):
        return (
            200,
            b"https://github.com/szl-holdings/source-one\n",
            "https://example/readme",
        )

    def resolver(name: str):
        return _repo(name)

    def unbound(repository: dict[str, object]):
        return {**repository, "default_branch_sha": None}

    try:
        MODULE.build_source_map(
            records,
            readme,
            resolver,
            lambda name, revision: {"state": "UNAVAILABLE", "paths": []},
            unbound,
        )
    except MODULE.SourceMapError as error:
        assert "no immutable default-branch revision" in str(error)
    else:
        raise AssertionError("unbound canonical repository candidate was accepted")


def test_repository_metadata_binds_the_exact_default_branch_head(monkeypatch) -> None:
    revision = "e" * 40
    seen: list[str] = []

    def request(url: str, github: bool = False):
        seen.append(url)
        return 200, {"sha": revision}

    monkeypatch.setattr(MODULE, "_safe_request_json", request)
    repository = _repo("szl-holdings/example-space")
    repository.pop("default_branch_sha")
    result = MODULE.bind_github_repo_revision(repository)
    assert result["default_branch_sha"] == revision
    assert seen[-1].endswith("/commits/main")


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

    def readme(space_id: str, revision: str):
        assert revision in {"a" * 40, "b" * 40}
        if space_id.endswith("example-space"):
            return (
                200,
                b"---\nsource_repo: https://github.com/szl-holdings/example-space\n---\n",
                "https://example/readme",
            )
        return 404, b"", "https://example/missing"

    def resolver(name: str):
        return _repo(name) if name.lower() == "szl-holdings/example-space" else None

    def workflows(name: str, revision: str):
        assert name == "szl-holdings/example-space"
        assert revision == "c" * 40
        return {
            "state": "OBSERVED",
            "github_ref": revision,
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
    assert exact["readme"]["revision"] == "a" * 40
    assert exact["source_mapping"]["canonical"]["full_name"] == "szl-holdings/example-space"
    assert exact["source_mapping"]["canonical"]["default_branch_sha"] == "c" * 40
    assert exact["workflow_candidates"]["github_ref"] == "c" * 40
    assert exact["workflow_candidates"]["single_writer_candidate"] is True


def test_workflow_listing_filters_non_deployment_files(monkeypatch) -> None:
    payload = [
        {"type": "file", "path": ".github/workflows/tests.yml", "name": "tests.yml"},
        {"type": "file", "path": ".github/workflows/hf-sync.yml", "name": "hf-sync.yml"},
        {"type": "file", "path": ".github/workflows/release-publish.yml", "name": "release-publish.yml"},
    ]
    seen: list[str] = []

    def request(url: str, github: bool = False):
        seen.append(url)
        return 200, payload

    monkeypatch.setattr(MODULE, "_safe_request_json", request)
    revision = "d" * 40
    result = MODULE.list_workflow_candidates("szl-holdings/example", revision)
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query) == {
        "ref": [revision]
    }
    assert result["github_ref"] == revision
    assert result["paths"] == [
        ".github/workflows/hf-sync.yml",
        ".github/workflows/release-publish.yml",
    ]
    assert result["single_writer_candidate"] is False


def test_committed_map_is_bound_to_immutable_repository_revisions() -> None:
    payload = json.loads(COMMITTED_MAP.read_text(encoding="utf-8"))
    assert payload["schema"] == "szl.hf-space-source-map/v1"
    assert payload["spaces"]
    for space in payload["spaces"]:
        hf_revision = space["hf_repository_sha"]
        assert MODULE.SHA40.fullmatch(hf_revision)
        readme = space["readme"]
        assert readme["revision"] == hf_revision
        if readme["http_status"] == 200:
            assert f"/{hf_revision}/README.md" in readme["url"]
            assert re.fullmatch(r"[0-9a-f]{64}", readme["sha256"])

        mapping = space["source_mapping"]
        canonical = mapping["canonical"]
        if canonical is None:
            for candidate in mapping["candidates"]:
                assert set(candidate) == {"full_name", "html_url"}
            continue
        for candidate in mapping["candidates"]:
            assert MODULE.SHA40.fullmatch(candidate["default_branch_sha"])
            assert "pushed_at" not in candidate
        github_ref = canonical["default_branch_sha"]
        assert MODULE.SHA40.fullmatch(github_ref)
        assert space["workflow_candidates"]["github_ref"] == github_ref
