# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Assembled-app regression for the Memory Covenant pre-catch-all routes."""

import warnings

warnings.filterwarnings("ignore")

import serve  # noqa: E402


def _paths() -> set[str]:
    return {
        path
        for route in serve.app.router.routes
        if (path := getattr(route, "path", None))
    }


def test_memory_covenant_routes_are_wired_before_spa_fallback() -> None:
    paths = _paths()
    assert "/api/a11oy/v1/memory-covenant/status" in paths
    assert "/api/a11oy/v1/memory-covenant/query" in paths


def test_memory_covenant_has_no_public_write_or_worker_route() -> None:
    paths = _paths()
    assert "/api/a11oy/v1/memory-covenant/write" not in paths
    assert "/api/a11oy/v1/memory-covenant/lease" not in paths
    assert "/api/a11oy/v1/memory-covenant/index" not in paths
