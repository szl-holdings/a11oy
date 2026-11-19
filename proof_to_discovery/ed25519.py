#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pure-Python Ed25519 signing and verification (RFC 8032, verification-first).

The Proof-to-Discovery engine must not pretend that content hashes are
signatures. This module provides real Ed25519 signatures with no third-party
dependency, so the acceptance suite can exercise genuine signature paths fully
offline. Correctness is pinned against the RFC 8032 section 7.1 test vectors in
tests/test_proof_to_discovery.py.

Point arithmetic follows RFC 8032 section 5.1.4 exactly: extended homogeneous
coordinates (X, Y, Z, T) with x = X/Z, y = Y/Z, xy = T/Z, using the complete
addition and doubling formulas from that section. Signing exists only so
deterministic fixtures and the admission demonstration can produce honestly
signed records. The engine itself only ever verifies.
"""

from __future__ import annotations

import hashlib

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)

# Extended homogeneous point: (X, Y, Z, T) with x = X/Z, y = Y/Z, xy = T/Z.
_Point = tuple[int, int, int, int]


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


def _to_extended(affine: tuple[int, int]) -> _Point:
    x, y = affine
    return (x, y, 1, x * y % _P)


def _point_add(p: _Point, q: _Point) -> _Point:
    # RFC 8032 section 5.1.4 addition (complete for all valid inputs).
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = t1 * 2 * _D * t2 % _P
    d = z1 * 2 * z2 % _P
    e = b - a
    f = d - c
    g = d + c
    h = b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _point_double(p: _Point) -> _Point:
    # RFC 8032 section 5.1.4 doubling.
    x1, y1, z1, _t1 = p
    a = x1 * x1 % _P
    b = y1 * y1 % _P
    c = 2 * z1 * z1 % _P
    h = a + b
    e = h - (x1 + y1) * (x1 + y1) % _P
    g = a - b
    f = c + g
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _point_mul(s: int, p: _Point) -> _Point:
    q: _Point = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _point_add(q, p)
        p = _point_double(p)
        s >>= 1
    return q


def _point_compressed(p: _Point) -> bytes:
    x1, y1, z1, _t1 = p
    x = x1 * _inv(z1) % _P
    y = y1 * _inv(z1) % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _point_decompress(data: bytes) -> tuple[int, int]:
    if len(data) != 32:
        raise ValueError("Ed25519 point must be 32 bytes")
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _P:
        raise ValueError("Ed25519 y coordinate out of field")
    xx = (y * y - 1) * _inv(_D * y * y + 1) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = x * _I % _P
    if (x * x - xx) % _P != 0:
        raise ValueError("Ed25519 point is not on the curve")
    if x == 0 and sign:
        raise ValueError("Ed25519 invalid sign bit")
    if x & 1 != sign:
        x = _P - x
    return (x, y)


_BASE_POINT_HEX = "5866666666666666666666666666666666666666666666666666666666666666"
_BASE = _to_extended(_point_decompress(bytes.fromhex(_BASE_POINT_HEX)))
_NEUTRAL: _Point = (0, 1, 1, 0)


def _secret_expand(seed: bytes) -> tuple[int, bytes]:
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    digest = _sha512(seed)
    a = int.from_bytes(digest[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, digest[32:]


def public_key(seed: bytes) -> bytes:
    """Derive the Ed25519 public key for a 32-byte seed."""
    a, _prefix = _secret_expand(seed)
    return _point_compressed(_point_mul(a, _BASE))


def sign(seed: bytes, message: bytes) -> bytes:
    """Produce a 64-byte detached Ed25519 signature over ``message``."""
    public = public_key(seed)
    a, prefix = _secret_expand(seed)
    r = int.from_bytes(_sha512(prefix + message), "little") % _L
    rp = _point_compressed(_point_mul(r, _BASE))
    k = int.from_bytes(_sha512(rp + public + message), "little") % _L
    s = (r + k * a) % _L
    return rp + int.to_bytes(s, 32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a detached Ed25519 signature; return False on any malformed input.

    Implements the RFC 8032 section 5.1.7 verification: ``[S]B == R + [k]A``
    with ``k = SHA-512(R || A || message) mod L``, rejecting non-canonical
    ``S`` and off-curve points. Fail-closed: any malformed input yields False,
    never an exception.
    """
    if len(public) != 32 or len(signature) != 64:
        return False
    try:
        point_a = _to_extended(_point_decompress(public))
        point_r = _to_extended(_point_decompress(signature[:32]))
        s = int.from_bytes(signature[32:], "little")
        if s >= _L:
            return False
        k = int.from_bytes(_sha512(signature[:32] + public + message), "little") % _L
        left = _point_mul(s, _BASE)
        right = _point_add(point_r, _point_mul(k, point_a))
        return _point_compressed(left) == _point_compressed(right)
    except (ValueError, IndexError, OverflowError):
        return False
