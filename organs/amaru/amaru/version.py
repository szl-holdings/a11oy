"""
version — resolve the running build's git SHA and start time.

Resolution order for the SHA (first hit wins):
  1. ``AMARU_GIT_SHA`` env var  — set this at build time (Docker ARG/ENV).
  2. ``GIT_SHA`` / ``SOURCE_COMMIT`` env vars — common CI / HF Spaces names.
  3. ``git rev-parse HEAD`` — works in a dev checkout.
  4. ``"unknown"`` — never raise; health must always answer.

The SHA is resolved once at import and cached so /healthz stays cheap.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

_BOOT_TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _from_env() -> str | None:
    for name in ("AMARU_GIT_SHA", "GIT_SHA", "SOURCE_COMMIT", "GIT_COMMIT"):
        val = os.environ.get(name)
        if val and val.strip():
            return val.strip()
    return None


def _from_git() -> str | None:
    try:
        here = Path(__file__).resolve().parent
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(here),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0:
            sha = out.stdout.strip()
            if sha:
                return sha
    except Exception:  # noqa: BLE001 — git may be absent in a container
        return None
    return None


def _resolve_git_sha() -> str:
    return _from_env() or _from_git() or "unknown"


GIT_SHA: str = _resolve_git_sha()
GIT_SHA_SHORT: str = GIT_SHA[:12] if GIT_SHA != "unknown" else "unknown"
BOOT_TS: str = _BOOT_TS
