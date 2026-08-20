#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""amaru_formula_endpoints.py — live HTTP surface for the shared thesis-v22 formulas
echoed into amaru from the a11oy front door.

ADDITIVE, self-contained. register(app, ns="amaru") mounts /api/amaru/v1/formula/*
+ /api/amaru/v1/formulas/index. HONEST schema {value, citation, lean_theorem}: each
citation is a real thesis_v22.pdf section, each lean_theorem a real Lean declaration.

Echoed formulas: ['hnsw_retrieval']

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import os
import sys
import threading

# Path bootstrap: the vendored package sits at repo root next to this file (WORKDIR /app).
_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in ("/app", _HERE):
    if os.path.isdir(os.path.join(_cand, "szl_shared_formulas")) and _cand not in sys.path:
        sys.path.insert(0, _cand)

try:
    from starlette.requests import Request
except Exception:  # pragma: no cover
    Request = None  # type: ignore

try:
    from szl_shared_formulas import (
        hnsw_retrieval,
    )
    _OK = True
except Exception as _imp_e:  # pragma: no cover
    _OK = False
    print(f"[amaru] shared formulas import failed: {_imp_e!r}", file=sys.stderr)


_LOCK = threading.Lock()

_INDEX = [
    {"name": "hnsw", "citation": "thesis_v22.pdf §2", "lean_theorem": "FrontierHNSWNavigability.lean::greedy_search_terminates"},
]


def formulas_summary() -> dict:
    """Honest summary for the /honest endpoint: which formulas amaru uses + citations."""
    return {
        "wired": _INDEX,
        "count": len(_INDEX),
        "source": "echoed from a11oy front door (a11oy.formulas, verbatim)",
        "provenance": "thesis_v22.pdf §2 + real Lean theorem/obligation per module",
    }


def register(app, ns: str = "amaru") -> str:
    """Mount the echoed formula endpoints. Returns a status string."""
    if not _OK:
        return "formulas-unavailable"
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/formula"

    @app.get(f"/api/{ns}/v1/formulas/index")
    async def _formulas_index():
        return JSONResponse({"wired": _INDEX, "count": len(_INDEX), "doctrine": "v11",
                             "source": "echoed from a11oy front door"})

    @app.get(f"{base}/hnsw")
    async def _hnsw():
        return JSONResponse(hnsw_retrieval.status())

    return f"formulas-wired:{len(_INDEX)}"


__all__ = ["register", "formulas_summary"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest (cosign-signed; verifiable via cosign verify). L2 build-provenance attestation is roadmap (Wire D) — not yet earned.
