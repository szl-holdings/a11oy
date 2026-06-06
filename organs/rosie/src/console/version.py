"""rosie.console.version — build identity for /healthz.

Resolves a git SHA and boot timestamp once at import so /healthz can report
exactly which build is running. Resolution order for the SHA:

    ROSIE_GIT_SHA -> GIT_SHA -> SOURCE_COMMIT -> GIT_COMMIT  (env vars)
    -> `git rev-parse HEAD`                                   (subprocess)
    -> "unknown"                                              (never raises)

SOURCE_COMMIT is the variable Hugging Face Spaces injects; the others cover
GitHub Actions and generic CI. Resolution never raises — a build with no git
metadata reports "unknown" rather than failing health.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import datetime
import os
import subprocess

SERVICE = "rosie"
VERSION = "0.0.1"

# Env vars consulted for the git SHA, in priority order.
_SHA_ENV_VARS = ("ROSIE_GIT_SHA", "GIT_SHA", "SOURCE_COMMIT", "GIT_COMMIT")


def _resolve_git_sha() -> str:
    """Resolve the build's git SHA without ever raising."""
    for var in _SHA_ENV_VARS:
        val = os.environ.get(var)
        if val:
            return val.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


# Resolved once at import.
GIT_SHA: str = _resolve_git_sha()
GIT_SHA_SHORT: str = GIT_SHA[:12] if GIT_SHA != "unknown" else "unknown"
BOOT_TS: str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_info() -> dict[str, str]:
    """Return the build-identity fields for the health payload."""
    return {
        "service": SERVICE,
        "version": VERSION,
        "gitSha": GIT_SHA,
        "gitShaShort": GIT_SHA_SHORT,
        "bootTs": BOOT_TS,
    }
