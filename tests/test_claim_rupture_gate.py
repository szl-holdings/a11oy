# SPDX-License-Identifier: Apache-2.0
"""Focused fail-closed checks for the SZL Claim Rupture Gate."""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import szl_claim_rupture_gate as rg


SHA_A = "a" * 64
SHA_B = "b" * 64
ROOT = Path(__file__).resolve().parents[1]


def _schema(name):
    return json.loads((ROOT / "schemas" / "evidenceos" / name).read_text(encoding="utf-8"))


def _validator(name):
    schema = _schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


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


def _evaluate_payload():
    return {
        "claims": [_claim()],
        "external_signals": {
            "claim-1": {
                "semantic_uncertainty": _semantic(0.2),
                "factuality": _factuality(rg.SUPPORTED),
            }
        },
        "contradictions": [],
    }


def test_atomize_request_contract_and_schema_are_strict_and_bounded():
    parsed = rg.parse_atomize_request({"text": "  Claim one.  "})
    assert parsed == {"text": "  Claim one.  "}
    assert list(_validator("claim-atomize-request.v1.schema.json").iter_errors(parsed)) == []

    invalid = [
        None,
        {},
        {"text": 4},
        {"text": " \n\t "},
        {"text": "x", "ignored": True},
        {"text": "x" * (rg.MAX_ATOMIZE_TEXT_CHARS + 1)},
    ]
    for payload in invalid:
        with pytest.raises(rg.ClaimContractError):
            rg.parse_atomize_request(payload)


def test_evaluate_request_normalizes_defaults_and_matches_schema():
    parsed = rg.parse_evaluate_request(_evaluate_payload())
    assert parsed["claims"][0]["claim_id"] == "claim-1"
    assert parsed["external_signals"]["claim-1"]["semantic_uncertainty"]["value"] == 0.2
    assert parsed["contradictions"] == []
    assert list(_validator("claim-evaluate-request.v1.schema.json").iter_errors(parsed)) == []

    defaults = rg.parse_evaluate_request({"claims": []})
    assert defaults == {"claims": [], "external_signals": {}, "contradictions": []}


def test_contract_accepts_epistemic_incompleteness_for_fail_closed_rubric():
    payload = {
        "claims": [{
            "claim_id": "claim-incomplete",
            "statement": "This claim deliberately lacks complete evidence and ownership.",
            "atomic": True,
            "evidence_refs": [{"reference_id": "source-open", "provenance": {}}],
            "consequence_owner": {},
        }]
    }
    parsed = rg.parse_evaluate_request(payload)
    row = rg.evaluate_claims(**parsed)["claims"][0]
    assert row["state"] == rg.UNKNOWN
    assert row["abstain_required"] is True
    assert {"RG-004", "RG-005"}.issubset(row["rubric_codes"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"unknown": True}),
        lambda payload: payload["claims"][0].update({"unknown": True}),
        lambda payload: payload["claims"][0]["evidence_refs"][0].update({"unknown": True}),
        lambda payload: payload["external_signals"]["claim-1"].update({"unknown": True}),
        lambda payload: payload["external_signals"]["claim-1"]["factuality"].update(
            {"unknown": True}
        ),
    ],
)
def test_evaluate_request_rejects_unknown_fields_at_every_layer(mutate):
    payload = _evaluate_payload()
    mutate(payload)
    with pytest.raises(rg.ClaimContractError, match="unknown field"):
        rg.parse_evaluate_request(payload)


def test_evaluate_request_rejects_cross_record_identifier_ambiguity():
    duplicate = _evaluate_payload()
    duplicate["claims"].append({**_claim(), "statement": "A second statement."})
    with pytest.raises(rg.ClaimContractError, match="must be unique"):
        rg.parse_evaluate_request(duplicate)

    orphan_signal = _evaluate_payload()
    orphan_signal["external_signals"] = {"missing-claim": {}}
    with pytest.raises(rg.ClaimContractError, match="explicit claim_id"):
        rg.parse_evaluate_request(orphan_signal)

    orphan_contradiction = _evaluate_payload()
    orphan_contradiction["contradictions"] = [{"claim_ids": ["missing-claim"]}]
    with pytest.raises(rg.ClaimContractError, match="unknown claim_id"):
        rg.parse_evaluate_request(orphan_contradiction)

    invalid_subset = _evaluate_payload()
    invalid_subset["claims"].append({**_claim(), "claim_id": "claim-2"})
    invalid_subset["contradictions"] = [{
        "claim_ids": ["claim-1"],
        "refutes_claim_ids": ["claim-2"],
    }]
    with pytest.raises(rg.ClaimContractError, match="subset"):
        rg.parse_evaluate_request(invalid_subset)


@pytest.mark.parametrize(
    "payload",
    [
        {"claims": [{}] * (rg.MAX_CLAIMS + 1)},
        {"claims": [{"statement": "x" * (rg.MAX_STATEMENT_CHARS + 1)}]},
        {"claims": [{"evidence_refs": [{}] * (rg.MAX_EVIDENCE_REFS_PER_CLAIM + 1)}]},
        {"claims": [], "contradictions": [{}] * (rg.MAX_CONTRADICTIONS + 1)},
        {
            "claims": [{"claim_id": f"c-{index}"} for index in range(rg.MAX_EXTERNAL_SIGNALS + 1)],
            "external_signals": {
                f"c-{index}": {} for index in range(rg.MAX_EXTERNAL_SIGNALS + 1)
            },
        },
        {
            "claims": [{"claim_id": f"c-{index}"} for index in range(rg.MAX_CLAIMS)],
            "contradictions": [{
                "claim_ids": [f"c-{index}" for index in range(rg.MAX_CLAIM_IDS_PER_CONTRADICTION)]
                + ["c-extra"]
            }],
        },
    ],
)
def test_evaluate_request_rejects_unbounded_work(payload):
    with pytest.raises(rg.ClaimContractError):
        rg.parse_evaluate_request(payload)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload["external_signals"]["claim-1"]["semantic_uncertainty"].update(
            {"value": True}
        ),
        lambda payload: payload["external_signals"]["claim-1"]["semantic_uncertainty"].update(
            {"value": 1.01}
        ),
        lambda payload: payload["external_signals"]["claim-1"]["factuality"].update(
            {"state": "CERTAIN"}
        ),
        lambda payload: payload["claims"][0]["evidence_refs"][0]["provenance"].update(
            {"content_sha256": "not-a-digest"}
        ),
    ],
)
def test_evaluate_request_rejects_malformed_typed_signals(mutator):
    payload = _evaluate_payload()
    mutator(payload)
    with pytest.raises(rg.ClaimContractError):
        rg.parse_evaluate_request(payload)


def test_runtime_and_json_schema_refuse_the_same_structural_attack_shapes():
    validator = _validator("claim-evaluate-request.v1.schema.json")
    structural_attacks = [
        {"claims": [], "extra": "smuggled"},
        {"claims": [{"atomic": 1}]},
        {"claims": [{"evidence_refs": [{}] * (rg.MAX_EVIDENCE_REFS_PER_CLAIM + 1)}]},
        {"claims": [], "external_signals": {" ": {}}},
        {"claims": [], "contradictions": [{"status": "CONCEALED"}]},
    ]
    for payload in structural_attacks:
        assert list(validator.iter_errors(payload)), payload
        with pytest.raises(rg.ClaimContractError):
            rg.parse_evaluate_request(payload)


def test_parser_returns_a_detached_sanitized_copy():
    payload = _evaluate_payload()
    parsed = rg.parse_evaluate_request(payload)
    payload["claims"][0]["statement"] = "mutated after validation"
    payload["external_signals"]["claim-1"]["factuality"]["state"] = rg.REFUTED
    assert parsed["claims"][0]["statement"] != "mutated after validation"
    assert parsed["external_signals"]["claim-1"]["factuality"]["state"] == rg.SUPPORTED


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


def test_structural_atomizer_refuses_candidate_amplification():
    with pytest.raises(rg.ClaimContractError, match="more than 32 candidates"):
        rg.atomize_text("x. " * (rg.MAX_ATOMIZE_CANDIDATES + 1))


def test_claim_identifiers_are_canonical_before_uniqueness_checks():
    parsed = rg.parse_evaluate_request({"claims": [{"claim_id": "  claim-1  "}]})
    assert parsed["claims"][0]["claim_id"] == "claim-1"

    with pytest.raises(rg.ClaimContractError, match="unique"):
        rg.parse_evaluate_request(
            {"claims": [{"claim_id": "claim-1"}, {"claim_id": " claim-1 "}]}
        )

    with pytest.raises(rg.ClaimContractError, match="collide after identifier normalization"):
        rg.parse_evaluate_request(
            {
                "claims": [{"claim_id": "claim-1"}],
                "external_signals": {"claim-1": {}, " claim-1 ": {}},
            }
        )


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
