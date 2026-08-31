"""feat/frontier-braincontradict — Brain Contradiction Detector contract guard.

The Brain Contradiction Detector surfaces potential CONTRADICTIONS between grounded
knowledge-graph claims HONESTLY and refuses to RESOLVE them. These tests pin the
honest-by-construction invariants that make it trustworthy — no mocks of the detection
logic itself, only planted subgraph inputs and a monkeypatched retrieval seam where the
real graph cannot be forced:

  1. Detects a PLANTED conflict pair -> CONFLICT-FLAGGED (antonym + numeric + negation).
  2. A clean, unrelated query -> NO-CONFLICT (never a fabricated pair).
  3. PRESENTS, NEVER RESOLVES: every conflict carries BOTH sides + adjudication=
     human-required + resolution=None. No winner is ever picked, no side hidden.
  4. RECEIPT-ON-WRITE-NOT-ON-READ: GET detect/info mint NOTHING; POST /receipt emits ONE
     UNSIGNED SHA-256 content-digest receipt (signed is False), deterministic on content.
  5. Labels are MODELED (never MEASURED/upgraded); UNAVAILABLE on honest degrade.
  6. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1 (never a theorem), trust
     ceiling 0.97 (never 100%), confidence capped below 1.0.
  7. Routes register (GET info/detect, POST receipt) and answer 200 (never 500).

Doctrine note: Λ is Conjecture 1, advisory, NEVER a theorem, never green/proven — the
qualifier is inlined here so the negated-theorem phrasing never false-flags a doctrine gate.

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
import pytest

import szl_braincontradict as bc


# --------------------------------------------------------------------------- #
# 1. detects a planted conflict pair
# --------------------------------------------------------------------------- #
def test_planted_conflict_is_flagged():
    """Same-subject claims with opposing polarity/numbers must reach CONFLICT-FLAGGED."""
    nodes = [
        {"id": "n1", "title": "the sensor link is secure", "community": "c0"},
        {"id": "n2", "title": "the sensor link is insecure", "community": "c0"},
        {"id": "n3", "title": "latency budget is 10 ms", "community": "c1"},
        {"id": "n4", "title": "latency budget is 40 ms", "community": "c1"},
    ]
    det = bc.detect_conflicts(nodes, links=[])
    assert det["verdict"] == bc.CONFLICT_FLAGGED
    assert det["conflict_count"] >= 2
    assert det["flagged_count"] >= 1
    signals = {c["signal"] for c in det["conflicts"]}
    assert "antonym" in signals and "numeric" in signals


def test_negation_polarity_is_detected():
    """One side negated, the other not, on a shared subject -> a candidate conflict."""
    nodes = [
        {"id": "a", "title": "the receipt chain verifies", "community": "c0"},
        {"id": "b", "title": "the receipt chain never verifies", "community": "c0"},
    ]
    det = bc.detect_conflicts(nodes, links=[])
    assert det["conflict_count"] >= 1
    assert any(c["signal"] == "negation" for c in det["conflicts"])


# --------------------------------------------------------------------------- #
# 2. clean query -> NO-CONFLICT (never fabricated)
# --------------------------------------------------------------------------- #
def test_clean_query_is_no_conflict():
    nodes = [
        {"id": "m1", "title": "energy ledger records joules", "community": "c0"},
        {"id": "m2", "title": "khipu receipts seal state changes", "community": "c1"},
        {"id": "m3", "title": "pagerank ranks node salience", "community": "c2"},
    ]
    det = bc.detect_conflicts(nodes, links=[])
    assert det["verdict"] == bc.NO_CONFLICT
    assert det["conflict_count"] == 0


def test_unrelated_opposing_terms_do_not_conflict():
    """Opposing terms on DIFFERENT subjects are not a conflict (no shared subject)."""
    nodes = [
        {"id": "x", "title": "the door is open", "community": "c0"},
        {"id": "y", "title": "the valve is closed", "community": "c0"},
    ]
    det = bc.detect_conflicts(nodes, links=[])
    assert det["conflict_count"] == 0
    assert det["verdict"] == bc.NO_CONFLICT


# --------------------------------------------------------------------------- #
# 3. PRESENTS, NEVER RESOLVES
# --------------------------------------------------------------------------- #
def test_never_resolves_never_picks_a_winner():
    nodes = [
        {"id": "n1", "title": "the sensor link is secure", "community": "c0"},
        {"id": "n2", "title": "the sensor link is insecure", "community": "c0"},
    ]
    det = bc.detect_conflicts(nodes, links=[])
    assert det["conflict_count"] >= 1
    for c in det["conflicts"]:
        assert c["resolution"] is None, "must NEVER fabricate a resolution"
        assert c["adjudication"] == "human-required"
        # both sides present, neither hidden
        assert c["a"]["id"] and c["b"]["id"]
        assert "winner" not in c and "verdict" not in c
        assert c["note"]  # honest 'a human must adjudicate' note


def test_confidence_capped_below_one():
    nodes = [
        {"id": "n1", "title": "sensor link secure secure secure", "community": "c0"},
        {"id": "n2", "title": "sensor link insecure insecure", "community": "c0"},
    ]
    det = bc.detect_conflicts(nodes, links=[])
    for c in det["conflicts"]:
        assert c["confidence"] <= bc.CONF_CAP < 1.0


# --------------------------------------------------------------------------- #
# 4. receipt-on-write-not-on-read
# --------------------------------------------------------------------------- #
def test_get_detect_mints_nothing(monkeypatch):
    monkeypatch.setattr(bc, "_retrieve_subgraph",
                        lambda q, k, ns: ([{"id": "n1", "title": "x"}], [], {"source": "t"}))
    out = bc.run_detection("anything", 5, "a11oy")
    assert out["ok"] is True and out["label"] == bc.MODELED
    assert "receipt" not in out, "GET detect is a PURE READ — must mint NO receipt"


def test_get_info_mints_nothing():
    info = bc.handle_info("a11oy")
    assert info["ok"] is True and info["label"] == bc.MODELED
    assert "receipt" not in info, "GET info is a PURE READ — must mint NO receipt"
    assert set(info["verdicts"]) == {bc.NO_CONFLICT, bc.POSSIBLE_CONFLICT, bc.CONFLICT_FLAGGED}


def test_post_receipt_is_unsigned_sha256_and_deterministic(monkeypatch):
    monkeypatch.setattr(bc, "_retrieve_subgraph",
                        lambda q, k, ns: (
                            [{"id": "n1", "title": "sensor link secure", "community": "c0"},
                             {"id": "n2", "title": "sensor link insecure", "community": "c0"}],
                            [], {"source": "t"}))
    out = bc.handle_receipt("sensor", 5, "a11oy")
    rec = out["receipt"]
    assert rec["algorithm"] == "sha256"
    assert rec["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(rec["content_sha256"], str) and len(rec["content_sha256"]) == 64
    # deterministic over the integrity content (excludes the volatile clock).
    again = bc.handle_receipt("sensor", 5, "a11oy")
    assert rec["content_sha256"] == again["receipt"]["content_sha256"]


# --------------------------------------------------------------------------- #
# 5. labels — MODELED, honest degrade, never upgraded
# --------------------------------------------------------------------------- #
def test_label_is_modeled_never_measured(monkeypatch):
    monkeypatch.setattr(bc, "_retrieve_subgraph",
                        lambda q, k, ns: ([], [], {"source": "t"}))
    out = bc.run_detection("q", 5, "a11oy")
    assert out["label"] == bc.MODELED
    assert out["label"] != "MEASURED", "detection is heuristic — never MEASURED"


def test_retrieval_failure_degrades_to_unavailable(monkeypatch):
    def _boom(q, k, ns):
        raise RuntimeError("graph offline")
    monkeypatch.setattr(bc, "_retrieve_subgraph", _boom)
    out = bc.run_detection("q", 5, "a11oy")
    assert out["ok"] is False
    assert out["label"] == bc.UNAVAILABLE, "honest degrade — never a fabricated verdict"
    assert "verdict" not in out, "no fabricated verdict when retrieval is unavailable"


# --------------------------------------------------------------------------- #
# 6. doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    d = bc.handle_info("a11oy")["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["confidence_cap"] < 1.0
    assert d["runtime_cdn"] == 0


def test_method_is_transparent_not_black_box():
    info = bc.handle_info("a11oy")
    assert info["method"]["black_box_model"] is False
    assert set(info["method"]["signals"]) == {
        "negation-polarity", "antonym-opposition", "numeric-conflict"}


# --------------------------------------------------------------------------- #
# 7. routes register + answer (real FastAPI app)
# --------------------------------------------------------------------------- #
def test_routes_register_and_answer_200():
    fastapi = pytest.importorskip("fastapi")
    from starlette.testclient import TestClient

    app = fastapi.FastAPI()
    status = bc.register(app, ns="a11oy")
    assert status.startswith("braincontradict-wired")

    base = "/api/a11oy/v1/brain/contradict"
    with TestClient(app) as c:
        r_info = c.get(f"{base}/info")
        r_det = c.get(base, params={"q": "anything", "k": 3})
        r_rec = c.post(f"{base}/receipt", json={"q": "anything", "k": 3})

    for r in (r_info, r_det, r_rec):
        assert r.status_code == 200, f"{r.request.url} -> {r.status_code} (must never 500)"
    assert r_info.json()["label"] == bc.MODELED
    assert "receipt" not in r_info.json() and "receipt" not in r_det.json()
    assert r_rec.json()["receipt"]["signed"] is False
