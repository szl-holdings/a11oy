from scripts.benchmark_inference_engines import Sample, canonical_sha256, percentile, summarize


def test_percentile_is_deterministic():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0.50) == 25.0
    assert percentile(values, 0.95) == 38.5


def test_summary_never_self_promotes():
    report = summarize(
        "vllm",
        "example/model",
        "abc123",
        "gpu:test",
        [Sample(True, 200, 10.0, 5), Sample(True, 200, 20.0, 10)],
    )
    assert report["classification"] == "MEASURED"
    assert report["promotion_status"] == "NOT_EVALUATED"
    assert report["success_count"] == 2
    assert report["failure_count"] == 0
    receipt = report.pop("receipt_sha256")
    assert receipt == canonical_sha256(report)


def test_failures_remain_visible_and_do_not_generate_fake_metrics():
    report = summarize(
        "sglang",
        "example/model",
        "abc123",
        "gpu:test",
        [Sample(False, 503, 5.0, None, "HTTP 503")],
    )
    assert report["failure_count"] == 1
    assert report["p50_latency_ms"] is None
    assert report["mean_tokens_per_second"] is None
    assert report["errors"] == ["HTTP 503"]
