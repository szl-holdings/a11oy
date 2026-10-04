from __future__ import annotations

import hashlib
import json
from urllib.parse import quote, urlencode
from typing import Any

import pytest

from scripts.materialize_brain_frontier_v7 import (
    ANATOMY_REPOSITORY,
    FORMULA_REPOSITORY,
    FORUM_PATH,
    FORUM_REPOSITORY,
    METADATA_REVISION_KIND,
    MaterializationError,
    OUROBOROS_REPOSITORY,
    build_snapshot,
    canonical_bytes,
    validate_frontier,
)


def row(
    index: int,
    kind: str,
    domain: str | None = None,
    repository: str = "szl-holdings/szl-formulas",
) -> dict[str, Any]:
    content = f"review candidate {index}; {kind}; no execution or promotion authority"
    result: dict[str, Any] = {
        "schema": "szl.second-brain.frontier-candidate/v1",
        "id": f"frontier:{index:032x}",
        "title": f"Candidate {index}",
        "content": content,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "source_repository": repository,
        "source_revision": "1" * 40,
        "source_path": "atlas/formula-atlas.v1.json",
        "source_kind": kind,
        "admission": "REFERENCE_AND_CONSTRAINT_INPUT_ONLY",
        "candidate_state": "DISCOVERED_REVIEW_REQUIRED",
        "content_access": "CONTROLLER_ONLY",
    }
    if domain:
        result["quant_domain"] = domain
    return result


def fixture() -> tuple[bytes, bytes]:
    rows: list[dict[str, Any]] = [row(1, "formula-authority")]
    for index in range(2, 32):
        rows.append(row(index, "attributed-formula", f"domain-{index % 9}"))
    for index in range(32, 53):
        rows.append(row(index, "executable-formula"))
    for index in range(53, 62):
        rows.append(row(index, "quant-domain", f"domain-{index - 53}"))
    reserve_repositories = (
        "szl-holdings/anatomy",
        "szl-holdings/szl-ouroboros",
        "szl-holdings/a11oy",
        "szl-holdings/szl-forge",
        "szl-holdings/szl-nemo",
        "szl-holdings/szl-kernels",
    )
    for index, repository in enumerate(reserve_repositories, start=62):
        rows.append(row(index, "source-document", repository=repository))
    for index in range(68, 82):
        rows.append(row(index, "source-document"))
    rows.sort(key=lambda item: item["id"])
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = {
        "schema": "szl.second-brain.frontier-state/v1",
        "state": "REVIEW_REQUIRED",
        "candidate_count": len(rows),
        "candidate_set_sha256": hashlib.sha256(candidates).hexdigest(),
        "source_count": 7,
        "sources": [],
        "source_kind_counts": {},
        "quant_domain_counts": {},
        "public_content_access": "HANDLES_ONLY",
        "controller_content_access": "AUTHORIZED_CONTROLLER_ONLY",
        "private_graph_nodes_loaded": 0,
        "raw_graph_nodes_admitted_to_gradients": 0,
        "training_authority": "NONE",
        "promotion_authority": "NONE",
        "execution_authority": "NONE",
        "merge_authority": "NONE",
        "lambda": "CONJECTURE_1",
    }
    return json.dumps(state).encode(), candidates


def dependencies() -> dict[str, str]:
    return {
        ANATOMY_REPOSITORY: "2" * 40,
        FORMULA_REPOSITORY: "3" * 40,
        OUROBOROS_REPOSITORY: "4" * 40,
    }


def forum_fixture(*, selected: bool = False, count: int = 1) -> tuple[bytes, bytes]:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    if selected:
        rows = rows[:72 - count]
    for index in range(count):
        pilot = row(82 + index, "forum-insight", repository=FORUM_REPOSITORY)
        pilot["source_path"] = FORUM_PATH
        pilot["admission"] = "DISCOVERED_REVIEW_REQUIRED"
        rows.append(pilot)
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["source_count"] = 8
    state["candidate_count"] = len(rows)
    state["candidate_set_sha256"] = hashlib.sha256(candidates).hexdigest()
    return json.dumps(state).encode(), candidates


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("count", [1, 2])
def test_reviewed_forum_pilot_is_optional_bounded_and_handles_only(selected: bool, count: int) -> None:
    state_raw, candidates_raw = forum_fixture(selected=selected, count=count)
    snapshot = build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    assert snapshot == build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    assert snapshot["selected_handle_count"] == len(snapshot["handles"]) == 72
    pilot_handles = [handle for handle in snapshot["handles"] if handle["kind"] == "forum-insight"]
    assert len(pilot_handles) == count * int(selected)
    if selected:
        assert pilot_handles[0]["repository"] == FORUM_REPOSITORY
        assert pilot_handles[0]["path"] == FORUM_PATH
        assert pilot_handles[0]["admission"] == "DISCOVERED_REVIEW_REQUIRED"
        assert pilot_handles[0]["contentAccess"] == "HANDLES_ONLY"
        assert pilot_handles[0]["authority"] == "NONE"
    assert snapshot["formula_atlas"]["locked_proven_formula_count"] == 8
    assert all(snapshot["authority"][key] == "NONE" for key in (
        "training", "promotion", "execution", "merge", "provider_mutation",
    ))
    assert '"content"' not in json.dumps(snapshot)


@pytest.mark.parametrize("field,value", [
    ("source_repository", "szl-holdings/a11oy"),
    ("source_repository", "external/forum-corpus"),
    ("source_path", "dataset/other.public.jsonl"),
    ("source_kind", "source-document"),
    ("source_kind", "invented-kind"),
    ("admission", "REFERENCE_AND_CONSTRAINT_INPUT_ONLY"),
    ("quant_domain", "domain-0"),
    ("candidate_state", "PROMOTED"),
    ("content_access", "PUBLIC"),
    ("source_revision", "main"),
    ("content_sha256", "0" * 64),
])
def test_forum_pilot_cannot_expand_source_or_authority(field: str, value: str) -> None:
    state_raw, candidates_raw = forum_fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows[-1][field] = value
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_set_sha256"] = hashlib.sha256(candidates).hexdigest()
    with pytest.raises(MaterializationError):
        validate_frontier(json.dumps(state).encode(), candidates)


def test_forum_pilot_count_cannot_silently_expand() -> None:
    state_raw, candidates_raw = forum_fixture(count=2)
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows.append(rows[-1] | {"id": f"frontier:{84:032x}"})
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_count"] = len(rows)
    state["candidate_set_sha256"] = hashlib.sha256(candidates).hexdigest()
    with pytest.raises(MaterializationError, match="forum pilot count"):
        validate_frontier(json.dumps(state).encode(), candidates)


def research_fixture(*, provider: str = "arxiv", selected: bool = False) -> tuple[bytes, bytes]:
    """Synthetic public metadata with real binding rules, never an external receipt."""
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    if selected:
        rows = rows[:71]
    identifier = "2401.01234v2" if provider == "arxiv" else "10.1234/example(2026)"
    metadata = {
        "provider": provider, "identifier": identifier,
        "canonical_url": ("https://arxiv.org/abs/" if provider == "arxiv" else "https://doi.org/") + identifier,
        "title": "Synthetic metadata contract fixture", "authors": ["Test Author"],
        "published": "2026-10-01T00:00:00Z" if provider == "arxiv" else "2026-10",
        "updated": "2026-10-02T00:00:00Z" if provider == "arxiv" else None,
        "categories": ["cs.AI"] if provider == "arxiv" else [], "licence_urls": [],
        "metadata_licence": "CC0-1.0" if provider == "arxiv" else "NOT_DECLARED_BY_RESPONSE",
        "full_text_licence": "NOT_INFERRED",
    }
    capture_sha = hashlib.sha256(canonical_bytes(metadata)).hexdigest()
    content = "\n".join((metadata["title"], "Authors: " + ", ".join(metadata["authors"]),
                         "Identifier: " + identifier, "Publication date: " + str(metadata["published"]),
                         ("Categories: " + ", ".join(metadata["categories"])).rstrip(),
                         "Metadata licence: " + metadata["metadata_licence"],
                         "Full text licence: NOT_INFERRED", "Source: " + metadata["canonical_url"]))
    candidate = row(90, "research-metadata", repository=f"public-metadata/{provider}")
    candidate.update({
        "title": metadata["title"], "source_path": identifier, "source_revision": capture_sha,
        "source_revision_kind": METADATA_REVISION_KIND,
        "content": content, "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "admission": "DISCOVERED_REVIEW_REQUIRED",
        "provenance": {
            "provider": provider, "identifier": identifier, "metadata": metadata,
            "capture_sha256": capture_sha, "response_sha256": "a" * 64, "response_bytes": 512,
            "request_url": ("https://export.arxiv.org/api/query?" + urlencode({"id_list": identifier, "max_results": 1})
                            if provider == "arxiv" else "https://api.crossref.org/works/" + quote(identifier, safe="")),
            "observed_at": "2026-10-03T00:00:00Z",
            "source_authentication": "PUBLIC_HTTPS_METADATA_NOT_INDEPENDENT_ATTESTATION",
        },
    })
    rows.append(candidate)
    return encode_frontier(json.loads(state_raw), rows)


def encode_frontier(state: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[bytes, bytes]:
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = state | {"candidate_count": len(rows), "candidate_set_sha256": hashlib.sha256(candidates).hexdigest()}
    return json.dumps(state).encode(), candidates


@pytest.mark.parametrize("provider", ["arxiv", "crossref"])
@pytest.mark.parametrize("selected", [False, True])
def test_research_capture_is_typed_and_handles_only(provider: str, selected: bool) -> None:
    state_raw, candidates_raw = research_fixture(provider=provider, selected=selected)
    snapshot = build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    assert snapshot == build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    handles = [handle for handle in snapshot["handles"] if handle["kind"] == "research-metadata"]
    assert len(handles) == int(selected)
    if selected:
        assert handles[0]["revisionKind"] == METADATA_REVISION_KIND
        assert len(handles[0]["revision"]) == 64
        assert handles[0]["repository"] == f"public-metadata/{provider}"
        assert handles[0]["contentAccess"] == "HANDLES_ONLY"
        assert handles[0]["authority"] == "NONE"
    assert len(snapshot["handles"]) == 72
    assert sum(handle["kind"] in {"formula-authority", "attributed-formula", "executable-formula", "quant-domain"}
               for handle in snapshot["handles"]) == 61
    assert '"provenance"' not in json.dumps(snapshot)
    assert '"metadata"' not in json.dumps(snapshot)
    assert '"content"' not in json.dumps(snapshot)


@pytest.mark.parametrize("path,value", [
    ("source_repository", "szl-holdings/szl-formulas"),
    ("source_repository", "public-metadata/unknown"),
    ("source_kind", "source-document"),
    ("source_path", "2401.01234"),
    ("source_revision", "1" * 40),
    ("source_revision_kind", "git-commit"),
    ("title", "Unbound title"),
    ("content", "Unbound content"),
    ("admission", "REFERENCE_AND_CONSTRAINT_INPUT_ONLY"),
    ("quant_domain", "domain-0"),
    ("provenance.provider", "crossref"),
    ("provenance.identifier", "2401.01234v1"),
    ("provenance.capture_sha256", "0" * 64),
    ("provenance.response_sha256", "1" * 40),
    ("provenance.response_bytes", 0),
    ("provenance.response_bytes", True),
    ("provenance.response_bytes", 262145),
    ("provenance.observed_at", "2026-10-03"),
    ("provenance.request_url", "https://attacker.invalid/metadata"),
    ("provenance.request_url", ["https://export.arxiv.org/api/query"]),
    ("provenance.source_authentication", "INDEPENDENTLY_ATTESTED"),
    ("provenance.metadata.canonical_url", "https://attacker.invalid/paper"),
    ("provenance.metadata.full_text_licence", "CC-BY-4.0"),
    ("provenance.metadata.metadata_licence", "NOT_DECLARED_BY_RESPONSE"),
    ("provenance.metadata.authors", ["Author"] * 33),
    ("provenance.metadata.title", "<b>Unnormalized</b>"),
    ("provenance.metadata.provider", ["arxiv"]),
    ("provenance.metadata.authors", ["hf_" + "a" * 30]),
    ("provenance.metadata.updated", None),
])
def test_research_binding_rejects_semantic_tampering_after_rehash(path: str, value: Any) -> None:
    state_raw, candidates_raw = research_fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    target = rows[-1]
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value
    # Refresh outer digests to prove the semantic binding, not just file hashing.
    rows[-1]["content_sha256"] = hashlib.sha256(rows[-1]["content"].encode()).hexdigest()
    if path.startswith("provenance.metadata."):
        capture = hashlib.sha256(canonical_bytes(rows[-1]["provenance"]["metadata"])).hexdigest()
        rows[-1]["source_revision"] = rows[-1]["provenance"]["capture_sha256"] = capture
    with pytest.raises(MaterializationError):
        validate_frontier(*encode_frontier(json.loads(state_raw), rows))


def test_git_source_cannot_be_retyped_as_a_metadata_capture() -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows[0]["source_revision_kind"] = METADATA_REVISION_KIND
    with pytest.raises(MaterializationError, match="Git source"):
        validate_frontier(*encode_frontier(json.loads(state_raw), rows))


def test_research_projection_uses_producer_title_and_content_bounds() -> None:
    state_raw, candidates_raw = research_fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    candidate = rows[-1]
    metadata = candidate["provenance"]["metadata"]
    old_title = metadata["title"]
    metadata["title"] = "A" * 240
    metadata["authors"] = ["B" * 240] * 32
    candidate["title"] = "A" * 180
    candidate["content"] = candidate["content"].replace(old_title, metadata["title"]).replace(
        "Authors: Test Author", "Authors: " + ", ".join(metadata["authors"]))[:1600]
    candidate["content_sha256"] = hashlib.sha256(candidate["content"].encode()).hexdigest()
    candidate["source_revision"] = candidate["provenance"]["capture_sha256"] = hashlib.sha256(canonical_bytes(metadata)).hexdigest()
    validate_frontier(*encode_frontier(json.loads(state_raw), rows))
    candidate["title"] = metadata["title"]
    with pytest.raises(MaterializationError, match="title"):
        validate_frontier(*encode_frontier(json.loads(state_raw), rows))


def test_research_capture_count_remains_bounded() -> None:
    state_raw, candidates_raw = research_fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    candidate = rows[-1]
    rows.extend(candidate | {"id": f"frontier:{100 + index:032x}"} for index in range(96))
    with pytest.raises(MaterializationError, match="research metadata count"):
        validate_frontier(*encode_frontier(json.loads(state_raw), rows))


def test_snapshot_is_handles_only_deterministic_and_exact() -> None:
    state_raw, candidates_raw = fixture()
    first = build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    second = build_snapshot("5" * 40, state_raw, candidates_raw, dependencies())
    assert first == second
    assert first["schema"] == "szl.a11oy.brain-frontier-holographic-v7/v1"
    assert first["state"] == "SOURCE_BOUND_REVIEW_MEMORY"
    assert first["selected_handle_count"] == len(first["handles"]) == 72
    assert first["sources"]["second_brain"]["revision"] == "5" * 40
    assert len(first["sources"]["second_brain"]["candidate_set_sha256"]) == 64
    assert len(first["snapshot_sha256"]) == 64
    assert first["formula_atlas"] == {
        "attributed_formula_count": 30,
        "executable_formula_count": 21,
        "quant_domain_count": 9,
        "locked_proven_formula_count": 8,
        "f_number_to_executable_mapping": "UNKNOWN_NOT_INFERRED",
        "lambda": "CONJECTURE_1",
    }
    assert first["loop"] == ["OBSERVE", "ORIENT", "PROPOSE", "VERIFY", "HOLD"]
    assert first["authority"] == {
        "public_content_access": "HANDLES_ONLY",
        "controller_content_access": "NOT_EXPOSED_BY_A11OY_HOLOGRAPHIC",
        "training": "NONE",
        "promotion": "NONE",
        "execution": "NONE",
        "merge": "NONE",
        "provider_mutation": "NONE",
        "private_graph_present": False,
        "raw_graph_nodes_admitted_to_gradients": 0,
        "human_review_required": True,
    }
    serialized = json.dumps(first, sort_keys=True).lower()
    assert '"content"' not in serialized
    assert '"text"' not in serialized
    assert all(handle["contentAccess"] == "HANDLES_ONLY" for handle in first["handles"])
    assert all(handle["authority"] == "NONE" for handle in first["handles"])
    assert {
        "szl-holdings/szl-formulas",
        "szl-holdings/anatomy",
        "szl-holdings/szl-ouroboros",
        "szl-holdings/a11oy",
        "szl-holdings/szl-forge",
        "szl-holdings/szl-nemo",
        "szl-holdings/szl-kernels",
    } == {handle["repository"] for handle in first["handles"]}


def test_selection_fails_closed_when_72_handles_are_unavailable() -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()][:-10]
    shortened = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_count"] = len(rows)
    state["candidate_set_sha256"] = hashlib.sha256(shortened).hexdigest()
    with pytest.raises(MaterializationError, match="72 are required"):
        build_snapshot(
            "5" * 40,
            json.dumps(state).encode(),
            shortened,
            dependencies(),
        )


def test_selection_fails_closed_when_a_reserved_repository_is_missing() -> None:
    state_raw, candidates_raw = fixture()
    rows = [
        json.loads(line)
        for line in candidates_raw.splitlines()
        if json.loads(line)["source_repository"] != "szl-holdings/anatomy"
    ]
    assert len(rows) >= 72
    missing_reserve = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_count"] = len(rows)
    state["candidate_set_sha256"] = hashlib.sha256(missing_reserve).hexdigest()
    with pytest.raises(
        MaterializationError,
        match="reserved repository has no candidate: szl-holdings/anatomy",
    ):
        build_snapshot(
            "5" * 40,
            json.dumps(state).encode(),
            missing_reserve,
            dependencies(),
        )


def test_selection_fails_closed_when_formula_repository_lineage_is_missing() -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    for item in rows:
        if item["source_repository"] == FORMULA_REPOSITORY:
            item["source_repository"] = "szl-holdings/a11oy"
    assert len(rows) >= 72
    missing_formula_lineage = b"".join(
        canonical_bytes(item) + b"\n" for item in rows
    )
    state = json.loads(state_raw)
    state["candidate_set_sha256"] = hashlib.sha256(
        missing_formula_lineage
    ).hexdigest()
    with pytest.raises(
        MaterializationError,
        match=f"reserved repository has no candidate: {FORMULA_REPOSITORY}",
    ):
        build_snapshot(
            "5" * 40,
            json.dumps(state).encode(),
            missing_formula_lineage,
            dependencies(),
        )


def test_formula_tissue_can_satisfy_a_reserved_repository() -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows[0]["source_repository"] = "szl-holdings/anatomy"
    rows = [
        item
        for item in rows
        if not (
            item["source_repository"] == "szl-holdings/anatomy"
            and item["source_kind"] == "source-document"
        )
    ]
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_count"] = len(rows)
    state["candidate_set_sha256"] = hashlib.sha256(candidates).hexdigest()
    snapshot = build_snapshot(
        "5" * 40,
        json.dumps(state).encode(),
        candidates,
        dependencies(),
    )
    assert len(snapshot["handles"]) == 72
    assert "szl-holdings/anatomy" in {
        handle["repository"] for handle in snapshot["handles"]
    }


def test_candidate_content_and_promotion_tampering_fail_closed() -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows[0]["content_sha256"] = "0" * 64
    tampered = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    with pytest.raises(MaterializationError, match="content digest"):
        validate_frontier(state_raw, tampered)

    state = json.loads(state_raw)
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows[0]["candidate_state"] = "PROMOTED"
    promoted = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state["candidate_set_sha256"] = hashlib.sha256(promoted).hexdigest()
    with pytest.raises(MaterializationError, match="promoted"):
        validate_frontier(json.dumps(state).encode(), promoted)


def test_private_graph_training_and_execution_authority_are_rejected() -> None:
    state_raw, candidates_raw = fixture()
    state = json.loads(state_raw)
    state["private_graph_nodes_loaded"] = 1
    with pytest.raises(MaterializationError, match="private graph"):
        validate_frontier(json.dumps(state).encode(), candidates_raw)

    state = json.loads(state_raw)
    state["training_authority"] = "ALLOWED"
    with pytest.raises(MaterializationError, match="training_authority"):
        validate_frontier(json.dumps(state).encode(), candidates_raw)

    state = json.loads(state_raw)
    state["execution_authority"] = "ALLOWED"
    with pytest.raises(MaterializationError, match="execution_authority"):
        validate_frontier(json.dumps(state).encode(), candidates_raw)


def test_dependency_revisions_must_be_exact() -> None:
    state_raw, candidates_raw = fixture()
    broken = dependencies()
    broken[ANATOMY_REPOSITORY] = "main"
    with pytest.raises(MaterializationError, match="not exact"):
        build_snapshot("5" * 40, state_raw, candidates_raw, broken)


def test_source_and_dependency_revision_sets_must_be_exact() -> None:
    state_raw, candidates_raw = fixture()
    with pytest.raises(MaterializationError, match="second brain revision"):
        build_snapshot("main", state_raw, candidates_raw, dependencies())

    missing = dependencies()
    del missing[ANATOMY_REPOSITORY]
    with pytest.raises(MaterializationError, match="dependency repository set"):
        build_snapshot("5" * 40, state_raw, candidates_raw, missing)

    unexpected = dependencies()
    unexpected["szl-holdings/a11oy"] = "6" * 40
    with pytest.raises(MaterializationError, match="dependency repository set"):
        build_snapshot("5" * 40, state_raw, candidates_raw, unexpected)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("title", "", "title"),
        ("title", "unsafe\nlabel", "title"),
        ("source_path", "../private.txt", "path"),
        ("source_kind", "invented-kind", "kind"),
        ("admission", "promoted", "admission"),
        ("admission", "EXECUTE_NOW", "admission"),
        ("quant_domain", "../private", "quant domain"),
    ),
)
def test_untrusted_display_metadata_fails_closed(
    field: str, value: str, message: str
) -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    rows[0][field] = value
    tampered = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_set_sha256"] = hashlib.sha256(tampered).hexdigest()
    with pytest.raises(MaterializationError, match=message):
        validate_frontier(json.dumps(state).encode(), tampered)


def test_candidate_count_requires_an_exact_integer() -> None:
    state_raw, candidates_raw = fixture()
    state = json.loads(state_raw)
    state["candidate_count"] = True
    with pytest.raises(MaterializationError, match="candidate count"):
        validate_frontier(json.dumps(state).encode(), candidates_raw)
