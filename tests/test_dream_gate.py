# SPDX-License-Identifier: Apache-2.0
from szl_dream_gate import (
    classify_claim,
    counterfactual_requirements,
    dream_status,
    hash_unknown,
    negative_knowledge,
    promote,
)


def test_agi_wish_is_forbidden_promotion():
    c = classify_claim("keep pushing the frontier make it all agi")
    assert c["kind"] == "FORBIDDEN_PROMOTION"
    assert c["promote"] is False


def test_empty_claim_is_unknown():
    assert classify_claim("")["kind"] == "UNKNOWN"


def test_cannot_promote_agi_even_with_all_done_and_http_200():
    out = promote("artificial general intelligence", {"all_done": True, "http": 200})
    assert out["decision"] == "BLOCKED"
    assert out["agi_claim"] is False


def test_ordinary_dream_holds():
    out = promote("a quieter operator shell")
    assert out["decision"] == "HOLD"
    assert out["agi_claim"] is False


def test_hash_linked_is_not_signed():
    rec = hash_unknown("compiled kernel v1")
    assert rec["signed"] is False
    assert rec["honesty"] == "UNSIGNED-LOCAL"
    assert rec["hash"].startswith("sha3-256:")


def test_prior_changes_hash():
    a = hash_unknown("x")
    b = hash_unknown("x", prior=a["hash"])
    assert a["hash"] != b["hash"]


def test_counterfactual_list_is_not_satisfaction():
    cf = counterfactual_requirements("undreamed capability")
    assert cf["all_done"] is False
    assert cf["satisfied"] == []
    assert cf["promote"] is False


def test_negative_knowledge_catalog():
    nk = negative_knowledge()
    assert nk["count"] >= 1
    assert nk["agi_claim"] is False
    assert nk["zero_stays_zero"] is False


def test_status_denies_agi():
    s = dream_status()
    assert s["agi_claim"] is False
    assert s["estate_gate"] == "HOLD"
    assert s["trust_ceiling"] == 0.97
    assert s["trust_ceiling_kind"] == "policy"
