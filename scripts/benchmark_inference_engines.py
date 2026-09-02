#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Benchmark OpenAI-compatible inference engines without fabricating evidence.

The harness measures only what it actually observes. It never marks an engine
production-qualified. Results are bound to engine/model/source identifiers and
sealed with a deterministic SHA-256 receipt over canonical JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sample:
    ok: bool
    status: int | None
    latency_ms: float
    output_tokens: int | None
    error: str | None = None


def canonical_sha256(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def run_sample(base_url: str, model: str, prompt: str, timeout: float, api_key: str | None) -> Sample:
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "stream": False,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            elapsed = (time.perf_counter() - started) * 1000.0
            parsed = json.loads(raw.decode("utf-8"))
            usage = parsed.get("usage") if isinstance(parsed, dict) else None
            out_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            return Sample(True, int(response.status), elapsed, out_tokens)
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000.0
        return Sample(False, int(exc.code), elapsed, None, f"HTTP {exc.code}")
    except Exception as exc:  # fail-closed, secret-free error class only
        elapsed = (time.perf_counter() - started) * 1000.0
        return Sample(False, None, elapsed, None, type(exc).__name__)


def summarize(engine_id: str, model: str, source_revision: str, hardware_fingerprint: str, samples: list[Sample]) -> dict:
    good = [s for s in samples if s.ok]
    latencies = [s.latency_ms for s in good]
    token_rates = [
        s.output_tokens / (s.latency_ms / 1000.0)
        for s in good
        if s.output_tokens is not None and s.latency_ms > 0
    ]
    result = {
        "schema_version": 1,
        "classification": "MEASURED",
        "promotion_status": "NOT_EVALUATED",
        "engine_id": engine_id,
        "model": model,
        "source_revision": source_revision,
        "hardware_fingerprint": hardware_fingerprint,
        "sample_count": len(samples),
        "success_count": len(good),
        "failure_count": len(samples) - len(good),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "mean_tokens_per_second": statistics.fmean(token_rates) if token_rates else None,
        "errors": [s.error for s in samples if s.error],
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="Return exactly: A11OY_BENCH_OK")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--source-revision", default=os.getenv("GITHUB_SHA", "UNAVAILABLE"))
    parser.add_argument("--hardware-fingerprint", default=os.getenv("A11OY_HARDWARE_FINGERPRINT", "UNAVAILABLE"))
    parser.add_argument("--api-key-env", default="A11OY_BENCH_API_KEY")
    parser.add_argument("--output", default="reports/inference-engine-benchmark.json")
    args = parser.parse_args()

    if args.samples < 1:
        raise SystemExit("--samples must be >= 1")

    api_key = os.getenv(args.api_key_env) if args.api_key_env else None
    samples = [run_sample(args.base_url, args.model, args.prompt, args.timeout, api_key) for _ in range(args.samples)]
    report = summarize(args.engine, args.model, args.source_revision, args.hardware_fingerprint, samples)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
