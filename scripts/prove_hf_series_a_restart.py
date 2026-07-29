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
from urllib.parse import urlsplit
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
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return HttpResponse(
                url=response.geturl(),
                status=response.status,
                content=response.read(),
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


def await_capture(
    session: HttpSession,
    origin: str,
    expected_source: str,
    deadline: float,
    *,
    attempts: int,
    retry_seconds: int,
    context: str,
) -> dict[str, Any]:
    """Poll until the restarted public runtime exposes the required contract."""

    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            return capture(session, origin, expected_source, deadline)
        except Exception as exc:  # noqa: BLE001 - bounded runtime polling
            last_error = exc
            if attempt + 1 < max(1, attempts):
                _sleep_with_deadline(deadline, retry_seconds)
    raise RestartProofError(
        f"{context}: {type(last_error).__name__}: {str(last_error)[:180]}"
    )


def validate_restart(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    receipt_hashes: set[str],
) -> None:
    if before.get("source_revision") != after.get("source_revision"):
        raise RestartProofError("source revision changed across restart")
    if before.get("runtime_boot_id") == after.get("runtime_boot_id"):
        raise RestartProofError("runtime boot identity did not change across restart")
    if (
        BOOT_ID.fullmatch(str(before.get("runtime_boot_id") or "")) is None
        or BOOT_ID.fullmatch(str(after.get("runtime_boot_id") or "")) is None
    ):
        raise RestartProofError("runtime boot identity evidence is invalid")
    if before.get("signing_key_source") != after.get("signing_key_source"):
        raise RestartProofError("signing source changed across restart")
    if before.get("public_key_sha256") != after.get("public_key_sha256"):
        raise RestartProofError("public signing identity changed across restart")
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
    previous_head = before_storage.get("chain_head")
    if previous_head and previous_head not in receipt_hashes:
        raise RestartProofError("pre-restart receipt-chain head was not recovered")


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
) -> dict[str, Any]:
    if attempts < 1 or retry_seconds < 0 or deadline_seconds < 1:
        raise RestartProofError("polling bounds must be positive and finite")
    deadline = time.monotonic() + deadline_seconds

    # Hub variable writes are configuration-plane state. Explicitly restart
    # before sampling so the public process is proved against the just-converged
    # configuration instead of a retiring replica with stale environment.
    activation_restart = api.restart_space(
        repo_id=repo_id,
        factory_reboot=False,
    )
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
    )
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

    _check_deadline(deadline)
    durability_restart = api.restart_space(
        repo_id=repo_id,
        factory_reboot=False,
    )
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
            break
        except Exception as exc:  # noqa: BLE001 - bounded restart polling
            last_error = exc
            _sleep_with_deadline(deadline, retry_seconds)
    if after is None:
        raise RestartProofError(
            "runtime restart was not observed after bounded polling: "
            f"{type(last_error).__name__}: {str(last_error)[:180]}"
        )

    receipts = _json(
        session.get(
            origin + "/api/a11oy/v1/series-a/receipts?limit=200",
            timeout=_remaining_timeout(deadline, 60),
        )
    )
    _check_deadline(deadline)
    items = receipts.get("items")
    if not isinstance(items, list):
        raise RestartProofError("receipt recovery endpoint is incomplete")
    hashes = {
        str(item.get("receipt_hash"))
        for item in items
        if isinstance(item, Mapping)
    }
    validate_restart(before, after, hashes)
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
        "durability_restart_requested": True,
        "durability_restart_response_stage": str(
            durability_stage or "UNKNOWN"
        ),
        "before": before,
        "after": after,
        "proof": {
            "source_stable": True,
            "runtime_boot_identity_changed": True,
            "public_signing_identity_stable": True,
            "database_instance_stable": True,
            "database_creation_identity_stable": True,
            "receipt_count_non_regressing": True,
            "pre_restart_chain_head_recovered": True,
        },
        "secret_values_read": False,
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

    source = args.source_sha.strip().lower()
    if SHA40.fullmatch(source) is None:
        raise RestartProofError("source SHA must be exact 40-character hex")
    token = os.environ.get("HF_TOKEN", "")
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
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
