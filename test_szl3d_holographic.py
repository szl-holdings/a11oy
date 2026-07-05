# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_szl3d_holographic — self-tests for the shared szl3d 3D toolkit (Dev0 foundation).

These prove the doctrine-critical + contract properties the holographic surface
devs depend on, WITHOUT needing a browser (the browser-level renderer/bloom/badge checks
live in static/3d/selftest/index.html and are asserted to exist + cover those cases here):

  * the register module imports + its in-module _selftest passes (toolkit, all
    manifest surfaces, vendor libs present; path-traversal-safe; 0 runtime CDN in
    authored code) — surface counts are derived from the SURFACES manifest, never hardcoded
  * three.js r170 is vendored (both WebGL2 + WebGPU builds) with the recorded sha256s
  * the renderer factory advertises WebGPU-with-WebGL2-fallback + a bloom pipeline
  * the live poller handles 404 / degraded and drives a LIVE badge; honesty label is read
  * all 4 doctrine honesty-label chips (MEASURED/MODELED/SAMPLE/STRUCTURAL-ONLY) render
  * the holographic shell hosts a tab-switcher that lazy-loads surface modules (the 9
    estate surfaces are always present; the frontier tier adds more)
  * NO external CDN URL is fetch-shaped anywhere in our authored 3d code/HTML
  * the selftest harness declares >= 15 checks
"""
import hashlib
import re
from pathlib import Path

import szl3d_holographic as m

BASE = m._base_dir()
VENDOR = BASE / "vendor"


def _read(rel):
    return (BASE / rel).read_text(encoding="utf-8")


# ---- register module + in-module selftest ---------------------------------
def test_module_selftest_passes():
    # raises AssertionError if anything is wrong; returns None on success
    m._selftest()


# The 9 original estate surfaces — a permanent subset of the SURFACES manifest.
# The full manifest has grown (frontier tier + estate); assert against the live
# registry so the count never goes stale again.
_ESTATE_SURFACE_IDS = {
    "energy", "fabric", "pnt", "counter-uas", "governance",
    "pinn", "router", "anatomy", "estate"}


def test_info_surface_contract():
    i = m.info()
    assert i["vendor"]["three_revision"] == "r170"
    # derive from the SURFACES manifest (single source of truth) — never hardcode
    assert len(i["surfaces"]) == len(m.SURFACES)
    assert i["doctrine"]["runtime_cdn"] == 0
    assert "WebGL2" in i["doctrine"]["webgpu"] or "WebGL2" in i["doctrine"]["webgpu"].replace("-", " ")
    # the info payload must expose exactly the ids declared in the manifest ...
    assert set(s["id"] for s in i["surfaces"]) == {s["id"] for s in m.SURFACES}
    # ... and the 9 original estate surfaces must always remain present.
    assert _ESTATE_SURFACE_IDS <= set(s["id"] for s in i["surfaces"])


def test_register_is_additive_and_returns_routes():
    class _FakeApp:
        def __init__(self): self.routes = []
        def add_api_route(self, path, fn, **kw): self.routes.append(path)
    app = _FakeApp()
    out = m.register(app, ns="a11oy")
    assert out["count"] >= 3
    # derive from the SURFACES manifest so this never goes stale as surfaces grow
    assert out["surfaces"] == len(m.SURFACES)
    assert any(r == "/static/3d/{path:path}" or r == "/static/3d/{path}" for r in app.routes)
    assert "/holographic" in app.routes
    assert "/a11oy/holographic" in app.routes


# ---- path traversal safety -------------------------------------------------
def test_path_traversal_rejected():
    assert m._safe_resolve(BASE, "../serve.py") is None
    assert m._safe_resolve(BASE, "../../etc/passwd") is None
    assert m._safe_resolve(BASE, "/etc/passwd") is None
    assert m._safe_resolve(BASE, "szl3d/szl3d_boot.js") is not None


# ---- vendored three.js r170 (WebGL2 + WebGPU) with recorded hashes ---------
_EXPECTED_SHA = {
    "three/three.module.min.js": "08fd7545d13d2c7fb65ab691530a802dafefd638596501854f267d0fb13c39e7",
    "three/three.webgpu.min.js": "9d01bb1bae1badb5071d341f76c3569f6118bad126effd425a06611a9d993035",
}


def test_three_r170_both_builds_vendored_with_hashes():
    for rel, want in _EXPECTED_SHA.items():
        f = VENDOR / rel
        assert f.is_file(), f"vendored lib missing: {rel}"
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        assert got == want, f"hash drift for {rel}: {got} != {want}"
    # the WebGL2 build self-identifies as r170
    assert 'const t="170"' in _read("vendor/three/three.module.min.js")


def test_postprocessing_addons_present():
    for f in ("EffectComposer", "RenderPass", "ShaderPass", "MaskPass",
              "Pass", "UnrealBloomPass", "OutputPass"):
        assert (VENDOR / "three/addons/postprocessing" / f"{f}.js").is_file(), f"missing {f}"
    assert (VENDOR / "three/addons/controls/OrbitControls.js").is_file()


def test_vendor_manifest_lists_hashes():
    man = _read("vendor/VENDOR_MANIFEST.md")
    for want in _EXPECTED_SHA.values():
        assert want in man, "manifest missing a recorded sha256"
    # the deck.gl / Cesium vendoring TODOs are documented for downstream devs
    assert "deck.gl" in man and "cesium" in man.lower()


# ---- szl3d_boot: WebGPU->WebGL2 fallback + bloom ---------------------------
def test_boot_factory_webgpu_then_webgl2_fallback():
    src = _read("szl3d/szl3d_boot.js")
    assert "export async function boot" in src
    assert "navigator.gpu" in src and "requestAdapter" in src
    assert 'import("three/webgpu")' in src or "three/webgpu" in src
    assert "WebGLRenderer" in src                  # the fallback path
    assert "_szlBackend" in src and "webgl2" in src and "webgpu" in src
    assert "forceWebGL" in src                     # selftest can force the fallback
    assert "addEventListener" in src and "resize" in src   # auto-resize


def test_boot_factory_bloom_pipeline():
    src = _read("szl3d/szl3d_boot.js")
    assert "EffectComposer" in src and "UnrealBloomPass" in src and "RenderPass" in src
    assert "setBloom" in src and "hasBloom" in src


# ---- szl3d_live: poll + 404/degraded + badge + honesty label ---------------
def test_live_poll_degraded_and_404_handling():
    src = _read("szl3d/szl3d_live.js")
    assert "export function poll" in src
    assert "404" in src and "MISSING" in src
    assert "degraded" in src and "DEGRADED" in src
    assert "createBadge" in src and "last fetch" in src and "NO-LIVE-DATA" in src


def test_live_reads_honesty_label_fields():
    src = _read("szl3d/szl3d_live.js")
    assert "joules_label" in src and "data_label" in src and "label" in src
    assert "readHonestyLabel" in src


# ---- szl3d_label: all 4 doctrine chips + billboard -------------------------
def test_label_all_four_honesty_states():
    src = _read("szl3d/szl3d_label.js")
    for k in ("MEASURED", "MODELED", "SAMPLE", "STRUCTURAL-ONLY"):
        assert k in src, f"missing honesty state {k}"
    assert "export function chip" in src
    assert "export function billboard" in src        # 3D billboard sprite path
    assert "Sprite" in src and "CanvasTexture" in src


# ---- holographic shell: 9-slot lazy tab-switcher ---------------------------
def test_shell_has_nine_lazy_surface_slots():
    html = _read("holographic.html")
    for sid in ("energy", "fabric", "pnt", "counter-uas", "governance",
                "pinn", "router", "anatomy", "estate"):
        assert f"/static/3d/surfaces/{sid}.js" in html, f"shell missing slot {sid}"
    assert 'role="tablist"' in html
    assert "import(" in html                          # lazy per-tab module import
    assert "__SZL3D_SHELL__" in html                  # headless test hook


def test_shell_uses_local_importmap_not_cdn():
    html = _read("holographic.html")
    assert '"three": "/static/3d/vendor/three/three.module.min.js"' in html
    assert '"three/webgpu": "/static/3d/vendor/three/three.webgpu.min.js"' in html
    assert '"three/addons/": "/static/3d/vendor/three/addons/"' in html


def test_all_nine_surface_stubs_follow_contract():
    # Every surface (including energy, now a standalone fully-wired showcase)
    # follows the same contract: ES-module default export, mount/unmount, a live
    # ctx.live.poll binding to a real endpoint, and the honest STRUCTURAL-ONLY
    # placeholder label for off-box / no-live-data states.
    for sid in ("energy", "fabric", "pnt", "counter-uas", "governance",
                "pinn", "router", "anatomy", "estate"):
        src = _read(f"surfaces/{sid}.js")
        assert "export default" in src
        assert "function mount" in src and "function unmount" in src
        assert "ctx.live.poll" in src                 # wired to a real endpoint
        assert "STRUCTURAL-ONLY" in src               # honest placeholder label


# ---- doctrine: 0 runtime CDN in authored code ------------------------------
def test_no_runtime_cdn_in_authored_code():
    violations = list(m.no_cdn_violations(BASE))
    assert not violations, "runtime-CDN reference in authored 3d code:\n" + "\n".join(violations)


# ---- the browser selftest harness exists + declares >= 15 checks -----------
def test_selftest_harness_declares_at_least_15_checks():
    h = BASE / "selftest" / "index.html"
    assert h.is_file(), "selftest harness missing"
    txt = h.read_text(encoding="utf-8")
    # each browser check is registered via check("...") — count them
    n = len(re.findall(r"\bcheck\(\s*['\"]", txt))
    assert n >= 15, f"selftest harness declares only {n} checks (need >= 15)"
