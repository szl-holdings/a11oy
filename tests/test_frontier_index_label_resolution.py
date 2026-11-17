import importlib.util
from pathlib import Path

import pytest

from szl_frontier_index import _extract_label


def test_label_resolution_uses_backend_document_order_recursively() -> None:
    payload = {
        "evidence": {"data_label": "SAMPLE"},
        "label": "LIVE",
    }

    assert _extract_label(payload) == "SAMPLE"


def test_label_resolution_preserves_top_level_label_when_it_comes_first() -> None:
    payload = {
        "label": "MODELED",
        "evidence": {"data_label": "SAMPLE"},
    }

    assert _extract_label(payload) == "MODELED"


def test_unknown_resolves_only_as_a_whole_label_value() -> None:
    assert _extract_label({"label": "UNKNOWN"}) == "UNKNOWN"
    assert _extract_label({"label": "theorem proved; unknown"}) is None
    assert _extract_label({"claim": "PRODUCTION-GRADE, risk unknown"}) is None
    # A real token earlier in the same value still wins over the word.
    assert _extract_label({"label": "MODELED, scale unknown"}) == "MODELED"


def test_router_status_unprobed_sovereign_node_resolves_to_unknown() -> None:
    """Pins a deliberate, disclosed change. /llm/router/status carries no top-level label;
    its only label-bearing field is the unprobed sovereign sub-node (state UNPROBED, label
    UNKNOWN, see szl_llm_registry). Once UNKNOWN joined the vocabulary, the catalog resolves
    the router surface from this endpoint as UNKNOWN instead of skipping it and falling
    through to MODELED from /router/active-flux-crossover/info. UNKNOWN is the weaker claim,
    so this is a downgrade, never an upgrade."""
    payload = {
        "hub": "a11oy",
        "local_nodes": [{
            "backend_id": "sovereign", "live": None, "reachable": None,
            "operational": False, "state": "UNPROBED", "label": "UNKNOWN",
        }],
    }
    assert _extract_label(payload) == "UNKNOWN"


def test_whatsnew_vocabulary_covers_every_catalog_label() -> None:
    """The whatsnew feed copies each catalog label verbatim, so every token the shared resolver
    can return (UNKNOWN included) must be representable in the feed's vocabulary."""
    import szl_frontier_index as fi
    import szl_whatsnew as wn

    assert set(fi.HONEST_LABELS) <= set(wn.HONEST_LABELS), (
        sorted(set(fi.HONEST_LABELS) - set(wn.HONEST_LABELS)))
    assert "UNKNOWN" in wn.HONEST_LABELS


# The two real-route pins below live in this file because CI runs it (tests.yml, Frontier
# Index honesty job). They boot the real app and real routes; only the sovereign mesh
# observation is simulated, and the sovereign env vars are cleared, so the result never
# depends on a node, port or variable on the machine running the tests.
_SOVEREIGN_ENV = ("A11OY_BRAIN_URL", "A11OY_MODEL_BASE_URL", "A11OY_SOVEREIGN_GATEWAY_URL",
                  "SZL_LOCAL_LLM_URL", "SZL_SOVEREIGN_NODES")
_DEAD_URL = "http://127.0.0.1:59999/v1"
_PRIVATE_URL = "http://secret-tunnel.example.invalid:11434/v1"
_MODEL_TAG = "llama3-szl-finetuned-q4"


def _mesh(reachable: bool) -> dict:
    if not reachable:
        return {
            "node_count": 1, "reachable_count": 0, "any_reachable": False,
            "primary_base_url": _DEAD_URL, "selected": None,
            "nodes": [{"index": 0, "base_url": _DEAD_URL, "role": "primary",
                       "reachable": False, "api_style": None, "served_models": [],
                       "error": "NETWORK_FAILURE"}],
            "note": "NO sovereign node reachable THIS request",
        }
    return {
        "node_count": 1, "reachable_count": 1, "any_reachable": True,
        "primary_base_url": _PRIVATE_URL, "selected": {"index": 0, "role": "primary"},
        "nodes": [{"index": 0, "role": "primary", "reachable": True,
                   "api_style": "openai /v1", "served_models": [_MODEL_TAG],
                   "base_url": _PRIVATE_URL, "error": "HTTP_STATUS:502"}],
        "note": _PRIVATE_URL,
    }


@pytest.fixture
def real_app(monkeypatch):
    pytest.importorskip("fastapi")
    import serve
    import szl_llm_registry as reg

    for name in _SOVEREIGN_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", _DEAD_URL)

    def simulate_mesh(reachable: bool) -> None:
        monkeypatch.setattr(reg, "sovereign_mesh_matrix",
                            lambda timeout=None: _mesh(reachable))
        monkeypatch.setattr(reg, "_sovereign_env_present", lambda: reachable)
        monkeypatch.setattr(reg, "_sovereign_env_used",
                            lambda: "A11OY_BRAIN_URL" if reachable else None)
        monkeypatch.setattr(reg, "_sovereign_model_slug", lambda: _MODEL_TAG)

    return serve.app, simulate_mesh


def _checker():
    path = Path(__file__).resolve().parents[1] / ".github/scripts/frontier_index_honesty_check.py"
    spec = importlib.util.spec_from_file_location("fi_honesty_checker_pin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_router_status_resolves_to_unknown_in_catalog_and_checker(real_app) -> None:
    """Pins a disclosed catalog change against the REAL route. Unprobed /llm/router/status
    exposes only the sovereign sub-node label UNKNOWN, so the catalog and the independent CI
    checker both resolve it to UNKNOWN (a downgrade from the MODELED it fell through to)."""
    from fastapi.testclient import TestClient

    app, simulate_mesh = real_app
    for reachable in (False, True):
        simulate_mesh(reachable)
        with TestClient(app) as client:
            response = client.get("/api/a11oy/v1/llm/router/status")
        assert response.status_code == 200
        payload = response.json()
        (node,) = payload["local_nodes"]
        assert node["state"] == "UNPROBED" and node["label"] == "UNKNOWN"
        assert _extract_label(payload) == "UNKNOWN"
        assert _checker().independent_label(payload) == "UNKNOWN"


def test_real_sovereign_catalog_entry_reports_the_node_health_label(real_app) -> None:
    """Pins the second disclosed catalog change. Node unreachable: the sovereign entry is
    UNAVAILABLE, unchanged from main. Node reachable but unverified (the live case): it
    reports the node's own label, UNKNOWN from /llm/sovereign/health, where main fell through
    to ROADMAP from /energy/sovereign. Neither case claims LIVE or MEASURED."""
    import szl_frontier_index as fi

    app, simulate_mesh = real_app
    (surface,) = [s for s in fi._surface_registry() if s.get("id") == "sovereign"]
    get_paths = fi._registered_get_paths(app, "a11oy")

    simulate_mesh(False)
    down = fi._classify_surface(app, surface, get_paths, "a11oy")
    assert down["label"] == "UNAVAILABLE", down

    simulate_mesh(True)
    live = fi._classify_surface(app, surface, get_paths, "a11oy")
    assert live["label"] == "UNKNOWN", live
    assert live["endpoint"] == "/api/a11oy/v1/llm/sovereign/health", live
    for entry in (down, live):
        assert entry["label"] not in {"LIVE", "MEASURED", "PROVEN"}
