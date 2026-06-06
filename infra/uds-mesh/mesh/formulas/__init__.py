#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""mesh.formulas — formulas the UDS mesh invokes at RUNTIME (not just static code).

These three modules are wired into mesh/sdk/mesh.py so the bundle's runtime actually
calls them when merging cross-organ verdicts and aggregating Khipu receipts:

  - pac_bayes_quorum : PAC-Bayes (Catoni) bound + Byzantine quorum (n≥3f+1), evaluated
                       BEFORE the mesh merges cross-organ verdicts.
  - bls_aggregate    : REAL BLS12-381 aggregate signatures (py_ecc) over the cross-organ
                       Khipu chain root (when 3+ organs co-sign).
  - welford_streaming: online running statistics on OTLP trace fan-out.

Each carries a real thesis-v22 citation + a real Lean theorem permalink into
szl-holdings/lutar-lean. No mocks; the BLS path is genuine pairing-based crypto.

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations
from . import pac_bayes_quorum
from . import bls_aggregate
from . import welford_streaming
__all__ = ["pac_bayes_quorum", "bls_aggregate", "welford_streaming"]
