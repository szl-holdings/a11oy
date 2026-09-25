"""Probe failure must not paint UP/LIVE.

HTTP errors and catch blocks are UNAVAILABLE. They are not a green fleet.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLES = (
    ROOT / "console" / "index.html",
    ROOT / "pages" / "console.html",
    ROOT / "pages_console.html",
)


def test_probe_catch_does_not_paint_up() -> None:
    for path in CONSOLES:
        text = path.read_text(encoding="utf-8")
        assert 'badge b-live">UP' not in text, path
        assert "b-err\">UNAVAILABLE" in text, path
