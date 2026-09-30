# SPDX-License-Identifier: Apache-2.0
"""Constellation tab wiring on /command/constellation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "constellation.html"
MOD = ROOT / "a11oy_command_center.py"


def test_page_exists_and_is_honest() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "ESTATES" in html
    assert "/api/a11oy/" in html
    assert "cdnjs" not in html and "googleapis" not in html and "jsdelivr" not in html
    assert "UNAVAILABLE" in html
    assert "Conjecture 1" in html


def test_module_mounts_constellation() -> None:
    src = MOD.read_text(encoding="utf-8")
    assert "/command/constellation" in src
    assert "constellation.html" in src
