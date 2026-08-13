#!/usr/bin/env python3
"""Fail closed on disabled HF drift workflow or corrupted public UTF-8.

This guard intentionally uses only the Python standard library.  It is run from
the independent ``Tests`` workflow so damage to ``hf-module-drift.yml`` cannot
silence the guard that checks it.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
PYTHON_EXECUTABLE = "$pythonLocation/bin/python3"
BASELINE_INVOCATION = (
    f"{PYTHON_EXECUTABLE} baseline/.github/scripts/verify_hf_repository_parity.py"
)
CANDIDATE_INVOCATION = (
    f"{PYTHON_EXECUTABLE} candidate/.github/scripts/verify_hf_repository_parity.py"
)
CANDIDATE_ALLOW_ARGUMENT = "--allow candidate/.github/hf-module-drift-allow.json"
TOOLS_ARGUMENT = "--tools-script tools/.github/scripts/hf_module_drift_check.py"
FAILURE_SUPPRESSORS = ("continue-on-error", "--warn-only", "|| true")
SHELL_CONTROL_TOKENS = frozenset({";", "&&", "||", "|", "&", ">", ">>", "<", "<<"})
CANONICAL_GITHUB_REPO = "$GITHUB_REPOSITORY"
CANONICAL_HF_REPO = "SZLHOLDINGS/a11oy"
CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
HARDEN_RUNNER_ACTION = (
    "step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40"
)
SETUP_PYTHON_ACTION = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
UPLOAD_ARTIFACT_ACTION = (
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
)
TOOLS_REPOSITORY = "szl-holdings/.github"
TOOLS_REVISION = "0816263f1e83734658d6e5a8a7cd3834f36a2054"
EXPECTED_ACTION_COUNTS = Counter(
    {
        HARDEN_RUNNER_ACTION: 1,
        CHECKOUT_ACTION: 2,
        SETUP_PYTHON_ACTION: 1,
        UPLOAD_ARTIFACT_ACTION: 1,
    }
)
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


def _property_values(block: str, key: str) -> list[str]:
    values: list[str] = []
    for line in block.splitlines():
        active = _strip_unquoted_comment(line).strip()
        if active.startswith("- "):
            active = active[2:].lstrip()
        match = re.fullmatch(rf"{re.escape(key)}:\s*(.+)", active)
        if match:
            values.append(match.group(1).strip().strip("\"'"))
    return values


def _step_blocks(block: str) -> list[str]:
    lines = block.splitlines()
    try:
        steps_index = next(index for index, line in enumerate(lines) if line.strip() == "steps:")
    except StopIteration:
        return []
    steps_indent = len(lines[steps_index]) - len(lines[steps_index].lstrip())
    starts: list[int] = []
    end = len(lines)
    for index in range(steps_index + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indentation = len(line) - len(line.lstrip())
        if indentation <= steps_indent:
            end = index
            break
        if indentation == steps_indent + 2 and line.lstrip().startswith("- "):
            starts.append(index)
    return [
        "\n".join(lines[start : starts[position + 1] if position + 1 < len(starts) else end])
        for position, start in enumerate(starts)
    ]


def _nested_mapping(block: str, parent: str) -> dict[str, str] | None:
    lines = block.splitlines()
    parent_matches: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        active = _strip_unquoted_comment(line)
        stripped = active.strip()
        if stripped == f"{parent}:":
            parent_matches.append((index, len(active) - len(active.lstrip())))
    if len(parent_matches) != 1:
        return None
    start, parent_indent = parent_matches[0]
    result: dict[str, str] = {}
    for line in lines[start + 1 :]:
        active = _strip_unquoted_comment(line)
        if not active.strip():
            continue
        indentation = len(active) - len(active.lstrip())
        if indentation <= parent_indent:
            break
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.+)", active.strip())
        if match is None or match.group(1) in result:
            return None
        result[match.group(1)] = match.group(2).strip().strip("\"'")
    return result


def _expected_command(*, candidate: bool) -> list[str]:
    checkout = "candidate" if candidate else "baseline"
    report = "hf-repository-parity.out.json" if candidate else "hf-current-base-parity.out.json"
    command = [
        PYTHON_EXECUTABLE,
        f"{checkout}/.github/scripts/verify_hf_repository_parity.py",
        "--tools-script",
        "tools/.github/scripts/hf_module_drift_check.py",
        "--github-repo",
        CANONICAL_GITHUB_REPO,
        "--github-ref",
        "$SOURCE_REF",
        "--hf-repo",
        CANONICAL_HF_REPO,
    ]
    if candidate:
        command.extend(["--allow", "candidate/.github/hf-module-drift-allow.json"])
    command.extend(["--report-out", report])
    return command


def _validate_checkout_steps(
    block: str,
    *,
    label: str,
    source_path: str,
    source_ref: str,
) -> list[str]:
    errors: list[str] = []
    steps = _step_blocks(block)
    uses = Counter(value for step in steps for value in _property_values(step, "uses"))
    if len(steps) != 6 or uses != EXPECTED_ACTION_COUNTS:
        errors.append(f"{label} job must contain only the six canonical proof steps")

    for path, expected in (
        (
            source_path,
            {
                "uses": [CHECKOUT_ACTION],
                "path": [source_path],
                "ref": [source_ref],
                "persist-credentials": ["false"],
                "repository": [],
            },
        ),
        (
            "tools",
            {
                "uses": [CHECKOUT_ACTION],
                "path": ["tools"],
                "ref": [TOOLS_REVISION],
                "persist-credentials": ["false"],
                "repository": [TOOLS_REPOSITORY],
            },
        ),
    ):
        matches = [step for step in steps if _property_values(step, "path") == [path]]
        if len(matches) != 1:
            errors.append(f"{label} job must contain one canonical {path} checkout")
            continue
        step = matches[0]
        if any(_property_values(step, key) != value for key, value in expected.items()):
            errors.append(f"{label} job has an untrusted {path} checkout identity")

    run_steps = [step for step in steps if _property_values(step, "run")]
    if len(run_steps) != 1:
        errors.append(f"{label} job must contain exactly one proof run step")
    else:
        expected_env = {
            "GITHUB_TOKEN": "${{ github.token }}",
            "SOURCE_REF": source_ref,
        }
        if _nested_mapping(run_steps[0], "env") != expected_env:
            errors.append(f"{label} proof step environment is not canonical")
    if _property_values(block, "shell"):
        errors.append(f"{label} job must not override the proof shell")
    for forbidden in ("env", "defaults", "container"):
        if any(re.fullmatch(rf"    {forbidden}:.*", line) for line in block.splitlines()):
            errors.append(f"{label} job must not define job-level {forbidden}")
    return errors


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

    errors.extend(
        _validate_checkout_steps(
            baseline,
            label="protected-base",
            source_path="baseline",
            source_ref="${{ github.event.pull_request.base.sha }}",
        )
    )
    errors.extend(
        _validate_checkout_steps(
            candidate,
            label="candidate",
            source_path="candidate",
            source_ref="${{ github.event.pull_request.head.sha }}",
        )
    )

    baseline_invocations = _wrapper_invocations(baseline_commands, BASELINE_INVOCATION)
    candidate_invocations = _wrapper_invocations(candidate_commands, CANDIDATE_INVOCATION)
    if len(baseline_commands) != 1 or len(baseline_invocations) != 1:
        errors.append("protected-base job must invoke the baseline wrapper exactly once")
    if len(baseline_invocations) == 1 and _argument_values(
        baseline_invocations[0], "--allow"
    ):
        errors.append("protected-base job must not receive an HF drift allowlist")
    if len(candidate_commands) != 1 or len(candidate_invocations) != 1:
        errors.append("candidate job must invoke the candidate wrapper exactly once")
    if len(candidate_invocations) == 1 and _argument_values(
        candidate_invocations[0], "--allow"
    ) != [
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
        expected_command = _expected_command(candidate=label == "candidate")
        if command != expected_command:
            errors.append(f"{label} job must use the exact canonical parity command")
        if _argument_values(command, "--tools-script") != [
            "tools/.github/scripts/hf_module_drift_check.py"
        ]:
            errors.append(f"{label} job must use the pinned organization comparator once")
        if _argument_values(command, "--github-ref") != ["$SOURCE_REF"]:
            errors.append(f"{label} wrapper must receive the admitted SOURCE_REF once")
        active_lines = _active_block_lines(block)
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
