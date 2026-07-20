# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
"""Focused contract tests for the pure EvidenceOS Involution Probe."""

import math

import szl_involution_probe as probe


def evaluate(**overrides):
    values = {
        "pair_id": "pair-001",
        "left_observation": [1.0, 3.0, -2.0, 5.0],
        "transformed_observation": [3.0, 1.0, 5.0, -2.0],
        "permutation": [1, 0, 3, 2],
    }
    values.update(overrides)
    return probe.evaluate_involution_pair(**values)


def test_symmetric_pair_has_zero_antisymmetric_component():
    result = evaluate()
    assert result["ok"] is True
    assert result["verdict"] == probe.VERDICT_DECOMPOSED
    assert result["decomposition"]["aligned_transformed"] == [1.0, 3.0, -2.0, 5.0]
    assert result["decomposition"]["symmetric"] == [1.0, 3.0, -2.0, 5.0]
    assert result["decomposition"]["antisymmetric"] == [0.0, 0.0, 0.0, 0.0]
    assert result["closure"]["paired_delta_linf"] == 0.0


def test_injected_asymmetry_is_recovered_with_sign_and_reconstructs_pair():
    # P^-1 y is [0.5, 3.5], so S=[0.75,3.25] and A=[0.25,-0.25].
    result = evaluate(
        left_observation=[1.0, 3.0],
        transformed_observation=[3.5, 0.5],
        permutation=[1, 0],
    )
    assert result["decomposition"]["symmetric"] == [0.75, 3.25]
    assert result["decomposition"]["antisymmetric"] == [0.25, -0.25]
    assert result["closure"]["pair_reconstruction_residual_linf"] == 0.0
    assert result["closure"]["permutation_closure_residual"] == 0


def test_identity_is_a_valid_involution():
    result = evaluate(
        left_observation=[2.0, 6.0],
        transformed_observation=[4.0, 2.0],
        permutation=[0, 1],
    )
    assert result["ok"] is True
    assert result["decomposition"]["symmetric"] == [3.0, 4.0]
    assert result["decomposition"]["antisymmetric"] == [-1.0, 2.0]


def test_deterministic_output_and_stable_digests():
    first = evaluate()
    second = evaluate()
    assert first == second
    assert first["digests"] == second["digests"]
    assert len(first["digests"]["input_sha256"]) == 64
    assert len(first["digests"]["result_sha256"]) == 64


def test_digest_changes_when_an_observation_changes():
    first = evaluate()
    second = evaluate(left_observation=[1.0, 3.0, -2.0, 5.5])
    assert first["digests"]["input_sha256"] != second["digests"]["input_sha256"]
    assert first["digests"]["result_sha256"] != second["digests"]["result_sha256"]


def test_missing_pair_refuses_closed():
    result = evaluate(transformed_observation=None)
    assert result["ok"] is False
    assert result["verdict"] == probe.VERDICT_REFUSED
    assert result["refusal"]["code"] == "PAIR_MISSING"


def test_pair_dimension_mismatch_refuses_closed():
    result = evaluate(transformed_observation=[1.0, 2.0])
    assert result["ok"] is False
    assert result["refusal"]["code"] == "PAIR_DIMENSION_MISMATCH"


def test_non_bijective_permutation_refuses_closed():
    result = evaluate(permutation=[0, 0, 3, 2])
    assert result["ok"] is False
    assert result["refusal"]["code"] == "PERMUTATION_NOT_BIJECTIVE"


def test_bijective_but_non_involutive_permutation_refuses_closed():
    result = evaluate(
        left_observation=[1.0, 2.0, 3.0],
        transformed_observation=[1.0, 2.0, 3.0],
        permutation=[1, 2, 0],
    )
    assert result["ok"] is False
    assert result["refusal"]["code"] == "PERMUTATION_NOT_INVOLUTION"


def test_out_of_range_permutation_refuses_closed():
    result = evaluate(permutation=[1, 0, 3, 4])
    assert result["ok"] is False
    assert result["refusal"]["code"] == "PERMUTATION_OUT_OF_RANGE"


def test_nonfinite_and_overbound_values_refuse_closed():
    nonfinite = evaluate(left_observation=[1.0, math.inf, -2.0, 5.0])
    assert nonfinite["ok"] is False
    assert nonfinite["refusal"]["code"] == "VECTOR_NONFINITE"

    overbound = evaluate(left_observation=[probe.MAX_ABS_VALUE + 1.0, 3.0, -2.0, 5.0])
    assert overbound["ok"] is False
    assert overbound["refusal"]["code"] == "VALUE_OUT_OF_BOUNDS"


def test_dimension_and_pair_id_bounds_refuse_closed():
    oversized_vector = [0.0] * (probe.MAX_DIMENSION + 1)
    dimension = evaluate(
        left_observation=oversized_vector,
        transformed_observation=oversized_vector,
        permutation=list(range(len(oversized_vector))),
    )
    assert dimension["ok"] is False
    assert dimension["refusal"]["code"] == "DIMENSION_OUT_OF_BOUNDS"

    pair_id = evaluate(pair_id="x" * (probe.MAX_PAIR_ID_BYTES + 1))
    assert pair_id["ok"] is False
    assert pair_id["refusal"]["code"] == "PAIR_ID_TOO_LARGE"

    invalid_utf8 = evaluate(pair_id="bad-\ud800-id")
    assert invalid_utf8["ok"] is False
    assert invalid_utf8["refusal"]["code"] == "PAIR_ID_INVALID"


def test_labels_citations_and_no_effects_are_explicit():
    result = evaluate()
    assert result["labels"]["algebraic_contract"] == probe.LABEL_PROVEN
    assert result["labels"]["computed_observation"] == probe.LABEL_MODELED
    assert result["labels"]["external_findings"] == probe.LABEL_REPORTED
    assert result["labels"]["adds_to_locked_8"] == 0
    assert {citation["doi"] for citation in result["citations"]} == {
        probe.ARTICLE_DOI,
        probe.DATA_CODE_DOI,
    }
    assert result["effects"] == {
        "writes": 0,
        "signatures": 0,
        "effectors": 0,
        "network_calls": 0,
    }
    assert result["digests"]["signed"] is False


def test_refusal_is_deterministic_and_carries_honest_labels_and_citations():
    first = evaluate(permutation=None)
    second = evaluate(permutation=None)
    assert first == second
    assert first["labels"]["algebraic_contract"] == probe.LABEL_PROVEN
    assert first["labels"]["computed_observation"] == probe.LABEL_MODELED
    assert first["labels"]["external_findings"] == probe.LABEL_REPORTED
    assert {citation["doi"] for citation in first["citations"]} == {
        probe.ARTICLE_DOI,
        probe.DATA_CODE_DOI,
    }
    assert first["digest"]["signed"] is False
