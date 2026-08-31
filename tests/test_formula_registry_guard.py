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

import a11oy_formula_registry_guard as guard
from a11oy_formula_endpoints import _INDEX


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
