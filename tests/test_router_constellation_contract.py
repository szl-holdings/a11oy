# SPDX-License-Identifier: Apache-2.0
"""Offline contract tests for the router constellation and mobile front door.

These checks deliberately use no browser, renderer, endpoint, or network. They
lock the honesty/accessibility contracts that are easy to regress in a visual
surface, while the PR verification pass supplies real desktop/mobile screenshots.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "console" / "static" / "viz" / "router"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_router_has_render_safe_accessible_fallback():
    html = source(ROUTER / "index.html")
    css = source(ROUTER / "style.css")
    app = source(ROUTER / "app.js")

    assert 'id="sceneFallback"' in html
    assert 'role="status"' in html and 'aria-live="polite"' in html
    assert "body.scene-ready .scene-fallback" in css
    assert "showRenderFallback" in app
    assert "WebGPU and WebGL2 are unavailable" in app
    assert "no blank canvas is shown" in app


def test_status_requires_validated_endpoint_data_and_never_calls_it_qps():
    html = source(ROUTER / "index.html")
    app = source(ROUTER / "app.js")

    assert "normalizeStats(await response.json())" in app
    assert "payload.mode !== 'live'" in app
    assert "routes.length !== payload.routes.length" in app
    assert "router stats signal does not equal route total" in app
    assert "stats.source !== 'szl_brain.TIERS'" in app
    assert "ENDPOINT · RESPONDING" in app
    assert "catalog pulse · not QPS" in app
    assert "MODELED decision signal" in app
    assert "response age, not model age" in app
    assert 'id="qps"' not in html
    assert "served / poll" not in html


def test_unknown_endpoint_model_is_not_mapped_to_an_unrelated_registry_node():
    app = source(ROUTER / "app.js")

    assert "const exactModel" in app
    assert "if(exactModel) segments.push" in app
    assert "Unknown endpoint" in app
    assert not re.search(r"find\([^\n]+\.tier\s*===\s*route\.tier", app)


def test_model_and_tier_labels_are_persistent_and_keyboard_operable():
    html = source(ROUTER / "index.html")
    css = source(ROUTER / "style.css")
    app = source(ROUTER / "app.js")

    assert 'id="labelLayer"' in html and 'id="tierRail"' in html
    assert "TIERS.forEach" in app and "modelMeshes.forEach" in app
    assert "button.type='button'" in app
    assert "addEventListener('focus'" in app
    assert "addEventListener('click'" in app
    assert ".node-label" in css and ".tier-chip" in css


def test_constellation_is_high_contrast_and_honors_reduced_motion():
    css = source(ROUTER / "style.css")
    app = source(ROUTER / "app.js")

    assert "--text:#f7fbff" in css
    assert "--bg:#06101d" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert "if(!SZL_REDUCED) scene.rotation.y" in app
    assert "controls.enableDamping=!SZL_REDUCED" in app


def test_mobile_nav_uses_a_bounded_short_cta_without_hiding_overflow_as_the_fix():
    landing = source(ROOT / "a11oy_landing.html")

    assert '@media(max-width:680px)' in landing
    assert ".nav .wrap{height:64px;padding-inline:14px;gap:10px}" in landing
    assert ".nav nav{margin-left:0;flex:0 0 auto;flex-wrap:nowrap;gap:0}" in landing
    assert ".nav nav .btn{padding:9px 12px;font-size:12px;max-width:154px}" in landing
    assert 'class="nav-cta-short"' in landing
    assert '>Command center</span> →' in landing
    assert 'aria-label="Open the command center"' in landing
