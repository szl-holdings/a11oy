#!/usr/bin/env python3
"""Exercise the exact live GDW successor without recording bearer material."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen


def request_json(method: str, url: str, *, token: str | None = None, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    payload = kwargs.pop("json", None)
    if kwargs:
        raise TypeError("unsupported request options")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _drain_converged(candidate: dict) -> bool:
    return (
        candidate.get("ok") is True
        and candidate.get("pending_effects") == 0
        and candidate.get("claimed_effects") == 0
        and candidate.get("dead_letter_effects") == 0
    )


def _drain_contract_is_valid(
    drain: dict,
    database_generation_id: str,
) -> bool:
    return (
        drain.get("failed") == 0
        and drain.get("legacy_pending_proofs") == 0
        and drain.get("integrity_ok") is True
        and drain.get("database_generation_id") == database_generation_id
    )


def _global_integrity_is_complete(
    integrity: dict,
    database_generation_id: str,
) -> bool:
    return (
        _drain_converged(integrity)
        and integrity.get("database_generation_id") == database_generation_id
        and integrity.get("journal_mode") == "DELETE"
        and integrity.get("pending_proofs") == 0
        and integrity.get("invalid_effect_bindings") == 0
        and integrity.get("invalid_exported_artifacts") == 0
    )


def _health_is_write_ready(health: dict, database_generation_id: str) -> bool:
    return (
        health.get("status") == "REAL"
        and health.get("write_ready") is True
        and not health.get("write_blockers")
        and (
            (health.get("persistence") or {})
            .get("storage", {})
            .get("database_generation_id")
            == database_generation_id
        )
        and (
            (health.get("persistence") or {})
            .get("drain", {})
            .get("last_outcome")
            == "SUCCEEDED"
        )
    )


def _safe_convergence_state(
    *,
    reason: str,
    health: dict | None,
    drain: dict | None,
    global_integrity: dict | None,
    stable_samples: int,
) -> dict:
    health = health or {}
    persistence = health.get("persistence") or {}
    supervisor = persistence.get("drain") or {}
    drain = drain or {}
    global_integrity = global_integrity or {}
    return {
        "reason": reason,
        "health_status": health.get("status"),
        "write_ready": health.get("write_ready"),
        "write_blockers": health.get("write_blockers"),
        "supervisor_outcome": supervisor.get("last_outcome"),
        "supervisor_attempt_at": supervisor.get("last_attempt_at"),
        "supervisor_success_at": supervisor.get("last_success_at"),
        "supervisor_errors": [
            value
            for value in (
                (supervisor.get("last_report") or {}).get("errors") or []
            )
            if isinstance(value, str)
            and len(value) <= 96
            and all(ch.isalnum() or ch in "_:" for ch in value)
        ],
        "stable_samples": stable_samples,
        "drain_failed": drain.get("failed"),
        "drain_errors": [
            value
            for value in (drain.get("errors") or [])
            if isinstance(value, str)
            and len(value) <= 96
            and all(ch.isalnum() or ch in "_:" for ch in value)
        ],
        "drain_pending_effects": drain.get("pending_effects"),
        "drain_legacy_pending_proofs": drain.get(
            "legacy_pending_proofs"
        ),
        "global_pending_proofs": global_integrity.get("pending_proofs"),
        "global_pending_effects": global_integrity.get("pending_effects"),
        "global_claimed_effects": global_integrity.get("claimed_effects"),
        "global_dead_letter_effects": global_integrity.get(
            "dead_letter_effects"
        ),
        "global_invalid_effect_bindings": global_integrity.get(
            "invalid_effect_bindings"
        ),
        "global_invalid_exported_artifacts": global_integrity.get(
            "invalid_exported_artifacts"
        ),
    }


def _prove_drain_convergence(
    *,
    base: str,
    operator_token: str,
    database_generation_id: str,
    attempts: int = 120,
    delay_seconds: float = 5,
    required_stable_samples: int = 3,
) -> tuple[dict, dict]:
    """Prove a protected drain after the supervised outbox reaches quiescence."""

    drain_url = f"{base}/api/a11oy/v1/gdw/drain?limit=100"
    global_integrity_url = (
        f"{base}/api/a11oy/v1/gdw/integrity/global"
    )
    health_url = f"{base}/api/a11oy/v1/gdw/healthz"
    last_error = "NOT_ATTEMPTED"
    last_health = None
    last_drain = None
    last_global_integrity = None
    last_supervisor_success = None
    stable_samples = 0

    try:
        initial_drain = request_json(
            "POST",
            drain_url,
            token=operator_token,
        )
        last_drain = initial_drain
        last_error = (
            "INITIAL_DRAIN_COMPLETE"
            if _drain_contract_is_valid(
                initial_drain,
                database_generation_id,
            )
            else "INITIAL_DRAIN_INCOMPLETE"
        )
    except Exception as exc:
        last_error = f"INITIAL_DRAIN_{type(exc).__name__}"

    for _attempt in range(1, attempts + 1):
        try:
            health = request_json("GET", health_url)
            last_health = health
            global_integrity = request_json(
                "GET",
                global_integrity_url,
                token=operator_token,
            )
            last_global_integrity = global_integrity
            supervisor_success = str(
                (
                    (health.get("persistence") or {})
                    .get("drain", {})
                    .get("last_success_at")
                    or ""
                )
            )
            if not (
                _health_is_write_ready(health, database_generation_id)
                and _global_integrity_is_complete(
                    global_integrity,
                    database_generation_id,
                )
                and supervisor_success
            ):
                stable_samples = 0
                last_supervisor_success = None
                last_error = "SUPERVISOR_NOT_QUIESCENT"
                time.sleep(delay_seconds)
                continue
            if supervisor_success == last_supervisor_success:
                last_error = "AWAITING_SUCCESSIVE_SUPERVISOR_COMPLETION"
                time.sleep(delay_seconds)
                continue
            last_supervisor_success = supervisor_success
            stable_samples += 1
            if stable_samples < required_stable_samples:
                last_error = "AWAITING_STABLE_SUPERVISOR_SAMPLES"
                time.sleep(delay_seconds)
                continue

            confirmed_drain = request_json(
                "POST",
                drain_url,
                token=operator_token,
            )
            last_drain = confirmed_drain
            if _drain_contract_is_valid(
                confirmed_drain,
                database_generation_id,
            ):
                confirmed_integrity = request_json(
                    "GET",
                    global_integrity_url,
                    token=operator_token,
                )
                last_global_integrity = confirmed_integrity
                if _global_integrity_is_complete(
                    confirmed_integrity,
                    database_generation_id,
                ):
                    return confirmed_drain, confirmed_integrity
            last_error = "CONFIRMATION_DRAIN_INCOMPLETE"
            stable_samples = 0
            last_supervisor_success = None
        except Exception as exc:
            last_error = f"CONVERGENCE_{type(exc).__name__}"
            stable_samples = 0
            last_supervisor_success = None
        time.sleep(delay_seconds)

    safe_state = _safe_convergence_state(
        reason=last_error,
        health=last_health,
        drain=last_drain,
        global_integrity=last_global_integrity,
        stable_samples=stable_samples,
    )
    raise RuntimeError(
        "GDW protected drain did not converge: "
        + json.dumps(safe_state, sort_keys=True)
    )


def _session_sha256(session: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            session,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def prove_restart(
    *,
    api,
    repo_id: str,
    base: str,
    source_sha: str,
    operator_token: str,
    attempts: int = 120,
    delay_seconds: float = 5,
) -> dict:
    """Restart the Space and prove GDW state and artifacts survived."""

    health_url = f"{base}/api/a11oy/v1/gdw/healthz"
    global_integrity_url = (
        f"{base}/api/a11oy/v1/gdw/integrity/global"
    )
    owner_integrity_url = f"{base}/api/a11oy/v1/gdw/integrity"
    session_url = (
        f"{base}/api/a11oy/v1/gdw/sessions/protected-promotion"
    )
    before_health = request_json("GET", health_url)
    before_global = request_json(
        "GET",
        global_integrity_url,
        token=operator_token,
    )
    before_session = request_json(
        "GET",
        session_url,
        token=operator_token,
    )
    before_persistence = before_health.get("persistence") or {}
    before_storage = before_persistence.get("storage") or {}
    database_generation_id = before_storage.get("database_generation_id")
    before_prepared_at = str(
        before_persistence.get("prepared_at") or ""
    )
    if (
        not before_prepared_at
        or not _health_is_write_ready(
            before_health,
            database_generation_id,
        )
        or not _global_integrity_is_complete(
            before_global,
            database_generation_id,
        )
        or before_session.get("database_generation_id")
        != database_generation_id
    ):
        raise RuntimeError("GDW pre-restart contract is incomplete")
    before_session_sha256 = _session_sha256(before_session)

    restart = api.restart_space(repo_id=repo_id, factory_reboot=False)
    stage = getattr(getattr(restart, "runtime", None), "stage", None)
    stage = getattr(stage, "value", stage)
    time.sleep(max(10, delay_seconds))

    after_health = None
    last_error = "NOT_OBSERVED"
    for _attempt in range(1, attempts + 1):
        try:
            build_info = request_json("GET", f"{base}/api/build-info")
            revision = str(
                (build_info.get("build") or {}).get("revision") or ""
            ).lower()
            candidate = request_json("GET", health_url)
            persistence = candidate.get("persistence") or {}
            storage = persistence.get("storage") or {}
            if (
                revision == source_sha
                and str(persistence.get("prepared_at") or "")
                and persistence.get("prepared_at") != before_prepared_at
                and storage.get("database_generation_id")
                == database_generation_id
            ):
                after_health = candidate
                break
            last_error = "RESTART_IDENTITY_NOT_CHANGED"
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(delay_seconds)
    if after_health is None:
        raise RuntimeError(
            f"GDW restart was not observed: {last_error}"
        )

    _drain, after_global = _prove_drain_convergence(
        base=base,
        operator_token=operator_token,
        database_generation_id=database_generation_id,
        attempts=attempts,
        delay_seconds=delay_seconds,
    )
    after_owner = request_json(
        "GET",
        owner_integrity_url,
        token=operator_token,
    )
    after_session = request_json(
        "GET",
        session_url,
        token=operator_token,
    )
    after_session_sha256 = _session_sha256(after_session)
    if (
        after_owner.get("ok") is not True
        or after_owner.get("database_generation_id")
        != database_generation_id
        or after_owner.get("journal_mode") != "DELETE"
        or after_owner.get("pending_effects") != 0
        or after_owner.get("invalid_effect_bindings") != 0
        or after_owner.get("invalid_exported_artifacts") != 0
        or after_session.get("database_generation_id")
        != database_generation_id
        or after_session_sha256 != before_session_sha256
    ):
        raise RuntimeError("GDW post-restart persistence contract failed")

    return {
        "schema": "szl.hf-gdw-restart-proof/v1",
        "restart_requested": True,
        "restart_response_stage": str(stage or "UNKNOWN"),
        "source_revision": source_sha,
        "database_generation_id": database_generation_id,
        "before_prepared_at": before_prepared_at,
        "after_prepared_at": (
            (after_health.get("persistence") or {}).get("prepared_at")
        ),
        "session_sha256": after_session_sha256,
        "global_integrity": {
            "ok": True,
            "pending_proofs": after_global["pending_proofs"],
            "pending_effects": after_global["pending_effects"],
            "claimed_effects": after_global["claimed_effects"],
            "dead_letter_effects": after_global[
                "dead_letter_effects"
            ],
            "invalid_effect_bindings": after_global[
                "invalid_effect_bindings"
            ],
            "invalid_exported_artifacts": after_global[
                "invalid_exported_artifacts"
            ],
        },
        "credential_values_recorded": False,
    }


def prove(*, origin: str, source_sha: str, operator_token: str) -> dict:
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise RuntimeError("source SHA must be canonical lowercase hexadecimal")
    if len(operator_token.encode("utf-8")) < 32:
        raise RuntimeError("GDW_OPERATOR_TOKEN is unavailable")
    base = origin.rstrip("/")
    health = None
    deployed_revision = ""
    last_error = None
    for attempt in range(1, 121):
        try:
            build_info = request_json("GET", f"{base}/api/build-info")
            deployed_revision = str(
                (build_info.get("build") or {}).get("revision") or ""
            ).lower()
            if deployed_revision != source_sha:
                last_error = "SOURCE_REVISION_MISMATCH"
                time.sleep(5)
                continue
            candidate = request_json(
                "GET", f"{base}/api/a11oy/v1/gdw/healthz"
            )
            if (
                candidate.get("status") == "REAL"
                and candidate.get("write_ready") is True
                and (
                    (candidate.get("persistence") or {})
                    .get("storage", {})
                    .get("journal_mode_observed")
                    == "DELETE"
                )
            ):
                health = candidate
                break
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(5)
    if health is None:
        raise RuntimeError(f"GDW health did not converge: {last_error}")

    request_id = f"promotion-{source_sha[:32]}"
    step = request_json(
        "POST",
        f"{base}/api/a11oy/v1/gdw/step",
        token=operator_token,
        headers={"X-Request-Id": request_id},
        json={
            "session_id": "protected-promotion",
            "request": "verify durable governed successor",
            "allowed_experts": ["planner", "auditor", "verifier"],
            "risk_budget": 0.1,
            "mode_hint": "auto",
            "dry_run": False,
        },
    )
    if (
        step.get("decision") != "ACCEPT"
        or step.get("receipt_status") != "UNSIGNED_ATOMIC"
        or step.get("proof", {}).get("status") != "OUTBOX_PENDING"
        or step.get("database_generation_id")
        != (health.get("persistence") or {})
        .get("storage", {})
        .get("database_generation_id")
    ):
        raise RuntimeError("GDW protected transition contract failed")

    database_generation_id = (
        (health.get("persistence") or {})
        .get("storage", {})
        .get("database_generation_id")
    )
    if (
        not isinstance(database_generation_id, str)
        or len(database_generation_id) != 32
        or any(
            ch not in "0123456789abcdef"
            for ch in database_generation_id
        )
    ):
        raise RuntimeError("GDW database generation is not canonical")
    drain, global_integrity = _prove_drain_convergence(
        base=base,
        operator_token=operator_token,
        database_generation_id=database_generation_id,
    )
    integrity = request_json(
        "GET",
        f"{base}/api/a11oy/v1/gdw/integrity",
        token=operator_token,
    )
    session = request_json(
        "GET",
        f"{base}/api/a11oy/v1/gdw/sessions/protected-promotion",
        token=operator_token,
    )
    if (
        integrity.get("ok") is not True
        or integrity.get("journal_mode") != "DELETE"
        or session.get("database_generation_id")
        != (health.get("persistence") or {})
        .get("storage", {})
        .get("database_generation_id")
    ):
        raise RuntimeError("GDW live persistence contract failed")

    return {
        "schema": "szl.hf-gdw-live-proof/v1",
        "source_revision": source_sha,
        "runtime_source_revision": deployed_revision,
        "health": health,
        "transition": {
            "decision": step["decision"],
            "receipt_status": step["receipt_status"],
            "proof_status": step["proof"]["status"],
            "replayed": bool(step.get("replayed")),
        },
        "drain": drain,
        "global_integrity": {
            "ok": True,
            "journal_mode": global_integrity["journal_mode"],
            "pending_proofs": global_integrity["pending_proofs"],
            "pending_effects": global_integrity["pending_effects"],
            "claimed_effects": global_integrity["claimed_effects"],
            "dead_letter_effects": global_integrity["dead_letter_effects"],
            "invalid_effect_bindings": global_integrity[
                "invalid_effect_bindings"
            ],
            "invalid_exported_artifacts": global_integrity[
                "invalid_exported_artifacts"
            ],
        },
        "integrity": {
            "ok": True,
            "journal_mode": integrity["journal_mode"],
            "pending_effects": integrity["pending_effects"],
            "invalid_effect_bindings": integrity[
                "invalid_effect_bindings"
            ],
            "invalid_exported_artifacts": integrity[
                "invalid_exported_artifacts"
            ],
        },
        "credential_values_recorded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output")
    parser.add_argument("--restart-repo-id")
    args = parser.parse_args()
    report = prove(
        origin=args.origin,
        source_sha=args.source_sha,
        operator_token=os.environ.get("GDW_OPERATOR_TOKEN", ""),
    )
    if args.restart_repo_id:
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            raise RuntimeError("HF_TOKEN is unavailable for restart proof")
        from huggingface_hub import HfApi

        report["restart"] = prove_restart(
            api=HfApi(token=hf_token),
            repo_id=args.restart_repo_id,
            base=args.origin.rstrip("/"),
            source_sha=args.source_sha,
            operator_token=os.environ.get("GDW_OPERATOR_TOKEN", ""),
        )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
