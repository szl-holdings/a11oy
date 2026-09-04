from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from scripts.materialize_brain_frontier_v7 import (
    ANATOMY_REPOSITORY,
    FORMULA_REPOSITORY,
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
        "szl-holdings/ouroboros",
        "szl-holdings/a11oy",
        "szl-holdings/szl-forge",
        "szl-holdings/szl-nemo",
    )
    for index, repository in enumerate(reserve_repositories, start=62):
        rows.append(row(index, "source-document", repository=repository))
    for index in range(67, 82):
        rows.append(row(index, "source-document"))
    rows.sort(key=lambda item: item["id"])
    candidates = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = {
        "schema": "szl.second-brain.frontier-state/v1",
        "state": "REVIEW_REQUIRED",
        "candidate_count": len(rows),
        "candidate_set_sha256": hashlib.sha256(candidates).hexdigest(),
        "source_count": 6,
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
        "szl-holdings/ouroboros",
        "szl-holdings/a11oy",
        "szl-holdings/szl-forge",
        "szl-holdings/szl-nemo",
    } <= {handle["repository"] for handle in first["handles"]}


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

def test_selection_accepts_reserved_repository_already_in_formula_tissue() -> None:
    state_raw, candidates_raw = fixture()
    rows = [json.loads(line) for line in candidates_raw.splitlines()]
    authority = next(item for item in rows if item["source_kind"] == "formula-authority")
    authority["source_repository"] = "szl-holdings/anatomy"
    rebuilt = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_set_sha256"] = hashlib.sha256(rebuilt).hexdigest()
    snapshot = build_snapshot(
        "5" * 40,
        json.dumps(state).encode(),
        rebuilt,
        dependencies(),
    )
    assert snapshot["selected_handle_count"] == 72
    assert "szl-holdings/anatomy" in {handle["repository"] for handle in snapshot["handles"]}


def test_selection_still_fails_when_reserved_repository_is_absent_from_all_rows() -> None:
    state_raw, candidates_raw = fixture()
    rows = [
        json.loads(line)
        for line in candidates_raw.splitlines()
        if json.loads(line)["source_repository"] != "szl-holdings/szl-nemo"
    ]
    missing = b"".join(canonical_bytes(item) + b"\n" for item in rows)
    state = json.loads(state_raw)
    state["candidate_count"] = len(rows)
    state["candidate_set_sha256"] = hashlib.sha256(missing).hexdigest()
    with pytest.raises(
        MaterializationError,
        match="reserved repository has no candidate: szl-holdings/szl-nemo",
    ):
        build_snapshot(
            "5" * 40,
            json.dumps(state).encode(),
            missing,
            dependencies(),
        )

