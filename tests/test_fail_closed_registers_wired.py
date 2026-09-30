# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Fail-closed advisory registers must be imported and COPY'd, never painted LIVE."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")
MODULES = (
    "szl_dream_gate",
    "szl_frontier_gate",
    "szl_hf_scout",
    "szl_kernel_hold",
    "szl_jev_gate",
)


def test_advisory_registers_are_wired_and_copied() -> None:
    for name in MODULES:
        alias = f"_{name}"
        assert f"import {name} as {alias}" in SERVE, name
        assert f'{alias}.register(app, ns="a11oy")' in SERVE, name
        assert f"{name}.py" in DOCKER, name
    assert "never LIVE/ALLOW" in SERVE
    assert "likes are not LIVE" in SERVE


def test_advisory_registers_are_not_allowlisted_as_dead_tabs() -> None:
    allow = (ROOT / ".github" / "register-invocation-allowlist.txt").read_text(
        encoding="utf-8"
    )
    for name in MODULES:
        assert name not in {
            line.split("#", 1)[0].strip()
            for line in allow.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }, name
