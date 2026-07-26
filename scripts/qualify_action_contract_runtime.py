#!/usr/bin/env python3
"""Protected qualification entrypoint for action-contract runtime promotion.

This file is the only runtime qualification program the manifest validator may
execute. Its exact bytes must already exist on the protected ``main`` branch
before a later pull request may promote the action contract. That two-step
sequence prevents a promotion change from supplying its own passing tests.

The authenticated, server-side idempotent, durable, operator-confirmed runtime
does not exist yet. Keep this qualification fail-closed until a separate,
reviewed change implements those controls and replaces this blocker with real
end-to-end assertions. Do not accept reports or testcase names as a substitute.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(runtime_root: Path) -> int:
    """Fail closed until protected tests can qualify this candidate root."""

    try:
        candidate_root = runtime_root.resolve(strict=True)
    except OSError as exc:
        print(f"BLOCKED: candidate runtime root is unavailable: {exc}", file=sys.stderr)
        return 1
    if not candidate_root.is_dir():
        print("BLOCKED: candidate runtime root is not a directory", file=sys.stderr)
        return 1
    print(
        "BLOCKED: the action-contract runtime remains ROADMAP; land real "
        "authenticated, idempotent, durable, operator-confirmed qualification "
        "tests on protected main before requesting verified-runtime promotion. "
        f"Candidate runtime root: {candidate_root}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    args = parser.parse_args()
    sys.exit(main(args.runtime_root))
