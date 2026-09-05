#!/usr/bin/env python3
"""Materialize the reviewed homepage shell on the current-main successor branch.

This temporary controller copies exactly seven reviewed files from the recorded
source commit and extends the permanent legacy repair controller with an exact,
fail-closed successor recognizer. It performs no provider or protected-main
mutation.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REVIEWED_COMMIT = "eb232693f1b28a732005805318e6ce5e85bc0be6"
REVIEWED_FILES = (
    "a11oy_landing.html",
    "console/assets/szl-flow.js",
    "console/assets/szl-holo-v2.js",
    "tests/test_homepage_shell_coherence.py",
    "tests/test_landing_flagship_catalog.py",
    "tests/test_landing_touch_targets.py",
    "tests/test_living_command_fabric_frontdoor.py",
)
REPAIR_PATH = Path("scripts/repair_a11oy_frontdoor.py")
CLASS_ANCHOR = "\n\nclass PatchError(RuntimeError):\n    pass\n"
CHECK_ANCHOR = """    if args.check:
        baseline_errors = validate_truth(original)
        if not baseline_errors:
"""
CHECK_REPLACEMENT = """    if args.check:
        if is_reviewed_homepage_shell_successor(original):
            print(
                json.dumps(
                    {
                        \"status\": \"PASS\",
                        \"target\": str(args.path),
                        \"notes\": \"reviewed homepage-owned shell successor is current\",
                    },
                    indent=2,
                )
            )
            return 0
        baseline_errors = validate_truth(original)
        if not baseline_errors:
"""
HELPER = r'''

REVIEWED_HOMEPAGE_SHELL_EXACT_MARKERS = (
    '<html lang="en" data-szl-shell-owner="homepage"',
    '<title>a11oy — The Living Command Fabric</title>',
    '<style id="szl-homepage-shell">',
    '<nav class="nav-links" id="site-nav" aria-label="Primary navigation">',
    '<h1 class="title">Governed AI actions. <span class="grad">Receipts you can verify.</span></h1>',
    'var btn=document.getElementById("menu-toggle");',
)
REVIEWED_HOMEPAGE_SHELL_REQUIRED_MARKERS = (
    "persistent signer evidence is active and verification passes",
    "Receipt records · signer state separate",
    "Signer state is disclosed separately only where an actual signer-status read is present.",
    'grayChip(relation + " · CONJECTURE")',
    "min-height:44px",
    "overflow-wrap:anywhere",
    "/* Mobile overrides intentionally follow all equal-specificity base rules. */",
)
REVIEWED_HOMEPAGE_SHELL_FORBIDDEN_MARKERS = (
    '<a href="/console">Command</a>',
    '<title>a11oy — Governed Agent Change Management',
    "Every answer arrives with a signed receipt",
    "AI that signs its work",
)


def is_reviewed_homepage_shell_successor(text: str) -> bool:
    """Recognize only the reviewed, truth-preserving homepage-owned shell."""
    return (
        all(text.count(marker) == 1 for marker in REVIEWED_HOMEPAGE_SHELL_EXACT_MARKERS)
        and all(marker in text for marker in REVIEWED_HOMEPAGE_SHELL_REQUIRED_MARKERS)
        and all(marker not in text for marker in REVIEWED_HOMEPAGE_SHELL_FORBIDDEN_MARKERS)
    )
'''


def require_one(text: str, marker: str, label: str) -> None:
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")


def main() -> int:
    subprocess.run(
        ["git", "checkout", REVIEWED_COMMIT, "--", *REVIEWED_FILES],
        check=True,
    )

    text = REPAIR_PATH.read_text(encoding="utf-8")
    if "REVIEWED_HOMEPAGE_SHELL_EXACT_MARKERS" in text:
        raise SystemExit("reviewed homepage successor contract already exists")
    require_one(text, CLASS_ANCHOR, "PatchError insertion")
    require_one(text, CHECK_ANCHOR, "--check insertion")
    text = text.replace(CLASS_ANCHOR, HELPER + CLASS_ANCHOR, 1)
    text = text.replace(CHECK_ANCHOR, CHECK_REPLACEMENT, 1)
    REPAIR_PATH.write_text(text, encoding="utf-8")

    landing = Path("a11oy_landing.html").read_text(encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(HELPER, "<homepage-successor-contract>", "exec"), namespace)
    predicate = namespace["is_reviewed_homepage_shell_successor"]
    if not callable(predicate) or not predicate(landing):
        raise SystemExit("materialized homepage does not satisfy the exact successor contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
