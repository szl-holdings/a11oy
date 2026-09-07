from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WAVE = ROOT / "model_release" / "frontier-qualification" / "top-choice-wave-2026-09-07.json"


def _wave() -> dict:
    return json.loads(WAVE.read_text(encoding="utf-8"))


def test_top_choice_wave_is_fail_closed_and_revision_bound() -> None:
    wave = _wave()
    assert wave["schema_version"] == "szl.frontier-top-choice-governance.v1"
    assert wave["status"] == "GOVERNED_PLAN_NOT_LOCAL_QUALIFICATION"
    assert wave["default_effect"] == "HOLD"
    assert wave["production_authorization_eligible"] is False
    assert wave["upstream_claims_are_local_measurements"] is False
    assert wave["canonical_frontier"]["revision"] == "94a039d086d1343d1fcfe5bca617f601006ca05b"
    revisions = wave["consumer_revisions"]
    assert revisions["szl-serve"] == "74c2fa12ee3cd17cc8d80ac85801f11683912176"
    assert revisions["szl-kernels"] == "24d06d1f3dc987d82d5920a9e32348a98541799f"
    assert revisions["szl-nemo"] == "fd5bfd21abb7a453506a00dc2d69f7aca7954d1a"
    assert revisions["szl-router"] == "2dd475b6147cb26dbb956e9c3e12530103a16af8"
    assert revisions["szl-second-brain"] == "956a96a6e62d1a6bdf8dd1a37bec6ba18225396c"


def test_a11oy_keeps_model_and_runtime_outputs_non_authoritative() -> None:
    rule = _wave()["authorization_rule"]
    assert rule["model_or_runtime_output_is_never_action_authority"] is True
    assert rule["all_candidate_outputs_are_proposal_or_evidence_only"] is True
    assert rule["silent_substitution_allowed"] is False
    assert rule["upstream_benchmark_claim_can_authorize_promotion"] is False
    required = " ".join(rule["required_before_any_production_authorization"]).lower()
    assert "no unresolved hold gate" in required
    assert "explicit a11oy production authorization receipt" in required


def test_all_five_candidates_are_present_and_held() -> None:
    candidates = {row["id"]: row for row in _wave()["candidates"]}
    assert set(candidates) == {
        "k2-horizon-mova-36b-a4b-2026-09-03",
        "neomme-2026-09-03",
        "funes-agent-memory-2026-09-03",
        "hf-webgpu-kernels-2026-09-01",
        "vaani-noise-event-2026-08-07",
    }
    for candidate in candidates.values():
        assert candidate["current_effect"] in {"HOLD", "GATED_HOLD"}
        assert candidate["required_evidence_sources"]
        assert candidate["hard_blockers"]


def test_vaani_remains_gated_and_k2_not_route_eligible() -> None:
    candidates = {row["id"]: row for row in _wave()["candidates"]}
    vaani = candidates["vaani-noise-event-2026-08-07"]
    assert vaani["current_effect"] == "GATED_HOLD"
    blockers = " ".join(vaani["hard_blockers"]).lower()
    assert "must not be bypassed" in blockers
    assert "no payload download" in blockers

    k2 = candidates["k2-horizon-mova-36b-a4b-2026-09-03"]
    blockers = " ".join(k2["hard_blockers"]).lower()
    assert "routing_eligibility=false" in blockers


def test_non_claims_preserve_upstream_attribution() -> None:
    non_claims = " ".join(_wave()["non_claims"]).lower()
    assert "not szl local measurements" in non_claims
    assert "rebranded as an szl-originated invention" in non_claims
    assert "no candidate can promote itself" in non_claims
