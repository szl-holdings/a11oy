#!/usr/bin/env python3
"""Fail closed on disabled HF drift workflow or corrupted public UTF-8.

This guard intentionally uses only the Python standard library.  It is run from
the independent ``Tests`` workflow so damage to ``hf-module-drift.yml`` cannot
silence the guard that checks it.
"""

from __future__ import annotations

import argparse
import json
import re
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
BASELINE_JOB = "hf-module-drift"
CANDIDATE_JOB = "hf-repository-parity"
BASELINE_INVOCATION = "python3 baseline/.github/scripts/verify_hf_repository_parity.py"
CANDIDATE_INVOCATION = "python3 candidate/.github/scripts/verify_hf_repository_parity.py"
CANDIDATE_ALLOW_ARGUMENT = "--allow candidate/.github/hf-module-drift-allow.json"
TOOLS_ARGUMENT = "--tools-script tools/.github/scripts/hf_module_drift_check.py"
FAILURE_SUPPRESSORS = ("continue-on-error", "--warn-only", "|| true")


def _job_block(workflow: str, job_name: str) -> str | None:
    lines = workflow.splitlines()
    marker = f"  {job_name}:"
    try:
        start = lines.index(marker)
    except ValueError:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.fullmatch(r"  [A-Za-z0-9_-]+:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def _validate_parity_jobs(workflow: str) -> list[str]:
    errors: list[str] = []
    baseline = _job_block(workflow, BASELINE_JOB)
    candidate = _job_block(workflow, CANDIDATE_JOB)
    if baseline is None:
        errors.append("HF drift workflow is missing the protected-base parity job")
    if candidate is None:
        errors.append("HF drift workflow is missing the candidate parity job")
    if baseline is None or candidate is None:
        return errors

    if baseline.count(BASELINE_INVOCATION) != 1:
        errors.append("protected-base job must invoke the baseline wrapper exactly once")
    if "--allow" in baseline:
        errors.append("protected-base job must not receive an HF drift allowlist")
    if candidate.count(CANDIDATE_INVOCATION) != 1:
        errors.append("candidate job must invoke the candidate wrapper exactly once")
    allow_lines = [
        line.strip().removesuffix("\\").rstrip()
        for line in candidate.splitlines()
        if line.lstrip().startswith("--allow ")
    ]
    if allow_lines != [CANDIDATE_ALLOW_ARGUMENT]:
        errors.append("candidate job must receive exactly its same-checkout allowlist")
    for label, block, source_ref in (
        ("protected-base", baseline, "github.event.pull_request.base.sha"),
        ("candidate", candidate, "github.event.pull_request.head.sha"),
    ):
        if block.count(TOOLS_ARGUMENT) != 1:
            errors.append(f"{label} job must use the pinned organization comparator once")
        if source_ref not in block:
            errors.append(f"{label} job is not bound to its exact pull-request SHA")
        pinned_refs = re.findall(r"(?m)^\s+ref: ([0-9a-f]{40})\s*$", block)
        if len(pinned_refs) != 1:
            errors.append(f"{label} job must contain one immutable tools revision")
        for suppressor in FAILURE_SUPPRESSORS:
            if suppressor in block:
                errors.append(f"{label} job contains failure suppressor: {suppressor}")
    return errors


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
        errors.extend(_validate_parity_jobs(workflow))

    allowlist_text, allowlist_errors = _read_strict_utf8(root, ALLOWLIST_PATH)
    errors.extend(allowlist_errors)
    if allowlist_text is not None:
        try:
            allowlist = json.loads(allowlist_text)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid HF drift allowlist: {exc}")
        else:
            accepted = allowlist.get("accepted_divergences")
            if not isinstance(accepted, dict):
                errors.append("accepted_divergences must be a JSON object")
            else:
                if any(
                    path in {".well-known/security.txt", "well-known/security.txt"}
                    for path in accepted
                ):
                    errors.append("security.txt cannot bypass its mandatory byte proof")
                for path, reason in accepted.items():
                    if not isinstance(path, str) or not path or "\\" in path or ".." in Path(path).parts:
                        errors.append(f"invalid accepted-divergence path: {path!r}")
                    if not isinstance(reason, str) or not reason.strip():
                        errors.append(f"invalid accepted-divergence reason: {path!r}")

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
