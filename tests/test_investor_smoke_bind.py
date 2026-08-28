# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""S7 fail-closed bind against the live product sources.

INTI owns the UI rewrite. This file must stay RED until cnt-locked and
setTiers.locked source /api/a11oy/v1/honest locked_formula_count (8).
Do not rewrite genome data. Do not demand genome LOCKED-PROVEN == 8.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import investor_smoke_gate as gate  # noqa: E402


def test_trust_html_cnt_locked_must_not_read_genome_into_kernel_slot():
    text = (ROOT / "web" / "trust.html").read_text(encoding="utf-8")
    failures = gate.kernel_slot_bind_failures(text, source_name="web/trust.html")
    assert not failures, (
        "UI copy that claims locked-proven kernel / cnt-locked must source "
        "/api/a11oy/v1/honest locked_formula_count (8). Genome 144 / "
        "LOCKED-PROVEN 25 may remain as a separately labelled count. "
        "INTI owns the product fix. " + " | ".join(failures)
    )


def test_landing_settiers_locked_must_not_read_genome_into_kernel_slot():
    text = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    failures = gate.kernel_slot_bind_failures(text, source_name="a11oy_landing.html")
    assert not failures, (
        "setTiers.locked must source /api/a11oy/v1/honest locked_formula_count "
        "(8), labelled. If it still reads genome 25 into that slot, RED. "
        "INTI owns the product fix. " + " | ".join(failures)
    )
