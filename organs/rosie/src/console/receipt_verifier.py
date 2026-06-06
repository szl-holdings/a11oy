"""rosie.console.receipt_verifier — DSSE/PAE v1 HMAC-SHA-256 verification.

The Receipt Verifier is the operator console's strongest interactive demo
asset: paste a DSSE envelope, get a deterministic valid / tampered / malformed
verdict. This module is the verification core, lifted out of the Gradio Space
into a plain, testable library so the same logic backs the UI, the API, and
the CLI.

Envelope shape (DSSE v1):

    {
      "payloadType": "application/vnd.szl.receipt+json;v=1",
      "payload": "<base64 of the canonical JSON payload>",
      "signatures": [{"keyid": "...", "sig": "<base64 HMAC-SHA-256 over PAE>"}]
    }

PAE (Pre-Authentication Encoding) follows the DSSE spec:

    "DSSEv1 " || len(type) || " " || type || " " || len(payload) || " " || payload

The signing key is the shared development HMAC key. This is a *symmetric*
demo verifier: it proves "signed by someone holding the dev key", which is
anyone who can read the public source. It is deliberately NOT production PKI.
The key is labelled `not-for-production` for exactly this reason.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

# HMAC key for receipt verification.
# MUST be injected as HF Space secret ROSIE_HMAC_KEY (env var).
# Without it, verification uses a PLACEHOLDER path and is informational only.
# DO NOT hardcode a real key here — the founder injects real keys as HF Space secrets.
import os as _os_rv
import logging as _logging_rv
_ROSIE_HMAC_KEY_RAW = _os_rv.environ.get("ROSIE_HMAC_KEY")
if _ROSIE_HMAC_KEY_RAW:
    DEV_HMAC_KEY: bytes = _ROSIE_HMAC_KEY_RAW.encode("utf-8")
    _HMAC_KEY_IS_PLACEHOLDER = False
else:
    # Key not set — verification is informational only (PLACEHOLDER mode).
    DEV_HMAC_KEY = b""  # Empty placeholder — will never match real signatures
    _HMAC_KEY_IS_PLACEHOLDER = True
    _logging_rv.warning(
        "ROSIE_HMAC_KEY env var is not set. "
        "Receipt verification is INFORMATIONAL ONLY (PLACEHOLDER mode). "
        "Inject the key as an HF Space secret before relying on verification results."
    )

DEFAULT_PAYLOAD_TYPE = "application/vnd.szl.receipt+json;v=1"


class Verdict(str, Enum):
    """Three terminal verdicts the verifier can return."""

    VALID = "valid"
    TAMPERED = "tampered"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of verifying one envelope.

    Attributes:
        verdict:  VALID, TAMPERED, or MALFORMED.
        ok:       True iff verdict is VALID.
        message:  Human-readable explanation.
        payload:  Decoded payload dict when VALID, else None.
        keyid:    keyid of the matched signature when VALID, else None.
    """

    verdict: Verdict
    ok: bool
    message: str
    payload: dict[str, Any] | None = None
    keyid: str | None = None


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE v1 Pre-Authentication Encoding.

    Args:
        payload_type: The envelope payloadType string.
        payload:      Raw (decoded) payload bytes.

    Returns:
        The PAE byte-string that is HMAC'd to produce the signature.
    """
    pt = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(pt)).encode() + b" " + pt + b" "
        + str(len(payload)).encode() + b" " + payload
    )


def sign_payload(
    payload: dict[str, Any] | bytes,
    *,
    payload_type: str = DEFAULT_PAYLOAD_TYPE,
    key: bytes = DEV_HMAC_KEY,
    keyid: str = "szl-dev-hmac-v1",
) -> dict[str, Any]:
    """Build a signed DSSE envelope for ``payload`` (test/fixture helper).

    Args:
        payload:      A JSON-serialisable dict, or raw payload bytes.
        payload_type: Envelope payloadType.
        key:          HMAC key (defaults to the shared dev key).
        keyid:        keyid recorded in the signature object.

    Returns:
        A complete DSSE envelope dict with a valid signature.
    """
    if isinstance(payload, bytes):
        payload_bytes = payload
    else:
        # Canonical, sorted JSON so signing is deterministic.
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(key, pae(payload_type, payload_bytes), hashlib.sha256).digest()
    return {
        "payloadType": payload_type,
        "payload": base64.b64encode(payload_bytes).decode(),
        "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode()}],
    }


def verify_envelope(envelope: dict[str, Any], *, key: bytes = DEV_HMAC_KEY) -> VerifyResult:
    """Verify a parsed DSSE envelope dict.

    The verdict is:
      * MALFORMED — required fields missing, or base64 / structure invalid.
      * TAMPERED  — structurally valid but no signature matches the PAE.
      * VALID     — at least one signature is a correct HMAC over the PAE.

    Verification uses :func:`hmac.compare_digest` for constant-time comparison.

    NOTE: If ROSIE_HMAC_KEY env var is not set, key defaults to an empty
    placeholder. Verification will return TAMPERED for all real receipts.
    This is the correct fail-safe: without the key, no forged receipt can
    be declared VALID, but the operator is informed it is PLACEHOLDER mode.

    Args:
        envelope: Parsed DSSE envelope (dict).
        key:      HMAC key to verify against.

    Returns:
        :class:`VerifyResult`.
    """
    # Guard: if operating in PLACEHOLDER mode, make that explicit.
    if key == b"" and _HMAC_KEY_IS_PLACEHOLDER:
        return VerifyResult(
            Verdict.TAMPERED, False,
            "PLACEHOLDER mode — ROSIE_HMAC_KEY env var not set. "
            "Verification is informational only. Inject the key as an HF Space secret.",
        )
    if not isinstance(envelope, dict):
        return VerifyResult(Verdict.MALFORMED, False, "Envelope is not a JSON object")

    if "payload" not in envelope or "payloadType" not in envelope:
        return VerifyResult(
            Verdict.MALFORMED, False,
            "Envelope missing required 'payload' or 'payloadType' field",
        )

    try:
        payload_bytes = base64.b64decode(envelope["payload"], validate=True)
    except (binascii.Error, ValueError) as exc:
        return VerifyResult(Verdict.MALFORMED, False, f"payload is not valid base64: {exc}")

    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return VerifyResult(
            Verdict.TAMPERED, False, "No signatures present in envelope",
        )

    expected = hmac.new(key, pae(envelope["payloadType"], payload_bytes), hashlib.sha256).digest()

    for sig_obj in signatures:
        if not isinstance(sig_obj, dict) or "sig" not in sig_obj:
            continue
        try:
            sig_bytes = base64.b64decode(sig_obj["sig"], validate=True)
        except (binascii.Error, ValueError):
            continue
        if hmac.compare_digest(expected, sig_bytes):
            try:
                decoded = json.loads(payload_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                return VerifyResult(
                    Verdict.MALFORMED, False,
                    f"Signature valid but payload is not JSON: {exc}",
                )
            return VerifyResult(
                Verdict.VALID, True,
                "HMAC-SHA-256 signature valid — PAE verified",
                payload=decoded,
                keyid=sig_obj.get("keyid"),
            )

    return VerifyResult(
        Verdict.TAMPERED, False, "No matching signature in envelope",
    )


def verify_receipt_json(envelope_json: str, *, key: bytes = DEV_HMAC_KEY) -> VerifyResult:
    """Verify a DSSE envelope supplied as a JSON string (the UI entry point).

    Empty / whitespace input and JSON parse errors map to MALFORMED so the
    caller never has to catch an exception.

    Args:
        envelope_json: Raw JSON text pasted by the operator.
        key:           HMAC key to verify against.

    Returns:
        :class:`VerifyResult`.
    """
    if not envelope_json or not envelope_json.strip():
        return VerifyResult(Verdict.MALFORMED, False, "Empty input — paste a DSSE envelope JSON")
    try:
        envelope = json.loads(envelope_json)
    except json.JSONDecodeError as exc:
        return VerifyResult(Verdict.MALFORMED, False, f"JSON parse error: {exc}")
    return verify_envelope(envelope, key=key)
