from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from szl_oro_core import (
    Allocation,
    Arrival,
    BarrierEngine,
    InvariantSpec,
    OROContractError,
    OROSignerUnavailable,
    OROStateError,
    OROStore,
    Rank,
    semantic_hash,
    validate_conserved_fanout,
)


def _expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")


def _invariant(passed: bool = True) -> InvariantSpec:
    return InvariantSpec(
        invariant_id="provenance.total",
        version="1.0.0",
        source_blob_digest="sha256:" + "1" * 64,
        implementation_digest="sha256:" + "2" * 64,
        input_schema="szl.oro-merged/v1",
        golden_vectors_digest="sha256:" + "3" * 64,
        evaluator=lambda _merged: (passed, "complete" if passed else "missing span"),
    )


def test_rank_rejects_bool_float_negative_overflow_and_version_drift() -> None:
    for bad in (True, 1.0, -1, 1 << 63):
        with pytest.raises(OROContractError):
            Rank(bad, 0, 0, 0)  # type: ignore[arg-type]
    with pytest.raises(OROContractError):
        Rank(1, 1, 1, 1, schema="szl.oro-rank/v999")


def test_rank_decrease_is_lexicographic_and_objective_is_separate() -> None:
    before = Rank(3, 5, 8, 13)
    assert before.strictly_decreases_to(Rank(2, 99, 99, 99))
    assert not before.strictly_decreases_to(Rank(3, 5, 8, 13))
    assert not before.strictly_decreases_to(Rank(4, 0, 0, 0))


def test_fanout_consumes_parent_turn_and_cannot_mint_authority() -> None:
    parent = Rank(4, 3, 10, 5)
    receipt = validate_conserved_fanout(
        parent,
        [
            Allocation("a", Rank(2, 1, 4, 2)),
            Allocation("b", Rank(2, 2, 6, 2)),
        ],
    )
    assert receipt["conserved"] is True
    assert receipt["consumed_parent_turns"] == 1
    assert receipt["totals"]["turns"] == 4
    with pytest.raises(OROContractError):
        validate_conserved_fanout(
            parent,
            [Allocation("a", Rank(4, 3, 10, 5))],
        )


def test_semantic_hash_is_domain_bound_and_canonical() -> None:
    left = semantic_hash({"b": 2, "a": 1})
    right = semantic_hash({"a": 1, "b": 2})
    assert left == right
    assert left.startswith("sha256:")


def test_store_requires_independent_candidate_and_evaluator(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    try:
        with pytest.raises(OROContractError):
            store.create_orbit(
                orbit_id="orbit-1",
                plan_id="plan-1",
                generation=0,
                candidate_author="same",
                evaluator_author="same",
            )
    finally:
        store.close()


def test_production_engine_fails_closed_without_governed_signer(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    try:
        with pytest.raises(OROSignerUnavailable):
            BarrierEngine(store=store, invariants=[_invariant()], production=True)
    finally:
        store.close()


def test_barrier_continues_only_after_invariants_and_rank_decrease(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    store.create_orbit(
        orbit_id="orbit-1",
        plan_id="plan-1",
        generation=0,
        candidate_author="builder",
        evaluator_author="verifier",
    )
    signer = lambda payload: {
        "mode": "SIGNED",
        "payload_digest": semantic_hash({"bytes": payload.hex()}),
        "signature": "test-signature",
        "signer_id": "test-governed-signer",
    }
    engine = BarrierEngine(store=store, invariants=[_invariant()], signer=signer, production=True)
    try:
        receipt = engine.evaluate(
            barrier_id="barrier-1",
            orbit_id="orbit-1",
            generation=0,
            expected_participants={"builder", "verifier"},
            arrivals=[
                Arrival("builder", 0, {"candidate": "A"}, "2026-08-11T10:00:00Z"),
                Arrival("verifier", 0, {"tests": "PASS"}, "2026-08-11T10:00:01Z"),
            ],
            rank_before=Rank(2, 2, 10, 4),
            rank_after=Rank(1, 2, 10, 3),
            objective_converged=False,
            expires_at=_expiry(),
            theorem_binding={"status": "MODELED", "rank_definition": "oro-rank/v1"},
        )
        assert receipt["decision"] == "CONTINUE"
        assert receipt["rank_decreased"] is True
        assert receipt["signature_envelope"]["mode"] == "SIGNED"
        assert store.barrier("barrier-1") is not None
    finally:
        store.close()


def test_barrier_halts_on_invariant_failure_and_persists_negative_result(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    store.create_orbit(
        orbit_id="orbit-2",
        plan_id="plan-2",
        generation=1,
        candidate_author="builder",
        evaluator_author="verifier",
    )
    engine = BarrierEngine(store=store, invariants=[_invariant(False)])
    try:
        receipt = engine.evaluate(
            barrier_id="barrier-2",
            orbit_id="orbit-2",
            generation=1,
            expected_participants={"builder"},
            arrivals=[Arrival("builder", 1, {"candidate": "B"}, "2026-08-11T10:00:00Z")],
            rank_before=Rank(2, 1, 8, 3),
            rank_after=Rank(1, 1, 7, 2),
            objective_converged=False,
            expires_at=_expiry(),
            theorem_binding={"status": "MODELED"},
        )
        assert receipt["decision"] == "HALT"
        assert "provenance.total" in receipt["reason"]
        count = store.connection.execute("SELECT COUNT(*) FROM negative_results").fetchone()[0]
        assert count == 1
    finally:
        store.close()


def test_conflicting_duplicate_arrival_is_rejected(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    store.create_orbit(
        orbit_id="orbit-3",
        plan_id="plan-3",
        generation=0,
        candidate_author="builder",
        evaluator_author="verifier",
    )
    engine = BarrierEngine(store=store, invariants=[_invariant()])
    try:
        with pytest.raises(OROContractError, match="conflicting duplicate"):
            engine.evaluate(
                barrier_id="barrier-3",
                orbit_id="orbit-3",
                generation=0,
                expected_participants={"builder"},
                arrivals=[
                    Arrival("builder", 0, {"v": 1}, "2026-08-11T10:00:00Z"),
                    Arrival("builder", 0, {"v": 2}, "2026-08-11T10:00:01Z"),
                ],
                rank_before=Rank(2, 1, 8, 3),
                rank_after=Rank(1, 1, 7, 2),
                objective_converged=False,
                expires_at=_expiry(),
                theorem_binding={"status": "MODELED"},
            )
    finally:
        store.close()


def test_semantic_cycle_is_rejected_on_repeat_generation_state(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    store.create_orbit(
        orbit_id="orbit-4",
        plan_id="plan-4",
        generation=0,
        candidate_author="builder",
        evaluator_author="verifier",
    )
    engine = BarrierEngine(store=store, invariants=[_invariant()])
    kwargs = dict(
        orbit_id="orbit-4",
        generation=0,
        expected_participants={"builder"},
        arrivals=[Arrival("builder", 0, {"stable": True}, "2026-08-11T10:00:00Z")],
        rank_before=Rank(2, 1, 8, 3),
        rank_after=Rank(1, 1, 7, 2),
        objective_converged=False,
        expires_at=_expiry(),
        theorem_binding={"status": "MODELED"},
    )
    try:
        engine.evaluate(barrier_id="barrier-4a", **kwargs)
        with pytest.raises(OROStateError, match="semantic cycle"):
            engine.evaluate(barrier_id="barrier-4b", **kwargs)
    finally:
        store.close()


def test_approval_cannot_be_candidate_or_evaluator_author(tmp_path) -> None:
    store = OROStore(tmp_path / "oro.sqlite3")
    store.create_orbit(
        orbit_id="orbit-5",
        plan_id="plan-5",
        generation=0,
        candidate_author="builder",
        evaluator_author="verifier",
    )
    engine = BarrierEngine(store=store, invariants=[_invariant()])
    try:
        engine.evaluate(
            barrier_id="barrier-5",
            orbit_id="orbit-5",
            generation=0,
            expected_participants={"builder"},
            arrivals=[Arrival("builder", 0, {"v": 1}, "2026-08-11T10:00:00Z")],
            rank_before=Rank(2, 1, 8, 3),
            rank_after=Rank(1, 1, 7, 2),
            objective_converged=False,
            expires_at=_expiry(),
            theorem_binding={"status": "MODELED"},
        )
        with pytest.raises(OROContractError):
            store.approve("barrier-5", "builder", {"approved": True})
        digest = store.approve("barrier-5", "integrator", {"approved": True})
        assert digest.startswith("sha256:")
    finally:
        store.close()
