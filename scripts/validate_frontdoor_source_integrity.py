#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
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

# Explicitly reject corruption signatures observed on this public surface.
# This is intentionally not a universal mojibake detector: a one-character
# denylist for every possible legacy decoding would also reject valid language.
MOJIBAKE_LEADERS = ("\u00c2", "\u00c3", "\u00ce", "\u00cf", "\u00e2", "\u00f0", "\ufffd")
MOJIBAKE_SEQUENCES = ("\u00ef\u00bb\u00bf", "\u00ef\u00bf\u00bd", "\u00d0\u0178\u00d1\u20ac")

REQUIRED_TOP_LEVEL_LINES = ("on:", "permissions:", "jobs:")
REQUIRED_WORKFLOW_TOKENS = (
    "  pull_request:",
    "  schedule:",
    "  workflow_dispatch:",
    "  hf-module-drift:",
    "  hf-runtime-live:",
    "  hf-repository-parity:",
    "verify_hf_repository_parity.py",
    "select_hf_candidate_admission.py",
    "reusable-hf-module-drift-check.yml@",
    "--tools-script tools/.github/scripts/hf_module_drift_check.py",
)
BASELINE_JOB = "hf-module-drift"
CANDIDATE_JOB = "hf-repository-parity"
EXPECTED_TOP_LEVEL_KEYS = frozenset(
    {"name", "on", "permissions", "concurrency", "jobs"}
)
EXPECTED_JOB_KEYS = frozenset(
    {BASELINE_JOB, "hf-runtime-live", CANDIDATE_JOB}
)
EXPECTED_JOB_NAMES = {
    BASELINE_JOB: "Protected base matches immutable HF repository",
    "hf-runtime-live": "Scheduled live HF runtime source witness",
    CANDIDATE_JOB: "Immutable HF repository byte parity",
}
RUNTIME_JOB = "hf-runtime-live"
RUNTIME_WORKFLOW = (
    "szl-holdings/.github/.github/workflows/"
    "reusable-hf-module-drift-check.yml@0816263f1e83734658d6e5a8a7cd3834f36a2054"
)
RUNTIME_INPUTS = {
    "hf-repo": "SZLHOLDINGS/a11oy",
    "mode": "source-bound-baseline",
    "trusted-base-ref": "${{ github.sha }}",
    "candidate-ref": "${{ github.sha }}",
    "source-probe-path": "/api/build-info",
    "dockerfile-path": "Dockerfile",
    "github-ref": "${{ github.sha }}",
    "hf-ref": "main",
}
PYTHON_EXECUTABLE = "$pythonLocation/bin/python3"
BASELINE_INVOCATION = (
    f"{PYTHON_EXECUTABLE} baseline/.github/scripts/verify_hf_repository_parity.py"
)
CANDIDATE_INVOCATION = (
    f"{PYTHON_EXECUTABLE} baseline/.github/scripts/select_hf_candidate_admission.py"
)
TOOLS_ARGUMENT = "--tools-script tools/.github/scripts/hf_module_drift_check.py"
FAILURE_SUPPRESSORS = ("continue-on-error", "--warn-only", "|| true")
SHELL_CONTROL_TOKENS = frozenset({";", "&&", "||", "|", "&", ">", ">>", "<", "<<"})
YAML_MAPPING_RE = re.compile(
    r"^(?P<indent> *)(?P<sequence>-\s+)?"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*|'(?:[^']|'')*'|\"(?:[^\"\\]|\\.)*\")"
    r"\s*:\s*(?P<value>.*)$"
)
CANONICAL_GITHUB_REPO = "$GITHUB_REPOSITORY"
CANONICAL_HF_REPO = "SZLHOLDINGS/a11oy"
CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
HARDEN_RUNNER_ACTION = (
    "step-security/harden-runner@bf7454d06d71f1098171f2acdf0cd4708d7b5920"
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


def _yaml_mapping_line(line: str) -> tuple[int, bool, str, str] | None:
    active = _strip_unquoted_comment(line).rstrip()
    if "\t" in active[: len(active) - len(active.lstrip())]:
        return None
    match = YAML_MAPPING_RE.fullmatch(active)
    if match is None:
        return None
    raw_key = match.group("key")
    if raw_key.startswith('"'):
        try:
            key = json.loads(raw_key)
        except json.JSONDecodeError:
            return None
    elif raw_key.startswith("'"):
        key = raw_key[1:-1].replace("''", "'")
    else:
        key = raw_key
    return (
        len(match.group("indent")),
        match.group("sequence") is not None,
        key,
        match.group("value").strip(),
    )


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
        parsed = _yaml_mapping_line(line)
        if parsed is not None and parsed[2] == key and parsed[3]:
            values.append(parsed[3].strip("\"'"))
    return values


def _step_level_values(block: str, key: str) -> list[str]:
    """Return direct step properties, excluding nested ``with``/``env`` keys."""

    first_active = next((line for line in block.splitlines() if line.strip()), "")
    step_indent = len(first_active) - len(first_active.lstrip())
    values: list[str] = []
    for line in block.splitlines():
        parsed = _yaml_mapping_line(line)
        if parsed is None:
            continue
        indentation, sequence, parsed_key, value = parsed
        direct = (sequence and indentation == step_indent) or (
            not sequence and indentation == step_indent + 2
        )
        if direct and parsed_key == key and value:
            values.append(value.strip("\"'"))
    return values


def _step_level_keys(block: str) -> Counter[str]:
    first_active = next((line for line in block.splitlines() if line.strip()), "")
    step_indent = len(first_active) - len(first_active.lstrip())
    keys: Counter[str] = Counter()
    for line in block.splitlines():
        parsed = _yaml_mapping_line(line)
        if parsed is None:
            continue
        indentation, sequence, key, _value = parsed
        if (sequence and indentation == step_indent) or (
            not sequence and indentation == step_indent + 2
        ):
            keys[key] += 1
    return keys


def _job_level_values(block: str, key: str) -> list[str]:
    return [
        value
        for line in block.splitlines()
        if (parsed := _yaml_mapping_line(line)) is not None
        for indentation, sequence, parsed_key, value in [parsed]
        if indentation == 4 and not sequence and parsed_key == key and value
    ]


def _job_level_has(block: str, key: str) -> bool:
    return any(
        parsed is not None
        and parsed[0] == 4
        and not parsed[1]
        and parsed[2] == key
        for line in block.splitlines()
        for parsed in [_yaml_mapping_line(line)]
    )


def _structural_block_lines(document: str, marker: str) -> list[str] | None:
    lines = document.splitlines()
    marker_parsed = _yaml_mapping_line(marker)
    if marker_parsed is None:
        return None
    marker_indent, marker_sequence, marker_key, marker_value = marker_parsed
    starts = [
        index
        for index, line in enumerate(lines)
        if _yaml_mapping_line(line)
        == (marker_indent, marker_sequence, marker_key, marker_value)
    ]
    if len(starts) != 1:
        return None
    start = starts[0]
    marker_line = _strip_unquoted_comment(lines[start]).rstrip()
    indentation = len(marker_line) - len(marker_line.lstrip())
    result = [marker_line.strip()]
    for line in lines[start + 1 :]:
        active = _strip_unquoted_comment(line).rstrip()
        if not active.strip():
            continue
        current_indent = len(active) - len(active.lstrip())
        if current_indent <= indentation:
            break
        result.append(active.strip())
    return result


def _validate_workflow_envelope(workflow: str) -> list[str]:
    errors: list[str] = []
    if _structural_block_lines(workflow, "  pull_request:") != [
        "pull_request:",
        "branches: [main]",
    ]:
        errors.append("HF drift workflow must use the canonical main pull-request trigger")
    if _structural_block_lines(workflow, "permissions:") != [
        "permissions:",
        "contents: read",
    ]:
        errors.append("HF drift workflow permissions must remain read-only")
    for forbidden in ("env", "defaults"):
        if any(
            parsed is not None
            and parsed[0] == 0
            and not parsed[1]
            and parsed[2] == forbidden
            for line in workflow.splitlines()
            for parsed in [_yaml_mapping_line(line)]
        ):
            errors.append(f"HF drift workflow must not define top-level {forbidden}")
    return errors


def _validate_restricted_yaml_shape(workflow: str) -> list[str]:
    """Reject YAML features that can change meaning outside the line parser.

    The committed workflow deliberately uses a small block-style YAML subset.
    Keeping that subset explicit prevents a later mapping, quoted duplicate key,
    flow mapping, anchor, or alias from overriding the canonical structure while
    this standard-library validator continues to inspect an earlier copy.
    """

    errors: list[str] = []
    lines = workflow.splitlines()
    top_level = Counter()
    job_keys = Counter()
    jobs_start: int | None = None

    for index, line in enumerate(lines):
        active = _strip_unquoted_comment(line).rstrip()
        if not active.strip():
            continue
        # GitHub expressions contain braces but are scalar substitutions, not
        # YAML flow collections. Remove only complete expressions before the
        # flow-style check.
        without_expressions = re.sub(r"\$\{\{.*?\}\}", "", active)
        if "{" in without_expressions or "}" in without_expressions:
            errors.append(
                f"HF drift workflow must not use flow mappings (line {index + 1})"
            )
        stripped = active.lstrip()
        if re.search(r"(?:^|[\s:\[,])-?\s*[&*][^\s,\]}]+", stripped):
            errors.append(
                f"HF drift workflow must not use YAML anchors or aliases (line {index + 1})"
            )
        if stripped in {"---", "..."} or re.match(r"^-?\s*[?!](?:!\S*)?\s", stripped):
            errors.append(
                f"HF drift workflow uses unsupported YAML syntax (line {index + 1})"
            )

        parsed = _yaml_mapping_line(line)
        if parsed is None:
            continue
        active_match = YAML_MAPPING_RE.fullmatch(_strip_unquoted_comment(line).rstrip())
        if active_match is not None and active_match.group("key").startswith(("'", '"')):
            errors.append(
                f"HF drift workflow must not use quoted mapping keys (line {index + 1})"
            )
        indentation, sequence, key, value = parsed
        if indentation == 0 and not sequence:
            top_level[key] += 1
            if key == "jobs" and value == "" and jobs_start is None:
                jobs_start = index

    if jobs_start is not None:
        for index in range(jobs_start + 1, len(lines)):
            parsed = _yaml_mapping_line(lines[index])
            if parsed is None:
                continue
            indentation, sequence, key, _value = parsed
            if indentation == 0 and not sequence:
                break
            if indentation == 2 and not sequence:
                job_keys[key] += 1

    duplicate_top = sorted(key for key, count in top_level.items() if count != 1)
    if duplicate_top:
        errors.append(
            f"HF drift workflow has duplicate top-level keys: {duplicate_top!r}"
        )
    unexpected_top = sorted(set(top_level) - EXPECTED_TOP_LEVEL_KEYS)
    missing_top = sorted(EXPECTED_TOP_LEVEL_KEYS - set(top_level))
    if unexpected_top or missing_top:
        errors.append(
            "HF drift workflow top-level keys are not canonical: "
            f"missing={missing_top!r}, unexpected={unexpected_top!r}"
        )
    duplicate_jobs = sorted(key for key, count in job_keys.items() if count != 1)
    if duplicate_jobs:
        errors.append(f"HF drift workflow has duplicate job keys: {duplicate_jobs!r}")
    unexpected_jobs = sorted(set(job_keys) - EXPECTED_JOB_KEYS)
    missing_jobs = sorted(EXPECTED_JOB_KEYS - set(job_keys))
    if unexpected_jobs or missing_jobs:
        errors.append(
            "HF drift workflow job keys are not canonical: "
            f"missing={missing_jobs!r}, unexpected={unexpected_jobs!r}"
        )

    # Every step is also a deliberately small mapping. Reject duplicate keys in
    # a step even when the duplicate would otherwise be ignored by a helper
    # looking for the canonical block-form mapping.
    for job_name in (BASELINE_JOB, CANDIDATE_JOB):
        block = _job_block(workflow, job_name)
        if block is None:
            continue
        block_lines = block.splitlines()
        job_level_keys = Counter()
        steps_indexes: list[int] = []
        for index, line in enumerate(block_lines):
            parsed = _yaml_mapping_line(line)
            if parsed is None:
                continue
            indentation, sequence, key, value = parsed
            if indentation == 4 and not sequence:
                job_level_keys[key] += 1
                if key == "steps" and value == "":
                    steps_indexes.append(index)
        duplicate_job_level = sorted(
            key for key, count in job_level_keys.items() if count != 1
        )
        if duplicate_job_level:
            errors.append(
                f"{job_name} job has duplicate keys: {duplicate_job_level!r}"
            )
        if len(steps_indexes) == 1:
            for index in range(steps_indexes[0] + 1, len(block_lines)):
                line = block_lines[index]
                active = _strip_unquoted_comment(line).rstrip()
                if not active.strip():
                    continue
                indentation = len(active) - len(active.lstrip())
                if indentation <= 4:
                    break
                if indentation == 6:
                    parsed = _yaml_mapping_line(line)
                    if parsed is None or not parsed[1]:
                        errors.append(
                            f"{job_name} job has an unsupported step declaration "
                            f"(line {index + 1} of the job)"
                        )
        for position, step in enumerate(_step_blocks(block), start=1):
            step_lines = step.splitlines()
            first_active = next((line for line in step_lines if line.strip()), "")
            step_indent = len(first_active) - len(first_active.lstrip())
            keys = Counter()
            for line in step_lines:
                parsed = _yaml_mapping_line(line)
                if parsed is None:
                    continue
                indentation, sequence, key, _value = parsed
                if (sequence and indentation == step_indent) or (
                    not sequence and indentation == step_indent + 2
                ):
                    keys[key] += 1
            duplicates = sorted(key for key, count in keys.items() if count != 1)
            if duplicates:
                errors.append(
                    f"{job_name} step {position} has duplicate keys: {duplicates!r}"
                )
    return errors


def _validate_trigger_and_runtime(workflow: str) -> list[str]:
    errors: list[str] = []
    workflow_names = [
        parsed[3].strip("\"'")
        for line in workflow.splitlines()
        if (parsed := _yaml_mapping_line(line)) is not None
        and parsed[0] == 0
        and not parsed[1]
        and parsed[2] == "name"
    ]
    if workflow_names != ["HF Space module-drift guard"]:
        errors.append("HF drift workflow display name is not canonical")
    trigger = _structural_block_lines(workflow, "on:")
    if trigger != [
        "on:",
        "pull_request:",
        "branches: [main]",
        "schedule:",
        "- cron: '37 6 * * 1'",
        "workflow_dispatch:",
    ]:
        errors.append("HF drift workflow trigger set and schedule must be canonical")

    runtime = _job_block(workflow, RUNTIME_JOB)
    if runtime is None:
        return errors + ["HF drift workflow is missing the runtime witness job"]
    expected_runtime_keys = frozenset({"name", "if", "uses", "with"})
    runtime_values: dict[str, list[str]] = {
        key: _job_level_values(runtime, key) for key in expected_runtime_keys - {"with"}
    }
    if runtime_values != {
        "name": [EXPECTED_JOB_NAMES[RUNTIME_JOB]],
        "if": ["github.event_name != 'pull_request'"],
        "uses": [RUNTIME_WORKFLOW],
    }:
        errors.append("runtime witness job identity is not canonical")
    if _nested_mapping(runtime, "with") != RUNTIME_INPUTS:
        errors.append("runtime witness job inputs are not canonical")
    observed_keys = Counter()
    for line in runtime.splitlines():
        parsed = _yaml_mapping_line(line)
        if parsed is not None and parsed[0] == 4 and not parsed[1]:
            observed_keys[parsed[2]] += 1
    if set(observed_keys) != expected_runtime_keys or any(
        count != 1 for count in observed_keys.values()
    ):
        errors.append("runtime witness job keys are not canonical")

    job_names: list[str] = []
    for job_name in EXPECTED_JOB_KEYS:
        block = _job_block(workflow, job_name)
        names = [] if block is None else _job_level_values(block, "name")
        if names != [EXPECTED_JOB_NAMES[job_name]]:
            errors.append(f"{job_name} display name is not canonical")
        else:
            job_names.extend(names)
    if len(job_names) != len(set(job_names)):
        errors.append("HF drift workflow job display names must be unique")
    return errors


def _step_blocks(block: str) -> list[str]:
    lines = block.splitlines()
    try:
        steps_index = next(
            index
            for index, line in enumerate(lines)
            if _yaml_mapping_line(line) == (4, False, "steps", "")
        )
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
        parsed = _yaml_mapping_line(line)
        if indentation == steps_indent + 2 and parsed is not None and parsed[1]:
            starts.append(index)
    return [
        "\n".join(lines[start : starts[position + 1] if position + 1 < len(starts) else end])
        for position, start in enumerate(starts)
    ]


def _nested_mapping(block: str, parent: str) -> dict[str, str] | None:
    lines = block.splitlines()
    parent_matches: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        parsed = _yaml_mapping_line(line)
        if parsed is not None and not parsed[1] and parsed[2:] == (parent, ""):
            parent_matches.append((index, parsed[0]))
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
        parsed = _yaml_mapping_line(line)
        if parsed is None or parsed[1] or not parsed[3] or parsed[2] in result:
            return None
        result[parsed[2]] = parsed[3].strip("\"'")
    return result


def _expected_command(*, candidate: bool) -> list[str]:
    checkout = "baseline"
    report = "hf-repository-parity.out.json" if candidate else "hf-current-base-parity.out.json"
    script = (
        "select_hf_candidate_admission.py"
        if candidate
        else "verify_hf_repository_parity.py"
    )
    command = [
        PYTHON_EXECUTABLE,
        f"{checkout}/.github/scripts/{script}",
        "--tools-script",
        "tools/.github/scripts/hf_module_drift_check.py",
        "--github-repo",
        CANONICAL_GITHUB_REPO,
    ]
    if candidate:
        command.extend(["--base-ref", "$BASE_REF"])
    command.extend(
        [
            "--github-ref",
            "$SOURCE_REF",
            "--hf-repo",
            CANONICAL_HF_REPO,
        ]
    )
    command.extend(["--report-out", report])
    return command


def _validate_checkout_steps(
    block: str,
    *,
    label: str,
    source_path: str,
    source_ref: str,
    report_path: str,
) -> list[str]:
    errors: list[str] = []
    steps = _step_blocks(block)
    uses = Counter(value for step in steps for value in _property_values(step, "uses"))
    if len(steps) != 6 or uses != EXPECTED_ACTION_COUNTS:
        errors.append(f"{label} job must contain only the six canonical proof steps")
    if _job_level_values(block, "if") != ["github.event_name == 'pull_request'"]:
        errors.append(f"{label} job must use the exact pull-request predicate")
    if _job_level_values(block, "runs-on") != ["ubuntu-latest"]:
        errors.append(f"{label} job must use the canonical GitHub-hosted runner")
    if _job_level_values(block, "timeout-minutes") != ["15"]:
        errors.append(f"{label} job must retain the canonical timeout")
    job_keys = Counter(
        parsed[2]
        for line in block.splitlines()
        if (parsed := _yaml_mapping_line(line)) is not None
        and parsed[0] == 4
        and not parsed[1]
    )
    expected_job_keys = frozenset({"name", "if", "runs-on", "timeout-minutes", "steps"})
    if set(job_keys) != expected_job_keys or any(count != 1 for count in job_keys.values()):
        errors.append(f"{label} job keys are not canonical")
    for forbidden in ("env", "defaults", "container", "needs", "strategy", "permissions"):
        if _job_level_has(block, forbidden):
            errors.append(f"{label} job must not define job-level {forbidden}")

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

    conditional_steps = [
        step
        for step in steps
        if _property_values(step, "if")
        and _property_values(step, "uses") != [UPLOAD_ARTIFACT_ACTION]
    ]
    if conditional_steps:
        errors.append(f"{label} job must execute every canonical proof step")

    run_steps = [step for step in steps if _property_values(step, "run")]
    if len(run_steps) != 1:
        errors.append(f"{label} job must contain exactly one proof run step")
    else:
        expected_env = {
            "GITHUB_TOKEN": "${{ github.token }}",
            "SOURCE_REF": source_ref,
        }
        if label == "candidate":
            expected_env["SOURCE_REF"] = "${{ github.event.pull_request.head.sha }}"
            expected_env["BASE_REF"] = "${{ github.event.pull_request.base.sha }}"
        if _nested_mapping(run_steps[0], "env") != expected_env:
            errors.append(f"{label} proof step environment is not canonical")
        if _property_values(run_steps[0], "if"):
            errors.append(f"{label} proof run step must not be conditionally skipped")
    setup_steps = [
        step
        for step in steps
        if _property_values(step, "uses") == [SETUP_PYTHON_ACTION]
    ]
    if len(setup_steps) != 1 or _property_values(
        setup_steps[0], "python-version"
    ) != ["3.12"]:
        errors.append(f"{label} job must use the canonical Python runtime")
    upload_steps = [
        step
        for step in steps
        if _property_values(step, "uses") == [UPLOAD_ARTIFACT_ACTION]
    ]
    if len(upload_steps) != 1 or any(
        _property_values(upload_steps[0], key) != expected
        for key, expected in (
            ("if", ["always()"]),
            ("path", [report_path]),
            ("if-no-files-found", ["error"]),
        )
    ):
        errors.append(f"{label} job must retain the fail-closed proof upload")
    if _property_values(block, "shell"):
        errors.append(f"{label} job must not override the proof shell")

    source_step_name = (
        "Checkout exact protected base verifier"
        if label == "protected-base"
        else "Checkout exact protected-base verifier"
    )
    run_step_name = (
        "Prove stable immutable deployed-base repository parity"
        if label == "protected-base"
        else "Prove the candidate introduces no unmanaged deployed-byte drift"
    )
    upload_step_name = (
        "Upload immutable deployed-base proof"
        if label == "protected-base"
        else "Upload immutable candidate repository parity report"
    )
    artifact_name = "hf-current-base-parity" if label == "protected-base" else "hf-repository-parity"
    expected_env = {
        "GITHUB_TOKEN": "${{ github.token }}",
        "SOURCE_REF": source_ref,
    }
    if label == "candidate":
        expected_env = {
            "GITHUB_TOKEN": "${{ github.token }}",
            "BASE_REF": "${{ github.event.pull_request.base.sha }}",
            "SOURCE_REF": "${{ github.event.pull_request.head.sha }}",
        }
    expected_steps = (
        (
            "Harden runner",
            frozenset({"name", "uses", "with"}),
            {"uses": [HARDEN_RUNNER_ACTION]},
            {"with": {"egress-policy": "audit"}},
        ),
        (
            source_step_name,
            frozenset({"name", "uses", "with"}),
            {"uses": [CHECKOUT_ACTION]},
            {
                "with": {
                    "path": source_path,
                    "ref": source_ref,
                    "persist-credentials": "false",
                }
            },
        ),
        (
            "Checkout exact reusable tools revision",
            frozenset({"name", "uses", "with"}),
            {"uses": [CHECKOUT_ACTION]},
            {
                "with": {
                    "repository": TOOLS_REPOSITORY,
                    "ref": TOOLS_REVISION,
                    "path": "tools",
                    "persist-credentials": "false",
                }
            },
        ),
        (
            "Set up Python",
            frozenset({"name", "uses", "with"}),
            {"uses": [SETUP_PYTHON_ACTION]},
            {"with": {"python-version": "3.12"}},
        ),
        (
            run_step_name,
            frozenset({"name", "env", "run"}),
            {"run": ["|"]},
            {"env": expected_env},
        ),
        (
            upload_step_name,
            frozenset({"name", "if", "uses", "with"}),
            {"if": ["always()"], "uses": [UPLOAD_ARTIFACT_ACTION]},
            {
                "with": {
                    "name": artifact_name,
                    "path": report_path,
                    "if-no-files-found": "error",
                    "retention-days": "90",
                }
            },
        ),
    )
    if len(steps) == len(expected_steps):
        for position, (step, expected) in enumerate(zip(steps, expected_steps), start=1):
            expected_name, expected_keys, expected_values, expected_nested = expected
            if _step_level_values(step, "name") != [expected_name]:
                errors.append(f"{label} step {position} name is not canonical")
            keys = _step_level_keys(step)
            if set(keys) != expected_keys or any(count != 1 for count in keys.values()):
                errors.append(f"{label} step {position} keys are not canonical")
            for key, values in expected_values.items():
                if _step_level_values(step, key) != values:
                    errors.append(f"{label} step {position} {key} is not canonical")
            for parent, values in expected_nested.items():
                if _nested_mapping(step, parent) != values:
                    errors.append(f"{label} step {position} {parent} inputs are not canonical")
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
            report_path="hf-current-base-parity.out.json",
        )
    )
    # The v1 lifecycle successor delegates the post-deployment job's
    # exact temporal and command contract to the dedicated standard-
    # library validator. The legacy candidate-fixture path remains
    # below so its adversarial self-tests retain full coverage.
    if "lifecycle: post-deployment-repository-parity/v1" in workflow:
        return errors
    errors.extend(
        _validate_checkout_steps(
            candidate,
            label="candidate",
            source_path="baseline",
            source_ref="${{ github.event.pull_request.base.sha }}",
            report_path="hf-repository-parity.out.json",
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
        errors.append(
            "candidate job must invoke the protected-base admission controller "
            "exactly once"
        )
    if len(candidate_invocations) == 1 and _argument_values(
        candidate_invocations[0], "--allow"
    ):
        errors.append("candidate job must not receive an HF drift allowlist")
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
        expected_base_refs = ["$BASE_REF"] if label == "candidate" else []
        if _argument_values(command, "--base-ref") != expected_base_refs:
            errors.append(f"{label} wrapper must receive the exact protected BASE_REF once")
        active_lines = _active_block_lines(block)
        active_text = "\n".join(active_lines)
        for suppressor in FAILURE_SUPPRESSORS:
            if suppressor in active_text:
                errors.append(f"{label} job contains failure suppressor: {suppressor}")
    return errors


def _read_strict_utf8(root: Path, relative: Path) -> tuple[str | None, list[str]]:
    path = root / relative
    try:
        root_resolved = root.resolve(strict=True)
        path_resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        return None, [f"missing or unresolved file: {relative.as_posix()}: {exc}"]
    if path.is_symlink() or root_resolved not in path_resolved.parents:
        return None, [f"symlink or path escape is forbidden: {relative.as_posix()}"]
    cursor = path.parent
    while cursor != root:
        if cursor.is_symlink():
            return None, [f"symlink or path escape is forbidden: {relative.as_posix()}"]
        if cursor.parent == cursor:
            return None, [f"path is outside validation root: {relative.as_posix()}"]
        cursor = cursor.parent
    if not path.is_file():
        return None, [f"missing file: {relative.as_posix()}"]

    raw = path.read_bytes()
    errors: list[str] = []
    if b"\xef\xbb\xbf" in raw:
        errors.append(f"UTF-8 BOM codepoint is forbidden: {relative.as_posix()}")
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
        errors.extend(_validate_restricted_yaml_shape(workflow))
        errors.extend(_validate_trigger_and_runtime(workflow))
        errors.extend(_validate_workflow_envelope(workflow))
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
        duplicate_json_keys: list[str] = []

        def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    duplicate_json_keys.append(key)
                result[key] = value
            return result

        try:
            allowlist = json.loads(allowlist_text, object_pairs_hook=_unique_object)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid HF drift allowlist: {exc}")
        else:
            if duplicate_json_keys:
                errors.append(
                    f"HF drift allowlist has duplicate JSON keys: {sorted(set(duplicate_json_keys))!r}"
                )
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
                if "accepted_divergences" not in allowlist:
                    errors.append("accepted_divergences must be present")
                accepted = allowlist.get("accepted_divergences")
            if accepted is not None and not isinstance(accepted, dict):
                errors.append("accepted_divergences must be a JSON object")
            elif isinstance(accepted, dict):
                if accepted:
                    errors.append("accepted divergences must be empty")
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
        for sequence in MOJIBAKE_SEQUENCES:
            count = content.count(sequence)
            if count:
                errors.append(
                    f"mojibake sequence {sequence!r} in "
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
