# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""Landing HTML must not race the packaged binder on kernel / is-live / state."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
PAGES_LANDING = (ROOT / "pages" / "landing.html").read_text(encoding="utf-8")


def test_packaged_binder_is_the_kernel_writer() -> None:
    assert 'src="/static/landing-honest-bind.js"' in LANDING
    assert "var lockedN" not in LANDING
    assert 'txt("nv-kernel"' not in LANDING
    assert 'txt("nv-kernel", "locked-8")' not in LANDING
    assert 'classList.add("is-live")' not in LANDING
    assert "read live ·" not in LANDING
    assert 'txt("nv-state"' not in LANDING


def test_inline_instrument_still_owns_surfaces_and_verdict() -> None:
    assert "/api/a11oy/v1/frontier/surfaces" in LANDING
    assert "sig.signed === true" in LANDING
    assert "HASH-LINKED" in LANDING


def test_pages_landing_first_paint_is_not_a_live_stamp() -> None:
    """HTTP 200 is not LIVE. Hero badge and KPI first paint stay BIND/CONNECTING."""
    assert "LIVE COMMAND PLATFORM" not in PAGES_LANDING
    assert 'id="liveBadge"' in PAGES_LANDING
    assert "BIND · CONNECTING" in PAGES_LANDING
    assert 'id="kpiServices"' in PAGES_LANDING
    assert 'class="ds-kpi__value is-live is-loading" id="kpiServices"' not in PAGES_LANDING
    assert 'classList.add("is-live")' not in PAGES_LANDING
