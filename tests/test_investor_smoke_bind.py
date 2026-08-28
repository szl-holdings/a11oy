# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""S7 fail-closed: kernel chips must bind to /honest locked_formula_count (8 or N/A).

Genome LOCKED-PROVEN=25 is a catalog tier and may remain. The FAIL is the bind:
landing #pt-locked and trust/console #cnt-locked must not paint catalog 25 into
the kernel slot. PR 1396 landed console #cnt-locked from GET /api/a11oy/v1/honest.
Do not rewrite genome.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import investor_smoke_gate as gate  # noqa: E402


def test_kernel_chips_bind_to_honest_locked_formula_count():
    counts = gate.genome_catalog_counts(ROOT / "data" / "genome.json")
    assert counts["locked_proven_tags"] != gate.LOCKED_KERNEL_COUNT, (
        "catalog LOCKED-PROVEN is not the kernel; this job must not demand they "
        f"be equal (catalog={counts['locked_proven_tags']}, kernel="
        f"{gate.LOCKED_KERNEL_COUNT})"
    )
    verdict = gate.s7_verdict(ROOT)
    assert verdict.status == "PASS", (
        "S7 PASS requires a11oy_landing.html #pt-locked via loadLockedKernel "
        "and web/trust.html + pages/console.html #cnt-locked all bound to "
        f"GET {gate.HONEST_PATH} {gate.HONEST_FIELD} (8 or N/A). Genome "
        "LOCKED-PROVEN may remain as a labelled catalog tier. "
        f"{verdict.detail} | {verdict.evidence}"
    )
