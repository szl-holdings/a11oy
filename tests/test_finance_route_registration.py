# SPDX-License-Identifier: Apache-2.0
"""Registration contracts across flat and grouped FastAPI router releases."""
import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient

routes = importlib.import_module("verticals.puriq-markets.runtime.routes")


def test_registration_is_idempotent_and_openapi_exposes_only_get():
    app = FastAPI()
    routes.register(app)
    count = len(app.router.routes)
    routes.register(app)
    assert len(app.router.routes) == count
    paths = {p: v for p, v in app.openapi()["paths"].items() if p.startswith(routes.PREFIX + "/")}
    assert set(paths) == {routes.PREFIX + "/providers", routes.PREFIX + "/overview", routes.PREFIX + "/observations/{source}"}
    assert all(set(methods) == {"get"} for methods in paths.values())
    assert TestClient(app).get(routes.PREFIX + "/providers").status_code == 200
