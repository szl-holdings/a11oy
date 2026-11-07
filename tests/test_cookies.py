"""Cookie recognition ledger contract tests."""
import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import serve
    with TestClient(serve.app) as c:
        yield c


def test_cookies_ledger_is_honest(client):
    r = client.get("/api/a11oy/v1/cookies")
    assert r.status_code == 200
    d = r.json()
    assert d["schema"] == "szl.cookies/v1"
    assert d["label"] == "RECOGNITION_ONLY"
    assert "no monetary value" in d["note"]
    assert d["total_awarded"] == len(d["ledger"]) == len(d["ledger"])


def test_every_cookie_names_its_verified_action(client):
    d = client.get("/api/a11oy/v1/cookies").json()
    for entry in d["ledger"]:
        assert entry["verified_action"], entry
        assert entry["label"] == "RECOGNITION_ONLY"
        assert entry["awarded_to"] and entry["awarded_at"]


def test_how_to_earn_names_verifiability(client):
    d = client.get("/api/a11oy/v1/cookies").json()
    assert "verified" in d["how_to_earn"].lower()
