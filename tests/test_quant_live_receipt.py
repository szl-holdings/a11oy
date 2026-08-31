"""Receipt-gated verification for the bounded local quant harness."""

from __future__ import annotations

import hashlib
import json
import base64
from datetime import datetime, timedelta, timezone

import pytest

import szl_gpu_quant as quant
from benchmarks.quant_live import run_bench as bench


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _measurement(model: str, passed: int, latency: float) -> dict:
    return {
        "model": model,
        "exact_match": {"accuracy_pct": round(100 * passed / 6, 3), "tasks_passed": passed, "tasks_total": 6},
        "bounded_retrieval": {"probes_passed": 2, "probes_total": 2, "max_prompt_eval_tokens": 1024},
        "runtime": {"requests": 8, "p50_wall_ms": latency, "p50_tokens_per_second": 28.5},
    }


def _identity(model: str, digest: str) -> dict:
    return {
        "requested_model": model,
        "show_response_sha256": digest,
        "show_wall_ms": 3.5,
        "reported_digest": digest,
        "base_lineage": {"base_ref": "sha256:" + digest, "parent_model": None, "base_digest": digest},
        "details": {"family": "qwen2"},
        "model_info": {"general.architecture": "qwen2"},
    }


def _receipt(completed_at: datetime | None = None):
    completed = completed_at or datetime.now(timezone.utc)
    started = completed - timedelta(minutes=3)
    candidate_hash = "a" * 64
    baseline_hash = "b" * 64
    body = {
        "schema_version": "szl.quant-live-benchmark-receipt.v1",
        "measurement_class": "MEASURED",
        "scope": "bounded local execution; not a replication of vendor-scale claims",
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "ollama": {
            "base_url_class": "loopback-local",
            "candidate_identity": _identity("szl-nemo:latest", candidate_hash),
            "baseline_identity": _identity("qwen2.5:3b", baseline_hash),
            "identity_stability": {
                "candidate_before_sha256": candidate_hash,
                "candidate_after_sha256": candidate_hash,
                "baseline_before_sha256": baseline_hash,
                "baseline_after_sha256": baseline_hash,
                "stable": True,
            },
            "candidate": _measurement("szl-nemo:latest", 5, 80.0),
            "baseline": _measurement("qwen2.5:3b", 4, 100.0),
        },
        "comparisons": {
            "candidate_vs_baseline_wall_speed_ratio": 1.25,
            "candidate_minus_baseline_exact_match_points": 16.666,
        },
        "quant_reference": {
            "pca_pipeline": {
                "repeats": 3, "p50_ms": 12.5, "min_ms": 12.0, "max_ms": 13.0,
                "compute_path": "CPU_REFERENCE",
            },
            "tda_stress_pipeline": {
                "repeats": 3, "p50_ms": 18.75, "min_ms": 18.0, "max_ms": 19.5,
                "compute_path": "CPU_REFERENCE",
            },
            "gpu_acceleration_comparison": "UNAVAILABLE: no distinct cuML/CuPy/Ripser++ execution receipt",
        },
    }
    body["content_sha256"] = hashlib.sha256(_canonical(body)).hexdigest()
    return {"receipt": body, "dsse": {"signed": False, "signatures": []}}


def _rehash(value):
    value["receipt"].pop("content_sha256", None)
    value["receipt"]["content_sha256"] = hashlib.sha256(_canonical(value["receipt"])).hexdigest()


def _claim_signed(value):
    value["dsse"] = {
        "payloadType": "application/vnd.szl.quant-live-benchmark+json",
        "payload": base64.b64encode(_canonical(value["receipt"])).decode("ascii"),
        "signatures": [
            {
                "keyid": "fixture",
                "sig": base64.b64encode(b"not-a-real-signature").decode("ascii"),
            }
        ],
        "signed": True,
    }
    return value


def _write(tmp_path, monkeypatch, value):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setenv("SZL_QUANT_BENCH_RECEIPT", str(path))


def test_valid_receipt_separates_gpu_claims_from_local_and_cpu_evidence(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, _receipt())
    monkeypatch.setattr(quant, "_gpu_reachable", lambda state=None: True)
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is True
    assert panel["receipt"]["freshness_state"] == "CURRENT"
    assert panel["receipt"]["signature_state"] == "UNSIGNED_CONTENT_ADDRESSED"
    assert all(row["nvidia_label"] == "REPORTED" for row in panel["rows"])
    for index in (0, 4, 5):
        assert panel["rows"][index]["szl_label"] == "NOT_MEASURED"
        assert panel["rows"][index]["szl_measured"] is None
        assert panel["rows"][index]["local_reference_label"] == "MEASURED"
    assert "1.25x local Ollama" in panel["rows"][0]["local_reference"]
    assert all(panel["rows"][index]["szl_label"] == "MEASURED" for index in (1, 2, 3))
    assert "CPU reference" in panel["rows"][4]["local_reference"]


def test_signed_receipt_requires_positive_cryptographic_verdict(tmp_path, monkeypatch):
    value = _claim_signed(_receipt())
    _write(tmp_path, monkeypatch, value)
    monkeypatch.setattr(quant, "_verify_envelope", lambda envelope: {"verified": True})
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is True
    assert panel["receipt"]["signature_state"] == "SIGNED_VERIFIED"
    assert panel["receipt"]["dsse_signed"] is True
    assert "cryptographically verified DSSE" in panel["summary"]


def test_forged_signed_receipt_fails_closed(tmp_path, monkeypatch):
    value = _claim_signed(_receipt())
    _write(tmp_path, monkeypatch, value)
    monkeypatch.setattr(
        quant,
        "_verify_envelope",
        lambda envelope: {"verified": False, "reason": "signature mismatch"},
    )
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is False
    assert panel["receipt"]["signature_state"] == "NO_RECEIPT"
    assert panel["receipt"]["dsse_signed"] is False
    assert "DSSE signature verification failed: signature mismatch" in panel["receipt"]["error"]


def test_unsigned_quant_html_never_calls_receipt_signed(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, _receipt())
    monkeypatch.setattr(
        quant,
        "_sign_payload",
        lambda payload, payload_type: {
            "payloadType": payload_type,
            "payload": base64.b64encode(_canonical(payload)).decode("ascii"),
            "signatures": [],
            "signed": False,
            "_pae_sha256": "e" * 64,
        },
    )
    monkeypatch.setattr(quant, "_gpu_reachable", lambda state=None: False)
    pipe = quant.run_pipeline()
    html = quant._html(pipe, quant.tiers_panel(), quant.verify_claims_panel())
    assert "Unsigned SAMPLE Receipt" in html
    assert "DSSE receipt: UNSIGNED_CONTENT_ADDRESSED" in html
    assert "each a SIGNED receipt" not in html
    assert "Signed SAMPLE Receipt" not in html


def test_missing_receipt_is_not_relabeled_as_measured(tmp_path, monkeypatch):
    monkeypatch.setenv("SZL_QUANT_BENCH_RECEIPT", str(tmp_path / "missing.json"))
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is False
    assert panel["receipt"]["signature_state"] == "NO_RECEIPT"
    assert all(row["szl_label"] == "NOT_MEASURED" for row in panel["rows"])
    assert all(row["local_reference_label"] == "NOT_MEASURED" for row in panel["rows"])


def test_tampered_receipt_fails_closed(tmp_path, monkeypatch):
    value = _receipt()
    value["receipt"]["comparisons"]["candidate_vs_baseline_wall_speed_ratio"] = 99.0
    _write(tmp_path, monkeypatch, value)
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is False
    assert "digest mismatch" in panel["receipt"]["error"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value["receipt"].__setitem__("measurement_class", "OPEN"), "not a completed MEASURED"),
        (lambda value: value["receipt"]["ollama"].__setitem__("base_url_class", "remote"), "loopback-local"),
        (lambda value: value["receipt"]["ollama"]["candidate"]["runtime"].__setitem__("p50_wall_ms", float("nan")), "finite number"),
        (lambda value: value["receipt"]["ollama"]["identity_stability"].__setitem__("stable", False), "stability is not proven"),
    ],
)
def test_semantically_invalid_receipts_fail_closed(tmp_path, monkeypatch, mutate, message):
    value = _receipt()
    mutate(value)
    _rehash(value)
    _write(tmp_path, monkeypatch, value)
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is False
    assert message in panel["receipt"]["error"]


def test_valid_old_receipt_is_visible_only_as_historical(tmp_path, monkeypatch):
    value = _receipt(datetime.now(timezone.utc) - timedelta(days=30))
    _write(tmp_path, monkeypatch, value)
    panel = quant.verify_claims_panel()
    assert panel["receipt"]["loaded"] is True
    assert panel["receipt"]["freshness_state"] == "HISTORICAL"
    assert all(row["freshness_label"] == "HISTORICAL" for row in panel["rows"])


def test_ollama_identity_binds_manifest_and_base_lineage(monkeypatch):
    payload = {
        "modelfile": "FROM sha256:" + "c" * 64 + "\nPARAMETER temperature 0",
        "details": {"family": "qwen2", "parameter_size": "1.5B"},
        "model_info": {"general.architecture": "qwen2"},
    }
    monkeypatch.setattr(bench, "_post_json_endpoint", lambda *args: (payload, 4.25))
    identity = bench._ollama_identity("http://127.0.0.1:11434", "szl-nemo:latest", 5)
    assert identity["base_lineage"]["base_digest"] == "c" * 64
    assert identity["show_response_sha256"] == hashlib.sha256(_canonical(payload)).hexdigest()


def test_ollama_identity_redacts_absolute_blob_path_to_content_digest(monkeypatch):
    digest = "d" * 64
    payload = {
        "modelfile": "FROM C:\\Users\\alice\\.ollama\\models\\blobs\\sha256-" + digest,
        "details": {"family": "nemotron_h", "parameter_size": "4.0B"},
        "model_info": {"general.architecture": "nemotron_h"},
    }
    monkeypatch.setattr(bench, "_post_json_endpoint", lambda *args: (payload, 4.25))
    identity = bench._ollama_identity("http://127.0.0.1:11434", "szl-nemo:latest", 5)
    encoded = json.dumps(identity)
    assert identity["base_lineage"]["base_ref"] == "sha256:" + digest
    assert "alice" not in encoded
    assert "C:\\\\Users" not in encoded


@pytest.mark.parametrize(
    "unsafe_ref",
    (
        r"C:\\Users\\alice\\.ollama\\models\\blobs\\model.bin",
        "/home/alice/.ollama/models/blobs/model.bin",
        r"..\\private\\model.bin",
    ),
)
def test_ollama_identity_refuses_unsafe_lineage_without_digest(monkeypatch, unsafe_ref):
    payload = {
        "modelfile": "FROM " + unsafe_ref,
        "details": {"family": "qwen2"},
        "model_info": {"general.architecture": "qwen2"},
    }
    monkeypatch.setattr(bench, "_post_json_endpoint", lambda *args: (payload, 4.25))
    with pytest.raises(ValueError, match="unsafe base-lineage path"):
        bench._ollama_identity("http://127.0.0.1:11434", "szl-nemo:latest", 5)


def test_ollama_identity_retains_bounded_public_model_tag(monkeypatch):
    payload = {
        "modelfile": "FROM registry.example/SZLHOLDINGS/szl-nemo:4b-q4",
        "details": {"family": "nemotron_h"},
        "model_info": {"general.architecture": "nemotron_h"},
    }
    monkeypatch.setattr(bench, "_post_json_endpoint", lambda *args: (payload, 4.25))
    identity = bench._ollama_identity("http://127.0.0.1:11434", "szl-nemo:latest", 5)
    assert identity["base_lineage"]["base_ref"] == "registry.example/SZLHOLDINGS/szl-nemo:4b-q4"


def test_benchmark_refuses_manifest_drift_without_writing_a_receipt(monkeypatch):
    calls = {"szl-nemo:latest": 0, "qwen2.5:3b": 0}

    def identity(_base_url, model, _timeout):
        calls[model] += 1
        digest = ("a" if model.startswith("szl") else "b") * 64
        if model.startswith("szl") and calls[model] == 2:
            digest = "d" * 64
        return _identity(model, digest)

    monkeypatch.setattr(bench, "_ollama_identity", identity)
    monkeypatch.setattr(
        bench, "_model_measurement",
        lambda _base_url, model, _timeout: _measurement(model, 5 if model.startswith("szl") else 4, 80 if model.startswith("szl") else 100),
    )
    monkeypatch.setattr(
        bench, "_time_call",
        lambda _fn, repeats: {"repeats": repeats, "p50_ms": 1.0, "min_ms": 0.9, "max_ms": 1.1, "compute_path": "CPU_REFERENCE"},
    )
    with pytest.raises(ValueError, match="identity drifted"):
        bench.run("http://127.0.0.1:11434", "szl-nemo:latest", "qwen2.5:3b", 5, 1)


def test_benchmark_cli_refuses_non_loopback_or_credentialed_endpoints():
    for value in (
        "https://example.com:11434",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434/api/generate",
        "http://127.0.0.1",
    ):
        with pytest.raises(ValueError):
            bench._require_loopback_base_url(value)
    bench._require_loopback_base_url("http://127.0.0.1:11434")
    bench._require_loopback_base_url("http://localhost:11435/")
