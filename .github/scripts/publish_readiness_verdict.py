#!/usr/bin/env python3
"""Publish one compact post-deploy readiness verdict as a Space variable."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


SHA40 = re.compile(r"^[0-9a-f]{40}$")
STRICT_UTC = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)
VERDICT_SCHEMA = "szl.readiness-verdict/v1"
VERDICT_VARIABLE = "SZL_PROBE_VERDICT_JSON"
MAX_INGEST_AGE_SECONDS = 3600
COUNT_FIELDS = (
    "endpoints",
    "ok",
    "skippedStateChanging",
    "lies",
    "unreachable",
    "throttled",
)


class VerdictError(RuntimeError):
    """The probe output is not safe to publish as deployment evidence."""


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
        raise VerdictError("verdict base must be a credential-free HTTPS origin")
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError as exc:
        raise VerdictError("verdict base has an invalid port") from exc
    return f"https://{parsed.hostname.lower()}{port}"


def compact_verdict(
    payload: Mapping[str, Any],
    *,
    expected_origin: str,
    expected_source_sha: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate fresh probe output and retain only the served evidence fields."""
    source_sha = str(expected_source_sha or "").strip().lower()
    if SHA40.fullmatch(source_sha) is None:
        raise VerdictError("expected source revision must be an exact Git SHA")
    if (
        payload.get("schema") != VERDICT_SCHEMA
        or payload.get("harness") != "a11oy-readiness probe"
        or payload.get("doctrine") != "v11"
        or payload.get("sourceRevision") != source_sha
        or normalize_origin(payload.get("base")) != normalize_origin(expected_origin)
    ):
        raise VerdictError("probe identity, origin, or source revision does not match")

    checked_at = payload.get("checkedAt")
    if not isinstance(checked_at, str) or STRICT_UTC.fullmatch(checked_at) is None:
        raise VerdictError("probe observation time is not strict UTC")
    try:
        checked = datetime.fromisoformat(checked_at[:-1] + "+00:00")
    except ValueError as exc:
        raise VerdictError("probe observation time is invalid") from exc
    current = now or datetime.now(timezone.utc)
    age_seconds = (current - checked).total_seconds()
    if age_seconds < 0 or age_seconds > MAX_INGEST_AGE_SECONDS:
        raise VerdictError("probe observation is future-dated or too old to ingest")

    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        raise VerdictError("probe summary is missing")
    counts = [summary.get(field) for field in COUNT_FIELDS]
    if not all(
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        for value in counts
    ):
        raise VerdictError("probe summary counts are incomplete")
    endpoints, _, skipped, *_ = counts
    if endpoints <= 0 or endpoints - skipped <= 0 or sum(counts[1:]) != endpoints:
        raise VerdictError("probe summary outcomes are inconsistent")
    if summary["lies"] != 0:
        raise VerdictError("probe summary contains doctrine lies")
    if summary["unreachable"] != 0:
        raise VerdictError("probe summary contains unreachable required endpoints")
    if summary["throttled"] != 0:
        raise VerdictError("probe summary contains throttled required endpoints")
    p95_worst = summary.get("p95_worst")
    if (
        not isinstance(p95_worst, (int, float))
        or isinstance(p95_worst, bool)
        or not math.isfinite(p95_worst)
        or p95_worst < 0
    ):
        raise VerdictError("probe summary latency is invalid")

    return {
        "schema": VERDICT_SCHEMA,
        "harness": "a11oy-readiness probe",
        "doctrine": "v11",
        "base": normalize_origin(expected_origin),
        "checkedAt": checked_at,
        "sourceRevision": source_sha,
        "summary": {
            **dict(zip(COUNT_FIELDS, counts, strict=True)),
            "p95_worst": p95_worst,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--variable", default=VERDICT_VARIABLE)
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise VerdictError("HF_TOKEN is required to publish the verdict")
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise VerdictError("probe output must be a JSON object")
    compact = compact_verdict(
        payload,
        expected_origin=args.expected_origin,
        expected_source_sha=args.expected_source_sha,
    )
    rendered = json.dumps(compact, sort_keys=True, separators=(",", ":"))
    if len(rendered.encode("utf-8")) > 4096:
        raise VerdictError("compact verdict exceeds the Space variable limit")

    from huggingface_hub import HfApi

    HfApi(token=token).add_space_variable(
        args.repo_id,
        key=args.variable,
        value=rendered,
        description=(
            "Post-deploy, source-bound readiness verdict published by hf-sync.yml"
        ),
    )
    print(
        json.dumps(
            {
                "repo_id": args.repo_id,
                "variable": args.variable,
                "source_revision": compact["sourceRevision"],
                "base": compact["base"],
                "checked_at": compact["checkedAt"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
