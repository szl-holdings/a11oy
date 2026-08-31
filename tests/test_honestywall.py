"""feat/frontier-honestywall — Honesty Wall contract guard.

The Honesty Wall aggregates the estate's OWN honesty invariants across every
registered frontier surface into a single verifiable verdict. These tests pin the
honest-by-construction invariants that make it trustworthy — no mocks of the honesty
logic itself, only controlled surface inputs where a real violation cannot be forced:

  1. Routes (GET status/info, POST aggregate) are registered and answer 200 (never
     500), BEFORE the SPA / Node-proxy catch-alls.
  2. RECEIPT-ON-WRITE-NOT-ON-READ: GET status mints NOTHING; POST aggregate emits ONE
     UNSIGNED SHA-256 content-digest receipt (signed is False).
  3. NEVER INTACT if anything is violated: when a surface's manifest declares a
     violated invariant, the verdict is VIOLATED (not INTACT/DEGRADED).
  4. Unreachable manifest -> UNKNOWN (degrades to DEGRADED, never a fabricated pass).
  5. NEVER upgrades a label: a surface's declared honest label is read VERBATIM.
  6. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1, trust 0.97 (never 100%).
  7. The honest vocabulary recognises DECLARED (asserted, not measured, never upgraded),
     so an honestly-labelled surface is SATISFIED instead of falsely flagged.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import pytest

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402
import szl_frontier_index as fi  # noqa: E402
import szl_honestywall as hw  # noqa: E402

STATUS = "/api/a11oy/v1/govern/honestywall/status"
INFO = "/api/a11oy/v1/govern/honestywall/info"
AGG = "/api/a11oy/v1/govern/honestywall/aggregate"
VERDICTS = {hw.INTACT, hw.VERDICT_DEGRADED, hw.VERDICT_VIOLATED}


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


# --------------------------------------------------------------------------- #
# 1. registration + ordering
# --------------------------------------------------------------------------- #
def test_routes_registered_before_catchalls():
    for path in (STATUS, INFO, AGG):
        assert _route_index(path) is not None, f"{path} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    for path in (STATUS, INFO, AGG):
        idx = _route_index(path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


# --------------------------------------------------------------------------- #
# 2. receipt-on-write-not-on-read
# --------------------------------------------------------------------------- #
def test_get_status_answers_and_mints_nothing():
    with TestClient(serve.app) as c:
        r = c.get(STATUS)
    assert r.status_code == 200, f"{STATUS} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert j["verdict"] in VERDICTS
    assert "receipt" not in j, "GET status is a PURE READ — must mint NO receipt"


def test_post_aggregate_mints_unsigned_sha256_receipt():
    with TestClient(serve.app) as c:
        r = c.post(AGG)
    assert r.status_code == 200, f"{AGG} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert j["verdict"] in VERDICTS
    rec = j["receipt"]
    assert rec["algorithm"] == "sha256"
    assert rec["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(rec["content_sha256"], str) and len(rec["content_sha256"]) == 64
    # digest is deterministic over the integrity content (excludes the volatile clock).
    assert rec["content_sha256"] == hw._content_receipt(j)["content_sha256"]


def test_get_info_is_static_pure_read():
    with TestClient(serve.app) as c:
        r = c.get(INFO)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and "receipt" not in j
    assert set(j["verdicts"]) == VERDICTS


# --------------------------------------------------------------------------- #
# 3. NEVER INTACT if anything is violated (controlled surface input)
# --------------------------------------------------------------------------- #
def test_verdict_violated_never_intact_when_manifest_violates(monkeypatch):
    """A surface manifest that inflates the locked-proof count violates an invariant;
    the wall MUST report VIOLATED — never INTACT, never DEGRADED."""
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "fake", "title": "fake", "cat": "governance"}])
    bad = {"label": "MODELED", "doctrine": {"locked_proven": 9, "lambda": "Conjecture 1",
                                            "trust_ceiling": 0.97, "trust_100_percent": False}}
    monkeypatch.setattr(hw, "_probe_surface",
                        lambda app, sid, gp, ns, timeout=3.0: (bad, "fake/x", hw.NATIVE_OK))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["verdict"] == hw.VERDICT_VIOLATED
    assert agg["summary"]["reachable_violations"] >= 1
    assert agg["verdict"] != hw.INTACT
    invs = {v["invariant"] for v in agg["violations"]}
    assert "locked_count_eight" in invs


def test_declared_false_invariant_is_a_violation(monkeypatch):
    """A surface that declares one of its OWN honesty_invariants False is VIOLATED verbatim."""
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "fake", "title": "fake", "cat": "governance"}])
    bad = {"label": "MODELED", "honesty_invariants": {"writer_ne_judge": False}}
    monkeypatch.setattr(hw, "_probe_surface",
                        lambda app, sid, gp, ns, timeout=3.0: (bad, "fake/x", hw.NATIVE_OK))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["verdict"] == hw.VERDICT_VIOLATED


# --------------------------------------------------------------------------- #
# 4. unreachable manifest -> UNKNOWN -> DEGRADED (never fabricated pass)
# --------------------------------------------------------------------------- #
def test_unreachable_manifest_is_unknown_and_degrades(monkeypatch):
    monkeypatch.setattr(hw, "_surface_registry",
                        lambda: [{"id": "fake", "title": "fake", "cat": "governance"}])
    monkeypatch.setattr(hw, "_probe_surface",
                        lambda app, sid, gp, ns, timeout=3.0: (None, "fake/x", hw.UNKNOWN))
    agg = hw._build_aggregate(None, "a11oy")
    assert agg["summary"]["unknown_surfaces"] == 1
    assert agg["summary"]["reachable_violations"] == 0
    assert agg["verdict"] == hw.VERDICT_DEGRADED, "UNKNOWN must degrade, never pass as INTACT"


# --------------------------------------------------------------------------- #
# 5. never upgrades a label (verbatim)
# --------------------------------------------------------------------------- #
def test_label_read_verbatim_never_upgraded():
    """A surface declaring ROADMAP must NOT be upgraded to MEASURED/PROVEN/etc."""
    label_tok, _prov, _checks = hw._eval_payload({"label": "ROADMAP"})
    assert label_tok == "ROADMAP", f"label upgraded to {label_tok} (must stay verbatim)"
    # a genuinely low label stays low.
    tok2, _, _ = hw._eval_payload({"data_label": "STRUCTURAL-ONLY"})
    assert tok2 == "STRUCTURAL-ONLY"


def test_bogus_marketing_label_is_a_violation():
    """A label that maps to NO honest-vocabulary token is a violation (never invented)."""
    label_tok, _prov, checks = hw._eval_payload({"label": "BOGUS-UNRECOGNIZED-LABEL"})
    assert label_tok is None
    vocab_check = [c for c in checks if c["invariant"] == "label_in_honest_vocabulary"]
    assert vocab_check and vocab_check[0]["status"] == hw.VIOLATED


# --------------------------------------------------------------------------- #
# 6. doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    with TestClient(serve.app) as c:
        j = c.post(AGG).json()
    d = j["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_status_in_real_estate_is_consistent():
    """Against the REAL booted estate: verdict is consistent with observed evidence and
    every per-surface label is in the honest vocabulary (never upgraded)."""
    with TestClient(serve.app) as c:
        j = c.post(AGG).json()
    sm = j["summary"]
    if sm["reachable_violations"] >= 1:
        assert j["verdict"] == hw.VERDICT_VIOLATED
    elif sm["unknown_surfaces"] > 0:
        assert j["verdict"] == hw.VERDICT_DEGRADED
    else:
        assert j["verdict"] == hw.INTACT
    vocab = set(hw.HONEST_LABELS)
    for e in j["surfaces"]:
        if e.get("label") is not None:
            assert e["label"] in vocab, f"{e['id']}: non-vocab label {e['label']}"


# --------------------------------------------------------------------------- #
# 7. DECLARED is an honest label (asserted, not measured, never upgraded)
# --------------------------------------------------------------------------- #
def test_declared_label_is_in_honest_vocabulary():
    """Regression: DECLARED honestly means 'asserted/stated, not measured and not proven'
    (same contract as EvidenceLabel.DECLARED in szl_quantum_utility). Its absence from the
    vocabulary made every honestly-DECLARED surface the single reachable violation that
    dragged the whole estate verdict to VIOLATED."""
    assert "DECLARED" in hw.HONEST_LABELS
    for payload in ({"label": "DECLARED"}, {"data_label": "DECLARED"},
                    {"doctrine": {"label_top": "DECLARED"}}):
        label_tok, _prov, checks = hw._eval_payload(payload)
        assert label_tok == "DECLARED", f"{payload} resolved to {label_tok!r}"
        by = {c["invariant"]: c for c in checks}
        vocab = by.get("label_in_honest_vocabulary")
        assert vocab is not None, f"invariant not evaluated for {payload}"
        assert vocab["status"] == hw.SATISFIED, f"honest DECLARED wrongly flagged: {payload}"


def test_declared_is_never_upgraded_to_measured_or_proven():
    """DECLARED is a WEAK claim and must stay weak — never silently promoted."""
    for raw in ("DECLARED", "DECLARED — static registry, live metadata fetched separately"):
        label_tok, _prov, _checks = hw._eval_payload({"label": raw})
        assert label_tok == "DECLARED", f"{raw!r} upgraded to {label_tok!r}"


def test_shared_label_resolver_also_recognises_declared():
    """The wall delegates token resolution to szl_frontier_index._primary_label, so that
    shared vocabulary — not only the wall's own copy — gates the verdict. Both must agree."""
    assert "DECLARED" in fi.HONEST_LABELS
    assert fi._primary_label("DECLARED") == "DECLARED"
    assert set(hw.HONEST_LABELS) == set(fi.HONEST_LABELS)


def test_frontier_registry_declared_label_is_satisfied():
    """The real surface that triggered this: the primary-project registry labels its static,
    operator-asserted registry DECLARED and labels only live GitHub reads MEASURED. Reading
    its OWN manifest must now be SATISFIED, never a violation."""
    registry = pytest.importorskip("research.a11oy_primary_project_registry")
    assert registry.STATIC_LABEL == "DECLARED"
    assert registry.LIVE_LABEL == "MEASURED", "measurements must keep the MEASURED label"
    label_tok, _prov, checks = hw._eval_payload(registry.info())
    assert label_tok == "DECLARED"
    by = {c["invariant"]: c for c in checks}
    assert by["label_in_honest_vocabulary"]["status"] == hw.SATISFIED


def test_widened_vocabulary_did_not_become_a_rubber_stamp():
    """Recognising DECLARED must not turn the check into a pass-everything. Λ is Conjecture 1,
    never a theorem: the strings below are NEGATIVE examples the estate never declares, kept
    only to prove a label outside the honest set is still VIOLATED."""
    for raw in ("UNRECOGNIZED-MARKETING-LABEL", "TOTALLY-VERIFIED-BY-ASSERTION"):
        label_tok, _prov, checks = hw._eval_payload({"label": raw})
        by = {c["invariant"]: c for c in checks}
        assert label_tok is None, f"{raw!r} must map to NO honest token, got {label_tok!r}"
        assert by["label_in_honest_vocabulary"]["status"] == hw.VIOLATED


def test_lambda_negated_theorem_is_not_a_violation():
    """Regression: a lambda declared as a Conjecture that explicitly says it is
    'NOT a theorem' / 'never a theorem' must PASS. The prior naive substring test
    (`"theorem" not in low`) false-flagged the honest negated phrasing, which was
    the single reachable violation dragging the live estate verdict to VIOLATED."""
    honest_variants = [
        "Conjecture 1 (advisory, NOT a theorem; never green/proven)",
        "Conjecture 1 — advisory only, never a theorem, never green",
        "Conjecture 1 (advisory, gray; isn't a theorem)",
    ]
    for lam in honest_variants:
        _, _, checks = hw._eval_payload({"doctrine": {"lambda": lam}})
        by = {c["invariant"]: c for c in checks}
        c = by.get("lambda_is_conjecture_not_theorem")
        assert c is not None, f"invariant not evaluated for: {lam!r}"
        assert c["status"] == "SATISFIED", f"honest negated-theorem lambda wrongly flagged: {lam!r}"


def test_lambda_affirmative_theorem_claim_is_a_violation():
    """A lambda that AFFIRMATIVELY claims to be proven must be flagged. The strings
    below are NEGATIVE examples the estate never claims: Λ stays Conjecture 1,
    never a theorem, never green. They exist only so the checker proves it still
    catches a real affirmative claim."""
    for lam in ["Lambda is a theorem, proven green",
                "now a theorem with trust 1.0"]:
        _, _, checks = hw._eval_payload({"doctrine": {"lambda": lam}})
        by = {c["invariant"]: c for c in checks}
        c = by.get("lambda_is_conjecture_not_theorem")
        assert c is not None
        assert c["status"] == "VIOLATED", f"affirmative theorem claim not flagged: {lam!r}"
