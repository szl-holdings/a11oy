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
    assert "@media(max-width:680px)" not in html
    assert "@media(min-width:681px){.nav-cta-short{display:none}}" not in html
