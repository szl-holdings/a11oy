# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oro.api import create_app
from oro.core import (
    Allocation,
    CodexManifest,
    OROContractError,
    Rank,
    RoleSpec,
    allocate_rank,
)
from oro.service import OROService
from oro.signing import Ed25519DSSESigner
from oro.store import OROStore

SOURCE_REVISION = "a" * 40
EVALUATOR_DIGEST = "sha256:" + "b" * 64
PARENT_DIGEST = "sha256:" + "c" * 64
GRANT_DIGEST = "sha256:" + "d" * 64
PROVENANCE_DIGEST = "sha256:" + "e" * 64
CREATED_AT = "2026-08-17T00:00:00.000Z"
RECEIVED_AT = "2026-08-17T00:00:01.000Z"
EXPIRES_AT = "2030-01-01T00:00:00.000Z"
DEVELOPMENT_TOKEN = "oro-development-explicit-authorization-token"
AUTH_HEADERS = {"Authorization": f"Bearer {DEVELOPMENT_TOKEN}"}


def service_for(tmp_path: Path) -> OROService:
    store = OROStore(tmp_path / "oro.sqlite", production=False)
    signer = Ed25519DSSESigner.ephemeral_for_tests()
    return OROService(store=store, signer=signer, production=False)


def plan_payload(service: OROService, *, plan_id: str = "plan-1", kind: str = "task") -> dict:
    return {
        "plan_id": plan_id,
        "orbit_kind": kind,
        "objective": "Produce a source-bound candidate and barrier evidence without release authority.",
        "rank": {
            "schema": "szl.oro-rank/v1",
            "obligations": 2,
            "evidence_deficits": 2,
            "budget_units": 10,
            "turns": 4,
        },
        "expected_participants": ["builder-1", "verifier-1"],
        "codex": service.codex.as_dict(),
        "candidate_author": "alice",
        "evaluator_author": "bob",
        "created_at": CREATED_AT,
        "requested_effectors": ["isolated-worktree-write", "pull-request-open"],
        "source_revision": SOURCE_REVISION,
        "theorem_binding": None,
    }


def participant_payload(participant_id: str, *, orbit_id: str, sequence: int = 0) -> dict:
    return {
        "participant_id": participant_id,
        "provenance": [
            {"span_id": f"{participant_id}-span", "digest": PROVENANCE_DIGEST}
        ],
        "retrieved_span_ids": [f"{participant_id}-span"],
        "citation_span_ids": [f"{participant_id}-span"],
        "amount_micros": 1250000,
        "measurements": [{"unit": "ms", "value_micros": 2500}],
        "observed_at": RECEIVED_AT,
        "authorization": {
            "subject": participant_id,
            "scope": "oro:task",
            "expires_at": EXPIRES_AT,
            "grant_digest": GRANT_DIGEST,
        },
        "evaluator_digest": EVALUATOR_DIGEST,
        "candidate_author": "alice",
        "evaluator_author": "bob",
        "protected_paths_changed": False,
        "formula_commit": SOURCE_REVISION,
        "lineage": {
            "orbit_id": orbit_id,
            "sequence": sequence,
            "parent_digest": PARENT_DIGEST,
            "source_revision": SOURCE_REVISION,
        },
    }


def execution_payload(
    *,
    orbit_id: str = "orbit-1",
    barrier_id: str = "barrier-1",
    generation: int = 0,
    objective_converged: bool = False,
    rank_after: dict | None = None,
    sequence: int = 0,
) -> dict:
    return {
        "orbit_id": orbit_id,
        "barrier_id": barrier_id,
        "generation": generation,
        "expires_at": EXPIRES_AT,
        "rank_after": rank_after
        or {
            "schema": "szl.oro-rank/v1",
            "obligations": 1,
            "evidence_deficits": 2,
            "budget_units": 8,
            "turns": 3,
        },
        "objective_converged": objective_converged,
        "arrivals": [
            {
                "participant_id": participant,
                "generation": generation,
                "payload": participant_payload(participant, orbit_id=orbit_id, sequence=sequence),
                "received_at": RECEIVED_AT,
            }
            for participant in ("builder-1", "verifier-1")
        ],
        "children": None,
        "lineage": {
            "source_revision": SOURCE_REVISION,
            "parent_receipt_digest": PARENT_DIGEST,
        },
        "theorem_binding": None,
    }


def test_rank_is_closed_and_strict() -> None:
    rank = Rank.parse(
        {
            "schema": "szl.oro-rank/v1",
            "obligations": 3,
            "evidence_deficits": 2,
            "budget_units": 1,
            "turns": 1,
        }
    )
    assert rank.vector() == (3, 2, 1, 1)
    assert rank.strictly_decreases_to(Rank(2, 99, 99, 99))
    for bad in (True, 1.0, -1, 1 << 63):
        with pytest.raises(OROContractError):
            Rank.parse(
                {
                    "schema": "szl.oro-rank/v1",
                    "obligations": bad,
                    "evidence_deficits": 0,
                    "budget_units": 0,
                    "turns": 0,
                }
            )
    with pytest.raises(OROContractError):
        Rank.parse(
            {
                "schema": "szl.oro-rank/v2",
                "obligations": 1,
                "evidence_deficits": 1,
                "budget_units": 1,
                "turns": 1,
            }
        )


def test_fanout_consumes_parent_turn_and_cannot_mint_authority() -> None:
    parent = Rank(3, 3, 10, 5)
    receipt = allocate_rank(
        parent,
        (
            Allocation("a", Rank(1, 1, 4, 2)),
            Allocation("b", Rank(2, 2, 6, 2)),
        ),
    )
    assert receipt["consumed_parent_turns"] == 1
    assert receipt["totals"]["turns"] == 4
    assert receipt["limits_after_parent_turn"]["turns"] == 4
    assert receipt["conserved"] is True
    assert receipt["digest"].startswith("sha256:")
    with pytest.raises(OROContractError):
        allocate_rank(parent, (Allocation("mint", Rank(3, 3, 10, 5)),))


def test_role_clone_deep_replaces_authority_and_release_is_absent() -> None:
    builder = RoleSpec(
        name="builder",
        orbit_kinds=("evolution",),
        tools=("isolated-worktree-write",),
        handoffs=("verifier",),
        may_write_candidate=True,
    )
    clone = builder.clone(name="scout", orbit_kinds=("discovery",), tools=("github-read",), may_write_candidate=False)
    assert builder.tools == ("isolated-worktree-write",)
    assert clone.tools == ("github-read",)
    with pytest.raises(OROContractError):
        builder.clone(may_release=True)
    with pytest.raises(OROContractError):
        builder.clone(may_approve=True)


def test_codex_is_data_only_and_rejects_executable_fields(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    body = service.codex.as_dict()
    body["code"] = "print('not permitted')"
    with pytest.raises(OROContractError):
        CodexManifest.parse(body)
    service.store.close()


def test_complete_barrier_is_signed_and_persisted(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    plan = service.create_plan(plan_payload(service))
    result = service.execute_plan(
        plan["plan_id"],
        execution_payload(objective_converged=True),
    )
    barrier = result["barrier"]
    assert barrier["decision"] == "COMPLETE"
    assert barrier["envelope"]["signatures"]
    assert barrier["signer_identity"]["algorithm"] == "Ed25519"
    assert result["certificate"]["kind"] == "completion"
    assert service.store.counts()["receipts"] == 1
    assert service.store.integrity()["ready"] is True
    service.store.close()


def test_continuation_advances_durable_generation_and_rank(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    first = service.execute_plan("plan-1", execution_payload())
    assert first["barrier"]["decision"] == "CONTINUE"
    orbit = service.store.get_orbit("orbit-1")
    assert orbit["status"] == "RUNNING"
    assert orbit["generation"] == 1
    assert orbit["current_rank"]["obligations"] == 1
    assert service.store.get_plan("plan-1")["status"] == "RUNNING"
    service.store.close()


def test_semantic_cycle_refuses_even_when_transport_generation_changes(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    service.execute_plan("plan-1", execution_payload())
    second = execution_payload(
        barrier_id="barrier-2",
        generation=1,
        sequence=0,
        rank_after={
            "schema": "szl.oro-rank/v1",
            "obligations": 0,
            "evidence_deficits": 2,
            "budget_units": 7,
            "turns": 2,
        },
    )
    result = service.execute_plan("plan-1", second)
    assert result["barrier"]["decision"] == "REFUSE"
    assert "semantic cycle" in result["barrier"]["reason"]
    assert result["certificate"]["kind"] == "refusal"
    assert service.store.counts()["negative_results"] == 1
    service.store.close()


def test_blocking_invariant_failure_is_a_persisted_refusal(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    payload = execution_payload()
    payload["arrivals"][0]["payload"]["citation_span_ids"] = ["never-retrieved"]
    result = service.execute_plan("plan-1", payload)
    assert result["barrier"]["decision"] == "REFUSE"
    assert "no-unretrieved-citation" in result["barrier"]["reason"]
    assert result["barrier"]["body"]["derived_descendants_valid"] is False
    service.store.close()


def test_conflicting_duplicate_arrival_is_rejected_and_recorded(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    payload = execution_payload()
    duplicate = json.loads(json.dumps(payload["arrivals"][0]))
    duplicate["payload"]["amount_micros"] = 999
    payload["arrivals"].append(duplicate)
    with pytest.raises(OROContractError, match="conflicting duplicate"):
        service.execute_plan("plan-1", payload)
    negatives = service.store.list_negative_results(orbit_id="orbit-1")
    assert negatives and negatives[0]["evidence"]["error_class"] == "OROContractError"
    service.store.close()


def test_approval_must_be_independent_and_is_idempotent(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    result = service.execute_plan("plan-1", execution_payload(objective_converged=True))
    barrier_id = result["barrier"]["barrier_id"]
    with pytest.raises(OROContractError):
        service.store.approve(barrier_id=barrier_id, approver="alice", approval={"decision": "approve"})
    first = service.store.approve(
        barrier_id=barrier_id,
        approver="carol",
        approval={"decision": "approve", "evidence": result["barrier"]["receipt_digest"]},
    )
    second = service.store.approve(
        barrier_id=barrier_id,
        approver="carol",
        approval={"decision": "approve", "evidence": result["barrier"]["receipt_digest"]},
    )
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    service.store.close()


def test_generation_must_match_durable_frontier(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    service.execute_plan("plan-1", execution_payload())
    with pytest.raises(Exception, match="durable orbit generation"):
        service.execute_plan(
            "plan-1",
            execution_payload(barrier_id="wrong-generation", generation=0),
        )
    service.store.close()


def test_discovery_orbit_rejects_effectors(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    payload = plan_payload(service, plan_id="discovery", kind="discovery")
    payload["requested_effectors"] = ["isolated-worktree-write"]
    with pytest.raises(OROContractError, match="read-only"):
        service.create_plan(payload)
    service.store.close()


def test_http_surface_is_real_and_source_bound(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "api.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        ready = client.get("/api/a11oy/v1/oro/readyz")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True
        contract = client.get("/api/a11oy/v1/oro/contract").json()
        assert contract["release_effector"] == "ABSENT"
        assert contract["machine_checked_termination"] == "NOT_PROVED"
        plan = plan_payload(application.state.oro_runtime.service, plan_id="http-plan")
        created = client.post("/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS)
        assert created.status_code == 201
        executed = client.post(
            "/api/a11oy/v1/oro/plans/http-plan/execute",
            json=execution_payload(orbit_id="http-orbit", barrier_id="http-barrier", objective_converged=True),
            headers=AUTH_HEADERS,
        )
        assert executed.status_code == 200
        assert executed.json()["barrier"]["decision"] == "COMPLETE"
        dashboard = client.get("/oro")
        assert dashboard.status_code == 200
        assert "Obligation-Ranked Orbits" in dashboard.text
        assert "cdn" not in dashboard.text.lower()



def test_write_routes_require_valid_bearer_authority(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "auth.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        plan = plan_payload(application.state.oro_runtime.service, plan_id="auth-plan")
        missing = client.post("/api/a11oy/v1/oro/plans", json=plan)
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"
        invalid = client.post("/api/a11oy/v1/oro/plans", json=plan, headers={"Authorization": "Bearer invalid"})
        assert invalid.status_code == 401
        accepted = client.post("/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS)
        assert accepted.status_code == 201


def test_http_approval_identity_comes_from_bearer_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "approval.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        plan = plan_payload(application.state.oro_runtime.service, plan_id="approval-plan")
        assert client.post("/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS).status_code == 201
        execution = client.post(
            "/api/a11oy/v1/oro/plans/approval-plan/execute",
            json=execution_payload(orbit_id="approval-orbit", barrier_id="approval-barrier", objective_converged=True),
            headers=AUTH_HEADERS,
        )
        assert execution.status_code == 200
        spoofed = client.post(
            "/api/a11oy/v1/oro/barriers/approval-barrier/approvals",
            json={"approver": "spoofed", "approval": {"decision": "approve"}},
            headers=AUTH_HEADERS,
        )
        assert spoofed.status_code == 422
        approved = client.post(
            "/api/a11oy/v1/oro/barriers/approval-barrier/approvals",
            json={"approval": {"decision": "approve"}},
            headers=AUTH_HEADERS,
        )
        assert approved.status_code == 200
        assert approved.json()["approval"]["approver"] == "oro-development"


def test_terminal_orbit_cannot_execute_again(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    service.execute_plan("plan-1", execution_payload(objective_converged=True))
    with pytest.raises(Exception, match="terminal"):
        service.execute_plan("plan-1", execution_payload(barrier_id="after-terminal", generation=0))
    service.store.close()

def test_production_fails_ready_when_managed_signer_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "production")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str((tmp_path / "prod.sqlite").resolve()))
    monkeypatch.delenv("SZL_ORO_SIGNING_KEY_PATH", raising=False)
    monkeypatch.delenv("SZL_ORO_SIGNING_KEY_ID", raising=False)
    monkeypatch.delenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", raising=False)
    application = create_app()
    with TestClient(application) as client:
        health = client.get("/api/a11oy/v1/oro/healthz")
        ready = client.get("/api/a11oy/v1/oro/readyz")
        assert health.status_code == 200
        assert health.json()["alive"] is True
        assert ready.status_code == 503
        assert ready.json()["ready"] is False
        assert ready.json()["secret_value_exposed"] is False
        write = client.post("/api/a11oy/v1/oro/plans", json={})
        assert write.status_code == 503


def test_duplicate_json_fields_and_non_json_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "closed-json.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        duplicate = client.post(
            "/api/a11oy/v1/oro/plans",
            content='{"plan_id":"a","plan_id":"b"}',
            headers={"Content-Type": "application/json", **AUTH_HEADERS},
        )
        assert duplicate.status_code == 422
        non_json = client.post(
            "/api/a11oy/v1/oro/plans",
            content="plan=a",
            headers={"Content-Type": "application/x-www-form-urlencoded", **AUTH_HEADERS},
        )
        assert non_json.status_code == 422
