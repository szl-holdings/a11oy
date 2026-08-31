# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainwatch — Brain Watch honesty-posture drift contract guard.

Brain Watch computes a deterministic honesty-posture snapshot of the live brain
graph (label distribution, orphan share, community fragmentation, salience
concentration) and compares CURRENT vs a caller-supplied PRIOR to report DRIFT.
These tests pin the honest-by-construction invariants — no mocks of the drift logic
itself, only controlled fixture graphs the pure functions run on:

  1. Snapshot metrics are MEASURED from the fixture graph and computed correctly.
  2. BASELINE-ONLY when no prior is supplied — NO trend is fabricated.
  3. STABLE (identical prior) vs DEGRADED (planted UNAVAILABLE/orphan rise), and a
     DEGRADED posture is NEVER softened to STABLE/DRIFTING.
  4. Structural counts labelled MEASURED; the drift delta labelled MODELED.
  5. RECEIPT-ON-WRITE: POST /compare emits ONE deterministic UNSIGNED SHA-256 digest;
     GET /watch mints nothing.
  6. Honesty labels are read VERBATIM and never upgraded.
  7. Doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem),
     trust ceiling 0.97 (never 100%).
  8. Routes register before the SPA / Node-proxy catch-alls and answer without 500.
"""
import pytest

import szl_brainwatch as bw


# --------------------------------------------------------------------------- #
# Fixtures — small, fully synthetic graphs (no network, no heavy index build).
# --------------------------------------------------------------------------- #
def _fixture_nodes():
    return [
        {"id": "a", "label": "HARVESTED", "degree": 4},
        {"id": "b", "label": "MODELED", "degree": 3},
        {"id": "c", "label": "LIVE", "degree": 2},
        {"id": "d", "label": "MODELED", "degree": 1},      # orphan (degree<=1)
        {"id": "e", "label": "UNAVAILABLE", "degree": 0},  # orphan
    ]


def _fixture_snapshot():
    return bw.compute_posture(
        nodes=_fixture_nodes(),
        link_count=5,
        community_of={"a": "c0", "b": "c0", "c": "c1", "d": "c1", "e": "c2"},
        salience={"a": 0.40, "b": 0.25, "c": 0.20, "d": 0.10, "e": 0.05},
        community_algo="fixture-cc",
        content_hash="deadbeef",
        ns="a11oy",
    )


# --------------------------------------------------------------------------- #
# 1. snapshot metrics MEASURED + correct
# --------------------------------------------------------------------------- #
def test_snapshot_metrics_measured():
    snap = _fixture_snapshot()
    assert snap["label"] == bw.LBL_MEASURED
    assert snap["node_count"] == 5 and snap["link_count"] == 5
    m = snap["metrics"]
    # label distribution is the verbatim node labels, counted honestly.
    assert m["label_distribution"] == {"MODELED": 2, "HARVESTED": 1, "LIVE": 1,
                                       "UNAVAILABLE": 1}
    assert m["unavailable_share"] == pytest.approx(0.2)      # 1/5
    assert m["orphan_count"] == 2 and m["orphan_share"] == pytest.approx(0.4)
    assert m["community_count"] == 3
    assert m["community_algo"] == "fixture-cc"
    assert m["largest_community_share"] == pytest.approx(0.4)  # 2/5
    assert m["singleton_community_share"] == pytest.approx(1 / 3)  # c2
    assert 0.0 <= m["salience_gini"] <= 1.0
    assert 0.0 <= m["salience_top1_share"] <= 1.0
    assert m["salience_top5_share"] == pytest.approx(1.0)   # all 5 in top-5


def test_gini_bounds_and_extremes():
    assert bw._gini([]) == 0.0
    assert bw._gini([0.0, 0.0, 0.0]) == 0.0
    assert bw._gini([1.0, 1.0, 1.0]) == pytest.approx(0.0, abs=1e-9)  # perfectly even
    # one node holds nearly all the mass -> high concentration, still <= 1.
    g = bw._gini([0.0, 0.0, 0.0, 100.0])
    assert 0.5 < g <= 1.0


# --------------------------------------------------------------------------- #
# 2. BASELINE-ONLY when no prior — no fabricated trend
# --------------------------------------------------------------------------- #
def test_no_prior_is_baseline_only():
    snap = _fixture_snapshot()
    for bogus in (None, {}, {"metrics": {}}, {"not": "a snapshot"}, "garbage"):
        res = bw.compare(snap, bogus)
        assert res["verdict"] == bw.BASELINE_ONLY, bogus
        assert res["drift"] is None
        assert res["prior_provided"] is False


# --------------------------------------------------------------------------- #
# 3. STABLE vs DEGRADED — degraded is never softened
# --------------------------------------------------------------------------- #
def test_identical_prior_is_stable():
    snap = _fixture_snapshot()
    res = bw.compare(snap, dict(snap))
    assert res["verdict"] == bw.STABLE
    assert res["prior_provided"] is True
    assert all(abs(v) < bw.DRIFT_EPS for v in res["drift"]["delta"].values())


def test_material_unavailable_rise_is_degraded():
    snap = _fixture_snapshot()
    m = snap["metrics"]
    prior = {"metrics": {
        "unavailable_share": 0.0,   # current is 0.2 -> +0.2 rise (material)
        "orphan_share": m["orphan_share"],
        "community_fragmentation": m["community_fragmentation"],
        "largest_community_share": m["largest_community_share"],
        "singleton_community_share": m["singleton_community_share"],
        "salience_gini": m["salience_gini"],
        "salience_top1_share": m["salience_top1_share"],
        "salience_top5_share": m["salience_top5_share"],
    }}
    res = bw.compare(snap, prior)
    assert res["verdict"] == bw.DEGRADED
    assert any(c["metric"] == "unavailable_share"
               for c in res["drift"]["material_changes"])


def test_material_orphan_rise_is_degraded():
    snap = _fixture_snapshot()
    m = snap["metrics"]
    prior = {"metrics": {
        "unavailable_share": m["unavailable_share"],
        "orphan_share": 0.0,        # current 0.4 -> +0.4 rise (material)
        "community_fragmentation": m["community_fragmentation"],
        "largest_community_share": m["largest_community_share"],
        "singleton_community_share": m["singleton_community_share"],
        "salience_gini": m["salience_gini"],
        "salience_top1_share": m["salience_top1_share"],
        "salience_top5_share": m["salience_top5_share"],
    }}
    res = bw.compare(snap, prior)
    assert res["verdict"] == bw.DEGRADED


def test_small_move_is_drifting_not_degraded():
    snap = _fixture_snapshot()
    m = snap["metrics"]
    prior = {"metrics": {
        "unavailable_share": m["unavailable_share"],  # unchanged -> not degrading
        "orphan_share": m["orphan_share"],
        "community_fragmentation": m["community_fragmentation"],
        "largest_community_share": m["largest_community_share"],
        "singleton_community_share": m["singleton_community_share"],
        # salience concentration moved a little (>1pp) but nothing degraded.
        "salience_gini": max(0.0, m["salience_gini"] - 0.05),
        "salience_top1_share": m["salience_top1_share"],
        "salience_top5_share": m["salience_top5_share"],
    }}
    res = bw.compare(snap, prior)
    assert res["verdict"] == bw.DRIFTING
    assert "salience_gini" in res["drift"]["moved_beyond_eps"]


# --------------------------------------------------------------------------- #
# 4. honest labelling — MEASURED snapshot, MODELED drift
# --------------------------------------------------------------------------- #
def test_snapshot_measured_drift_modeled():
    snap = _fixture_snapshot()
    assert snap["label"] == bw.LBL_MEASURED
    res = bw.compare(snap, dict(snap))
    assert res["label"] == bw.LBL_MODELED
    assert res["drift"]["label"] == bw.LBL_MODELED
    # both labels are inside the honest vocabulary (never a token outside the set).
    assert bw.LBL_MEASURED in bw.HONEST_LABELS
    assert bw.LBL_MODELED in bw.HONEST_LABELS


def test_labels_read_verbatim_never_upgraded():
    # A node carrying a low-trust label must be counted VERBATIM, never promoted.
    nodes = [{"id": "x", "label": "STRUCTURAL-ONLY", "degree": 0},
             {"id": "y", "label": "UNAVAILABLE", "degree": 1}]
    snap = bw.compute_posture(
        nodes=nodes, link_count=0, community_of={"x": "c0", "y": "c1"},
        salience={"x": 0.5, "y": 0.5}, community_algo="cc",
        content_hash="beef", ns="a11oy")
    dist = snap["metrics"]["label_distribution"]
    assert dist["STRUCTURAL-ONLY"] == 1 and dist["UNAVAILABLE"] == 1
    # nothing got upgraded to MEASURED/PROVEN.
    assert "MEASURED" not in dist and "PROVEN" not in dist


# --------------------------------------------------------------------------- #
# 5. RECEIPT-ON-WRITE — deterministic unsigned SHA-256 on compare only
# --------------------------------------------------------------------------- #
def test_receipt_deterministic_and_unsigned():
    snap = _fixture_snapshot()
    res = bw.compare(snap, dict(snap))
    r1 = bw._content_receipt(res)
    r2 = bw._content_receipt(res)
    assert r1["algorithm"] == "sha256" and len(r1["content_sha256"]) == 64
    assert r1["signed"] is False and r1["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert r1["content_sha256"] == r2["content_sha256"], "digest must be deterministic"


def test_get_watch_mints_nothing():
    # handle_watch is a pure read (live snapshot may be UNAVAILABLE off-box) — but it
    # must NEVER carry a receipt (receipt-on-write, not on-read).
    out = bw.handle_watch("a11oy")
    assert "receipt" not in out
    assert out["verdict"] == bw.BASELINE_ONLY


# --------------------------------------------------------------------------- #
# 6. doctrine block
# --------------------------------------------------------------------------- #
def test_doctrine_block_locked_and_lambda():
    d = bw._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == bw.LOCKED_SET
    assert len(d["locked_set"]) == 8 and d["adds_to_locked_8"] == 0
    # Λ is Conjecture 1, never a theorem; Khipu BFT is Conjecture 2, never a theorem.
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


# --------------------------------------------------------------------------- #
# 7. live endpoints via TestClient (registration, ordering, honest responses)
# --------------------------------------------------------------------------- #
INFO = "/api/a11oy/v1/brain/watch/info"
WATCH = "/api/a11oy/v1/brain/watch"
COMPARE = "/api/a11oy/v1/brain/watch/compare"


def _route_index(app, path):
    for i, r in enumerate(app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def test_routes_registered_before_catchalls():
    pytest.importorskip("starlette.testclient")
    import serve
    for path in (INFO, WATCH, COMPARE):
        assert _route_index(serve.app, path) is not None, f"{path} not registered"
    spa = _route_index(serve.app, "/{full_path:path}")
    proxy = _route_index(serve.app, "/api/a11oy/{path:path}")
    for path in (INFO, WATCH, COMPARE):
        idx = _route_index(serve.app, path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


def test_endpoints_answer_without_500():
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    import serve
    client = TestClient(serve.app)

    # info — static describe, never 500.
    ri = client.get(INFO)
    assert ri.status_code == 200
    ji = ri.json()
    assert ji["surface_id"] == "brainwatch"
    assert set([bw.STABLE, bw.DRIFTING, bw.DEGRADED, bw.BASELINE_ONLY]) <= set(ji["verdicts"])

    # watch — current posture; BASELINE-ONLY; mints nothing.
    rw = client.get(WATCH)
    assert rw.status_code == 200
    jw = rw.json()
    assert jw["verdict"] == bw.BASELINE_ONLY
    assert "receipt" not in jw
    snap = jw["snapshot"]

    # compare (no body) — honest BASELINE-ONLY, still receipt-on-write.
    rc0 = client.post(COMPARE)
    assert rc0.status_code == 200
    jc0 = rc0.json()
    assert jc0["verdict"] == bw.BASELINE_ONLY and jc0["drift"] is None
    assert "receipt" in jc0 and jc0["receipt"]["signed"] is False

    # compare WITH the prior snapshot — the real drift path.
    rc = client.post(COMPARE, json={"prior": snap})
    assert rc.status_code == 200
    jc = rc.json()
    assert jc["verdict"] in (bw.STABLE, bw.DRIFTING, bw.DEGRADED, bw.BASELINE_ONLY)
    assert jc["receipt"]["algorithm"] == "sha256"
    assert len(jc["receipt"]["content_sha256"]) == 64
    # if the live snapshot was MEASURED, comparing it to itself must be STABLE
    # (deterministic graph -> zero drift), never a fabricated DRIFTING/DEGRADED.
    if snap.get("label") == bw.LBL_MEASURED and jc.get("prior_provided"):
        assert jc["verdict"] == bw.STABLE
