# SPDX-License-Identifier: Apache-2.0
"""Managed Ed25519 DSSE signing for ORO receipts.

Production accepts a private key only through an absolute mounted file path. The
key value is never accepted as a process argument, environment value, response,
or log field. Public identity is represented by an operator-selected key ID and
a SHA-256 fingerprint of the public key.
"""
from __future__ import annotations

import base64
import hashlib
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from .core import OROContractError, OROSignerUnavailable

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # pragma: no cover - exercised by readiness degradation
    serialization = None  # type: ignore[assignment]
    Ed25519PrivateKey = None  # type: ignore[assignment]


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    if not isinstance(payload_type, str) or not payload_type:
        raise OROContractError("DSSE payload type is required")
    if not isinstance(payload, bytes):
        raise OROContractError("DSSE payload must be bytes")
    encoded_type = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(encoded_type)).encode("ascii")
        + b" "
        + encoded_type
        + b" "
        + str(len(payload)).encode("ascii")
        + b" "
        + payload
    )


class Ed25519DSSESigner:
    def __init__(self, *, key_id: str, private_key: Any, source: str) -> None:
        if not isinstance(key_id, str) or not key_id.strip():
            raise OROContractError("signer key_id is required")
        if Ed25519PrivateKey is None or serialization is None:
            raise OROSignerUnavailable("cryptography Ed25519 support is unavailable")
        if not isinstance(private_key, Ed25519PrivateKey):
            raise OROContractError("signer key must be Ed25519")
        self._key = private_key
        self._key_id = key_id.strip()
        self._source = source
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self._fingerprint = "sha256:" + hashlib.sha256(public_bytes).hexdigest()

    @classmethod
    def from_pem_file(cls, *, key_id: str, path: str | Path) -> "Ed25519DSSESigner":
        if Ed25519PrivateKey is None or serialization is None:
            raise OROSignerUnavailable("cryptography Ed25519 support is unavailable")
        key_path = Path(path)
        if not key_path.is_absolute():
            raise OROContractError("production signing key path must be absolute")
        try:
            metadata = key_path.stat()
        except OSError as exc:
            raise OROSignerUnavailable("managed signing key file is unavailable") from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise OROContractError("managed signing key path must be a regular file")
        if metadata.st_mode & 0o077:
            raise OROContractError("managed signing key file must not be accessible by group/other")
        try:
            pem = key_path.read_bytes()
            loaded = serialization.load_pem_private_key(pem, password=None)
        except (OSError, ValueError, TypeError) as exc:
            raise OROSignerUnavailable("managed signing key could not be loaded") from exc
        if not isinstance(loaded, Ed25519PrivateKey):
            raise OROContractError("managed signing key must be Ed25519")
        return cls(key_id=key_id, private_key=loaded, source="managed-file")

    @classmethod
    def ephemeral_for_tests(cls, *, key_id: str = "oro-ephemeral-test") -> "Ed25519DSSESigner":
        if Ed25519PrivateKey is None:
            raise OROSignerUnavailable("cryptography Ed25519 support is unavailable")
        return cls(key_id=key_id, private_key=Ed25519PrivateKey.generate(), source="ephemeral-test")

    @property
    def identity(self) -> Mapping[str, Any]:
        return {
            "state": "ACTIVE",
            "algorithm": "Ed25519",
            "key_id": self._key_id,
            "public_key_fingerprint": self._fingerprint,
            "source": self._source,
            "private_key_exposed": False,
        }

    def sign(self, payload_type: str, payload: bytes) -> Mapping[str, Any]:
        signature = self._key.sign(dsse_pae(payload_type, payload))
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [
                {
                    "keyid": self._key_id,
                    "sig": base64.b64encode(signature).decode("ascii"),
                }
            ],
            "signer": dict(self.identity),
        }


def signer_from_environment(*, production: bool) -> Ed25519DSSESigner | None:
    """Resolve a signer without ever reading a key value from the environment."""
    key_path = os.environ.get("SZL_ORO_SIGNING_KEY_PATH", "").strip()
    key_id = os.environ.get("SZL_ORO_SIGNING_KEY_ID", "").strip()
    if key_path or key_id:
        if not key_path or not key_id:
            raise OROContractError(
                "SZL_ORO_SIGNING_KEY_PATH and SZL_ORO_SIGNING_KEY_ID must be set together"
            )
        return Ed25519DSSESigner.from_pem_file(key_id=key_id, path=key_path)
    if not production and os.environ.get("SZL_ORO_ALLOW_EPHEMERAL_SIGNER") == "1":
        return Ed25519DSSESigner.ephemeral_for_tests()
    return None
