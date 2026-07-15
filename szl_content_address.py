# SPDX-License-Identifier: Apache-2.0
"""Explicit SHA-256 content addressing for protocol and receipt bytes.

This module is deliberately *not* a password or credential derivation API.
Callers must provide one of the narrow protocol purposes below, and the input
bytes are hashed exactly as supplied.  Keeping this operation separate from
PBKDF2-based credential fingerprints prevents accidental reuse while
preserving the byte-for-byte hashes already carried by DSSE envelopes and
Khipu receipts.
"""
from __future__ import annotations

import hashlib


_PURPOSES = frozenset({"dsse-pae", "khipu-receipt", "public-key"})


def sha256_content_address(data: bytes, *, purpose: str) -> str:
    """Return the protocol-compatible SHA-256 hex address of public content.

    ``purpose`` is intentionally mandatory and allowlisted.  Secret values
    belong in a password KDF such as PBKDF2, never in this function.
    """
    if purpose not in _PURPOSES:
        raise ValueError(f"unsupported content-address purpose: {purpose!r}")
    if not isinstance(data, bytes):
        raise TypeError("content address input must be bytes")
    return hashlib.sha256(data).hexdigest()


__all__ = ["sha256_content_address"]
