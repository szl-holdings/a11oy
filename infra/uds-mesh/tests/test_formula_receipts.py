"""
tests/test_formula_receipts.py — pytest coverage for formula_receipts.py

Layer 5 DSSE receipt tests for the 5 anchor SZL formulas.
Run: pytest tests/test_formula_receipts.py -v

SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings
"""
import json
import math
import base64
import pytest

# Import relative to project root (pytest adds cwd to sys.path)
from formula_receipts import (
    emit_formula_receipt,
    FormulaReceipt,
    ANCHOR_REGISTRY,
    LEAN_COMMIT_SHA,
    PAYLOAD_TYPE,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

MADHAVA_INPUTS   = {"x": 1.0, "N": 10}
FALSE_POS_INPUTS = {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 2.0, "T": 4.0}
LIU_HUI_INPUTS   = {"k": 4}
ADV_ROB_INPUTS   = {"l1": 2.0, "l2": 3.0, "delta": 0.1}
SUMMATION_INPUTS = {
    "organs": [
        {"organId": "o1", "decisions": [{"decisionId": "d1", "value": 10}, {"decisionId": "d2", "value": 20}]},
        {"organId": "o2", "decisions": [{"decisionId": "d3", "value": 5}]},
    ],
    "primary_cord": 35,
}

ALL_CASES = [
    ("MadhavaBound",          MADHAVA_INPUTS),
    ("FalsePosition",         FALSE_POS_INPUTS),
    ("LiuHuiPi",              LIU_HUI_INPUTS),
    ("AdversarialRobustness", ADV_ROB_INPUTS),
    ("SummationInvariant",    SUMMATION_INPUTS),
]


# ── Registry tests ────────────────────────────────────────────────────────────

class TestRegistry:
    def test_all_5_formulas_registered(self):
        assert set(ANCHOR_REGISTRY.keys()) == {
            "MadhavaBound", "FalsePosition", "LiuHuiPi",
            "AdversarialRobustness", "SummationInvariant",
        }

    @pytest.mark.parametrize("formula", list(ANCHOR_REGISTRY))
    def test_registry_has_required_fields(self, formula):
        entry = ANCHOR_REGISTRY[formula]
        for field in ("lean_theorem", "lean_file", "lean_blob_sha", "lean_commit_sha"):
            assert field in entry, f"{formula} missing {field}"

    @pytest.mark.parametrize("formula", list(ANCHOR_REGISTRY))
    def test_commit_sha_matches_main(self, formula):
        assert ANCHOR_REGISTRY[formula]["lean_commit_sha"] == LEAN_COMMIT_SHA


# ── Receipt structure tests ───────────────────────────────────────────────────

class TestReceiptStructure:
    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_emit_returns_receipt_and_envelope(self, formula, inputs):
        receipt, envelope = emit_formula_receipt(formula, inputs)
        assert isinstance(receipt, FormulaReceipt)
        assert isinstance(envelope, dict)

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_receipt_has_all_required_fields(self, formula, inputs):
        receipt, _ = emit_formula_receipt(formula, inputs)
        for field in ("formula", "inputs_hash", "output", "lean_theorem",
                      "lean_file", "lean_commit_sha", "timestamp", "signature"):
            assert getattr(receipt, field, None) is not None, f"Missing field: {field}"

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_receipt_formula_name_matches(self, formula, inputs):
        receipt, _ = emit_formula_receipt(formula, inputs)
        assert receipt.formula == formula

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_receipt_lean_commit_sha_matches(self, formula, inputs):
        receipt, _ = emit_formula_receipt(formula, inputs)
        assert receipt.lean_commit_sha == LEAN_COMMIT_SHA

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_inputs_hash_is_64_hex(self, formula, inputs):
        receipt, _ = emit_formula_receipt(formula, inputs)
        assert len(receipt.inputs_hash) == 64
        assert all(c in "0123456789abcdef" for c in receipt.inputs_hash)

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_inputs_hash_is_deterministic(self, formula, inputs):
        r1, _ = emit_formula_receipt(formula, inputs)
        r2, _ = emit_formula_receipt(formula, inputs)
        assert r1.inputs_hash == r2.inputs_hash


# ── DSSE envelope tests ───────────────────────────────────────────────────────

class TestDSSEEnvelope:
    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_envelope_has_payload_payloadtype_signatures(self, formula, inputs):
        _, env = emit_formula_receipt(formula, inputs)
        assert "payload" in env
        assert "payloadType" in env
        assert "signatures" in env

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_envelope_payload_type_is_szl_receipt(self, formula, inputs):
        _, env = emit_formula_receipt(formula, inputs)
        assert env["payloadType"] == PAYLOAD_TYPE

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_envelope_signature_is_valid_base64(self, formula, inputs):
        _, env = emit_formula_receipt(formula, inputs)
        sig = env["signatures"][0]["sig"]
        decoded = base64.b64decode(sig)
        assert len(decoded) == 32  # HMAC-SHA-256 = 32 bytes

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_envelope_payload_decodes_to_receipt(self, formula, inputs):
        receipt, env = emit_formula_receipt(formula, inputs)
        raw = base64.b64decode(env["payload"])
        decoded = json.loads(raw)
        assert decoded["formula"] == formula
        assert decoded["lean_commit_sha"] == LEAN_COMMIT_SHA


# ── DSSE verification tests ───────────────────────────────────────────────────

class TestDSSEVerification:
    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_verify_returns_true_for_valid_envelope(self, formula, inputs):
        _, env = emit_formula_receipt(formula, inputs)
        valid, msg = FormulaReceipt.verify(env)
        assert valid is True, f"Verification failed: {msg}"

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_tampered_payload_fails_verification(self, formula, inputs):
        _, env = emit_formula_receipt(formula, inputs)
        # Corrupt the payload by appending a byte
        raw = base64.b64decode(env["payload"]) + b"x"
        tampered_env = {**env, "payload": base64.b64encode(raw).decode()}
        valid, _ = FormulaReceipt.verify(tampered_env)
        assert valid is False

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_wrong_hmac_key_fails_verification(self, formula, inputs):
        _, env = emit_formula_receipt(formula, inputs)
        valid, _ = FormulaReceipt.verify(env, hmac_key=b"wrong-key")
        assert valid is False


# ── Formula output tests ──────────────────────────────────────────────────────

class TestFormulaOutputs:
    def test_madhava_output_has_remainder_bound_nonneg(self):
        receipt, _ = emit_formula_receipt("MadhavaBound", MADHAVA_INPUTS)
        assert receipt.output["remainder_bound"] >= 0

    def test_madhava_partial_within_bound_of_arctan(self):
        receipt, _ = emit_formula_receipt("MadhavaBound", {"x": 1.0, "N": 20})
        import math as _math
        residual = abs(_math.atan(1.0) - receipt.output["partial"])
        assert residual <= receipt.output["remainder_bound"] + 1e-14

    def test_false_position_xstar_recovers_T(self):
        receipt, _ = emit_formula_receipt("FalsePosition", FALSE_POS_INPUTS)
        # f(x)=2x, xStar=2 → f(2)=4=T
        assert abs(2 * receipt.output["x_star"] - 4.0) < 1e-10

    def test_liu_hui_pi_estimate_less_than_pi(self):
        receipt, _ = emit_formula_receipt("LiuHuiPi", {"k": 4})
        assert receipt.output["pi_estimate"] < math.pi + 1e-12

    def test_liu_hui_96gon(self):
        receipt, _ = emit_formula_receipt("LiuHuiPi", {"k": 4})
        assert receipt.output["side_count"] == 96
        assert receipt.output["pi_estimate"] > 3.14

    def test_adversarial_epsilon2_equals_l1_l2_delta(self):
        receipt, _ = emit_formula_receipt("AdversarialRobustness", ADV_ROB_INPUTS)
        expected = 2.0 * 3.0 * 0.1
        assert abs(receipt.output["epsilon2"] - expected) < 1e-12

    def test_summation_invariant_holds(self):
        receipt, _ = emit_formula_receipt("SummationInvariant", SUMMATION_INPUTS)
        assert receipt.output["invariant_holds"] is True
        assert receipt.output["computed_total"] == 35

    def test_summation_invariant_broken_on_tamper(self):
        tampered = {**SUMMATION_INPUTS, "primary_cord": 36}
        receipt, _ = emit_formula_receipt("SummationInvariant", tampered)
        assert receipt.output["invariant_holds"] is False

    @pytest.mark.parametrize("formula,inputs", ALL_CASES)
    def test_lambda_score_in_0_1(self, formula, inputs):
        receipt, _ = emit_formula_receipt(formula, inputs)
        ls = receipt.output.get("lambda_score", None)
        assert ls is not None, f"{formula} missing lambda_score"
        assert 0 <= ls <= 1, f"{formula} lambda_score out of range: {ls}"


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_unknown_formula_raises(self):
        with pytest.raises(ValueError, match="Unknown formula"):
            emit_formula_receipt("NotAFormula", {})

    def test_madhava_x_out_of_range_raises(self):
        with pytest.raises(ValueError):
            emit_formula_receipt("MadhavaBound", {"x": 2.0, "N": 5})

    def test_liu_hui_k_negative_raises(self):
        with pytest.raises(ValueError):
            emit_formula_receipt("LiuHuiPi", {"k": -1})

    def test_adversarial_zero_delta_raises(self):
        with pytest.raises(ValueError):
            emit_formula_receipt("AdversarialRobustness", {"l1": 1.0, "l2": 1.0, "delta": 0.0})
