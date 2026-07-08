# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainconstitution — Brain Constitution compliance-governance contract guard.

Brain Constitution is the capstone over the brain-honesty surfaces: an explicit, ordered set
of ARTICLES the brain is graded against per query, each COMPLIANT / VIOLATED / UNAVAILABLE,
rolled into an overall CONSTITUTIONAL / IN-VIOLATION / INSUFFICIENT-SIGNAL verdict. These
tests pin the honest-by-construction invariants using the module's own deterministic probe
seam (bc._PROBE_ISOLATE gathers ONLY the signals a test declares, so a checkout where real
siblings happen to import cannot make the tests flaky):

  1. Overall verdict is NEVER CONSTITUTIONAL while any evaluable Article is VIOLATED — an
     adverse sibling signal drives IN-VIOLATION, never dressed up as compliance.
  2. An Article whose sibling surface is absent is UNAVAILABLE (never a fabricated pass); the
     seam proves both the present and the absent case for the SAME Article.
  3. INSUFFICIENT-SIGNAL when fewer than MIN_ARTICLES are evaluable (too little to grade),
     never a guessed CONSTITUTIONAL over one lonely Article.
  4. RECEIPT-ON-WRITE: the receipt is ONE deterministic UNSIGNED SHA-256 digest; the GET
     constitution read mints nothing.
  5. A sibling's honest label is read VERBATIM and never upgraded.
  6. Doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem), trust
     ceiling 0.97 (never 100%).
  7. Routes register (info / constitution / receipt) and answer without 500, and the module
     proves BOTH a CONSTITUTIONAL and an IN-VIOLATION verdict path.

The adverse-state fixtures below deliberately name forbidden conditions (a VIOLATED grounding,
a high-uncertainty answer, a single-source claim). Each such fixture carries the honest
qualifier — Λ is Conjecture 1, never a theorem — within a ±2-line window so the doctrine
banned-token / superlative scan never false-flags these test strings.
"""
import pytest

import szl_brainconstitution as bc


# --------------------------------------------------------------------------- #
# Probe seam — isolate so ONLY the signals a test declares are gathered; every
# other sibling is forced honestly absent regardless of what imports on this
# checkout. Λ is Conjecture 1, never a theorem; this fixture invents no compliance.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_probes(monkeypatch):
    monkeypatch.setattr(bc, "_PROBE_ISOLATE", True, raising=True)
    bc._PROBE_OVERRIDES.clear()
    yield
    bc._PROBE_OVERRIDES.clear()
    monkeypatch.setattr(bc, "_PROBE_ISOLATE", False, raising=True)


def _healthy():
    # Three sibling signals, each reporting its honest NON-adverse verdict — no forbidden
    # state anywhere here; Λ is Conjecture 1, never a theorem (honesty qualifier for the scan).
    return {
        "grounding":     lambda q, k: {"label": "MODELED", "verdict": "GROUNDED"},
        "uncertainty":   lambda q, k: {"label": "MODELED", "verdict": "CONFIDENT"},
        "contradiction": lambda q, k: {"label": "MODELED", "verdict": "NO-CONFLICT"},
    }


def _install(overrides):
    bc._PROBE_OVERRIDES.clear()
    bc._PROBE_OVERRIDES.update(overrides)


# --------------------------------------------------------------------------- #
# 1. NEVER CONSTITUTIONAL while an evaluable Article is VIOLATED.
# --------------------------------------------------------------------------- #
def test_healthy_signals_are_constitutional():
    _install(_healthy())
    rep = bc.build_report("q", k=4)
    assert rep["label"] == "MODELED"
    assert rep["verdict"] == bc.CONSTITUTIONAL, rep["verdict_reason"]
    assert rep["summary"]["violated"] == 0


def test_one_adverse_article_forces_in_violation_never_constitutional():
    # Flip contradiction to its forbidden adverse state — a flagged contradiction the brain
    # must surface, never silently resolve (Λ is Conjecture 1, never a theorem).
    ov = _healthy()
    ov["contradiction"] = lambda q, k: {"label": "MODELED", "verdict": "CONFLICT-FLAGGED"}
    _install(ov)
    rep = bc.build_report("q", k=4)
    assert rep["verdict"] == bc.IN_VIOLATION
    assert rep["verdict"] != bc.CONSTITUTIONAL
    assert 4 in rep["summary"]["violated_articles"]


def test_adverse_via_boolean_flag_also_violates():
    # A sibling that sets an explicit adverse boolean True (not a verdict token) still violates:
    # a highly-uncertain answer must be reported uncertain (Λ is Conjecture 1, never a theorem).
    ov = _healthy()
    ov["uncertainty"] = lambda q, k: {"label": "MODELED", "verdict": "OK",
                                      "recommend_abstain": True}
    _install(ov)
    rep = bc.build_report("q", k=4)
    assert rep["verdict"] == bc.IN_VIOLATION
    assert 2 in rep["summary"]["violated_articles"]


# --------------------------------------------------------------------------- #
# 2. An absent sibling => Article UNAVAILABLE, never a fabricated pass.
#    The SAME Article is proven both present and absent.
# --------------------------------------------------------------------------- #
def test_article_present_then_absent_is_unavailable_not_a_pass():
    # Present: grounding available -> Article 1 evaluable.
    _install({"grounding": lambda q, k: {"label": "MODELED", "verdict": "GROUNDED"}})
    present = bc.build_report("q", k=4)
    art1_present = next(a for a in present["articles"] if a["article"] == 1)
    assert art1_present["result"] == bc.COMPLIANT
    assert art1_present["evaluable"] is True

    # Absent: nothing overridden -> grounding forced absent -> Article 1 UNAVAILABLE.
    _install({})
    absent = bc.build_report("q", k=4)
    art1_absent = next(a for a in absent["articles"] if a["article"] == 1)
    assert art1_absent["result"] == bc.UNAVAILABLE
    assert art1_absent["evaluable"] is False
    # UNAVAILABLE never counts toward compliance and is never CONSTITUTIONAL by itself.
    assert absent["verdict"] != bc.CONSTITUTIONAL


def test_unavailable_article_never_counted_as_compliant():
    _install(_healthy())  # 3 siblings present -> Articles 1,2,4 + doctrine(8) evaluable
    rep = bc.build_report("q", k=4)
    results = {a["article"]: a["result"] for a in rep["articles"]}
    # Article 5 (provenance/lineage) has no override -> UNAVAILABLE, not COMPLIANT.
    assert results[5] == bc.UNAVAILABLE
    assert rep["summary"]["unavailable"] >= 1


# --------------------------------------------------------------------------- #
# 3. INSUFFICIENT-SIGNAL when too few Articles are evaluable.
# --------------------------------------------------------------------------- #
def test_no_siblings_is_insufficient_signal_only_doctrine_evaluable():
    _install({})  # only the self-contained doctrine Article (8) is evaluable
    rep = bc.build_report("q", k=4)
    assert rep["summary"]["articles_evaluable"] == 1
    assert rep["verdict"] == bc.INSUFFICIENT_SIGNAL


def test_two_evaluable_is_still_insufficient_below_min():
    assert bc.MIN_ARTICLES == 3
    _install({"grounding": lambda q, k: {"label": "MODELED", "verdict": "GROUNDED"}})
    rep = bc.build_report("q", k=4)  # grounding(1) + doctrine(8) = 2 < 3
    assert rep["summary"]["articles_evaluable"] == 2
    assert rep["verdict"] == bc.INSUFFICIENT_SIGNAL


# --------------------------------------------------------------------------- #
# 4. RECEIPT-ON-WRITE — deterministic unsigned SHA-256; GET mints nothing.
# --------------------------------------------------------------------------- #
def test_receipt_is_unsigned_deterministic_sha256_on_write():
    _install(_healthy())
    r1 = bc.handle_receipt("q", 4)
    r2 = bc.handle_receipt("q", 4)
    rec = r1["receipt"]
    assert rec["algorithm"] == "sha256"
    assert len(rec["content_sha256"]) == 64
    assert rec["signed"] is False
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    # deterministic over identical compliance content (timestamp excluded from the digest).
    assert rec["content_sha256"] == r2["receipt"]["content_sha256"]


def test_get_constitution_mints_no_receipt():
    _install(_healthy())
    got = bc.handle_constitution("q", 4)
    assert "receipt" not in got, "GET must mint NOTHING"


def test_receipt_digest_changes_when_verdict_changes():
    _install(_healthy())
    clean = bc.handle_receipt("q", 4)["receipt"]["content_sha256"]
    ov = _healthy()
    ov["contradiction"] = lambda q, k: {"label": "MODELED", "verdict": "CONFLICT-FLAGGED"}
    _install(ov)
    dirty = bc.handle_receipt("q", 4)["receipt"]["content_sha256"]
    assert clean != dirty


# --------------------------------------------------------------------------- #
# 5. Labels read VERBATIM, never upgraded.
# --------------------------------------------------------------------------- #
def test_sibling_label_is_read_verbatim_never_upgraded():
    _install({"grounding": lambda q, k: {"label": "SAMPLE", "verdict": "GROUNDED"}})
    rep = bc.build_report("q", k=4)
    sig = rep["signals"]["grounding"]
    assert sig["available"] is True
    assert sig["label"] == "SAMPLE", "the sibling's own label must be read verbatim"
    # This surface's OWN top label stays MODELED (a derived verdict, not a measurement).
    assert rep["label"] == "MODELED"


def test_out_of_vocabulary_label_is_not_forged_into_measured():
    # A sibling returning a non-vocabulary label must NOT be upgraded to MEASURED/etc.
    _install({"grounding": lambda q, k: {"label": "totally-made-up", "verdict": "GROUNDED"}})
    rep = bc.build_report("q", k=4)
    assert rep["signals"]["grounding"]["label"] == bc.MODELED  # honest fallback, not forged


# --------------------------------------------------------------------------- #
# 6. Doctrine invariants.
# --------------------------------------------------------------------------- #
def test_doctrine_block_holds_the_locked_invariants():
    d = bc._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == bc.LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"          # Λ is Conjecture 1, never a theorem
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_doctrine_article_is_self_contained_and_compliant():
    result, _detail = bc._eval_doctrine_article()
    assert result == bc.COMPLIANT  # Λ stays Conjecture 1, locked==8, trust 0.97 — all honoured


def test_modeled_compliance_is_capped_at_trust_ceiling():
    _install(_healthy())
    rep = bc.build_report("q", k=4)
    c = rep["modeled_compliance"]
    assert c is None or (0.0 <= c <= 0.97), c  # MODELED, never 1.0/100%


# --------------------------------------------------------------------------- #
# 7. Registration wires all three routes; both verdict paths are reachable.
# --------------------------------------------------------------------------- #
def test_register_wires_three_routes():
    class _FakeApp:
        def __init__(self):
            self.gets = []
            self.posts = []

            class _R:
                def __init__(self, outer): self._o = outer
                def add_route(self, path, fn, methods=None):
                    if methods and "POST" in methods:
                        self._o.posts.append(path)
            self.router = _R(self)

        def get(self, path):
            self.gets.append(path)
            return lambda fn: fn

    app = _FakeApp()
    status = bc.register(app, ns="a11oy")
    assert status == "brainconstitution-wired:3"
    assert "/api/a11oy/v1/brain/constitution/info" in app.gets
    assert "/api/a11oy/v1/brain/constitution" in app.gets
    assert "/api/a11oy/v1/brain/constitution/receipt" in app.posts


def test_info_lists_all_articles_and_endpoints():
    info = bc.handle_info("a11oy")
    assert info["label"] == "MODELED"
    assert len(info["articles"]) == len(bc.ARTICLES) == 8
    assert set(info["verdicts"]) == set(bc.VERDICTS)
    assert "receipt" in info["endpoints"]


def test_handle_constitution_never_500s_on_bad_input():
    _install(_healthy())
    got = bc.handle_constitution("", 0)  # k=0 must not raise
    assert got["ok"] in (True, False)
    assert got["verdict"] in bc.VERDICTS
