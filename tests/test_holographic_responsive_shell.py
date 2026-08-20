"""Static guards for the compact, accessible Holographic surface browser."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "static" / "3d" / "holographic.html"


def _shell() -> str:
    return SHELL.read_text(encoding="utf-8")


def test_surface_browser_stays_compact_and_can_layer_above_the_intro():
    html = _shell()
    assert '.tabs[data-browse="true"],.tabs:focus-within{z-index:40}' in html
    assert '.tabs[data-browse="true"] .surface-browser{display:flex' in html
    assert 'class="surface-search"' in html
    assert 'id="nav-mode"' in html


def test_mobile_shell_hides_native_horizontal_scrollbars_without_hiding_surfaces():
    html = _shell()
    assert '.navrow::-webkit-scrollbar{display:none}' in html
    assert 'footer{font-size:9px;padding:5px 10px}' in html
    assert 'white-space:normal;overflow:visible;line-height:1.35' in html
    assert 'const SURFACES = [' in html


def test_surface_navigation_is_keyboard_and_history_aware():
    html = _shell()
    assert 'role="tablist"' not in html
    assert 'aria-current", "page"' in html
    assert '"ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"' in html
    assert 'window.addEventListener("hashchange"' in html
    assert 'history.pushState(null, "", "#" + id)' in html
    assert 'selectSurface(requested, "none")' in html
    assert 'const b = document.createElement("a")' in html
    assert 'if (current && current.def && current.def.id === id)' in html
    assert 'matches[0].setAttribute("aria-current", "page")' in html
    assert 'btn.setAttribute("aria-controls", panel.id)' in html
    assert 'panel.setAttribute("aria-labelledby", btn.id)' in html
    assert '["finance", "Finance & Markets"]' in html
    assert 'Show more results' in html


def test_intro_dialog_has_modal_focus_and_escape_contracts():
    html = _shell()
    assert 'aria-modal="true"' in html
    assert 'tabindex="-1"' in html
    assert 'if (ev.key === "Escape")' in html
    assert 'introReturnFocus' in html
    assert '#intro{position:fixed;inset:0;z-index:80' in html
    assert 'introBackground.forEach((el) => { el.inert = true; })' in html
    assert 'introBackground.forEach((el) => { el.inert = false; })' in html
