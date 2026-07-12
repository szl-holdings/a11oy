# SPDX-License-Identifier: Apache-2.0
"""Focused fail-closed checks for the SZL Claim Rupture Gate."""

import hashlib
import json

import szl_claim_rupture_gate as rg


SHA_A = "a" * 64
SHA_B = "b" * 64


def _owner():
    return {"owner_id": "operator:stephen", "accountability_scope": "public technical claim"}


def _evidence(state=rg.SUPPORTED, *, verification=False):
    row = {
        "reference_id": "source-1",
        "evidence_state": state,
        "provenance": {"source_id": "repo:szl", "content_sha256": SHA_A},
    }
    if verification:
        row["verification_ref"] = "receipt:independent-replay-1"
    return [row]


def _claim(state=rg.SUPPORTED, *, verification=False):
    return {
        "claim_id": "claim-1",
        "statement": "The candidate passed the pinned local contract suite.",
        "atomic": True,
        "evidence_refs": _evidence(state, verification=verification),
        "consequence_owner": _owner(),
    }


def _factuality(state):
    return {"state": state, "source_ref": "eval:frozen-contract-1", "method": "independent replay"}


def _semantic(value):
    return {"value": value, "source_ref": "eval:calibrator-1", "method": "held-out calibration"}


def test_structural_atomizer_never_pretends_semantic_atomicity():
    out = rg.atomize_text("Alpha passed.\nBeta remains open; Gamma is unknown.")
    assert out["candidate_count"] == 3
    assert out["semantic_atomization_computed"] is False
    assert out["decision_state"] == rg.PROPOSAL_ONLY and out["effectors_enabled"] == 0
    assert all(a["atomic"] is False and a["human_review_required"] for a in out["atoms"])
    evaluation = rg.evaluate_claims(out["atoms"])
    assert evaluation["overall_state"] == rg.UNKNOWN
    assert evaluation["gate_outcome"] == "ABSTAIN"
    assert all("RG-002" in a["rubric_codes"] for a in evaluation["claims"])


def test_missing_evidence_provenance_or_owner_fails_closed():
    no_evidence = {**_claim(), "evidence_refs": []}
    no_provenance = {**_claim(), "evidence_refs": [{"reference_id": "x", "evidence_state": rg.SUPPORTED}]}
    no_owner = {**_claim(), "consequence_owner": None}
    for claim, code in [(no_evidence, "RG-003"), (no_provenance, "RG-004"), (no_owner, "RG-005")]:
        row = rg.evaluate_claims([claim])["claims"][0]
        assert row["state"] == rg.UNKNOWN
        assert row["abstain_required"] is True and code in row["rubric_codes"]


def test_bare_verified_label_is_not_accepted_as_verification():
    row = rg.evaluate_claims([_claim(rg.VERIFIED, verification=False)])["claims"][0]
    assert row["state"] == rg.UNKNOWN
    assert "RG-004" in row["rubric_codes"]


def test_all_five_states_are_distinct_and_reachable():
    verified = rg.evaluate_claims(
        [_claim(rg.VERIFIED, verification=True)],
        external_signals={"claim-1": {"factuality": _factuality(rg.VERIFIED), "semantic_uncertainty": _semantic(0.1)}},
    )["overall_state"]
    supported = rg.evaluate_claims([_claim(rg.SUPPORTED)])["overall_state"]
    uncertain = rg.evaluate_claims([_claim(rg.UNCERTAIN)])["overall_state"]
    refuted = rg.evaluate_claims([_claim(rg.REFUTED)])["overall_state"]
    unknown = rg.evaluate_claims([{**_claim(), "evidence_refs": []}])["overall_state"]
    assert [verified, supported, uncertain, refuted, unknown] == list(rg.CLAIM_STATES)


def test_verified_evidence_without_factuality_is_only_supported():
    out = rg.evaluate_claims([_claim(rg.VERIFIED, verification=True)])
    assert out["overall_state"] == rg.SUPPORTED
    assert out["abstain_required"] is False


def test_external_signals_are_carried_but_never_computed_by_gate():
    out = rg.evaluate_claims(
        [_claim()],
        external_signals={"claim-1": {"semantic_uncertainty": _semantic(0.2), "factuality": _factuality(rg.SUPPORTED)}},
    )
    signals = out["claims"][0]["external_signals"]
    assert signals["semantic_uncertainty"]["value"] == 0.2
    assert signals["semantic_uncertainty"]["computed_by_gate"] is False
    assert signals["factuality"]["computed_by_gate"] is False
    assert signals["computed_by_gate"] == []
    assert out["signal_contract"]["computed_by_gate"] == []


def test_malformed_or_untraceable_external_signal_fails_closed():
    malformed = {"semantic_uncertainty": {"value": 0.1}}
    row = rg.evaluate_claims([_claim()], external_signals={"claim-1": malformed})["claims"][0]
    assert row["state"] == rg.UNKNOWN and "RG-008" in row["rubric_codes"]


def test_high_external_semantic_uncertainty_requires_abstention():
    row = rg.evaluate_claims(
        [_claim()], external_signals={"claim-1": {"semantic_uncertainty": _semantic(0.66)}}
    )["claims"][0]
    assert row["state"] == rg.UNCERTAIN
    assert row["abstain_required"] is True and "RG-009" in row["rubric_codes"]


def test_unresolved_contradiction_fails_closed_without_resolving_it():
    claim2 = {**_claim(), "claim_id": "claim-2", "statement": "The candidate did not pass the suite."}
    contradiction = [{
        "claim_ids": ["claim-1", "claim-2"],
        "status": "UNRESOLVED",
        "provenance": {"source_id": "detector:transparent", "content_sha256": SHA_B},
    }]
    out = rg.evaluate_claims([_claim(), claim2], contradictions=contradiction)
    assert out["overall_state"] == rg.UNCERTAIN and out["gate_outcome"] == "ABSTAIN"
    for row in out["claims"]:
        assert row["state"] == rg.UNCERTAIN and "RG-006" in row["rubric_codes"]
        assert row["contradictions"][0]["status"] == "UNRESOLVED"


def test_traceable_explicit_refutation_remains_refuted():
    contradiction = [{
        "claim_ids": ["claim-1"],
        "refutes_claim_ids": ["claim-1"],
        "status": "CONFIRMED",
        "provenance": {"source_id": "replay:negative-test", "receipt_ref": "receipt:failed-1"},
    }]
    row = rg.evaluate_claims([_claim()], contradictions=contradiction)["claims"][0]
    assert row["state"] == rg.REFUTED and "RG-007" in row["rubric_codes"]


def test_every_result_is_proposal_only_with_zero_effectors():
    out = rg.evaluate_claims([_claim()])
    assert out["decision_state"] == rg.PROPOSAL_ONLY and out["effectors_enabled"] == 0
    assert out["claims"][0]["decision_state"] == rg.PROPOSAL_ONLY
    assert out["claims"][0]["effectors_enabled"] == 0
    assert out["honesty_invariants"]["effectors_are_zero"] is True


def test_unsigned_receipt_is_deterministic_and_matches_core_payload():
    out1 = rg.evaluate_claims([_claim()])
    out2 = rg.evaluate_claims([_claim()])
    assert out1["receipt"] == out2["receipt"]
    receipt = out1["receipt"]
    assert receipt["signed"] is False and receipt["attests_truth"] is False
    assert receipt["mode"] == "UNSIGNED-CONTENT-DIGEST"
    core = {k: v for k, v in out1.items() if k != "receipt"}
    expected = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert receipt["content_sha256"] == expected


def test_info_exposes_open_rubric_and_read_only_surface():
    info = rg.info()
    assert info["rubric"] == rg.ERROR_RUBRIC
    assert set(info["states"]) == set(rg.CLAIM_STATES)
    assert all(route["mutates"] is False for route in info["intended_read_only_api"])
    assert info["effectors_enabled"] == 0

