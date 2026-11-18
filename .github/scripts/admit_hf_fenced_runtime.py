#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings
"""Fail-closed post-cutover release admission for a CLEAN, FENCED A11oy writer.

No state changes, signing, provider calls with effects, or secrets in output.
Uses the independent private HEAD/heartbeat baseline collected by the existing
configuration-handover reader and the existing canonical relock validator.
A crashed, paused, stale, unfenced, unsigned, or incomplete observer is a HOLD.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import requests

HERE = Path(__file__).resolve().parent
SCHEMA = "szl.hf-fenced-release-admission/v1"
STORAGE_ROUTE = "/api/a11oy/v1/storage/status"
MAX_BYTES = 65536


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handover = _load(HERE / "await_hf_configuration_handover.py", "_szl_handover_admission")
relock = _load(HERE / "verify_canonical_a11oy.py", "_szl_relock_admission")


class AdmissionHold(ValueError):
    """Stable, secret-free reason code."""


def require(condition: bool, code: str) -> None:
    if condition is not True:
        raise AdmissionHold(code)


def assess(baseline: dict, status: dict, *, expected_live_sha: str,
           now: float | None = None) -> dict:
    """Admit deployment only on already-active v2 fencing with clean restore."""
    require(type(expected_live_sha) is str
            and relock.SHA40.fullmatch(expected_live_sha) is not None,
            "SOURCE_EXPECTATION_INVALID")
    at = time.time() if now is None else now
    require(type(at) in (int, float) and math.isfinite(at), "CLOCK_INVALID")
    try:
        observed = handover.canonical_baseline(baseline, now=at)
    except (handover.Hold, KeyError, TypeError, ValueError):
        raise AdmissionHold("PRIVATE_BASELINE_UNAVAILABLE") from None
    require(0 <= at - observed["observed_at"] <= 90,
            "PRIVATE_BASELINE_STALE")
    require(observed["source_revision"] == expected_live_sha,
            "SOURCE_IDENTITY_MISMATCH")
    require(observed["state"] == "ACTIVE" and observed["claim"] == "CLEAN",
            "UNCLEAN_WRITER_NOT_ADMITTED")
    require(observed["heartbeat_age_seconds"] <= handover.FRESH_SECONDS,
            "PRIVATE_HEARTBEAT_STALE")
    require(type(status) is dict, "PUBLIC_STORAGE_UNAVAILABLE")
    try:
        relock.validate_state_store_status(status)
    except (relock.RelockError, AttributeError, TypeError, KeyError, ValueError):
        raise AdmissionHold("PUBLIC_FENCING_UNAVAILABLE") from None
    lease = status["lease"]
    require(status.get("active_errors") == {}
            and status.get("claim") == "CLEAN"
            and status["epoch"] == observed["epoch"]
            and lease["sequence"] >= observed["sequence"]
            and lease["heartbeat_age_s"] <= handover.FRESH_SECONDS,
            "WRITER_COHERENCE_UNAVAILABLE")
    require(all(store.get("origin") == "RESTORED"
                for store in status["stores"].values()),
            "STORES_NOT_CLEANLY_RESTORED")
    return {
        "schema": SCHEMA, "status": "ADMITTED",
        "scope": "CLEAN_FENCED_WRITER_ONLY",
        "provider_writes": 0, "signature": "UNSIGNED",
        "deployment_authority": False,
        "source_revision": expected_live_sha,
        "hf_repository_revision": observed["hf_revision"],
        "head_revision": observed["head_commit"],
        "head_sha256": observed["head_sha256"],
        "epoch": observed["epoch"],
        "lease_sequence": lease["sequence"],
        "store_count": len(status["stores"]),
        "observed_at": at,
    }



def verify_v2_control_plane_setting() -> None:
    """Independent read of the installed Space variable; never print secrets."""
    try:
        api = relock.HfApi()
        variables = api.get_space_variables("SZLHOLDINGS/a11oy")
        require(type(variables) is dict
                and getattr(variables.get("A11OY_STATE_STORE"), "value", None) == "v2",
                "V2_RUNTIME_VARIABLE_UNAVAILABLE")
    except AdmissionHold:
        raise
    except Exception:
        raise AdmissionHold("V2_RUNTIME_VARIABLE_UNAVAILABLE") from None

def read_public_status(origin: str) -> dict:
    require(origin == handover.ORIGIN, "CANONICAL_ORIGIN_REQUIRED")
    url = origin + STORAGE_ROUTE
    try:
        with requests.Session() as session:
            with session.get(url, allow_redirects=False, timeout=(5, 12),
                             stream=True, headers={
                                 "Accept": "application/json",
                                 "Cache-Control": "no-cache, no-store",
                             }) as response:
                require(response.status_code == 200, "PUBLIC_STORAGE_HTTP_UNAVAILABLE")
                require(response.url == url, "PUBLIC_STORAGE_REDIRECT_REFUSED")
                require(response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        == "application/json", "PUBLIC_STORAGE_NOT_JSON")
                pieces = []
                size = 0
                for chunk in response.iter_content(16384):
                    size += len(chunk)
                    require(size <= MAX_BYTES, "PUBLIC_STORAGE_TOO_LARGE")
                    pieces.append(chunk)
        return handover.strict_json(b"".join(pieces))
    except AdmissionHold:
        raise
    except (requests.RequestException, ValueError, handover.Hold):
        raise AdmissionHold("PUBLIC_STORAGE_UNAVAILABLE") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--expected-live-sha", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(args.origin == handover.ORIGIN, "CANONICAL_ORIGIN_REQUIRED")
        raw = args.baseline.read_bytes()
        require(0 < len(raw) <= MAX_BYTES, "PRIVATE_BASELINE_SIZE_INVALID")
        baseline = handover.strict_json(raw)
        verify_v2_control_plane_setting()
        result = assess(
            baseline, read_public_status(args.origin),
            expected_live_sha=args.expected_live_sha,
        )
        result["v2_runtime_variable_verified"] = True
        args.output.write_text(json.dumps(result, sort_keys=True) + "\n",
                               encoding="utf-8")
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write("open=true\n")
        print(json.dumps({"status": "ADMITTED",
                          "scope": result["scope"], "epoch": result["epoch"],
                          "store_count": result["store_count"],
                          "provider_writes": 0}))
        return 0
    except (AdmissionHold, handover.Hold, OSError) as exc:
        code = str(exc) if isinstance(exc, AdmissionHold) else "BASELINE_UNAVAILABLE"
        print(json.dumps({"status": "HOLD", "reason": code,
                          "provider_writes": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
