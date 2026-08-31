from __future__ import annotations

import gdw_runtime
from routers import gdw_frontier


def test_supervisor_does_not_report_success_with_pending_effects(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gdw_runtime,
        "_STATE",
        {
            "startup_state": "READY",
            "evidence_label": "VERIFIED",
            "storage": {"database_generation_id": "a" * 32},
            "drain": {
                "enabled": False,
                "running": False,
                "last_outcome": "NOT_RUN",
            },
        },
    )
    monkeypatch.setattr(
        gdw_runtime,
        "drain_once",
        lambda **_kwargs: {
            "attempted": 0,
            "exported": 0,
            "failed": 0,
            "pending_effects": 8,
            "dead_letter_effects": 0,
            "legacy_pending_proofs": 0,
            "sqlite_integrity": "ok",
            "invalid_effect_bindings": 0,
            "invalid_exported_artifacts": 0,
            "errors": [],
        },
    )
    supervisor = gdw_runtime.OutboxSupervisor(
        enabled=True,
        interval_seconds=5,
        retry_max_seconds=60,
        batch_size=10,
        lease_seconds=30,
    )
    waits = iter((False, True))
    observed_delays = []

    def wait(_self, delay):
        observed_delays.append(delay)
        return next(waits)

    supervisor._stop = type(
        "TwoPassStop",
        (),
        {"wait": wait},
    )()

    supervisor._run()
    drain = gdw_runtime.runtime_health()["drain"]

    assert drain["last_outcome"] == "RETRY_SCHEDULED"
    assert drain["last_error"] == "bounded drain pass remains non-quiescent"
    assert drain["success_run_generation_id"] is None
    assert observed_delays == [0, 5]


def test_public_health_exposes_only_sanitized_drain_report() -> None:
    public = gdw_frontier._public_runtime_health(
        {
            "drain": {
                "last_outcome": "RETRY_SCHEDULED",
                "last_report": {
                    "attempted": 1,
                    "exported": 0,
                    "failed": 1,
                    "pending_effects": 8,
                    "legacy_pending_proofs": 0,
                    "sqlite_integrity": "ok",
                    "errors": ["proof_export:ValueError"],
                    "worker_id": "private-worker",
                    "payload": {"secret": "never-publish"},
                },
            }
        }
    )

    report = public["drain"]["last_report"]
    assert report["pending_effects"] == 8
    assert report["errors"] == ["proof_export:ValueError"]
    assert "worker_id" not in report
    assert "payload" not in report
