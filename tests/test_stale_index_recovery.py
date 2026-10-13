# SPDX-License-Identifier: Apache-2.0
"""One synthetic stale-index recovery. This is not estate readiness."""

from __future__ import annotations

import hashlib

import pytest

import a11oy_org_rag as org_rag


ORIGINAL = "owned-token stable alpha evidence"
CHANGED = "owned-token stable alpha evidence beta-only"
REGRESSION = "stable alpha evidence"
HOLDOUT = "owned-token holdout evidence"
PATH = "fixture/owned-source.txt"


def _reset(monkeypatch, db_path) -> None:
    monkeypatch.setenv("A11OY_RECOVERY_TEST_SEAM", "1")
    monkeypatch.setattr(org_rag, "RAG_DB_PATH", str(db_path))
    monkeypatch.setattr(org_rag, "_GRAPH", org_rag.OrgGraph())
    monkeypatch.setattr(org_rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(org_rag, "_REHYDRATE_ATTEMPTED", False)
    monkeypatch.setattr(org_rag, "_maybe_embedder", lambda load=False: None)


def _run(tmp_path, **overrides):
    kwargs = dict(
        source_path=PATH,
        source_revision="rev-1",
        original_body=ORIGINAL,
        changed_body=CHANGED,
        actor="fixture-actor",
        tenant="fixture-tenant",
        auth_scope="recovery:isolate",
        operation_id="op-stale-1",
        incident_id="inc-stale-1",
        required_tokens=("owned-token",),
        holdout_body=HOLDOUT,
        regression_body=REGRESSION,
        now=1_700_000_000.0,
        anatomy_path=str(tmp_path / "anatomy-recovery.json"),
    )
    kwargs.update(overrides)
    return org_rag.run_stale_index_recovery(**kwargs)


def test_retrieval_source_state_requires_two_digests() -> None:
    original = hashlib.sha256(ORIGINAL.encode()).hexdigest()
    changed = hashlib.sha256(CHANGED.encode()).hexdigest()
    assert org_rag.retrieval_source_state(original, original) == "CURRENT"
    assert org_rag.retrieval_source_state(original, changed) == "STALE"
    assert org_rag.retrieval_source_state(original, None) == "UNBOUND"
    assert org_rag.retrieval_source_state(None, original) == "UNBOUND"
    assert org_rag.retrieval_source_state(original.upper(), changed) == "UNBOUND"
    assert org_rag.retrieval_source_state("", changed) == "UNBOUND"


def test_stale_source_keeps_the_active_generation(monkeypatch, tmp_path) -> None:
    _reset(monkeypatch, tmp_path / "rag.sqlite3")
    result = _run(tmp_path)
    assert result["status"] == "VERIFIED"
    assert result["ok"] is True
    assert result["production_authority"] is False
    assert result["estate_operational"] is False
    assert result["self_improvement"] is False
    assert result["anatomy_display"] == "WRITTEN"
    for state in (
        "OBSERVED", "TRIAGED", "PROPOSED", "ISOLATED", "EVALUATED",
        "APPROVAL_PENDING", "APPLIED", "VERIFIED", "REJECTED",
        "ROLLBACK_REQUIRED", "ROLLED_BACK",
    ):
        assert state in result["states"]
    pinned = result["active_generation_id"]
    served = org_rag.query("owned-token", k=2)
    assert served["generation_id"] == pinned
    assert served["grounded_count"] == 1
    assert served["chunks"][0]["text"].startswith(ORIGINAL)
    assert "beta-only" not in served["chunks"][0]["text"]
    witnessed = org_rag.query("owned-token", k=2, source_witness={PATH: CHANGED})
    assert witnessed["index_stale"] is True
    assert witnessed["source_states"] == ["STALE"]
    assert witnessed["chunks"][0]["source_state"] == "STALE"
    assert witnessed["chunks"][0]["text"].startswith(ORIGINAL)
    assert witnessed["production_authority"] is False
    missed = org_rag.query("beta-only", k=2)
    assert missed["grounded_count"] == 0
    again = _run(tmp_path)
    assert again["status"] == "VERIFIED"
    assert again["active_generation_id"] == pinned
    conn = org_rag._db()
    try:
        active_count = conn.execute(
            "SELECT COUNT(*) AS n FROM org_generations WHERE status='ACTIVE'"
        ).fetchone()["n"]
        candidate = conn.execute(
            "SELECT status FROM org_generations WHERE generation_id=?",
            (result["candidate_id"],),
        ).fetchone()
        revocation = conn.execute(
            "SELECT source_digest FROM org_source_revocations"
        ).fetchone()
    finally:
        conn.close()
    assert active_count == 1
    assert candidate["status"] == "ROLLED_BACK"
    assert revocation is not None
    conn = org_rag._db()
    try:
        conn.execute(
            "UPDATE org_chunks_gen SET sha256=? WHERE generation_id=?",
            (revocation["source_digest"], pinned),
        )
        conn.commit()
    finally:
        conn.close()
    suppressed = org_rag.query("owned-token", k=2)
    assert suppressed["grounded_count"] == 0
    assert suppressed["revoked_suppressed"] >= 1


def test_interrupt_resume_keeps_the_pinned_index(monkeypatch, tmp_path) -> None:
    _reset(monkeypatch, tmp_path / "rag.sqlite3")
    with pytest.raises(org_rag.RecoveryBoundaryInterrupt):
        _run(tmp_path, operation_id="op-interrupt-1", incident_id="inc-interrupt-1",
             crash_after="isolated")
    interrupted = org_rag.query("owned-token", k=2)
    assert interrupted["grounded_count"] == 1
    assert "beta-only" not in interrupted["chunks"][0]["text"]
    resumed = org_rag.resume_stale_index_recovery(
        "op-interrupt-1", actor="fixture-actor", tenant="fixture-tenant",
        now=1_700_000_000.0, anatomy_path=str(tmp_path / "resume.json"),
    )
    assert resumed["status"] == "VERIFIED"
    assert resumed["production_authority"] is False
    assert resumed["active_generation_id"] == interrupted["generation_id"]
    assert "restart_reconciliation" in resumed["demonstrated"]
    served = org_rag.query("beta-only", k=2)
    assert served["grounded_count"] == 0


def test_repeated_regression_holds_without_promotion(monkeypatch, tmp_path) -> None:
    _reset(monkeypatch, tmp_path / "rag.sqlite3")
    result = _run(
        tmp_path, operation_id="op-hold-1", incident_id="inc-hold-1",
        regression_repeats=3, max_attempts=3,
    )
    assert result["status"] == "HELD"
    assert result["production_authority"] is False
    assert "HELD" in result["states"]
    served = org_rag.query("owned-token", k=2)
    assert served["grounded_count"] == 1
    assert "beta-only" not in served["chunks"][0]["text"]


def test_kill_switch_and_deadline_stop(monkeypatch, tmp_path) -> None:
    _reset(monkeypatch, tmp_path / "rag.sqlite3")
    held = _run(tmp_path, operation_id="op-kill-1", incident_id="inc-kill-1", kill_switch=True)
    assert held["status"] == "HELD"
    assert "ISOLATED" not in held["states"]
    cancelled = _run(
        tmp_path, operation_id="op-cancel-1", incident_id="inc-cancel-1", deadline_s=-1,
    )
    assert cancelled["status"] == "CANCELLED"
    assert org_rag.run_stale_index_recovery(
        source_path=PATH, source_revision="rev-1", original_body=ORIGINAL,
        changed_body=CHANGED, actor="", tenant="fixture-tenant", auth_scope="recovery:isolate",
        operation_id="bad id", incident_id="inc-bad-1", required_tokens=("owned-token",),
        holdout_body=HOLDOUT, regression_body=REGRESSION,
    )["status"] == "UNBOUND"
