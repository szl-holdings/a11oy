# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""QA input-hardening regression tests (QA squad, 2026-06-04).

While stress/edge-testing the live rosie Space, the UNAY + Khipu-LMDB v2 POST
handlers returned an opaque HTTP 500 on empty / malformed / wrong-type JSON
bodies (unguarded ``await request.json()`` followed by ``.get()`` on a non-dict):

  POST /api/rosie/v2/unay/remember     -> 500 on empty / malformed / array
  POST /api/rosie/v2/unay/recall       -> 500 on empty / malformed / array
  POST /api/rosie/v2/khipu/lmdb/append -> 500 on empty / malformed / array
  POST /api/rosie/v2/khipu/replicate   -> 500 on empty / malformed / array

Every public POST surface must answer with a clean 4xx and never a 500 on bad
input. These tests mount the REAL szl_unay_routes module on a minimal app via
szl_unay_routes.register() — the exact production code path, no mocks of the
handlers themselves.
"""
import os
import tempfile

import pytest

pytest.importorskip("lmdb")
pytest.importorskip("fastapi")
starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

os.environ.setdefault("UNAY_DATA_DIR", tempfile.mkdtemp(prefix="unay_qa_"))

from fastapi import FastAPI  # noqa: E402

import szl_unay_routes  # noqa: E402


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    info = szl_unay_routes.register(app, ns="rosie")
    assert info.get("registered") is True
    return TestClient(app)


POST_HANDLERS = [
    "/api/rosie/v2/unay/remember",
    "/api/rosie/v2/unay/recall",
    "/api/rosie/v2/khipu/lmdb/append",
    "/api/rosie/v2/khipu/replicate",
]


@pytest.mark.parametrize("path", POST_HANDLERS)
@pytest.mark.parametrize("payload", [b"", b"{not json"])
def test_bad_body_is_400_not_500(client, path, payload):
    r = client.post(path, content=payload)
    assert r.status_code != 500, f"{path} returned 500 on bad input"
    assert r.status_code == 400


@pytest.mark.parametrize("path", POST_HANDLERS)
def test_array_body_is_400_not_500(client, path):
    r = client.post(path, json=[1, 2, 3])
    assert r.status_code != 500, f"{path} returned 500 on array body"
    assert r.status_code == 400


# --- valid paths still work (regression lock) -------------------------------

def test_remember_valid_ok(client):
    r = client.post("/api/rosie/v2/unay/remember", json={"text": "hello world"})
    assert r.status_code == 200


def test_remember_missing_text_is_400(client):
    r = client.post("/api/rosie/v2/unay/remember", json={"meta": {}})
    assert r.status_code == 400


def test_recall_valid_ok(client):
    r = client.post("/api/rosie/v2/unay/recall", json={"q": "hello"})
    assert r.status_code == 200


def test_recall_missing_query_is_400(client):
    r = client.post("/api/rosie/v2/unay/recall", json={"k": 5})
    assert r.status_code == 400


def test_lmdb_append_valid_ok(client):
    r = client.post("/api/rosie/v2/khipu/lmdb/append", json={"action": "note"})
    assert r.status_code == 200


def test_replicate_empty_list_ok(client):
    r = client.post("/api/rosie/v2/khipu/replicate", json={"receipts": []})
    assert r.status_code == 200
    assert r.json().get("accepted") == 0


def test_replicate_non_list_receipts_is_400(client):
    r = client.post("/api/rosie/v2/khipu/replicate", json={"receipts": "notalist"})
    assert r.status_code == 400


def test_replicate_garbage_receipts_rejected_not_500(client):
    """Non-dict / digest-less entries are counted as rejected, never crash."""
    r = client.post("/api/rosie/v2/khipu/replicate",
                    json={"receipts": [1, 2, {"no": "digest"}]})
    assert r.status_code == 200
    assert r.json().get("rejected") == 3


# --- substrate sanity: injection string carried as opaque payload -----------

def test_remember_injection_string_not_reflected(client):
    r = client.post("/api/rosie/v2/unay/remember",
                    json={"text": "<script>alert(1)</script> DROP TABLE x"})
    assert r.status_code == 200
    assert "<script>" not in r.text
