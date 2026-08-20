# SPDX-License-Identifier: Apache-2.0
"""Tests for szl_feature_badge — honest badge-state rules + live proof resolution."""
import szl_feature_badge as fb


def test_proven_theorem_is_theorem_backed_and_hash_resolves():
    b = fb.build_badge("khipu-checksum-invariant")
    assert b["badge_state"] == "THEOREM-BACKED"
    lp = b["provenance_chain"]["lean_proof"]
    assert lp["proof_file_present"] is True
    assert lp["hash_verified_live"] is True            # live sha256 == registry
    assert lp["status"] == "PROVEN"
    assert lp["real_sorries"] == 0
    assert b["color"] == fb._PROOF


def test_second_proven_theorem():
    b = fb.build_badge("receipt-transduction")
    assert b["badge_state"] == "THEOREM-BACKED"
    assert b["provenance_chain"]["lean_proof"]["real_sorries"] == 0


def test_conjecture_is_never_green():
    for fid in ("lambda-uniqueness", "khipu-bft-consensus"):
        b = fb.build_badge(fid)
        assert b["badge_state"] == "CONJECTURE-GATED", fid
        lp = b["provenance_chain"]["lean_proof"]
        assert lp["status"] == "OPEN", fid             # has a real sorry
        assert lp["real_sorries"] >= 1, fid
        assert b["color"] == fb._GRAY, fid


def test_tampered_proof_drops_to_conjecture_gated():
    # if a 'theorem'-kind feature's file no longer matches its recorded hash and is
    # absent/unproven, it must NOT stay green
    reg = {"features": [{
        "id": "x", "feature": "x", "kind": "theorem",
        "lean_file": "Lutar/Thesis/TH_V18_08_KhipuChecksumInvariant.lean",
        "lean_sha256": "deadbeef" * 8, "recorded_status": "PROVEN",
    }]}
    b = fb.build_badge("x", registry=reg)
    # file present + proven but hash mismatch ⇒ not THEOREM-BACKED
    assert b["badge_state"] == "CONJECTURE-GATED"
    assert b["provenance_chain"]["lean_proof"]["hash_verified_live"] is False


def test_svg_renders():
    svg = fb.render_svg(fb.build_badge("khipu-checksum-invariant"))
    assert svg.startswith("<svg") and "theorem-backed" in svg
    assert fb._PROOF in svg


def test_unknown_feature():
    assert fb.build_badge("nope").get("error") == "unknown_feature"
