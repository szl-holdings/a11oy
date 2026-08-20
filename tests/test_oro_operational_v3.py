# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import oro.api as oro_api
from oro.api import create_app
from oro.core import (
    Allocation,
    CodexManifest,
    OROContractError,
    OROStateError,
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


def test_api_import_does_not_construct_an_unowned_runtime() -> None:
    assert callable(oro_api.create_app)
    assert not hasattr(oro_api, "app")


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


def test_plan_text_fields_match_the_closed_schema_contract(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    numeric_id = plan_payload(service)
    numeric_id["plan_id"] = 123
    with pytest.raises(OROContractError, match="plan_id must be a non-empty string"):
        service.create_plan(numeric_id)
    oversized_participant = plan_payload(service)
    oversized_participant["expected_participants"] = ["x" * 513]
    with pytest.raises(OROContractError, match="participant ID is too long"):
        service.create_plan(oversized_participant)
    empty_effector = plan_payload(service)
    empty_effector["requested_effectors"] = [""]
    with pytest.raises(OROContractError, match="requested effector must be a non-empty string"):
        service.create_plan(empty_effector)
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


def test_persisted_plan_and_receipt_match_committed_schemas(tmp_path: Path) -> None:
    schema_dir = Path(__file__).resolve().parents[1] / "schemas/oro/v1"
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in schema_dir.glob("*.json")]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    service = service_for(tmp_path)
    plan = service.create_plan(plan_payload(service))
    result = service.execute_plan("plan-1", execution_payload(objective_converged=True))
    by_name = {Path(schema["$id"]).name: schema for schema in schemas}
    Draft202012Validator(by_name["plan.schema.json"], registry=registry).validate(plan["body"])
    Draft202012Validator(
        by_name["barrier-receipt.schema.json"], registry=registry
    ).validate(result["barrier"]["body"])
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


def test_each_barrier_compares_against_the_current_durable_rank(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    service.execute_plan("plan-1", execution_payload())
    result = service.execute_plan(
        "plan-1",
        execution_payload(
            barrier_id="barrier-2",
            generation=1,
            sequence=1,
            rank_after={
                "schema": "szl.oro-rank/v1",
                "obligations": 1,
                "evidence_deficits": 2,
                "budget_units": 9,
                "turns": 0,
            },
        ),
    )
    assert result["barrier"]["rank_before"]["budget_units"] == 8
    assert result["barrier"]["decision"] == "REFUSE"
    assert "rank did not strictly decrease" in result["barrier"]["reason"]
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


def test_expired_participant_authority_is_a_persisted_refusal(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    payload = execution_payload(objective_converged=True)
    for arrival in payload["arrivals"]:
        arrival["payload"]["authorization"]["expires_at"] = "2026-08-16T00:00:00.000Z"
    result = service.execute_plan("plan-1", payload)
    assert result["barrier"]["decision"] == "REFUSE"
    assert "scoped-authorization" in result["barrier"]["reason"]
    details = {
        item["invariant_id"]: item["detail"]
        for item in result["barrier"]["body"]["invariant_results"]
    }
    assert "expired before barrier evaluation" in details["scoped-authorization"]
    service.store.close()


def test_future_arrival_time_is_rejected_and_recorded(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    payload = execution_payload()
    payload["expires_at"] = "2100-01-01T00:00:00.000Z"
    for arrival in payload["arrivals"]:
        arrival["received_at"] = "2099-01-01T00:00:00.000Z"
    with pytest.raises(OROContractError, match="after barrier evaluation"):
        service.execute_plan("plan-1", payload)
    assert service.store.counts()["negative_results"] == 1
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


def test_production_fails_ready_when_managed_signer_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "production")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str((tmp_path / "prod.sqlite").resolve()))
    token_path = (tmp_path / "api-token").resolve()
    token_path.write_text("t" * 48, encoding="utf-8")
    token_path.chmod(0o600)
    monkeypatch.setenv("SZL_ORO_API_TOKEN_PATH", str(token_path))
    monkeypatch.setenv("SZL_ORO_API_TOKEN_ID", "operator-1")
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
        write = client.post(
            "/api/a11oy/v1/oro/plans",
            json={},
            headers={"Authorization": "Bearer " + "t" * 48},
        )
        assert write.status_code == 503


def test_production_fails_before_storage_when_authorizer_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "production")
    database = (tmp_path / "must-not-exist.sqlite").resolve()
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(database))
    monkeypatch.delenv("SZL_ORO_API_TOKEN_PATH", raising=False)
    monkeypatch.delenv("SZL_ORO_API_TOKEN_ID", raising=False)
    application = create_app()
    with TestClient(application) as client:
        ready = client.get("/api/a11oy/v1/oro/readyz")
        assert ready.status_code == 503
        assert ready.json()["error_class"] == "OROAuthorizerUnavailable"
        write = client.post("/api/a11oy/v1/oro/plans", json={})
        assert write.status_code == 503
        assert write.json()["error"]["code"] == "authorizer_unavailable"
    assert not database.exists()


def test_unknown_environment_fails_closed_before_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "prodution")
    database = (tmp_path / "typo-must-not-exist.sqlite").resolve()
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(database))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        ready = client.get("/api/a11oy/v1/oro/readyz")
        assert ready.status_code == 503
        assert ready.json()["production"] is True
        assert ready.json()["error_class"] == "OROContractError"
    assert not database.exists()


def test_write_routes_require_valid_bearer_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
        invalid = client.post(
            "/api/a11oy/v1/oro/plans",
            json=plan,
            headers={"Authorization": "Bearer invalid"},
        )
        assert invalid.status_code == 401
        accepted = client.post(
            "/api/a11oy/v1/oro/plans",
            json=plan,
            headers=AUTH_HEADERS,
        )
        assert accepted.status_code == 201
        missing_execute = client.post(
            "/api/a11oy/v1/oro/plans/auth-plan/execute",
            json=execution_payload(
                orbit_id="auth-orbit",
                barrier_id="auth-barrier",
                objective_converged=True,
            ),
        )
        assert missing_execute.status_code == 401
        executed = client.post(
            "/api/a11oy/v1/oro/plans/auth-plan/execute",
            json=execution_payload(
                orbit_id="auth-orbit",
                barrier_id="auth-barrier",
                objective_converged=True,
            ),
            headers=AUTH_HEADERS,
        )
        assert executed.status_code == 200
        missing_approval = client.post(
            "/api/a11oy/v1/oro/barriers/auth-barrier/approvals",
            json={"approval": {"decision": "approve"}},
        )
        assert missing_approval.status_code == 401


def test_http_approval_identity_comes_from_bearer_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "approval.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        plan = plan_payload(application.state.oro_runtime.service, plan_id="approval-plan")
        assert client.post(
            "/api/a11oy/v1/oro/plans", json=plan, headers=AUTH_HEADERS
        ).status_code == 201
        execution = client.post(
            "/api/a11oy/v1/oro/plans/approval-plan/execute",
            json=execution_payload(
                orbit_id="approval-orbit",
                barrier_id="approval-barrier",
                objective_converged=True,
            ),
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
    with pytest.raises(OROStateError, match="terminal"):
        service.execute_plan(
            "plan-1",
            execution_payload(barrier_id="after-terminal", generation=0),
        )
    service.store.close()


def test_store_cannot_reopen_a_terminal_plan(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_plan(plan_payload(service))
    service.store.connection.execute(
        "UPDATE plans SET status='COMPLETE' WHERE plan_id='plan-1'"
    )
    with pytest.raises(OROStateError, match="terminal plan cannot be reopened"):
        service.store.create_orbit(
            orbit_id="stale-orbit",
            plan_id="plan-1",
            generation=0,
            rank=Rank(2, 2, 10, 4),
        )
    assert service.store.get_orbit("stale-orbit") is None
    assert service.store.get_plan("plan-1")["status"] == "COMPLETE"
    service.store.close()


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


def test_query_limits_are_rejected_at_the_http_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZL_ORO_ENV", "development")
    monkeypatch.setenv("SZL_ORO_DB_PATH", str(tmp_path / "query.sqlite"))
    monkeypatch.setenv("SZL_ORO_ALLOW_EPHEMERAL_SIGNER", "1")
    monkeypatch.setenv("SZL_ORO_ALLOW_DEVELOPMENT_AUTH", "1")
    application = create_app()
    with TestClient(application) as client:
        assert client.get("/api/a11oy/v1/oro/plans?limit=501").status_code == 422
        assert client.get("/api/a11oy/v1/oro/negative-results?limit=1001").status_code == 422


def test_v1_database_is_migrated_to_a_rank_bound_frontier(tmp_path: Path) -> None:
    database = tmp_path / "upgrade.sqlite"
    service = OROService(
        store=OROStore(database, production=False),
        signer=Ed25519DSSESigner.ephemeral_for_tests(),
        production=False,
    )
    service.create_plan(plan_payload(service))
    service.store.create_orbit(
        orbit_id="upgrade-orbit",
        plan_id="plan-1",
        generation=0,
        rank=Rank(2, 2, 10, 4),
    )
    service.store.close()
    connection = sqlite3.connect(database)
    connection.execute("ALTER TABLE orbit_runs DROP COLUMN current_rank_json")
    connection.execute(
        "UPDATE metadata SET value='szl.oro.sqlite/v1' WHERE key='schema'"
    )
    connection.execute("PRAGMA user_version=1")
    connection.commit()
    connection.close()

    upgraded = OROStore(database, production=False)
    orbit = upgraded.get_orbit("upgrade-orbit")
    assert upgraded.integrity()["schema_version"] == 2
    assert upgraded.integrity()["schema"] == "szl.oro.sqlite/v2"
    assert orbit["current_rank"] == Rank(2, 2, 10, 4).as_dict()
    with pytest.raises(sqlite3.IntegrityError, match="invalid v2 orbit frontier"):
        upgraded.connection.execute(
            "UPDATE orbit_runs SET current_rank_json=NULL WHERE orbit_id='upgrade-orbit'"
        )
    upgraded.close()


def test_standalone_runtime_delivery_does_not_change_protected_hf_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    protected_dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    standalone_dockerfile = (root / "deploy/oro/Dockerfile").read_text(encoding="utf-8")
    assert "COPY oro/ ./oro/" not in protected_dockerfile
    assert "COPY schemas/oro/ ./schemas/oro/" not in protected_dockerfile
    assert "COPY --chown=10001:10001 oro/ ./oro/" in standalone_dockerfile
    assert "COPY --chown=10001:10001 schemas/oro/ ./schemas/oro/" in standalone_dockerfile


def test_oro_workflow_is_validation_only() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/oro-control-plane.yml").read_text(encoding="utf-8")
    runtime_lock = (root / ".github/requirements/ci-oro.txt").read_text(encoding="utf-8")
    assert "contents: write" not in workflow
    assert "persist-credentials: true" not in workflow
    assert "git push" not in workflow
    assert "_apply_oro_v3_repairs.py" not in workflow
    assert "oro.api:create_app --factory" in workflow
    assert "-r .github/requirements/ci-oro.txt" in workflow
    assert "uvicorn==0.49.0" in runtime_lock
    assert "click==8.3.3" in runtime_lock
    assert runtime_lock.count("--hash=sha256:") == 4
    assert not (root / "scripts/_apply_oro_v3_repairs.py").exists()
