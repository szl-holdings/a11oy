#!/usr/bin/env python3
"""Fail closed on disabled HF drift workflow or corrupted public UTF-8.

This guard intentionally uses only the Python standard library.  It is run from
the independent ``Tests`` workflow so damage to ``hf-module-drift.yml`` cannot
silence the guard that checks it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = Path(".github/workflows/hf-module-drift.yml")
ALLOWLIST_PATH = Path(".github/hf-module-drift-allow.json")

PUBLIC_UTF8_PATHS = (
    Path("a11oy_landing.html"),
    Path("govern_showcase.html"),
    Path("pages/assurance.html"),
    Path("pages/chaski.html"),
    Path("pages/console.html"),
    Path("pages/fabric.html"),
    Path("pages/landing.html"),
    Path("pages/pinn-console.html"),
    Path("pages/pricing.html"),
    Path("pages/substrate.html"),
    Path("pages/verify.html"),
)

# Explicitly reject UTF-8 bytes rendered through legacy encodings.
MOJIBAKE_LEADERS = ("\u00c2", "\u00c3", "\u00ce", "\u00cf", "\u00e2", "\u00f0", "\ufffd")

REQUIRED_TOP_LEVEL_LINES = ("on:", "permissions:", "jobs:")
REQUIRED_WORKFLOW_TOKENS = (
    "  pull_request:",
    "  schedule:",
    "  workflow_dispatch:",
    "  hf-module-drift:",
    "  hf-runtime-live:",
    "  hf-repository-parity:",
    "verify_hf_repository_parity.py",
    "reusable-hf-module-drift-check.yml@",
    "--tools-script tools/.github/scripts/hf_module_drift_check.py",
)


def _read_strict_utf8(root: Path, relative: Path) -> tuple[str | None, list[str]]:
    path = root / relative
    if not path.is_file():
        return None, [f"missing file: {relative.as_posix()}"]

    raw = path.read_bytes()
    errors: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"UTF-8 BOM is forbidden: {relative.as_posix()}")
    try:
        return raw.decode("utf-8"), errors
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8: {relative.as_posix()}: {exc}")
        return None, errors


def validate(root: Path = REPO_ROOT) -> list[str]:
    """Return every integrity error; an empty list is PASS."""

    errors: list[str] = []
    workflow, workflow_errors = _read_strict_utf8(root, WORKFLOW_PATH)
    errors.extend(workflow_errors)
    if workflow is not None:
        lines = workflow.splitlines()
        if len(lines) < 100:
            errors.append(
                f"HF drift workflow is unexpectedly short: {len(lines)} lines (minimum 100)"
            )
        for required in REQUIRED_TOP_LEVEL_LINES:
            if required not in lines:
                errors.append(f"HF drift workflow missing top-level line: {required}")
        for required in REQUIRED_WORKFLOW_TOKENS:
            if required not in workflow:
                errors.append(f"HF drift workflow missing required token: {required}")
        tool_path_count = workflow.count(
            "--tools-script tools/.github/scripts/hf_module_drift_check.py"
        )
        if tool_path_count != 2:
            errors.append(
                "HF drift workflow must contain exactly two canonical tools-script "
                f"arguments; observed {tool_path_count}"
            )

    allowlist_path = root / ALLOWLIST_PATH
    if not allowlist_path.is_file():
        errors.append(f"missing file: {ALLOWLIST_PATH.as_posix()}")
    else:
        try:
            allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid HF drift allowlist: {exc}")
        else:
            accepted = allowlist.get("accepted_divergences")
            if not isinstance(accepted, dict):
                errors.append("accepted_divergences must be a JSON object")

    for relative in PUBLIC_UTF8_PATHS:
        content, file_errors = _read_strict_utf8(root, relative)
        errors.extend(file_errors)
        if content is None:
            continue
        for marker in MOJIBAKE_LEADERS:
            count = content.count(marker)
            if count:
                errors.append(
                    f"mojibake marker U+{ord(marker):04X} in "
                    f"{relative.as_posix()}: {count} occurrence(s)"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    result = {
        "status": "PASS" if not errors else "FAIL",
        "workflow": WORKFLOW_PATH.as_posix(),
        "public_files_checked": len(PUBLIC_UTF8_PATHS),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
