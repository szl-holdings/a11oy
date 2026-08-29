# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Regression guards for the unfinished Cursor landing-hamburger honesty work.

Console ENERGY/joules and /warhacker fragment stay on current main. Do not
replay the stale #1389 serve.py/console.html trees over later honesty contracts.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT_DOOR = ROOT / "a11oy_landing.html"
MARKETING = ROOT / "pages" / "landing.html"
NAV = ROOT / "a11oy_nav_wireup.py"


def test_front_door_hamburger_is_44px_and_opens_hidden_links() -> None:
    html = FRONT_DOOR.read_text(encoding="utf-8")
    assert 'id="menu-toggle"' in html
    assert 'class="menu-toggle"' in html
    assert "min-width:44px" in html and "min-height:44px" in html
    assert "header.nav.nav-open nav" in html
    assert 'aria-controls="site-nav"' in html
    assert ".nav nav a.hide-sm,.nav nav a:not(.btn){display:none}" in html
    assert "header.nav.nav-open nav a.hide-sm" in html
    assert "setOpen(!header.classList.contains" in html


def test_marketing_landing_ds_nav_has_hamburger_under_760px() -> None:
    html = MARKETING.read_text(encoding="utf-8")
    assert 'id="menu-toggle"' in html
    assert 'class="menu-toggle"' in html
    assert "@media (max-width:760px)" in html
    assert ".ds-topbar.nav-open .ds-nav{display:flex;}" in html
    assert ".ds-topbar.nav-open .ds-nav a{display:flex;align-items:center;min-height:44px" in html
    assert 'aria-controls="ds-nav"' in html
    # The old hide-and-forget rule must not remain as the only mobile nav.
    assert "@media (max-width:760px){.ds-nav{display:none;}}" not in html


def test_hero_receipts_share_ledger_source_and_label_historical() -> None:
    html = FRONT_DOOR.read_text(encoding="utf-8")
    assert "function setHeroReceiptsFromLedger" in html
    assert "SAMPLE/historical" in html
    assert "setHeroReceiptsFromLedger(d)" in html
    assert 'id="hs-receipts-hist"' in html
    # Hero no longer copies lake/overview totals unlabeled into hs-receipts.
    assert (
        '$("hs-receipts").textContent    = (num(receipts)===null) ? "—"           : receipts.toLocaleString();'
        not in html
    )


def test_public_page_aliases_remain_registered() -> None:
    src = NAV.read_text(encoding="utf-8")
    for path in ("/mesh", "/evidence", "/arena", "/router"):
        assert path in src


def test_landing_router_health_is_stale_not_measured() -> None:
    html = FRONT_DOOR.read_text(encoding="utf-8")
    assert "STALE NOT_MEASURED" in html
    assert "snapshot 2026-07-11" in html
    assert "live, drift-checked" not in html
    assert "LLM-Router Live scene" not in html
    assert "LLM-Router Live · 3D" not in html


def test_pr_does_not_skin_nvidia_adapters_as_nim() -> None:
    landing = FRONT_DOOR.read_text(encoding="utf-8")
    marketing = MARKETING.read_text(encoding="utf-8")
    assert "nvidia-adapters" not in landing
    assert "nvidia-adapters" not in marketing
    assert "NVIDIA NIM" not in landing


