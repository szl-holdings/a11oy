from szl_inference_engine_registry import (
    MATURITY_COMPATIBILITY,
    choose_candidates,
    eligible_for_promotion,
    engine,
    engines,
    missing_promotion_evidence,
)


def _complete_evidence():
    return {
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
        "source_revision": "abc123",
        "hardware_fingerprint": "gpu:test",
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


def test_unknown_engine_is_not_silently_invented():
    assert engine("imaginary-engine") is None
