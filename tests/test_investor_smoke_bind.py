# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""S7 fail-closed: genome LOCKED-PROVEN must equal /honest locked_formula_count=8.

INTI owns the real count. Keep RED until every surface agrees, labelled.
Do not rewrite genome data or Trust Center copy to fake agreement.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import investor_smoke_gate as gate  # noqa: E402


def test_genome_locked_proven_must_equal_honest_eight():
    counts = gate.genome_catalog_counts(ROOT / "data" / "genome.json")
    verdict = gate.s7_verdict(ROOT)
    assert counts["locked_proven_tags"] == gate.LOCKED_KERNEL_COUNT, (
        f"genome tier_counts.LOCKED-PROVEN={counts['locked_proven_tags']} must "
        f"equal honest locked_formula_count={gate.LOCKED_KERNEL_COUNT}. INTI "
        "owns the real count. Do not rewrite genome.json or Trust Center copy "
        f"to fake agreement. {verdict.detail}"
    )
    assert verdict.status == "PASS", verdict.detail
