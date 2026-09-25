# SPDX-License-Identifier: Apache-2.0
"""Offline tests for szl_jev_gate — no TypeSafe key required."""
from __future__ import annotations

import szl_jev_gate as g


def test_status_is_not_agi() -> None:
    s = g.jev_status()
    assert s["agi_claim"] is False
    assert s["promotion"] == "denied"
    assert s["trust_ceiling"] == 0.97
    assert s["lambda"] == "Conjecture 1"


def test_questions_match_system_one_types() -> None:
    qs = g.questions()
    assert qs["claim_kind"]["type"] == "choice"
    assert set(qs["claim_kind"]["criteria"]) == {"MEASURED", "DREAMED", "FORBIDDEN_PROMOTION"}
    assert qs["card_relation"]["type"] == "choice"
    assert set(qs["card_relation"]["criteria"]) == {"supports", "contradicts", "says_nothing"}
    assert qs["promote_ok"]["type"] == "noul"
    assert qs["evidence_strength"]["type"] == "score"
    assert len(qs["evidence_strength"]["criteria"]) == 4


def test_agi_wish_is_blocked_even_if_jev_were_bound() -> None:
    answers = {
        "claim_kind": {"choice": "MEASURED", "confidence": 0.99},
        "card_relation": {"choice": "supports", "confidence": 0.99},
        "promote_ok": {"noul": 0.99},
        "evidence_strength": {"score": 0.99},
    }
    out = g.compose("make it all AGI now", "a model card with 2M downloads", answers)
    assert out["verdict"] == "BLOCKED"
    assert out["all_done"] is False
    assert out["promotion"] == "denied"
    assert out["agi_claim"] is False


def test_says_nothing_is_unknown() -> None:
    answers = {
        "claim_kind": {"choice": "DREAMED", "confidence": 0.9},
        "card_relation": {"choice": "says_nothing", "confidence": 0.9},
        "promote_ok": {"noul": 0.1},
        "evidence_strength": {"score": 0.1},
    }
    out = g.compose("this Space is LIVE AGI", "downloads: 12", answers)
    assert out["verdict"] in {"UNKNOWN", "BLOCKED"}
    assert out["promotion"] == "denied"


def test_low_confidence_abstains() -> None:
    answers = {
        "claim_kind": {"choice": "MEASURED", "confidence": 0.4},
        "card_relation": {"choice": "supports", "confidence": 0.4},
        "promote_ok": {"noul": 0.4},
        "evidence_strength": {"score": 0.4},
    }
    out = g.compose("console paints Command Center chrome", "HTML contains LIVE label", answers)
    assert out["verdict"] == "ABSTAIN"
    assert out["all_done"] is False


def test_trust_never_exceeds_ceiling() -> None:
    answers = {
        "claim_kind": {"choice": "MEASURED", "confidence": 1.0},
        "card_relation": {"choice": "supports", "confidence": 1.0},
        "promote_ok": {"noul": 1.0},
        "evidence_strength": {"score": 1.0},
    }
    out = g.compose("trust ceiling 0.97 is policy", "doctrine lock", answers)
    assert out["trust"]["admitted"] <= g.TRUST_CEILING
    assert out["trust"]["kind"] == "policy"


def test_judge_without_key_is_software_fallback() -> None:
    out = g.judge("keep pushing the frontier make it all AGI")
    assert out["source"] == "software-fallback"
    assert out["verdict"] == "BLOCKED"
    assert out["engine"]["bound"] is False


def test_register_without_fastapi_is_noop() -> None:
    class _App:
        pass

    report = g.register(_App())
    assert report["ok"] is False or "registered" in report
