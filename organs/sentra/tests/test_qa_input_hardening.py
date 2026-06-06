"""QA input-hardening regression tests (QA squad, 2026-06-04).

While stress/edge-testing the live sentra Space, several POST handlers returned
an opaque HTTP 500 (internal_error + trace_id) on empty / malformed / wrong-type
JSON bodies:

  POST /api/sentra/v1/rosie-companion/{ponder,synthesize,evolve,brain-jack}
      -> 500 on empty / malformed / array (unguarded request.json())
  POST /api/sentra/v1/brain/screen, /api/sentra/v1/llm/route
      -> 500 on a JSON array body (.get() on a list after a guarded parse)

The verdict engine itself (/api/sentra/v1/verdict[/attested]) is pydantic-validated
and already answers 422 on bad input — those are covered here as a regression lock.

Every public POST surface must answer with a clean 4xx (or graceful fallback) and
never a 500 on bad input. Boots the real app in-process (no mocks).
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


ROSIE_COMPANION = [
    "/api/sentra/v1/rosie-companion/ponder",
    "/api/sentra/v1/rosie-companion/synthesize",
    "/api/sentra/v1/rosie-companion/evolve",
    "/api/sentra/v1/rosie-companion/brain-jack",
]


@pytest.mark.parametrize("path", ROSIE_COMPANION)
@pytest.mark.parametrize("payload", [b"", b"{not json", b"[1,2,3]"])
def test_rosie_companion_bad_input_never_500(client, path, payload):
    r = client.post(path, content=payload)
    assert r.status_code != 500, f"{path} returned 500 on bad input"
    assert r.status_code == 400


def test_rosie_companion_valid_still_ok(client):
    r = client.post("/api/sentra/v1/rosie-companion/ponder", json={"context": "test"})
    assert r.status_code == 200


@pytest.mark.parametrize("path", [
    "/api/sentra/v1/brain/screen",
    "/api/sentra/v1/llm/route",
])
def test_brain_endpoints_array_body_never_500(client, path):
    r = client.post(path, json=[1, 2, 3])
    assert r.status_code != 500
    assert r.status_code == 200  # graceful fallback to defaults
    r = client.post(path, json={"prompt": "x"})
    assert r.status_code == 200


# --- verdict engine: graceful validation, never 500 -------------------------

@pytest.mark.parametrize("payload", [b"", b"{not json", b"[1,2,3]"])
def test_verdict_bad_input_never_500(client, payload):
    r = client.post("/api/sentra/v1/verdict", content=payload)
    assert r.status_code != 500


def test_verdict_blocks_injection(client):
    """sentra is the immune system — known threat signatures must DENY."""
    for action in ["DROP TABLE users", "rm -rf /", "<script>alert(1)</script>"]:
        r = client.post("/api/sentra/v1/verdict", json={"action": action})
        assert r.status_code == 200
        assert r.json().get("decision") == "deny", f"{action!r} should be denied"


def test_verdict_allows_benign(client):
    r = client.post("/api/sentra/v1/verdict", json={"action": "read_config"})
    assert r.status_code == 200
    assert r.json().get("decision") == "allow"
