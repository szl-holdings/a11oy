#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_shared_formulas — thesis-v22 formulas echoed from the a11oy front door.

a11oy is the canonical home (src/a11oy/formulas/*); these are VERBATIM vendored copies
of the subset amaru uses (single source of truth). Each module carries a real
thesis_v22.pdf citation + a real Lean theorem/obligation name. No mocks.

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations
from . import hnsw_retrieval
__all__ = ['hnsw_retrieval']
# SLSA L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet earned.
