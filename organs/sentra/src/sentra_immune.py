"""SENTRA immune compatibility entrypoint.

The legacy six-pattern implementation was bypassable through encoding,
Unicode compatibility characters, and unbounded action shapes. Production
callers now pass through the deny-by-default v2 engine. The boolean return
shape remains compatible with the historical Wire B callers.
"""

from __future__ import annotations

from typing import Any

from sentra_immune_v2 import sentra_inspect_v2

# Kept for callers that import the historical signature catalogue. The v2
# scanner is authoritative and includes these plus additional patterns.
THREAT_KEYWORDS = ["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]


def sentra_inspect(packet: dict[str, Any]) -> bool:
    """Return True only when the v2 deny-by-default inspection allows a packet."""
    if not isinstance(packet, dict):
        return False
    normalized = dict(packet)
    normalized.setdefault("action", "inspect")
    try:
        verdict = sentra_inspect_v2(normalized)
    except Exception:
        # A malformed or unexpected packet must never become an allow.
        return False
    return verdict.get("allow") is True and verdict.get("verdict") == "allow"
