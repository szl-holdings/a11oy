# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import math
import re
from pathlib import Path


CSS_PATH = (
    Path(__file__).resolve().parents[1]
    / "routers"
    / "atelier_frontier_web"
    / "styles.css"
)
CSS = CSS_PATH.read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    match = re.search(rf"(?:^|\}}){re.escape(selector)}\{{([^}}]*)\}}", CSS)
    assert match is not None, f"missing CSS rule: {selector}"
    return match.group(1)


def _px(declarations: str, property_name: str) -> int:
    match = re.search(rf"(?:^|;){re.escape(property_name)}:(\d+)px(?:;|$)", declarations)
    assert match is not None, f"missing pixel property: {property_name}"
    return int(match.group(1))


def _centered_square_fits(
    width: int,
    height: int,
    radius: int,
    square: int = 44,
) -> bool:
    """Return whether a centered square is fully inside a rounded rectangle."""
    if width < square or height < square:
        return False
    inset_x = (width - square) / 2.0
    inset_y = (height - square) / 2.0
    if inset_x >= radius or inset_y >= radius:
        return True
    return math.hypot(radius - inset_x, radius - inset_y) <= radius


def test_primary_rounded_controls_contain_a_real_44px_hit_region() -> None:
    for selector in ("nav a", ".button", ".bindings a"):
        declarations = _rule(selector)
        width = _px(declarations, "min-width")
        height = _px(declarations, "min-height")
        radius = _px(declarations, "border-radius")
        assert _centered_square_fits(width, height, radius), (
            selector,
            width,
            height,
            radius,
        )


def test_secondary_navigation_and_accessibility_modes_remain_operable() -> None:
    assert _px(_rule("footer a"), "min-height") >= 48
    assert "@media(prefers-reduced-motion:reduce)" in CSS
    assert "@media(forced-colors:active)" in CSS
    assert ":focus-visible" in CSS
    assert "overflow-x:hidden" in CSS
