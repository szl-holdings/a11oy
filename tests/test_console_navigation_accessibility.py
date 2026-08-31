# SPDX-License-Identifier: Apache-2.0
"""Offline accessibility contract for the production operator-console rail."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


CONSOLE = Path(__file__).resolve().parents[1] / "pages" / "console.html"


class _SidebarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._side_depth = 0
        self.items: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if self._side_depth:
            self._side_depth += 1
        elif tag == "aside" and "side" in classes:
            self._side_depth = 1

        if self._side_depth and "nav-item" in classes:
            self.items.append((tag, attributes))

    def handle_endtag(self, tag: str) -> None:
        if self._side_depth:
            self._side_depth -= 1


def _sidebar_items() -> list[tuple[str, dict[str, str | None]]]:
    parser = _SidebarParser()
    parser.feed(CONSOLE.read_text(encoding="utf-8"))
    return parser.items


def test_initial_console_navigation_uses_native_buttons() -> None:
    items = _sidebar_items()

    assert len(items) >= 20, "the initial, pre-JavaScript rail must remain complete"
    assert all(tag == "button" for tag, _ in items)
    assert all(attrs.get("type") == "button" for _, attrs in items)
    assert all(attrs.get("data-view") for _, attrs in items)


def test_initial_console_navigation_exposes_one_current_page() -> None:
    current = [
        attrs
        for _, attrs in _sidebar_items()
        if attrs.get("aria-current") == "page"
    ]

    assert len(current) == 1
    assert current[0].get("data-view") == "command"


def test_runtime_navigation_preserves_semantics_and_visible_focus() -> None:
    html = CONSOLE.read_text(encoding="utf-8")

    assert ".nav-item:focus-visible" in html
    assert "outline:2px solid var(--teal)" in html
    assert "var d = document.createElement('button');" in html
    assert "d.type = 'button';" in html
    assert "n.setAttribute('aria-current','page')" in html
    assert "n.removeAttribute('aria-current')" in html
    assert "act.setAttribute('aria-current','page')" in html
    assert "!n.closest('#pinned-host')" in html
    assert "if(!pinnedCurrent && n.closest('#pinned-host'))" in html
    assert "canonicalCurrent=canonicalCurrent||pinnedCurrent" in html
    assert "if(n===canonicalCurrent)" in html
    assert "var c = side.querySelector('.nav-item[data-view=\"command\"]')" not in html


def test_persisted_pinned_navigation_uses_native_buttons() -> None:
    html = CONSOLE.read_text(encoding="utf-8")

    assert (
        "h+='<button type=\"button\" class=\"nav-item\" data-view=\"'"
        in html
    )
    assert (
        "h+='<div class=\"nav-item\" data-view=\"'+esc(k)"
        not in html
    )
    assert "var cur=window._requestedView||(typeof szlViewFromLocation==='function'?szlViewFromLocation():(location.hash||'#command').slice(1))" in html
    assert "if(!n.closest('#pinned-host')&&n.dataset.view===cur)" in html
    assert "var isCurrent=n.dataset.view===cur" in html
    assert "n.classList.toggle('active',isCurrent)" in html
    assert "if(isCurrent&&!canonicalCurrent){ n.setAttribute('aria-current','page'); }" in html
