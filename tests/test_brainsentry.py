# SPDX-License-Identifier: Apache-2.0
"""Tests for szl_brainsentry — defensive-cyber signal triage (blue-team, transparent)."""
import szl_brainsentry as bs


def test_no_signals_is_unavailable_never_fabricated():
    r = bs.triage([])
    assert r["label"] == bs.LBL_UNAVAILABLE and r["verdict"] == "UNAVAILABLE"
    assert r["ranked"] == []


def test_score_is_transparent_rule_sum_and_auditable():
    t = bs.triage_signal("sudo: COMMAND=/bin/sh to root")  # priv-esc weight 4
    assert t["score"] == 4
    assert t["matched_count"] == 1
    assert t["matched_rules"][0]["rule_id"] == "priv-esc"
    assert "why" in t["matched_rules"][0]  # every match explains itself (auditable)


def test_multi_indicator_ranks_high_or_critical():
    bad = "base64 -enc " + "A" * 50 + " powershell; wevtutil cl Security; sudo to root"
    t = bs.triage_signal(bad)
    assert t["priority"] in (bs.PRIORITY_CRITICAL, bs.PRIORITY_HIGH)
    assert t["matched_count"] >= 2


def test_benign_is_informational():
    assert bs.triage_signal("user logged in successfully")["priority"] == bs.PRIORITY_INFO


def test_batch_ranked_highest_first():
    r = bs.triage(["benign heartbeat", "union select password from users", "failed password for root"])
    scores = [x["score"] for x in r["ranked"]]
    assert scores == sorted(scores, reverse=True)  # highest priority first
    assert r["verdict"] in (bs.PRIORITY_HIGH, bs.PRIORITY_MEDIUM, bs.PRIORITY_CRITICAL)


def test_surface_never_claims_malice_or_acts():
    # the note and doctrine must state ranking-only, human-adjudicated, no action
    r = bs.triage(["union select 1"])
    assert "never claims" in r["note"] or "human-required" in r["note"]
    d = bs._doctrine_block()
    assert d["takes_action"] is False
    assert d["posture"] == "DEFENSIVE-BLUE-TEAM-ONLY"


def test_receipt_deterministic_unsigned_write_only():
    r = bs.triage(["failed password for admin"])
    a = bs.content_receipt(r)["content_sha256"]
    assert a == bs.content_receipt(r)["content_sha256"]
    assert len(a) == 64 and bs.content_receipt(r)["signed"] is False
    assert "receipt" not in bs.handle_info("s")       # GET info mints nothing
    assert "receipt" in bs.handle_triage(["x"], "s")  # POST triage mints one


def test_manifest_native_ok_defensive_invariants():
    man = bs.handle_manifest("s")
    assert man["surface_id"] == "brainsentry" and man["data_label"] == bs.LBL_MODELED
    inv = man["honesty_invariants"]
    assert all(inv.values())
    assert inv["defensive_only_not_offensive"] is True
    assert inv["not_counter_uas"] is True
    assert inv["takes_no_action"] is True
    assert inv["never_claims_malice_human_adjudicates"] is True
    assert inv["score_is_transparent_rule_sum"] is True


def test_doctrine_honest_and_defensive():
    d = bs._doctrine_block()
    assert d["lambda"] == "Conjecture 1" and d["adds_to_locked_8"] == 0
    assert d["is_model_training"] is False and d["sentience_claim"] is False
    assert d["takes_action"] is False


def test_rule_families_are_defensive_mitre_flavored():
    # sanity: rules are detection indicators, not exploit payloads
    ids = {r["id"] for r in bs.RULES}
    assert "auth-bruteforce" in ids and "ransomware-note" in ids and "c2-beacon" in ids
    for r in bs.RULES:
        assert "ATT&CK" in r["why"] or "threat intel" in r["why"] or "defensive" in r["why"]


def test_selftest_passes():
    out = bs._selftest()
    assert out["ok"] is True and out["checks"] >= 7
