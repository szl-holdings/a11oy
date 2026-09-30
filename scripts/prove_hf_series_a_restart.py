#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Prove A11oy signer and receipt identity across an actual Space restart."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import hf_live_proof_bounds as bounds  # noqa: E402
from hf_live_proof_bounds import ProofBoundaryError  # noqa: E402

HfApi = Any  # the proof never constructs huggingface_hub.HfApi; see ScopedSpaceControl


SCHEMA = "szl.series-a-restart-proof/v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STORE_ID = re.compile(r"^store_[0-9a-f]{32}$")
BOOT_ID = re.compile(r"^boot_[0-9a-f]{32}$")
RECEIPT_HASH = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_SIGNER = "persistent:env:SZL_COSIGN_PRIVATE_PEM"
EXPECTED_DATABASE = "/data/a11oy/series-a/control-plane-v2.sqlite3"
# Proof-wide deadline: two stop-the-world restarts (activation + durability)
# share one clock. 20 minutes equals the reviewed deploy wait-running bound;
# callers may lower it, never raise it. Transient admission retries are capped
# separately at bounds.MAX_ATTEMPTS inside bounds.RETRY_WINDOW_SECONDS.
DEFAULT_DEADLINE_SECONDS = 20 * 60
MAX_DEADLINE_SECONDS = 20 * 60
MAX_POLL_ATTEMPTS = 90
MAX_RETRY_SECONDS = 30


class RestartProofError(RuntimeError):
    """The restarted runtime did not preserve the required identity.

    Messages are fixed literals authored here; reports carry only ``code``.
    """

    def __init__(self, message: str, *, code: str = "RESTART_CONTRACT_FAILED") -> None:
        super().__init__(message)
        self.code = code if code in bounds.DIAGNOSTIC_CODES else "RESTART_CONTRACT_FAILED"


def _code(error: BaseException | None) -> str:
    """Fixed diagnostic for an exception; provider text is never returned."""

    if error is None:
        return "NOT_OBSERVED"
    return bounds.diagnostic_code(error, "UNEXPECTED_FAILURE")


def _reraise_hard(error: BaseException) -> None:
    """Destination, redirect, scope and deadline failures are never polled past."""

    if bounds.is_hard_failure(error):
        raise error


class HttpResponse:
    """Minimal response surface; error bodies are never read or retained."""

    def __init__(self, url: str, status: int, content: bytes) -> None:
        self.url = url
        self.status = status
        self.content = content

    def raise_for_status(self) -> None:
        if not 200 <= self.status < 300:
            raise RestartProofError(
                "live endpoint returned a non-success status",
                code="HTTP_STATUS_REJECTED",
            )

    def json(self) -> Any:
        return json.loads(self.content)


class HttpSession:
    """Public-origin reader routed through the bounded no-redirect transport.

    Only ``CANONICAL_ORIGIN`` is reachable (``bounds.check_destination``); any
    3xx is a hard ``REDIRECT_REJECTED``; 429/502/503/504 are retried inside the
    capped budget; every other non-2xx status becomes an empty response whose
    body was never read, so provider text cannot reach evidence.
    """

    def __init__(self, transport: bounds.BoundedTransport | None = None) -> None:
        self.headers: dict[str, str] = {}
        self._transport = transport or bounds.BoundedTransport()

    def _request(self, method: str, url: str, *, timeout: float) -> HttpResponse:
        del timeout  # the transport derives per-request timeouts from its deadline
        try:
            status, content = self._transport.request(
                method, url, headers=self.headers, expect_json=False,
            )
        except ProofBoundaryError as exc:
            if exc.code in {"HTTP_STATUS_REJECTED", "TRANSIENT_RETRY_EXHAUSTED"}:
                return HttpResponse(url=url, status=int(exc.http_status or 0), content=b"")
            raise
        return HttpResponse(url=url, status=status, content=content)

    def get(self, url: str, *, timeout: float) -> HttpResponse:
        return self._request("GET", url, timeout=timeout)


def normalize_origin(value: str) -> str:
    """Admit exactly ``CANONICAL_ORIGIN``; hostnames are compared exactly."""

    raw = str(value or "")
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise RestartProofError(
            "origin must be a credential-free HTTPS origin",
            code="DESTINATION_REJECTED",
        )
    if raw.rstrip("/") != bounds.CANONICAL_ORIGIN or raw.count("/") > 3:
        raise RestartProofError(
            "origin is not the canonical A11oy Space origin",
            code="DESTINATION_REJECTED",
        )
    return bounds.CANONICAL_ORIGIN


def _json(response: HttpResponse) -> Mapping[str, Any]:
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, Mapping):
        raise RestartProofError(
            "live endpoint did not return a JSON object", code="RESPONSE_NOT_JSON"
        )
    return value


def _remaining_timeout(deadline: float, maximum: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RestartProofError(
            "restart proof deadline exhausted", code="DEADLINE_EXHAUSTED"
        )
    return max(0.1, min(maximum, remaining))


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise RestartProofError(
            "restart proof deadline exhausted", code="DEADLINE_EXHAUSTED"
        )


def _sleep_with_deadline(deadline: float, seconds: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RestartProofError(
            "restart proof deadline exhausted", code="DEADLINE_EXHAUSTED"
        )
    time.sleep(min(max(0.0, seconds), remaining))
    _check_deadline(deadline)



def _runtime_stage(value: Any) -> str:
    """Normalize huggingface_hub SpaceRuntime and SpaceInfo stage shapes."""

    candidate = value
    if isinstance(candidate, Mapping):
        candidate = candidate.get("runtime", candidate)
        stage = candidate.get("stage") if isinstance(candidate, Mapping) else None
    else:
        nested = getattr(candidate, "runtime", None)
        candidate = nested if nested is not None else candidate
        stage = getattr(candidate, "stage", None)
    stage = getattr(stage, "value", stage)
    return str(stage or "UNKNOWN").strip().upper()


def stop_the_world_restart(
    api: HfApi,
    *,
    repo_id: str,
    deadline: float,
    attempts: int,
    retry_seconds: int,
    phase: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pause to zero writers, confirm PAUSED, then start one replacement runtime.

    A direct restart may overlap a retiring and replacement replica. That is not
    admissible for a single-writer SQLite receipt chain on a mounted provider
    filesystem. This transition proves the old runtime is PAUSED before any new
    runtime is requested. If the restart response is lost, provider stage is
    inspected before a retry so an accepted request is never duplicated blindly.
    """

    if attempts < 1 or retry_seconds < 0:
        raise RestartProofError("stop-the-world polling bounds are invalid")
    # Effect scope: the only Space this proof may pause/restart.
    bounds.require_canonical_space(repo_id)
    record: dict[str, Any] = {
        "phase": phase,
        "pause_requested": False,
        "pause_confirmed": False,
        "pause_observations": [],
        "restart_requested": False,
        "restart_response_lost": False,
        "restart_retry_requested": False,
        "writer_overlap_prevented": False,
    }
    if evidence is not None:
        evidence[f"{phase}_restart_control"] = record

    _check_deadline(deadline)
    try:
        paused = api.pause_space(repo_id=repo_id)
    except Exception as exc:  # noqa: BLE001 - provider error is receipt evidence
        _reraise_hard(exc)
        record["pause_error"] = {
            "type": type(exc).__name__,
            "message": _code(exc),
        }
        raise RestartProofError(
            f"{phase} pause request failed: {type(exc).__name__}: {_code(exc)}"
        ) from exc
    record["pause_requested"] = True
    pause_stage = _runtime_stage(paused)
    record["pause_response_stage"] = pause_stage
    confirmed = pause_stage == "PAUSED"
    last_stage = pause_stage

    for attempt in range(max(1, attempts)):
        if confirmed:
            break
        _check_deadline(deadline)
        try:
            runtime = api.get_space_runtime(repo_id=repo_id)
            last_stage = _runtime_stage(runtime)
            record["pause_observations"].append(
                {"attempt": attempt + 1, "stage": last_stage}
            )
            confirmed = last_stage == "PAUSED"
        except Exception as exc:  # noqa: BLE001 - bounded provider polling
            _reraise_hard(exc)
            record["pause_observations"].append(
                {
                    "attempt": attempt + 1,
                    "stage": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": _code(exc),
                }
            )
        if not confirmed and attempt + 1 < max(1, attempts):
            _sleep_with_deadline(deadline, retry_seconds)

    if not confirmed:
        raise RestartProofError(
            f"{phase} runtime did not reach PAUSED before replacement request; "
            f"last stage={last_stage}"
        )
    record["pause_confirmed"] = True
    record["confirmed_pause_stage"] = "PAUSED"
    _check_deadline(deadline)

    try:
        restarted = api.restart_space(repo_id=repo_id, factory_reboot=False)
        record["restart_requested"] = True
        restart_stage = _runtime_stage(restarted)
    except Exception as exc:  # noqa: BLE001 - recover availability without overlap
        _reraise_hard(exc)
        record["restart_response_lost"] = True
        record["restart_error"] = {
            "type": type(exc).__name__,
            "message": _code(exc),
        }
        _check_deadline(deadline)
        try:
            runtime = api.get_space_runtime(repo_id=repo_id)
            observed_stage = _runtime_stage(runtime)
        except Exception as runtime_exc:  # noqa: BLE001
            _reraise_hard(runtime_exc)
            record["restart_failure_runtime_error"] = {
                "type": type(runtime_exc).__name__,
                "message": _code(runtime_exc),
            }
            raise RestartProofError(
                f"{phase} restart response was lost and runtime state is unavailable"
            ) from runtime_exc
        record["restart_failure_runtime_stage"] = observed_stage
        if observed_stage == "PAUSED":
            record["restart_retry_requested"] = True
            try:
                restarted = api.restart_space(
                    repo_id=repo_id,
                    factory_reboot=False,
                )
            except Exception as retry_exc:  # noqa: BLE001
                _reraise_hard(retry_exc)
                raise RestartProofError(
                    f"{phase} restart failed after confirmed pause: "
                    f"{type(retry_exc).__name__}: {_code(retry_exc)}"
                ) from retry_exc
            record["restart_requested"] = True
            restart_stage = _runtime_stage(restarted)
        else:
            # The provider no longer reports PAUSED, so the first request may
            # have been accepted. Do not issue a duplicate restart; the later
            # public boot-ID proof decides whether the transition completed.
            record["restart_requested"] = True
            restart_stage = observed_stage

    record["restart_response_stage"] = restart_stage
    record["writer_overlap_prevented"] = True
    _check_deadline(deadline)
    return record


def capture(
    session: HttpSession,
    origin: str,
    expected_source: str,
    deadline: float | None = None,
) -> dict[str, Any]:
    if deadline is None:
        deadline = time.monotonic() + DEFAULT_DEADLINE_SECONDS
    status = _json(
        session.get(
            origin + "/api/a11oy/v1/series-a/status",
            timeout=_remaining_timeout(deadline, 45),
        )
    )
    _check_deadline(deadline)
    build = _json(
        session.get(
            origin + "/api/build-info",
            timeout=_remaining_timeout(deadline, 45),
        )
    )
    _check_deadline(deadline)
    key = session.get(
        origin + "/api/a11oy/v1/series-a/public-key",
        timeout=_remaining_timeout(deadline, 45),
    )
    _check_deadline(deadline)
    key.raise_for_status()
    storage = status.get("storage")
    build_record = build.get("build")
    if (
        status.get("schema") != "szl.series-a-status/v1"
        or str(status.get("source_revision") or "").lower() != expected_source
        or status.get("signing_key_source") != EXPECTED_SIGNER
        or status.get("database") != EXPECTED_DATABASE
        or BOOT_ID.fullmatch(str(status.get("runtime_boot_id") or "")) is None
        or not isinstance(storage, Mapping)
        or storage.get("persistence_required") is not True
        or storage.get("required_mount") != "/data"
        or storage.get("mount_verified") is not True
        or storage.get("journal_mode") != "DELETE"
        or STORE_ID.fullmatch(str(storage.get("instance_id") or "")) is None
        or not isinstance(storage.get("created_at"), str)
        or not storage.get("created_at")
        or not isinstance(storage.get("receipt_count"), int)
        or isinstance(storage.get("receipt_count"), bool)
        or storage.get("receipt_count") < 0
        or not isinstance(build_record, Mapping)
        or str(build_record.get("revision") or "").lower() != expected_source
        or key.content.count(b"-----BEGIN PUBLIC KEY-----") != 1
        or key.content.count(b"-----END PUBLIC KEY-----") != 1
    ):
        raise RestartProofError(
            "live source, signer, or persistent storage contract is incomplete"
        )
    chain_head = storage.get("chain_head")
    if storage["receipt_count"] > 0:
        if RECEIPT_HASH.fullmatch(str(chain_head or "")) is None:
            raise RestartProofError("non-empty receipt chain lacks a valid head")
    elif chain_head is not None:
        raise RestartProofError("empty receipt chain unexpectedly has a head")
    return {
        "source_revision": expected_source,
        "runtime_boot_id": status["runtime_boot_id"],
        "signing_key_source": status["signing_key_source"],
        "public_key_sha256": hashlib.sha256(key.content).hexdigest(),
        "database": status["database"],
        "storage": {
            "instance_id": storage["instance_id"],
            "created_at": storage.get("created_at"),
            "receipt_count": storage["receipt_count"],
            "last_receipt_sequence": storage.get("last_receipt_sequence"),
            "chain_head": chain_head,
            "mount_verified": storage["mount_verified"],
            "journal_mode": storage["journal_mode"],
        },
    }


def observe_boot_id(
    session: HttpSession,
    origin: str,
    deadline: float,
) -> str | None:
    """Observe the current boot identity even when its contract is unavailable."""

    status = _json(
        session.get(
            origin + "/api/a11oy/v1/series-a/status",
            timeout=_remaining_timeout(deadline, 45),
        )
    )
    _check_deadline(deadline)
    boot_id = str(status.get("runtime_boot_id") or "")
    return boot_id if BOOT_ID.fullmatch(boot_id) is not None else None


def await_capture(
    session: HttpSession,
    origin: str,
    expected_source: str,
    deadline: float,
    *,
    attempts: int,
    retry_seconds: int,
    context: str,
    previous_boot_id: str | None = None,
) -> dict[str, Any]:
    """Poll until the restarted public runtime exposes the required contract."""

    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            candidate = capture(session, origin, expected_source, deadline)
            if (
                previous_boot_id is not None
                and candidate["runtime_boot_id"] == previous_boot_id
            ):
                raise RestartProofError(
                    "activation restart boot identity did not change"
                )
            return candidate
        except Exception as exc:  # noqa: BLE001 - bounded runtime polling
            _reraise_hard(exc)
            last_error = exc
            if attempt + 1 < max(1, attempts):
                _sleep_with_deadline(deadline, retry_seconds)
    raise RestartProofError(
        f"{context}: {type(last_error).__name__}: {_code(last_error)}"
    )


def validate_continuity(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    if before.get("source_revision") != after.get("source_revision"):
        raise RestartProofError("source revision changed across restart")
    if before.get("signing_key_source") != after.get("signing_key_source"):
        raise RestartProofError("signing source changed across restart")
    if before.get("public_key_sha256") != after.get("public_key_sha256"):
        raise RestartProofError("public signing identity changed across restart")
    if before.get("database") != after.get("database"):
        raise RestartProofError("database path changed across restart")
    before_storage = before.get("storage")
    after_storage = after.get("storage")
    if not isinstance(before_storage, Mapping) or not isinstance(
        after_storage, Mapping
    ):
        raise RestartProofError("storage evidence is absent")
    if before_storage.get("instance_id") != after_storage.get("instance_id"):
        raise RestartProofError("database instance changed across restart")
    if before_storage.get("created_at") != after_storage.get("created_at"):
        raise RestartProofError("database creation identity changed across restart")
    if int(after_storage.get("receipt_count") or 0) < int(
        before_storage.get("receipt_count") or 0
    ):
        raise RestartProofError("receipt count regressed across restart")
    if int(after_storage.get("last_receipt_sequence") or 0) < int(
        before_storage.get("last_receipt_sequence") or 0
    ):
        raise RestartProofError("receipt sequence regressed across restart")


def validate_restart(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    receipt_hashes: set[str],
) -> None:
    validate_continuity(before, after)
    if before.get("runtime_boot_id") == after.get("runtime_boot_id"):
        raise RestartProofError("runtime boot identity did not change across restart")
    if (
        BOOT_ID.fullmatch(str(before.get("runtime_boot_id") or "")) is None
        or BOOT_ID.fullmatch(str(after.get("runtime_boot_id") or "")) is None
    ):
        raise RestartProofError("runtime boot identity evidence is invalid")
    before_storage = before.get("storage")
    if not isinstance(before_storage, Mapping):
        raise RestartProofError("pre-restart storage evidence is absent")
    previous_head = before_storage.get("chain_head")
    if previous_head and previous_head not in receipt_hashes:
        raise RestartProofError("pre-restart receipt-chain head was not recovered")


def recovery_capture(
    payload: Mapping[str, Any],
    *,
    expected_source: str,
    expected_head: str,
    expected_sequence: int,
) -> dict[str, Any]:
    if payload.get("schema") != "szl.series-a-receipt-recovery/v1":
        raise RestartProofError("exact receipt recovery schema is invalid")
    if str(payload.get("source_revision") or "").lower() != expected_source:
        raise RestartProofError("exact receipt recovery source is invalid")
    if payload.get("signing_key_source") != EXPECTED_SIGNER:
        raise RestartProofError("exact receipt recovery signer is invalid")
    if RECEIPT_HASH.fullmatch(
        str(payload.get("public_key_sha256") or "")
    ) is None:
        raise RestartProofError("exact receipt recovery key hash is invalid")
    storage = payload.get("storage")
    item = payload.get("item")
    if not isinstance(storage, Mapping) or not isinstance(item, Mapping):
        raise RestartProofError("exact receipt recovery record is incomplete")
    if item.get("receipt_hash") != expected_head:
        raise RestartProofError("exact receipt recovery returned the wrong hash")
    if item.get("sequence") != expected_sequence:
        raise RestartProofError(
            "recovered receipt sequence does not match the pre-restart head"
        )
    envelope = item.get("envelope")
    if not isinstance(envelope, Mapping):
        raise RestartProofError("recovered receipt envelope is absent")
    envelope_hash = hashlib.sha256(
        json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if envelope_hash != expected_head:
        raise RestartProofError(
            "recovered receipt envelope does not match its hash"
        )
    return {
        "source_revision": expected_source,
        "runtime_boot_id": payload.get("runtime_boot_id"),
        "signing_key_source": payload.get("signing_key_source"),
        "public_key_sha256": payload.get("public_key_sha256"),
        "database": payload.get("database"),
        "storage": dict(storage),
    }


def recovery_response_evidence(response: HttpResponse) -> dict[str, Any]:
    """Return the secret-free storage identity exposed by exact recovery."""

    captured: dict[str, Any] = {"http_status": response.status}
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 - evidence remains bounded and optional
        return captured
    if not isinstance(payload, Mapping):
        return captured
    for key in (
        "schema",
        "source_revision",
        "runtime_boot_id",
        "database",
        "queried_receipt_hash",
    ):
        value = payload.get(key)
        if isinstance(value, (str, int, bool)) or value is None:
            captured[key] = value
    storage = payload.get("storage")
    if isinstance(storage, Mapping):
        captured["storage"] = dict(storage)
    return captured


def capture_pre_restart_receipt(
    session: HttpSession,
    origin: str,
    source_sha: str,
    before: Mapping[str, Any],
    deadline: float,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before_storage = before.get("storage")
    if not isinstance(before_storage, Mapping):
        raise RestartProofError("pre-restart storage evidence is absent")
    expected_head = str(before_storage.get("chain_head") or "")
    expected_sequence = before_storage.get("last_receipt_sequence")
    if (
        RECEIPT_HASH.fullmatch(expected_head) is None
        or not isinstance(expected_sequence, int)
        or isinstance(expected_sequence, bool)
        or expected_sequence < 1
    ):
        raise RestartProofError("pre-restart receipt head evidence is invalid")
    response = session.get(
        origin
        + "/api/a11oy/v1/series-a/receipts?"
        + urlencode({"receipt_hash": expected_head}),
        timeout=_remaining_timeout(deadline, 60),
    )
    if evidence is not None:
        evidence["pre_restart_exact_recovery_attempt"] = (
            recovery_response_evidence(response)
        )
    payload = _json(response)
    captured = recovery_capture(
        payload,
        expected_source=source_sha,
        expected_head=expected_head,
        expected_sequence=expected_sequence,
    )
    if captured.get("runtime_boot_id") != before.get("runtime_boot_id"):
        raise RestartProofError(
            "pre-restart exact receipt came from a different runtime"
        )
    validate_continuity(before, captured)
    return captured


def await_receipt_recovery(
    session: HttpSession,
    origin: str,
    source_sha: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    deadline: float,
    *,
    attempts: int,
    retry_seconds: int,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before_storage = before.get("storage")
    if not isinstance(before_storage, Mapping):
        raise RestartProofError("pre-restart storage evidence is absent")
    expected_head = str(before_storage.get("chain_head") or "")
    expected_sequence = before_storage.get("last_receipt_sequence")
    if (
        RECEIPT_HASH.fullmatch(expected_head) is None
        or not isinstance(expected_sequence, int)
        or isinstance(expected_sequence, bool)
        or expected_sequence < 1
    ):
        raise RestartProofError("pre-restart receipt head evidence is invalid")

    last_error: Exception | None = None
    current_after = dict(after)
    validate_continuity(before, current_after)
    retry_evidence: list[dict[str, Any]] = []
    if evidence is not None:
        evidence["post_restart_recovery_attempts"] = retry_evidence
    for attempt in range(max(1, attempts)):
        try:
            response = session.get(
                origin
                + "/api/a11oy/v1/series-a/receipts?"
                + urlencode({"receipt_hash": expected_head}),
                timeout=_remaining_timeout(deadline, 60),
            )
            attempt_evidence = recovery_response_evidence(response)
            attempt_evidence["attempt"] = attempt + 1
            retry_evidence.append(attempt_evidence)
            payload = _json(response)
            _check_deadline(deadline)
            current_after = recovery_capture(
                payload,
                expected_source=source_sha,
                expected_head=expected_head,
                expected_sequence=expected_sequence,
            )
            validate_restart(before, current_after, {expected_head})
            retry_evidence[-1]["recovered"] = True
            return current_after
        except Exception as exc:  # noqa: BLE001 - bounded recovery polling
            _reraise_hard(exc)
            last_error = exc
            if not retry_evidence or retry_evidence[-1].get("attempt") != attempt + 1:
                retry_evidence.append({"attempt": attempt + 1})
            retry_evidence[-1].update(
                {
                    "recovered": False,
                    "error_type": type(exc).__name__,
                    "error": _code(exc),
                }
            )
            if attempt + 1 < max(1, attempts):
                _sleep_with_deadline(deadline, retry_seconds)
    raise RestartProofError(
        "pre-restart receipt-chain head was not recovered after bounded polling: "
        f"{type(last_error).__name__}: {_code(last_error)}"
    )


HONEST_ROUTE = "/api/a11oy/v1/honest"


def await_running_source(
    api: Any,
    session: HttpSession,
    *,
    repo_id: str,
    origin: str,
    expected_source: str,
    deadline: float,
    attempts: int,
    retry_seconds: int,
    phase: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wait for ``runtime.stage == RUNNING`` and live honest ``git_sha``.

    Persistence is never declared from a runtime that is not RUNNING or that
    serves another revision. Exhausting the attempt cap or the shared deadline
    is ``RESTART_PROOF_TIMEOUT`` (a failure, never a pass).
    """

    bounds.require_canonical_space(repo_id)
    observations: list[dict[str, Any]] = []
    if evidence is not None:
        evidence[f"{phase}_running_source_observations"] = observations
    for attempt in range(max(1, attempts)):
        stage = "UNKNOWN"
        git_sha_matches = False
        try:
            _check_deadline(deadline)
            stage = _runtime_stage(api.get_space_runtime(repo_id=repo_id))
            if stage == "RUNNING":
                honest = _json(
                    session.get(
                        origin + HONEST_ROUTE,
                        timeout=_remaining_timeout(deadline, 45),
                    )
                )
                git_sha_matches = (
                    str(honest.get("git_sha") or "").lower() == expected_source
                )
            if len(observations) < 32:
                observations.append({
                    "attempt": attempt + 1,
                    "stage": stage if re.fullmatch(r"[A-Z_]{1,32}", stage) else "UNKNOWN",
                    "git_sha_matches": git_sha_matches,
                })
            if stage == "RUNNING" and git_sha_matches:
                return {"stage": "RUNNING", "git_sha": expected_source, "attempts": attempt + 1}
        except Exception as exc:  # noqa: BLE001 - bounded readiness polling
            if isinstance(exc, ProofBoundaryError) and exc.code == "DEADLINE_EXHAUSTED":
                break
            if getattr(exc, "code", None) == "DEADLINE_EXHAUSTED":
                break
            _reraise_hard(exc)
            if len(observations) < 32:
                observations.append({"attempt": attempt + 1, "error": _code(exc)})
        if attempt + 1 < max(1, attempts):
            if deadline - time.monotonic() <= 0:
                break
            try:
                _sleep_with_deadline(deadline, retry_seconds)
            except RestartProofError:
                break
    raise RestartProofError(
        f"{phase} runtime did not reach RUNNING at the deployed revision",
        code="RESTART_PROOF_TIMEOUT",
    )


def prove(
    *,
    api: HfApi,
    session: HttpSession,
    repo_id: str,
    origin: str,
    source_sha: str,
    attempts: int,
    retry_seconds: int,
    deadline_seconds: int = DEFAULT_DEADLINE_SECONDS,
    evidence: dict[str, Any] | None = None,
    require_running_source: bool = True,
) -> dict[str, Any]:
    if (
        attempts < 1
        or attempts > MAX_POLL_ATTEMPTS
        or retry_seconds < 0
        or retry_seconds > MAX_RETRY_SECONDS
        or deadline_seconds < 1
        or deadline_seconds > MAX_DEADLINE_SECONDS
    ):
        raise RestartProofError(
            "polling bounds must be positive and finite", code="INVALID_ARGUMENTS"
        )
    # Destination and effect scope are fixed before any network access.
    bounds.require_canonical_space(repo_id)
    if origin != bounds.CANONICAL_ORIGIN:
        raise ProofBoundaryError("DESTINATION_REJECTED")
    if SHA40.fullmatch(str(source_sha or "")) is None:
        raise RestartProofError("source revision is not canonical", code="INVALID_ARGUMENTS")
    deadline = time.monotonic() + deadline_seconds
    trace = evidence if evidence is not None else {}
    trace.update(
        {
            "source_revision": source_sha,
            "repo_id": repo_id,
            "origin": origin,
            "phase": "observe_pre_activation_runtime",
        }
    )

    pre_activation_boot_id = observe_boot_id(session, origin, deadline)
    trace["pre_activation_runtime_boot_id"] = pre_activation_boot_id
    # Hub variable writes are configuration-plane state. Explicitly restart
    # before sampling so the public process is proved against the just-converged
    # configuration instead of a retiring replica with stale environment. When
    # the old guarded contract has no boot ID, the new full contract's valid boot
    # is itself the observed transition.
    activation_control = stop_the_world_restart(
        api,
        repo_id=repo_id,
        deadline=deadline,
        attempts=attempts,
        retry_seconds=retry_seconds,
        phase="activation",
        evidence=trace,
    )
    trace["activation_restart_requested"] = True
    activation_stage = activation_control["restart_response_stage"]
    _sleep_with_deadline(deadline, max(10, retry_seconds))
    activation_running = None
    if require_running_source:
        activation_running = await_running_source(
            api, session, repo_id=repo_id, origin=origin,
            expected_source=source_sha, deadline=deadline, attempts=attempts,
            retry_seconds=retry_seconds, phase="activation", evidence=trace,
        )
    before = await_capture(
        session,
        origin,
        source_sha,
        deadline,
        attempts=attempts,
        retry_seconds=retry_seconds,
        context="configured runtime was not observed after activation restart",
        previous_boot_id=pre_activation_boot_id,
    )
    trace["before"] = before
    startup_error: Exception | None = None
    if before["storage"]["receipt_count"] == 0:
        # Public refresh is passport-only. The canonical startup scheduler owns
        # the initial observation, so the proof waits for its persisted receipt
        # instead of invoking a privileged mutation shortcut.
        for _ in range(max(1, attempts)):
            _sleep_with_deadline(deadline, retry_seconds)
            try:
                candidate = capture(session, origin, source_sha, deadline)
                before = candidate
                trace["before"] = before
                if before["storage"]["receipt_count"] > 0:
                    break
            except Exception as exc:  # noqa: BLE001 - bounded startup polling
                _reraise_hard(exc)
                startup_error = exc
    if before["storage"]["receipt_count"] == 0:
        detail = (
            f": {type(startup_error).__name__}: {_code(startup_error)}"
            if startup_error is not None
            else ""
        )
        raise RestartProofError(
            "no receipt exists to recover across restart" + detail
        )

    trace["phase"] = "verify_pre_restart_head"
    pre_restart_recovery = capture_pre_restart_receipt(
        session,
        origin,
        source_sha,
        before,
        deadline,
        evidence=trace,
    )
    trace["pre_restart_exact_recovery"] = pre_restart_recovery
    _check_deadline(deadline)
    trace["phase"] = "request_durability_restart"
    durability_control = stop_the_world_restart(
        api,
        repo_id=repo_id,
        deadline=deadline,
        attempts=attempts,
        retry_seconds=retry_seconds,
        phase="durability",
        evidence=trace,
    )
    trace["durability_restart_requested"] = True
    durability_stage = durability_control["restart_response_stage"]
    # Do not accept a response from the pre-restart process as post-restart
    # evidence while the control plane is still draining.
    _sleep_with_deadline(deadline, max(10, retry_seconds))
    durability_running = None
    if require_running_source:
        # Persistence is only declared against a RUNNING runtime that serves
        # the deployed revision; a timeout here is RESTART_PROOF_TIMEOUT.
        durability_running = await_running_source(
            api, session, repo_id=repo_id, origin=origin,
            expected_source=source_sha, deadline=deadline, attempts=attempts,
            retry_seconds=retry_seconds, phase="durability", evidence=trace,
        )

    last_error: Exception | None = None
    after: dict[str, Any] | None = None
    for _ in range(max(1, attempts)):
        try:
            candidate = capture(session, origin, source_sha, deadline)
            if candidate["runtime_boot_id"] == before["runtime_boot_id"]:
                raise RestartProofError(
                    "runtime boot identity did not change across restart"
                )
            after = candidate
            trace["after_capture"] = after
            break
        except Exception as exc:  # noqa: BLE001 - bounded restart polling
            _reraise_hard(exc)
            last_error = exc
            _sleep_with_deadline(deadline, retry_seconds)
    if after is None:
        raise RestartProofError(
            "runtime restart was not observed after bounded polling: "
            f"{type(last_error).__name__}: {_code(last_error)}"
        )

    trace["phase"] = "recover_post_restart_head"
    after = await_receipt_recovery(
        session,
        origin,
        source_sha,
        before,
        after,
        deadline,
        attempts=attempts,
        retry_seconds=retry_seconds,
        evidence=trace,
    )
    trace["after"] = after
    trace["phase"] = "complete"
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "ok": True,
        "repo_id": repo_id,
        "origin": origin,
        "restart_requested": True,
        "restart_response_stage": str(durability_stage or "UNKNOWN"),
        "activation_restart_requested": True,
        "activation_restart_response_stage": str(
            activation_stage or "UNKNOWN"
        ),
        "activation_pause_confirmed": activation_control["pause_confirmed"],
        "activation_writer_overlap_prevented": activation_control[
            "writer_overlap_prevented"
        ],
        "pre_activation_runtime_boot_id": pre_activation_boot_id,
        "activation_runtime_boot_identity_observed": True,
        "durability_restart_requested": True,
        "durability_restart_response_stage": str(
            durability_stage or "UNKNOWN"
        ),
        "durability_pause_confirmed": durability_control["pause_confirmed"],
        "durability_writer_overlap_prevented": durability_control[
            "writer_overlap_prevented"
        ],
        "before": before,
        "after": after,
        "proof": {
            "source_stable": True,
            "activation_runtime_transition_observed": True,
            "runtime_boot_identity_changed": True,
            "public_signing_identity_stable": True,
            "database_instance_stable": True,
            "database_creation_identity_stable": True,
            "receipt_count_non_regressing": True,
            "pre_restart_chain_head_recovered": True,
            "activation_stop_the_world": True,
            "durability_stop_the_world": True,
            "writer_overlap_prevented": True,
            "running_stage_and_source_observed": bool(
                activation_running and durability_running
            ),
        },
        "activation_running": activation_running,
        "durability_running": durability_running,
        "secret_values_read": False,
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    bounds.write_json(path, report)


MAX_REPORT_BYTES = 12 * 1024
_EVIDENCE_KEYS = (
    "phase",
    "pre_activation_runtime_boot_id",
    "activation_restart_control",
    "durability_restart_control",
    "activation_running_source_observations",
    "durability_running_source_observations",
    "activation_restart_requested",
    "durability_restart_requested",
)


def _bounded_evidence(evidence: Mapping[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    summary = bounds.bounded_report(
        {key: evidence.get(key) for key in _EVIDENCE_KEYS if key in evidence}
    )
    before = evidence.get("before")
    if isinstance(before, Mapping):
        summary["before"] = bounds.bounded_report({
            "runtime_boot_id": before.get("runtime_boot_id"),
            "storage": {
                key: (before.get("storage") or {}).get(key)
                for key in ("instance_id", "receipt_count", "last_receipt_sequence", "chain_head")
            } if isinstance(before.get("storage"), Mapping) else None,
        })
    encoded = json.dumps(summary, sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES // 2 or any(
        secret and secret in encoded for secret in secrets
    ):
        return {"phase": bounds.bounded_report(evidence.get("phase"))}
    return summary


def failure_report(
    *,
    repo_id: str,
    origin: str | None,
    source_revision: str,
    evidence: Mapping[str, Any],
    error: Exception,
    secrets: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Fixed-code failure report: no exception text, provider body or secret."""

    code = bounds.diagnostic_code(error, "UNEXPECTED_FAILURE")
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL",
        "ok": False,
        "diagnostic_code": code,
        "repo_id": bounds.CANONICAL_SPACE,
        "requested_repo_id_admitted": repo_id == bounds.CANONICAL_SPACE,
        "origin": bounds.CANONICAL_ORIGIN if origin == bounds.CANONICAL_ORIGIN else "UNVALIDATED",
        "source_revision": source_revision if SHA40.fullmatch(str(source_revision or "")) else "UNVALIDATED",
        "evidence": _bounded_evidence(evidence, secrets),
        "error": {
            "type": type(error).__name__ if type(error).__name__ in {
                "RestartProofError", "ProofBoundaryError"} else "UnexpectedError",
            "code": code,
        },
        "credential_authority_state": "UNKNOWN",
        "secret_values_recorded": False,
    }


def setup_required_report(*, source_revision: str, missing: list[str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL",
        "ok": False,
        "state": "SETUP_REQUIRED",
        "diagnostic_code": "SETUP_REQUIRED",
        "missing_secret_names": list(missing),
        "repo_id": bounds.CANONICAL_SPACE,
        "origin": bounds.CANONICAL_ORIGIN,
        "source_revision": source_revision if SHA40.fullmatch(source_revision) else "UNVALIDATED",
        "evidence": {},
        "credential_authority_state": "UNKNOWN",
        "secret_values_recorded": False,
    }


def pass_report(result: Mapping[str, Any], *, deadline_seconds: int, effects: list[Any]) -> dict[str, Any]:
    report = bounds.bounded_report(dict(result))
    report.update({
        "schema": SCHEMA,
        "status": "PASS",
        "ok": True,
        "state": "PROVEN",
        "diagnostic_code": "LIVE_PROOF_PASSED",
        "repo_id": bounds.CANONICAL_SPACE,
        "origin": bounds.CANONICAL_ORIGIN,
        "bounds": bounds.bounds_record(deadline_seconds=deadline_seconds),
        "effects": bounds.bounded_report(effects),
        "credential_authority_state": "VERIFIED",
        "secret_values_read": False,
        "secret_values_recorded": False,
    })
    return report


# The only credential this proof reads. Its value is placed in one
# Authorization header for huggingface.co/api/spaces/SZLHOLDINGS/a11oy and is
# never printed, logged or persisted.
HF_TOKEN_NAME = "HF_TOKEN"


def main(argv: list[str] | None = None, *, transport_factory: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded live Series-A restart persistence proof (SZLHOLDINGS/a11oy only)."
    )
    parser.add_argument("--repo-id", default=bounds.CANONICAL_SPACE)
    parser.add_argument("--origin", default=bounds.CANONICAL_ORIGIN)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--attempts", type=int, default=MAX_POLL_ATTEMPTS)
    parser.add_argument("--retry-seconds", type=int, default=10)
    parser.add_argument("--deadline-seconds", type=int, default=DEFAULT_DEADLINE_SECONDS)
    args = parser.parse_args(argv)
    source = str(args.source_sha or "").strip().lower()
    output = Path(args.output)
    evidence: dict[str, Any] = {}
    token = ""
    try:
        if SHA40.fullmatch(source) is None:
            raise RestartProofError("source revision is not canonical", code="INVALID_ARGUMENTS")
        bounds.require_canonical_space(args.repo_id)
        origin = normalize_origin(args.origin)
        token = os.environ.get(HF_TOKEN_NAME, "")
        if not token.strip():
            report = setup_required_report(source_revision=source, missing=[HF_TOKEN_NAME])
            encoded = bounds.write_json(output, report)
            print(encoded, end="")
            return 1
        deadline_seconds = min(max(1, args.deadline_seconds), MAX_DEADLINE_SECONDS)
        make_transport = transport_factory or bounds.BoundedTransport
        transport = make_transport(deadline_seconds=deadline_seconds)
        api = bounds.ScopedSpaceControl(transport, token, bounds.CANONICAL_SPACE)
        session = HttpSession(transport)
        result = prove(
            api=api,
            session=session,
            repo_id=bounds.CANONICAL_SPACE,
            origin=origin,
            source_sha=source,
            attempts=args.attempts,
            retry_seconds=args.retry_seconds,
            deadline_seconds=deadline_seconds,
            evidence=evidence,
            require_running_source=True,
        )
        report = pass_report(result, deadline_seconds=deadline_seconds, effects=api.effects)
        report["source_revision"] = source
        code = 0
    except Exception as exc:  # noqa: BLE001 - every failure is a fixed code
        report = failure_report(
            repo_id=str(args.repo_id),
            origin=str(args.origin),
            source_revision=source,
            evidence=evidence,
            error=exc,
            secrets=(token,) if token else (),
        )
        code = 1
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if token and token in encoded:  # defence in depth; never persist a secret
        report = failure_report(
            repo_id=bounds.CANONICAL_SPACE, origin=None, source_revision=source,
            evidence={}, error=ProofBoundaryError("UNEXPECTED_FAILURE"),
        )
        code = 1
    encoded = bounds.write_json(output, report)
    print(encoded, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
