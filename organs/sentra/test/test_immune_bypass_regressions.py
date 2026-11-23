# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the documented six-pattern Sentra bypasses."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sentra_immune import sentra_inspect  # noqa: E402


def test_uppercase_variant_is_denied() -> None:
    assert not sentra_inspect({"payload": "DROP TABLE receipts"})


def test_base64_encoded_variant_is_denied() -> None:
    encoded = base64.b64encode(b"rm -rf /tmp/cache").decode("ascii")
    assert not sentra_inspect({"payload": encoded})


def test_unicode_compatibility_variant_is_denied() -> None:
    fullwidth = "ＤＲＯＰ ＴＡＢＬＥ receipts"
    assert not sentra_inspect({"payload": fullwidth})


def test_unknown_action_is_denied_by_default() -> None:
    assert not sentra_inspect({"action": "execute arbitrary code"})


def test_clean_legacy_packet_keeps_boolean_allow_shape() -> None:
    assert sentra_inspect({"operation": "read", "resource": "/api/data"})
