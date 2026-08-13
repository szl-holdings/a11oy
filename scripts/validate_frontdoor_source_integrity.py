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
import shlex
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
SHELL_CONTROL_TOKENS = frozenset({";", "&&", "||", "|", "&", ">", ">>", "<", "<<"})
ALLOWED_ALLOWLIST_KEYS = frozenset(
    {"_comment", "ignore_paths", "ignore_extensions", "accepted_divergences"}
)
PROTECTED_IGNORE_PATHS = frozenset(
    {"console/assets/**", "console/static/**", "pages/claims/**"}
)
PROTECTED_IGNORE_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".svg",
        ".wasm",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp4",
        ".mp3",
        ".pdf",
        ".zip",
        ".gz",
        ".br",
        ".map",
    }
)


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


def _strip_unquoted_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote != "'":
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character == "#" and quote is None:
            return line[:index].rstrip()
    return line.rstrip()


def _tokenize_shell_command(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _job_commands(block: str) -> list[list[str]]:
    lines = block.splitlines()
    commands: list[list[str]] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)(-\s+)?run:\s*(.*?)\s*$", lines[index])
        if match is None:
            index += 1
            continue
        run_indent = len(match.group(1)) + (2 if match.group(2) else 0)
        marker = _strip_unquoted_comment(match.group(3)).strip()
        content: list[str] = []
        index += 1
        if marker and not re.fullmatch(r"[|>][+-]?", marker):
            content.append(marker)
        else:
            while index < len(lines):
                line = lines[index]
                if line.strip():
                    indentation = len(line) - len(line.lstrip())
                    if indentation <= run_indent:
                        break
                content.append(line.lstrip())
                index += 1

        fragments: list[str] = []
        for raw_line in content:
            active = _strip_unquoted_comment(raw_line).strip()
            if not active:
                if fragments:
                    commands.append(_tokenize_shell_command(" ".join(fragments)))
                    fragments = []
                continue
            continued = active.endswith("\\")
            fragments.append(active[:-1].rstrip() if continued else active)
            if not continued:
                commands.append(_tokenize_shell_command(" ".join(fragments)))
                fragments = []
        if fragments:
            commands.append(_tokenize_shell_command(" ".join(fragments)))
    return commands


def _wrapper_invocations(commands: list[list[str]], invocation: str) -> list[list[str]]:
    prefix = shlex.split(invocation)
    return [
        command
        for command in commands
        if command[: len(prefix)] == prefix
        and not any(token in SHELL_CONTROL_TOKENS for token in command)
    ]


def _argument_values(command: list[str], argument: str) -> list[str | None]:
    values: list[str | None] = []
    for index, token in enumerate(command):
        if token == argument:
            values.append(command[index + 1] if index + 1 < len(command) else None)
    return values


def _active_block_lines(block: str) -> list[str]:
    return [
        active
        for line in block.splitlines()
        if (active := _strip_unquoted_comment(line).strip())
    ]


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

    try:
        baseline_commands = _job_commands(baseline)
    except ValueError as exc:
        errors.append(f"protected-base job contains invalid shell syntax: {exc}")
        baseline_commands = []
    try:
        candidate_commands = _job_commands(candidate)
    except ValueError as exc:
        errors.append(f"candidate job contains invalid shell syntax: {exc}")
        candidate_commands = []

    baseline_invocations = _wrapper_invocations(baseline_commands, BASELINE_INVOCATION)
    candidate_invocations = _wrapper_invocations(candidate_commands, CANDIDATE_INVOCATION)
    if len(baseline_invocations) != 1:
        errors.append("protected-base job must invoke the baseline wrapper exactly once")
    elif _argument_values(baseline_invocations[0], "--allow"):
        errors.append("protected-base job must not receive an HF drift allowlist")
    if len(candidate_invocations) != 1:
        errors.append("candidate job must invoke the candidate wrapper exactly once")
    elif _argument_values(candidate_invocations[0], "--allow") != [
        "candidate/.github/hf-module-drift-allow.json"
    ]:
        errors.append("candidate job must receive exactly its same-checkout allowlist")
    for label, block, invocations, source_ref in (
        (
            "protected-base",
            baseline,
            baseline_invocations,
            "github.event.pull_request.base.sha",
        ),
        (
            "candidate",
            candidate,
            candidate_invocations,
            "github.event.pull_request.head.sha",
        ),
    ):
        command = invocations[0] if len(invocations) == 1 else []
        if _argument_values(command, "--tools-script") != [
            "tools/.github/scripts/hf_module_drift_check.py"
        ]:
            errors.append(f"{label} job must use the pinned organization comparator once")
        if _argument_values(command, "--github-ref") != ["$SOURCE_REF"]:
            errors.append(f"{label} wrapper must receive the admitted SOURCE_REF once")
        active_lines = _active_block_lines(block)
        source_binding = f"SOURCE_REF: ${{{{ {source_ref} }}}}"
        if active_lines.count(source_binding) != 1:
            errors.append(f"{label} job is not bound to its exact pull-request SHA")
        pinned_refs = [
            match.group(1)
            for line in active_lines
            if (match := re.fullmatch(r"ref:\s*([0-9a-f]{40})", line))
        ]
        if len(pinned_refs) != 1:
            errors.append(f"{label} job must contain one immutable tools revision")
        active_text = "\n".join(active_lines)
        for suppressor in FAILURE_SUPPRESSORS:
            if suppressor in active_text:
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
            if not isinstance(allowlist, dict):
                errors.append("HF drift allowlist must be a JSON object")
                accepted = None
            else:
                unknown_keys = sorted(set(allowlist) - ALLOWED_ALLOWLIST_KEYS)
                if unknown_keys:
                    errors.append(f"HF drift allowlist has unknown policy keys: {unknown_keys!r}")
                for key, protected in (
                    ("ignore_paths", PROTECTED_IGNORE_PATHS),
                    ("ignore_extensions", PROTECTED_IGNORE_EXTENSIONS),
                ):
                    values = allowlist.get(key, [])
                    if not isinstance(values, list) or any(
                        not isinstance(value, str) for value in values
                    ):
                        errors.append(f"{key} must be an array of strings")
                        continue
                    if len(values) != len(set(values)):
                        errors.append(f"{key} must not contain duplicates")
                    unexpected = sorted(set(values) - protected)
                    if unexpected:
                        errors.append(f"{key} broadens protected exclusions: {unexpected!r}")
                accepted = allowlist.get("accepted_divergences")
            if accepted is not None and not isinstance(accepted, dict):
                errors.append("accepted_divergences must be a JSON object")
            elif isinstance(accepted, dict):
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
