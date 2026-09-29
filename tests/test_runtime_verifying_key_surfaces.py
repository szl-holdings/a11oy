#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Public-key surfaces must name the key that verifies this runtime's receipts.

Receipts are signed by the runtime signer whose public half is served at
/cosign.pub. Every other surface that hands a verifier a key (or a key URL)
must agree with it, and a surface that reports a fingerprint must serve the
key that fingerprint names. No real private key is used: tests run with the
process-local ephemeral key or a freshly generated one.
"""

from __future__ import annotations

import asyncio
import base64
import json
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from starlette.testclient import TestClient

import a11oy_ayllu_wall
import serve
import szl_dsse
import szl_ecosystem_routes
import szl_proof_carrying_infer

_ORG_KEY_REPO = "szl-holdings/.github"


def _der(pem) -> bytes:
    if isinstance(pem, str):
        pem = pem.encode("ascii")
    return serialization.load_pem_public_key(pem).public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


def test_khipu_pubkey_serves_the_key_its_fingerprint_names(client) -> None:
    runtime = client.get("/cosign.pub")
    assert runtime.status_code == 200, runtime.text

    body = client.get("/khipu/pubkey").json()
    assert szl_dsse.keyid_for_public_pem(body["pem"]) == body["fingerprint_sha256"]
    assert _der(body["pem"]) == _der(runtime.content)

    raw = client.get("/khipu/pubkey.pem")
    assert raw.status_code == 200
    assert _der(raw.content) == _der(runtime.content)


def test_assurance_credential_pem_matches_its_fingerprint(client) -> None:
    runtime = client.get("/cosign.pub")
    body = client.get("/api/a11oy/v1/assurance/credential").json()
    assert body["data_kind"] == "live"
    pem = body["public_key_pem"]
    assert szl_dsse.keyid_for_public_pem(pem) == body["public_key_fingerprint_sha256"]
    assert _der(pem) == _der(runtime.content)


def test_credential_honesty_follows_signing_available(client, monkeypatch) -> None:
    # Without a signer, active_public_key_pem() can fall back to the embedded
    # org key, so the text must not call public_key_pem the signer's key.
    path = "/api/a11oy/v1/assurance/credential"
    monkeypatch.setattr(szl_dsse, "signing_available", lambda: False)
    unsigned = client.get(path).json()
    assert unsigned["signing_available"] is False
    assert "fallback verification key" in unsigned["honesty"]
    assert "runtime signer's public key" not in unsigned["honesty"]

    monkeypatch.setattr(szl_dsse, "signing_available", lambda: True)
    signed = client.get(path).json()
    assert signed["signing_available"] is True
    assert "runtime signer's public key" in signed["honesty"]
    assert "fallback" not in signed["honesty"]


def _assert_signing_is_conditional(body: dict, where: str) -> None:
    description = body["what_is_now_verifiable"]["1_dsse_signature"]["description"]
    assert "UNSIGNED" in description, where
    assert "DSSE_PLACEHOLDER" in description, where
    assert "signed=true" in description, where
    assert body["public_key_url"] == "/cosign.pub", where


def test_intoto_guide_points_at_runtime_key_and_does_not_overclaim(client) -> None:
    for path in ("/api/a11oy/v1/verify/intoto", "/v1/verify/intoto"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert "Every receipt is DSSE-signed" not in response.text, path
        _assert_signing_is_conditional(response.json(), path)


def test_serve_fallback_intoto_guides_state_the_signing_condition() -> None:
    # Both serve.py copies are shadowed while szl_intoto_routes registers, so
    # call them directly; they are what ships if that registration fails.
    for where, response in (
        ("serve._intoto_verify_guide", asyncio.run(serve._intoto_verify_guide(None))),
        ("serve.api_proxy", asyncio.run(serve.api_proxy(None, "v1/verify/intoto"))),
    ):
        _assert_signing_is_conditional(json.loads(response.body), where)


def test_verifier_key_urls_are_not_the_org_key() -> None:
    for url in (
        szl_proof_carrying_infer.COSIGN_PUB_URL,
        szl_proof_carrying_infer.COSIGN_PUB_RAW,
        szl_ecosystem_routes.COSIGN_PUB_URL,
    ):
        assert url.endswith("/cosign.pub")
        assert _ORG_KEY_REPO not in url


def test_verify_page_links_runtime_key_and_names_the_keyring() -> None:
    page = (Path(serve.__file__).parent / "web" / "verify-receipt.html").read_text(
        encoding="utf-8"
    )
    assert 'href="/cosign.pub"' in page
    assert "github.com/" + _ORG_KEY_REPO + "/blob/main/cosign.pub" not in page
    # The server falls back to its retained keyring (which includes the org
    # key), so the page must not say the org key verifies only on a match.
    assert "only if its fingerprint matches" not in page
    assert "verified_by" in page


def test_cross_app_ledger_names_each_apps_own_key(monkeypatch) -> None:
    # Shared with killinchu byte-for-byte, so no origin may be hard-coded as
    # the ledger's key; each signer is paired with its own app's /cosign.pub.
    monkeypatch.setattr(szl_ecosystem_routes, "_get_json", lambda *_a, **_k: None)
    ledger = szl_ecosystem_routes.build_ledger("a11oy")
    assert ledger["cosign_pub_url"] == "/cosign.pub"
    assert ledger["a11oy_signer"]["public_key_url"] == (
        szl_ecosystem_routes.A11OY_BASE + "/cosign.pub"
    )
    assert ledger["killinchu_signer"]["public_key_url"] == (
        szl_ecosystem_routes.KILLINCHU_BASE + "/cosign.pub"
    )


def _runtime_key():
    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, der


def _pem_wrapped(der: bytes, width: int) -> bytes:
    body = "\n".join(textwrap.wrap(base64.b64encode(der).decode("ascii"), width))
    return (
        "-----BEGIN PUBLIC KEY-----\n" + body + "\n-----END PUBLIC KEY-----\n"
    ).encode("ascii")


def test_ayllu_runtime_probe_matches_same_key_wrapped_at_76(monkeypatch) -> None:
    private_key, der = _runtime_key()
    pinned = _pem_wrapped(der, 76)
    assert pinned.strip() != private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).strip()
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: private_key)

    state = a11oy_ayllu_wall._runtime_key_state(pinned)

    assert state["state"] == "ENV_SIGNER_MATCHES_PIN"


def test_ayllu_runtime_probe_reports_a_different_key(monkeypatch) -> None:
    private_key, _ = _runtime_key()
    _, other_der = _runtime_key()
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: private_key)

    state = a11oy_ayllu_wall._runtime_key_state(_pem_wrapped(other_der, 76))

    assert state["state"] == "ENV_SIGNER_DIFFERS_FROM_PIN"


def test_intoto_rekor_verifier_is_the_signing_key(monkeypatch) -> None:
    # Rekor checks the envelope against the verifier key it is sent, and
    # szl_dsse.sign_payload signs with the active runtime key, not the org key.
    import szl_intoto

    assert _der(szl_intoto._load_public_pem()) == _der(szl_dsse.active_public_key_pem())

    private_key, der = _runtime_key()
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: private_key)
    sent = _der(szl_intoto._load_public_pem())
    assert sent == der
    assert sent != _der(szl_dsse.COSIGN_PUBLIC_PEM)


def test_assurance_text_matches_the_served_verify_page(client) -> None:
    page = client.get("/verify").text
    assert "/api/a11oy/v1/verify/receipt" in page
    matrix = client.get("/api/a11oy/v1/assurance/matrix").text
    fit = client.get("/api/a11oy/v1/assurance/fit").text
    assert "/api/a11oy/v1/verify/receipt" in matrix
    if "crypto.subtle" not in page:
        # /verify is the server-side verifier, so nothing may call it in-browser.
        for text in (matrix, fit):
            assert "WebCrypto" not in text
            assert "in-browser" not in text


def test_govern_infer_receipt_matches_the_assurance_signing_claim(monkeypatch) -> None:
    # szl_governed_api calls governed_turn with no actor. The matrix says that
    # path returns dsse=null and a DSSE_PLACEHOLDER chain entry, so if signing
    # is ever wired in, this fails until the matrix text is updated with it.
    import hashlib

    import a11oy_vertical_feeds
    import szl_assurance

    calls = []
    monkeypatch.setattr(szl_dsse, "signing_available", lambda: True)
    monkeypatch.setattr(
        szl_dsse,
        "sign_khipu_receipt",
        lambda *a, **k: calls.append(a) or {"receipt": a[0], "dsse": {"signed": True}},
    )
    turn = a11oy_vertical_feeds.governed_turn(
        "general", "summarize the quarterly report", declared="PUBLIC",
        severity=0.0, action_kind="inference",
    )
    receipt = turn["receipt"]
    assert calls == []
    assert turn["dsse"] is None
    assert receipt["signature"] == "DSSE_PLACEHOLDER"
    body = {k: receipt[k] for k in ("organ", "ns", "seq", "action", "payload_digest", "ts", "prev")}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha3_256(raw).hexdigest() == receipt["digest"]

    rows = {row["req_id"]: row for row in szl_assurance.ASSURANCE_MATRIX}
    detail = rows["SI7-1"]["status_detail"]
    assert "dsse=null" in detail
    assert "DSSE_PLACEHOLDER" in detail
    assert "SHA3-256" in detail
