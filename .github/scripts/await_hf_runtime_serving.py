#!/usr/bin/env python3
"""Wait, read-only, until the deployed revision serves again after a config write.

runtime-config converges configuration against the deployed revision when
preflight could not (a paused or crashed Space). On drift, every Space variable
or volume write restarts that revision. The readiness probe must not run
against a restarting Space, so this helper waits until the runtime is RUNNING
and /api/build-info reports the exact source for several consecutive reads.
It performs only Hugging Face metadata reads and same-host GETs; it never
restarts, pauses or writes anything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

SHA40 = re.compile(r"^[0-9a-f]{40}$")
INITIAL_DELAY_SECONDS = 30
POLL_SECONDS = 10
REQUIRED_CONSECUTIVE = 3
TIMEOUT_SECONDS = 900


class AwaitError(RuntimeError):
    """The deployed revision did not serve again within the bound."""


def convergence_wrote(reports: Iterable[Mapping[str, Any]]) -> bool:
    """True when any configure report records a provider write (a restart)."""
    for report in reports:
        if report.get("variables_changed") or report.get("volume_changed"):
            return True
    return False


def load_reports(paths: Iterable[str]) -> list[Mapping[str, Any]]:
    reports: list[Mapping[str, Any]] = []
    for path in paths:
        decoded = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(decoded, Mapping):
            raise AwaitError(f"configuration report is not an object: {path}")
        reports.append(decoded)
    return reports


def _stage(runtime: Any) -> str:
    stage = getattr(runtime, "stage", None)
    return str(getattr(stage, "value", stage) or "UNKNOWN").upper()


def serves_source(
    api: Any,
    fetch: Callable[[str], Any],
    *,
    repo_id: str,
    origin: str,
    source_sha: str,
) -> bool:
    if _stage(api.get_space_runtime(repo_id=repo_id)) != "RUNNING":
        return False
    try:
        payload = fetch(origin.rstrip("/") + "/api/build-info")
    except Exception:  # noqa: BLE001 - a restarting Space refuses or resets.
        return False
    build = payload.get("build") if isinstance(payload, Mapping) else None
    return (
        isinstance(build, Mapping)
        and str(build.get("revision") or "").lower() == source_sha
    )


def await_serving(
    api: Any,
    fetch: Callable[[str], Any],
    *,
    repo_id: str,
    origin: str,
    source_sha: str,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    timeout: float = TIMEOUT_SECONDS,
) -> int:
    """Return the number of polls once the source serves consecutively."""
    if SHA40.fullmatch(source_sha) is None:
        raise AwaitError("source revision must be an exact Git SHA")
    # A write's restart is not instantaneous; never accept the pre-restart
    # process as the settled one.
    sleep(INITIAL_DELAY_SECONDS)
    deadline = clock() + timeout
    streak = 0
    polls = 0
    while clock() < deadline:
        polls += 1
        if serves_source(
            api, fetch, repo_id=repo_id, origin=origin, source_sha=source_sha
        ):
            streak += 1
            if streak >= REQUIRED_CONSECUTIVE:
                return polls
        else:
            streak = 0
        sleep(POLL_SECONDS)
    raise AwaitError("the deployed revision did not serve again within the bound")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--report", action="append", required=True)
    args = parser.parse_args(argv)

    if not convergence_wrote(load_reports(args.report)):
        print(json.dumps({"convergence_wrote": False, "waited": False}))
        return 0

    import requests
    from huggingface_hub import HfApi

    api = HfApi(token=os.environ["HF_TOKEN"])
    session = requests.Session()
    session.headers.update({"Cache-Control": "no-cache", "Accept": "application/json"})

    def fetch(url: str) -> Any:
        response = session.get(url, allow_redirects=False, timeout=30)
        response.raise_for_status()
        return response.json()

    polls = await_serving(
        api,
        fetch,
        repo_id=args.repo_id,
        origin=args.origin,
        source_sha=str(args.source_sha).strip().lower(),
    )
    print(json.dumps({"convergence_wrote": True, "waited": True, "polls": polls}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
