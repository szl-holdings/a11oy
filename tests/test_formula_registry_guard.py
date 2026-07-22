# SPDX-License-Identifier: Apache-2.0
"""Proof-carrying formula registry guard tests.

Proves a11oy_formula_registry_guard discriminates a corpus-BACKED formula from an
overclaim (a non-experimental formula whose claimed Lean theorem is absent from the
canonical corpus), and that the LIVE served registry (_INDEX) carries no overclaims
against the bundled corpus. Λ-uniqueness stays Conjecture 1 (never a theorem).

Stdlib + pytest only: importing a11oy_formula_endpoints does not require FastAPI
(the framework import is lazy inside register()), and the guard is pure stdlib.
"""
from __future__ import annotations

import re
from pathlib import Path

import a11oy_formula_registry_guard as guard
import formula_claim_validator as claim_validator
import szl_formula_registry as formula_registry
from a11oy_formula_endpoints import _INDEX


ROOT = Path(__file__).resolve().parents[1]


def _corpus(theorem_names=(), lean_files=(), thesis=False):
    return {
        "theorem_names": set(theorem_names),
        "lean_files": set(lean_files),
        "thesis_docs": ["thesis_v22.pdf"] if thesis else [],
        "thesis_available": thesis,
        "roots": ["<synthetic>"],
    }


def test_backed_formula_is_verified():
    r = guard.verify_formula(
        {"name": "demo", "citation": "thesis", "lean_theorem": "Demo.lean::real_thm"},
        _corpus(theorem_names={"real_thm"}),
    )
    assert r["status"] == "verified"
    assert r["lean_theorem_exists"] is True


def test_unbacked_overclaim_is_caught():
    # The guard's entire reason to exist: a non-experimental formula claiming a
    # Lean theorem that does NOT exist in the corpus is flagged, never passed.
    r = guard.verify_formula(
        {"name": "ghost", "citation": "external only", "lean_theorem": "Ghost.lean::nope"},
        _corpus(theorem_names={"something_else"}),
    )
    assert r["status"] == "unbacked"
    assert r["lean_theorem_exists"] is False
    assert r["in_corpus"] is False


def test_experimental_is_reported_never_unbacked():
    # An honestly-declared experimental / proposed obligation is allowed (reported),
    # never dressed up as proven and never counted as an overclaim.
    r = guard.verify_formula(
        {"name": "wip", "tier": "experimental",
         "citation": "arXiv:...", "lean_theorem": "Wip.lean::open_obligation"},
        _corpus(),
    )
    assert r["status"] == "experimental"


def test_registry_report_shape_and_lambda_conjecture():
    report = guard.registry_report(_INDEX)
    assert report["count"] == len(_INDEX)
    assert set(report["counts"]) == {"verified", "unbacked", "experimental"}
    assert report["lambda_status"] == "Conjecture 1 (never a theorem)"


def test_live_registry_has_no_overclaims():
    # Against the bundled canonical corpus (corpus/ + proofs/), every non-experimental
    # served formula must be backed by a REAL Lean theorem. If this fails, a11oy is
    # overclaiming a machine-checked proof it does not have — fix the citation or mark
    # the formula honestly experimental.
    report = guard.registry_report(_INDEX)
    assert report["unbacked"] == [], f"unbacked overclaims: {report['unbacked']}"
    assert report["honest"] is True


def test_guard_catches_an_injected_overclaim_into_the_live_index():
    poisoned = list(_INDEX) + [
        {"name": "phantom", "citation": "none",
         "lean_theorem": "Phantom.lean::this_is_not_a_real_theorem"}
    ]
    report = guard.registry_report(poisoned)
    assert "phantom" in report["unbacked"]
    assert report["honest"] is False


def test_active_formula_claims_and_runtime_projections_match_canonical_registry():
    assert "pages/console.html" in claim_validator.ACTIVE_CLAIM_PATHS
    assert claim_validator.claim_errors() == []
    assert claim_validator.projection_errors() == []


def test_runtime_image_copies_registry_and_every_pinned_evidence_asset():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert (
        "COPY formula_registry/formula-registry.v1.json "
        "./formula_registry/formula-registry.v1.json"
    ) in dockerfile
    for source_path in formula_registry.EXPECTED_SOURCE_PATHS:
        assert source_path in dockerfile, f"runtime image omits pinned evidence: {source_path}"


def test_console_and_proof_surfaces_keep_experimental_formulas_outside_locked_pack():
    console = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")
    proof = (ROOT / "web" / "proof.html").read_text(encoding="utf-8")

    assert "locked-proven = 5" in console
    assert "F4/F7/F22 experimental" in console
    assert "F1,F4,F7,F11,F12,F18,F19,F22" not in console
    assert "locked-8" not in console.lower()
    for formula_id in ("F4", "F7", "F22"):
        assert re.search(
            rf"{formula_id}:\{{.*?mat:'experimental'",
            console,
        )

    for formula_id in ("f4", "f7", "f22"):
        assert re.search(
            rf'{formula_id}:\s*\{{.*?status:"experimental"',
            proof,
            re.S,
        )
    assert "EXPERIMENTAL · NOT LOCKED" in proof


def test_claim_guard_rejects_old_locked_and_bulk_proof_overclaims(tmp_path):
    bad = tmp_path / "claim.md"
    bad.write_text("Exactly 8 locked-proven formulas.\nWe have 200 proven formulas.\n",
                   encoding="utf-8")
    errors = claim_validator.claim_errors(("claim.md",), root=tmp_path)
    assert len(errors) == 2


def test_claim_guard_allows_honest_denials_and_experimental_language(tmp_path):
    honest = tmp_path / "claim.md"
    honest.write_text(
        "This evidence does not establish 200 proven formulas.\n"
        "F4, F7, and F22 are experimental and are not locked.\n",
        encoding="utf-8",
    )
    assert claim_validator.claim_errors(("claim.md",), root=tmp_path) == []
