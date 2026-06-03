#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy — front-door organ package.

This package namespace exists so that ``a11oy.formulas`` (the thesis-v22 formulas
instilled into the front door) is importable when ``/app/src`` is on ``sys.path``.
It deliberately stays import-light: it MUST NOT import heavy runtime deps so that
``import a11oy.formulas`` is cheap and side-effect free at serve.py startup.

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""

__all__ = ["formulas"]
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
