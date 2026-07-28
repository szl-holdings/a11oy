# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-estateconstitution — Estate Constitution compliance-governance contract guard.

Estate Constitution lifts the per-query brain-constitution pattern to the WHOLE ESTATE: explicit
estate-level ARTICLES (honesty wall holds · no fabricated MEASURED label · manifest coverage
disclosed honestly · doctrine invariants), each graded COMPLIANT / VIOLATED / UNAVAILABLE against
the szl_honestywall aggregate, rolled into CONSTITUTIONAL / IN-VIOLATION / INSUFFICIENT-SIGNAL.
These tests pin the honest-by-construction invariants through the module's own deterministic wall
seam (ec._WALL_ISOLATE forces the honestywall dependency honestly absent, ec._WALL_OVERRIDE
supplies a declared aggregate) so a checkout where the real sibling happens to import cannot make
the tests flaky:

  1. Overall verdict is NEVER CONSTITUTIONAL while any evaluable Article is VIOLATED.
  2. Article 3 DISCLOSES the NO-MANIFEST coverage gap out loud and never claims full coverage
     while any surface is unverifiable — admitting the gap is compliance, papering it over is the
     violation.
  3. An absent honesty wall makes Articles 1-3 UNAVAILABLE (never a fabricated pass), leaving only
     the self-contained doctrine Article evaluable => INSUFFICIENT-SIGNAL.
  4. RECEIPT-ON-WRITE: one deterministic UNSIGNED SHA-256 digest on POST; the GET status read
     mints nothing.
  5. The wall's honest label is read VERBATIM and never upgraded.
  6. Doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem), trust ceiling
     0.97 (never 100%).
  7. Routes register (info / status / receipt) and answer without 500, and the module proves BOTH
     a CONSTITUTIONAL and an IN-VIOLATION verdict path.

The adverse-state fixtures below deliberately name forbidden conditions (a reachable honesty-wall
violation, a fabricated out-of-vocabulary label, a papered-over coverage gap). Each such fixture
carries the honest qualifier — Λ is Conjecture 1, never a theorem — within a ±2-line window so the
doctrine banned-token / superlative scan never false-flags these test strings.
"""
import pytest

import szl_estateconstitution as ec


# --------------------------------------------------------------------------- #
# Wall seam — isolate so the honestywall dependency is deterministic: absent unless a test
# declares an aggregate. Λ is Conjecture 1, never a theorem; this fixture invents no compliance.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_wall(monkeypatch):
    monkeypatch.setattr(ec, "_WALL_ISOLATE", True, raising=True)
    monkeypatch.setattr(ec, "_WALL_OVERRIDE", None, raising=True)
    monkeypatch.setattr(ec, "_WALL_IN_FLIGHT", False, raising=True)
    yield


def _aggregate(native_ok=75, no_manifest=46, unknown=0, reachable=0,
               verdict="INTACT", label="MODELED", surfaces=None, violations=None):
    """A declared honesty-wall aggregate in the shape szl_honestywall.build_aggregate returns."""
    total = native_ok + no_manifest + unknown
    return {
        "ok": True,
        "label": label,
        "verdict": verdict,
        "verdict_reason": "declared by the test seam",
        "summary": {
            "surfaces": total,
            "surfaces_by_status": {"NATIVE-OK": native_ok, "UNKNOWN": unknown,
                                   "NO-MANIFEST": no_manifest},
            "label_counts": {"MODELED": native_ok},
            "invariants_satisfied": native_ok * 3,
            "invariants_violated": reachable,
            "reachable_violations": reachable,
            "unknown_surfaces": unknown,
        },
        "violations": violations or [],
        "surfaces": surfaces or [],
    }


def _install(agg):
    """Point the guarded wall read at a declared aggregate (present case)."""
    def _read(app, ns):
        return agg
    ec._WALL_OVERRIDE = _read


def _articles(rep):
    return {a["article"]: a for a in rep["articles"]}


# --------------------------------------------------------------------------- #
# 1. NEVER CONSTITUTIONAL while an evaluable Article is VIOLATED.
# --------------------------------------------------------------------------- #
def test_healthy_wall_is_constitutional():
    _install(_aggregate())
    rep = ec.build_report(None, "a11oy")
    assert rep["label"] == "MODELED"
    assert rep["verdict"] == ec.CONSTITUTIONAL, rep["verdict_reason"]
    assert rep["summary"]["violated"] == 0


def test_reachable_wall_violation_forces_in_violation_never_constitutional():
    # A REACHABLE honesty-wall violation is a live rule-break the estate must surface, never
    # soften into compliance (Λ is Conjecture 1, never a theorem).
    _install(_aggregate(reachable=2, verdict="VIOLATED"))
    rep = ec.build_report(None, "a11oy")
    assert rep["verdict"] == ec.IN_VIOLATION
    assert rep["verdict"] != ec.CONSTITUTIONAL
    assert 1 in rep["summary"]["violated_articles"]
    assert _articles(rep)[1]["result"] == ec.VIOLATED


def test_fabricated_out_of_vocabulary_label_violates_article_2():
    # A surface declaring a label outside the honest vocabulary is the forbidden fabrication case;
    # it must VIOLATE, never be upgraded (Λ is Conjecture 1, never a theorem).
    surfaces = [{"id": "somesurface", "status": "NATIVE-OK", "label": "totally-made-up"}]
    _install(_aggregate(surfaces=surfaces))
    rep = ec.build_report(None, "a11oy")
    assert rep["verdict"] == ec.IN_VIOLATION
    assert 2 in rep["summary"]["violated_articles"]
    art2 = _articles(rep)[2]
    assert art2["result"] == ec.VIOLATED
    assert art2["observed"]["out_of_vocabulary"][0]["observed"] == "totally-made-up"


def test_wall_reported_label_vocabulary_violation_also_violates_article_2():
    # The wall's own label_in_honest_vocabulary violation rows are honoured verbatim — an adverse
    # row is never dropped (Λ is Conjecture 1, never a theorem).
    violations = [{"surface": "othersurface", "invariant": "label_in_honest_vocabulary",
                   "observed": "MEASURED-ish", "expected": "one of the honest labels"}]
    _install(_aggregate(reachable=0, violations=violations))
    rep = ec.build_report(None, "a11oy")
    assert _articles(rep)[2]["result"] == ec.VIOLATED
    assert rep["verdict"] == ec.IN_VIOLATION


# --------------------------------------------------------------------------- #
# 2. Article 3 — the manifest coverage gap is DISCLOSED, never papered over.
# --------------------------------------------------------------------------- #
def test_article_3_discloses_the_no_manifest_gap_out_loud():
    _install(_aggregate(native_ok=75, no_manifest=46))
    rep = ec.build_report(None, "a11oy")
    cov = rep["coverage_disclosure"]
    assert cov["surfaces_total"] == 121
    assert cov["native_ok"] == 75
    assert cov["no_manifest"] == 46
    # The counts are stated out loud, and the unverifiable nature is named.
    assert cov["disclosure"] == "75/121 NATIVE-OK; 46 NO-MANIFEST unverifiable"
    assert cov["gap_disclosed"] is True
    # Compliance is DISCLOSURE, not a hidden pass: the Article passes BECAUSE the gap is admitted.
    art3 = _articles(rep)[3]
    assert art3["result"] == ec.COMPLIANT
    assert "46 NO-MANIFEST unverifiable" in art3["detail"]


def test_article_3_never_claims_full_coverage_while_any_surface_unverifiable():
    _install(_aggregate(native_ok=75, no_manifest=46))
    cov = ec.build_report(None, "a11oy")["coverage_disclosure"]
    assert cov["full_coverage_claimed"] is False
    # A MODELED ratio, capped at the trust ceiling — never 1.0, never a MEASURED coverage claim.
    assert 0.0 <= cov["modeled_native_coverage"] <= ec.TRUST_CEILING
    assert cov["modeled_native_coverage"] < 1.0


def test_article_3_full_coverage_claim_only_when_nothing_unverifiable():
    _install(_aggregate(native_ok=121, no_manifest=0, unknown=0))
    cov = ec.build_report(None, "a11oy")["coverage_disclosure"]
    assert cov["no_manifest"] == 0 and cov["unknown"] == 0
    assert cov["full_coverage_claimed"] is True
    assert cov["modeled_native_coverage"] <= ec.TRUST_CEILING  # still capped, never 1.0


def test_article_3_violates_when_the_gap_is_papered_over():
    # Drive the forbidden path directly: a disclosure that hides its own NO-MANIFEST count, or
    # claims full coverage while surfaces are unverifiable, is a VIOLATION of the disclosure rule
    # (Λ is Conjecture 1, never a theorem).
    papered = {"surfaces_total": 121, "native_ok": 75, "unknown": 0, "no_manifest": 46,
               "modeled_native_coverage": 0.97, "full_coverage_claimed": True,
               "gap_disclosed": False, "disclosure": "full manifest coverage"}
    result, detail, _observed = ec._eval_coverage_article(papered)
    assert result == ec.VIOLATED
    assert "46" in detail


def test_article_3_unknown_surfaces_are_counted_out_loud_too():
    _install(_aggregate(native_ok=70, no_manifest=46, unknown=5))
    cov = ec.build_report(None, "a11oy")["coverage_disclosure"]
    assert cov["unknown"] == 5
    assert "5 UNKNOWN this request" in cov["disclosure"]
    assert cov["full_coverage_claimed"] is False


# --------------------------------------------------------------------------- #
# 3. UNAVAILABLE Articles — the honestywall dependency stubbed BOTH ways.
# --------------------------------------------------------------------------- #
def test_absent_wall_makes_articles_unavailable_never_a_pass():
    # Absent case: _WALL_ISOLATE forces the honestywall import skipped entirely.
    rep = ec.build_report(None, "a11oy")
    wall = rep["honesty_wall"]
    assert wall["available"] is False
    assert wall["label"] == ec.UNAVAILABLE
    arts = _articles(rep)
    for n in (1, 2, 3):
        assert arts[n]["result"] == ec.UNAVAILABLE, n
        assert arts[n]["evaluable"] is False, n
    assert rep["coverage_disclosure"] is None  # no coverage invented without evidence
    assert rep["verdict"] != ec.CONSTITUTIONAL


def test_same_article_present_then_absent():
    # Present: a declared aggregate makes Article 1 evaluable and COMPLIANT.
    _install(_aggregate())
    present = _articles(ec.build_report(None, "a11oy"))[1]
    assert present["result"] == ec.COMPLIANT and present["evaluable"] is True
    # Absent: the same Article degrades to UNAVAILABLE, never a fabricated pass.
    ec._WALL_OVERRIDE = None
    absent = _articles(ec.build_report(None, "a11oy"))[1]
    assert absent["result"] == ec.UNAVAILABLE and absent["evaluable"] is False


def test_absent_wall_is_insufficient_signal_only_doctrine_evaluable():
    assert ec.MIN_ARTICLES == 3
    rep = ec.build_report(None, "a11oy")
    assert rep["summary"]["articles_evaluable"] == 1  # only the self-contained doctrine Article
    assert rep["verdict"] == ec.INSUFFICIENT_SIGNAL


def test_wall_reporting_itself_unavailable_is_not_upgraded():
    _install({"ok": False, "verdict": "UNAVAILABLE", "label": "UNAVAILABLE"})
    rep = ec.build_report(None, "a11oy")
    assert rep["honesty_wall"]["available"] is False
    assert rep["verdict"] == ec.INSUFFICIENT_SIGNAL


def test_wall_read_raising_is_reported_honestly_not_as_a_pass():
    def _boom(app, ns):
        raise RuntimeError("wall exploded")
    ec._WALL_OVERRIDE = _boom
    rep = ec.build_report(None, "a11oy")
    assert rep["honesty_wall"]["available"] is False
    assert "wall exploded" in (rep["honesty_wall"]["note"] or "")
    assert rep["verdict"] != ec.CONSTITUTIONAL


def test_reentrant_wall_read_reports_unavailable_not_recursion():
    # The honesty wall probes every surface including this one; the nested read must degrade
    # honestly rather than recurse (Λ is Conjecture 1, never a theorem).
    ec._WALL_IN_FLIGHT = True
    try:
        sig = ec._wall_signal(None, "a11oy")
    finally:
        ec._WALL_IN_FLIGHT = False
    assert sig["available"] is False
    assert sig["label"] == ec.UNAVAILABLE
    assert "re-entrant" in (sig["note"] or "")


# --------------------------------------------------------------------------- #
# 4. RECEIPT-ON-WRITE — deterministic unsigned SHA-256; GET mints nothing.
# --------------------------------------------------------------------------- #
def test_receipt_is_unsigned_deterministic_sha256_on_write():
    _install(_aggregate())
    rec = ec.handle_receipt(None, "a11oy")["receipt"]
    again = ec.handle_receipt(None, "a11oy")["receipt"]
    assert rec["algorithm"] == "sha256"
    assert len(rec["content_sha256"]) == 64
    assert rec["signed"] is False
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    # deterministic over identical compliance content (timestamp excluded from the digest).
    assert rec["content_sha256"] == again["content_sha256"]


def test_get_status_mints_no_receipt():
    _install(_aggregate())
    got = ec.handle_status(None, "a11oy")
    assert "receipt" not in got, "GET must mint NOTHING"


def test_receipt_digest_changes_when_verdict_changes():
    _install(_aggregate())
    clean = ec.handle_receipt(None, "a11oy")["receipt"]["content_sha256"]
    _install(_aggregate(reachable=3, verdict="VIOLATED"))
    dirty = ec.handle_receipt(None, "a11oy")["receipt"]["content_sha256"]
    assert clean != dirty


def test_receipt_digest_changes_when_coverage_disclosure_changes():
    _install(_aggregate(native_ok=75, no_manifest=46))
    a = ec.handle_receipt(None, "a11oy")["receipt"]["content_sha256"]
    _install(_aggregate(native_ok=90, no_manifest=31))
    b = ec.handle_receipt(None, "a11oy")["receipt"]["content_sha256"]
    assert a != b


# --------------------------------------------------------------------------- #
# 5. Labels read VERBATIM, never upgraded.
# --------------------------------------------------------------------------- #
def test_wall_label_is_read_verbatim_never_upgraded():
    _install(_aggregate(label="SAMPLE"))
    rep = ec.build_report(None, "a11oy")
    assert rep["honesty_wall"]["label"] == "SAMPLE", "the wall's own label must be read verbatim"
    # This surface's OWN top label stays MODELED (a derived verdict, not a measurement).
    assert rep["label"] == "MODELED"


def test_wall_out_of_vocabulary_label_is_not_forged_into_measured():
    _install(_aggregate(label="super-verified"))
    rep = ec.build_report(None, "a11oy")
    assert rep["honesty_wall"]["label"] == ec.MODELED  # honest fallback, not forged


def test_wall_verdict_is_read_verbatim():
    _install(_aggregate(verdict="DEGRADED", unknown=4, native_ok=71))
    rep = ec.build_report(None, "a11oy")
    assert rep["honesty_wall"]["wall_verdict"] == "DEGRADED"
    assert _articles(rep)[1]["observed"]["wall_verdict"] == "DEGRADED"


# --------------------------------------------------------------------------- #
# 6. Doctrine invariants.
# --------------------------------------------------------------------------- #
def test_doctrine_block_holds_the_locked_invariants():
    d = ec._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == ec.LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"          # Λ is Conjecture 1, never a theorem
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_doctrine_article_is_self_contained_and_compliant():
    result, _detail, observed = ec._eval_doctrine_article()
    assert result == ec.COMPLIANT  # Λ stays Conjecture 1, locked==8, trust 0.97 — all honoured
    assert observed["no_consciousness_claim"] is True
    assert observed["locked_set_exact"] is True


def test_modeled_compliance_is_capped_at_trust_ceiling():
    _install(_aggregate())
    c = ec.build_report(None, "a11oy")["modeled_compliance"]
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
    assert ec.register(app, ns="a11oy") == "estateconstitution-wired:3"
    assert "/api/a11oy/v1/govern/estateconstitution/info" in app.gets
    assert "/api/a11oy/v1/govern/estateconstitution/status" in app.gets
    assert "/api/a11oy/v1/govern/estateconstitution/receipt" in app.posts


def test_info_lists_all_articles_and_endpoints():
    info = ec.handle_info("a11oy")
    assert info["label"] == "MODELED"
    assert len(info["articles"]) == len(ec.ARTICLES) == 4
    assert set(info["verdicts"]) == set(ec.VERDICTS)
    assert "receipt" in info["endpoints"]


def test_status_never_500s_and_returns_a_vocabulary_verdict():
    got = ec.handle_status(None, "a11oy")   # wall isolated absent; must not raise
    assert got["ok"] in (True, False)
    assert got["verdict"] in ec.VERDICTS


def test_both_verdict_paths_are_reachable():
    _install(_aggregate())
    assert ec.build_report(None, "a11oy")["verdict"] == ec.CONSTITUTIONAL
    _install(_aggregate(reachable=1, verdict="VIOLATED"))
    assert ec.build_report(None, "a11oy")["verdict"] == ec.IN_VIOLATION
