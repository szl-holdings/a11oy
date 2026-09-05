import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts import benchmark_inference_engines as benchmark
from scripts.benchmark_inference_engines import (
    Sample,
    budget_authorization,
    percentile,
    run_sample,
    summarize,
    verify_receipt,
    write_immutable_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "benchmark-result.schema.json").read_text(encoding="utf-8")
)
FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER


def _report(samples, *, blocked_reason=None):
    return summarize(
        "vllm",
        "example/model",
        "3" * 40,
        "cpu:test",
        samples,
        engine_version="1.2.3",
        model_revision="1" * 40,
        tokenizer_revision="2" * 40,
        model_license="Apache-2.0",
        environment_digest="sha256:" + "4" * 64,
        workload="cpu-safe-smoke/v1",
        rollback={
            "target_engine": "llama-cpp",
            "target_model_revision": "5" * 40,
            "instructions": "Restore the pinned llama.cpp baseline and verify readiness.",
        },
        budget={
            "allowed": blocked_reason is None,
            "mode": "LOCAL_UNMETERED" if blocked_reason is None else "BLOCKED_BUDGET",
            "budget_usd": None,
            "reason": "loopback fixture" if blocked_reason is None else blocked_reason,
        },
        run_id="00000000-0000-4000-8000-000000000001",
        started_at="2026-09-04T12:00:00Z",
        completed_at="2026-09-04T12:00:01Z",
        blocked_reason=blocked_reason,
    )


def _validate(report):
    Draft202012Validator(SCHEMA, format_checker=FORMAT_CHECKER).validate(report)


def test_percentile_is_deterministic():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0.50) == 25.0
    assert percentile(values, 0.95) == 38.5


def test_measured_summary_is_schema_valid_receipted_and_never_self_promotes():
    report = _report(
        [
            Sample(True, 200, 10.0, 5, request_id="run:1"),
            Sample(True, 200, 20.0, 10, request_id="run:2"),
        ]
    )
    _validate(report)
    assert report["classification"] == "MEASURED"
    assert report["status"] == "MEASURED"
    assert report["promotion_status"] == "NOT_EVALUATED"
    assert report["metrics"]["success_count"] == 2
    assert report["metrics"]["failure_count"] == 0
    assert report["receipt"]["signature_status"] == "UNSIGNED"
    assert verify_receipt(report) is True


def test_failures_are_failed_not_measured_and_keep_metrics_honest():
    report = _report(
        [Sample(False, 503, 5.0, None, "HTTP 503", "run:1")]
    )
    _validate(report)
    assert report["classification"] == "FAILED"
    assert report["status"] == "FAILED"
    assert report["metrics"]["failure_count"] == 1
    assert report["metrics"]["end_to_end_latency_ms_p50"] is None
    assert report["metrics"]["mean_output_tokens_per_second"] is None
    assert report["errors"] == ["HTTP 503"]


def test_external_endpoint_is_blocked_without_both_authorities():
    denied = budget_authorization("https://provider.example", None, {})
    assert denied["allowed"] is False
    assert denied["mode"] == "BLOCKED_BUDGET"

    still_denied = budget_authorization(
        "https://provider.example",
        10.0,
        {"SZL_ALLOW_METERED_INFERENCE_BAKEOFF": "0"},
    )
    assert still_denied["allowed"] is False

    allowed = budget_authorization(
        "https://provider.example",
        10.0,
        {"SZL_ALLOW_METERED_INFERENCE_BAKEOFF": "1"},
    )
    assert allowed["allowed"] is True
    assert allowed["budget_usd"] == 10.0


def test_cli_blocks_remote_before_adapter_and_writes_blocked_receipt(
    monkeypatch, tmp_path, capsys
):
    output = tmp_path / "blocked.json"

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("network adapter must not run without budget authority")

    monkeypatch.delenv("SZL_ALLOW_METERED_INFERENCE_BAKEOFF", raising=False)
    monkeypatch.setattr(benchmark, "run_sample", forbidden_network)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_inference_engines.py",
            "--engine",
            "vllm",
            "--engine-version",
            "1.2.3",
            "--base-url",
            "https://provider.example",
            "--model",
            "example/model",
            "--model-revision",
            "1" * 40,
            "--tokenizer-revision",
            "2" * 40,
            "--model-license",
            "Apache-2.0",
            "--environment-digest",
            "sha256:" + "4" * 64,
            "--source-revision",
            "3" * 40,
            "--hardware-fingerprint",
            "cpu:test",
            "--rollback-target-engine",
            "llama-cpp",
            "--rollback-target-model-revision",
            "5" * 40,
            "--rollback-instructions",
            "Restore the pinned llama.cpp baseline and verify readiness.",
            "--output",
            str(output),
        ],
    )
    assert benchmark.main() == 3
    capsys.readouterr()
    report = json.loads(output.read_text(encoding="utf-8"))
    _validate(report)
    assert report["status"] == "BLOCKED"
    assert report["request_ids"] == []
    assert verify_receipt(report) is True


def test_cli_identity_rejects_unavailable_hardware():
    with pytest.raises(ValueError, match="hardware fingerprint"):
        benchmark._validate_identity(
            engine_id="vllm",
            engine_version="1.2.3",
            model_revision="1" * 40,
            tokenizer_revision="2" * 40,
            source_revision="3" * 40,
            hardware_fingerprint="UNAVAILABLE",
            environment_digest="sha256:" + "4" * 64,
            model_license="Apache-2.0",
        )


def test_accepted_identity_variants_are_canonicalized_before_receipting():
    model_revision = "  " + "A" * 40 + "  "
    tokenizer_revision = "\tSHA256:" + "B" * 64 + "\n"
    source_revision = " " + "C" * 64 + " "
    environment_digest = " SHA256:" + "D" * 64 + " "
    rollback_revision = "\t" + "E" * 40 + " "

    benchmark._validate_identity(
        engine_id=" VLLM ",
        engine_version="1.2.3",
        model_revision=model_revision,
        tokenizer_revision=tokenizer_revision,
        source_revision=source_revision,
        hardware_fingerprint="cpu:test",
        environment_digest=environment_digest,
        model_license="Apache-2.0",
    )
    report = summarize(
        " VLLM ",
        " example/model ",
        source_revision,
        " cpu:test ",
        [Sample(True, 200, 10.0, 5, request_id="run:1")],
        engine_version="1.2.3",
        model_revision=model_revision,
        tokenizer_revision=tokenizer_revision,
        model_license=" Apache-2.0 ",
        environment_digest=environment_digest,
        workload=" cpu-safe-smoke/v1 ",
        rollback={
            "target_engine": " LLAMA-CPP ",
            "target_model_revision": rollback_revision,
            "instructions": "Restore the pinned llama.cpp baseline and verify readiness.",
        },
        budget={
            "allowed": True,
            "mode": "LOCAL_UNMETERED",
            "budget_usd": None,
            "reason": "loopback fixture",
        },
        run_id="00000000-0000-4000-8000-000000000002",
        started_at="2026-09-04T12:00:00Z",
        completed_at="2026-09-04T12:00:01Z",
    )

    _validate(report)
    assert report["engine"] == "vllm"
    assert report["model"] == "example/model"
    assert report["model_revision"] == "a" * 40
    assert report["tokenizer_revision"] == "sha256:" + "b" * 64
    assert report["model_license"] == "Apache-2.0"
    assert report["source_revision"] == "c" * 64
    assert report["hardware_fingerprint"] == "cpu:test"
    assert report["environment_digest"] == "sha256:" + "d" * 64
    assert report["workload"] == "cpu-safe-smoke/v1"
    assert report["rollback"]["target_engine"] == "llama-cpp"
    assert report["rollback"]["target_model_revision"] == "e" * 40
    assert verify_receipt(report) is True


def test_loopback_is_cpu_safe_without_metered_authority():
    authority = budget_authorization("http://127.0.0.1:8000", None, {})
    assert authority == {
        "allowed": True,
        "mode": "LOCAL_UNMETERED",
        "budget_usd": None,
        "reason": "loopback endpoint; no provider spend authorized",
    }


def test_blocked_budget_receipt_is_schema_valid_and_not_measured():
    reason = "external benchmark is BLOCKED_BUDGET; no request was sent"
    report = _report([], blocked_reason=reason)
    _validate(report)
    assert report["classification"] == "BLOCKED"
    assert report["metrics"]["sample_count"] == 0
    assert report["budget_authorization"]["allowed"] is False
    assert verify_receipt(report) is True


def test_receipt_detects_tampering_and_is_write_once(tmp_path):
    report = _report([Sample(True, 200, 10.0, 5, request_id="run:1")])
    target = tmp_path / "receipt.json"
    write_immutable_receipt(target, report)
    assert json.loads(target.read_text(encoding="utf-8")) == report
    with pytest.raises(FileExistsError):
        write_immutable_receipt(target, report)

    tampered = json.loads(json.dumps(report))
    tampered["metrics"]["success_count"] = 99
    assert verify_receipt(tampered) is False


def test_schema_rejects_status_classification_mismatch():
    report = _report([Sample(True, 200, 10.0, 5, request_id="run:1")])
    report["classification"] = "FAILED"
    with pytest.raises(ValidationError):
        _validate(report)


def test_cpu_safe_openai_adapter_smoke_and_malformed_response_fail_closed():
    class Handler(BaseHTTPRequestHandler):
        payload = {
            "choices": [{"message": {"content": "A11OY_BENCH_OK"}}],
            "usage": {"completion_tokens": 3},
        }
        received = {}

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            type(self).received = {
                "path": self.path,
                "request_id": self.headers.get("X-Request-ID"),
                "body": json.loads(self.rfile.read(length)),
            }
            raw = json.dumps(type(self).payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        sample = run_sample(
            base,
            "example/model",
            "Return exactly: A11OY_BENCH_OK",
            2.0,
            None,
            request_id="cpu-smoke:1",
        )
        assert sample.ok is True
        assert sample.output_tokens == 3
        assert sample.request_id == "cpu-smoke:1"
        assert Handler.received["path"] == "/v1/chat/completions"
        assert Handler.received["request_id"] == "cpu-smoke:1"
        assert Handler.received["body"]["stream"] is False

        Handler.payload = {"not_choices": []}
        malformed = run_sample(
            base,
            "example/model",
            "test",
            2.0,
            None,
            request_id="cpu-smoke:2",
        )
        assert malformed.ok is False
        assert malformed.error == "ValueError"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
