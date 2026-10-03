# SPDX-License-Identifier: Apache-2.0
"""Additive Yuyay evaluate surface. SOFTWARE analog. Cannot ALLOW-alone."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "yuyay-gate.html"
COMMAND = ROOT / "pages" / "command-center.html"


def test_yuyay_gate_page_is_software_and_cannot_allow_alone() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "yuyay13.systemone.v1" in text
    assert 'honesty:"SOFTWARE"' in text
    assert "jev_allow_alone:false" in text
    assert 'decision:"UNAVAILABLE"' in text
    assert "Lambda is never a theorem" in text
    assert "Jev never ALLOW-alone" in text
    assert 'decision:"ALLOW"' not in text
    assert 'tok("bo","11y sku")' in text
    assert "yuyay13" in text
    assert "engage_admissible:0" in text
    assert "conjecture_1:\"OPEN\"" in text


def test_command_center_not_stubbed() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert "<p>temp</p>" not in text
    assert len(text) > 20000
