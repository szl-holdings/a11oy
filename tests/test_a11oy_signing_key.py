"""Focused tests for the shared persistent P-256 receipt-key loader."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

import a11oy_signing_key


_KEY_ENV_NAMES = (
    "SZL_COSIGN_PRIVATE_PEM",
    "SZL_COSIGN_PRIVATE_KEY_PEM",
    "A11OY_RECEIPT_KEY_PEM",
    "A11OY_RECEIPT_KEY_PATH",
    "A11OY_RECEIPT_KEY_DIR",
    "A11OY_REQUIRE_PERSISTENT_SIGNING",
)


@pytest.fixture(autouse=True)
def clean_key_environment(monkeypatch: pytest.MonkeyPatch):
    original_cache = dict(a11oy_signing_key._KEY_CACHE)
    for name in _KEY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    a11oy_signing_key._KEY_CACHE.clear()
    yield
    a11oy_signing_key._KEY_CACHE.clear()
    a11oy_signing_key._KEY_CACHE.update(original_cache)


def private_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


def fingerprint(public_pem: str) -> str:
    public_key = serialization.load_pem_public_key(public_pem.encode("ascii"))
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def test_canonical_env_pem_has_stable_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", private_pem())

    first = a11oy_signing_key.load_signing_key()
    second = a11oy_signing_key.load_signing_key()

    assert first[0] is not None
    assert first[2:] == ("persistent:env:SZL_COSIGN_PRIVATE_PEM", "")
    assert second[2:] == first[2:]
    assert fingerprint(first[1]) == fingerprint(second[1])


def test_canonical_env_identity_survives_process_restart() -> None:
    script = """
import hashlib
import json
from a11oy_signing_key import load_signing_key
private_key, public_pem, source, error = load_signing_key()
print(json.dumps({
    "available": private_key is not None,
    "fingerprint": hashlib.sha256(public_pem.encode("ascii")).hexdigest(),
    "source": source,
    "error": error,
}))
"""
    env = dict(os.environ)
    for name in _KEY_ENV_NAMES:
        env.pop(name, None)
    env["SZL_COSIGN_PRIVATE_PEM"] = private_pem()
    env["A11OY_REQUIRE_PERSISTENT_SIGNING"] = "1"
    root = Path(__file__).resolve().parents[1]

    def boot() -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(result.stdout)

    first = boot()
    restarted = boot()

    assert first == restarted
    assert first["available"] is True
    assert first["source"] == "persistent:env:SZL_COSIGN_PRIVATE_PEM"
    assert first["error"] == ""


def test_optional_env_pem_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A11OY_RECEIPT_KEY_PEM", private_pem())

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is not None
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert source == "persistent:env:A11OY_RECEIPT_KEY_PEM"
    assert error == ""


def test_compatibility_env_pem_uses_shared_signer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_KEY_PEM", private_pem())

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is not None
    assert fingerprint(public_pem)
    assert source == "persistent:env:SZL_COSIGN_PRIVATE_KEY_PEM"
    assert error == ""


def test_base64_compatibility_env_uses_shared_signer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded = base64.b64encode(private_pem().encode("ascii")).decode("ascii")
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_KEY_PEM", encoded)

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is not None
    assert fingerprint(public_pem)
    assert source == "persistent:env:SZL_COSIGN_PRIVATE_KEY_PEM"
    assert error == ""


def test_canonical_env_precedes_compatibility_spelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = private_pem()
    compatibility = private_pem()
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", canonical)
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_KEY_PEM", compatibility)

    _, public_pem, source, error = a11oy_signing_key.load_signing_key()

    canonical_private = serialization.load_pem_private_key(
        canonical.encode("ascii"), password=None
    )
    canonical_public = canonical_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    assert fingerprint(public_pem) == fingerprint(canonical_public)
    assert source == "persistent:env:SZL_COSIGN_PRIVATE_PEM"
    assert error == ""


def test_cache_identity_changes_when_env_pem_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", private_pem())
    first = a11oy_signing_key.load_signing_key()
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", private_pem())
    second = a11oy_signing_key.load_signing_key()

    assert fingerprint(first[1]) != fingerprint(second[1])


def test_malformed_configured_env_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    valid_path = tmp_path / "valid.pem"
    valid_path.write_text(private_pem(), encoding="ascii")
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", "not a private key")
    monkeypatch.setenv("A11OY_RECEIPT_KEY_PATH", str(valid_path))

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is None
    assert public_pem == ""
    assert source == "unavailable"
    assert "persistent:env:SZL_COSIGN_PRIVATE_PEM" in error
    assert "not a private key" not in error


def test_strict_mode_without_source_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        a11oy_signing_key,
        "_DEFAULT_KEY_DIR",
        str(tmp_path / "default-mount-is-absent"),
    )
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_SIGNING", "1")

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is None
    assert public_pem == ""
    assert source == "unavailable"
    assert error == "persistent signing is required but no key source is configured"


def test_valid_explicit_file_path_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    path = tmp_path / "receipt.pem"
    path.write_text(private_pem(), encoding="ascii")
    monkeypatch.setenv("A11OY_RECEIPT_KEY_PATH", str(path))

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is not None
    assert fingerprint(public_pem)
    assert source == "persistent:%s" % path
    assert error == ""


def test_missing_explicit_file_path_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    path = tmp_path / "missing.pem"
    monkeypatch.setenv("A11OY_RECEIPT_KEY_PATH", str(path))

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is None
    assert public_pem == ""
    assert source == "unavailable"
    assert error == "configured receipt key path does not exist: %s" % path


def test_configured_directory_requires_a_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("A11OY_RECEIPT_KEY_DIR", str(tmp_path))

    private_key, public_pem, source, error = (
        a11oy_signing_key.load_signing_key()
    )

    assert private_key is None
    assert public_pem == ""
    assert source == "unavailable"
    assert "contains no candidate key" in error


def test_unconfigured_non_strict_callers_share_ephemeral_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        a11oy_signing_key,
        "_DEFAULT_KEY_DIR",
        str(tmp_path / "default-mount-is-absent"),
    )

    first = a11oy_signing_key.load_signing_key()
    second = a11oy_signing_key.load_signing_key()

    assert first[0] is second[0]
    assert fingerprint(first[1]) == fingerprint(second[1])
    assert first[2:] == ("ephemeral", "")
    assert second[2:] == first[2:]
