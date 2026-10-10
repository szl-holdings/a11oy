"""Offline verification of Pulse Verity index prints; no trading authority.

The caller supplies a separately acquired, trusted-origin public keyring. A
valid signature authenticates a provider assertion, not the truth of a price.
``full-record`` covers only INDEX_V2_FIELDS; request envelope fields and future
extensions remain unsigned. This module performs no network or storage work.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import time
import unicodedata
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

INDEX_V2_FIELDS = (
    "symbol", "price", "priceText", "at", "grade", "engine", "sources",
    "tier", "confidence", "dispersionBps", "interval.lower", "interval.upper",
    "cadence.band", "cadence.calculatedAgeMs", "cadence.newestSourceAgeMs",
    "cadence.oldestSourceAgeMs", "cadence.p50UpdateMs", "cadence.p95UpdateMs",
)
CORE_SIGNED_FIELDS = ("symbol", "priceText", "at", "grade")
MAX_PRINT_BYTES = 16_384
MAX_KEYRING_BYTES = 65_536
MAX_CANONICAL_BYTES = 8_192
MAX_KEYS = 32
MAX_NUMBER = Decimal("1e15")
FUTURE_TOLERANCE_SECONDS = 2.0
_KID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_SYMBOL = re.compile(r"[A-Z0-9]{2,16}\Z")
_PRICE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")


class _Rejected(ValueError):
    def __init__(self, code: str):
        super().__init__("Signed print rejected")
        self.code = code


def _text(value: Any, *, limit: int = 256) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise _Rejected("INVALID_TEXT")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise _Rejected("CONTROL_CHARACTER")
    return value


def _bounded_object(value: Any, maximum: int, reason: str) -> None:
    if not isinstance(value, dict):
        raise _Rejected(reason)
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=True,
                             separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise _Rejected(reason) from exc
    if len(encoded) > maximum:
        raise _Rejected(reason)


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise _Rejected("INVALID_NUMBER")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise _Rejected("INVALID_NUMBER") from exc
    if not number.is_finite() or number.copy_abs() > MAX_NUMBER:
        raise _Rejected("INVALID_NUMBER")
    return number


def _keyring(ring: Any) -> dict[str, tuple[ec.EllipticCurvePublicKey, str]]:
    _bounded_object(ring, MAX_KEYRING_BYTES, "INVALID_KEYRING")
    rows = ring.get("verificationKeys")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_KEYS:
        raise _Rejected("INVALID_KEYRING")
    # A remotely supplied schema cannot redefine which fields we authenticate.
    if "canonicalV2Fields" in ring:
        schema = ring["canonicalV2Fields"]
        if not isinstance(schema, dict) or schema.get("index") != list(INDEX_V2_FIELDS):
            raise _Rejected("KEYRING_SCHEMA_MISMATCH")
    keys = {}
    for row in rows:
        if not isinstance(row, dict):
            raise _Rejected("INVALID_KEYRING")
        kid, pem = row.get("kid"), row.get("pem")
        if not isinstance(kid, str) or not _KID.fullmatch(kid):
            raise _Rejected("INVALID_KEY_ID")
        if kid in keys:
            raise _Rejected("DUPLICATE_KEY_ID")
        if not isinstance(pem, str) or not 1 <= len(pem) <= 2048:
            raise _Rejected("INVALID_PUBLIC_KEY")
        try:
            key = serialization.load_pem_public_key(pem.encode("ascii"))
        except (ValueError, TypeError, UnicodeError, UnsupportedAlgorithm) as exc:
            raise _Rejected("INVALID_PUBLIC_KEY") from exc
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise _Rejected("PUBLIC_KEY_NOT_P256")
        spki = key.public_bytes(serialization.Encoding.DER,
                               serialization.PublicFormat.SubjectPublicKeyInfo)
        keys[kid] = (key, hashlib.sha256(spki).hexdigest())
    return keys


def _select_key(keys: dict, kid: Any) -> tuple[ec.EllipticCurvePublicKey, str]:
    if not isinstance(kid, str) or not _KID.fullmatch(kid):
        raise _Rejected("INVALID_KEY_ID")
    if kid not in keys:
        raise _Rejected("UNKNOWN_KEY_ID")
    return keys[kid]


def _verify(key: ec.EllipticCurvePublicKey, signature: Any, payload: bytes) -> None:
    if not isinstance(signature, str) or len(signature) != 88:
        raise _Rejected("INVALID_SIGNATURE_ENCODING")
    try:
        raw = base64.b64decode(signature, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _Rejected("INVALID_SIGNATURE_ENCODING") from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != signature:
        raise _Rejected("INVALID_SIGNATURE_ENCODING")
    r, s = int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    try:
        key.verify(utils.encode_dss_signature(r, s), payload, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError) as exc:
        raise _Rejected("SIGNATURE_INVALID") from exc


def _event_time(stamp: Any) -> float:
    if not isinstance(stamp, str) or not _STAMP.fullmatch(stamp):
        raise _Rejected("INVALID_EVENT_TIME")
    try:
        parsed = datetime.fromisoformat(stamp[:-1] + "+00:00")
        epoch = (parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
    except (ValueError, OverflowError) as exc:
        raise _Rejected("INVALID_EVENT_TIME") from exc
    if epoch < 0:
        raise _Rejected("INVALID_EVENT_TIME")
    return epoch


def _core_payload(data: dict, expected_symbol: str | None) -> tuple[bytes, float]:
    if data.get("sig") != "pulse-index-v1":
        raise _Rejected("UNSUPPORTED_V1_VERSION")
    symbol = _text(data.get("symbol"), limit=16)
    if not _SYMBOL.fullmatch(symbol) or (expected_symbol is not None and symbol != expected_symbol):
        raise _Rejected("SYMBOL_MISMATCH")
    price_text = _text(data.get("priceText"), limit=64)
    if not _PRICE.fullmatch(price_text):
        raise _Rejected("INVALID_PRICE_TEXT")
    exact_price = Decimal(price_text)
    if not 0 < exact_price <= MAX_NUMBER:
        raise _Rejected("INVALID_PRICE_TEXT")
    # No float(priceText) round-trip: that could hide a changed decimal value.
    if _number(data.get("price")) != exact_price:
        raise _Rejected("PRICE_TEXT_MISMATCH")
    at = _text(data.get("at"), limit=32)
    grade = _text(data.get("grade"), limit=64)
    event_time = _event_time(at)
    return "\n".join(("pulse-index-v1", symbol, price_text, at, grade)).encode("utf-8"), event_time


def _field(data: dict, path: str) -> Any:
    parts = path.split(".")
    value = data.get(parts[0])
    if len(parts) == 1:
        return value
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _Rejected("INVALID_RECORD_FIELD")
    return value.get(parts[1])


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, (int, float, Decimal)):
        return _number(value)
    raise _Rejected("NONSCALAR_RECORD_FIELD")


def _reject_json_constant(_: str) -> None:
    raise _Rejected("NONFINITE_CANONICAL_VALUE")


def _record(data: dict, keys: dict) -> str:
    block = data.get("v2")
    if not isinstance(block, dict) or block.get("sig") != "pulse-index-v2":
        raise _Rejected("UNSUPPORTED_V2_VERSION")
    if block.get("kid") != data.get("kid"):
        raise _Rejected("V2_KEY_ID_MISMATCH")
    key, fingerprint = _select_key(keys, block.get("kid"))
    canonical = block.get("canonical")
    if not isinstance(canonical, str) or len(canonical) > MAX_CANONICAL_BYTES:
        raise _Rejected("INVALID_V2_CANONICAL")
    try:
        encoded = canonical.encode("utf-8")
    except UnicodeError as exc:
        raise _Rejected("INVALID_V2_CANONICAL") from exc
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise _Rejected("INVALID_V2_CANONICAL")
    # Authenticate the provider's exact bytes before interpreting their claims.
    _verify(key, block.get("signature"), encoded)
    lines = canonical.split("\n")
    if len(lines) != len(INDEX_V2_FIELDS) + 1 or lines[0] != "pulse-index-v2":
        raise _Rejected("V2_FIELD_SCHEMA_MISMATCH")
    for expected, line in zip(INDEX_V2_FIELDS, lines[1:]):
        path, sep, text = line.partition("=")
        if not sep or path != expected or not text or text.strip() != text:
            raise _Rejected("V2_FIELD_SCHEMA_MISMATCH")
        try:
            signed = json.loads(text, parse_float=Decimal, parse_int=Decimal,
                                parse_constant=_reject_json_constant)
        except (ValueError, TypeError, ArithmeticError, RecursionError) as exc:
            raise _Rejected("INVALID_CANONICAL_VALUE") from exc
        signed, actual = _scalar(signed), _scalar(_field(data, path))
        # Python's True == 1 is unsuitable for a signed typed JSON record.
        if type(signed) is not type(actual) or signed != actual:
            raise _Rejected("V2_FIELD_MISMATCH:" + path)
    return fingerprint


def verify_print(
    print_data: Any,
    keyring: Any,
    *,
    now: float | None = None,
    expected_symbol: str | None = None,
    max_age_seconds: float = 30,
) -> dict[str, Any]:
    """Verify an index print with independently supplied public keys.

    All untrusted-input failures are structured results. ``fresh`` additionally
    requires an authenticated v1 timestamp. A supplied but invalid v2 block
    yields ``invalid`` even if v1 survives; missing v2 yields ``price-only``.
    Neither successful result authorizes investment or execution.
    """
    result = {
        "core_valid": False, "record_valid": False,
        "verification_scope": "invalid", "fresh": False,
        "freshness": {"status": "UNAVAILABLE", "age_seconds": None,
                      "max_age_seconds": None,
                      "future_tolerance_seconds": FUTURE_TOLERANCE_SECONDS,
                      "basis": "authenticated_provider_at_vs_local_clock"},
        "reasons": [], "key_fingerprint": None, "signed_fields": [],
        "can_authorize": False,
    }
    try:
        clock = time.time() if now is None else now
        if (isinstance(clock, bool) or not isinstance(clock, (int, float))
                or not 0 <= clock <= 1e15):
            raise _Rejected("INVALID_CLOCK")
        if (isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float))
                or not 0 < max_age_seconds <= 86_400):
            raise _Rejected("INVALID_MAX_AGE")
        result["freshness"]["max_age_seconds"] = max_age_seconds
        if expected_symbol is not None and (not isinstance(expected_symbol, str)
                                           or not _SYMBOL.fullmatch(expected_symbol)):
            raise _Rejected("INVALID_EXPECTED_SYMBOL")
        _bounded_object(print_data, MAX_PRINT_BYTES, "INVALID_PRINT")
        keys = _keyring(keyring)
        payload, event_time = _core_payload(print_data, expected_symbol)
        key, fingerprint = _select_key(keys, print_data.get("kid"))
        _verify(key, print_data.get("signature"), payload)
        result.update(core_valid=True, key_fingerprint=fingerprint,
                      signed_fields=list(CORE_SIGNED_FIELDS))
        age = float(clock) - event_time
        status = "FUTURE" if age < -FUTURE_TOLERANCE_SECONDS else "STALE" if age > max_age_seconds else "FRESH"
        result["freshness"].update(status=status, age_seconds=age)
        result["fresh"] = status == "FRESH"
        if status != "FRESH":
            result["reasons"].append("EVENT_TIME_" + status)
        if "v2" not in print_data:
            result["verification_scope"] = "price-only"
            result["reasons"].append("V2_MISSING")
            return result
        _record(print_data, keys)
        result.update(record_valid=True, verification_scope="full-record",
                      signed_fields=list(INDEX_V2_FIELDS))
    except _Rejected as exc:
        # Only internal decision codes cross the API boundary, never exception
        # messages or chained parser/cryptography diagnostics.
        result["reasons"].append(exc.code)
    return result
