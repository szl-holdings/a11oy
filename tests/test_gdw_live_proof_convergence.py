from __future__ import annotations

from scripts import prove_hf_gdw_runtime


def test_live_proof_waits_for_supervisor_claim_to_converge(monkeypatch) -> None:
    source_sha = "a" * 40
    database_generation_id = "b" * 32
    integrity_reads = 0
    health_reads = 0

    def request_json(method, url, **_kwargs):
        nonlocal health_reads, integrity_reads
        if url.endswith("/api/build-info"):
            return {"build": {"revision": source_sha}}
        if url.endswith("/gdw/healthz"):
            health_reads += 1
            return {
                "status": "REAL",
                "write_ready": True,
                "write_blockers": [],
                "persistence": {
                    "storage": {
                        "journal_mode_observed": "DELETE",
                        "database_generation_id": database_generation_id,
                    },
                    "drain": {
                        "last_outcome": "SUCCEEDED",
                        "last_attempt_at": f"attempt-{health_reads}",
                        "last_success_at": f"success-{health_reads}",
                    },
                },
            }
        if method == "POST" and url.endswith("/gdw/step"):
            assert _kwargs["json"]["session_id"] == (
                f"protected-promotion-{source_sha[:16]}"
            )
            return {
                "decision": "ACCEPT",
                "receipt_status": "UNSIGNED_ATOMIC",
                "proof": {"status": "OUTBOX_PENDING"},
                "database_generation_id": database_generation_id,
            }
        if method == "POST" and "/gdw/drain" in url:
            return {
                "failed": 0,
                "pending_effects": 1,
                "legacy_pending_proofs": 0,
                "integrity_ok": True,
                "database_generation_id": database_generation_id,
            }
        if method == "GET" and url.endswith("/gdw/integrity/global"):
            integrity_reads += 1
            pending = 1 if integrity_reads == 1 else 0
            return {
                "ok": True,
                "database_generation_id": database_generation_id,
                "journal_mode": "DELETE",
                "pending_proofs": 0,
                "pending_effects": pending,
                "claimed_effects": pending,
                "dead_letter_effects": 0,
                "invalid_effect_bindings": 0,
                "invalid_exported_artifacts": 0,
            }
        if method == "GET" and url.endswith("/gdw/integrity"):
            return {
                "ok": True,
                "database_generation_id": database_generation_id,
                "journal_mode": "DELETE",
                "pending_proofs": 0,
                "pending_effects": 0,
                "claimed_effects": 0,
                "dead_letter_effects": 0,
                "invalid_effect_bindings": 0,
                "invalid_exported_artifacts": 0,
            }
        if method == "GET" and url.endswith(
            "/gdw/sessions/protected-promotion-aaaaaaaaaaaaaaaa"
        ):
            return {"database_generation_id": database_generation_id}
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(
        prove_hf_gdw_runtime,
        "request_json",
        request_json,
    )
    monkeypatch.setattr(prove_hf_gdw_runtime.time, "sleep", lambda _seconds: None)

    report = prove_hf_gdw_runtime.prove(
        origin="https://example.invalid",
        source_sha=source_sha,
        operator_token="operator-token-with-at-least-32-bytes",
    )

    assert integrity_reads == 5
    assert health_reads == 5
    assert report["drain"]["pending_effects"] == 1
    assert report["integrity"]["pending_effects"] == 0


def test_dead_letter_effect_is_not_terminal_convergence() -> None:
    assert prove_hf_gdw_runtime._drain_converged(
        {
            "ok": True,
            "pending_effects": 0,
            "claimed_effects": 0,
            "dead_letter_effects": 1,
        }
    ) is False
