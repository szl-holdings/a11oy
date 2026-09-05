# SPDX-License-Identifier: Apache-2.0
from pathlib import Path


def test_landing_nav_uses_real_touch_target_height() -> None:
    html = Path("a11oy_landing.html").read_text(encoding="utf-8")
    rule = html.split(".nav nav a{", 1)[1].split("}", 1)[0]
    assert "display:inline-flex" in rule
    assert "align-items:center" in rule
    assert "justify-content:center" in rule
    assert "min-height:48px" in rule


def test_compact_navigation_covers_tablet_and_small_desktop() -> None:
    html = Path("a11oy_landing.html").read_text(encoding="utf-8")
    assert "@media(max-width:1100px)" in html
    assert "@media(min-width:1101px){.nav-cta-short{display:none}}" in html
    nav_styles = html.split("/* ---- nav ---- */", 1)[1].split("/* ---- origin", 1)[0]
    assert "@media(max-width:680px)" not in nav_styles
    assert "@media(min-width:681px){.nav-cta-short{display:none}}" not in html


def test_phone_hero_ctas_use_durable_product_css_not_patch_artifacts() -> None:
    html = Path("a11oy_landing.html").read_text(encoding="utf-8")
    flow = Path("console/assets/szl-flow.css").read_text(encoding="utf-8")
    assert 'href="/assets/szl-flow.css"' in html
    assert '@media(max-width:480px){html[data-szl-shell-owner="homepage"] .cta-row .btn{min-height:44px}}' in flow
    assert not Path("ops/patches/mobile-cta-hit-area-44px.patch").exists()
    assert not Path("ops/patches/README-mobile-cta-hit-area.md").exists()
