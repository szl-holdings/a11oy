"""
Tests for Adversarial Regression Gate — Composition Robustness
Lean theorem: Lutar.Composition.Robustness.robustness_preserved_by_composition (GREEN)

Property: (delta, eps1)-robust ∘ (eps1, eps2)-robust = (delta, eps2)-robust.
1000 random perturbations within delta-ball; composed robustness holds.
"""

import math
import random
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root without installation, matching
# test_witnessed_forecast.py. CI sets PYTHONPATH=src; this insertion makes the
# suite runnable directly (pytest test/test_adversarial_regression.py) too.
# ---------------------------------------------------------------------------
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from adversarial.adversarial_regression import (  # noqa: E402
    RobustnessSpec,
    verify_composition_robustness,
    lipschitz_compose,
    compose_models,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_lipschitz_model(L: float, dim: int):
    """
    Return a deterministic Lipschitz-L model: f(x) = L * x (elementwise scaling).
    ‖f(x) - f(x')‖ = L * ‖x - x'‖ ≤ L * ‖x - x'‖. Lipschitz constant = L.
    """
    def f(x: list[float]) -> list[float]:
        return [L * xi for xi in x]
    f.__name__ = f"scale_{L}"
    return f


def l2(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def random_point(dim: int, scale: float = 1.0) -> list[float]:
    return [random.gauss(0, scale) for _ in range(dim)]


def perturb_within_ball(x: list[float], delta: float) -> list[float]:
    """Return x' with ‖x - x'‖ ≤ delta (uniform random direction, radius = delta/2)."""
    dim = len(x)
    direction = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(d ** 2 for d in direction)) or 1.0
    radius = random.uniform(0, delta)
    return [xi + radius * d / norm for xi, d in zip(x, direction)]


# ---------------------------------------------------------------------------
# Deterministic cases
# ---------------------------------------------------------------------------


class TestLipschitzCompose:
    def test_basic_composition(self):
        spec_f = RobustnessSpec(delta=0.5, eps=1.0)
        spec_g = RobustnessSpec(delta=1.0, eps=2.0)
        composed = lipschitz_compose(spec_f, spec_g)
        assert composed.delta == pytest.approx(0.5)
        assert composed.eps == pytest.approx(2.0)

    def test_precondition_check(self):
        """Composition requires spec_g.delta == spec_f.eps."""
        spec_f = RobustnessSpec(delta=0.5, eps=1.0)
        spec_g = RobustnessSpec(delta=0.8, eps=2.0)  # mismatch!
        with pytest.raises(ValueError, match="Composition precondition"):
            lipschitz_compose(spec_f, spec_g)

    def test_identity_composition(self):
        """Identity: (d, e)∘(d, e) is not valid unless e==d; check (d,e)∘(e,eps2)."""
        spec_f = RobustnessSpec(delta=1.0, eps=1.0)
        spec_g = RobustnessSpec(delta=1.0, eps=0.5)
        composed = lipschitz_compose(spec_f, spec_g)
        assert composed.delta == pytest.approx(1.0)
        assert composed.eps == pytest.approx(0.5)


class TestVerifyCompositionRobustness:
    def test_scale_models_verify(self):
        """
        f = scale by L1=0.5 (delta=1.0 → eps1=0.5)
        g = scale by L2=2.0 (eps1=0.5 → eps2=1.0)
        Composed: delta=1.0 → eps2=1.0. Theorem guarantees ‖h(x)-h(x')‖ ≤ 1.0.
        """
        dim = 4
        L1, L2 = 0.5, 2.0
        f = make_lipschitz_model(L1, dim)
        g = make_lipschitz_model(L2, dim)
        spec_f = RobustnessSpec(delta=1.0, eps=L1 * 1.0)  # eps1 = 0.5
        spec_g = RobustnessSpec(delta=L1 * 1.0, eps=L2 * L1 * 1.0)  # eps2 = 1.0

        random.seed(42)
        test_points = [random_point(dim) for _ in range(100)]
        perturbations = [perturb_within_ball(x, spec_f.delta) for x in test_points]

        result = verify_composition_robustness(f, g, spec_f, spec_g, test_points, perturbations)
        assert result.verified
        assert result.n_violations == 0
        assert result.receipt["lean_theorem"] == (
            "Lutar.Composition.Robustness.robustness_preserved_by_composition"
        )

    def test_receipt_fields(self):
        f = make_lipschitz_model(0.3, 2)
        g = make_lipschitz_model(0.3, 2)
        spec_f = RobustnessSpec(delta=1.0, eps=0.3)
        spec_g = RobustnessSpec(delta=0.3, eps=0.09)

        random.seed(0)
        pts = [random_point(2) for _ in range(10)]
        perturbs = [perturb_within_ball(x, 1.0) for x in pts]

        result = verify_composition_robustness(f, g, spec_f, spec_g, pts, perturbs)
        r = result.receipt
        assert r["formula"] == "robustness_preserved_by_composition"
        assert r["lean_file"] == "Lutar/Composition/AdversarialRobustness.lean"
        assert len(r["inputs_hash"]) == 64
        assert "ts" in r

    def test_mismatched_lengths_raises(self):
        f = make_lipschitz_model(1.0, 2)
        g = make_lipschitz_model(1.0, 2)
        spec_f = RobustnessSpec(delta=1.0, eps=1.0)
        spec_g = RobustnessSpec(delta=1.0, eps=1.0)
        with pytest.raises(ValueError, match="length"):
            verify_composition_robustness(f, g, spec_f, spec_g, [[1.0, 2.0]], [])

    def test_precondition_mismatch_raises(self):
        f = make_lipschitz_model(0.5, 2)
        g = make_lipschitz_model(1.0, 2)
        spec_f = RobustnessSpec(delta=1.0, eps=0.5)
        spec_g = RobustnessSpec(delta=0.8, eps=1.0)  # should be 0.5
        with pytest.raises(ValueError, match="Composition precondition"):
            verify_composition_robustness(f, g, spec_f, spec_g, [], [])


# ---------------------------------------------------------------------------
# Fuzz: 1000 random perturbations
# ---------------------------------------------------------------------------


class TestFuzz1000:
    def test_1000_perturbations_within_delta_ball(self):
        """
        Theorem fuzz: for 1000 random (x, x') pairs with ‖x-x'‖ ≤ delta,
        composed Lipschitz model satisfies ‖h(x)-h(x')‖ ≤ eps2.
        """
        dim = 3
        L1, L2 = 0.4, 0.6
        # eps2 = L1 * L2 * delta = 0.24 * delta
        delta = 2.0
        eps1 = L1 * delta   # = 0.8
        eps2 = L2 * eps1    # = 0.48

        f = make_lipschitz_model(L1, dim)
        g = make_lipschitz_model(L2, dim)
        spec_f = RobustnessSpec(delta=delta, eps=eps1)
        spec_g = RobustnessSpec(delta=eps1, eps=eps2)

        random.seed(12345)
        test_points = [random_point(dim, scale=5.0) for _ in range(1000)]
        perturbations = [perturb_within_ball(x, delta) for x in test_points]

        result = verify_composition_robustness(
            f, g, spec_f, spec_g, test_points, perturbations
        )
        assert result.verified, (
            f"THEOREM VIOLATION: {result.n_violations}/{result.n_tested} pairs exceeded "
            f"composed eps2={eps2:.4f}. max_output_perturbation={result.max_output_perturbation:.6f}"
        )
        assert result.n_violations == 0
        assert result.n_tested == 1000
        # Also check max perturbation is within bound (with tiny float slack)
        assert result.max_output_perturbation <= eps2 + 1e-9

    def test_1000_varied_lipschitz_constants(self):
        """
        1000 independent trials with random L1, L2 ∈ (0, 1); each trial uses 5 samples.
        All should pass (composition theorem is universal for Lipschitz models).
        """
        dim = 2
        total_violations = 0
        random.seed(99)
        for _ in range(1000):
            L1 = random.uniform(0.01, 0.99)
            L2 = random.uniform(0.01, 0.99)
            delta = random.uniform(0.1, 3.0)
            eps1 = L1 * delta
            eps2 = L2 * eps1

            f = make_lipschitz_model(L1, dim)
            g = make_lipschitz_model(L2, dim)
            spec_f = RobustnessSpec(delta=delta, eps=eps1)
            spec_g = RobustnessSpec(delta=eps1, eps=eps2)

            pts = [random_point(dim) for _ in range(5)]
            perturbs = [perturb_within_ball(x, delta) for x in pts]

            result = verify_composition_robustness(f, g, spec_f, spec_g, pts, perturbs)
            total_violations += result.n_violations

        assert total_violations == 0
