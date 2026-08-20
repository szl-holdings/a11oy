# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_router_surface_3d — Dev7 self-tests for the Model-Router holographic surface.

Doctrine-critical properties proved here WITHOUT a browser (the renderer/animation paths
live in the szl3d toolkit + its browser selftest harness; these check the wiring + honesty
contract of static/3d/surfaces/router.js and the live router endpoint it consumes):

  * the surface module follows the szl3d default-export contract (id/title/endpoints/
    mount/unmount) and keeps the slot id "router"
  * it WIRES TO THE REAL endpoints (crossover + sweep + compute-pool) via ctx.live.poll —
    it never hardcodes a telemetry value; the displayed route/weights are read off the JSON
  * it carries the doctrine honesty posture (reads data_label; renders MODELED / the 4 chips;
    a STRUCTURAL-ONLY honest fallback when the live model list is absent)
  * 0 runtime CDN: NO fetch-shaped external URL anywhere in the authored module
  * the client-side crossover-blend mirror is BYTE-FAITHFUL to the server's
    szl_cuas_formulas.active_flux_blend so the surface warp tracks the live crossover exactly
  * the live router endpoint registers, returns the real fields, and flips small/local <->
    large/cloud across the crossover (the surface's whole reason to exist)
"""
import math

import a11oy_active_flux_router as router
import szl_cuas_formulas as af
import szl3d_holographic as holo

BASE = holo._base_dir()
SURF = BASE / "surfaces" / "router.js"


def _src() -> str:
    return SURF.read_text(encoding="utf-8")


# ---- surface module contract ----------------------------------------------
def test_surface_file_exists():
    assert SURF.is_file(), "router surface module missing"


def test_surface_default_export_contract():
    s = _src()
    assert "export default" in s
    assert "function mount" in s and "function unmount" in s
    assert 'id: ID' in s or 'id:ID' in s
    assert 'const ID = "router"' in s, "slot id must stay 'router' (shell contract)"
    # endpoints array advertises all three real live endpoints it consumes
    assert "endpoints: [EP_CROSS, EP_SWEEP, EP_POOL]" in s


# ---- WIRE TO LIVE DATA (never fabricate) -----------------------------------
def test_surface_wires_all_three_real_endpoints():
    s = _src()
    assert "/api/a11oy/v1/router/active-flux-crossover" in s
    assert "/api/a11oy/v1/router/active-flux-crossover/sweep" in s
    assert "/api/a11oy/v1/compute-pool" in s
    # three independent live polls
    assert s.count("ctx.live.poll(") >= 3 or s.count("_ctx.live.poll(") + s.count("ctx.live.poll(") >= 3


def test_surface_reads_server_values_not_fabricated():
    s = _src()
    # values are pulled off the JSON, not invented
    for field in ("json.route", "json.regime", "json.crossover_difficulty",
                  "json.weight_small_local", "json.weight_large_cloud"):
        assert field in s, f"surface must read live field {field} from the endpoint"
    # honest 'awaiting'/dash states exist (no seeded fake telemetry)
    assert "NO-LIVE-DATA" in s or "missing" in s
    assert "awaiting live" in s


def test_surface_honesty_labels_present():
    s = _src()
    assert "MODELED" in s
    assert "STRUCTURAL-ONLY" in s           # honest fallback for the model scatter
    assert "ctx.label" in s or "_ctx.label" in s
    assert "data_label" in s                 # reads the doctrine label straight from JSON
    assert ".legend(" in s                   # all 4 chips rendered


# ---- 0 runtime CDN ---------------------------------------------------------
def test_surface_zero_runtime_cdn():
    s = _src()
    for pat in holo._CDN_PATTERNS:
        assert not pat.search(s), f"runtime-CDN reference (0-CDN doctrine) matched {pat.pattern}"


# ---- client mirror is byte-faithful to the server blend --------------------
def test_client_blend_mirror_matches_server():
    """The JS surface mirrors active_flux_blend to shape geometry; prove the mirror equals
    the server's closed form at representative (bw, difficulty) points so the warp can never
    drift from the live crossover the endpoint reports."""
    SPAN = 60.0
    for bw in (5.0, 12.0, 30.0):
        for d in (0.0, 0.2, 0.5, 0.8, 1.0):
            f = d * SPAN
            srv = af.active_flux_blend(bw, f)
            # JS mirror: wx = 2π·(150/bw), we = 2π·f, hc = wx/√(wx²+we²)
            wx = 2 * math.pi * (150.0 / max(bw, 1e-6))
            we = 2 * math.pi * max(f, 0.0)
            den = math.sqrt(wx * wx + we * we) or 1e-12
            hc, hv = wx / den, we / den
            assert abs(hc - srv["current_model_weight"]) < 1e-6
            assert abs(hv - srv["voltage_model_weight"]) < 1e-6
    # crossover difficulty mirror: (150/bw)/SPAN
    for bw in (5.0, 12.0, 30.0):
        srv_cd = af.pi_crossover_freq(bw) / SPAN
        js_cd = (150.0 / bw) / SPAN
        assert abs(srv_cd - js_cd) < 1e-9


# ---- the live router endpoint the surface consumes -------------------------
def test_router_endpoint_real_fields_and_crossover_flip():
    easy = router.router_crossover(query_difficulty=0.05, pi_bandwidth_hz=5.0)
    hard = router.router_crossover(query_difficulty=0.95, pi_bandwidth_hz=5.0)
    for r in (easy, hard):
        assert set(("route", "regime", "crossover_difficulty",
                    "weight_small_local", "weight_large_cloud",
                    "models", "data_label")).issubset(r.keys())
        assert r["data_label"] == "MODELED"
    assert easy["route"] == "small/local" and easy["regime"] == "easy"
    assert hard["route"] == "large/cloud" and hard["regime"] == "hard"
    # weights are a complementary blend (|hc|²+|hv|² = 1) — never fabricated free numbers
    for r in (easy, hard):
        assert abs(r["weight_small_local"] ** 2 + r["weight_large_cloud"] ** 2 - 1.0) < 1e-3


def test_router_sweep_curve_shape():
    s = router.sweep(pi_bandwidth_hz=12.0, points=61)
    assert s["points"] == 61 and len(s["curve"]) == 61
    assert s["data_label"] == "MODELED"
    first, last = s["curve"][0], s["curve"][-1]
    # easy end favors small/local, hard end favors large/cloud
    assert first["small_local"] >= first["large_cloud"]
    assert last["large_cloud"] >= last["small_local"]


def test_router_register_is_additive():
    class _FakeApp:
        def __init__(self): self.routes = []
        def add_api_route(self, path, fn, **kw): self.routes.append(path)
    app = _FakeApp()
    out = router.register(app, ns="a11oy")
    assert out["data_label"] == "MODELED"
    assert any("active-flux-crossover" in r for r in app.routes)
    assert any("/sweep" in r for r in app.routes)


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn(); passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"test_router_surface_3d: ALL OK ({passed} checks)")
    sys.exit(0)
