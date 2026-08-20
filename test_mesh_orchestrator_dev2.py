# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_mesh_orchestrator_dev2 — Wave-P Dev2 self-tests for the live cross-node mesh.

Doctrine-critical properties proved here WITHOUT a live fleet (the probes are mocked so the
state machine + honesty spine are exercised deterministically). Covers both the backend
(szl_mesh_orchestrator) and the wiring/honesty contract of static/3d/surfaces/mesh.js:

  * the per-node state machine is honest: LIVE (models 2xx + live meter), DEGRADED (models up,
    no live meter), OFFLINE (models unreachable) — reachability + watts NEVER fabricated
  * cheapest-live-watt routing picks the lowest MEASURED-watt LIVE node (basis
    `cheapest-measured-watt`); honest round-robin `heuristic-fallback` when no meter is live;
    honest `none` when no reachable node hosts the model — advisory, Λ ≤ 0.97
  * the quorum view is CONJECTURE 2, never claims proven consensus, never fakes a witness live
  * register() is additive + dual-registers /api/{ns}/v1/mesh/* AND /v1/mesh/*
  * the mesh surface module follows the szl3d default-export contract, wires all three real
    endpoints via ctx.live.poll, carries the honesty labels, and is 0 runtime CDN
  * the surface is registered in BOTH manifests (python + html) in lockstep, LAST
  * PURPLE is BANNED in the authored surface (no `purple`/`magenta`/`#ff00ff` tokens)
"""
import szl_mesh_orchestrator as m
import szl3d_holographic as holo

BASE = holo._base_dir()
SURF = BASE / "surfaces" / "mesh.js"


def _src() -> str:
    return SURF.read_text(encoding="utf-8")


# ---- backend: module self-test (the state machine + routing + quorum) -------
def test_module_selftest_passes():
    out = m._selftest()
    assert out["live_node"] == "LIVE"
    assert out["degraded_node"] == "DEGRADED"
    assert out["offline_node"] == "OFFLINE"
    assert out["route_cheapest"] == "betterwithage"
    assert out["route_fallback"] == "heuristic-fallback"
    assert out["route_none"] == "none"
    assert out["quorum_conjecture"] == "Conjecture 2"


# ---- backend: honest state machine (mocked probes) --------------------------
def _patch(monkeypatch, models_ret, meter_ret):
    monkeypatch.setattr(m, "_probe_models", lambda node: models_ret)
    monkeypatch.setattr(m, "_probe_meter", lambda node: meter_ret)


def test_node_live_uses_measured_watts(monkeypatch):
    _patch(monkeypatch,
           {"reachable": True, "models": ["qwen2.5:7b"], "http_status": 200,
            "api_style": "ollama", "offline": False},
           {"watts": 14.2, "joules_label": "measured", "http_status": 200,
            "blocked": False, "reason": "live"})
    n = m.probe_node(m._NODES[0])
    assert n["state"] == "LIVE" and n["watts"] == 14.2 and n["joules_label"] == "measured"
    assert n["reachable"] is True and n["model_count"] == 1


def test_node_degraded_never_fabricates_watts(monkeypatch):
    _patch(monkeypatch,
           {"reachable": True, "models": ["llama3.1:8b"], "http_status": 200,
            "api_style": "ollama", "offline": False},
           {"watts": None, "joules_label": "sample", "http_status": 403,
            "blocked": True, "reason": "blocked"})
    n = m.probe_node(m._NODES[0])
    assert n["state"] == "DEGRADED"
    assert n["watts"] is None and n["joules_label"] == "sample"
    assert n["meter_blocked"] is True


def test_node_offline_on_cloudflare_530(monkeypatch):
    _patch(monkeypatch,
           {"reachable": False, "models": [], "http_status": 530,
            "api_style": None, "offline": True},
           {"watts": None, "joules_label": "sample", "http_status": None,
            "blocked": False, "reason": "x"})
    n = m.probe_node(m._NODES[0])
    assert n["state"] == "OFFLINE" and n["reachable"] is False and n["models"] == []


def test_mesh_status_data_label_measured_only_when_live(monkeypatch):
    _patch(monkeypatch,
           {"reachable": True, "models": ["m"], "http_status": 200,
            "api_style": "ollama", "offline": False},
           {"watts": 10.0, "joules_label": "measured", "http_status": 200,
            "blocked": False, "reason": "live"})
    st = m.mesh_status()
    assert st["data_label"] == "MEASURED"
    assert st["mesh_state"] == "LIVE"
    assert st["counts"]["live"] == len(m._NODES)


def test_mesh_status_structural_when_no_meter(monkeypatch):
    _patch(monkeypatch,
           {"reachable": True, "models": ["m"], "http_status": 200,
            "api_style": "ollama", "offline": False},
           {"watts": None, "joules_label": "sample", "http_status": 403,
            "blocked": True, "reason": "blocked"})
    st = m.mesh_status()
    assert st["data_label"] == "STRUCTURAL-ONLY"
    assert st["mesh_state"] == "DEGRADED"


# ---- backend: routing policy is honest + advisory ---------------------------
def test_route_cheapest_measured_watt(monkeypatch):
    fake = {"nodes": [
        {"name": "omen", "label": "omen", "state": "LIVE", "reachable": True,
         "models": ["qwen2.5:7b"], "watts": 20.0, "joules_label": "measured"},
        {"name": "betterwithage", "label": "bwa", "state": "LIVE", "reachable": True,
         "models": ["qwen2.5:7b"], "watts": 7.5, "joules_label": "measured"},
    ]}
    monkeypatch.setattr(m, "mesh_status", lambda: fake)
    r = m.mesh_route("qwen2.5:7b")
    assert r["route"] == "betterwithage"
    assert r["basis"] == "cheapest-measured-watt"
    assert r["data_label"] == "MEASURED"
    assert r["advisory"] is True
    assert r["doctrine"]["trust_ceiling"] <= 0.97


def test_route_heuristic_fallback_when_no_meter(monkeypatch):
    fake = {"nodes": [
        {"name": "omen", "label": "omen", "state": "DEGRADED", "reachable": True,
         "models": ["m"], "watts": None, "joules_label": "sample"},
        {"name": "betterwithage", "label": "bwa", "state": "OFFLINE", "reachable": False,
         "models": [], "watts": None, "joules_label": "sample"},
    ]}
    monkeypatch.setattr(m, "mesh_status", lambda: fake)
    r = m.mesh_route("m")
    assert r["route"] == "omen"
    assert r["basis"] == "heuristic-fallback"
    assert r["data_label"] == "MODELED"


def test_route_none_when_no_host(monkeypatch):
    fake = {"nodes": [
        {"name": "omen", "label": "omen", "state": "OFFLINE", "reachable": False,
         "models": [], "watts": None, "joules_label": "sample"},
    ]}
    monkeypatch.setattr(m, "mesh_status", lambda: fake)
    r = m.mesh_route("something")
    assert r["route"] is None and r["basis"] == "none"


# ---- backend: quorum is CONJECTURE 2, never proven --------------------------
def test_quorum_is_conjecture_2_never_proven(monkeypatch):
    fake = {"nodes": [
        {"name": "omen", "state": "LIVE", "reachable": True, "note": "x"},
        {"name": "betterwithage", "state": "LIVE", "reachable": True, "note": "y"},
    ]}
    monkeypatch.setattr(m, "mesh_status", lambda: fake)
    q = m.mesh_quorum()
    assert q["conjecture"] == "Conjecture 2"
    assert q["quorum_proven"] is False
    assert q["data_label"] == "STRUCTURAL-ONLY"
    assert q["threshold"] == 3 and q["witnesses_total"] == 4
    gov = [w for w in q["witnesses"] if w["kind"] == "governance"][0]
    assert gov["reachable"] is False


# ---- backend: register is additive + dual-registers -------------------------
def test_register_is_additive_and_dual():
    class _FakeApp:
        def __init__(self):
            self.routes = []

            class _R:
                def __init__(self, outer): self.outer = outer
                def add_route(self, path, fn, **kw): self.outer.routes.append(path)
            self.router = _R(self)

        def add_api_route(self, path, fn, **kw):
            self.routes.append(path)

    app = _FakeApp()
    out = m.register(app, ns="a11oy")
    assert out["ok"] is True
    assert any(r == "/api/a11oy/v1/mesh/status" for r in app.routes)
    assert any(r == "/api/a11oy/v1/mesh/route" for r in app.routes)
    assert any(r == "/api/a11oy/v1/mesh/quorum" for r in app.routes)
    assert any(r == "/v1/mesh/status" for r in app.routes)


def test_info_exposes_three_endpoints():
    i = m.info()
    for suffix in ("/mesh/status", "/mesh/route", "/mesh/quorum"):
        assert any(suffix in e for e in i["endpoints"])
    assert i["doctrine"]["bft"] == "Conjecture 2"
    assert i["doctrine"]["locked_proven"] == 8


# ---- surface: szl3d default-export contract + live wiring -------------------
def test_surface_file_exists():
    assert SURF.is_file(), "mesh surface module missing"


def test_surface_default_export_contract():
    s = _src()
    assert "export default" in s
    assert "function mount" in s and "function unmount" in s
    assert 'const ID = "mesh"' in s, "slot id must stay 'mesh' (shell contract)"
    assert "endpoints: [EP_STATUS, EP_ROUTE, EP_QUORUM]" in s
    assert 'import { createShowcase } from "./_showcase.js"' in s


def test_surface_wires_all_three_real_endpoints():
    s = _src()
    assert "/api/a11oy/v1/mesh/status" in s
    assert "/api/a11oy/v1/mesh/route" in s
    assert "/api/a11oy/v1/mesh/quorum" in s
    assert s.count("ctx.live.poll(") >= 3


def test_surface_reads_server_values_not_fabricated():
    s = _src()
    for field in ("json.mesh_state", "n.state", "n.watts", "n.joules_label",
                  "json.route", "json.basis", "json.witnesses_reachable"):
        assert field in s, f"surface must read live field {field} from the endpoint"
    assert "NO-LIVE-DATA" in s
    assert "awaiting live" in s


def test_surface_honesty_labels_and_conjecture():
    s = _src()
    assert "STRUCTURAL-ONLY" in s
    assert "MEASURED" in s
    assert "Conjecture 1" in s and "Conjecture 2" in s
    assert "ctx.label" in s or "_ctx.label" in s
    assert "data_label" in s
    assert ".legend(" in s
    # glow tracks watts ONLY when the reading is MEASURED (never fabricated)
    assert 'joules_label === "measured"' in s


def test_surface_zero_runtime_cdn():
    s = _src()
    for pat in holo._CDN_PATTERNS:
        assert not pat.search(s), f"runtime-CDN reference (0-CDN doctrine) matched {pat.pattern}"


def test_surface_no_purple_doctrine():
    s = _src().lower()
    for banned in ("purple", "magenta", "#ff00ff", "0xff00ff", "fuchsia", "indigo"):
        assert banned not in s, f"PURPLE BANNED — found forbidden token {banned!r}"


# ---- both manifests carry `mesh` in lockstep, LAST --------------------------
def test_mesh_in_both_manifests_lockstep_last():
    ids_py = [s["id"] for s in holo.SURFACES]
    assert ids_py[-1] == "mesh", "mesh must be the LAST python-manifest surface"
    html = (BASE / "holographic.html").read_text(encoding="utf-8")
    import re
    ids_html = re.findall(r"\{\s*id\s*:\s*\"([A-Za-z0-9_-]+)\"", html)
    assert ids_html[-1] == "mesh", "mesh must be the LAST html-manifest surface"
    assert ids_py == ids_html, "python + html manifests must be identical, in order"


def test_mesh_surface_stub_follows_contract():
    # the shell requires each surface module id to have a matching static file
    assert (BASE / "surfaces" / "mesh.js").is_file()


if __name__ == "__main__":
    import sys
    # lightweight monkeypatch shim so this runs without pytest
    class _MP:
        def __init__(self): self._undo = []
        def setattr(self, obj, name, val): self._undo.append((obj, name, getattr(obj, name))); setattr(obj, name, val)
        def undo(self):
            for obj, name, val in reversed(self._undo): setattr(obj, name, val)
            self._undo = []
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for name, fn in fns:
        n_args = fn.__code__.co_argcount
        if n_args == 1:
            mp = _MP()
            try:
                fn(mp)
            finally:
                mp.undo()
        else:
            fn()
        passed += 1
        print(f"  ok  {name}")
    print(f"test_mesh_orchestrator_dev2: ALL OK ({passed} checks)")
    sys.exit(0)
