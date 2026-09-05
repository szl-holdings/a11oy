from szl_inference_engine_registry import (
    MATURITY_COMPATIBILITY,
    choose_candidates,
    eligible_for_promotion,
    engine,
    engines,
    invalid_promotion_evidence,
    missing_promotion_evidence,
)


def _complete_evidence():
    return {
        "benchmark_status": "MEASURED",
        "engine_id": "vllm",
        "model_revision": "1" * 40,
        "tokenizer_revision": "2" * 40,
        "p50_latency_ms": 10.0,
        "p95_latency_ms": 20.0,
        "p99_latency_ms": 30.0,
        "time_to_first_token_ms": 15.0,
        "tokens_per_second": 100.0,
        "peak_memory_mb": 4096,
        "structured_output_pass_rate": 1.0,
        "refusal_parity_pass": True,
        "governance_pass": True,
        "reproducibility_pass": True,
        "baseline_improvement_pass": True,
        "source_revision": "3" * 40,
        "hardware_fingerprint": "gpu:test",
        "receipt_sha256": "4" * 64,
        "receipt_signature_status": "UNSIGNED",
        "rollback_instructions": "Restore the pinned prior engine and model revision.",
    }


def test_registry_prioritizes_modern_candidates_and_keeps_tgi_compat_only():
    ids = [item.id for item in engines()]
    assert ids[:3] == ["vllm", "sglang", "transformers-v5-serve"]
    assert engine("tgi").maturity == MATURITY_COMPATIBILITY
    assert "tgi" not in [item.id for item in choose_candidates()]


def test_promotion_fails_closed_when_evidence_is_missing():
    assert eligible_for_promotion({}) is False
    assert "source_revision" in missing_promotion_evidence({})


def test_promotion_requires_governance_and_reproducibility():
    evidence = _complete_evidence()
    assert eligible_for_promotion(evidence) is True
    evidence["governance_pass"] = False
    assert eligible_for_promotion(evidence) is False
    evidence = _complete_evidence()
    evidence["reproducibility_pass"] = False
    assert eligible_for_promotion(evidence) is False


def test_promotion_rejects_truthy_strings_and_unavailable_identity():
    evidence = _complete_evidence()
    evidence["governance_pass"] = "false"
    evidence["reproducibility_pass"] = "false"
    evidence["source_revision"] = "UNAVAILABLE"
    evidence["hardware_fingerprint"] = "UNAVAILABLE"
    assert eligible_for_promotion(evidence) is False
    invalid = invalid_promotion_evidence(evidence)
    assert "governance_pass" in invalid
    assert "reproducibility_pass" in invalid
    assert "source_revision" in invalid
    assert "hardware_fingerprint" in invalid


def test_promotion_rejects_failed_or_compatibility_only_benchmark():
    evidence = _complete_evidence()
    evidence["benchmark_status"] = "FAILED"
    assert eligible_for_promotion(evidence) is False

    evidence = _complete_evidence()
    evidence["engine_id"] = "tgi"
    assert eligible_for_promotion(evidence) is False


def test_promotion_rejects_non_finite_or_disordered_metrics():
    evidence = _complete_evidence()
    evidence["p50_latency_ms"] = float("nan")
    assert eligible_for_promotion(evidence) is False

    evidence = _complete_evidence()
    evidence["p50_latency_ms"] = 40.0
    assert eligible_for_promotion(evidence) is False


def test_unknown_engine_is_not_silently_invented():
    assert engine("imaginary-engine") is None
