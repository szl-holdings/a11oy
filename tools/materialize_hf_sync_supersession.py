#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Materialize verified-supersession semantics into the canonical HF workflow."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
TARGET_JOB = "Publish and live-verify six domain-native flagship Spaces"
OWNERSHIP_STEP = "Assert the workflow owns exact protected main"
PUBLICATION_STEP = "Publish and verify the v4 vertical estate"
PUBLICATION_RECEIPT_STEP = "Upload immutable vertical publication receipt"
GATE = "steps.exact_main_owner.outputs.publish == 'true'"


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def job_span(lines: list[str]) -> tuple[int, int]:
    pattern = re.compile(
        rf"^\s*name:\s*[\"']?{re.escape(TARGET_JOB)}[\"']?\s*$"
    )
    matches = [index for index, line in enumerate(lines) if pattern.fullmatch(line)]
    if len(matches) != 1:
        raise SystemExit(
            f"target job drifted: expected one {TARGET_JOB!r}, found {len(matches)}"
        )
    name_index = matches[0]
    name_indent = indentation(lines[name_index])
    key_pattern = re.compile(r"^[A-Za-z0-9_-]+:\s*$")
    start = None
    for index in range(name_index - 1, -1, -1):
        if (
            indentation(lines[index]) < name_indent
            and key_pattern.fullmatch(lines[index].strip())
        ):
            start = index
            break
    if start is None:
        raise SystemExit("target job key could not be located")
    job_indent = indentation(lines[start])
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if (
            stripped
            and not stripped.startswith("#")
            and indentation(lines[index]) == job_indent
            and key_pattern.fullmatch(stripped)
        ):
            end = index
            break
    return start, end


def step_span(lines: list[str], name: str) -> tuple[int, int, str]:
    job_start, job_end = job_span(lines)
    pattern = re.compile(
        rf"^(\s*)- name:\s*[\"']?{re.escape(name)}[\"']?\s*$"
    )
    matches: list[tuple[int, str]] = []
    for index in range(job_start, job_end):
        match = pattern.fullmatch(lines[index])
        if match:
            matches.append((index, match.group(1)))
    if len(matches) != 1:
        raise SystemExit(
            f"target step drifted: expected one {name!r}, found {len(matches)}"
        )
    start, prefix = matches[0]
    step_indent = len(prefix)
    end = job_end
    for index in range(start + 1, job_end):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        current = indentation(lines[index])
        if current < step_indent or (
            current == step_indent and lines[index].lstrip().startswith("- name:")
        ):
            end = index
            break
    return start, end, prefix


def upload_artifact_sha(lines: list[str]) -> str:
    start, end, _prefix = step_span(lines, PUBLICATION_RECEIPT_STEP)
    pattern = re.compile(r"^\s*uses:\s*actions/upload-artifact@([0-9a-f]{40})\s*$")
    values = []
    for line in lines[start:end]:
        match = pattern.fullmatch(line)
        if match:
            values.append(match.group(1))
    if len(values) != 1:
        raise SystemExit("publication receipt no longer has one SHA-pinned uploader")
    return values[0]


def expression_body(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("${{") and candidate.endswith("}}"):
        candidate = candidate[3:-2].strip()
    return candidate


def gate_step(lines: list[str], name: str, *, require_always: bool = False) -> None:
    start, end, prefix = step_span(lines, name)
    property_prefix = prefix + "  "
    current_index = None
    current_value = None
    for index in range(start + 1, end):
        if lines[index].startswith(property_prefix + "if:"):
            if current_index is not None:
                raise SystemExit(f"step {name!r} has multiple if properties")
            current_index = index
            current_value = lines[index].split("if:", 1)[1].strip()
    if current_value and GATE in current_value:
        raise SystemExit(f"source ownership gate already exists on {name!r}")
    terms: list[str] = []
    if require_always:
        terms.append("always()")
    if current_value:
        body = expression_body(current_value)
        if body and body != "always()":
            terms.append(f"({body})")
        elif body == "always()" and not require_always:
            terms.append(body)
    terms.append(GATE)
    rendered = property_prefix + "if: ${{ " + " && ".join(terms) + " }}"
    if current_index is None:
        lines.insert(start + 1, rendered)
    else:
        lines[current_index] = rendered


def replace_ownership_step(lines: list[str], uploader_sha: str) -> None:
    start, end, prefix = step_span(lines, OWNERSHIP_STEP)
    slash = "\\"
    replacement = [
        prefix + "- name: " + OWNERSHIP_STEP,
        prefix + "  id: exact_main_owner",
        prefix + "  env:",
        prefix + "    GITHUB_TOKEN: ${{ github.token }}",
        prefix + "  shell: bash",
        prefix + "  run: |",
        prefix + "    set -euo pipefail",
        prefix + "    python3 -B scripts/hf_exact_main_ownership.py " + slash,
        prefix + '      --repository "$GITHUB_REPOSITORY" ' + slash,
        prefix + '      --expected-sha "$GITHUB_SHA" ' + slash,
        prefix + '      --receipt "$RUNNER_TEMP/hf-main-ownership.json" ' + slash,
        prefix + '      --github-output "$GITHUB_OUTPUT"',
        "",
        prefix + "- name: Upload exact-main ownership receipt",
        prefix + "  if: always()",
        prefix + f"  uses: actions/upload-artifact@{uploader_sha}",
        prefix + "  with:",
        prefix
        + "    name: hf-main-ownership-${{ github.run_id }}-${{ github.run_attempt }}",
        prefix + "    path: ${{ runner.temp }}/hf-main-ownership.json",
        prefix + "    if-no-files-found: error",
        prefix + "    retention-days: 90",
    ]
    lines[start:end] = replacement


def validate_materialized(source: str) -> None:
    if source.count("id: exact_main_owner") != 1:
        raise SystemExit("exact-main ownership controller is not unique")
    if source.count("Upload exact-main ownership receipt") != 1:
        raise SystemExit("exact-main receipt uploader is not unique")
    job_start, job_end = job_span(source.splitlines())
    job = "\n".join(source.splitlines()[job_start:job_end])
    if job.count(GATE) < 4:
        raise SystemExit("not every publication-capable step is ownership-gated")
    if "continue-on-error" in job.split(OWNERSHIP_STEP, 1)[1].split("- name:", 1)[0]:
        raise SystemExit("ownership verification may not continue on error")


def main() -> int:
    source = WORKFLOW.read_text(encoding="utf-8")
    if "id: exact_main_owner" in source:
        raise SystemExit("exact-main supersession semantics already exist")
    lines = source.splitlines()
    uploader_sha = upload_artifact_sha(lines)
    replace_ownership_step(lines, uploader_sha)
    gate_step(lines, "Set up Python")
    gate_step(lines, "Install pinned vertical publisher")
    gate_step(lines, PUBLICATION_STEP)
    gate_step(lines, PUBLICATION_RECEIPT_STEP, require_always=True)
    rendered = "\n".join(lines) + "\n"
    validate_materialized(rendered)
    if rendered == source:
        raise SystemExit("workflow did not change")
    WORKFLOW.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
