from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_landing_exposes_mobile_hamburger_and_44px_targets() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    assert 'id="menuToggle"' in landing
    assert 'id="primaryLinks"' in landing
    assert '.nav-links[data-open="true"]{display:flex}' in landing
    assert ".menu-toggle{display:none;min-width:44px;min-height:44px" in landing
    assert ".nav nav a.hide-sm,.nav nav a:not(.btn){display:none}" not in landing
    assert 'padding:10px 14px;min-height:44px' in landing
    assert "padding:2px 10px" not in landing
    # honesty labels stay honest
    assert "UNAVAILABLE" in landing
    assert "CHECKING" in landing
    assert "SAMPLE" in landing


def test_dead_path_aliases_are_fragment_free() -> None:
    src = (ROOT / "a11oy_nav_wireup.py").read_text(encoding="utf-8")
    assert '("/mesh", "/console")' in src
    assert '("/evidence", "/trust")' in src
    assert '("/arena", "/console")' in src
    assert '("/router", "/console")' in src
    assert "/console#mesh" not in src
    assert "/console#arena" not in src
