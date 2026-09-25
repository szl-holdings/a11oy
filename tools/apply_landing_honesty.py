#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Apply the two-string Wave-1 honesty patch to pages/landing.html.

Does not stamp LIVE. Does not touch /console. Does not mint five-space.
Expected output sha256: 0fd5bb2a28535f25fa86895f7715f917e3aece204a68c98a32a44900c3c441cf
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

EXPECTED_SHA256 = "0fd5bb2a28535f25fa86895f7715f917e3aece204a68c98a32a44900c3c441cf"
LIVE = "LIVE COMMAND PLATFORM"
BIND = "BIND \u00b7 CONNECTING"
KPI_OLD = 'class="ds-kpi__value is-live is-loading" id="kpiServices"'
KPI_NEW = 'class="ds-kpi__value is-loading" id="kpiServices"'


def main(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    if LIVE not in text and BIND in text and KPI_OLD not in text:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        print(f"already patched {path} sha256={digest}")
        return 0
    if LIVE not in text:
        print(f"refusing: {path} missing {LIVE!r} and is not already patched", file=sys.stderr)
        return 2
    if KPI_OLD not in text:
        print(f"refusing: {path} missing kpiServices is-live first paint", file=sys.stderr)
        return 2
    patched = text.replace(LIVE, BIND, 1).replace(KPI_OLD, KPI_NEW, 1)
    if LIVE in patched:
        print("refusing: LIVE stamp still present after replace", file=sys.stderr)
        return 2
    if KPI_OLD in patched:
        print("refusing: kpiServices still first-paints is-live", file=sys.stderr)
        return 2
    path.write_text(patched, encoding="utf-8")
    digest = hashlib.sha256(patched.encode("utf-8")).hexdigest()
    print(f"wrote {path} bytes={len(patched.encode('utf-8'))} sha256={digest}")
    if digest != EXPECTED_SHA256:
        print(
            f"warning: sha256 != canned expect {EXPECTED_SHA256} (source drifted; inspect diff)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pages/landing.html")
    raise SystemExit(main(target))
