from __future__ import annotations

"""Deterministic JSON and digest helpers.

The encoder is deliberately small and explicit. It produces stable UTF-8 JSON for
Council Kernel protocol objects, rejects non-finite floats, normalizes UTC time,
and never serializes arbitrary object attributes. It is not advertised as a full
RFC 8785 implementation; protocol schemas identify it as ``SZL-CJ/1``.
"""

import base64
import binascii
import dataclasses
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$")
_DIGEST = re.compile(r"^(sha256|sha3-256):[0-9a-f]{64}$")
_B64URL = re.compile(r"^[A-Za-z0-9_-]*$")
_MAX_SAFE_INTEGER = 2**53 - 1


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValidationError(f"invalid RFC3339 timestamp: {value!r}") from exc
    else:
        raise ValidationError("timestamp must be a string or datetime")
    if parsed.tzinfo is None:
        raise ValidationError("timestamp must include a UTC offset")
    return parsed.astimezone(UTC)


def isoformat_utc(value: str | datetime) -> str:
    return parse_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def require_identifier(value: str, *, field: str = "identifier") -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValidationError(f"{field} is not a valid bounded identifier")
    return value


def require_digest(value: str, *, field: str = "digest") -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValidationError(f"{field} must be sha256:<64 hex> or sha3-256:<64 hex>")
    return value


def _normalize_float(value: float) -> int | float:
    if not math.isfinite(value):
        raise ValidationError("non-finite floats are forbidden in canonical protocol data")
    if value == 0:
        return 0
    if value.is_integer() and abs(value) <= 2**53:
        return int(value)
    # Stable decimal round-trip. JSON's encoder uses the shortest repr in supported Python.
    return float(repr(value))


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INTEGER:
            raise ValidationError(
                "integers outside the interoperable ±(2^53-1) range must be encoded as strings"
            )
        return value
    if isinstance(value, float):
        return _normalize_float(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValidationError("non-finite Decimal is forbidden")
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return isoformat_utc(value)
    if isinstance(value, Enum):
        return normalize(value.value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, bytes):
        return {"$bytes": base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")}
    if dataclasses.is_dataclass(value):
        return normalize(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError("canonical JSON object keys must be strings")
            result[key] = normalize(item)
        return result
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [normalize(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return normalize(value.to_dict())
    raise ValidationError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_text(value: Any, *, pretty: bool = False) -> str:
    normalized = normalize(value)
    if pretty:
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return canonical_json_bytes(normalized).decode("utf-8")


def digest_bytes(data: bytes, *, algorithm: str = "sha256") -> str:
    if algorithm == "sha256":
        return "sha256:" + hashlib.sha256(data).hexdigest()
    if algorithm == "sha3-256":
        return "sha3-256:" + hashlib.sha3_256(data).hexdigest()
    raise ValidationError(f"unsupported digest algorithm: {algorithm}")


def digest_object(value: Any, *, algorithm: str = "sha256") -> str:
    return digest_bytes(canonical_json_bytes(value), algorithm=algorithm)


def file_digest(path: str | Path, *, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha3-256":
        hasher = hashlib.sha3_256()
    else:
        raise ValidationError(f"unsupported digest algorithm: {algorithm}")
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return f"{algorithm}:{hasher.hexdigest()}"


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValidationError("base64url value must be a string")
    if not _B64URL.fullmatch(value) or len(value) % 4 == 1:
        raise ValidationError("invalid canonical base64url value")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("invalid base64url value") from exc
    if b64url_encode(decoded) != value:
        raise ValidationError("non-canonical base64url encoding")
    return decoded


def redact_digest(value: str, *, visible: int = 12) -> str:
    require_digest(value)
    algorithm, hex_value = value.split(":", 1)
    return f"{algorithm}:{hex_value[:visible]}…"
