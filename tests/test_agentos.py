"""feat/frontier-agentos — Agent OS map contract guard.

agentos composes the estate's OWN in-process components (agentops, anatomy,
honestywall, doctrine + locked-8, optional governed loops) into ONE operator's-eye
node/edge map, carrying each node's LIVE verdict from the honestywall aggregate.
These tests pin the honest-by-construction invariants that make the map trustworthy —
no mocks of the honesty logic itself, only controlled aggregate/registry inputs where
a real violation cannot be forced against the live estate:

  1. Routes (GET map/status/info, POST snapshot) are registered and answer 200 (never
     500), BEFORE the SPA / Node-proxy catch-alls.
  2. RECEIPT-ON-WRITE-NOT-ON-READ: GET map/status mint NOTHING; POST snapshot emits ONE
     UNSIGNED SHA-256 content-digest receipt (signed is False).
  3. NEVER OPERATING when a backing node is VIOLATED: a backing surface that reports a
     reachable invariant violation forces the node VIOLATED and the map HALTED-HONEST.
  4. Unreachable backing -> UNKNOWN (map DEGRADED, never a fabricated OPERATING).
  5. NEVER invents a node whose backing is absent from the live surface registry.
  6. Doctrine: locked-8 exact, adds nothing, Λ = Conjecture 1, trust 0.97 (never 100%).

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import pytest

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient  # noqa: E402

import serve  # noqa: E402
import szl_agentos as ao  # noqa: E402

MAP = "/api/a11oy/v1/govern/agentos"
STATUS = "/api/a11oy/v1/govern/agentos/status"
INFO = "/api/a11oy/v1/govern/agentos/info"
SNAP = "/api/a11oy/v1/govern/agentos/snapshot"
VERDICTS = {ao.N_INTACT, ao.N_DEGRADED, ao.N_UNKNOWN, ao.N_VIOLATED}
STATES = {ao.OPERATING, ao.MAP_DEGRADED, ao.HALTED_HONEST}


def _route_index(path):
    for i, r in enumerate(serve.app.router.routes):
        if getattr(r, "path", None) == path:
            return i
    return None


def _agg_with(surfaces, doctrine=None):
    """A minimal, well-formed honestywall aggregate fixture."""
    return {
        "ok": True,
        "verdict": "INTACT",
        "surfaces": surfaces,
        "doctrine": doctrine or {
            "locked_proven": 8, "adds_to_locked_8": 0, "lambda": "Conjecture 1",
            "trust_ceiling": 0.97, "trust_100_percent": False,
        },
        "summary": {},
    }


# --------------------------------------------------------------------------- #
# 1. registration + ordering
# --------------------------------------------------------------------------- #
def test_routes_registered_before_catchalls():
    for path in (MAP, STATUS, INFO, SNAP):
        assert _route_index(path) is not None, f"{path} not registered"
    spa = _route_index("/{full_path:path}")
    proxy = _route_index("/api/a11oy/{path:path}")
    for path in (MAP, STATUS, INFO, SNAP):
        idx = _route_index(path)
        if spa is not None:
            assert idx < spa, f"{path} ({idx}) must precede the SPA catch-all ({spa})"
        if proxy is not None:
            assert idx < proxy, f"{path} ({idx}) must precede the Node proxy ({proxy})"


# --------------------------------------------------------------------------- #
# 2. receipt-on-write-not-on-read
# --------------------------------------------------------------------------- #
def test_get_map_answers_and_mints_nothing():
    with TestClient(serve.app) as c:
        r = c.get(MAP)
    assert r.status_code == 200, f"{MAP} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == ao.MODELED
    assert j["state"] in STATES
    assert "receipt" not in j, "GET map is a PURE READ — must mint NO receipt"


def test_get_status_is_static_and_mints_nothing():
    with TestClient(serve.app) as c:
        r = c.get(STATUS)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["label"] == ao.MODELED
    # status is a STATIC self-manifest (the honestywall probe target): no live state/receipt.
    assert "receipt" not in j
    assert j["honesty_invariants"]["never_operating_while_any_node_violated"] is True


def test_post_snapshot_mints_unsigned_sha256_receipt():
    with TestClient(serve.app) as c:
        r = c.post(SNAP)
    assert r.status_code == 200, f"{SNAP} -> {r.status_code} (must never 500)"
    j = r.json()
    assert j["ok"] is True and j["label"] == ao.MODELED
    assert j["state"] in STATES
    rec = j["receipt"]
    assert rec["algorithm"] == "sha256"
    assert rec["signed"] is False, "receipt must be UNSIGNED (no fabricated signature)"
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert isinstance(rec["content_sha256"], str) and len(rec["content_sha256"]) == 64
    # digest is deterministic over the integrity content (excludes the volatile clock).
    assert rec["content_sha256"] == ao._content_receipt(j)["content_sha256"]


def test_get_info_is_static_pure_read():
    with TestClient(serve.app) as c:
        r = c.get(INFO)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and "receipt" not in j
    assert set(j["node_verdicts"]) == VERDICTS
    assert set(j["states"]) == STATES


# --------------------------------------------------------------------------- #
# 3. NEVER OPERATING when a backing node is VIOLATED (controlled aggregate input)
# --------------------------------------------------------------------------- #
def test_violated_backing_forces_halted_honest(monkeypatch):
    """A backing surface that reports a reachable invariant violation MUST force its node
    VIOLATED and the whole map HALTED-HONEST — never OPERATING, never a confident green."""
    monkeypatch.setattr(ao, "_registry_ids", lambda: {"agentops", "anatomy", "honestywall"})
    agg = _agg_with([
        {"id": "agentops", "status": "NATIVE-OK", "checks_violated": 1, "label": "MODELED"},
        {"id": "anatomy", "status": "NATIVE-OK", "checks_violated": 0, "label": "MODELED"},
        {"id": "honestywall", "status": "NATIVE-OK", "checks_violated": 0, "label": "MODELED"},
    ])
    monkeypatch.setattr(ao, "_honestywall_aggregate", lambda app, ns="a11oy": agg)
    mp = ao._build_map(None, "a11oy")
    daily = next(n for n in mp["nodes"] if n["id"] == "daily_loop")
    assert daily["verdict"] == ao.N_VIOLATED
    assert mp["state"] == ao.HALTED_HONEST, "must HALT-HONEST when a backing node is VIOLATED"
    assert mp["state"] != ao.OPERATING


def test_all_intact_backing_operates(monkeypatch):
    """When every present backing node is INTACT, the map may report OPERATING (positive
    control so the HALTED-HONEST path above is meaningful, not vacuous)."""
    monkeypatch.setattr(ao, "_registry_ids", lambda: {"agentops", "anatomy", "honestywall"})
    agg = _agg_with([
        {"id": "agentops", "status": "NATIVE-OK", "checks_violated": 0, "label": "MODELED"},
        {"id": "anatomy", "status": "NATIVE-OK", "checks_violated": 0, "label": "MODELED"},
        {"id": "honestywall", "status": "NATIVE-OK", "checks_violated": 0, "label": "MODELED"},
    ])
    monkeypatch.setattr(ao, "_honestywall_aggregate", lambda app, ns="a11oy": agg)
    mp = ao._build_map(None, "a11oy")
    assert mp["summary"]["verdict_counts"][ao.N_VIOLATED] == 0
    assert mp["summary"]["verdict_counts"][ao.N_UNKNOWN] == 0
    assert mp["state"] == ao.OPERATING


# --------------------------------------------------------------------------- #
# 4. unreachable backing -> UNKNOWN -> DEGRADED (never fabricated OPERATING)
# --------------------------------------------------------------------------- #
def test_unreachable_aggregate_is_unknown_and_degrades(monkeypatch):
    monkeypatch.setattr(ao, "_registry_ids", lambda: {"agentops", "anatomy", "honestywall"})
    monkeypatch.setattr(ao, "_honestywall_aggregate", lambda app, ns="a11oy": None)
    mp = ao._build_map(None, "a11oy")
    surf_nodes = [n for n in mp["nodes"] if n["backing_kind"] == "surface"]
    assert surf_nodes, "expected surface-backed nodes present in the registry"
    for n in surf_nodes:
        assert n["verdict"] == ao.N_UNKNOWN, "unreachable backing must render UNKNOWN"
    assert mp["state"] == ao.MAP_DEGRADED, "UNKNOWN must degrade, never pass as OPERATING"
    assert mp["state"] != ao.OPERATING


def test_missing_backing_entry_is_unknown(monkeypatch):
    """A backing surface registered but absent from the aggregate this request is UNKNOWN
    (never silently treated as intact)."""
    monkeypatch.setattr(ao, "_registry_ids", lambda: {"agentops"})
    agg = _agg_with([])  # agentops present in registry but not in the aggregate
    monkeypatch.setattr(ao, "_honestywall_aggregate", lambda app, ns="a11oy": agg)
    mp = ao._build_map(None, "a11oy")
    daily = next(n for n in mp["nodes"] if n["id"] == "daily_loop")
    assert daily["verdict"] == ao.N_UNKNOWN


# --------------------------------------------------------------------------- #
# 5. never invents a node whose backing is absent from the live registry
# --------------------------------------------------------------------------- #
def test_never_invents_a_node_absent_from_registry(monkeypatch):
    """With an EMPTY surface registry, no surface-backed node may appear; only the
    immutable-doctrine node (standing goals) is rendered fixed."""
    monkeypatch.setattr(ao, "_registry_ids", lambda: set())
    monkeypatch.setattr(ao, "_honestywall_aggregate", lambda app, ns="a11oy": _agg_with([]))
    mp = ao._build_map(None, "a11oy")
    ids = {n["id"] for n in mp["nodes"]}
    assert ids == {"standing_goals"}, f"surface-backed node invented w/o backing: {ids}"
    # and no edge dangles to an absent node.
    present = {n["id"] for n in mp["nodes"]}
    for e in mp["edges"]:
        assert e["src"] in present and e["dst"] in present


def test_optional_loop_node_present_only_when_registered(monkeypatch):
    monkeypatch.setattr(ao, "_registry_ids", lambda: {"agentops", "loopforge"})
    monkeypatch.setattr(ao, "_honestywall_aggregate", lambda app, ns="a11oy": None)
    mp = ao._build_map(None, "a11oy")
    ids = {n["id"] for n in mp["nodes"]}
    assert "loopforge" in ids
    assert "mesh" not in ids, "mesh has no registered backing — must not be rendered"


# --------------------------------------------------------------------------- #
# 6. doctrine — verbatim, never upgraded
# --------------------------------------------------------------------------- #
def test_doctrine_node_violated_when_aggregate_inflates_locked_count(monkeypatch):
    """A honestywall doctrine block that inflates the locked-proof count forces the
    immutable-doctrine node VIOLATED — the map never upgrades it to INTACT."""
    monkeypatch.setattr(ao, "_registry_ids", lambda: set())
    bad_doctrine = {"locked_proven": 9, "adds_to_locked_8": 0, "lambda": "Conjecture 1",
                    "trust_ceiling": 0.97, "trust_100_percent": False}
    monkeypatch.setattr(ao, "_honestywall_aggregate",
                        lambda app, ns="a11oy": _agg_with([], doctrine=bad_doctrine))
    mp = ao._build_map(None, "a11oy")
    goals = next(n for n in mp["nodes"] if n["id"] == "standing_goals")
    assert goals["verdict"] == ao.N_VIOLATED
    assert mp["state"] == ao.HALTED_HONEST


def test_doctrine_block_locked8_lambda_trust():
    with TestClient(serve.app) as c:
        j = c.post(SNAP).json()
    d = j["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_state_in_real_estate_is_consistent():
    """Against the REAL booted estate: the map state is consistent with the observed
    per-node verdict evidence and no node verdict is outside the honest vocabulary."""
    with TestClient(serve.app) as c:
        j = c.post(SNAP).json()
    vc = j["summary"]["verdict_counts"]
    if vc.get(ao.N_VIOLATED, 0) >= 1:
        assert j["state"] == ao.HALTED_HONEST
    elif vc.get(ao.N_UNKNOWN, 0) + vc.get(ao.N_DEGRADED, 0) >= 1:
        assert j["state"] == ao.MAP_DEGRADED
    else:
        assert j["state"] == ao.OPERATING
    for n in j["nodes"]:
        assert n["verdict"] in VERDICTS, f"{n['id']}: non-vocab verdict {n['verdict']}"
