#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""The console opens Atelier without a second public inference path.

Operator authorization, exact public disclosure acknowledgement and outcome
validation belong to the governed Atelier form. Navigation cannot run inference.
Energy evidence stays UNAVAILABLE. Ask & Act is not a live control plane.
Λ = Conjecture 1.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
GOVERNED_FORM = "/command-centre#cpu-work"


def _console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def test_try_khipu_opens_authenticated_atelier_only() -> None:
    html = _console()
    start = html.find("/* try-khipu-panel")
    stop = html.find("/* end try-khipu-panel */")
    assert start >= 0 and stop > start
    slice_ = html[start:stop]
    assert f'href="{GOVERNED_FORM}"' in slice_
    assert "/api/a11oy/v1/khipu/chat" not in slice_
    assert "/api/a11oy/v1/khipu/status" not in slice_
    assert "/v1/chat/completions" not in slice_
    assert "fetch(" not in slice_
    assert "XMLHttpRequest" not in slice_
    assert "<textarea" not in slice_
    assert "szl-forge-lab.hf.space" not in slice_.lower()
    assert "szl-forge-lab.static.hf.space" not in slice_.lower()


def test_forge_lab_not_wired_as_trainer_or_serve_studio() -> None:
    html = _console()
    lowered = html.lower()
    assert "not a trainer" in lowered
    assert "not serve studio" in lowered
    # Must not present forge-lab as a live trainer or Serve Studio surface.
    for banned in (
        "forge-lab trainer",
        "trainer: forge",
        "serve studio live",
        "wire forge-lab",
    ):
        assert banned not in lowered


def test_energy_attested_runs_fail_closed_without_evidence_contract() -> None:
    html = _console()
    start = html.find("/* try-khipu-panel")
    stop = html.find("/* end try-khipu-panel */")
    assert start >= 0 and stop > start
    panel = html[start:stop]
    compact = "".join(panel.split())

    assert "Energy evidence remains UNAVAILABLE" in panel
    assert "hon.energy_attested_runs" not in panel
    assert "pin.energy_attested_runs" not in panel
    assert "MEASURED" not in panel
    assert "||'8/8 SIMULATED'" not in compact


def test_ask_and_act_is_not_a_live_control_plane() -> None:
    html = _console()
    assert "Ask & Act" in html
    assert "not a live control plane" in html
    # Last-wins overlay and the initial VIEWS.ask both carry the honest badge.
    assert html.count("NOT A LIVE CONTROL PLANE") >= 2
    # Do not keep the OPERATOR control-plane claim on Ask & Act.
    ask_first = html.find("ask:{title:'Ask & Act'")
    assert ask_first >= 0
    first_block = html[ask_first : ask_first + 500]
    assert "OPERATOR" not in first_block
    overlay = html.find("V.ask={title:'Ask & Act'")
    assert overlay >= 0
    overlay_block = html[overlay : overlay + 700]
    assert "not a live control plane" in overlay_block.lower() or "NOT A LIVE CONTROL PLANE" in overlay_block


def test_does_not_retune_nawi_command_bar_or_rail() -> None:
    """The KANCHAY bar may name Ask & Act only with its explicit demo boundary."""
    html = _console()
    assert html.count('["ask","\\u2726","Ask & Act (demo)"]') == 1
    assert '["ask","\\u2726","Ask & Act"]' not in html
    panel = html[html.find("/* try-khipu-panel") : html.find("/* end try-khipu-panel */")]
    assert "Proof registry" not in panel
    assert "mod-home" not in panel
    assert "Command|Proof" not in panel
