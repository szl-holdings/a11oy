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
# Exact base 5ec5b66 has 579 explicit COPY sources with SHA-256
# aa11d167572da80452e1247815b1a0e08bbd9ba206f4d859b0b26f8d84ffc48e.
# Steward adds only its four named adapter/reader/projection/lock files, batched
# into one COPY; no original source is removed and the layer budget is unchanged.
# The civilian services surface adds exactly its registrar and package directory.
# The public HF inventory repair adds exactly three reviewed docs sources; the
# prior 585-source allowlist remains pinned separately below.
# Preserve every prior source and the unchanged layer budget, not a broad COPY.
COPY_SOURCE_ALLOWLIST_COUNT = 588
COPY_SOURCE_ALLOWLIST_SHA256 = (
    "371fbd0b54830459ce3096248a7ca33e4ffded466a5f538fd5996b3513947bf9"
)
PRE_CIVILIAN_ALLOWLIST_COUNT = 586
PRE_CIVILIAN_ALLOWLIST_SHA256 = (
    "4c312d5120c7920fe90a197fb47bcde5034699e24993862f88162b1502b063bb"
)
PRE_HF_DOCS_ALLOWLIST_COUNT = 585
PRE_HF_DOCS_ALLOWLIST_SHA256 = (
    "4ca6083c0625d01db45342bf15badb633427c4550c6f1896b30c3b95926f0641"
)
HF_DOCS_COPY_ADDITIONS = {
    "docs/huggingface-ecosystem-manifest.json",
    "docs/huggingface-ecosystem-manifest.schema.json",
    "docs/huggingface.md",
}
CIVILIAN_COPY_ADDITIONS = {
    "a11oy_civilian_observatory.py",
    "civilian_observatory/",
}


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


def test_civilian_packaging_preserves_every_previous_source() -> None:
    sources = {
        source
        for _line, instruction in _logical_instructions()
        if instruction.upper().startswith("COPY ")
        for source in _copy_sources(instruction)
    }
    assert CIVILIAN_COPY_ADDITIONS <= sources
    previous = sources - CIVILIAN_COPY_ADDITIONS
    encoded = ("\n".join(sorted(previous)) + "\n").encode("utf-8")
    assert len(previous) == PRE_CIVILIAN_ALLOWLIST_COUNT
    assert hashlib.sha256(encoded).hexdigest() == PRE_CIVILIAN_ALLOWLIST_SHA256


def test_public_hf_docs_preserve_the_previous_copy_allowlist() -> None:
    sources = {
        source
        for _line, instruction in _logical_instructions()
        if instruction.upper().startswith("COPY ")
        for source in _copy_sources(instruction)
    }
    assert HF_DOCS_COPY_ADDITIONS <= sources
    previous = sources - HF_DOCS_COPY_ADDITIONS
    encoded = ("\n".join(sorted(previous)) + "\n").encode("utf-8")
    assert len(previous) == PRE_HF_DOCS_ALLOWLIST_COUNT
    assert hashlib.sha256(encoded).hexdigest() == PRE_HF_DOCS_ALLOWLIST_SHA256
