# SPDX-License-Identifier: Apache-2.0
"""Fail-closed bearer authorization for governed ORO writes.

Production accepts the bearer token only through an absolute owner-only mounted
file. The token itself is never returned or logged; public identity contains
only an operator-selected ID and a SHA-256 fingerprint.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import stat
from pathlib import Path
from typing import Any, Mapping

from fastapi import Request

from .core import OROContractError, OROStateError


class OROAuthorizerUnavailable(OROStateError):
    """The governed write-authorization boundary is unavailable."""


class OROAuthorizationError(OROContractError):
    """A governed write request did not present valid bearer authority."""


class BearerTokenAuthorizer:
    def __init__(self, *, token_id: str, token: bytes, source: str) -> None:
        if not isinstance(token_id, str) or not token_id.strip():
            raise OROContractError("authorization token_id is required")
        if not isinstance(token, bytes) or not 32 <= len(token) <= 4096:
            raise OROContractError("authorization token must contain 32-4096 bytes")
        if any(byte in b"\r\n\t " for byte in token):
            raise OROContractError("authorization token must not contain whitespace")
        self._token_id = token_id.strip()
        self._token = token
        self._source = source
        self._fingerprint = "sha256:" + hashlib.sha256(token).hexdigest()

    @classmethod
    def from_file(cls, *, token_id: str, path: str | Path) -> "BearerTokenAuthorizer":
        token_path = Path(path)
        if not token_path.is_absolute():
            raise OROContractError("production authorization token path must be absolute")
        try:
            metadata = token_path.stat()
        except OSError as exc:
            raise OROAuthorizerUnavailable("managed authorization token file is unavailable") from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise OROContractError("managed authorization token path must be a regular file")
        if metadata.st_mode & 0o077:
            raise OROContractError(
                "managed authorization token file must not be accessible by group/other"
            )
        try:
            token = token_path.read_bytes().strip()
        except OSError as exc:
            raise OROAuthorizerUnavailable("managed authorization token could not be loaded") from exc
        return cls(token_id=token_id, token=token, source="managed-file")

    @classmethod
    def development(cls) -> "BearerTokenAuthorizer":
        return cls(
            token_id="oro-development",
            token=b"oro-development-explicit-authorization-token",
            source="explicit-development",
        )

    @property
    def identity(self) -> Mapping[str, Any]:
        return {
            "state": "ACTIVE",
            "scheme": "Bearer",
            "token_id": self._token_id,
            "token_fingerprint": self._fingerprint,
            "source": self._source,
            "token_value_exposed": False,
        }

    def authorize(self, request: Request) -> str:
        header = request.headers.get("authorization", "")
        scheme, separator, supplied = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not supplied:
            raise OROAuthorizationError("a Bearer authorization header is required")
        try:
            supplied_bytes = supplied.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise OROAuthorizationError("authorization token is malformed") from exc
        if not secrets.compare_digest(supplied_bytes, self._token):
            raise OROAuthorizationError("authorization token is invalid")
        return self._token_id


def authorizer_from_environment(*, production: bool) -> BearerTokenAuthorizer | None:
    path = os.environ.get("SZL_ORO_API_TOKEN_PATH", "").strip()
    token_id = os.environ.get("SZL_ORO_API_TOKEN_ID", "").strip()
    if path or token_id:
        if not path or not token_id:
            raise OROContractError(
                "SZL_ORO_API_TOKEN_PATH and SZL_ORO_API_TOKEN_ID must be set together"
            )
        return BearerTokenAuthorizer.from_file(token_id=token_id, path=path)
    if not production and os.environ.get("SZL_ORO_ALLOW_DEVELOPMENT_AUTH") == "1":
        return BearerTokenAuthorizer.development()
    return None
