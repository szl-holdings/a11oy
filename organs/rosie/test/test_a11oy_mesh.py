"""Integration tests for rosie.console.a11oy_mesh.

Reuses the a11oy-like stdlib server fixture to prove the console panel reflects
real a11oy HTTP responses, and degrades honestly (no fabricated green) when
a11oy is unreachable.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from src.console.a11oy_client import A11oyClient
from src.console.a11oy_mesh import a11oy_panel

# The a11oy_server fixture is provided by test/conftest.py.


def test_panel_reflects_live_a11oy(a11oy_server):  # noqa: F811
    panel = a11oy_panel(A11oyClient(a11oy_server))
    assert panel.reachable is True
    assert panel.healthy is True
    assert panel.ready is True
    assert panel.sha == "abc123"
    assert panel.ledger_total == 1
    assert panel.recent_receipts and panel.recent_receipts[0]["receipt_id"] == "r-1"
    assert panel.error is None


def test_panel_degrades_honestly_when_unreachable():
    panel = a11oy_panel(A11oyClient("http://127.0.0.1:1", timeout=0.5))
    assert panel.reachable is False
    assert panel.healthy is False
    assert panel.ready is False
    assert panel.error is not None
    # honesty: no fabricated green state
    assert panel.ledger_total is None
