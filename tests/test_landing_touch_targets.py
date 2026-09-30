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


def test_phone_hero_ctas_preserve_full_mobile_target_contract() -> None:
    html = Path("a11oy_landing.html").read_text(encoding="utf-8")
    flow = Path("console/assets/szl-flow.css").read_text(encoding="utf-8")
    inline_contract = (
        ".cta-row .btn{width:100%;min-height:52px;border-radius:6px;"
        "white-space:normal;text-align:center}"
    )
    size_rule = (
        '@media(max-width:480px){'
        'html[data-szl-shell-owner="homepage"] .cta-row .btn{min-height:52px}'
        '}'
    )
    assert 'href="/assets/szl-flow.css"' in html
    assert inline_contract in html
    assert size_rule in flow
    assert "52px" in flow and "inside the viewport" in flow
    assert 'html[data-szl-shell-owner="homepage"] .cta-row .btn{min-height:45px}' not in flow
    assert not Path("ops/patches/mobile-cta-hit-area-44px.patch").exists()
    assert not Path("ops/patches/README-mobile-cta-hit-area.md").exists()
    assert not Path(".github/workflows/_materialize_mobile_hero_cta_hit_area_once.yml").exists()
    assert not Path(".github/workflows/_reconcile_phone_fold_cta_once.yml").exists()


def test_short_phone_first_fold_compacts_geometry_not_control_size() -> None:
    flow = Path("console/assets/szl-flow.css").read_text(encoding="utf-8")
    start = flow.index("@media(max-width:380px) and (max-height:820px)")
    compact = flow[start:]
    owner = (
        'html[data-szl-shell-owner="homepage"]'
        '[data-szl-public-experience-v3="true"]'
    )

    assert f"{owner} .hero .wrap{{padding-top:20px!important}}" in compact
    assert f"{owner} .hero .vision-kicker{{margin-bottom:10px!important}}" in compact
    assert f"{owner} .hero .eyebrow{{margin-bottom:14px!important}}" in compact
    assert f"{owner} .hero p.lede{{margin-bottom:18px!important}}" in compact
    assert "intrinsically 46px" in flow
    assert "below the first fold" in flow

    # The measured failure was viewport clipping (43.17 visible pixels), not an
    # intrinsically undersized button. The short-phone contract must not shrink,
    # transform, zoom, or hide the CTA itself to manufacture a green result.
    assert ".cta-row .btn{" not in compact
    assert "transform:" not in compact
    assert "zoom:" not in compact
    assert "display:none" not in compact


def test_evidence_links_are_real_targets_without_hiding_the_source() -> None:
    html = Path("a11oy_landing.html").read_text(encoding="utf-8")
    flow = Path("console/assets/szl-flow.css").read_text(encoding="utf-8")
    selector = 'html[data-szl-shell-owner="homepage"] .stat-note a{'
    assert flow.count(selector) == 1
    rule = flow.split(selector, 1)[1].split("}", 1)[0]
    for declaration in (
        "display:inline-flex",
        "align-items:center",
        "justify-content:center",
        "min-width:48px",
        "min-height:48px",
        "vertical-align:middle",
    ):
        assert declaration in rule
    for forbidden in (
        "display:none", "visibility:hidden", "pointer-events:none",
        "position:absolute", "transform:", "zoom:",
    ):
        assert forbidden not in rule
    assert 'href="/assets/szl-flow.css"' in html
    assert 'class="stat-note"' in html
    assert (
        'href="https://github.com/szl-holdings/platform/blob/main/docs/OVERCLAIM_LEDGER.md">open ledger</a>'
        in html
    )
