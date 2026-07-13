"""feat/frontier-brainhealth — Brain Health rollup contract guard.

Brain Health is the brain's equivalent of the Honesty Wall: a governed ROLLUP that reads
each brain-honesty sibling surface's OWN signal + honest label VERBATIM and rolls the
AVAILABLE ones into ONE brain-trust verdict for a query. These tests pin the honest-by-
construction invariants — sibling availability is stubbed BOTH ways (present -> a callable in
the probe-override seam; absent -> no override AND no real module on the path), because the
sibling modules ship in separate not-yet-merged PRs:

  1. Routes (GET health/info, POST receipt) are registered and answer 200 (never 500),
     BEFORE the SPA / Node-proxy catch-alls.
  2. RECEIPT-ON-WRITE-NOT-ON-READ: GET health/info mint NOTHING; POST receipt emits ONE
     UNSIGNED SHA-256 content-digest receipt (signed is False), deterministic over content.
  3. NEVER TRUSTWORTHY if any AVAILABLE component reports an adverse honesty signal
     (abstain / insufficient / conflict-flagged / stale-dominant) -> UNTRUSTWORTHY.
  4. UNAVAILABLE handled honestly: an unimportable sibling degrades to UNAVAILABLE with a
     reason and no fabricated value/label; gaps -> DEGRADED, never TRUSTWORTHY.
  5. INSUFFICIENT-SIGNAL when fewer than MIN_COMPONENTS are available (never a guess).
  6. NEVER upgrades a label: a component's declared honest label is read VERBATIM.
  7. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1, trust ceiling 0.97 (never 100%).

Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
import pytest
import types

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402
import szl_brainhealth as bh  # noqa: E402

HEALTH = "/api/a11oy/v1/brain/health"
INFO = "/api/a11oy/v1/brain/health/info"
RECEIPT = "/api/a11oy/v1/brain/health/receipt"
REFRESH = "/api/a11oy/v1/brain/health/refresh"
CORPUS_SOURCES = "/api/a11oy/v1/brain/health/corpus-sources"
VERDICTS = {bh.TRUSTWORTHY, bh.DEGRADED, bh.UNTRUSTWORTHY, bh.INSUFFICIENT_SIGNAL}


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def _stub(monkeypatch, key, payload):
    """Stub a sibling as AVAILABLE by supplying a callable in the probe-override seam."""
    monkeypatch.setitem(bh._PROBE_OVERRIDES, key, lambda q, k: dict(payload))


_ALL_KEYS = tuple(c["key"] for c in bh.COMPONENTS)


def _force_unavailable(monkeypatch, *keys):
    """Force each named sibling UNAVAILABLE through the probe-override seam by supplying a
    callable that returns a non-manifest (None). This makes the 'sibling absent' scenarios
    deterministic regardless of which sibling modules happen to be importable on this branch —
    the module treats an override that yields no manifest dict as honestly UNAVAILABLE."""
    for key in keys:
        monkeypatch.setitem(bh._PROBE_OVERRIDES, key, lambda q, k: None)


# --------------------------------------------------------------------------- #
# 1. registration + ordering
# --------------------------------------------------------------------------- #
def test_routes_registered_before_catchalls():
    for path in (HEALTH, INFO, RECEIPT, REFRESH, CORPUS_SOURCES):
        assert _route_index(path) is not None, f"{path} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    for path in (HEALTH, INFO, RECEIPT, REFRESH, CORPUS_SOURCES):
        idx = _route_index(path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


# --------------------------------------------------------------------------- #
# 2. receipt-on-write-not-on-read
# --------------------------------------------------------------------------- #
def test_get_health_answers_and_mints_nothing():
    with TestClient(serve.app) as c:
        r = c.get(HEALTH, params={"q": "what proves the thesis", "k": 6})
    assert r.status_code == 200, f"{HEALTH} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    assert j["verdict"] in VERDICTS
    assert "receipt" not in j, "GET health is a PURE READ — must mint NO receipt"


def test_empty_query_is_service_view_not_fake_query_failure(monkeypatch):
    """Blank dashboard polling must not run query components or emit a tiny trust score."""
    for key in _ALL_KEYS:
        monkeypatch.setitem(
            bh._PROBE_OVERRIDES, key,
            lambda q, k: (_ for _ in ()).throw(AssertionError("blank q invoked component")),
        )
    monkeypatch.setattr(bh, "_source_snapshot_metadata", lambda ns: {
        "available": True, "graph_content_hash": "abc", "node_count": 12,
        "capture_evidence": {"repo_snapshot_captured": "2026-07-07"},
    })
    monkeypatch.setattr(bh, "_service_readiness", lambda ns, snapshot=None: {
        "status": bh.SERVICE_READY, "operational": True, "query_trust_equivalent": False,
    })
    agg = bh.build_rollup("", 12)
    assert agg["query_assessment"]["status"] == bh.QUERY_NOT_EVALUATED
    assert agg["service_readiness"]["status"] == bh.SERVICE_READY
    assert agg["verdict"] == bh.INSUFFICIENT_SIGNAL
    assert agg["modeled_trust"] is None
    assert all(c["evaluation_status"] == bh.QUERY_NOT_EVALUATED for c in agg["components"])


def test_untraceable_provenance_is_adverse(monkeypatch):
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "provenance", {
        "label": "MODELED", "verdict": "UNTRACEABLE",
        "coverage": {"fraction_traceable_to_source": 0.0},
    })
    _force_unavailable(monkeypatch, "freshness", "contradiction", "uncertainty")
    agg = bh.build_rollup("specific query", 4)
    assert agg["verdict"] == bh.UNTRUSTWORTHY
    assert {a["key"] for a in agg["summary"]["adverse"]} == {"provenance"}


def test_bounded_refresh_reindexes_but_never_claims_freshness(monkeypatch):
    snapshots = iter([
        {"available": True, "graph_content_hash": "old", "node_count": 10,
         "capture_evidence": {"repo_snapshot_captured": "2026-07-07"}},
        {"available": True, "graph_content_hash": "new", "node_count": 11,
         "capture_evidence": {"repo_snapshot_captured": "2026-07-07"}},
    ])
    monkeypatch.setattr(bh, "_source_snapshot_metadata", lambda ns: next(snapshots))
    called = []
    monkeypatch.setitem(__import__("sys").modules, "szl_brain_api", types.SimpleNamespace(
        get_index=lambda ns, refresh=False: called.append((ns, refresh))))
    monkeypatch.setattr(bh, "_LAST_REFRESH_MONOTONIC", 0.0)
    out = bh.handle_refresh("a11oy")
    assert out["ok"] is True and out["outcome"] == "REINDEXED"
    assert out["changed"] is True and out["source_freshness_changed"] is False
    assert called == [("a11oy", True)]
    assert out["receipt"]["signed"] is False
    assert len(out["receipt"]["content_sha256"]) == 64
    second = bh.handle_refresh("a11oy")
    assert second["ok"] is False and second["outcome"] == "REINDEX-COOLDOWN"
    monkeypatch.setattr(bh, "_LAST_REFRESH_MONOTONIC", 0.0)


def test_refresh_client_guard_fails_closed():
    assert bh._client_is_loopback("127.0.0.1") is True
    assert bh._client_is_loopback("::1") is True
    assert bh._client_is_loopback("testclient") is True
    assert bh._client_is_loopback("10.0.0.7") is False
    assert bh._client_is_loopback(None) is False


def test_testclient_is_allowed_to_call_local_refresh_route(monkeypatch):
    monkeypatch.setattr(bh, "handle_refresh", lambda ns: {
        "ok": True, "outcome": "REINDEXED", "source_freshness_changed": False,
        "receipt": {"signed": False},
    })
    with TestClient(serve.app) as c:
        r = c.post(REFRESH)
    assert r.status_code == 200
    assert r.json()["outcome"] == "REINDEXED"


def test_nonproved_corpus_classes_never_raise_proof_or_trust():
    rows = [
        {"id": "open", "evidence_class": "OPEN", "artifact_sha256": "a" * 64},
        {"id": "refuted", "evidence_class": "REFUTED", "artifact_sha256": "b" * 64},
        {"id": "sorry", "evidence_class": "PROVED", "artifact_sha256": "c" * 64,
         "sorry_count": 1, "proof_receipt": {"verified": True, "kernel_commit": "k",
                                                 "artifact_sha256": "c" * 64}},
        {"id": "no-receipt", "evidence_class": "PROVED", "artifact_sha256": "d" * 64},
    ]
    got = [bh._classify_corpus_entry(row) for row in rows]
    assert [r["effective_class"] for r in got] == ["OPEN", "REFUTED", "OPEN", "UNKNOWN"]
    assert all(r["proof_credit"] == 0 and not r["trust_uplift_eligible"] for r in got)


def test_proved_requires_matching_verified_kernel_receipt():
    sha = "e" * 64
    got = bh._classify_corpus_entry({
        "id": "proved", "evidence_class": "PROVED", "artifact_sha256": sha,
        "sorry_count": 0,
        "proof_receipt": {"verified": True, "kernel_commit": "c7c0ba17",
                          "artifact_sha256": sha},
    })
    assert got["effective_class"] == "PROVED"
    assert got["proof_credit"] == 1 and got["trust_uplift_eligible"] is True


def test_get_info_is_static_pure_read():
    with TestClient(serve.app) as c:
        r = c.get(INFO)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED" and "receipt" not in j
    assert set(j["verdicts"]) == VERDICTS


def test_post_receipt_mints_unsigned_sha256_and_is_deterministic():
    with TestClient(serve.app) as c:
        r = c.post(RECEIPT, params={"q": "q1", "k": 5})
    assert r.status_code == 200, f"{RECEIPT} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == "MODELED"
    rec = j["receipt"]
    assert rec["algorithm"] == "sha256"
    assert rec["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(rec["content_sha256"], str) and len(rec["content_sha256"]) == 64
    # digest is deterministic over the integrity content (excludes the volatile clock).
    assert rec["content_sha256"] == bh._content_receipt(j)["content_sha256"]


def test_handle_health_never_mints_but_handle_receipt_does():
    read = bh.handle_health("q", 4)
    assert "receipt" not in read, "GET path must never mint a receipt"
    write = bh.handle_receipt("q", 4)
    assert "receipt" in write and write["receipt"]["signed"] is False


# --------------------------------------------------------------------------- #
# 3. NEVER TRUSTWORTHY when an available component is adverse
# --------------------------------------------------------------------------- #
def test_abstain_forces_untrustworthy_never_trustworthy(monkeypatch):
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "freshness", {"label": "SAMPLE", "freshness": 0.8})
    _stub(monkeypatch, "provenance", {"label": "MEASURED", "provenance_coverage": 0.9})
    # one component honestly declares it must abstain -> the whole rollup is UNTRUSTWORTHY.
    _stub(monkeypatch, "uncertainty", {"label": "MODELED", "abstain": True})
    agg = bh.build_rollup("q", 4)
    assert agg["verdict"] == bh.UNTRUSTWORTHY
    assert agg["verdict"] != bh.TRUSTWORTHY
    keys = {a["key"] for a in agg["summary"]["adverse"]}
    assert "uncertainty" in keys


def test_conflict_flag_string_is_adverse(monkeypatch):
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "contradiction",
          {"label": "MODELED", "verdict": "conflict-flagged", "conflict": True})
    agg = bh.build_rollup("q", 4)
    assert agg["verdict"] == bh.UNTRUSTWORTHY


def test_negated_adverse_token_is_not_a_violation(monkeypatch):
    # a component that DECLARES it has "no conflict" is honestly OK, not adverse.
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "contradiction",
          {"label": "MODELED", "verdict": "no-conflict", "contradiction_score": 0.0})
    # Force the remaining siblings UNAVAILABLE so the verdict turns ONLY on the negated
    # contradiction token, not on whatever a real sibling happens to report on this branch.
    _force_unavailable(monkeypatch, "freshness", "provenance", "uncertainty")
    agg = bh.build_rollup("q", 4)
    assert agg["verdict"] in (bh.TRUSTWORTHY, bh.DEGRADED)
    assert agg["verdict"] != bh.UNTRUSTWORTHY
    sigs = agg["summary"]["signals"]
    assert sigs.get("contradiction") == bh.SIG_OK


# --------------------------------------------------------------------------- #
# 4. UNAVAILABLE handled honestly (no fabrication) — siblings absent
# --------------------------------------------------------------------------- #
def test_unavailable_sibling_degrades_never_fabricates(monkeypatch):
    # All five sibling modules now ship together. Exercise the unavailable contract through
    # the explicit probe seam instead of depending on three modules being absent on disk.
    expected_keys = {"grounding", "freshness", "provenance", "contradiction", "uncertainty"}
    unavailable_keys = {"provenance", "contradiction", "uncertainty"}
    assert set(_ALL_KEYS) == expected_keys, "Brain Health must govern the complete five-module roster"
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "freshness", {"label": "SAMPLE", "freshness": 0.8})
    _force_unavailable(monkeypatch, *unavailable_keys)
    agg = bh.build_rollup("q", 4)
    assert agg["summary"]["components_available"] == 2
    assert agg["summary"]["components_unavailable"] == 3
    # every unavailable component is honestly UNAVAILABLE with no fabricated value/label.
    observed_unavailable = {c["key"] for c in agg["components"] if not c["available"]}
    assert observed_unavailable == unavailable_keys
    for c in agg["components"]:
        if not c["available"]:
            assert c["label"] == bh.UNAVAILABLE
            assert c["value"] is None and c["signal"] is None
            assert c["note"], "an unavailable component must carry an honest reason"
    # gaps but nothing adverse -> DEGRADED, never TRUSTWORTHY.
    assert agg["verdict"] == bh.DEGRADED
    assert agg["verdict"] != bh.TRUSTWORTHY


def test_all_siblings_absent_is_insufficient_signal(monkeypatch):
    # Force EVERY component UNAVAILABLE through the probe-override seam so the zero-signal
    # scenario is deterministic even though sibling modules are importable on this branch ->
    # honestly INSUFFICIENT-SIGNAL, never a fabricated TRUSTWORTHY over zero signal.
    _force_unavailable(monkeypatch, *_ALL_KEYS)
    agg = bh.build_rollup("q", 4)
    assert agg["summary"]["components_available"] == 0
    assert agg["verdict"] == bh.INSUFFICIENT_SIGNAL


# --------------------------------------------------------------------------- #
# 5. INSUFFICIENT-SIGNAL when too few available
# --------------------------------------------------------------------------- #
def test_one_component_is_insufficient_signal(monkeypatch):
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    # Force the remaining siblings UNAVAILABLE so EXACTLY one component is available (below
    # MIN_COMPONENTS), deterministically regardless of which siblings import on this branch.
    _force_unavailable(monkeypatch, "freshness", "provenance", "contradiction", "uncertainty")
    agg = bh.build_rollup("q", 4)
    assert agg["summary"]["components_available"] == 1
    assert agg["summary"]["components_available"] < bh.MIN_COMPONENTS
    assert agg["verdict"] == bh.INSUFFICIENT_SIGNAL


# --------------------------------------------------------------------------- #
# 6. never upgrades a label (verbatim); all-OK -> TRUSTWORTHY
# --------------------------------------------------------------------------- #
def test_labels_read_verbatim_and_all_ok_is_trustworthy(monkeypatch):
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "freshness", {"label": "SAMPLE", "freshness": 0.8})
    _stub(monkeypatch, "provenance", {"label": "MEASURED", "provenance_coverage": 0.95})
    _stub(monkeypatch, "contradiction",
          {"label": "STRUCTURAL-ONLY", "verdict": "no-conflict", "contradiction_score": 0.0})
    _stub(monkeypatch, "uncertainty", {"label": "MODELED", "uncertainty": 0.1})
    agg = bh.build_rollup("q", 4)
    assert agg["verdict"] == bh.TRUSTWORTHY
    labels = {c["key"]: c["label"] for c in agg["components"]}
    # each declared honest label is read VERBATIM, never upgraded.
    assert labels["provenance"] == "MEASURED"
    assert labels["freshness"] == "SAMPLE"
    assert labels["contradiction"] == "STRUCTURAL-ONLY"
    # the modeled aggregate is capped at the trust ceiling, never 100%.
    assert agg["modeled_trust"] is not None and agg["modeled_trust"] <= bh.TRUST_CEILING


def test_bogus_marketing_label_is_not_invented(monkeypatch):
    # a token outside the honest vocabulary is NOT accepted as a label; the rollup falls back
    # to its own MODELED label rather than echoing an invented one.
    _stub(monkeypatch, "grounding",
          {"label": "SUPER-VERIFIED-1.0", "grounding_confidence": 0.9})
    _stub(monkeypatch, "freshness", {"label": "SAMPLE", "freshness": 0.8})
    agg = bh.build_rollup("q", 4)
    labels = {c["key"]: c["label"] for c in agg["components"]}
    assert labels["grounding"] == "MODELED", "unrecognized label must NOT be echoed verbatim"
    assert labels["grounding"] != "SUPER-VERIFIED-1.0"


# --------------------------------------------------------------------------- #
# 7. doctrine
# --------------------------------------------------------------------------- #
def test_doctrine_locked8_lambda_trust():
    with TestClient(serve.app) as c:
        j = c.post(RECEIPT).json()
    d = j["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
