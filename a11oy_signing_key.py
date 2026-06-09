# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
#
# a11oy persistent signing identity.
#
# a11oy historically generated a fresh ephemeral ECDSA P-256 key at every boot,
# so its public key (served at /cosign.pub and /api/a11oy/v1/wow/cosign.pub)
# changed on every pod restart and receipts signed before a restart could no
# longer be verified against the live key.
#
# This module provides ONE loader, shared by serve.py and the wow endpoints, that
# prefers a PERSISTENT ECDSA P-256 key mounted from a Kubernetes Secret (BYOK /
# provisioned by the receipt-key-init hook) and falls back to an ephemeral key
# only when no persistent key is mounted. The same public key then verifies
# receipts across restarts.
#
# The signing curve stays ECDSA P-256 (SECP256R1) to match cosign.pub and every
# existing verify path — it is deliberately NOT Ed25519.
#
# Key discovery (first match wins):
#   * env A11OY_RECEIPT_KEY_PATH  — explicit path to a PEM private key file, OR
#   * env A11OY_RECEIPT_KEY_DIR   — directory (default /etc/szl/receipt-key)
#     searched for candidate filenames:
#         ecdsa-p256.key, ecdsa-p256.pem, receipt.key, receipt.pem, tls.key
#
# Returns a 4-tuple: (private_key, public_pem_str, source, err)
#   source ∈ {"persistent:<path>", "ephemeral", "unavailable"}
#   err is "" on success, else a short reason string.
#
# Key material is NEVER logged or returned in any form except the PUBLIC PEM.

import os

# Default mount path for the receipt-signing Secret (matches the chart volume).
_DEFAULT_KEY_DIR = "/etc/szl/receipt-key"
_CANDIDATE_FILENAMES = (
    "ecdsa-p256.key",
    "ecdsa-p256.pem",
    "receipt.key",
    "receipt.pem",
    "tls.key",
)


def _candidate_paths():
    """Yield candidate private-key file paths, most explicit first."""
    explicit = os.environ.get("A11OY_RECEIPT_KEY_PATH", "").strip()
    if explicit:
        yield explicit
    key_dir = os.environ.get("A11OY_RECEIPT_KEY_DIR", "").strip() or _DEFAULT_KEY_DIR
    for name in _CANDIDATE_FILENAMES:
        yield os.path.join(key_dir, name)


def load_signing_key():
    """Load a11oy's receipt-signing key.

    Prefers a persistent ECDSA P-256 PEM mounted from a Secret; falls back to a
    freshly generated ephemeral ECDSA P-256 key. Returns
    (private_key, public_pem_str, source, err).
    """
    try:
        from cryptography.hazmat.primitives import serialization as _ser
        from cryptography.hazmat.primitives.asymmetric import ec as _ec
    except Exception as e:  # pragma: no cover - crypto not installed
        return (None, "", "unavailable", "cryptography unavailable: %r" % (e,))

    def _pub_pem(priv):
        return priv.public_key().public_bytes(
            encoding=_ser.Encoding.PEM,
            format=_ser.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    # 1) Persistent key mounted from a Secret.
    last_err = ""
    for path in _candidate_paths():
        try:
            if not path or not os.path.isfile(path):
                continue
            with open(path, "rb") as fh:
                pem = fh.read()
            priv = _ser.load_pem_private_key(pem, password=None)
        except Exception as e:
            # A present-but-unreadable key is worth surfacing, but keep scanning.
            last_err = "failed to load %s: %r" % (path, e)
            continue
        # Enforce ECDSA P-256 — anything else is rejected (no silent downgrade).
        if not isinstance(priv, _ec.EllipticCurvePrivateKey):
            last_err = "key at %s is not ECDSA (got %s)" % (
                path, type(priv).__name__)
            continue
        curve_name = getattr(getattr(priv, "curve", None), "name", "")
        if curve_name != "secp256r1":
            last_err = "key at %s is ECDSA but curve=%s (want secp256r1)" % (
                path, curve_name or "?")
            continue
        try:
            return (priv, _pub_pem(priv), "persistent:%s" % path, "")
        except Exception as e:  # pragma: no cover
            last_err = "loaded %s but could not derive pubkey: %r" % (path, e)
            continue

    # 2) Ephemeral fallback (legacy behaviour) — key resets on restart.
    try:
        priv = _ec.generate_private_key(_ec.SECP256R1())
        return (priv, _pub_pem(priv), "ephemeral", "")
    except Exception as e:  # pragma: no cover
        return (None, "", "unavailable",
                last_err or ("ephemeral keygen failed: %r" % (e,)))
