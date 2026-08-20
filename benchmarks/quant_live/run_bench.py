# SPDX-License-Identifier: Apache-2.0
"""Execute the bounded, on-metal SZL quant/model verification harness.

The CLI is the measurement write boundary. It calls two real local Ollama tags,
records native timing counters, runs predeclared exact-match and bounded needle
probes, times the existing CPU quant reference, and writes a content-addressed
receipt. DSSE is signed only when the approved runtime key is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import szl_gpu_quant as quant  # noqa: E402

SCHEMA = "szl.quant-live-benchmark-receipt.v1"
PAYLOAD_TYPE = "application/vnd.szl.quant-live-benchmark+json"
DEFAULT_OUTPUT = Path.home() / ".a11oy" / "receipts" / "quant-live-benchmark.json"

TASKS = (
    ("literal", "Reply with exactly: A11OY", "A11OY"),
    ("multiply", "Compute 7*8 and reply with only the integer.", "56"),
    ("divide", "What is 144 divided by 12? Reply only with the integer.", "12"),
    (
        "policy",
        "Return DENY if an unauthenticated request asks to delete production data. Reply with one word only.",
        "DENY",
    ),
    ("prime", "Is 17 prime? Reply with exactly YES or NO.", "YES"),
    ("sequence", "What is the next number: 2, 4, 8, 16? Reply only with the integer.", "32"),
)


def _require_loopback_base_url(value: str) -> None:
    """Refuse remote or credential-bearing Ollama endpoints.

    This harness emits a *local* execution receipt. Allowing an arbitrary URL
    would both violate that scope and turn an operator CLI into a network probe.
    """
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Ollama base URL has an invalid port") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port is None
    ):
        raise ValueError("Ollama base URL must be a credential-free loopback HTTP endpoint with an explicit port")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _normalize_answer(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split()).strip("`.* ")


def _post_json_endpoint(
    base_url: str, endpoint: str, body: dict[str, Any], timeout_s: float
) -> tuple[dict[str, Any], float]:
    if endpoint not in {"/api/generate", "/api/show"}:
        raise ValueError("unsupported Ollama endpoint")
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint,
        data=_canonical(body),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - local operator endpoint
        payload = json.loads(response.read().decode("utf-8"))
    return payload, (time.perf_counter() - started) * 1000.0


def _post_json(base_url: str, body: dict[str, Any], timeout_s: float) -> tuple[dict[str, Any], float]:
    return _post_json_endpoint(base_url, "/api/generate", body, timeout_s)


_SHA256_RE = re.compile(r"(?i)(?:sha256:)?([0-9a-f]{64})")
_SAFE_LINEAGE_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,255}")
_WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)^[a-z]:[\\/]")


def _digest_from_ref(value: Any) -> str | None:
    match = _SHA256_RE.search(str(value or ""))
    return match.group(1).lower() if match else None


def _safe_lineage_ref(value: Any, field: str) -> str | None:
    """Return a bounded public lineage reference without host-path disclosure.

    Ollama Modelfiles can expand a content-addressed ``FROM`` instruction to
    the host's absolute blob path.  The path is neither portable provenance
    nor safe publication metadata.  Preserve its immutable SHA-256 identity
    when present; otherwise reject path-like or malformed lineage instead of
    copying it into a receipt.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    digest = _digest_from_ref(raw)
    if digest:
        return "sha256:" + digest
    path_like = (
        _WINDOWS_ABSOLUTE_RE.match(raw) is not None
        or raw.startswith(("/", "\\", "~/", "~\\", "file:"))
        or "\\" in raw
        or any(part in {".", "..", "~"} for part in raw.split("/"))
    )
    if path_like:
        raise ValueError("Ollama /api/show exposed unsafe %s path without a SHA-256 digest" % field)
    if not _SAFE_LINEAGE_REF_RE.fullmatch(raw):
        raise ValueError("Ollama /api/show exposed an invalid or overlong %s reference" % field)
    return raw


def _ollama_identity(base_url: str, model: str, timeout_s: float) -> dict[str, Any]:
    """Bind a mutable Ollama tag to the exact manifest returned by /api/show."""
    payload, wall_ms = _post_json_endpoint(
        base_url, "/api/show", {"model": model, "verbose": True}, timeout_s
    )
    if not isinstance(payload, dict):
        raise ValueError("Ollama /api/show returned a non-object")
    modelfile = payload.get("modelfile")
    if not isinstance(modelfile, str):
        modelfile = ""
    base_ref = None
    for line in modelfile.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("FROM "):
            base_ref = stripped[5:].strip()
            break
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    model_info = payload.get("model_info") if isinstance(payload.get("model_info"), dict) else {}
    digest_candidates = [payload.get("digest"), base_ref, details.get("parent_model")]
    reported_digest = None
    for candidate in digest_candidates:
        match = _SHA256_RE.search(str(candidate or ""))
        if match:
            reported_digest = match.group(1).lower()
            break
    safe_base_ref = _safe_lineage_ref(base_ref, "base-lineage")
    safe_parent_model = _safe_lineage_ref(details.get("parent_model"), "parent-model")
    if not safe_base_ref and not safe_parent_model and not reported_digest:
        raise ValueError("Ollama /api/show did not expose manifest or base-lineage evidence")
    return {
        "requested_model": model,
        "show_response_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
        "show_wall_ms": round(wall_ms, 3),
        "reported_digest": reported_digest,
        "base_lineage": {
            "base_ref": safe_base_ref,
            "parent_model": safe_parent_model,
            "base_digest": reported_digest,
        },
        "details": {
            key: details.get(key)
            for key in ("format", "family", "families", "parameter_size", "quantization_level")
            if details.get(key) is not None
        },
        "model_info": {
            key: model_info.get(key)
            for key in (
                "general.architecture",
                "general.name",
                "general.file_type",
                "general.parameter_count",
            )
            if model_info.get(key) is not None
        },
    }


def _generate(base_url: str, model: str, prompt: str, timeout_s: float, num_predict: int = 64) -> dict[str, Any]:
    payload, wall_ms = _post_json(
        base_url,
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {"temperature": 0, "seed": 42, "num_predict": num_predict},
        },
        timeout_s,
    )
    eval_count = int(payload.get("eval_count") or 0)
    eval_ns = int(payload.get("eval_duration") or 0)
    return {
        "response": str(payload.get("response") or ""),
        "done_reason": payload.get("done_reason"),
        "wall_ms": round(wall_ms, 3),
        "total_duration_ms": round(int(payload.get("total_duration") or 0) / 1_000_000.0, 3),
        "load_duration_ms": round(int(payload.get("load_duration") or 0) / 1_000_000.0, 3),
        "prompt_eval_count": int(payload.get("prompt_eval_count") or 0),
        "eval_count": eval_count,
        "tokens_per_second": round(eval_count / (eval_ns / 1_000_000_000.0), 3) if eval_count and eval_ns else None,
    }


def _gpu_inventory() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,driver_version,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "error": type(exc).__name__, "devices": []}
    devices = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 8:
            continue
        devices.append(
            {
                "index": int(parts[0]),
                "name": parts[1],
                "driver_version": parts[2],
                "memory_total_mib": float(parts[3]),
                "memory_used_mib": float(parts[4]),
                "utilization_pct": float(parts[5]),
                "temperature_c": float(parts[6]),
                "power_w": float(parts[7]),
            }
        )
    return {"available": bool(devices), "devices": devices}


def _model_measurement(base_url: str, model: str, timeout_s: float) -> dict[str, Any]:
    warmup = _generate(base_url, model, "Reply with exactly: WARM", timeout_s, num_predict=16)
    exact_rows = []
    for task_id, prompt, expected in TASKS:
        result = _generate(base_url, model, prompt, timeout_s)
        actual = _normalize_answer(result.pop("response"))
        exact_rows.append(
            {"task_id": task_id, "expected": expected, "actual": actual, "passed": actual == expected, **result}
        )

    needle_rows = []
    for words, needle in ((256, "KHIPU-7319"), (768, "OUROBOROS-2048")):
        filler = " ".join("context_%04d" % idx for idx in range(words))
        prompt = (
            "Read the context and return only the value after BOUND_TOKEN=.\n"
            + filler
            + "\nBOUND_TOKEN="
            + needle
            + "\nQuestion: What is BOUND_TOKEN?"
        )
        result = _generate(base_url, model, prompt, timeout_s)
        actual = _normalize_answer(result.pop("response"))
        needle_rows.append(
            {
                "declared_context_words": words,
                "needle": needle,
                "actual": actual,
                "passed": actual == needle,
                **result,
            }
        )

    exact_passed = sum(1 for row in exact_rows if row["passed"])
    needle_passed = sum(1 for row in needle_rows if row["passed"])
    inference_rows = exact_rows + needle_rows
    throughput = [row["tokens_per_second"] for row in inference_rows if row["tokens_per_second"] is not None]
    return {
        "model": model,
        "warmup": warmup,
        "exact_match": {
            "tasks_total": len(exact_rows),
            "tasks_passed": exact_passed,
            "accuracy_pct": round(100.0 * exact_passed / len(exact_rows), 3),
            "rows": exact_rows,
        },
        "bounded_retrieval": {
            "probes_total": len(needle_rows),
            "probes_passed": needle_passed,
            "max_prompt_eval_tokens": max((row["prompt_eval_count"] for row in needle_rows), default=0),
            "rows": needle_rows,
        },
        "runtime": {
            "requests": len(inference_rows),
            "p50_wall_ms": round(statistics.median(row["wall_ms"] for row in inference_rows), 3),
            "p50_tokens_per_second": round(statistics.median(throughput), 3) if throughput else None,
        },
    }


def _time_call(fn, repeats: int) -> dict[str, Any]:
    samples = []
    last = None
    for _ in range(repeats):
        started = time.perf_counter()
        last = fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return {
        "repeats": repeats,
        "p50_ms": round(statistics.median(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "compute_path": (last or {}).get("compute_backend", {}).get("compute_path", "CPU_REFERENCE"),
    }


def run(base_url: str, candidate: str, baseline: str, timeout_s: float, repeats: int) -> dict[str, Any]:
    _require_loopback_base_url(base_url)
    if candidate.strip() == baseline.strip():
        raise ValueError("candidate and baseline must be distinct Ollama tags")
    started_at = datetime.now(timezone.utc).isoformat()
    candidate_identity_before = _ollama_identity(base_url, candidate, timeout_s)
    baseline_identity_before = _ollama_identity(base_url, baseline, timeout_s)
    if candidate_identity_before["show_response_sha256"] == baseline_identity_before["show_response_sha256"]:
        raise ValueError("candidate and baseline resolve to the same Ollama manifest")
    candidate_result = _model_measurement(base_url, candidate, timeout_s)
    baseline_result = _model_measurement(base_url, baseline, timeout_s)
    pca = _time_call(lambda: quant.run_pipeline(stress=False), repeats)
    tda = _time_call(lambda: quant.run_pipeline(stress=True), repeats)
    candidate_identity_after = _ollama_identity(base_url, candidate, timeout_s)
    baseline_identity_after = _ollama_identity(base_url, baseline, timeout_s)
    candidate_stable = (
        candidate_identity_before["show_response_sha256"]
        == candidate_identity_after["show_response_sha256"]
    )
    baseline_stable = (
        baseline_identity_before["show_response_sha256"]
        == baseline_identity_after["show_response_sha256"]
    )
    if not candidate_stable or not baseline_stable:
        raise ValueError("Ollama model identity drifted during benchmark; receipt refused")

    c_latency = candidate_result["runtime"]["p50_wall_ms"]
    b_latency = baseline_result["runtime"]["p50_wall_ms"]
    c_accuracy = candidate_result["exact_match"]["accuracy_pct"]
    b_accuracy = baseline_result["exact_match"]["accuracy_pct"]
    body: dict[str, Any] = {
        "schema_version": SCHEMA,
        "measurement_class": "MEASURED",
        "scope": "bounded local execution; not a replication of vendor-scale claims",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": platform.platform(), "python": platform.python_version(), "gpu": _gpu_inventory()},
        "ollama": {
            "base_url_class": "loopback-local",
            "candidate_identity": candidate_identity_before,
            "baseline_identity": baseline_identity_before,
            "identity_stability": {
                "candidate_before_sha256": candidate_identity_before["show_response_sha256"],
                "candidate_after_sha256": candidate_identity_after["show_response_sha256"],
                "baseline_before_sha256": baseline_identity_before["show_response_sha256"],
                "baseline_after_sha256": baseline_identity_after["show_response_sha256"],
                "stable": True,
            },
            "candidate": candidate_result,
            "baseline": baseline_result,
        },
        "comparisons": {
            "candidate_vs_baseline_wall_speed_ratio": round(b_latency / c_latency, 4) if c_latency else None,
            "candidate_minus_baseline_exact_match_points": round(c_accuracy - b_accuracy, 3),
        },
        "quant_reference": {
            "pca_pipeline": pca,
            "tda_stress_pipeline": tda,
            "gpu_acceleration_comparison": "UNAVAILABLE: no distinct cuML/CuPy/Ripser++ execution receipt",
        },
        "limitations": [
            "Candidate and baseline differ in architecture and size; results are not vendor-claim replications.",
            "Exact-match and needle suites are bounded operational probes, not general capability benchmarks.",
            "PCA/TDA timings exercise the existing CPU reference path only.",
            "No energy claim is made without an independently verified interval energy meter.",
        ],
    }
    body["content_sha256"] = hashlib.sha256(_canonical(body)).hexdigest()
    try:
        from szl_dsse import sign_payload

        dsse = sign_payload(body, PAYLOAD_TYPE)
    except Exception as exc:
        dsse = {"signed": False, "signatures": [], "error": type(exc).__name__}
    return {"receipt": body, "dsse": dsse}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--candidate", default=os.environ.get("SZL_LOCAL_LLM_MODEL", "szl-nemo:latest"))
    parser.add_argument("--baseline", default="qwen2.5:3b")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("SZL_QUANT_BENCH_RECEIPT", DEFAULT_OUTPUT)))
    args = parser.parse_args()
    if not (1 <= args.repeats <= 20):
        parser.error("--repeats must be between 1 and 20")
    try:
        _require_loopback_base_url(args.base_url)
        output = run(args.base_url, args.candidate, args.baseline, args.timeout, args.repeats)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print("benchmark refused: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps({"ok": True, "path": str(args.output), "receipt": output["receipt"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
