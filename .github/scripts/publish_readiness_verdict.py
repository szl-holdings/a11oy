#!/usr/bin/env python3
"""Publish one compact post-deploy readiness verdict as a Space variable."""

from __future__ import annotations

import argparse
import json
import importlib.util
import sys
from functools import lru_cache
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
    "degraded",
)
BLOCKING_DEGRADED_FIELD = "blockingDegraded"
REQUIRED_NOT_PROBED_FIELD = "requiredNotProbed"


class VerdictError(RuntimeError):
    """The probe output is not safe to publish as deployment evidence."""


@lru_cache(maxsize=1)
def execution_validator():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("_publisher_execution_readiness", root / "szl_execution_readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    matrix=None, execution_bundle=None, execution_context=None,
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
    required_not_probed = summary.get(REQUIRED_NOT_PROBED_FIELD, skipped)
    if (
        not isinstance(required_not_probed, int)
        or isinstance(required_not_probed, bool)
        or not 0 <= required_not_probed <= skipped
    ):
        raise VerdictError("probe summary required-not-probed count is invalid")
    execution_coverage = None
    if matrix is None and normalize_origin(expected_origin) == "https://szlholdings-a11oy.hf.space":
        gate = execution_validator()
        matrix = gate.acceptance.strict_json(gate.acceptance.read_file(
            str(Path(__file__).resolve().parents[2] / "tools/readiness-harness/tabs.json")))
    matrix_requires_execution = isinstance(matrix, dict) and any(
        path in matrix.get("endpoints", {}) for path in (
            "/api/a11oy/v1/policy/decide", "/api/a11oy/v1/policy/compliance",
            "/api/a11oy/v1/operator/ask", "/api/a11oy/v1/eval/run", "/api/a11oy/v1/agentloop/run"))
    if required_not_probed != 0 or matrix_requires_execution:
        try:
            execution_coverage = execution_validator().validate_combined(
                payload, matrix, execution_bundle, execution_context, source=source_sha, now=current)
        except Exception as exc:
            raise VerdictError("probe summary contains unprobed required endpoints without verified execution evidence") from exc
    elif execution_bundle is not None or execution_context is not None:
        raise VerdictError("execution evidence cannot relabel the five passive NOT_PROBED rows")
    blocking_degraded = summary.get(BLOCKING_DEGRADED_FIELD, summary["degraded"])
    if (
        not isinstance(blocking_degraded, int)
        or isinstance(blocking_degraded, bool)
        or blocking_degraded < 0
        or blocking_degraded > summary["degraded"]
    ):
        raise VerdictError("probe summary blocking degradation is invalid")
    if summary["lies"] != 0:
        raise VerdictError("probe summary contains doctrine lies")
    if summary["unreachable"] != 0:
        raise VerdictError("probe summary contains unreachable required endpoints")
    if summary["throttled"] != 0:
        raise VerdictError("probe summary contains throttled required endpoints")
    if blocking_degraded != 0:
        raise VerdictError("probe summary contains unavailable required sources")
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
        **({"executionCoverage": execution_coverage} if execution_coverage is not None else {}),
        "summary": {
            **dict(zip(COUNT_FIELDS, counts, strict=True)),
            BLOCKING_DEGRADED_FIELD: blocking_degraded,
            REQUIRED_NOT_PROBED_FIELD: required_not_probed,
            "p95_worst": p95_worst,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--repo-id")
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--variable", default=VERDICT_VARIABLE)
    parser.add_argument("--execution-bundle")
    parser.add_argument("--authority-pins")
    parser.add_argument("--expected-runtime-sha")
    parser.add_argument("--expected-boot-id")
    parser.add_argument("--expected-run-nonce")
    parser.add_argument("--matrix", default=str(Path(__file__).resolve().parents[2] / "tools/readiness-harness/tabs.json"))
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Fail closed on the same verdict gate and print the compact verdict, "
            "but never write a Space variable: a variable write restarts the Space."
        ),
    )
    parser.add_argument(
        "--github-output",
        help=(
            "With --validate-only, append verdict=<compact JSON> so relock can "
            "re-validate this run's verdict without a Space write."
        ),
    )
    args = parser.parse_args(argv)
    if args.github_output and not args.validate_only:
        parser.error("--github-output is only valid with --validate-only")
    if not args.validate_only and not args.repo_id:
        parser.error("--repo-id is required to publish the verdict")

    token = os.environ.get("HF_TOKEN")
    if not args.validate_only and not token:
        raise VerdictError("HF_TOKEN is required to publish the verdict")
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise VerdictError("probe output must be a JSON object")
    execution_bundle = execution_context = None
    gate = execution_validator()
    matrix = gate.canonical_matrix(args.matrix)
    if args.execution_bundle:
        if not args.validate_only:
            raise VerdictError("combined evidence cannot be published through a restarting Space variable")
        gate = execution_validator()
        execution_context = gate.context_from_independent_file(
            args.authority_pins, expected_source=args.expected_source_sha,
            expected_runtime_revision=args.expected_runtime_sha,
            expected_runtime_boot_id=args.expected_boot_id,
            expected_run_nonce=args.expected_run_nonce)
        execution_bundle = gate.acceptance.strict_json(gate.acceptance.read_file(args.execution_bundle))
        matrix = gate.canonical_matrix(args.matrix)
    elif any((args.authority_pins, args.expected_runtime_sha, args.expected_boot_id, args.expected_run_nonce)):
        raise VerdictError("execution context requires the raw observation bundle")
    compact = compact_verdict(
        payload,
        expected_origin=args.expected_origin,
        expected_source_sha=args.expected_source_sha,
        matrix=matrix, execution_bundle=execution_bundle, execution_context=execution_context,
    )
    rendered = json.dumps(compact, sort_keys=True, separators=(",", ":"))
    if len(rendered.encode("utf-8")) > 4096:
        raise VerdictError("compact verdict exceeds the Space variable limit")
    if args.validate_only:
        if args.github_output:
            with open(args.github_output, "a", encoding="utf-8") as stream:
                stream.write(f"verdict={rendered}\n")
        print(json.dumps({"validated": True, "space_variable_written": False,
                          "verdict": compact}, sort_keys=True))
        return 0

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
