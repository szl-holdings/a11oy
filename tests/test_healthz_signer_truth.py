"""/healthz reports the observed signer and running commit, never constants.

Before: szl_be_hardening /healthz hard-coded signer ABSENT, dsse_live ABSENT
and commit "c7c0ba17" while /api/a11oy/healthz rollup.signer said DSSE-LIVE.
Now the signer is the same validated runtime provider the rollup reads, dsse_live
is proven by a szl_dsse sign -> verify round trip, and commit is SZL_GIT_SHA.
The protected invariant is unchanged: nothing is DSSE-LIVE without verification,
and no key material is ever emitted.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_be_hardening as H

ORGAN = "signertruth"
FINGERPRINT = "9926bf69" + "0" * 56


@pytest.fixture(autouse=True)
def fresh_dsse_probe(monkeypatch):
    monkeypatch.setattr(H, "_DSSE_PROBE_CACHE", {})


def _client(tmp_path, provider=None):
    app = FastAPI()
    H.harden(app, organ=ORGAN, khipu_path=str(tmp_path / "khipu.sqlite3"))
    if provider is not None:
        app.state.szl_signer_status = provider
    return TestClient(app)


def _live_status(**overrides):
    value = {
        "status": "DSSE-LIVE",
        "signing_available": True,
        "scheme": "DSSEv1 / ECDSA-P256-SHA256",
        "public_key_fingerprint": FINGERPRINT,
        "key_scope": "DEPLOYMENT_PERSISTENT",
        "key_source": "persistent:env:SZL_COSIGN_PRIVATE_PEM",
        "key_lifetime": "UNTIL_SECRET_ROTATION",
        # A provider must never leak this; the route must not copy it either.
        "private_pem": "-----BEGIN EC PRIVATE KEY-----\nK3Y-MATERIAL-MARKER\n",
    }
    value.update(overrides)
    return value


def test_live_runtime_signer_is_reported_truthfully(tmp_path):
    client = _client(tmp_path, provider=_live_status)
    response = client.get("/healthz")
    assert response.status_code == 200
    signer = response.json()["signer"]
    assert signer["status"] == "DSSE-LIVE"
    assert signer["signing_available"] is True
    assert signer["public_key_fingerprint"] == FINGERPRINT
    assert signer["key_scope"] == "DEPLOYMENT_PERSISTENT"
    assert signer["source"] == "app.state.szl_signer_status"
    serialized = json.dumps(response.json())
    assert "PRIVATE KEY" not in serialized
    assert "K3Y-MATERIAL-MARKER" not in serialized
    assert "private_pem" not in serialized
    assert "key_source" not in signer
    # The organ-scoped alias serves the identical body.
    assert client.get(f"/api/{ORGAN}/v1/healthz").json()["signer"] == signer


def test_absent_provider_is_absent_not_live(tmp_path):
    signer = _client(tmp_path).get("/healthz").json()["signer"]
    assert signer["status"] == "ABSENT"
    assert signer["signing_available"] is False
    assert signer["scheme"] == "UNAVAILABLE"
    assert signer["reason"] == "SIGNER_STATUS_PROVIDER_ABSENT"


@pytest.mark.parametrize(
    "provider",
    [
        lambda: _live_status(signing_available=False),  # contradictory
        lambda: _live_status(status="ABSENT"),  # contradictory the other way
        lambda: _live_status(public_key_fingerprint=None),  # no key identity
        lambda: _live_status(public_key_fingerprint="not-hex"),
        lambda: _live_status(scheme="UNAVAILABLE"),
        lambda: _live_status(status="SIGNED"),  # outside the vocabulary
        lambda: "DSSE-LIVE",  # not a mapping
    ],
)
def test_unverifiable_live_claims_fail_closed(tmp_path, provider):
    signer = _client(tmp_path, provider=provider).get("/healthz").json()["signer"]
    assert signer["status"] == "UNAVAILABLE"
    assert signer["status"] != "DSSE-LIVE"
    assert signer["signing_available"] is False


def test_provider_error_reports_class_only(tmp_path):
    def broken():
        raise RuntimeError("could not parse -----BEGIN EC PRIVATE KEY----- K3Y-MATERIAL-MARKER")

    body = _client(tmp_path, provider=broken).get("/healthz").json()
    assert body["signer"]["status"] == "UNAVAILABLE"
    assert body["signer"]["error"] == "RuntimeError"
    assert "K3Y-MATERIAL-MARKER" not in json.dumps(body)


def test_commit_is_the_running_revision(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("SZL_GIT_SHA", "A2B4524A" + "1" * 32)
    body = client.get("/healthz").json()
    assert body["commit"] == "a2b4524a" + "1" * 32
    assert body["doctrine_lock_commit"] == "c7c0ba17"
    assert body["lock"] == "749/14/163"

    monkeypatch.delenv("SZL_GIT_SHA")
    assert client.get("/healthz").json()["commit"] == "UNKNOWN"
    monkeypatch.setenv("SZL_GIT_SHA", "main; rm -rf /")
    assert client.get("/healthz").json()["commit"] == "UNKNOWN"


def _ec_private_pem():
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


@pytest.fixture
def isolated_dsse(monkeypatch):
    import szl_dsse

    monkeypatch.setattr(szl_dsse, "_RUNTIME_PUBLIC_KEYS", dict(szl_dsse._RUNTIME_PUBLIC_KEYS))
    monkeypatch.setattr(szl_dsse, "_ACTIVE_RUNTIME_KEYID", szl_dsse._ACTIVE_RUNTIME_KEYID)
    for name in ("SZL_COSIGN_PRIVATE_KEY_PEM", "A11OY_RECEIPT_KEY_PEM",
                 "A11OY_RECEIPT_KEY_PATH", "A11OY_REQUIRE_PERSISTENT_SIGNING"):
        monkeypatch.delenv(name, raising=False)
    return szl_dsse


def test_dsse_live_requires_a_real_sign_verify_round_trip(tmp_path, monkeypatch, isolated_dsse):
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", _ec_private_pem())
    dsse = _client(tmp_path).get("/healthz").json()["dsse_live"]
    assert dsse["status"] == "DSSE-LIVE"
    assert dsse["signing_available"] is True
    assert dsse["verification"] == "SIGN_VERIFY_ROUNDTRIP_OK"
    assert dsse["rollup"] == "/api/a11oy/healthz"
    assert dsse["public_key_fingerprint"]
    assert "BEGIN" not in json.dumps(dsse)


def test_dsse_signature_that_does_not_verify_is_never_live(tmp_path, monkeypatch, isolated_dsse):
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", _ec_private_pem())
    monkeypatch.setattr(isolated_dsse, "verify_envelope", lambda env: {"verified": False})
    dsse = _client(tmp_path).get("/healthz").json()["dsse_live"]
    assert dsse["status"] == "UNAVAILABLE"
    assert dsse["signing_available"] is False
    assert dsse["verification"] == "SIGN_VERIFY_ROUNDTRIP_FAILED"


def test_dsse_without_key_is_absent(tmp_path, monkeypatch, isolated_dsse):
    monkeypatch.delenv("SZL_COSIGN_PRIVATE_PEM", raising=False)
    monkeypatch.setattr(isolated_dsse, "signing_available", lambda: False)
    dsse = _client(tmp_path).get("/healthz").json()["dsse_live"]
    assert dsse["status"] == "ABSENT"
    assert dsse["signing_available"] is False
    assert dsse["verification"] == "NO_SIGNING_KEY"


def test_healthz_matches_the_assembled_rollup_signer():
    """In the real app, /healthz.signer and the rollup read one provider."""

    from starlette.testclient import TestClient as StarletteClient

    import serve

    client = StarletteClient(serve.app, raise_server_exceptions=False)
    rollup = client.get("/api/a11oy/healthz").json()["rollup"]["signer"]
    signer = client.get("/healthz").json()["signer"]
    assert signer["status"] == rollup["status"]
    assert signer["signing_available"] is rollup["signing_available"]
    if signer["status"] == "DSSE-LIVE":
        assert signer["public_key_fingerprint"] == rollup["public_key_fingerprint"]
        assert "DSSE" in signer["scheme"]
