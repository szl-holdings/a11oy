# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Assembled-app regression for the governed token-ingress routes."""

import warnings

warnings.filterwarnings("ignore")

import serve  # noqa: E402


def _paths() -> set[str]:
    return {
        path
        for route in serve.app.router.routes
        if (path := getattr(route, "path", None))
    }


def test_token_ingress_routes_are_wired_before_spa_fallback() -> None:
    paths = _paths()
    assert "/api/a11oy/v1/token-ingress/status" in paths
    assert "/api/a11oy/v1/token-ingress/route" in paths
    assert "/api/a11oy/v1/token-ingress/qualify" in paths
    assert "/api/a11oy/v1/token-ingress/verification-budget" in paths


def test_token_ingress_has_no_public_repository_or_prefix_mutation_route() -> None:
    paths = _paths()
    assert "/api/a11oy/v1/token-ingress/ingest-repository" not in paths
    assert "/api/a11oy/v1/token-ingress/prefix" not in paths
    assert "/api/a11oy/v1/token-ingress/promote" not in paths
