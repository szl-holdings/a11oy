#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Prove A11oy signer and receipt identity across an actual Space restart."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from huggingface_hub import HfApi


SCHEMA = "szl.series-a-restart-proof/v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STORE_ID = re.compile(r"^store_[0-9a-f]{32}$")
BOOT_ID = re.compile(r"^boot_[0-9a-f]{32}$")
RECEIPT_HASH = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_SIGNER = "persistent:env:SZL_COSIGN_PRIVATE_PEM"
EXPECTED_DATABASE = "/data/a11oy/series-a/control-plane-v2.sqlite3"
DEFAULT_DEADLINE_SECONDS = 20 * 60


class RestartProofError(RuntimeError):
    """The restarted runtime did not preserve the required identity."""


class HttpResponse:
    """Minimal response surface for a dependency-free proof client."""

    def __init__(self, url: str, status: int, content: bytes) -> None:
        self.url = url
        self.status = status
        self.content = content

    def raise_for_status(self) -> None:
        if not 200 <= self.status < 300:
            raise RestartProofError(f"{self.url} returned HTTP {self.status}")

    def json(self) -> Any:
        return json.loads(self.content)


class HttpSession:
    """Small urllib-backed session; deliberately has no undeclared dependency."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def _request(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        value: Mapping[str, Any] | None = None,
    ) -> HttpResponse:
        data = None
        headers = dict(self.headers)
        if value is not None:
            data = json.dumps(value).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                return HttpResponse(
                    url=response.geturl(),
                    status=response.status,
                    content=response.read(),
                )
        except HTTPError as exc:
            return HttpResponse(
                url=exc.geturl(),
                status=int(exc.code),
                content=exc.read(),
            )

    def get(self, url: str, *, timeout: float) -> HttpResponse:
        return self._request("GET", url, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        timeout: int,
    ) -> HttpResponse:
        return self._request("POST", url, timeout=timeout, value=json)


def normalize_origin(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise RestartProofError("origin must be a credential-free HTTPS origin")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname.lower()}{port}"


def _json(response: HttpResponse) -> Mapping[str, Any]:
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, Mapping):
        raise RestartProofError(f"{response.url} did not return a JSON object")
    return value


def _remaining_timeout(deadline: float, maximum: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RestartProofError("restart proof deadline exhausted")
    return max(0.1, min(maximum, remaining))


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise RestartProofError("restart proof deadline exhausted")


def _sleep_with_deadline(deadline: float, seconds: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RestartProofError("restart proof deadline exhausted")
    time.sleep(min(max(0.0, seconds), remaining))
    _check_deadline(deadline)


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
            last_error = exc
            if attempt + 1 < max(1, attempts):
                _sleep_with_deadline(deadline, retry_seconds)
    raise RestartProofError(
        f"{context}: {type(last_error).__name__}: {str(last_error)[:180]}"
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
            last_error = exc
            if not retry_evidence or retry_evidence[-1].get("attempt") != attempt + 1:
                retry_evidence.append({"attempt": attempt + 1})
            retry_evidence[-1].update(
                {
                    "recovered": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:180],
                }
            )
            if attempt + 1 < max(1, attempts):
                _sleep_with_deadline(deadline, retry_seconds)
    raise RestartProofError(
        "pre-restart receipt-chain head was not recovered after bounded polling: "
        f"{type(last_error).__name__}: {str(last_error)[:180]}"
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
) -> dict[str, Any]:
    if attempts < 1 or retry_seconds < 0 or deadline_seconds < 1:
        raise RestartProofError("polling bounds must be positive and finite")
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
    activation_restart = api.restart_space(
        repo_id=repo_id,
        factory_reboot=False,
    )
    trace["activation_restart_requested"] = True
    _check_deadline(deadline)
    activation_stage = getattr(
        getattr(activation_restart, "runtime", None),
        "stage",
        None,
    )
    activation_stage = getattr(activation_stage, "value", activation_stage)
    _sleep_with_deadline(deadline, max(10, retry_seconds))
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
                startup_error = exc
    if before["storage"]["receipt_count"] == 0:
        detail = (
            f": {type(startup_error).__name__}: {str(startup_error)[:180]}"
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
    durability_restart = api.restart_space(
        repo_id=repo_id,
        factory_reboot=False,
    )
    trace["durability_restart_requested"] = True
    _check_deadline(deadline)
    durability_stage = getattr(
        getattr(durability_restart, "runtime", None),
        "stage",
        None,
    )
    durability_stage = getattr(
        durability_stage,
        "value",
        durability_stage,
    )
    # Do not accept a response from the pre-restart process as post-restart
    # evidence while the control plane is still draining.
    _sleep_with_deadline(deadline, max(10, retry_seconds))

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
            last_error = exc
            _sleep_with_deadline(deadline, retry_seconds)
    if after is None:
        raise RestartProofError(
            "runtime restart was not observed after bounded polling: "
            f"{type(last_error).__name__}: {str(last_error)[:180]}"
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
        "pre_activation_runtime_boot_id": pre_activation_boot_id,
        "activation_runtime_boot_identity_observed": True,
        "durability_restart_requested": True,
        "durability_restart_response_stage": str(
            durability_stage or "UNKNOWN"
        ),
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
        },
        "secret_values_read": False,
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def failure_report(
    *,
    repo_id: str,
    origin: str | None,
    source_revision: str,
    evidence: Mapping[str, Any],
    error: Exception,
    secrets: tuple[str, ...] = (),
) -> dict[str, Any]:
    message = str(error)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL",
        "ok": False,
        "repo_id": repo_id,
        "origin": origin or "UNVALIDATED",
        "source_revision": source_revision,
        "evidence": dict(evidence),
        "error": {
            "type": type(error).__name__,
            "message": message[:500],
        },
        "secret_values_recorded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default="SZLHOLDINGS/a11oy")
    parser.add_argument("--origin", default="https://a-11-oy.com")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--attempts", type=int, default=90)
    parser.add_argument("--retry-seconds", type=int, default=10)
    parser.add_argument(
        "--deadline-seconds",
        type=int,
        default=DEFAULT_DEADLINE_SECONDS,
    )
    args = parser.parse_args()

    output = Path(args.output)
    source = args.source_sha.strip().lower()
    token = os.environ.get("HF_TOKEN", "")
    origin: str | None = None
    evidence: dict[str, Any] = {}
    try:
        if SHA40.fullmatch(source) is None:
            raise RestartProofError("source SHA must be exact 40-character hex")
        if not token:
            raise RestartProofError("HF_TOKEN is required")
        origin = normalize_origin(args.origin)
        session = HttpSession()
        session.headers.update(
            {
                "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache, no-store, max-age=0",
                "Pragma": "no-cache",
                "User-Agent": "szl-series-a-restart-proof/1",
            }
        )
        report = prove(
            api=HfApi(token=token),
            session=session,
            repo_id=args.repo_id,
            origin=origin,
            source_sha=source,
            attempts=args.attempts,
            retry_seconds=args.retry_seconds,
            deadline_seconds=args.deadline_seconds,
            evidence=evidence,
        )
    except Exception as exc:
        report = failure_report(
            repo_id=args.repo_id,
            origin=origin,
            source_revision=source,
            evidence=evidence,
            error=exc,
            secrets=(token,),
        )
        write_report(output, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        raise
    write_report(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
