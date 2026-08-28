# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""Source contract for the /console Try Khipu panel.

Does not add a nav data-view (tabs.json 139-tab gate). No tokens/s marketing
number inside the panel slice.
"""
from pathlib import Path

CONSOLE = Path(__file__).resolve().parents[1] / "pages" / "console.html"
BEGIN = "/* try-khipu-panel"
END = "/* end try-khipu-panel */"


def _panel_slice() -> str:
    html = CONSOLE.read_text(encoding="utf-8")
    start = html.find(BEGIN)
    stop = html.find(END)
    assert start >= 0, "Try Khipu panel marker missing from pages/console.html"
    assert stop > start, "Try Khipu panel end marker missing from pages/console.html"
    return html[start:stop]


def test_try_khipu_panel_present_on_command_center_only():
    html = CONSOLE.read_text(encoding="utf-8")
    slice_ = _panel_slice()
    assert "Try Khipu" in slice_
    assert "/api/a11oy/v1/khipu/status" in slice_
    assert "/api/a11oy/v1/khipu/chat" in slice_
    assert "UNSIGNED" in slice_
    assert "Conjecture 1" in slice_
    assert "READY" in slice_
    assert "FAILED" in slice_
    assert "record_sha256" in slice_
    assert 'data-view="' not in slice_
    assert "data-view='" not in slice_
    # wrap Command Center only
    assert "V.command" in slice_ or "command.render" in slice_


def test_try_khipu_panel_has_no_tokens_per_second_marketing():
    slice_ = _panel_slice()
    lowered = slice_.lower()
    assert "tokens/s" not in lowered
    assert "tok/s" not in lowered
    assert "tokens_per_second" not in lowered
    assert "tokens per second" not in lowered


def test_try_khipu_honesty_labels():
    slice_ = _panel_slice()
    assert "ROADMAP" in slice_
    assert "SNAPSHOT" in slice_
    assert "SIMULATED" in slice_
    assert "MEASURED" in slice_
    assert "not-a-secret" in slice_
