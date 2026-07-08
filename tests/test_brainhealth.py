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

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402
import szl_brainhealth as bh  # noqa: E402

HEALTH = "/api/a11oy/v1/brain/health"
INFO = "/api/a11oy/v1/brain/health/info"
RECEIPT = "/api/a11oy/v1/brain/health/receipt"
VERDICTS = {bh.TRUSTWORTHY, bh.DEGRADED, bh.UNTRUSTWORTHY, bh.INSUFFICIENT_SIGNAL}


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def _stub(monkeypatch, key, payload):
    """Stub a sibling as AVAILABLE by supplying a callable in the probe-override seam."""
    monkeypatch.setitem(bh._PROBE_OVERRIDES, key, lambda q, k: dict(payload))


# --------------------------------------------------------------------------- #
# 1. registration + ordering
# --------------------------------------------------------------------------- #
def test_routes_registered_before_catchalls():
    for path in (HEALTH, INFO, RECEIPT):
        assert _route_index(path) is not None, f"{path} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    for path in (HEALTH, INFO, RECEIPT):
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
    agg = bh.build_rollup("q", 4)
    assert agg["verdict"] in (bh.TRUSTWORTHY, bh.DEGRADED)
    assert agg["verdict"] != bh.UNTRUSTWORTHY
    sigs = agg["summary"]["signals"]
    assert sigs.get("contradiction") == bh.SIG_OK


# --------------------------------------------------------------------------- #
# 4. UNAVAILABLE handled honestly (no fabrication) — siblings absent
# --------------------------------------------------------------------------- #
def test_unavailable_sibling_degrades_never_fabricates(monkeypatch):
    # only two siblings present; the other three are absent (no override, unimportable).
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
    _stub(monkeypatch, "freshness", {"label": "SAMPLE", "freshness": 0.8})
    agg = bh.build_rollup("q", 4)
    assert agg["summary"]["components_available"] == 2
    assert agg["summary"]["components_unavailable"] == 3
    # every unavailable component is honestly UNAVAILABLE with no fabricated value/label.
    for c in agg["components"]:
        if not c["available"]:
            assert c["label"] == bh.UNAVAILABLE
            assert c["value"] is None and c["signal"] is None
            assert c["note"], "an unavailable component must carry an honest reason"
    # gaps but nothing adverse -> DEGRADED, never TRUSTWORTHY.
    assert agg["verdict"] == bh.DEGRADED
    assert agg["verdict"] != bh.TRUSTWORTHY


def test_all_siblings_absent_is_insufficient_signal():
    # No overrides and (on main) no sibling modules importable -> honestly INSUFFICIENT-SIGNAL,
    # never a fabricated TRUSTWORTHY over zero signal.
    bh._PROBE_OVERRIDES.clear()
    agg = bh.build_rollup("q", 4)
    assert agg["summary"]["components_available"] == 0
    assert agg["verdict"] == bh.INSUFFICIENT_SIGNAL


# --------------------------------------------------------------------------- #
# 5. INSUFFICIENT-SIGNAL when too few available
# --------------------------------------------------------------------------- #
def test_one_component_is_insufficient_signal(monkeypatch):
    _stub(monkeypatch, "grounding", {"label": "MODELED", "grounding_confidence": 0.9})
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
