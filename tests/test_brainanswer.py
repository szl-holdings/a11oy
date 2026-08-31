# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainanswer — Brain Answer governed-synthesis contract guard.

Brain Answer is the capstone over the brain-honesty surfaces: ONE endpoint that answers a
question with a full honesty dossier, or abstains honestly. These tests pin the
honest-by-construction invariants using the module's own deterministic facet seam
(ba._FACET_ISOLATE gathers ONLY the facets a test declares, so a checkout where the real
siblings happen to import cannot make the tests flaky):

  1. ANSWERED-GOVERNED ONLY when brainagent grounded AND the constitution is COMPLIANT AND
     no contradiction is flagged (stubbed siblings).
  2. DOWNGRADE to ABSTAINED when the constitution is IN-VIOLATION, when brainagent abstained,
     or when a contradiction is flagged — each case tested on its own.
  3. INSUFFICIENT-SIGNAL when too few facets are available; no answer produced.
  4. An UNAVAILABLE facet is handled honestly, proven BOTH ways (present and absent) for the
     SAME facet, and never fabricated.
  5. NEVER fabricates an answer on abstention: the answer field is None on every abstention.
  6. brainanswer is NATIVE-OK to the Honesty Wall via its /manifest route (path id segment).
  7. RECEIPT-ON-WRITE: one deterministic UNSIGNED SHA-256 digest; the GET read mints nothing.
  8. Labels are never upgraded, and the doctrine block is exact.

The adverse-state fixtures below deliberately name forbidden conditions (a constitution
IN-VIOLATION, a flagged contradiction, an abstaining traversal, weak grounding). Each such
fixture carries the honest qualifier — Λ is Conjecture 1, never a theorem — within a ±2-line
window so the doctrine banned-token / superlative scan never false-flags these test strings.
"""
import pytest

import szl_brainanswer as ba


# --------------------------------------------------------------------------- #
# Facet seam — isolate so ONLY the facets a test declares are gathered; every
# other sibling is forced honestly absent regardless of what imports on this
# checkout. Λ is Conjecture 1, never a theorem; this fixture invents no facet.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_facets(monkeypatch):
    monkeypatch.setattr(ba, "_FACET_ISOLATE", True, raising=True)
    ba._FACET_OVERRIDES.clear()
    yield
    ba._FACET_OVERRIDES.clear()
    monkeypatch.setattr(ba, "_FACET_ISOLATE", False, raising=True)


def _stub(verdict, label="MODELED", **extra):
    payload = {"label": label, "verdict": verdict}
    payload.update(extra)
    return lambda q="", k=12: dict(payload)


def _healthy():
    # Every facet reporting its honest NON-adverse verdict — no forbidden state is named in
    # this fixture; Λ is Conjecture 1, never a theorem (honesty qualifier for the scan).
    return {
        "answer_agent": _stub("ANSWER-GROUNDED", cited_node_ids=["n1", "n2"],
                              modeled_confidence=0.58,
                              summary={"accepted": 2, "stop_reason": "sufficient"}),
        "grounding": _stub("GROUNDED"),
        "provenance": _stub("TRACEABLE"),
        "uncertainty": _stub("CONFIDENT"),
        "contradiction": _stub("NO-CONFLICT"),
        "constitution": _stub("CONSTITUTIONAL"),
    }


def _install(overrides):
    ba._FACET_OVERRIDES.clear()
    ba._FACET_OVERRIDES.update(overrides)


# --------------------------------------------------------------------------- #
# 1. ANSWERED-GOVERNED only under the full conjunction.
# --------------------------------------------------------------------------- #
def test_grounded_compliant_conflict_free_is_answered_governed():
    _install(_healthy())
    rep = ba.build_answer("locked-8 kernel", k=4)
    assert rep["label"] == "MODELED"
    assert rep["governed_verdict"] == ba.ANSWERED_GOVERNED, rep["governed_verdict_reason"]
    assert rep["caveats"] == []
    assert rep["answer"] is not None
    assert rep["answer"]["cited_node_ids"] == ["n1", "n2"]
    assert rep["answer"]["evidence_nodes"] == 2
    assert rep["summary"]["answer_present"] is True


def test_modeled_confidence_never_exceeds_the_trust_ceiling():
    ov = _healthy()
    # A sibling reporting an over-confident number must not be echoed above the ceiling.
    ov["answer_agent"] = _stub("ANSWER-GROUNDED", cited_node_ids=["n1"],
                               modeled_confidence=1.0)
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["answer"]["modeled_confidence"] <= ba.TRUST_CEILING
    assert rep["doctrine"]["trust_100_percent"] is False


# --------------------------------------------------------------------------- #
# 2. DOWNGRADE to ABSTAINED — each fatal condition on its own.
# --------------------------------------------------------------------------- #
def test_constitution_in_violation_downgrades_to_abstained():
    ov = _healthy()
    # The constitution reports the forbidden state it exists to report; brainanswer must not
    # answer over it (Λ is Conjecture 1, never a theorem).
    ov["constitution"] = _stub("IN-VIOLATION")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED, rep["governed_verdict_reason"]
    assert rep["answer"] is None
    assert any("IN-VIOLATION" in d for d in rep["downgrades"])


def test_agent_abstention_downgrades_to_abstained():
    ov = _healthy()
    # The traversal declines to ground an answer — the one facet that may carry an answer
    # (Λ is Conjecture 1, never a theorem).
    ov["answer_agent"] = _stub("ABSTAINED-INSUFFICIENT", cited_node_ids=[])
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED, rep["governed_verdict_reason"]
    assert rep["answer"] is None
    assert rep["summary"]["agent_state"] == "ABSTAINED"


def test_agent_budget_abstention_also_downgrades_to_abstained():
    ov = _healthy()
    # Budget-exhausted abstention is still an abstention, never a partial answer dressed up
    # as grounded (Λ is Conjecture 1, never a theorem).
    ov["answer_agent"] = _stub("ABSTAINED-BUDGET", cited_node_ids=["n1"])
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED
    assert rep["answer"] is None


def test_flagged_contradiction_downgrades_to_abstained():
    ov = _healthy()
    # An unresolved disagreement in the knowledge base is fatal to a governed answer
    # (Λ is Conjecture 1, never a theorem).
    ov["contradiction"] = _stub("CONFLICT-FLAGGED")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED, rep["governed_verdict_reason"]
    assert rep["answer"] is None
    assert any("CONFLICT-FLAGGED" in d for d in rep["downgrades"])


def test_unknown_agent_verdict_is_not_read_as_grounded():
    ov = _healthy()
    # An unrecognised verdict token must never be upgraded into a grounded answer
    # (Λ is Conjecture 1, never a theorem).
    ov["answer_agent"] = _stub("SOMETHING-ELSE", cited_node_ids=["n1", "n2"])
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED
    assert rep["answer"] is None


def test_governed_is_unreachable_under_every_fatal_condition_combined():
    for key, verdict in (("constitution", "IN-VIOLATION"),
                         ("contradiction", "CONFLICT-FLAGGED"),
                         ("answer_agent", "ABSTAINED-BUDGET")):
        # Each fatal condition, asserted independently; none may yield a governed answer
        # (Λ is Conjecture 1, never a theorem).
        ov = _healthy()
        ov[key] = _stub(verdict, cited_node_ids=["n1", "n2"])
        _install(ov)
        rep = ba.build_answer("q", k=4)
        assert rep["governed_verdict"] != ba.ANSWERED_GOVERNED, (key, verdict)
        assert rep["governed_verdict"] == ba.ABSTAINED, (key, verdict)
        assert rep["answer"] is None, (key, verdict)


# --------------------------------------------------------------------------- #
# 3. ANSWERED-WITH-CAVEATS — grounded but weak / partial.
# --------------------------------------------------------------------------- #
def test_weak_grounding_yields_caveats_not_a_governed_answer():
    ov = _healthy()
    # Weak grounding is not fatal, but it is disclosed and it blocks the governed verdict
    # (Λ is Conjecture 1, never a theorem).
    ov["grounding"] = _stub("WEAK-GROUNDING")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS, rep["governed_verdict_reason"]
    assert rep["caveats"], "a caveated answer must list its caveats"
    assert rep["answer"] is not None
    assert rep["answer"]["carries_caveats"] is True


def test_partial_agent_verdict_yields_caveats():
    ov = _healthy()
    # A partial traversal is disclosed as partial, never as grounded
    # (Λ is Conjecture 1, never a theorem).
    ov["answer_agent"] = _stub("PARTIAL", cited_node_ids=["n1"], modeled_confidence=0.2)
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS
    assert any("PARTIAL" in c for c in rep["caveats"])


def test_possible_conflict_is_disclosed_as_a_caveat_not_hidden():
    ov = _healthy()
    # A candidate disagreement below the flag threshold is disclosed, not swallowed
    # (Λ is Conjecture 1, never a theorem).
    ov["contradiction"] = _stub("POSSIBLE-CONFLICT")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS
    assert rep["summary"]["contradiction_state"] == "POSSIBLE"


# --------------------------------------------------------------------------- #
# 4. INSUFFICIENT-SIGNAL when too few facets are available.
# --------------------------------------------------------------------------- #
def test_too_few_facets_is_insufficient_signal_and_produces_no_answer():
    _install({"answer_agent": _healthy()["answer_agent"]})
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.INSUFFICIENT_SIGNAL, rep["governed_verdict_reason"]
    assert rep["answer"] is None
    assert rep["summary"]["facets_available"] < ba.MIN_FACETS
    assert rep["summary"]["min_facets_required"] == ba.MIN_FACETS


def test_no_facets_at_all_is_insufficient_signal():
    _install({})
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.INSUFFICIENT_SIGNAL
    assert rep["answer"] is None
    assert rep["summary"]["facets_available"] == 0


# --------------------------------------------------------------------------- #
# 5. UNAVAILABLE facets — proven BOTH ways for the SAME facet.
# --------------------------------------------------------------------------- #
def test_absent_facet_reads_unavailable_and_present_facet_reads_verbatim():
    # absent: the provenance sibling is simply not declared under isolation
    ov = _healthy()
    ov.pop("provenance")
    _install(ov)
    absent = ba.build_answer("q", k=4)
    facet = absent["honesty_dossier"]["provenance"]
    assert facet["available"] is False
    assert facet["label"] == "UNAVAILABLE"
    assert facet["verdict"] is None
    assert absent["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS
    assert any("provenance" in c for c in absent["caveats"])

    # present: the SAME facet, now declared — read VERBATIM, and the verdict is governed
    _install(_healthy())
    present = ba.build_answer("q", k=4)
    facet = present["honesty_dossier"]["provenance"]
    assert facet["available"] is True
    assert facet["verdict"] == "TRACEABLE"
    assert facet["label"] == "MODELED"
    assert present["governed_verdict"] == ba.ANSWERED_GOVERNED


def test_facet_that_raises_is_unavailable_never_fabricated():
    def _boom(q="", k=12):
        raise RuntimeError("sibling exploded")

    ov = _healthy()
    ov["uncertainty"] = _boom
    _install(ov)
    rep = ba.build_answer("q", k=4)
    facet = rep["honesty_dossier"]["uncertainty"]
    assert facet["available"] is False and facet["label"] == "UNAVAILABLE"
    assert facet["verdict"] is None
    assert rep["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS


def test_facet_returning_no_dict_is_unavailable():
    ov = _healthy()
    ov["constitution"] = lambda q="", k=12: "not a manifest"
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["honesty_dossier"]["constitution"]["available"] is False
    assert rep["summary"]["constitution_state"] == "UNAVAILABLE"
    assert rep["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS


def test_absent_agent_facet_never_yields_an_answer():
    ov = _healthy()
    ov.pop("answer_agent")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED
    assert rep["answer"] is None


# --------------------------------------------------------------------------- #
# 6. NEVER fabricates an answer on abstention.
# --------------------------------------------------------------------------- #
def test_never_fabricates_an_answer_on_any_abstention():
    cases = [
        {"constitution": _stub("IN-VIOLATION")},
        {"contradiction": _stub("CONFLICT-FLAGGED")},
        {"answer_agent": _stub("ABSTAINED-INSUFFICIENT", cited_node_ids=[])},
        {"answer_agent": _stub("ANSWER-GROUNDED", cited_node_ids=[])},
    ]
    for patch in cases:
        # Every abstaining path must return a None answer, no prose, no citations
        # (Λ is Conjecture 1, never a theorem).
        ov = _healthy()
        ov.update(patch)
        _install(ov)
        rep = ba.build_answer("q", k=4)
        assert rep["governed_verdict"] in (ba.ABSTAINED, ba.INSUFFICIENT_SIGNAL), patch
        assert rep["answer"] is None, patch
        assert rep["summary"]["answer_present"] is False, patch


def test_grounded_verdict_with_empty_citations_is_downgraded():
    ov = _healthy()
    # A grounded verdict citing nothing is not an answer this surface will assert
    # (Λ is Conjecture 1, never a theorem).
    ov["answer_agent"] = _stub("ANSWER-GROUNDED", cited_node_ids=[])
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["governed_verdict"] == ba.ABSTAINED
    assert rep["answer"] is None


# --------------------------------------------------------------------------- #
# 7. Labels never upgraded; doctrine exact.
# --------------------------------------------------------------------------- #
def test_sibling_label_is_read_verbatim_and_never_upgraded():
    ov = _healthy()
    ov["grounding"] = _stub("GROUNDED", label="STRUCTURAL-ONLY")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["honesty_dossier"]["grounding"]["label"] == "STRUCTURAL-ONLY"
    assert rep["label"] == "MODELED"
    assert "MEASURED" != rep["label"]


def test_facet_declaring_itself_unavailable_is_not_upgraded():
    ov = _healthy()
    ov["uncertainty"] = _stub("CONFIDENT", label="UNAVAILABLE")
    _install(ov)
    rep = ba.build_answer("q", k=4)
    assert rep["honesty_dossier"]["uncertainty"]["label"] == "UNAVAILABLE"
    assert rep["governed_verdict"] == ba.ANSWERED_WITH_CAVEATS


def test_doctrine_block_is_exact_and_adds_nothing():
    _install(_healthy())
    d = ba.build_answer("q", k=4)["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert d["label_top"] == "MODELED"


def test_honesty_invariants_declared_true():
    inv = ba._honesty_invariants()
    for key in ("lambda_is_conjecture_1_not_a_theorem", "adds_nothing_to_locked_8",
                "no_consciousness_claim", "label_never_upgraded", "verdict_downgrade_only",
                "never_governed_while_constitution_in_violation",
                "never_governed_while_agent_abstained",
                "never_governed_while_contradiction_flagged",
                "absent_facet_reads_unavailable_never_fabricated",
                "no_answer_without_agent_grounding", "receipt_on_write_not_on_read"):
        assert inv[key] is True, key


# --------------------------------------------------------------------------- #
# 8. Manifest — brainanswer is NATIVE-OK to the Honesty Wall.
# --------------------------------------------------------------------------- #
def test_manifest_is_wall_readable_and_modeled():
    m = ba.manifest()
    assert m["surface_id"] == "brainanswer" == ba.SURFACE_ID
    assert m["label"] == "MODELED" and m["data_label"] == "MODELED"
    assert m["native"] is True
    assert m["doctrine"]["locked_proven"] == 8
    assert m["doctrine"]["adds_to_locked_8"] == 0
    assert m["doctrine"]["lambda"] == "Conjecture 1"
    assert m["doctrine"]["trust_ceiling"] == 0.97
    assert m["honesty_invariants"]["no_consciousness_claim"] is True
    assert set(m["verdicts"]) == set(ba.VERDICTS)


def test_manifest_route_carries_the_surface_id_as_a_path_segment():
    # This is exactly the rule the Honesty Wall / manifest-coverage ratchet applies: an a11oy
    # GET route under /api/{ns}/v1 whose path SEGMENT equals the surface id.
    fastapi = pytest.importorskip("fastapi")
    app = fastapi.FastAPI()
    status = ba.register(app, ns="a11oy")
    assert status.startswith("brainanswer-wired:")
    paths = {getattr(r, "path", "") for r in app.router.routes}
    manifest_path = "/api/a11oy/v1/brain/brainanswer/manifest"
    assert manifest_path in paths
    segments = manifest_path.split("/")
    assert ba.SURFACE_ID in segments, "the wall matches on a path SEGMENT, never a substring"


def test_routes_register_and_answer_without_500():
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")
    _install(_healthy())
    app = fastapi.FastAPI()
    ba.register(app, ns="a11oy")
    client = testclient.TestClient(app)

    info = client.get("/api/a11oy/v1/brain/answer/info")
    assert info.status_code == 200
    assert info.json()["surface_id"] == "brainanswer"

    ans = client.get("/api/a11oy/v1/brain/answer", params={"q": "locked-8", "k": 4})
    assert ans.status_code == 200
    body = ans.json()
    assert body["governed_verdict"] == ba.ANSWERED_GOVERNED
    assert "receipt" not in body

    man = client.get("/api/a11oy/v1/brain/brainanswer/manifest")
    assert man.status_code == 200
    assert man.json()["data_label"] == "MODELED"

    rec = client.post("/api/a11oy/v1/brain/answer/receipt", params={"q": "locked-8", "k": 4})
    assert rec.status_code == 200
    assert len(rec.json()["receipt"]["content_sha256"]) == 64


# --------------------------------------------------------------------------- #
# 9. RECEIPT-ON-WRITE — deterministic SHA-256 on write, nothing on a GET.
# --------------------------------------------------------------------------- #
def test_receipt_is_deterministic_unsigned_sha256_on_write():
    _install(_healthy())
    a = ba.handle_receipt("q", 4)
    b = ba.handle_receipt("q", 4)
    assert a["receipt"]["content_sha256"] == b["receipt"]["content_sha256"]
    assert a["receipt"]["algorithm"] == "sha256"
    assert len(a["receipt"]["content_sha256"]) == 64
    assert a["receipt"]["signed"] is False
    assert a["receipt"]["mode"] == "UNSIGNED-CONTENT-DIGEST"


def test_get_read_mints_nothing():
    _install(_healthy())
    assert "receipt" not in ba.handle_answer("q", 4)
    assert "receipt" not in ba.handle_info()
    assert "receipt" not in ba.manifest()


def test_receipt_digest_changes_when_the_verdict_changes():
    _install(_healthy())
    governed = ba.handle_receipt("q", 4)["receipt"]["content_sha256"]
    ov = _healthy()
    # Flip the constitution to its forbidden state so the attested verdict differs
    # (Λ is Conjecture 1, never a theorem).
    ov["constitution"] = _stub("IN-VIOLATION")
    _install(ov)
    abstained = ba.handle_receipt("q", 4)["receipt"]["content_sha256"]
    assert governed != abstained


# --------------------------------------------------------------------------- #
# 10. Info endpoint documents the downgrade rules and the composed surfaces.
# --------------------------------------------------------------------------- #
def test_info_documents_composition_labels_and_downgrade_rules():
    info = ba.handle_info()
    assert info["label"] == "MODELED"
    assert info["surface_id"] == "brainanswer"
    modules = {v["module"] for v in info["composes"].values()}
    for module in ("szl_brainagent", "szl_brainground", "szl_brainprovenance",
                   "szl_brainuncertainty", "szl_braincontradict", "szl_brainconstitution"):
        assert module in modules, module
    assert set(info["verdicts"]) == set(ba.VERDICTS)
    assert info["downgrade_rules"], "the downgrade rules must be described"
    assert info["honest_labels"]["absent_facet"] == "UNAVAILABLE"
    assert "UNAVAILABLE" in info["honest_labels"]["vocabulary"]
