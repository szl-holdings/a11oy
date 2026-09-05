# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
from pathlib import Path

COMMAND = Path("a11oy_command_center.py")
DOCKER = Path("Dockerfile")
HTML = Path("web/command_v2.html")


def test_command_v2_is_registered_before_the_command_catchall() -> None:
    source = COMMAND.read_text(encoding="utf-8")
    ast.parse(source)
    assert 'V2_MOUNTS = ("/command-v2",)' in source
    assert 'for path in V2_MOUNTS:' in source
    assert 'list(V2_MOUNTS) + [path for path, _name in SPECIFIC]' in source
    assert 'status_code=503' in source
    assert source.index('V2_MOUNTS = ("/command-v2",)') < source.index('CATCHALL = "/command/{rest:path}"')


def test_command_v2_exact_source_is_in_the_runtime_image() -> None:
    docker = DOCKER.read_text(encoding="utf-8")
    assert docker.count("COPY web/command_v2.html ./web/command_v2.html") == 1
    assert docker.index("COPY web/command_v2.html ./web/command_v2.html") < docker.index("ENV PORT=7860")


def test_command_v2_surface_is_mobile_keyboard_and_truth_safe() -> None:
    html = HTML.read_text(encoding="utf-8")
    for room in (
        'id:"command"',
        'id:"evidence"',
        'id:"governance"',
        'id:"telemetry"',
        'id:"defense"',
        'id:"markets"',
        'id:"models"',
        'id:"diligence"',
    ):
        assert room in html
    for contract in (
        "viewport-fit=cover",
        "min-height:44px",
        "focus-visible",
        "prefers-reduced-motion:reduce",
        "forced-colors:active",
        'aria-modal="true"',
        "Conjecture 1",
        "SAMPLE",
        "UNAVAILABLE",
    ):
        assert contract in html
    for external in ("cdnjs", "googleapis", "jsdelivr", "unpkg.com"):
        assert external not in html
