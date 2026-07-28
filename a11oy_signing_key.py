# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Shared ECDSA P-256 receipt-signing identity.

Persistent key discovery, in priority order:

1. ``SZL_COSIGN_PRIVATE_PEM`` inline runtime secret.
2. ``SZL_COSIGN_PRIVATE_KEY_PEM`` inline compatibility secret.
3. ``A11OY_RECEIPT_KEY_PEM`` inline compatibility secret.
4. ``A11OY_RECEIPT_KEY_PATH`` mounted PEM file.
5. The first recognized PEM file in ``A11OY_RECEIPT_KEY_DIR`` or the
   conventional ``/etc/szl/receipt-key`` mount.

A configured source that is empty, missing, unreadable, malformed, or not
ECDSA P-256 fails closed. When no persistent source is configured,
``A11OY_REQUIRE_PERSISTENT_SIGNING=1`` also fails closed. Ephemeral fallback is
available only for a non-strict runtime with no configured source.

Results are cached by a configuration identity containing only source names,
paths, flags, and one-way SHA-256 digests. This gives independently initialized
surfaces one process-local fallback identity without retaining secret PEM text
in cache keys or diagnostics. Key material is never logged or returned except
for the public PEM.
"""

import base64
import hashlib
import os
import threading


_DEFAULT_KEY_DIR = "/etc/szl/receipt-key"
_CANDIDATE_FILENAMES = (
    "ecdsa-p256.key",
    "ecdsa-p256.pem",
    "receipt.key",
    "receipt.pem",
    "tls.key",
)
_INLINE_KEY_NAMES = (
    "SZL_COSIGN_PRIVATE_PEM",
    "SZL_COSIGN_PRIVATE_KEY_PEM",
    "A11OY_RECEIPT_KEY_PEM",
)
_KEY_CACHE = {}
_KEY_CACHE_LOCK = threading.Lock()


def _strict_mode_enabled(env=None):
    env = os.environ if env is None else env
    return env.get(
        "A11OY_REQUIRE_PERSISTENT_SIGNING", ""
    ).strip().lower() in {"1", "true", "yes", "on"}


def _pem_digest(pem):
    return hashlib.sha256(pem).hexdigest()


def _file_request(path, strict):
    identity_base = ("file", path, strict)
    if not os.path.isfile(path):
        return (
            identity_base + ("missing",),
            "",
            "",
            "configured receipt key path does not exist: %s" % path,
        )
    try:
        with open(path, "rb") as fh:
            pem = fh.read()
    except Exception as e:
        return (
            identity_base + ("read-error", type(e).__name__),
            "",
            "",
            "failed to read %s: %s" % (path, type(e).__name__),
        )
    return (
        identity_base + (_pem_digest(pem),),
        pem,
        "persistent:%s" % path,
        "",
    )


def _configured_request(env=None):
    env = os.environ if env is None else env
    strict = _strict_mode_enabled(env)

    for name in _INLINE_KEY_NAMES:
        if name not in env:
            continue
        value = env.get(name, "")
        pem = value.encode("utf-8")
        identity = ("env", name, _pem_digest(pem), strict)
        if not value.strip():
            return (
                identity,
                b"",
                "",
                "%s is configured but empty" % name,
            )
        return (identity, pem, "persistent:env:%s" % name, "")

    if "A11OY_RECEIPT_KEY_PATH" in env:
        path = env.get("A11OY_RECEIPT_KEY_PATH", "").strip()
        if not path:
            return (
                ("file", "empty", strict),
                b"",
                "",
                "A11OY_RECEIPT_KEY_PATH is configured but empty",
            )
        return _file_request(path, strict)

    key_dir_env = "A11OY" + "_RECEIPT_KEY_DIR"
    key_dir_configured = key_dir_env in env
    key_dir = env.get(key_dir_env, "").strip()
    if key_dir_configured and not key_dir:
        return (
            ("directory", "empty", strict),
            b"",
            "",
            "A11OY_RECEIPT_KEY_DIR is configured but empty",
        )
    key_dir = key_dir or _DEFAULT_KEY_DIR
    for name in _CANDIDATE_FILENAMES:
        path = os.path.join(key_dir, name)
        if os.path.isfile(path):
            return _file_request(path, strict)

    if key_dir_configured:
        return (
            ("directory", key_dir, "missing", strict),
            b"",
            "",
            "configured receipt key directory contains no candidate key: %s"
            % key_dir,
        )
    if strict:
        return (
            ("strict", "missing", key_dir),
            b"",
            "",
            "persistent signing is required but no key source is configured",
        )
    return (("ephemeral", key_dir), b"", "ephemeral", "")


def load_signing_key(env=None):
    """Return ``(private_key, public_pem, source, error)``.

    ``env`` may be an explicit environment mapping for preflight validation;
    runtime callers default to ``os.environ``.

    ``source`` is ``persistent:env:<name>``, ``persistent:<path>``,
    ``ephemeral``, or ``unavailable``. A configured persistent source never
    falls through to an ephemeral replacement.
    """
    try:
        from cryptography.hazmat.primitives import serialization as _ser
        from cryptography.hazmat.primitives.asymmetric import ec as _ec
    except Exception as e:  # pragma: no cover - crypto not installed
        return (
            None,
            "",
            "unavailable",
            "cryptography unavailable: %s" % type(e).__name__,
        )

    identity, pem, source, request_error = _configured_request(env)

    with _KEY_CACHE_LOCK:
        cached = _KEY_CACHE.get(identity)
        if cached is not None:
            return cached

        if request_error:
            result = (None, "", "unavailable", request_error)
            _KEY_CACHE[identity] = result
            return result

        def _public_pem(private_key):
            return private_key.public_key().public_bytes(
                encoding=_ser.Encoding.PEM,
                format=_ser.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii")

        if source == "ephemeral":
            try:
                private_key = _ec.generate_private_key(_ec.SECP256R1())
                result = (
                    private_key,
                    _public_pem(private_key),
                    "ephemeral",
                    "",
                )
            except Exception as e:  # pragma: no cover
                result = (
                    None,
                    "",
                    "unavailable",
                    "ephemeral keygen failed: %s" % type(e).__name__,
                )
            _KEY_CACHE[identity] = result
            return result

        load_pem = pem
        if b"BEGIN" not in load_pem:
            try:
                load_pem = base64.b64decode(load_pem, validate=True)
            except Exception:
                load_pem = pem
        try:
            private_key = _ser.load_pem_private_key(load_pem, password=None)
        except Exception as e:
            result = (
                None,
                "",
                "unavailable",
                "failed to load %s: %s" % (source, type(e).__name__),
            )
            _KEY_CACHE[identity] = result
            return result

        if not isinstance(private_key, _ec.EllipticCurvePrivateKey):
            result = (
                None,
                "",
                "unavailable",
                "%s is not ECDSA (got %s)"
                % (source, type(private_key).__name__),
            )
            _KEY_CACHE[identity] = result
            return result

        curve_name = getattr(getattr(private_key, "curve", None), "name", "")
        if curve_name != "secp256r1":
            result = (
                None,
                "",
                "unavailable",
                "%s is ECDSA but curve=%s (want secp256r1)"
                % (source, curve_name or "?"),
            )
            _KEY_CACHE[identity] = result
            return result

        try:
            result = (private_key, _public_pem(private_key), source, "")
        except Exception as e:  # pragma: no cover
            result = (
                None,
                "",
                "unavailable",
                "loaded %s but could not derive pubkey: %s"
                % (source, type(e).__name__),
            )
        _KEY_CACHE[identity] = result
        return result
