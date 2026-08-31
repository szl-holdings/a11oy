"""pytest test suite for amaru.src.regression.adversarial_regression
and amaru.src.cortex.entropy_budget.

Doctrine v6 | SPDX-License-Identifier: BSL-1.1

Assertions (≥ 30):
  1.  load_receipt_jsonl yields correct count from JSONL string
  2.  load_receipt_jsonl skips blank lines
  3.  load_receipt_jsonl skips comment lines
  4.  extract_numeric_vector from output subdict
  5.  extract_numeric_vector from top-level fields
  6.  extract_numeric_vector returns empty for non-numeric
  7.  l2_norm correct on known vector
  8.  lutar_drift_metric zero when vectors equal
  9.  lutar_drift_metric > 1 for large deviation
  10. lutar_drift_metric raises on vector length mismatch
  11. lutar_drift_metric raises on eps2 ≤ 0
  12. run_adversarial_regression: total_receipts correct
  13. run_adversarial_regression: baseline phase drift=0
  14. run_adversarial_regression: adversarial receipt detected as failure
  15. run_adversarial_regression: failures list non-empty after injection
  16. run_adversarial_regression: dsse_receipt theorem correct
  17. run_adversarial_regression: dsse_receipt inputs_hash 64-char hex
  18. run_adversarial_regression: lean_theorem in report
  19. run_adversarial_regression: raises on baseline_n < 1
  20. run_adversarial_regression: raises on eps2 ≤ 0
  21. RegressionReport.as_dict() contains required keys
  22. RegressionResult.as_dict() JSON round-trip
  23. shannon_entropy_bits uniform = log2(n)
  24. shannon_entropy_bits degenerate = 0
  25. shannon_entropy_bits raises on negative prob
  26. validate_doctrine_probs normalises correctly
  27. validate_doctrine_probs raises on wrong length
  28. validate_doctrine_probs raises on negative entry
  29. validate_doctrine_probs raises on all-zero
  30. doctrine_entropy_budget uniform = 2 bits
  31. doctrine_entropy_budget degenerate = 0 bits, within_budget
  32. doctrine_entropy_budget dsse_receipt structure
  33. doctrine_entropy_budget 1000 random distributions all within budget
  34. rate_limit_inference: uniform allowed at threshold=1.0
  35. entropy_budget_from_labels: label counts → correct entropy
"""

from __future__ import annotations

import io
import json
import math
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from regression.adversarial_regression import (  # noqa: E402
    DEFAULT_EPS2,
    LUTAR_LEAN_HEAD_SHA,
    ROBUSTNESS_THEOREM,
    RegressionReport,
    RegressionResult,
    extract_numeric_vector,
    l2_norm,
    load_receipt_jsonl,
    lutar_drift_metric,
    run_adversarial_regression,
    run_adversarial_regression_from_jsonl,
)
from cortex.entropy_budget import (  # noqa: E402
    MAX_DOCTRINE_ENTROPY_BITS,
    DoctrineLabel,
    EntropyBudgetResult,
    doctrine_entropy_budget,
    entropy_budget_from_labels,
    rate_limit_inference,
    shannon_entropy_bits,
    validate_doctrine_probs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(receipts: list[dict]) -> Path:
    """Write receipts to a temp JSONL file and return the path."""
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    with tmp.open("w") as fh:
        for r in receipts:
            fh.write(json.dumps(r) + "\n")
    return tmp


def _make_receipts(n: int, base_val: float = 0.5) -> list[dict]:
    return [
        {"id": f"r{i}", "output": {"prediction": base_val + 0.001 * i, "confidence": 0.9}}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# 1–3: load_receipt_jsonl
# ---------------------------------------------------------------------------

def test_load_jsonl_yields_correct_count() -> None:
    receipts = _make_receipts(10)
    path = _write_jsonl(receipts)
    loaded = list(load_receipt_jsonl(path))
    assert len(loaded) == 10


def test_load_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "test.jsonl"
    p.write_text('{"id":"a"}\n\n\n{"id":"b"}\n', encoding="utf-8")
    loaded = list(load_receipt_jsonl(p))
    assert len(loaded) == 2


def test_load_jsonl_skips_comment_lines(tmp_path: Path) -> None:
    p = tmp_path / "test.jsonl"
    p.write_text('# comment\n{"id":"c"}\n# another\n{"id":"d"}\n', encoding="utf-8")
    loaded = list(load_receipt_jsonl(p))
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# 4–6: extract_numeric_vector
# ---------------------------------------------------------------------------

def test_extract_from_output_subdict() -> None:
    r = {"output": {"prediction": 0.7, "confidence": 0.9}}
    vec = extract_numeric_vector(r)
    assert 0.7 in vec
    assert 0.9 in vec


def test_extract_from_toplevel() -> None:
    r = {"prediction": 0.6, "score": 0.8}
    vec = extract_numeric_vector(r)
    assert len(vec) >= 1


def test_extract_empty_for_nonnumeric() -> None:
    r = {"name": "test", "label": "ok"}
    vec = extract_numeric_vector(r)
    assert len(vec) == 0


# ---------------------------------------------------------------------------
# 7: l2_norm
# ---------------------------------------------------------------------------

def test_l2_norm_known() -> None:
    assert abs(l2_norm([3.0, 4.0]) - 5.0) < 1e-12


def test_l2_norm_zero() -> None:
    assert l2_norm([0.0, 0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# 8–11: lutar_drift_metric
# ---------------------------------------------------------------------------

def test_drift_zero_equal_vectors() -> None:
    v = [0.5, 0.5, 0.5]
    assert lutar_drift_metric(v, v) == 0.0


def test_drift_large_deviation() -> None:
    baseline = [0.5, 0.5]
    outlier = [10.0, 10.0]
    drift = lutar_drift_metric(outlier, baseline)
    assert drift > 1.0


def test_drift_raises_length_mismatch() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        lutar_drift_metric([1.0, 2.0], [1.0])


def test_drift_raises_non_positive_eps2() -> None:
    with pytest.raises(ValueError, match="eps2 must be > 0"):
        lutar_drift_metric([1.0], [1.0], eps2=0.0)


# ---------------------------------------------------------------------------
# 12–22: run_adversarial_regression
# ---------------------------------------------------------------------------

def test_regression_total_receipts() -> None:
    receipts = _make_receipts(15)
    report = run_adversarial_regression(receipts, baseline_n=5)
    assert report.total_receipts == 15


def test_regression_baseline_phase_drift_zero() -> None:
    receipts = _make_receipts(10)
    report = run_adversarial_regression(receipts, baseline_n=5)
    for r in report.all_results[:5]:
        assert r.drift == 0.0, f"baseline receipt {r.receipt_index} should have drift=0"


def test_regression_adversarial_receipt_detected() -> None:
    receipts = _make_receipts(10, base_val=0.5)
    receipts.append({"id": "adv", "output": {"prediction": 500.0, "confidence": 0.0}})
    report = run_adversarial_regression(receipts, baseline_n=5, eps2=0.15)
    failure_ids = {f.receipt_id for f in report.failures}
    assert "adv" in failure_ids


def test_regression_failures_non_empty_after_injection() -> None:
    receipts = _make_receipts(10)
    # Must include both fields to match the 2-element baseline vector.
    receipts.append({"id": "outlier", "output": {"prediction": 1000.0, "confidence": 1000.0}})
    report = run_adversarial_regression(receipts, baseline_n=5)
    assert len(report.failures) >= 1


def test_regression_dsse_receipt_theorem() -> None:
    receipts = _make_receipts(8)
    report = run_adversarial_regression(receipts, baseline_n=3)
    for r in report.all_results:
        assert r.dsse_receipt["theorem"] == ROBUSTNESS_THEOREM


def test_regression_dsse_receipt_inputs_hash_hex() -> None:
    receipts = _make_receipts(8)
    report = run_adversarial_regression(receipts, baseline_n=3)
    for r in report.all_results:
        h = r.dsse_receipt["inputs_hash"]
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h.lower())


def test_regression_lean_theorem_in_report() -> None:
    report = run_adversarial_regression(_make_receipts(8), baseline_n=3)
    assert report.lean_theorem == ROBUSTNESS_THEOREM


def test_regression_raises_baseline_n_zero() -> None:
    with pytest.raises(ValueError, match="baseline_n must be ≥ 1"):
        run_adversarial_regression(_make_receipts(5), baseline_n=0)


def test_regression_raises_eps2_zero() -> None:
    with pytest.raises(ValueError, match="eps2 must be > 0"):
        run_adversarial_regression(_make_receipts(5), eps2=0.0)


def test_regression_report_as_dict_keys() -> None:
    report = run_adversarial_regression(_make_receipts(8), baseline_n=3)
    d = report.as_dict()
    for key in ("total_receipts", "baseline_n", "failures", "max_drift",
                "mean_drift", "eps2", "all_results", "lean_theorem"):
        assert key in d, f"Missing key: {key}"


def test_regression_result_json_roundtrip() -> None:
    receipts = _make_receipts(8)
    report = run_adversarial_regression(receipts, baseline_n=3)
    r = report.all_results[-1]
    d = r.as_dict()
    serialised = json.dumps(d)
    recovered = json.loads(serialised)
    assert recovered["dsse_receipt"]["theorem"] == ROBUSTNESS_THEOREM


# ---------------------------------------------------------------------------
# 23–25: shannon_entropy_bits
# ---------------------------------------------------------------------------

def test_entropy_uniform_n4() -> None:
    # H([0.25]*4) = log2(4) = 2.0 bits exactly.
    h = shannon_entropy_bits([0.25, 0.25, 0.25, 0.25])
    assert abs(h - 2.0) < 1e-12


def test_entropy_degenerate_zero() -> None:
    h = shannon_entropy_bits([1.0, 0.0, 0.0, 0.0])
    assert abs(h) < 1e-12


def test_entropy_raises_negative_prob() -> None:
    with pytest.raises(ValueError, match="Negative probability"):
        shannon_entropy_bits([0.5, -0.1, 0.3, 0.3])


# ---------------------------------------------------------------------------
# 26–29: validate_doctrine_probs
# ---------------------------------------------------------------------------

def test_validate_normalises() -> None:
    normalised = validate_doctrine_probs([1.0, 1.0, 1.0, 1.0])
    assert abs(sum(normalised) - 1.0) < 1e-12
    assert all(abs(p - 0.25) < 1e-12 for p in normalised)


def test_validate_raises_wrong_length() -> None:
    with pytest.raises(ValueError, match="exactly 4"):
        validate_doctrine_probs([0.5, 0.5, 0.0])


def test_validate_raises_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        validate_doctrine_probs([-0.1, 0.5, 0.4, 0.2])


def test_validate_raises_all_zero() -> None:
    with pytest.raises(ValueError, match="All-zero"):
        validate_doctrine_probs([0.0, 0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# 30–33: doctrine_entropy_budget
# ---------------------------------------------------------------------------

def test_entropy_budget_uniform_2_bits() -> None:
    r = doctrine_entropy_budget([0.25, 0.25, 0.25, 0.25])
    assert abs(r.entropy_bits - 2.0) < 1e-9
    assert r.within_budget is True


def test_entropy_budget_degenerate() -> None:
    r = doctrine_entropy_budget([1.0, 0.0, 0.0, 0.0])
    assert abs(r.entropy_bits) < 1e-12
    assert r.within_budget is True


def test_entropy_budget_dsse_receipt() -> None:
    r = doctrine_entropy_budget([0.25, 0.25, 0.25, 0.25])
    rec = r.dsse_receipt
    assert rec["theorem"] == "Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits"
    assert len(rec["inputs_hash"]) == 64


def test_entropy_budget_1000_random_within_bound() -> None:
    import random
    rng = random.Random(42)
    for _ in range(1000):
        raw = [rng.random() for _ in range(4)]
        result = doctrine_entropy_budget(raw)
        assert result.within_budget is True
        assert result.entropy_bits <= MAX_DOCTRINE_ENTROPY_BITS + 1e-9


# ---------------------------------------------------------------------------
# 34: rate_limit_inference
# ---------------------------------------------------------------------------

def test_rate_limit_uniform_allowed_at_full_threshold() -> None:
    result = rate_limit_inference([0.25, 0.25, 0.25, 0.25], load_threshold=1.0)
    assert result["allowed"] is True


def test_rate_limit_uniform_blocked_at_low_threshold() -> None:
    result = rate_limit_inference([0.25, 0.25, 0.25, 0.25], load_threshold=0.5)
    # Uniform = 2 bits = 100% load → exceeds 50% threshold.
    assert result["allowed"] is False


# ---------------------------------------------------------------------------
# 35: entropy_budget_from_labels
# ---------------------------------------------------------------------------

def test_entropy_from_labels_uniform() -> None:
    counts = {"Bot": 25, "L1": 25, "L2": 25, "Top": 25}
    r = entropy_budget_from_labels(counts)
    assert abs(r.entropy_bits - 2.0) < 1e-9


def test_entropy_from_labels_raises_all_zero() -> None:
    with pytest.raises(ValueError, match="All label counts are zero"):
        entropy_budget_from_labels({"Bot": 0, "L1": 0, "L2": 0, "Top": 0})
