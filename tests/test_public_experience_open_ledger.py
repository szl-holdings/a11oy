from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_open_ledger_link_is_a_full_touch_target() -> None:
    source = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    assert ".stat .stat-note a{" in source
    rule = source.split(".stat .stat-note a{", 1)[1].split("}", 1)[0]
    assert "display:inline-flex" in rule
    assert "align-items:center" in rule
    assert "min-height:44px" in rule
    assert "padding-inline" in rule
    assert ">open ledger</a>" in source
