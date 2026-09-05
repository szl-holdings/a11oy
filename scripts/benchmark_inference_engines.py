#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run a governed OpenAI-compatible inference benchmark.

The harness is fail closed: an external endpoint is never contacted without
explicit metered-run authority and an operator budget, identity sentinels never
produce measured evidence, and each result is written once as an explicit
SIGNED/UNSIGNED receipt. This harness never promotes an engine.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from szl_inference_engine_registry import engine as registered_engine  # noqa: E402


SCHEMA_VERSION = "szl.inference-benchmark-result/v1"
METERED_AUTHORITY_ENV = "SZL_ALLOW_METERED_INFERENCE_BAKEOFF"
_IMMUTABLE_REVISION_RE = re.compile(
    r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})$"
)
_ENVIRONMENT_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-.+][A-Za-z0-9.-]+)?$")
_UNAVAILABLE = {
    "",
    "BLOCKED",
    "NOT_AVAILABLE",
    "NOT_MEASURED",
    "UNKNOWN",
    "UNAVAILABLE",
}


def _canonical_identity(value: str) -> str:
    """Return the canonical representation accepted by the result schema."""
    return value.strip().lower()


def _canonical_engine_id(value: str) -> str:
    """Resolve a user spelling to the registry's schema-safe engine id."""
    spec = registered_engine(value)
    if spec is None:
        raise ValueError(f"unregistered engine: {value}")
    return spec.id


def _canonical_available_text(
    value: str, *, name: str, minimum: int, maximum: int
) -> str:
    """Normalize bounded text without allowing honesty sentinels through."""
    normalized = value.strip()
    if normalized.upper() in _UNAVAILABLE or not minimum <= len(normalized) <= maximum:
        raise ValueError(
            f"{name} must be explicit and between {minimum} and {maximum} characters"
        )
    return normalized


@dataclass(frozen=True)
class Sample:
    ok: bool
    status: int | None
    latency_ms: float
    output_tokens: int | None
    error: str | None = None
    request_id: str | None = None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent a permitted endpoint from redirecting into an unapproved one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def canonical_sha256(payload: Mapping[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_receipt(report: Mapping[str, object]) -> bool:
    receipt = report.get("receipt")
    if not isinstance(receipt, Mapping):
        return False
    expected = receipt.get("payload_sha256")
    if not isinstance(expected, str):
        return False
    unsigned_payload = dict(report)
    unsigned_payload.pop("receipt", None)
    return expected == canonical_sha256(unsigned_payload)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_loopback_endpoint(base_url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.hostname.lower() == "localhost":
            return True
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def budget_authorization(
    base_url: str,
    budget_usd: float | None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Authorize loopback for free; require both gates for any other host."""
    if _is_loopback_endpoint(base_url):
        return {
            "allowed": True,
            "mode": "LOCAL_UNMETERED",
            "budget_usd": None,
            "reason": "loopback endpoint; no provider spend authorized",
        }

    env = os.environ if environ is None else environ
    explicit = env.get(METERED_AUTHORITY_ENV) == "1"
    valid_budget = (
        isinstance(budget_usd, (int, float))
        and not isinstance(budget_usd, bool)
        and math.isfinite(float(budget_usd))
        and float(budget_usd) > 0
    )
    if explicit and valid_budget:
        return {
            "allowed": True,
            "mode": "METERED_OPERATOR_AUTHORIZED",
            "budget_usd": float(budget_usd),
            "reason": "explicit metered authority and positive operator budget present",
        }
    return {
        "allowed": False,
        "mode": "BLOCKED_BUDGET",
        "budget_usd": float(budget_usd) if valid_budget else None,
        "reason": (
            f"external benchmark requires {METERED_AUTHORITY_ENV}=1 "
            "and a positive --budget-usd; no request was sent"
        ),
    }


def _validate_identity(
    *,
    engine_id: str,
    engine_version: str,
    model_revision: str,
    tokenizer_revision: str,
    source_revision: str,
    hardware_fingerprint: str,
    environment_digest: str,
    model_license: str,
) -> None:
    _canonical_engine_id(engine_id)
    if not _SEMVER_RE.fullmatch(engine_version):
        raise ValueError("engine version must be exact semantic version")
    for name, value in (
        ("model revision", model_revision),
        ("tokenizer revision", tokenizer_revision),
        ("source revision", source_revision),
    ):
        if not _IMMUTABLE_REVISION_RE.fullmatch(_canonical_identity(value)):
            raise ValueError(
                f"{name} must be an immutable 40/64-hex revision or sha256 digest"
            )
    if not _ENVIRONMENT_DIGEST_RE.fullmatch(
        _canonical_identity(environment_digest)
    ):
        raise ValueError("environment digest must be sha256:<64 lowercase hex>")
    _canonical_available_text(
        hardware_fingerprint,
        name="hardware fingerprint",
        minimum=3,
        maximum=512,
    )
    _canonical_available_text(
        model_license,
        name="model license",
        minimum=1,
        maximum=256,
    )


def run_sample(
    base_url: str,
    model: str,
    prompt: str,
    timeout: float,
    api_key: str | None,
    *,
    request_id: str | None = None,
) -> Sample:
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    rid = request_id or str(uuid.uuid4())
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Request-ID": rid}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    started = time.perf_counter()
    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            elapsed = (time.perf_counter() - started) * 1000.0
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("response exceeds 8 MiB evidence bound")
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("response is not a JSON object")
            choices = parsed.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("response has no choices")
            first = choices[0]
            message = first.get("message") if isinstance(first, dict) else None
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ValueError("response has no message content")
            usage = parsed.get("usage")
            out_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            if isinstance(out_tokens, bool) or not isinstance(out_tokens, int) or out_tokens < 0:
                out_tokens = None
            return Sample(True, int(response.status), elapsed, out_tokens, request_id=rid)
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000.0
        return Sample(False, int(exc.code), elapsed, None, f"HTTP {exc.code}", rid)
    except Exception as exc:  # fail closed; expose only the error class
        elapsed = (time.perf_counter() - started) * 1000.0
        return Sample(False, None, elapsed, None, type(exc).__name__, rid)


def summarize(
    engine_id: str,
    model: str,
    source_revision: str,
    hardware_fingerprint: str,
    samples: list[Sample],
    *,
    engine_version: str,
    model_revision: str,
    tokenizer_revision: str,
    model_license: str,
    environment_digest: str,
    workload: str,
    rollback: Mapping[str, str],
    budget: Mapping[str, object],
    run_id: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    blocked_reason: str | None = None,
) -> dict[str, object]:
    canonical_engine = _canonical_engine_id(engine_id)
    canonical_model = _canonical_available_text(
        model, name="model", minimum=1, maximum=256
    )
    canonical_hardware = _canonical_available_text(
        hardware_fingerprint,
        name="hardware fingerprint",
        minimum=3,
        maximum=512,
    )
    canonical_license = _canonical_available_text(
        model_license,
        name="model license",
        minimum=1,
        maximum=256,
    )
    canonical_workload = _canonical_available_text(
        workload, name="workload", minimum=1, maximum=128
    )
    good = [sample for sample in samples if sample.ok]
    latencies = [sample.latency_ms for sample in good]
    token_rates = [
        sample.output_tokens / (sample.latency_ms / 1000.0)
        for sample in good
        if sample.output_tokens is not None and sample.latency_ms > 0
    ]
    failures = len(samples) - len(good)
    if blocked_reason:
        classification = "BLOCKED"
        failure = blocked_reason
    elif not samples or failures:
        classification = "FAILED"
        failure = (
            "no samples were executed"
            if not samples
            else f"{failures} of {len(samples)} samples failed"
        )
    else:
        classification = "MEASURED"
        failure = None

    canonical_rollback = dict(rollback)
    rollback_engine = canonical_rollback.get("target_engine")
    if not isinstance(rollback_engine, str):
        raise ValueError("rollback target engine must be explicit")
    canonical_rollback["target_engine"] = _canonical_engine_id(rollback_engine)
    rollback_revision = canonical_rollback.get("target_model_revision")
    if isinstance(rollback_revision, str):
        canonical_rollback["target_model_revision"] = _canonical_identity(
            rollback_revision
        )

    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id or str(uuid.uuid4()),
        "engine": canonical_engine,
        "engine_version": engine_version,
        "model": canonical_model,
        "model_revision": _canonical_identity(model_revision),
        "tokenizer_revision": _canonical_identity(tokenizer_revision),
        "model_license": canonical_license,
        "source_revision": _canonical_identity(source_revision),
        "hardware_fingerprint": canonical_hardware,
        "environment_digest": _canonical_identity(environment_digest),
        "workload": canonical_workload,
        "repetition": len(samples),
        "status": classification,
        "classification": classification,
        "started_at": started_at or _utc_now(),
        "completed_at": completed_at or _utc_now(),
        "metrics": {
            "sample_count": len(samples),
            "success_count": len(good),
            "failure_count": failures,
            "end_to_end_latency_ms_p50": percentile(latencies, 0.50),
            "end_to_end_latency_ms_p95": percentile(latencies, 0.95),
            "end_to_end_latency_ms_p99": percentile(latencies, 0.99),
            "mean_output_tokens_per_second": (
                statistics.fmean(token_rates) if token_rates else None
            ),
            "time_to_first_token_ms_p50": None,
            "time_to_first_token_ms_p95": None,
            "peak_memory_mb": None,
            "structured_output_pass_rate": None,
            "refusal_parity_pass": None,
            "receipt_overhead_ms": None,
            "error_rate": failures / len(samples) if samples else None,
        },
        "request_ids": [sample.request_id for sample in samples if sample.request_id],
        "errors": [sample.error for sample in samples if sample.error],
        "failure": failure,
        "budget_authorization": dict(budget),
        "promotion_status": "NOT_EVALUATED",
        "rollback": canonical_rollback,
    }
    result["receipt"] = {
        "signature_status": "UNSIGNED",
        "payload_sha256": canonical_sha256(result),
        "signature": None,
    }
    return result


def write_immutable_receipt(path: Path, report: Mapping[str, object]) -> None:
    if not verify_receipt(report):
        raise ValueError("refusing to write an invalid benchmark receipt")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--engine-version", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--tokenizer-revision", required=True)
    parser.add_argument("--model-license", required=True)
    parser.add_argument("--environment-digest", required=True)
    parser.add_argument("--workload", default="a11oy-governed-chat-smoke/v1")
    parser.add_argument("--prompt", default="Return exactly: A11OY_BENCH_OK")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--source-revision", default=os.getenv("GITHUB_SHA", "UNAVAILABLE"))
    parser.add_argument(
        "--hardware-fingerprint",
        default=os.getenv("A11OY_HARDWARE_FINGERPRINT", "UNAVAILABLE"),
    )
    parser.add_argument("--api-key-env", default="A11OY_BENCH_API_KEY")
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--rollback-target-engine", required=True)
    parser.add_argument("--rollback-target-model-revision", required=True)
    parser.add_argument("--rollback-instructions", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.samples < 1:
        raise SystemExit("--samples must be >= 1")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise SystemExit("--timeout must be a positive finite number")
    _validate_identity(
        engine_id=args.engine,
        engine_version=args.engine_version,
        model_revision=args.model_revision,
        tokenizer_revision=args.tokenizer_revision,
        source_revision=args.source_revision,
        hardware_fingerprint=args.hardware_fingerprint,
        environment_digest=args.environment_digest,
        model_license=args.model_license,
    )
    if registered_engine(args.rollback_target_engine) is None:
        raise SystemExit("--rollback-target-engine must be registered")
    if not _IMMUTABLE_REVISION_RE.fullmatch(
        _canonical_identity(args.rollback_target_model_revision)
    ):
        raise SystemExit("--rollback-target-model-revision must be immutable")
    canonical_model = _canonical_available_text(
        args.model, name="model", minimum=1, maximum=256
    )
    canonical_workload = _canonical_available_text(
        args.workload, name="workload", minimum=1, maximum=128
    )
    canonical_rollback_instructions = _canonical_available_text(
        args.rollback_instructions,
        name="rollback instructions",
        minimum=10,
        maximum=4096,
    )

    authority = budget_authorization(args.base_url, args.budget_usd)
    run_id = str(uuid.uuid4())
    started_at = _utc_now()
    samples: list[Sample] = []
    blocked_reason = None
    if authority["allowed"]:
        api_key = os.getenv(args.api_key_env) if args.api_key_env else None
        for index in range(args.samples):
            samples.append(
                run_sample(
                    args.base_url,
                    canonical_model,
                    args.prompt,
                    args.timeout,
                    api_key,
                    request_id=f"{run_id}:{index + 1}",
                )
            )
    else:
        blocked_reason = str(authority["reason"])

    report = summarize(
        _canonical_engine_id(args.engine),
        canonical_model,
        args.source_revision,
        args.hardware_fingerprint,
        samples,
        engine_version=args.engine_version,
        model_revision=args.model_revision,
        tokenizer_revision=args.tokenizer_revision,
        model_license=args.model_license,
        environment_digest=args.environment_digest,
        workload=canonical_workload,
        rollback={
            "target_engine": _canonical_engine_id(args.rollback_target_engine),
            "target_model_revision": args.rollback_target_model_revision,
            "instructions": canonical_rollback_instructions,
        },
        budget=authority,
        run_id=run_id,
        started_at=started_at,
        completed_at=_utc_now(),
        blocked_reason=blocked_reason,
    )

    output = (
        Path(args.output)
        if args.output
        else Path("reports/inference-engine-benchmark") / f"{run_id}.json"
    )
    write_immutable_receipt(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] == "MEASURED":
        return 0
    return 3 if report["status"] == "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
