# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Assembled-production-app ownership guard for budget/token ingress."""

import warnings

warnings.filterwarnings("ignore")

import serve  # noqa: E402


_EXPECTED = {
    "/api/a11oy/v1/token-ingress/status": "GET",
    "/api/a11oy/v1/token-ingress/route": "POST",
    "/api/a11oy/v1/token-ingress/qualify": "POST",
    "/api/a11oy/v1/token-ingress/verification-budget": "POST",
}


def _module(route: object) -> str | None:
    endpoint = getattr(route, "endpoint", None)
    return getattr(endpoint, "__module__", None)


def test_token_ingress_routes_are_owned_and_precede_catchalls() -> None:
    routes = list(serve.app.router.routes)
    spa_index = next(
        index
        for index, route in enumerate(routes)
        if getattr(route, "path", None) == "/{full_path:path}"
    )
    proxy_index = next(
        index
        for index, route in enumerate(routes)
        if getattr(route, "path", None) == "/api/a11oy/{path:path}"
    )

    for path, method in _EXPECTED.items():
        owned = [
            (index, route)
            for index, route in enumerate(routes)
            if getattr(route, "path", None) == path
        ]
        assert len(owned) == 1, f"expected one route owner for {path}, got {len(owned)}"
        index, route = owned[0]
        assert _module(route) == "szl_budget_router"
        assert method in getattr(route, "methods", set())
        assert index < proxy_index
        assert index < spa_index


def test_token_ingress_exposes_no_storage_provider_or_deploy_effector() -> None:
    paths = {
        getattr(route, "path", "")
        for route in serve.app.router.routes
        if _module(route) == "szl_budget_router"
        and "/token-ingress/" in getattr(route, "path", "")
    }
    assert paths == set(_EXPECTED)
    assert not any(
        fragment in path
        for path in paths
        for fragment in (
            "/prefix/write",
            "/repository/read",
            "/provider",
            "/model",
            "/deploy",
        )
    )
