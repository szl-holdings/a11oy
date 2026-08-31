# SPDX-License-Identifier: Apache-2.0
"""Regression guard for Docker daemon import depth on PR image builds."""

import hashlib
import json
from pathlib import Path
import shlex


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "docker-build.yml"
RUNTIME_LAYER_BUDGET = 110
COPY_SOURCE_ALLOWLIST_COUNT = 550
COPY_SOURCE_ALLOWLIST_SHA256 = (
    "1aa2f1eacb990dcab973343d2460ed755b63e4762d543df0174839881695cd28"
)


def _logical_instructions() -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 0
    lines = DOCKERFILE.read_text(encoding="utf-8").splitlines()
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if not pending:
            start = line_number
        continued = line.endswith("\\")
        pending.append(line[:-1].rstrip() if continued else line)
        if not continued:
            rows.append((start, " ".join(pending)))
            pending = []
    assert not pending, f"unterminated Dockerfile instruction at line {start}"
    return rows


def _runtime_filesystem_instructions() -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    in_runtime = False
    for line_number, line in _logical_instructions():
        if line.upper().startswith("FROM "):
            in_runtime = line.upper().endswith(" AS RUNTIME")
            continue
        if not in_runtime:
            continue
        instruction = line.split(maxsplit=1)[0].upper()
        if instruction in {"RUN", "COPY", "ADD"}:
            rows.append((line_number, instruction))
    return rows


def _copy_sources(instruction: str) -> list[str]:
    payload = instruction.split(maxsplit=1)[1].strip()
    if payload.startswith("["):
        values = json.loads(payload)
        return values[:-1]
    values = shlex.split(payload)
    while values and values[0].startswith("--"):
        values.pop(0)
    return values[:-1]


def test_runtime_image_stays_below_docker_layer_depth_budget() -> None:
    """Leave margin below the daemon depth reached by PR ``load: true`` builds."""
    rows = _runtime_filesystem_instructions()
    assert len(rows) <= RUNTIME_LAYER_BUDGET, (
        f"runtime stage has {len(rows)} filesystem instructions; "
        f"budget is {RUNTIME_LAYER_BUDGET}. Batch explicit COPY sources instead "
        "of disabling the PR image load and smoke test."
    )


def test_layer_batching_keeps_the_explicit_source_allowlist() -> None:
    workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
    copy_sources = {
        source
        for _line, instruction in _logical_instructions()
        if instruction.upper().startswith("COPY ")
        for source in _copy_sources(instruction)
    }
    assert "." not in copy_sources
    assert "./" not in copy_sources
    encoded_allowlist = ("\n".join(sorted(copy_sources)) + "\n").encode("utf-8")
    assert len(copy_sources) == COPY_SOURCE_ALLOWLIST_COUNT
    assert hashlib.sha256(encoded_allowlist).hexdigest() == COPY_SOURCE_ALLOWLIST_SHA256
    assert "load: ${{ github.event_name == 'pull_request' }}" in workflow
    assert "Smoke test image (PR builds — loaded into local daemon)" in workflow
