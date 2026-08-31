#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Honesty-only: killinchu effector SIMULATED; console empty states stay UNKNOWN.

Does not restore the old three-color console palette after KANCHAY.
Does not replace UNAVAILABLE organ probes with UNKNOWN.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
LANDING = ROOT / "pages" / "landing.html"


def test_landing_labels_killinchu_effector_simulated() -> None:
    html = LANDING.read_text(encoding="utf-8")
    assert "killinchu effector stays SIMULATED" in html
    assert "<b>UNAVAILABLE</b>" in html
    assert "function unavailable" in html or "unavailable(" in html


def test_console_empty_helpers_keep_unknown_and_unavailable() -> None:
    html = CONSOLE.read_text(encoding="utf-8")
    helpers = html[html.index("function emptyUnknown(") : html.index("function honestDegraded")]
    assert "UNKNOWN" in helpers
    assert "ROADMAP" in helpers
    assert "UNAVAILABLE" in helpers
    assert "sample / snapshot" not in html[html.index("function _szlHonestChip()") : html.index("function _szlIsSpinnerText")]
