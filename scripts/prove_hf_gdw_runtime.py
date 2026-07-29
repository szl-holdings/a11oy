#!/usr/bin/env python3
"""Exercise the exact live GDW successor without recording bearer material."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import requests


def request_json(method: str, url: str, *, token: str | None = None, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def _request_digest(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fresh_transition(
    *,
    base: str,
    source_sha: str,
    attempt_id: str,
    operator_token: str,
    generation_id: str,
) -> tuple[dict, dict]:
    challenge = hashlib.sha256(
        f"{source_sha}\0{attempt_id}".encode("utf-8")
    ).hexdigest()[:32]
    request_id = f"promotion-{source_sha[:16]}-{challenge}"
    session_id = f"promotion-session-{challenge}"
    session_url = f"{base}/api/a11oy/v1/gdw/sessions/{session_id}"
    preflight = requests.request(
        "GET",
        session_url,
        headers={"Authorization": f"Bearer {operator_token}"},
        timeout=30,
    )
    if preflight.status_code != 404:
        raise RuntimeError("GDW promotion session existed before fresh proof")

    request_payload = {
        "session_id": session_id,
        "request": (
            "verify durable governed successor "
            f"source={source_sha} challenge={challenge}"
        ),
        "allowed_experts": ["planner", "auditor", "verifier"],
        "risk_budget": 0.1,
        "mode_hint": "auto",
        "dry_run": False,
    }
    canonical_payload = {
        **request_payload,
        "novelty": None,
        "disagreement": None,
        "context_tokens": 0,
        "active_tool_count": 0,
        "memory_pressure": None,
    }
    expected_request_digest = _request_digest(canonical_payload)
    ambiguous_send = False
    step = None
    recovered_after_ambiguous_retry = False
    for retry in range(3):
        try:
            response = requests.request(
                "POST",
                f"{base}/api/a11oy/v1/gdw/step",
                headers={
                    "Authorization": f"Bearer {operator_token}",
                    "X-Request-Id": request_id,
                },
                json=request_payload,
                timeout=30,
            )
            if 400 <= response.status_code < 500:
                raise RuntimeError(
                    f"GDW promotion request was rejected with HTTP "
                    f"{response.status_code}"
                )
            if response.status_code >= 500:
                ambiguous_send = True
                if retry < 2:
                    time.sleep(2)
                    continue
                response.raise_for_status()
            response.raise_for_status()
            step = response.json()
        except requests.RequestException:
            ambiguous_send = True
            if retry < 2:
                time.sleep(2)
                continue
            raise

        if step.get("replayed") is True:
            if not ambiguous_send:
                raise RuntimeError(
                    "first successful GDW promotion response was already replayed"
                )
            recovered = request_json(
                "GET",
                session_url,
                token=operator_token,
            )
            state = recovered.get("state", {})
            if (
                recovered.get("step") != 1
                or state.get("generation_id") != generation_id
                or state.get("request_digest") != expected_request_digest
            ):
                raise RuntimeError(
                    "ambiguous GDW retry did not recover the exact fresh write"
                )
            recovered_after_ambiguous_retry = True
        break

    if step is None:
        raise RuntimeError("GDW protected transition produced no response")
    freshness = {
        "fresh_logical_write": True,
        "fresh_response_observed": step.get("replayed") is False,
        "recovered_after_ambiguous_retry": recovered_after_ambiguous_retry,
        "replayed": bool(step.get("replayed")),
        "attempt_id_sha256": hashlib.sha256(
            attempt_id.encode("utf-8")
        ).hexdigest(),
        "challenge": challenge,
        "request_id": request_id,
        "session_id": session_id,
        "request_digest": expected_request_digest,
    }
    return step, freshness


def prove(
    *,
    origin: str,
    source_sha: str,
    attempt_id: str,
    operator_token: str,
) -> dict:
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise RuntimeError("source SHA must be canonical lowercase hexadecimal")
    if not attempt_id or len(attempt_id.encode("utf-8")) > 512:
        raise RuntimeError("promotion attempt ID is unavailable or too long")
    if len(operator_token.encode("utf-8")) < 32:
        raise RuntimeError("GDW_OPERATOR_TOKEN is unavailable")
    base = origin.rstrip("/")
    health = None
    last_error = None
    for attempt in range(1, 121):
        try:
            candidate = request_json(
                "GET", f"{base}/api/a11oy/v1/gdw/healthz"
            )
            if (
                candidate.get("status") == "REAL"
                and candidate.get("write_ready") is True
                and candidate.get("persistence") == "SQLITE_DELETE"
            ):
                health = candidate
                break
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(5)
    if health is None:
        raise RuntimeError(f"GDW health did not converge: {last_error}")

    step, freshness = _fresh_transition(
        base=base,
        source_sha=source_sha,
        attempt_id=attempt_id,
        operator_token=operator_token,
        generation_id=health["generation_id"],
    )
    if (
        step.get("decision") != "ACCEPT"
        or step.get("receipt_status") != "UNSIGNED_ATOMIC"
        or step.get("proof", {}).get("status") != "OUTBOX_PENDING"
        or (
            step.get("replayed") is True
            and freshness["recovered_after_ambiguous_retry"] is not True
        )
    ):
        raise RuntimeError("GDW protected transition contract failed")

    drain = request_json(
        "POST",
        f"{base}/api/a11oy/v1/gdw/drain?limit=100",
        token=operator_token,
    )
    if (
        drain.get("failed") != 0
        or drain.get("gc_failed") != 0
        or drain.get("pending_effects") != 0
        or drain.get("pending_artifact_gc") != 0
        or drain.get("integrity_ok") is not True
    ):
        raise RuntimeError("GDW protected drain contract failed")
    integrity = request_json(
        "GET",
        f"{base}/api/a11oy/v1/gdw/integrity",
        token=operator_token,
    )
    session = request_json(
        "GET",
        f"{base}/api/a11oy/v1/gdw/sessions/{freshness['session_id']}",
        token=operator_token,
    )
    if (
        integrity.get("ok") is not True
        or integrity.get("journal_mode") != "DELETE"
        or session.get("state", {}).get("generation_id")
        != health.get("generation_id")
    ):
        raise RuntimeError("GDW live persistence contract failed")

    return {
        "schema": "szl.hf-gdw-live-proof/v1",
        "source_revision": source_sha,
        "health": health,
        "transition": {
            "decision": step["decision"],
            "receipt_status": step["receipt_status"],
            "proof_status": step["proof"]["status"],
            "replayed": bool(step.get("replayed")),
        },
        "freshness": freshness,
        "drain": drain,
        "integrity": {
            "ok": True,
            "journal_mode": integrity["journal_mode"],
            "pending_effects": integrity["pending_effects"],
            "pending_artifact_gc": integrity["pending_artifact_gc"],
            "violations": integrity["violations"],
        },
        "credential_values_recorded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = prove(
        origin=args.origin,
        source_sha=args.source_sha,
        attempt_id=args.attempt_id,
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
