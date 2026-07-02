"""Ayllu HTTP route-wiring regression guard.

REGRESSION THIS CATCHES: the ayllu handlers annotate `request: "Request"` as a
string forward-ref (because a11oy_ayllu.py uses `from __future__ import
annotations`). FastAPI resolves endpoint annotations with get_type_hints against
the handler's *module* globals. If `Request` is only imported *inside*
register() (function-local), FastAPI cannot resolve the forward-ref, fails to
recognise the special Request parameter, and mis-treats `request` as a REQUIRED
query param — so every GET route 422s with loc=["query","request"] and the POST
handlers never even parse their body. The module-level (guarded) `from fastapi
import Request` in a11oy_ayllu.py is what keeps these green.

A route-*presence* test (see test_demo_critical_routes.py) cannot catch this: the
route IS registered, it just returns 422 instead of running. So this guard boots
the ayllu routes on a bare app and exercises them for real (no mocks, no network).
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import a11oy_ayllu  # noqa: E402


def _client() -> TestClient:
    app = FastAPI()
    a11oy_ayllu.register(app, ns="a11oy")
    return TestClient(app)


def test_roster_returns_200_not_query_param_422():
    r = _client().get("/api/a11oy/v1/ayllu/roster")
    assert r.status_code == 200, (
        "roster GET must be 200. A 422 here is the forward-ref regression where "
        "FastAPI mis-binds `request` as a required query param — re-add the "
        "module-level `from fastapi import Request` in a11oy_ayllu.py. "
        f"Body: {r.text[:300]}"
    )
    d = r.json()
    assert d["count"] == len(a11oy_ayllu.ROSTER) == 11
    assert len(d["personas"]) == 11
    assert "mode" in d["backend"]


def test_page_and_lounge_are_200():
    c = _client()
    assert c.get("/ayllu").status_code == 200
    lr = c.get("/api/a11oy/v1/ayllu/lounge")
    assert lr.status_code == 200
    assert "recent" in lr.json()


def test_ask_empty_body_hits_our_validation_not_fastapi_query_422():
    r = _client().post("/api/a11oy/v1/ayllu/ask", json={})
    assert r.status_code == 422
    err = r.json().get("error")
    assert isinstance(err, str) and ("persona" in err or "prompt" in err), (
        "empty-body ask must reach OUR validation ('persona' and 'prompt' are "
        "required), not FastAPI's query-param 422 (the forward-ref regression). "
        f"Got: {r.json()}"
    )


def test_ask_unknown_persona_is_404():
    r = _client().post(
        "/api/a11oy/v1/ayllu/ask", json={"persona": "nobody", "prompt": "hi"})
    assert r.status_code == 404
