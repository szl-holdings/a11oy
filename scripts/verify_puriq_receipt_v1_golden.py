#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Independently verify the PurIQ v1 canonical Unicode/number golden vector.

This standard-library implementation deliberately does not import, execute, or
translate the JavaScript verifier. It reconstructs the committed golden value
with Python-native recursion, ECMAScript-compatible number spelling for the
golden domain, and UTF-16 code-unit key ordering, then checks exact UTF-8 bytes
and SHA-256. It is a cross-language golden check, not a second public verifier.
"""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "puriq-receipt-v1-vectors.json"


def _utf16_sort_key(value: str) -> bytes:
    # strict rejects lone surrogates independently of the JavaScript guard.
    return value.encode("utf-16-be", errors="strict")


def _string(value: str) -> str:
    _utf16_sort_key(value)
    # ensure_ascii=False preserves scalar Unicode as JSON.stringify does.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _number(value: int | float) -> str:
    if isinstance(value, bool):
        raise TypeError("booleans are not numbers")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("canonical JSON rejects non-finite numbers")
    if value == 0:
        return "0"

    # Python repr supplies a shortest round-trippable decimal. ECMAScript uses
    # fixed notation for exponents -6 through 20 and compact scientific notation
    # outside that interval; Decimal performs that notation conversion exactly
    # for the committed golden values.
    decimal = Decimal(repr(value))
    exponent = decimal.adjusted()
    if -6 <= exponent < 21:
        rendered = format(decimal, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered

    mantissa, exponent_text = format(decimal.normalize(), "e").split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    exponent_value = int(exponent_text)
    sign = "+" if exponent_value >= 0 else "-"
    return f"{mantissa}e{sign}{abs(exponent_value)}"


def canonical_json(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value, key=_utf16_sort_key)
        return "{" + ",".join(
            f"{_string(key)}:{canonical_json(value[key])}" for key in keys
        ) + "}"
    raise TypeError(f"canonical JSON rejects {type(value).__name__}")


def main() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    golden = document["canonical_vectors"][0]
    rendered = canonical_json(golden["value"])
    encoded = rendered.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    if rendered != golden["canonical"]:
        raise SystemExit("independent canonical bytes differ from committed golden bytes")
    if digest != golden["sha256"]:
        raise SystemExit("independent SHA-256 differs from committed golden digest")
    print(f"PurIQ v1 independent Python golden verified: {digest}")


if __name__ == "__main__":
    main()
