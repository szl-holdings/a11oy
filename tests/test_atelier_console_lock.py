#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""ATELIER lock for /console: inference-lab /v1 only; honest labels.

Try Khipu must call szl-model-inference-lab /v1. Forge lab is SNAPSHOT — not a
trainer, not Serve Studio. Energy-attested-runs 8/8 is SIMULATED. Ask & Act is
not a live control plane. Λ = Conjecture 1.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
LOCKED_V1 = "https://szlholdings-szl-model-inference-lab.hf.space/v1"


def _console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def test_try_khipu_calls_inference_lab_v1_only() -> None:
    html = _console()
    start = html.find("/* try-khipu-panel")
    stop = html.find("/* end try-khipu-panel */")
    assert start >= 0 and stop > start
    slice_ = html[start:stop]
    assert LOCKED_V1 in slice_
    assert "/api/a11oy/v1/khipu/chat" in slice_
    assert "/api/a11oy/v1/khipu/status" in slice_
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


def test_energy_attested_runs_labeled_simulated_if_present() -> None:
    html = _console()
    if "energy-attested-runs" not in html.lower() and "energy-attested" not in html.lower():
        # Honesty strip on Try Khipu names the 8/8 SIMULATED lock even without a tile.
        assert "8/8" in html
        assert "SIMULATED" in html
        return
    assert "8/8" in html
    assert "SIMULATED" in html
    idx = html.lower().find("energy-attested")
    window = html[max(0, idx - 400) : idx + 400]
    assert "SIMULATED" in window


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
    """PR 1396 owns KANCHAY bar, 7-module rail, Command|Proof, Proof registry."""
    html = _console()
    assert '["ask","\\u2726","Ask & Act (demo)"]' not in html
    panel = html[html.find("/* try-khipu-panel") : html.find("/* end try-khipu-panel */")]
    assert "Proof registry" not in panel
    assert "mod-home" not in panel
    assert "Command|Proof" not in panel
