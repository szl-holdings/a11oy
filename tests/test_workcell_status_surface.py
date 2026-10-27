# SPDX-License-Identifier: Apache-2.0
"""Fail-closed checks for the bounded master-workcell status seam.

The workcell report is source-bound integration metadata.  The status page may
display it, but it must not turn transport success into runtime readiness or
upgrade an honest BLOCKED/UNKNOWN label.
"""
from pathlib import Path

import pytest

pytest.importorskip("starlette.testclient")
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "status.html"
SERVE = ROOT / "serve.py"
STATUS = "/api/a11oy/v1/workcell/status"


def test_status_route_has_a_source_tree_page_fallback() -> None:
    source = SERVE.read_text(encoding="utf-8")
    assert 'f = _szl_doc("web/status.html")' in source
    assert 'f = _szl_doc("pages/status.html")' in source
    assert source.index('f = _szl_doc("web/status.html")') < source.index(
        'f = _szl_doc("pages/status.html")'
    )


def test_status_page_binds_the_declared_workcell_contract() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "WORKCELL_URL='/api/a11oy/v1/workcell/status'" in page
    assert "WORKCELL_SCHEMA='szl.master-workcell.v1'" in page
    assert "integration_summary" in page
    assert "Array.isArray(body.nodes)" in page
    assert "source-bound declaration only" in page


def test_workcell_transport_failures_paint_unavailable() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "paintWorkcellUnavailable('network error')" in page
    assert "!r.ok" in page
    assert "await r.json().catch(()=>null)" in page
    assert "invalid or missing workcell contract" in page
    assert "<span class=\"pill r\">UNAVAILABLE</span>" in page


def test_workcell_http_success_never_becomes_live_or_measured() -> None:
    page = PAGE.read_text(encoding="utf-8")
    # HTTP success is checked only as a prerequisite for parsing the declared
    # contract.  No `r.ok` expression may paint a readiness/data label.
    assert "r.ok?'LIVE'" not in page
    assert "r.ok?'MEASURED'" not in page
    assert "r.ok?\"LIVE\"" not in page
    assert "r.ok?\"MEASURED\"" not in page
    assert "HTTP success only permits parsing the declared payload" in page


def test_workcell_backend_is_registered_before_catchalls_and_get_only() -> None:
    import serve

    routes = list(serve.app.router.routes)
    route_index = next(
        i for i, route in enumerate(routes) if getattr(route, "path", None) == STATUS
    )
    catchall = next(
        (i for i, route in enumerate(routes)
         if getattr(route, "path", None) == "/{full_path:path}"),
        len(routes),
    )
    assert route_index < catchall
    methods = getattr(routes[route_index], "methods", set())
    assert methods == {"GET"}


def test_workcell_backend_returns_declared_payload_without_receipt() -> None:
    import serve

    with TestClient(serve.app) as client:
        response = client.get(STATUS)
        post = client.post(STATUS, json={})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["schema"] == "szl.master-workcell.v1"
    assert body["status"] == "BLOCKED"
    assert body["integration_summary"]["runtime"]["status"] == "UNKNOWN"
    assert body["integration_summary"]["provider_publication"]["status"] == "UNKNOWN"
    assert body["read_only"] is True
    assert "receipt" not in body and "signature" not in body and "signed" not in body
    assert post.status_code == 405


def test_unknown_pr_state_cannot_be_promoted() -> None:
    import serve

    with TestClient(serve.app) as client:
        body = client.get(STATUS).json()
    pr = next(node for node in body["nodes"] if node["id"] == "pr.2775")
    assert pr["status"] == "UNKNOWN"
    assert body["status"] == "BLOCKED"


def test_missing_or_malformed_artifact_is_unavailable(monkeypatch, tmp_path) -> None:
    import serve
    import szl_master_workcell

    missing = tmp_path / "missing.json"
    monkeypatch.setattr(szl_master_workcell, "ARTIFACT_PATH", missing)
    with TestClient(serve.app) as client:
        response = client.get(STATUS)
    assert response.status_code == 503
    assert response.json() == {
        "ok": False,
        "schema": "szl.master-workcell.v1",
        "status": "UNAVAILABLE",
        "label": "UNAVAILABLE",
        "read_only": True,
        "reason": "workcell artifact unavailable or invalid",
    }

    malformed = tmp_path / "malformed.json"
    malformed.write_text(
        '{"schema":"szl.master-workcell.v1","integration_summary":[]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(szl_master_workcell, "ARTIFACT_PATH", malformed)
    with TestClient(serve.app) as client:
        response = client.get(STATUS)
    assert response.status_code == 503
    assert response.json()["status"] == "UNAVAILABLE"


def test_workcell_status_and_label_are_displayed_verbatim() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "const label=String(body.label||'UNKNOWN');" in page
    assert "const status=String(body.status||'UNKNOWN');" in page
    assert "String(body.label||'UNKNOWN').toUpperCase()" not in page
    assert "String(body.status||'UNKNOWN').toUpperCase()" not in page
