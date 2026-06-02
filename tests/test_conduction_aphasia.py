# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
# Doctrine v11 LOCKED 749/14/163 · Λ Conjecture 1 · SLSA L1 honest
"""
tests/test_conduction_aphasia.py — pytest suite for the Conduction-Aphasia Detector.

Three core tests (per task spec):
  1. Single observation below threshold -> no alert
  2. N consecutive observations above threshold -> alert fires
  3. Receipt is signed and has all required fields (lutar_anchor, neuro_citation, etc.)

Hickok citation: Hickok, Houde, Rong 2011, Neuron 69:407-422.
DOI 10.1016/j.neuron.2011.01.019
"""
from __future__ import annotations

import sys
import types
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Stub szl_dsse if not present
for _mod in ("szl_dsse",):
    if _mod not in sys.modules:
        stub = types.ModuleType(_mod)
        stub.sign_payload = lambda x, **kw: {"signed": False, "signatures": [], "honesty": "UNSIGNED stub"}
        stub.signing_available = lambda: False
        sys.modules[_mod] = stub

import conduction_aphasia as ca


def fresh_state(tau: float = 0.30, window: int = 3) -> ca._ConductionState:
    return ca._ConductionState(tau=tau, window=window)


# ---------------------------------------------------------------------------
# Test 1 — Single observation below threshold -> no alert
# ---------------------------------------------------------------------------

class TestBelowThreshold:
    """A single observation with delta <= tau must not breach or raise an alert."""

    def test_cosine_identical_inputs_no_breach(self):
        state = fresh_state(tau=0.30, window=3)
        receipt = state.observe("t1", [1.0, 0.5, 0.2], [1.0, 0.5, 0.2], metric="cosine")
        assert receipt["breach"] is False
        assert receipt["delta"] == pytest.approx(0.0, abs=1e-9)
        assert receipt["alert_level"] == ca.ALERT_NORMAL
        assert receipt["consecutive_breaches"] == 0

    def test_l2_small_perturbation_no_breach(self):
        state = fresh_state(tau=0.30, window=3)
        receipt = state.observe("t2", [0.8, 0.6, 0.0], [0.81, 0.59, 0.01], metric="l2")
        assert receipt["breach"] is False
        assert receipt["delta"] < 0.30
        assert receipt["alert_level"] == ca.ALERT_NORMAL

    def test_hash_hamming_identical_no_breach(self):
        state = fresh_state(tau=0.30, window=3)
        receipt = state.observe("t3", "hello world", "hello world", metric="hash_hamming")
        assert receipt["breach"] is False
        assert receipt["delta"] == pytest.approx(0.0, abs=1e-9)

    def test_status_shows_normal_after_clean(self):
        state = fresh_state()
        state.observe("t_clean", [1.0], [1.0], metric="cosine")
        status = state.status()
        assert status["current_alert_level"] == ca.ALERT_NORMAL
        assert status["consecutive_breaches"] == 0


# ---------------------------------------------------------------------------
# Test 2 — N consecutive observations above threshold -> alert fires
# ---------------------------------------------------------------------------

class TestConsecutiveBreachesFireAlert:

    def _high_pair(self):
        return [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]  # orthogonal -> cosine dist = 1.0

    def test_n_consecutive_fire_conduction_alert(self):
        state = fresh_state(tau=0.30, window=3)
        p, a = self._high_pair()
        receipts = [state.observe(f"tick_{i}", p, a, metric="cosine") for i in range(3)]
        assert receipts[0]["alert_level"] == ca.ALERT_WATCHING
        assert receipts[1]["alert_level"] == ca.ALERT_WATCHING
        assert receipts[2]["alert_level"] == ca.ALERT_CONDUCTION
        assert receipts[2]["breach"] is True
        assert receipts[2]["consecutive_breaches"] == 3

    def test_status_after_n_breaches_is_alert(self):
        state = fresh_state(tau=0.30, window=3)
        p, a = self._high_pair()
        for i in range(3):
            state.observe(f"tick_s_{i}", p, a, metric="cosine")
        status = state.status()
        assert status["current_alert_level"] == ca.ALERT_CONDUCTION
        assert status["last_alert_at"] is not None

    def test_streak_resets_on_clean(self):
        state = fresh_state(tau=0.30, window=3)
        p, a = self._high_pair()
        for i in range(2):
            state.observe(f"breach_{i}", p, a, metric="cosine")
        state.observe("clean", [1.0], [1.0], metric="cosine")
        assert state._breach_streak == 0

    def test_n_minus_one_only_watching(self):
        state = fresh_state(tau=0.30, window=3)
        p, a = self._high_pair()
        for i in range(2):
            state.observe(f"tick_{i}", p, a, metric="cosine")
        assert state.status()["current_alert_level"] == ca.ALERT_WATCHING

    def test_window_of_1_fires_immediately(self):
        state = fresh_state(tau=0.05, window=1)
        p, a = self._high_pair()
        r = state.observe("immediate", p, a, metric="cosine")
        assert r["alert_level"] == ca.ALERT_CONDUCTION

    def test_breach_with_l2_metric(self):
        state = fresh_state(tau=0.10, window=3)
        p = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        a = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        for i in range(3):
            state.observe(f"l2_{i}", p, a, metric="l2")
        assert state._current_alert == ca.ALERT_CONDUCTION


# ---------------------------------------------------------------------------
# Test 3 — Receipt has all required fields, lutar_anchor, neuro_citation
# ---------------------------------------------------------------------------

class TestReceiptSchema:
    REQUIRED_FIELDS = [
        "receipt_id", "kind", "tick_id", "predicted_hash", "actual_hash",
        "delta", "metric", "threshold_tau", "breach", "alert_level",
        "consecutive_breaches", "doctrine_v", "neuro_citation",
        "lutar_anchor", "signed_by", "sig", "ts",
    ]

    def _get_receipt(self, **kw):
        state = fresh_state()
        return state.observe(
            tick_id=kw.get("tick_id", "schema_test"),
            predicted_sensory=kw.get("predicted_sensory", [0.5, 0.5]),
            actual_sensory=kw.get("actual_sensory", [0.5, 0.5]),
            metric=kw.get("metric", "cosine"),
        )

    def test_all_required_fields_present(self):
        r = self._get_receipt()
        for field in self.REQUIRED_FIELDS:
            assert field in r, f"Missing required field: {field}"

    def test_lutar_anchor_value(self):
        r = self._get_receipt()
        assert r["lutar_anchor"] == "A37_InternalFeedbackIntegrity"

    def test_neuro_citation_has_hickok_doi(self):
        r = self._get_receipt()
        nc = r["neuro_citation"]
        assert isinstance(nc, dict)
        assert nc.get("doi") == "10.1016/j.neuron.2011.01.019"

    def test_neuro_citation_has_label(self):
        r = self._get_receipt()
        nc = r["neuro_citation"]
        assert "Hickok" in nc.get("label", "")
        assert "2011" in nc.get("label", "")

    def test_kind_is_conduction_observation(self):
        assert self._get_receipt()["kind"] == "conduction_observation"

    def test_doctrine_v_is_11(self):
        assert self._get_receipt()["doctrine_v"] == "11"

    def test_signed_by_is_yachay(self):
        assert self._get_receipt()["signed_by"] == "yachay"

    def test_predicted_hash_format(self):
        r = self._get_receipt(predicted_sensory=[0.1, 0.2])
        assert r["predicted_hash"].startswith("sha256:")

    def test_actual_hash_format(self):
        r = self._get_receipt(actual_sensory=[0.4, 0.5])
        assert r["actual_hash"].startswith("sha256:")

    def test_receipt_ids_unique(self):
        state = fresh_state()
        r1 = state.observe("t_a", [1.0], [1.0], "cosine")
        r2 = state.observe("t_b", [1.0], [1.0], "cosine")
        assert r1["receipt_id"] != r2["receipt_id"]

    def test_receipts_ring_newest_first(self):
        state = fresh_state()
        for i in range(3):
            state.observe(f"order_{i}", [float(i)], [float(i)], "cosine")
        receipts = state.receipts()
        assert receipts[0]["tick_id"] == "order_2"
        assert receipts[2]["tick_id"] == "order_0"


# ---------------------------------------------------------------------------
# Test 4 — Metric math
# ---------------------------------------------------------------------------

class TestMetricComputation:
    def test_cosine_identical_zero(self):
        assert ca._cosine_delta([1.0, 0.5], [1.0, 0.5]) == pytest.approx(0.0, abs=1e-9)

    def test_cosine_orthogonal_one(self):
        assert ca._cosine_delta([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0, abs=1e-9)

    def test_l2_identical_zero(self):
        assert ca._l2_delta([3.0, 4.0], [3.0, 4.0]) == pytest.approx(0.0, abs=1e-9)

    def test_l2_pythagorean(self):
        assert ca._l2_delta([0.0, 0.0], [3.0, 4.0]) == pytest.approx(5.0, abs=1e-9)

    def test_hamming_identical_zero(self):
        assert ca._hash_hamming_delta("abc", "abc") == pytest.approx(0.0, abs=1e-9)

    def test_hamming_different_positive(self):
        d = ca._hash_hamming_delta("abc", "xyz")
        assert 0.0 < d <= 1.0


# ---------------------------------------------------------------------------
# Test 5 — FastAPI HTTP contract
# ---------------------------------------------------------------------------

class TestFastAPIEndpoints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("FastAPI / httpx not installed")
        ca.reset_state(tau=0.30, window=3)
        app = FastAPI()
        ca.register(app, ns="a11oy")
        self.client = TestClient(app)
        yield

    def test_status_200_doctrine_v(self):
        r = self.client.get("/api/a11oy/v4/conduction/status")
        assert r.status_code == 200
        d = r.json()
        assert d["doctrine_v"] == "11"
        assert "threshold_tau" in d

    def test_observe_below_no_breach(self):
        r = self.client.post("/api/a11oy/v4/conduction/observe", json={
            "tick_id": "http_t1", "predicted_sensory": [1.0, 1.0],
            "actual_sensory": [1.0, 1.0], "metric": "cosine"})
        assert r.status_code == 200
        d = r.json()
        assert d["breach"] is False
        assert d["alert_level"] == "normal"

    def test_observe_high_delta_breach(self):
        r = self.client.post("/api/a11oy/v4/conduction/observe", json={
            "tick_id": "http_breach", "predicted_sensory": [1.0, 0.0, 0.0],
            "actual_sensory": [0.0, 0.0, 1.0], "metric": "cosine"})
        assert r.status_code == 200
        assert r.json()["breach"] is True

    def test_n_consecutive_fires_conduction_alert(self):
        for i in range(3):
            self.client.post("/api/a11oy/v4/conduction/observe", json={
                "tick_id": f"alert_{i}", "predicted_sensory": [1.0, 0.0, 0.0],
                "actual_sensory": [0.0, 0.0, 1.0], "metric": "cosine"})
        status = self.client.get("/api/a11oy/v4/conduction/status").json()
        assert status["current_alert_level"] == "conduction_alert"

    def test_receipts_returns_list(self):
        self.client.post("/api/a11oy/v4/conduction/observe", json={
            "tick_id": "rec_1", "predicted_sensory": [0.5],
            "actual_sensory": [0.5], "metric": "cosine"})
        r = self.client.get("/api/a11oy/v4/conduction/receipts?limit=5")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["receipts"], list)
        assert len(d["receipts"]) >= 1

    def test_receipt_has_lutar_anchor_and_doi(self):
        self.client.post("/api/a11oy/v4/conduction/observe", json={
            "tick_id": "schema_http", "predicted_sensory": [1.0],
            "actual_sensory": [1.0], "metric": "cosine"})
        d = self.client.get("/api/a11oy/v4/conduction/receipts?limit=1").json()
        rec = d["receipts"][0]
        assert rec["lutar_anchor"] == "A37_InternalFeedbackIntegrity"
        assert rec["neuro_citation"]["doi"] == "10.1016/j.neuron.2011.01.019"

    def test_demo_endpoint_injects_high_delta(self):
        r = self.client.post("/api/a11oy/v4/conduction/demo")
        assert r.status_code == 200
        d = r.json()
        assert d.get("demo") is True
        assert d["delta"] > 0.0

    def test_conduction_html_has_doi(self):
        r = self.client.get("/conduction")
        assert r.status_code == 200
        assert "10.1016/j.neuron.2011.01.019" in r.text
        assert "A37" in r.text

    def test_status_has_neuro_citation(self):
        d = self.client.get("/api/a11oy/v4/conduction/status").json()
        assert d["neuro_citation"]["doi"] == "10.1016/j.neuron.2011.01.019"
