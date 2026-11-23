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


def test_documented_read_action_remains_allowed() -> None:
    assert sentra_inspect({"action": "read", "payload": "safe"})


def test_rate_limit_buckets_remain_bounded() -> None:
    import sentra_immune_v2 as immune_v2

    original_limit = immune_v2._RATE_BUCKET_MAX_CLIENTS
    immune_v2._RATE_BUCKET_MAX_CLIENTS = 2
    immune_v2._RATE_BUCKETS.clear()
    try:
        for index in range(5):
            immune_v2.gate_auth_ratelimit({"client_id": f"client-{index}"})
        assert len(immune_v2._RATE_BUCKETS) <= 2
    finally:
        immune_v2._RATE_BUCKETS.clear()
        immune_v2._RATE_BUCKET_MAX_CLIENTS = original_limit
