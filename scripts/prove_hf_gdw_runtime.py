#!/usr/bin/env python3
"""Exercise the exact live GDW successor without recording bearer material."""

from __future__ import annotations

import argparse
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

    drain = request_json(
        "POST",
        f"{base}/api/a11oy/v1/gdw/drain?limit=100",
        token=operator_token,
    )
    if (
        drain.get("failed") != 0
        or drain.get("integrity_ok") is not True
    ):
        raise RuntimeError("GDW protected drain contract failed")
    integrity = None
    last_integrity = None
    for _attempt in range(1, 61):
        candidate = request_json(
            "GET",
            f"{base}/api/a11oy/v1/gdw/integrity/global",
            token=operator_token,
        )
        last_integrity = candidate
        if (
            candidate.get("ok") is True
            and candidate.get("pending_effects") == 0
            and candidate.get("claimed_effects") == 0
        ):
            integrity = candidate
            break
        time.sleep(1)
    if integrity is None:
        pending = (
            last_integrity.get("pending_effects")
            if isinstance(last_integrity, dict)
            else None
        )
        claimed = (
            last_integrity.get("claimed_effects")
            if isinstance(last_integrity, dict)
            else None
        )
        raise RuntimeError(
            "GDW protected drain did not converge: "
            f"pending={pending}, claimed={claimed}"
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
    args = parser.parse_args()
    report = prove(
        origin=args.origin,
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
