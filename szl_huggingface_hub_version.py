# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""Installed huggingface_hub.__version__ readback.

The Dockerfile pin is not this field. Missing import or empty __version__
is UNAVAILABLE. Never copies 1.31.0 from audit/source pins.
"""
from __future__ import annotations


def huggingface_hub_version() -> str:
    try:
        import huggingface_hub as _hub
    except Exception:
        return "UNAVAILABLE"
    version = getattr(_hub, "__version__", None)
    if isinstance(version, str) and version.strip():
        return version.strip()
    return "UNAVAILABLE"
