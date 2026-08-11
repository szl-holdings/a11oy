from __future__ import annotations

"""Ed25519 signing, DSSE-style envelopes, and receipt verification."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canonical import (
    b64url_decode,
    b64url_encode,
    canonical_json_bytes,
    digest_bytes,
    digest_object,
    require_digest,
)
from .errors import IntegrityError, ValidationError


def _pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE pre-auth encoding."""
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(type_bytes)).encode("ascii") + b" " + type_bytes + b" " + str(len(payload)).encode("ascii") + b" " + payload


@dataclass(frozen=True, slots=True)
class PublicVerifier:
    key_id: str
    public_key: str

    def __post_init__(self) -> None:
        require_digest(self.key_id, field="key_id")
        raw = b64url_decode(self.public_key)
        if len(raw) != 32:
            raise ValidationError("Ed25519 public key must be 32 bytes")
        observed = digest_bytes(raw)
        if observed != self.key_id:
            raise ValidationError("public key does not match key_id")

    def verify(self, data: bytes, signature: str) -> None:
        key = Ed25519PublicKey.from_public_bytes(b64url_decode(self.public_key))
        try:
            key.verify(b64url_decode(signature), data)
        except InvalidSignature as exc:
            raise IntegrityError("Ed25519 signature verification failed") from exc

    def to_dict(self) -> dict[str, str]:
        return {"algorithm": "Ed25519", "key_id": self.key_id, "public_key": self.public_key}


class Ed25519Signer:
    def __init__(self, private_key: Ed25519PrivateKey, *, signer_state: str = "SIGNED_PERSISTENT") -> None:
        if signer_state not in {"SIGNED_TEST", "SIGNED_PERSISTENT"}:
            raise ValidationError("signer state must be SIGNED_TEST or SIGNED_PERSISTENT")
        self._private_key = private_key
        self.signer_state = signer_state
        raw_public = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_key = b64url_encode(raw_public)
        self.key_id = digest_bytes(raw_public)

    @classmethod
    def generate(cls, *, signer_state: str = "SIGNED_PERSISTENT") -> "Ed25519Signer":
        return cls(Ed25519PrivateKey.generate(), signer_state=signer_state)

    @classmethod
    def from_seed(cls, seed: bytes, *, signer_state: str = "SIGNED_TEST") -> "Ed25519Signer":
        if len(seed) != 32:
            raise ValidationError("Ed25519 deterministic seed must be exactly 32 bytes")
        return cls(Ed25519PrivateKey.from_private_bytes(seed), signer_state=signer_state)

    @classmethod
    def load(cls, path: str | Path, *, signer_state: str = "SIGNED_PERSISTENT") -> "Ed25519Signer":
        raw = Path(path).read_bytes()
        if len(raw) != 32:
            raise ValidationError("signer key file must contain a raw 32-byte Ed25519 private key")
        return cls.from_seed(raw, signer_state=signer_state)

    @classmethod
    def load_or_create(cls, path: str | Path) -> "Ed25519Signer":
        key_path = Path(path)
        if key_path.exists():
            if key_path.is_symlink() or not key_path.is_file():
                raise ValidationError("signer key path must be a regular file")
            mode = key_path.stat().st_mode & 0o777
            if mode & 0o077:
                raise ValidationError("signer key file must not be group/world accessible")
            return cls.load(key_path)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        private = Ed25519PrivateKey.generate()
        raw = private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(key_path, flags, 0o600)
        try:
            written = os.write(fd, raw)
            if written != len(raw):
                raise OSError("short private-key write")
            os.fsync(fd)
        finally:
            os.close(fd)
        return cls(private, signer_state="SIGNED_PERSISTENT")

    def verifier(self) -> PublicVerifier:
        return PublicVerifier(key_id=self.key_id, public_key=self.public_key)

    def sign(self, data: bytes) -> str:
        return b64url_encode(self._private_key.sign(data))

    def sign_object(self, value: Any, *, payload_type: str) -> dict[str, Any]:
        payload = canonical_json_bytes(value)
        signature = self.sign(_pae(payload_type, payload))
        envelope = {
            "payloadType": payload_type,
            "payload": b64url_encode(payload),
            "signatures": [{"keyid": self.key_id, "sig": signature}],
        }
        return {
            "schema": "szl.dsse-envelope/v1",
            "envelope": envelope,
            "envelope_digest": digest_object(envelope),
            "signer_state": self.signer_state,
        }


def verify_signed_object(
    signed: Mapping[str, Any],
    verifier: PublicVerifier,
    *,
    expected_payload_type: str | None = None,
) -> Any:
    if signed.get("schema") != "szl.dsse-envelope/v1":
        raise IntegrityError("unsupported signed-envelope schema")
    envelope = signed.get("envelope")
    if not isinstance(envelope, Mapping):
        raise IntegrityError("signed envelope is missing")
    if digest_object(envelope) != signed.get("envelope_digest"):
        raise IntegrityError("signed envelope digest mismatch")
    payload_type = envelope.get("payloadType")
    if not isinstance(payload_type, str) or not payload_type:
        raise IntegrityError("payloadType is missing")
    if expected_payload_type is not None and payload_type != expected_payload_type:
        raise IntegrityError("signed envelope payload type mismatch")
    payload_value = envelope.get("payload")
    signatures = envelope.get("signatures")
    if not isinstance(payload_value, str) or not isinstance(signatures, list) or len(signatures) != 1:
        raise IntegrityError("signed envelope must contain exactly one signature")
    signature = signatures[0]
    if not isinstance(signature, Mapping) or signature.get("keyid") != verifier.key_id:
        raise IntegrityError("signed envelope key identity mismatch")
    payload = b64url_decode(payload_value)
    verifier.verify(_pae(payload_type, payload), str(signature.get("sig", "")))
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("signed payload is not canonical JSON") from exc
