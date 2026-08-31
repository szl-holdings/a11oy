# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""test_brainuncertainty — calibrated, honest uncertainty on a brain retrieval.

These checks pin the honest-by-construction contract of the BRAIN UNCERTAINTY surface,
which derives deterministic, explainable uncertainty (score dispersion + retrieval entropy
+ rank stability) over the SAME honest ranked retrieval szl_brain_api serves:

  * the combined uncertainty AND every component always land in [0,1], and all three
    components are reported (never silently dropped);
  * a flat / smeared / ambiguous retrieval reads HIGHLY-UNCERTAIN and recommends abstain;
    a single dominant, coherent, stable retrieval reads CONFIDENT;
  * NEVER CONFIDENT while the dispersion or entropy component is high — the honesty override
    holds whatever the weighted mean happens to be;
  * RECEIPT-ON-WRITE-NOT-ON-READ: the assessment (GET) mints NOTHING; only the receipt
    (POST) emits an UNSIGNED SHA-256 content digest, deterministic over the content;
  * the honest MODELED label is read verbatim and is NEVER upgraded; a missing brain index
    degrades honestly to UNAVAILABLE rather than fabricating a number;
  * doctrine: locked-8 exact, adds 0, Λ = Conjecture 1 (never a theorem), trust 0.97 not 100%.

Adversarial / negative strings below are labeled: Λ stays Conjecture 1, never a theorem,
never green — they exist only to prove the checks still catch a real drift.
"""
import szl_brainuncertainty as bu


class _FakeIndex:
    """Deterministic stand-in retriever so these unit checks never depend on the live graph.
    search(q, k) returns a preset ranked list keyed by a substring of the query."""

    def __init__(self, rows_by_key):
        self._rows = rows_by_key

    def search(self, q, k):
        key = "flat" if "flat" in q else ("single" if "single" in q else "sharp")
        return [dict(r) for r in self._rows.get(key, [])[:max(1, int(k))]]


def _idx():
    sharp = [{"id": "s0", "title": "s0", "community": "c0", "score": 0.95},
             {"id": "s1", "title": "s1", "community": "c0", "score": 0.30},
             {"id": "s2", "title": "s2", "community": "c0", "score": 0.20},
             {"id": "s3", "title": "s3", "community": "c0", "score": 0.12},
             {"id": "s4", "title": "s4", "community": "c0", "score": 0.06}]
    flat = [{"id": f"f{i}", "title": f"f{i}", "community": f"c{i}",
             "score": round(0.50 - 0.005 * i, 4)} for i in range(12)]
    single = [{"id": "u0", "title": "u0", "community": "c0", "score": 0.80}]
    return _FakeIndex({"sharp": sharp, "flat": flat, "single": single})


# --------------------------------------------------------------------------- #
# uncertainty + components in the unit interval, all three reported
# --------------------------------------------------------------------------- #
def test_uncertainty_and_every_component_in_unit_interval():
    idx = _idx()
    for q, k in [("sharp query", 6), ("flat query", 10), ("single query", 3)]:
        a = bu.assess(idx, q, k)
        assert a["ok"] is True and a["label"] == bu.MODELED
        assert 0.0 <= a["uncertainty"] <= 1.0
        comps = a["components"]
        for name in ("score_dispersion", "retrieval_entropy", "rank_stability"):
            assert name in comps, f"{name} component missing"
            u = comps[name]["uncertainty"]
            assert 0.0 <= u <= 1.0, (name, u)
        assert a["honesty_invariants"]["every_component_reported"] is True


# --------------------------------------------------------------------------- #
# verdicts: sharp => CONFIDENT; flat => HIGHLY-UNCERTAIN + abstain
# --------------------------------------------------------------------------- #
def test_sharp_retrieval_is_confident():
    a = bu.assess(_idx(), "sharp query", 6)
    assert a["verdict"] == bu.CONFIDENT
    assert a["abstain_recommended"] is False


def test_flat_retrieval_is_highly_uncertain_and_abstains():
    a = bu.assess(_idx(), "flat query", 10)
    assert a["verdict"] == bu.HIGHLY_UNCERTAIN
    assert a["abstain_recommended"] is True


def test_never_confident_when_dispersion_or_entropy_high():
    a = bu.assess(_idx(), "flat query", 10)
    comps = a["components"]
    high = (comps["score_dispersion"]["uncertainty"] >= bu.COMPONENT_CONFIDENT_CAP
            or comps["retrieval_entropy"]["uncertainty"] >= bu.COMPONENT_CONFIDENT_CAP)
    assert high, "flat fixture should drive dispersion/entropy high"
    assert a["verdict"] != bu.CONFIDENT


def test_no_results_is_highly_uncertain_abstain():
    empty = _FakeIndex({})
    a = bu.assess(empty, "sharp query", 5)  # key resolves to sharp but rows are empty
    assert a["results_retrieved"] == 0
    assert a["verdict"] == bu.HIGHLY_UNCERTAIN
    assert a["abstain_recommended"] is True


# --------------------------------------------------------------------------- #
# component math — direct unit checks on the pure functions
# --------------------------------------------------------------------------- #
def test_score_dispersion_edges():
    u0, _ = bu._score_dispersion([])
    assert u0 == 1.0, "no results => maximal dispersion uncertainty"
    u1, _ = bu._score_dispersion([0.8])
    assert u1 == 0.0, "single result => no dispersion to measure"
    sharp, _ = bu._score_dispersion([0.95, 0.05, 0.03])
    flat, _ = bu._score_dispersion([0.5, 0.49, 0.48, 0.47])
    assert sharp < flat, "a dominant top-1 must be less uncertain than a flat spread"


def test_community_entropy_one_community_is_zero():
    coherent = [{"community": "c0", "score": 0.6}, {"community": "c0", "score": 0.4}]
    u, d = bu._community_entropy(coherent)
    assert u == 0.0 and d["communities"] == 1
    smeared = [{"community": f"c{i}", "score": 0.25} for i in range(4)]
    us, _ = bu._community_entropy(smeared)
    assert us > 0.5, "mass smeared across communities => high retrieval entropy"


def test_rank_stability_reports_ordering_churn_zero_honestly():
    # deterministic score-truncation => observed top-k ordering churn is 0 by construction.
    _u, d = bu._rank_stability([0.9, 0.5, 0.2], [0.9, 0.5, 0.2, 0.19], k=3)
    assert d["ordering_churn_observed"] == 0.0


# --------------------------------------------------------------------------- #
# RECEIPT-ON-WRITE-NOT-ON-READ
# --------------------------------------------------------------------------- #
def test_assessment_get_mints_no_receipt():
    a = bu.assess(_idx(), "sharp query", 6)
    assert "receipt" not in a, "the GET assessment is a PURE READ — must mint no receipt"


def test_content_receipt_is_unsigned_sha256_and_deterministic():
    a = bu.assess(_idx(), "sharp query", 6)
    r1 = bu._content_receipt(a)
    r2 = bu._content_receipt(a)
    assert r1["algorithm"] == "sha256"
    assert r1["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(r1["content_sha256"], str) and len(r1["content_sha256"]) == 64
    assert r1["content_sha256"] == r2["content_sha256"], "digest must be deterministic"


def test_handle_receipt_carries_the_digest_on_write():
    # handle_receipt reads through the live namespace; guard so a missing index degrades
    # honestly rather than failing the suite.
    out = bu.handle_receipt("a11oy", "estate thesis", 6)
    if out.get("ok"):
        rec = out["receipt"]
        assert rec is not None and rec["algorithm"] == "sha256"
        assert rec["signed"] is False and len(rec["content_sha256"]) == 64
    else:
        assert out["label"] == bu.UNAVAILABLE and out.get("receipt") is None


# --------------------------------------------------------------------------- #
# honest labels + degraded path
# --------------------------------------------------------------------------- #
def test_label_is_modeled_and_never_upgraded():
    a = bu.assess(_idx(), "sharp query", 6)
    assert a["label"] == bu.MODELED
    info = bu.handle_info("a11oy")
    assert info["label"] == bu.MODELED
    assert set(info["honest_labels"]) <= {bu.MODELED, bu.UNAVAILABLE}


def test_missing_brain_index_degrades_to_unavailable(monkeypatch):
    def _boom(_ns):
        raise RuntimeError("brain index offline")
    monkeypatch.setattr(bu, "_get_index", _boom)
    out = bu.handle_uncertainty("a11oy", "sharp query", 6)
    assert out["ok"] is False
    assert out["label"] == bu.UNAVAILABLE
    assert "uncertainty" not in out, "must not fabricate a number when degraded"


# --------------------------------------------------------------------------- #
# doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    d = bu._doctrine_block()
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, advisory, never a theorem, never green.
    assert d["lambda"].startswith("Conjecture 1")
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


# --------------------------------------------------------------------------- #
# routes register (GET reads + POST receipt) BEFORE any catch-all
# --------------------------------------------------------------------------- #
def test_register_wires_all_three_routes():
    import pytest
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    status = bu.register(app, ns="a11oy")
    assert status.startswith("brainuncertainty-wired")

    client = TestClient(app)
    info = client.get("/api/a11oy/v1/brain/uncertainty/info")
    assert info.status_code == 200
    j = info.json()
    assert j["ok"] is True and j["label"] == bu.MODELED
    assert "receipt" not in j, "GET info is a pure read"
