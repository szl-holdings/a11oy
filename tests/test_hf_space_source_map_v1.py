from __future__ import annotations

import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

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
Uses [a library](https://github.com/szl-holdings/dependency).
Ignore https://github.com/other/example.
"""
    front = MODULE.parse_front_matter(readme)
    assert front["sdk"] == "docker"
    assert MODULE.extract_explicit_github_repositories(readme, front) == [
        "szl-holdings/example-space"
    ]
    assert MODULE.extract_github_repository_references(readme) == [
        "szl-holdings/dependency", "szl-holdings/example-space",
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


@pytest.mark.parametrize("revision", ["main", "0" * 40])
def test_space_readme_rejects_a_mutable_or_missing_revision(revision) -> None:
    try:
        MODULE.fetch_space_readme("SZLHOLDINGS/example-space", revision)
    except MODULE.SourceMapError as error:
        assert "exact 40-character" in str(error)
    else:
        raise AssertionError("mutable or missing Hugging Face revision was accepted")


def test_runtime_zero_revision_is_unavailable() -> None:
    assert MODULE._runtime_sha({"runtime": {"sha": "0" * 40}}) is None
    assert MODULE._runtime_sha({"runtime": {"raw": {"sha": "0" * 40}}}) is None


def test_zero_cached_github_revision_requires_fresh_immutable_readback(monkeypatch) -> None:
    observed = []
    def request(url, *, github):
        assert github is True
        observed.append(url)
        return 200, {"sha": "d" * 40}
    monkeypatch.setattr(MODULE, "_safe_request_json", request)
    result = MODULE.bind_github_repo_revision({**_repo("szl-holdings/example-space"), "default_branch_sha": "0" * 40})
    assert result["default_branch_sha"] == "d" * 40
    assert observed == ["https://api.github.com/repos/szl-holdings/example-space/commits/main"]


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
            b"Canonical source: https://github.com/szl-holdings/source-one\n\n"
            b"Source repository: https://github.com/szl-holdings/source-two\n",
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
            b"Canonical source: https://github.com/szl-holdings/a11oy\n\n"
            b"Source repository: https://github.com/szl-holdings/source-two\n",
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
            b"Canonical source: https://github.com/szl-holdings/source-one\n",
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


@pytest.mark.parametrize("readme", [
    "---\nsource_repo: szl-holdings/example-space # source owner\n---\n",
    "---\ngithub_repository: 'szl-holdings/example-space'\n---\n",
    '---\nsource_url: "https://github.com/szl-holdings/example-space" # owner\n---\n',
    "---\nszl:\n  source_repo: szl-holdings/example-space\n---\n",
    "---\r\nsdk: docker\r\nszl:\r\n  source_repo: szl-holdings/example-space\r\n---\r\n",
    "---\ntags:\n- governed-ai\n- szl-holdings\nsource_repo: szl-holdings/example-space\n---\n",
    "Canonical source: `szl-holdings/example-space`. Public surface: https://example.org.\n",
    "**Canonical source:** https://github.com/szl-holdings/example-space.\n",
    "Source repository: https://github.com/szl-holdings/example-space/tree/main/space\n",
    "The canonical source is\n[`owner`](https://github.com/szl-holdings/example-space).\n",
    "- GitHub source of record: public Apache-2.0 repository\n  [`owner`](https://github.com/szl-holdings/example-space)\n- Runtime: elsewhere\n",
    "This Space is published from [owner](https://github.com/szl-holdings/example-space) (`frontier/atelier_v3`) by the committed workflow.\n",
])
def test_explicit_metadata_and_narrow_prose_declarations(readme: str) -> None:
    assert MODULE.extract_explicit_github_repositories(
        readme, MODULE.parse_front_matter(readme)
    ) == ["szl-holdings/example-space"]


def test_repeated_consistent_declarations_deduplicate_case_and_dot_git() -> None:
    readme = """---
source_repo: SZL-Holdings/Example-Space.git
szl:
  source_repo: https://github.com/szl-holdings/example-space
---
Canonical source: `szl-holdings/example-space`.
"""
    assert MODULE.extract_explicit_github_repositories(
        readme, MODULE.parse_front_matter(readme)
    ) == ["szl-holdings/example-space"]


def _build_from_readme(readme: str, resolver=_repo):
    return MODULE.build_source_map(
        [{"id": "SZLHOLDINGS/example-space", "sha": "a" * 40}],
        lambda space_id, revision: (200, readme.encode(), f"https://example/{revision}/README.md"),
        resolver,
        lambda name, revision: {"state": "OBSERVED", "github_ref": revision, "paths": []},
    )["spaces"][0]


def test_generic_links_are_references_and_cannot_create_exact_or_divergent_ownership() -> None:
    space = _build_from_readme(
        "Built with https://github.com/szl-holdings/dependency.\n"
        "Also see https://github.com/szl-holdings/other-library.\n",
        lambda name: _repo(name) if name == "szl-holdings/example-space" else None,
    )
    assert space["source_mapping"]["state"] == "INFERRED"
    assert space["source_mapping"]["evidence"] == "NORMALIZED_NAME_MATCH"
    assert space["explicit_github_repositories"] == []
    assert space["github_repository_references"] == [
        "szl-holdings/dependency", "szl-holdings/other-library",
    ]


def test_dependencies_do_not_conflict_with_a_declared_owner() -> None:
    space = _build_from_readme(
        "Canonical source: https://github.com/szl-holdings/source-one. "
        "Depends on https://github.com/szl-holdings/dependency.\n"
    )
    assert space["source_mapping"]["state"] == "EXACT"
    assert space["source_mapping"]["canonical"]["full_name"] == "szl-holdings/source-one"
    assert space["explicit_github_repositories"] == ["szl-holdings/source-one"]
    assert len(space["github_repository_references"]) == 2


def test_examples_quotes_comments_and_unrelated_nested_fields_are_not_owners() -> None:
    readme = """---
sdk: docker
example:
  source_repo: szl-holdings/not-owner
---
```yaml
Canonical source: https://github.com/szl-holdings/not-owner
```
~~~markdown
Source repository: https://github.com/szl-holdings/not-owner
~~~
> Canonical source: https://github.com/szl-holdings/not-owner
    Canonical source: https://github.com/szl-holdings/not-owner
<!--
Canonical source: https://github.com/szl-holdings/not-owner
-->
<pre>
Canonical source: https://github.com/szl-holdings/not-owner
</pre>
<blockquote>
Canonical source: https://github.com/szl-holdings/not-owner
</blockquote>
The documentation mentions https://github.com/szl-holdings/not-owner.
"""
    space = _build_from_readme(readme, lambda name: None)
    assert space["source_mapping"]["state"] == "UNAVAILABLE"
    assert space["source_declarations"] == []
    assert space["explicit_github_repositories"] == []
    assert space["github_repository_references"] == ["szl-holdings/not-owner"]


@pytest.mark.parametrize("readme", [
    "---\nsource_repo: szl-holdings/one\nsource_repo: szl-holdings/two\n---\n",
    "---\nsource_repo: szl-holdings/one\nSOURCE_REPO: szl-holdings/one\n---\n",
    "---\nszl:\n  source_repo: szl-holdings/one\n  source_repo: szl-holdings/two\n---\n",
    "---\nszl: {source_repo: szl-holdings/one}\n---\n",
    "---\nszl:\n  source_repo: szl-holdings/one\nszl:\n  source_repo: szl-holdings/two\n---\n",
    "---\nsource_repo:\n  - szl-holdings/one\n---\n",
    "---\nsource_repo: [szl-holdings/one, szl-holdings/two]\n---\n",
    "---\nsource_repo: >\n  szl-holdings/one\n---\n",
    "---\nsource_repo: *source_alias\n---\n",
    "---\n<<: *source_defaults\n---\n",
    "---\nszl:\n  <<: *source_defaults\n---\n",
    "---\nszl:\n\tsource_repo: szl-holdings/one\n---\n",
    "---\nszl:\n  source_repo: szl-holdings/one\n    source_repo: szl-holdings/two\n---\n",
    "---\nsource_repo: szl-holdings/one\n",
    "---\nsource_repo: 'szl-holdings/one' junk\n---\n",
    '---\n"source_repo": szl-holdings/one\n---\nCanonical source: szl-holdings/two\n',
    "---\n!!str source_repo: szl-holdings/one\n---\nCanonical source: szl-holdings/two\n",
    "---\n source_repo: szl-holdings/one\n---\nCanonical source: szl-holdings/two\n",
    "---\nsource_repo: szl-holdings/one or szl-holdings/two\n---\n",
    "---\nsource_repo: https://github.com/other/one\n---\n",
    "---\nsource_repo: https://github.com.evil.invalid/szl-holdings/one\n---\n",
    "---\nsource_repo: https://github.com@evil.invalid/szl-holdings/one\n---\n",
    "---\nsource_repo: https://[malformed/szl-holdings/one\n---\n",
    "Canonical source: https://github.com/szl-holdings/one or https://github.com/szl-holdings/two\n",
    "Canonical source: https://github.com/other/one\n",
    "Canonical source: pending owner review\n",
])
def test_invalid_or_ambiguous_declarations_block_name_fallback_and_workflow_binding(readme: str) -> None:
    def forbidden(*args):
        raise AssertionError(f"invalid owner declaration attempted source binding: {args}")

    payload = MODULE.build_source_map(
        [{"id": "SZLHOLDINGS/example-space", "sha": "a" * 40}],
        lambda space_id, revision: (200, readme.encode(), "https://example/readme"),
        _repo,
        forbidden,
        forbidden,
    )
    space = payload["spaces"][0]
    assert space["source_mapping"]["state"] == "DIVERGENT"
    assert space["source_mapping"]["canonical"] is None
    assert space["source_declaration_errors"]
    assert space["workflow_candidates"] == {"state": "BLOCKED_SOURCE_MAPPING", "paths": []}
    assert all(set(candidate) == {"full_name", "html_url"} for candidate in space["source_mapping"]["candidates"])


def test_conflicting_metadata_and_prose_are_divergent() -> None:
    space = _build_from_readme(
        "---\nsource_repo: szl-holdings/one\n---\n"
        "Canonical source: `szl-holdings/two`.\n"
    )
    assert space["source_mapping"]["state"] == "DIVERGENT"
    assert space["source_mapping"]["canonical"] is None
    assert space["explicit_github_repositories"] == ["szl-holdings/one", "szl-holdings/two"]
    assert space["workflow_candidates"]["state"] == "BLOCKED_SOURCE_MAPPING"


def test_explicit_repository_resolution_cannot_change_identity() -> None:
    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/example-space", ["szl-holdings/declared-owner"],
        lambda name: _repo("other-org/redirected-owner"),
    )
    assert mapping["state"] == "DIVERGENT"
    assert mapping["canonical"] is None
    assert mapping["missing_candidates"] == ["szl-holdings/declared-owner"]


def test_inferred_repository_resolution_cannot_escape_the_candidate_identity() -> None:
    mapping = MODULE.select_source_mapping(
        "SZLHOLDINGS/example-space", [], lambda name: _repo("other-org/example-space"),
    )
    assert mapping["state"] == "UNAVAILABLE"
    assert mapping["canonical"] is None


def _space_record(name: str):
    return {"id": f"SZLHOLDINGS/{name}", "sha": "a" * 40, "private": False}


def _page_url(cursor: str | None = None, **changes):
    query = {"author": "SZLHOLDINGS", "limit": "100", "full": "true"}
    if cursor is not None:
        query["cursor"] = cursor
    query.update(changes)
    return f"{MODULE.HF_SPACES_API}?{urllib.parse.urlencode(query)}"


def test_fetch_spaces_follows_valid_bounded_pagination_without_losing_revisions(monkeypatch) -> None:
    seen = []
    pages = [
        ([_space_record("zeta")], f'<{_page_url("opaque+/=")}>; rel="next"'),
        ([_space_record("alpha")], None),
    ]

    def request(url):
        seen.append(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query))
        return pages.pop(0)

    monkeypatch.setattr(MODULE, "_request_hf_space_page", request)
    assert MODULE.fetch_spaces() == [_space_record("alpha"), _space_record("zeta")]
    assert seen == [
        {"author": ["SZLHOLDINGS"], "limit": ["100"], "full": ["true"]},
        {"author": ["SZLHOLDINGS"], "limit": ["100"], "full": ["true"], "cursor": ["opaque+/="]},
    ]


@pytest.mark.parametrize("link", [
    "",
    "malformed",
    f'<{_page_url("next")}>',
    f'<{_page_url("next")}>; rel="next", <{_page_url("again")}>; rel="next"',
    f'<{_page_url("next")}>; rel="next next"',
    f'<{_page_url("next")}>; rel="unknown"',
    f'<{_page_url("next").replace("https:", "http:")}>; rel="next"',
    f'<{_page_url("next").replace("huggingface.co", "evil.invalid")}>; rel="next"',
    f'<{_page_url("next").replace("huggingface.co", "huggingface.co@evil.invalid")}>; rel="next"',
    f'<{_page_url("next").replace("huggingface.co", "huggingface.co:443")}>; rel="next"',
    f'<{_page_url("next").replace("/api/spaces", "/api/models")}>; rel="next"',
    f'<{_page_url("next", author="another-org")}>; rel="next"',
    f'<{_page_url("next", limit="1000")}>; rel="next"',
    f'<{_page_url("next", full="false")}>; rel="next"',
    f'<{_page_url("next", search="partial")}>; rel="next"',
    f'<{_page_url("next")}&author=SZLHOLDINGS>; rel="next"',
    f'<{_page_url("next").replace("&full=true", "")}>; rel="next"',
    f'<{_page_url("")}>; rel="next"',
    f'<{_page_url("next")}#fragment>; rel="next"',
    f'<{_page_url("next")}>; rel="next" trailing-junk',
    f'<{_page_url("next").replace("cursor=next", "cursor=%ZZ")}>; rel="next"',
    f'<{_page_url("next").replace("cursor=next", "cursor=%0A")}>; rel="next"',
    f'<{_page_url("next")}>; rel="next"\n',
    "x" * (MODULE.MAX_LINK_HEADER_BYTES + 1),
])
def test_pagination_rejects_malformed_or_out_of_scope_links_before_fetch(monkeypatch, link: str) -> None:
    seen = []

    def request(url):
        seen.append(url)
        assert len(seen) == 1, "unvalidated pagination target was fetched"
        return [_space_record("first")], link

    monkeypatch.setattr(MODULE, "_request_hf_space_page", request)
    with pytest.raises(MODULE.SourceMapError):
        MODULE.fetch_spaces()
    assert len(seen) == 1


@pytest.mark.parametrize("payload", [
    {}, [None], [{"id": 123}], [{"id": "SZLHOLDINGS/space/extra"}],
    [{**_space_record("space"), "id": "other/space"}],
    [{**_space_record("space"), "author": "other"}],
    [{**_space_record("space"), "private": True}],
    [{"id": "SZLHOLDINGS/space", "sha": "a" * 40}],
    [{**_space_record("space"), "private": "false"}],
    [{**_space_record("space"), "sha": "main"}],
    [{**_space_record("space"), "sha": "0" * 40}],
    [_space_record(str(index)) for index in range(101)],
])
def test_pagination_rejects_malformed_private_or_unbound_records(monkeypatch, payload) -> None:
    monkeypatch.setattr(MODULE, "_request_hf_space_page", lambda url: (payload, None))
    with pytest.raises(MODULE.SourceMapError):
        MODULE.fetch_spaces()


def test_pagination_detects_url_loops_despite_query_reordering(monkeypatch) -> None:
    seen = []

    def request(url):
        seen.append(url)
        return [_space_record("first")], f'<{_page_url()}>; rel="next"'

    monkeypatch.setattr(MODULE, "_request_hf_space_page", request)
    with pytest.raises(MODULE.SourceMapError, match="repeated a page"):
        MODULE.fetch_spaces()
    assert len(seen) == 1


def test_pagination_rejects_duplicate_ids_across_pages(monkeypatch) -> None:
    pages = [
        ([_space_record("same")], f'<{_page_url("next")}>; rel="next"'),
        ([_space_record("SAME")], None),
    ]
    monkeypatch.setattr(MODULE, "_request_hf_space_page", lambda url: pages.pop(0))
    with pytest.raises(MODULE.SourceMapError, match="repeated repository"):
        MODULE.fetch_spaces()


def test_pagination_limits_fail_without_returning_a_partial_census(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "MAX_HF_PAGES", 1)
    monkeypatch.setattr(MODULE, "_request_hf_space_page", lambda url: (
        [_space_record("one")], f'<{_page_url("next")}>; rel="next"',
    ))
    with pytest.raises(MODULE.SourceMapError, match="page limit"):
        MODULE.fetch_spaces()
    monkeypatch.setattr(MODULE, "MAX_HF_SPACES", 1)
    monkeypatch.setattr(MODULE, "_request_hf_space_page", lambda url: (
        [_space_record("one"), _space_record("two")], None,
    ))
    with pytest.raises(MODULE.SourceMapError, match="repository limit"):
        MODULE.fetch_spaces()


def test_pagination_rejects_empty_nonterminal_pages_and_an_empty_census(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "_request_hf_space_page", lambda url: (
        [], f'<{_page_url("next")}>; rel="next"',
    ))
    with pytest.raises(MODULE.SourceMapError, match="empty nonterminal"):
        MODULE.fetch_spaces()
    monkeypatch.setattr(MODULE, "_request_hf_space_page", lambda url: ([], None))
    with pytest.raises(MODULE.SourceMapError, match="no public Spaces"):
        MODULE.fetch_spaces()


def test_page_reader_bounds_response_bytes_and_rejects_redirects(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            assert limit == MODULE.MAX_HF_PAGE_BYTES + 1
            return b"x" * limit

    class Opener:
        def open(self, request, timeout):
            assert timeout == 45
            return Response()

    def build_opener(handler):
        assert isinstance(handler, MODULE._RejectPaginationRedirect)
        with pytest.raises(MODULE.SourceMapError, match="redirect"):
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.invalid/")
        return Opener()

    monkeypatch.setattr(MODULE.urllib.request, "build_opener", build_opener)
    with pytest.raises(MODULE.SourceMapError, match="byte limit"):
        MODULE._request_hf_space_page(_page_url())


def test_check_mode_still_fails_on_any_snapshot_drift(monkeypatch, tmp_path, capsys) -> None:
    output = tmp_path / "map.json"
    output.write_text('{"old":true}\n')
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--check", "--output", str(output)])
    monkeypatch.setattr(MODULE, "fetch_spaces", lambda: [])
    monkeypatch.setattr(MODULE, "build_source_map", lambda records: {"summary": {}, "changed": True})
    assert MODULE.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "DRIFT"
    assert output.read_text() == '{"old":true}\n'


def test_source_evidence_reader_rejects_an_oversized_readme(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            assert limit == MODULE.MAX_SOURCE_RESPONSE_BYTES + 1
            return b"x" * limit

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", lambda request, timeout: Response())
    with pytest.raises(MODULE.SourceMapError, match="byte limit"):
        MODULE.fetch_space_readme("SZLHOLDINGS/example-space", "a" * 40)
