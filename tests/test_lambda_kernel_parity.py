"""Λ parity guard: flagship inline aggregator vs the published universal kernel.

WHY THIS EXISTS (the wiring gap this closes)
---------------------------------------------
The org publishes a universal Hugging Face Kernel-Hub kernel, ``szl-lambda-gate``
(``torch-ext/szl_lambda_gate/_lambda.py``), whose Λ aggregator is a *torch* port
of a canonical pure-Python reference
(``platform/packages/puriq-os/puriq_os/lambda_aggregator.py``, mirrored in the
kernel repo as ``tests/lambda_aggregator_source.py``). The flagship does NOT — and
safely CANNOT — import that kernel on its live Λ path: the kernel needs
``torch>=2.5`` and is loaded over the network via ``kernels.get_kernel(...)``,
while the flagship's Λ gate (``szl_formulas.lambda_aggregate``, imported by
``serve.py`` / ``szl_org_lambda`` / ``szl_lambda_tripwire`` / the agent loop) is
pure-stdlib and on the request path. Adding torch + a Hub download there would be
a real regression, so the flagship keeps its own inline copy.

That is exactly how Λ drifted into 5+ divergent copies. This test makes the inline
copy the SINGLE canonical Python source of truth and pins it to the published
kernel: it re-derives Λ from the kernel's OWN canonical reference and asserts the
flagship produces identical results. If the flagship Λ ever drifts from the
published kernel's math, this goes red. No behavior change, no new dependency —
a drift-catching guard, not a rewire.

SCOPE (honest): parity is asserted on the SHARED valid domain both implementations
agree on — axis scores in [0,1] and weights that already sum to 1 (or uniform).
The two differ only at input-validation BOUNDARIES (empty input, un-normalized
weights, scores > 1); those are deliberate guard choices, not Λ-math drift, and
are documented — not asserted — below. Λ remains ADVISORY (Conjecture 1, open);
this test proves numerical agreement, NOT trust.

Pure stdlib (math + unittest); network-free; imports only ``szl_formulas`` (itself
stdlib-only). Run: ``pytest tests/test_lambda_kernel_parity.py -q``.
"""
from __future__ import annotations

import math
import random
import unittest
from typing import Sequence

import szl_formulas


# --- Published-kernel canonical reference -----------------------------------
# VERBATIM from szl-holdings/szl-lambda-gate ::tests/lambda_aggregator_source.py
# (itself the CANONICAL source pulled from
#  szl-holdings/platform packages/puriq-os/puriq_os/lambda_aggregator.py).
# Kept as an independent, dependency-free re-derivation of the kernel's math so a
# drift between the flagship and the published kernel is caught here. Do NOT
# "simplify" it to call szl_formulas — that would defeat the parity check.
def _kernel_reference_lambda_aggregate(
    axes: Sequence[float], weights: Sequence[float] | None = None
) -> float:
    """Weighted geometric mean Λ(x) = ∏ xᵢ^{wᵢ} — the szl-lambda-gate reference."""
    n = len(axes)
    if n == 0:
        return 0.0
    if weights is None:
        weights = [1.0 / n] * n
    if len(weights) != n:
        raise ValueError("axes and weights length mismatch")
    sw = sum(weights)
    if sw <= 0:
        raise ValueError("weights must be positive and sum > 0")
    weights = [w / sw for w in weights]  # normalize Σw=1
    acc = 0.0
    for x, w in zip(axes, weights):
        x = min(max(float(x), 0.0), 1.0)
        if x <= 0.0:
            return 0.0  # any zero axis zeroes the product (A4-consistent)
        acc += w * math.log(x)
    val = math.exp(acc)
    return min(max(val, 0.0), 1.0)


# Tight numerical tolerance: the flagship sums log-terms with math.fsum while the
# reference uses a naive running sum, so results can differ by a few ULP. Anything
# above this is real drift, not floating-point noise.
PARITY_TOL = 1e-12

# The canonical 13-axis Yuyay weight vector the kernel exposes (uniform 1/13).
YUYAY_K = 13


class LambdaKernelParity(unittest.TestCase):
    def _assert_parity(self, axes, weights=None, msg=""):
        got = szl_formulas.lambda_aggregate(axes, weights)
        ref = _kernel_reference_lambda_aggregate(axes, weights)
        self.assertLessEqual(
            abs(got - ref),
            PARITY_TOL,
            f"Λ drift {msg}: flagship={got!r} kernel_ref={ref!r} "
            f"axes={axes} weights={weights}",
        )

    def test_uniform_weight_fixtures(self):
        for axes in (
            [0.9, 0.8, 0.95],
            [0.5, 0.5, 0.5],
            [0.99, 0.01],
            [1.0, 1.0, 1.0],
            [0.7],
            [0.5] * YUYAY_K,
        ):
            with self.subTest(axes=axes):
                self._assert_parity(axes, msg="uniform-weight fixture")

    def test_zero_pin_edge_cases(self):
        """Non-compensatory zero-routing: any zero axis ⇒ Λ = exactly 0.0 in BOTH."""
        for axes in ([0.0, 0.5], [0.5, 0.0, 0.9], [0.0] * 3, [0.9, 0.9, 0.0]):
            with self.subTest(axes=axes):
                got = szl_formulas.lambda_aggregate(axes)
                ref = _kernel_reference_lambda_aggregate(axes)
                self.assertEqual(got, 0.0, f"flagship not zero-pinned: {axes}")
                self.assertEqual(ref, 0.0, f"kernel ref not zero-pinned: {axes}")

    def test_explicit_normalized_weights(self):
        for axes, weights in (
            ([0.8, 0.9, 0.7], [0.2, 0.3, 0.5]),
            ([0.95, 0.6], [0.5, 0.5]),
            ([0.9, 0.8, 0.85, 0.7], [0.4, 0.3, 0.2, 0.1]),
        ):
            with self.subTest(axes=axes, weights=weights):
                self._assert_parity(axes, weights, msg="explicit normalized weights")

    def test_yuyay_13axis_uniform_weights(self):
        """The published 13-axis Yuyay preset: uniform 1/13 over 13 axis scores."""
        weights = [1.0 / YUYAY_K] * YUYAY_K
        axes = [0.97, 0.96, 0.93, 0.91, 0.90, 0.92, 0.94, 0.90, 0.95, 0.91, 0.90, 0.93, 0.90]
        self.assertEqual(len(axes), YUYAY_K)
        self._assert_parity(axes, weights, msg="yuyay 13-axis")

    def test_randomized_parity_sweep(self):
        rng = random.Random(0)  # deterministic
        for _ in range(4000):
            k = rng.randint(1, 15)
            axes = [rng.random() for _ in range(k)]  # in [0,1)
            self._assert_parity(axes, msg="random uniform-weight sweep")

    def test_randomized_weighted_parity_sweep(self):
        rng = random.Random(1)
        for _ in range(2000):
            k = rng.randint(1, 15)
            axes = [rng.random() for _ in range(k)]
            raw = [rng.random() + 1e-3 for _ in range(k)]
            s = sum(raw)
            weights = [w / s for w in raw]  # pre-normalized to the shared domain
            self._assert_parity(axes, weights, msg="random weighted sweep")

    def test_reference_would_catch_drift(self):
        """Negative self-test: a MUTATED aggregator must trip the parity check, so
        this guard cannot rot into an always-pass if the flagship silently drifts."""

        def drifted(axes, weights=None):
            # Plausible-but-wrong: arithmetic mean instead of geometric mean.
            return sum(axes) / len(axes)

        axes = [0.9, 0.8, 0.95]
        ref = _kernel_reference_lambda_aggregate(axes)
        self.assertGreater(
            abs(drifted(axes) - ref),
            PARITY_TOL,
            "parity check is vacuous — an arithmetic-mean impostor slipped through",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
