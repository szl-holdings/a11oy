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


# ---- CVSS v3.1 enrichment (FIRST.org arithmetic, deterministic + auditable) ----

def test_cvss_reference_vectors_exact():
    # FIRST.org spec examples
    r = bs.cvss_v31_base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert r["score"] == 9.8 and r["severity"] == "CRITICAL"
    r2 = bs.cvss_v31_base_score("CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N")
    assert r2["score"] == 3.1 and r2["severity"] == "LOW"
    r3 = bs.cvss_v31_base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H")
    assert r3["score"] == 10.0 and r3["severity"] == "CRITICAL"  # scope-changed formula


def test_cvss_malformed_never_scored():
    assert bs.cvss_v31_base_score("CVSS:3.1/AV:N/garbage") is None
    assert bs.cvss_v31_base_score("") is None
    assert bs.cvss_v31_base_score("not a vector") is None
    assert bs.parse_cvss_v31("CVSS:3.1/AV:Q/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is None


def test_triage_enrichment_cve_and_cvss():
    sig = ("alert: exploit attempt CVE-2026-12345 "
           "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H union select from users")
    t = bs.triage_signal(sig)
    e = t["enrichment"]
    assert e["cve_ids"] == ["CVE-2026-12345"]
    assert e["cvss"]["score"] == 9.8 and e["cvss"]["severity"] == "CRITICAL"
    assert e["cvss_weight_added"] == 4  # deterministic, shown
    assert t["score"] > 4  # injection rule (4) + cvss critical weight (4)
    # still auditable: rules also returned
    assert "web-injection" in [m["rule_id"] for m in t["matched_rules"]]


def test_triage_malformed_vector_recorded_not_scored():
    t = bs.triage_signal("scanner output CVSS:3.1/AV:N/garbage benign text")
    e = t.get("enrichment", {})
    assert e.get("cvss", {}).get("score") is None  # recorded, never fabricated
    assert "cvss_weight_added" not in e
    assert t["score"] == 0  # nothing fabricated


def test_benign_signal_still_informational_with_enrichment():
    t = bs.triage_signal("CVE-2024-0001 noted in report CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N")
    # LOW severity (1.8) adds weight 1 -> REVIEW-LOW, not critical
    assert t["enrichment"]["cvss"]["severity"] == "LOW"
    assert t["priority"] == bs.PRIORITY_LOW
