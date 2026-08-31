# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contracts for the KANCHAY holographic command bar and Lean-8 kernel chip.

Empty-state helpers (UNKNOWN / ROADMAP / UNAVAILABLE) are in scope.
PR 1391's gold/tan restore (#0a0a0a / #c9b787 / #5fb3a3) is not.
/ecosystem is owned by PR 1392 — this suite does not pin that page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = (ROOT / "pages" / "console.html").read_text(encoding="utf-8")
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
TRUST = (ROOT / "web" / "trust.html").read_text(encoding="utf-8")
BAR_CSS = (ROOT / "static" / "shared" / "szl_command_bar.css").read_text(encoding="utf-8")
BAR_JS = (ROOT / "static" / "shared" / "szl_command_bar.js").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
INDEX = (ROOT / "console" / "index.html").read_text(encoding="utf-8")
NAV = (ROOT / "a11oy_nav_wireup.py").read_text(encoding="utf-8")
OBS = (ROOT / "pages" / "observability.html").read_text(encoding="utf-8")


def _root_blocks(html: str) -> list[str]:
    return re.findall(r":root\{[^}]+\}", html)


def test_last_console_root_is_kanchay_not_tan_restore() -> None:
    last = _root_blocks(CONSOLE)[-1]
    assert "--gold:#d7b96b" in last
    assert "--teal:#3af4c8" in last
    assert "--ground:#080c14" in last
    assert "--proof:#3af4c8" in last
    assert "--lattice:#5b8dee" in last
    assert "#c9b787" not in last
    assert "#5fb3a3" not in last
    assert "#0a0a0a" not in last


def test_shared_bar_assets_are_kanchay_and_copied() -> None:
    assert "--void:#080c14" in BAR_CSS
    assert "--proof:#3af4c8" in BAR_CSS
    assert "--lattice:#5b8dee" in BAR_CSS
    assert "--kanchay-gold:#d7b96b" in BAR_CSS
    assert "#c9b787" not in BAR_CSS
    assert "#5fb3a3" not in BAR_CSS
    assert "szl_command_bar.js" in DOCKER
    assert "szl_command_bar.css" in DOCKER
    assert '"szl_command_bar.js": _VENDOR_JS_CT' in SERVE
    assert '"szl_command_bar.css": _VENDOR_CSS_CT' in SERVE
    lockstep_cfg = json.loads(
        (ROOT / ".github" / "copy-sync-lockstep.json").read_text(encoding="utf-8")
    )
    extra = set(lockstep_cfg.get("extra_mirror_paths") or [])
    image_only = set(lockstep_cfg.get("image_only_assets") or [])
    assert "static/shared/szl_command_bar.js" in extra
    assert "static/shared/szl_command_bar.css" in extra
    assert "static/shared/szl_command_bar.js" not in image_only
    assert "static/shared/szl_command_bar.css" not in image_only
    hf_sync = (ROOT / ".github" / "workflows" / "hf-sync.yml").read_text(encoding="utf-8")
    assert "dockerfile-path: Dockerfile" in hf_sync
    assert "/static/shared/szl_command_bar.css" in CONSOLE
    assert "/static/shared/szl_command_bar.js" in CONSOLE
    assert "data-szl-command-bar" in CONSOLE
    assert "data-szl-command-bar" in INDEX


def test_seven_module_ia_yields_over_five_group_rail() -> None:
    for group in ("Home", "Operate", "Build", "Observe", "Govern", "Research", "More"):
        assert f'["{group}"' in CONSOLE
    assert '["Prove"' not in CONSOLE
    assert '["Knowledge"' not in CONSOLE
    assert '["Models & Tools"' not in CONSOLE
    assert '["investor"' in CONSOLE


def test_public_header_is_command_and_proof_registry() -> None:
    assert "text: 'Command'" in BAR_JS
    assert "Proof registry ↗" in BAR_JS
    assert "https://a11oy.net" in BAR_JS
    assert '<a href="/console">Command</a>' in LANDING
    assert "Proof registry ↗" in LANDING
    assert 'href="https://a11oy.net"' in LANDING
    assert ">Command center</span> →" in LANDING
    assert 'aria-label="Open the command center"' in LANDING
    assert 'class="nav-cta-short"' in LANDING
    assert '<a href="/console">Command</a>' in TRUST
    assert "Proof registry ↗" in TRUST


def test_no_investor_route_stub() -> None:
    assert 'href="/investor"' not in CONSOLE
    assert 'href="/investor"' not in LANDING
    assert 'href="/investor"' not in TRUST
    assert 'href="/investor"' not in BAR_JS
    assert "go('investor')" in CONSOLE
    assert "V.investor=" in CONSOLE
    assert "/console?view=investor" in CONSOLE
    assert "/console?view=investor" in BAR_JS
    assert 'url="/console?view=investor"' in SERVE
    assert 'app.add_api_route("/investor"' in SERVE
    assert "_investor_view_redirect" in SERVE
    # Destination is V.investor (go('investor')), not the leftover overlay.
    assert 'id="inv-overlay"' in CONSOLE
    overlay_js = CONSOLE.split('id="inv-mode-js"', 1)[1].split("</script>", 1)[0]
    assert "go('investor')" in overlay_js
    assert "o.classList.toggle('open', !!open)" not in overlay_js.split("function open()")[1].split("function close()")[0]
    view = CONSOLE.split("V.investor=", 1)[1]
    assert "{F1, F4, F7, F11, F12, F18, F19, F22}" in view[:2500]
    assert "Verify a receipt" in view[:4000]
    assert "Open diligence on a11oy.net" in view[:4000]
    assert "UNAVAILABLE" in view[:4500]
    assert "if(VIEWS[view]){ go(view); return true; }" in CONSOLE


def test_console_deep_links_are_query_with_hash_fallback() -> None:
    assert "u.searchParams.set('view', view)" in CONSOLE
    assert "function szlViewFromLocation()" in CONSOLE
    assert "location.search).get('view')" in CONSOLE
    # Hash still resolves so 1392 / legacy /console#ask links keep working.
    assert "location.hash||'').replace(/^#/,'')" in CONSOLE


def test_first_fold_is_receipt_stream_and_verify_not_kernel_or_radar() -> None:
    assert "Verify on a11oy.net" in CONSOLE
    assert "Pull the kernel" in CONSOLE
    assert 'szl-below-fold" href="https://huggingface.co/SZLHOLDINGS/governed-inference-meter' in CONSOLE
    assert "grid2 szl-below-fold" in CONSOLE
    stream_at = CONSOLE.find("id=\"cc-stream\"")
    estate_at = CONSOLE.find("id=\"szl-series-a-cards\"")
    radar_at = CONSOLE.find("id=\"cc-radar\"")
    assert stream_at > 0 and estate_at > stream_at and radar_at > estate_at


def test_empty_states_and_public_hides() -> None:
    assert "function emptyUnknown(kind, detail)" in CONSOLE
    assert "function emptyUnknownBlock(kind, detail)" in CONSOLE
    assert "emptyUnknown('UNKNOWN'" in CONSOLE
    assert "showing sample / snapshot" not in CONSOLE
    assert 'html:not([data-operator="1"]) [data-view="labs"]' in BAR_CSS
    assert 'html:not([data-operator="1"]) a[href*="killinchu"]' in BAR_CSS
    assert "CONTRACT GAP" in CONSOLE
    assert "op?'ONLINE · CONTRACT GAP':'ONLINE'" in CONSOLE
    assert 'operator = (request.url.query or "").find("operator=1") >= 0' in NAV
    assert 'assert "qa12-nav" not in public' in NAV
    assert 'if p == "/" or p == "/landing":' in SERVE
    assert "_is_public_front" in SERVE


def test_kernel_chip_reads_honest_locked_formula_count_not_genome_25() -> None:
    assert "locked_formula_count===8" in CONSOLE
    assert "id=\"cnt-locked\"" in CONSOLE
    assert "from /honest locked_formula_count" in CONSOLE
    assert "catalog:true" in CONSOLE
    assert "LOCKED-PROVEN (catalog)" in CONSOLE
    assert "green:true" not in CONSOLE.split("LOCKED-PROVEN (catalog)")[1][:200]
    assert "tier_counts['LOCKED-PROVEN']" not in CONSOLE
    assert "$('cnt-locked').firstChild.nodeValue=(kernel==null?'N/A':kernel)" in TRUST
    assert "tc['LOCKED-PROVEN']??'N/A')" not in TRUST.split("cnt-locked")[1][:400]
    # Identity lock owns the canonical name; no dead compatibility alias remains.
    assert "loadKernelLocked" in LANDING
    assert "loadLockedKernel" not in LANDING
    assert 'h.locked_formula_count' in LANDING
    assert 'setTiers({ locked: tc["LOCKED-PROVEN"]' not in LANDING
    assert "setCatalogNote" in LANDING
    assert "fetchJson('/api/a11oy/v1/honest'" in BAR_JS
    assert "locked_formula_count" in BAR_JS
    assert "szl-chip--lambda" in BAR_JS
    assert "CONJECTURE 1" in BAR_JS


def test_observability_primary_buttons_are_proof_teal_not_tan() -> None:
    last = _root_blocks(OBS)[-1]
    assert "--gold:#d7b96b" in last
    assert "--teal:#3af4c8" in last
    assert "#c9b787" not in last
    assert ".r-btn-primary{background:var(--teal)" in OBS
    assert "UNAVAILABLE — DAG 0 / IDLE" in OBS
