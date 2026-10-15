# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Regression guards for the 2026-08-28 live-audit + ATELIER honesty fixes.

  1. Landing hamburger at mobile breakpoints (44px targets).
  2. Console ENERGY uses paired operator aggregates with explicit source labels.
  3. Hero receipts cite the same SAMPLE ledger source as the runtime card.
  4. /warhacker 307 Location keeps the #arena fragment.
  5. Public aliases /mesh /evidence /arena /router remain registered.
  6. Landing router health is STALE NOT_MEASURED · snapshot 2026-07-11.
  7. Ask & Act / Governed Decision: HTML nav, GDW UNAVAILABLE, EXECUTION ROADMAP.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONT_DOOR = ROOT / "a11oy_landing.html"
MARKETING = ROOT / "pages" / "landing.html"
CONSOLE = ROOT / "pages" / "console.html"
SERVE = ROOT / "serve.py"
NAV = ROOT / "a11oy_nav_wireup.py"


def test_front_door_hamburger_is_44px_and_opens_hidden_links() -> None:
    html = FRONT_DOOR.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/assets/a11oy-homepage.css?v=dab2353006c8" id="szl-homepage-shell" />' in html
    css = (ROOT / "console/assets/a11oy-homepage.css").read_text(encoding="utf-8")
    compact = "".join(css.split())
    owner = 'html[data-szl-shell-owner="homepage"]'
    assert 'id="menu-toggle"' in html
    assert 'class="menu-toggle"' in html
    toggle = compact.split(f"{owner}.menu-toggle{{", 1)[1].split("}", 1)[0]
    assert "width:48px" in toggle and "min-height:48px" in toggle
    assert 'aria-controls="site-nav"' in html
    # The links remain available without JavaScript; only a ready controller
    # may collapse the mobile navigation and its existing toggle opens it.
    assert f'{owner}[data-szl-menu-ready="true"].navnav{{display:none;}}' in compact
    assert f'{owner}[data-szl-menu-ready="true"]header.nav.nav-opennav{{display:grid;}}' in compact
    assert 'document.documentElement.dataset.szlMenuReady="true"' in html
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


def test_console_energy_requires_source_labels_and_a_paired_token_window() -> None:
    # The current operator has a verified NVML-window attribution contract. The
    # former permanent-ROADMAP assertion predates that API. Browser execution of
    # these branches (including zero, missing, and sample data) is covered by
    # scripts/test_console_evidence.cjs without contacting an operator.
    html = CONSOLE.read_text(encoding="utf-8")
    helper = html.split("window._a11oyEnergyReading=function(reading)", 1)[1].split(
        "// ===== VISUAL HELPERS", 1
    )[0]
    assert "d.joules_measured_label==='MEASURED'" in helper
    assert "d.stub_mode===false" in helper
    assert "d.measured_token_joules/d.measured_tokens" in helper
    assert "d.joules_sample_label==='SAMPLE'" in helper
    assert "{label:'UNAVAILABLE',value:null}" in helper
    assert "window._a11oyEnergyReading(_eh)" in html
    assert "API+'/v1/energy/operator/status'" in html
    assert "_eh.measured_token_joules.toFixed" not in html
    assert "JOULES SAMPLE" in html


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


def test_warhacker_redirect_preserves_arena_fragment() -> None:
    src = SERVE.read_text(encoding="utf-8")
    assert 'url="/console#arena"' in src
    assert "async def warhacker_page" in src
    war = src.split("async def warhacker_page", 1)[1].split("async def ", 1)[0]
    assert "/console#arena" in war
    assert 'url="/console"' not in war


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


def test_ask_and_governed_decision_are_html_nav_roadmap() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    last_ask = html.rfind("V.ask={")
    last_decision = html.rfind("V.decision={")
    assert last_ask != -1 and last_decision != -1
    ask_chunk = html[last_ask : last_ask + 1600]
    dec_chunk = html[last_decision : last_decision + 1600]
    for chunk in (ask_chunk, dec_chunk):
        assert "GDW UNAVAILABLE" in chunk
        assert "EXECUTION ROADMAP" in chunk
        assert "_gdwDraftPlane" in chunk
    assert "does not run" in ask_chunk
    assert "/operator/act" not in ask_chunk
    assert "governed-decision" not in dec_chunk
    assert "Approve draft (does not run)" in html
    # Leftover approve-and-run POST is neutralized.
    act = html.split("async function act_do", 1)[1].split("async function ", 1)[0]
    assert "orgPost" not in act
    assert "EXECUTION ROADMAP" in act


def test_pr_does_not_skin_nvidia_adapters_as_nim() -> None:
    landing = FRONT_DOOR.read_text(encoding="utf-8")
    marketing = MARKETING.read_text(encoding="utf-8")
    assert "nvidia-adapters" not in landing
    assert "nvidia-adapters" not in marketing
    assert "NVIDIA NIM" not in landing


def test_warhacker_http_location_includes_fragment() -> None:
    pytest.importorskip("starlette.testclient")
    import serve

    from starlette.testclient import TestClient

    client = TestClient(serve.app, follow_redirects=False)
    r = client.get("/warhacker")
    assert r.status_code == 307
    assert r.headers.get("location", "").endswith("/console#arena")
