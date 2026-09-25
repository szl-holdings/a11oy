# SPDX-License-Identifier: Apache-2.0
"""Registration contracts across flat and grouped FastAPI router releases."""
import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient

routes = importlib.import_module("verticals.puriq-markets.runtime.routes")


def test_registration_is_idempotent_and_openapi_exposes_only_declared_operations():
    app = FastAPI()
    routes.register(app)
    count = len(app.router.routes)
    routes.register(app)
    assert len(app.router.routes) == count
    paths = {p: v for p, v in app.openapi()["paths"].items() if p.startswith(routes.PREFIX + "/")}
    expected = {"/providers": {"get"}, "/overview": {"get"}, "/observations/{source}": {"get"},
                "/analytics/v2/signals/{symbol_name}": {"get"},
                "/analytics/v2/quote/{symbol_name}": {"get"},
                "/analytics/v2/portfolio": {"post"}, "/analytics/v2/receipts": {"get"},
                "/analytics/v2/receipts/verify": {"get", "post"}}
    assert {path.removeprefix(routes.PREFIX): set(methods) for path, methods in paths.items()} == expected
    assert TestClient(app).get(routes.PREFIX + "/providers").status_code == 200
