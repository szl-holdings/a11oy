# SPDX-License-Identifier: Apache-2.0
"""Mobile-first contracts for the ecosystem and Anatomy v5 surfaces.

These static checks lock the layout decisions used at 320, 375, and 768 CSS
pixels without pretending to replace browser/device testing.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ECOSYSTEM = (ROOT / "pages" / "ecosystem.html").read_text(encoding="utf-8")
ANATOMY = (ROOT / "pages" / "anatomy-v5.html").read_text(encoding="utf-8")


def test_mobile_viewport_breakpoints_keep_navigation_contained_and_cards_fluid() -> None:
    for html in (ECOSYSTEM, ANATOMY):
        assert '<meta name="viewport" content="width=device-width,initial-scale=1">' in html
        assert "@media(max-width:800px){.brand small{display:none}}" in html
        assert "@media(max-width:680px){header{position:static}" in html
        assert "nav{width:100%;margin-left:0;flex-wrap:nowrap;overflow-x:auto" in html
        assert "nav a{flex:0 0 auto}" in html
        assert "nav a:not(.primary){display:none}" not in html
        assert "@media(max-width:620px)" in html
        assert "100vw" not in html

    assert ".grid{grid-template-columns:1fr}" in ECOSYSTEM
    assert ".search{min-width:0;width:100%}" in ECOSYSTEM
    assert ".meta span{align-items:flex-start;flex-direction:column" in ECOSYSTEM
    assert ".vitals{grid-template-columns:repeat(2,minmax(0,1fr))}" in ANATOMY
    assert ".route{grid-template-columns:1fr}" in ANATOMY
    assert ".formula{grid-template-columns:1fr}" in ANATOMY


def test_touch_targets_focus_and_primary_navigation_are_accessible() -> None:
    for html in (ECOSYSTEM, ANATOMY):
        assert '<a class="skip" href="#main">Skip to content</a>' in html
        assert '<main id="main">' in html
        assert '<nav aria-label="Primary">' in html
        assert "a:focus-visible,button:focus-visible,input:focus-visible" in html
        assert "outline:2px solid var(--teal)" in html
        assert "nav a{min-height:44px;display:inline-flex;align-items:center" in html
        assert ".brand{min-height:44px;display:flex;align-items:center" in html
        assert ".tab{min-height:44px" in html
        assert "touch-action:manipulation" in html

    assert ".chip{min-height:44px" in ECOSYSTEM
    assert ".search{min-height:44px" in ECOSYSTEM
    assert ".state[href]{min-height:44px" in ECOSYSTEM
    assert ".badges a.badge{min-height:44px" in ANATOMY
    assert ".formula-tools input{min-height:44px" in ANATOMY


def test_sticky_header_and_anatomy_tabs_have_non_colliding_mobile_contract() -> None:
    assert "header{position:sticky;top:0" in ECOSYSTEM
    assert "header{position:sticky;top:0" in ANATOMY
    assert ".tabs{position:sticky;top:67px" in ANATOMY
    assert "header{position:static}header .wrap{flex-wrap:wrap;padding:11px 0 8px}" in ANATOMY
    assert "nav a{flex:0 0 auto}.tabs{top:0}" in ANATOMY
    assert "overscroll-behavior-inline:contain;scrollbar-width:thin" in ECOSYSTEM
    assert "overscroll-behavior-inline:contain;scrollbar-width:thin" in ANATOMY


def test_narrow_anatomy_panels_cannot_force_horizontal_page_overflow() -> None:
    assert ".organism>*,.nervous-grid>*,.formula>*{min-width:0}" in ANATOMY
    assert ".source{display:flex;justify-content:space-between;flex-wrap:wrap" in ANATOMY
    assert ".source span{min-width:0;overflow-wrap:anywhere}" in ANATOMY
    assert ".formula-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap" in ANATOMY
    assert ".formula-tools{align-items:stretch;flex-direction:column}" in ANATOMY
    assert ".formula-tools input{min-width:0;width:100%}" in ANATOMY


def test_category_tabs_and_endpoint_states_match_backend_semantics() -> None:
    assert 'id="tabs" role="tablist"' in ECOSYSTEM
    assert 'id="grid" role="tabpanel"' in ECOSYSTEM
    assert 'role="tab" aria-selected="${k===active}" aria-controls="grid"' in ECOSYSTEM
    assert "setAttribute('aria-labelledby','tab-'+active)" in ECOSYSTEM
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in ECOSYSTEM
    assert "amberStates=['CACHED','STALE_CACHE','SNAPSHOT','DEGRADED','MODELED','OBSERVED','AVAILABLE']" in ECOSYSTEM
    assert "displayState=evidenceStates.includes(normalized)?normalized:'UNAVAILABLE'" in ECOSYSTEM

    assert "const pulse=evidenceState(data?.labels?.pulse)" in ANATOMY
    assert "const throughput=evidenceState(data?.throughput_state)" in ANATOMY
    assert "const throughputState=evidenceState(router?.throughput_state)||'MODELED'" in ANATOMY
    assert "'modeled load':'throughput'" in ANATOMY
    assert 'class="ok"' not in ANATOMY
    assert "a successful HTTP response is not silently converted" in ANATOMY
