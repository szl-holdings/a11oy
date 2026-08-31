"""
sentra_immune_v2 — real deny-by-default 8-gate immune system.

ADDITIVE — does NOT modify sentra_immune.py (v1 preserved for regression).
Doctrine v11 LOCKED — 749/14/163 — ADDITIVE only.
SLSA L1 honest. No Iron Bank / FedRAMP / CMMC.

Gates (deny-by-default — ALL must pass; any FAIL = deny):
  G1: Size guard            — reject payloads > MAX_PACKET_BYTES
  G2: Structural integrity  — JSON schema / dict shape validation
  G3: Recursive pattern scan — threat-pattern scan across all string fields
  G4: Base64 decode-and-rescan — detect encoded bypasses (embedded in G3)
  G5: Entropy check         — flag high-entropy strings (potential exfil)
  G6: Action schema validation — known action vocab only (deny-by-default)
  G7: Payload digest verification — content-addressed integrity (when digest present)
  G8: Authorization claim check / rate-limit + replay protection — nonce window

Each gate helper returns (passed: bool, reason: str, score: float).
The public API sentra_inspect_v2() returns a full verdict dict.

Author: Perplexity Computer Agent · 2026-06-03
Co-Author: Yachay <yachay@szlholdings.ai>
"""

# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION (added by Perplexity Computer Agent, 2026-06)
# Purpose:       The 8-gate deny-by-default immune engine. Start here to
#                understand sentra's core logic.
# Key entry pts: sentra_inspect_v2(payload) -> verdict dict with Khipu receipt
#                Each gate helper returns (passed: bool, reason: str, score: float)
# Gate order:    G1 size, G2 structural, G3 pattern-scan, G4 base64-rescan,
#                G5 entropy, G6 action-schema, G7 digest-verify, G8 auth+replay
# Related mods:  szl_dsse.py (signing), szl_khipu.py (DAG), szl_wire.py (Wire B)
# Doctrine note: Deny-by-default — ANY gate failure = DENY. Never short-circuit
#                to allow. The 8-gate count is canonical (Doctrine v11).
# ---------------------------------------------------------------------------
from __future__ import annotations

import base64
import collections
import hashlib
import json
import math
import re
import threading
import time
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Gate 1 — size guard
MAX_PACKET_BYTES: int = 500_000  # 500 KB hard limit

# Gate 2 — structural integrity
MAX_DEPTH: int = 5
MAX_KEYS: int = 50
MAX_FIELD_LEN: int = 10_000

# Gate 3/4 — threat patterns (expanded, case-insensitive, base64-rescan)
_THREAT_PATTERNS: list[str] = [
    r"drop\s+table",           # SQL injection
    r"rm\s+-rf",               # shell injection
    r"<\s*script",             # XSS
    r"eval\s*\(",              # code injection
    r"subprocess",             # subprocess injection
    r"\.\./\.\./etc",          # path traversal
    r"__import__",             # Python import injection
    r"os\.system",             # OS command injection
    r"exec\s*\(",              # exec injection
    r"base64\.b64decode",      # base64 code injection
    r"<!--.*?-->",             # HTML comment injection
    r"\x00",                   # null byte injection
    r"\\u0000",                # Unicode null injection
    r"javascript:",            # javascript: protocol
    r"data:text/html",         # data URI injection
]
_COMPILED: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _THREAT_PATTERNS
]

# Gate 5 — entropy threshold
# Base64 ≈ 6.0 bits/char; random ≈ 6.0; normal English ≈ 3.5–4.5
_ENTROPY_THRESHOLD: float = 5.5
_ENTROPY_MIN_LEN: int = 100  # only check strings longer than this

# Gate 6 — action schema allowlist
_ALLOWED_ACTION_PREFIXES: frozenset[str] = frozenset([
    "inspect",
    "evaluate",
    "query",
    "decode",
    "classify",
    "attest",
    "healthz",
    "status",
    "verify",
    "report",
    "read_",
    "get_",
    "list_",
    "fetch_",
    "check_",
    "log_",
    "nmap_scan",   # dual-use allowed in threat context
    "connect",
    "write_file",  # allowed by Wire B contract spec
])

# Gate 8 — replay protection (nonce window)
_NONCE_WINDOW_SECONDS: int = 300   # 5-minute nonce validity window
_NONCE_MAX_SIZE: int = 10_000      # max nonces kept in memory
_RATE_LIMIT_MAX: int = 100         # max requests per client per window
_RATE_WINDOW_SECONDS: int = 60     # rate limit window

# ---------------------------------------------------------------------------
# Gate 4 helper — base64 decode-and-rescan
# ---------------------------------------------------------------------------

def _try_decode_b64(s: str) -> str | None:
    """Attempt base64 decode; return decoded string if it looks printable."""
    try:
        # Pad to multiple of 4
        padded = s + "=" * (-len(s) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
        # Only return if decoded content is non-trivial and printable
        if len(decoded) > 2 and sum(c.isprintable() for c in decoded) / len(decoded) > 0.8:
            return decoded
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Gate 3+4 — recursive pattern scan (with base64 rescan embedded)
# ---------------------------------------------------------------------------

def _scan_value(
    v: Any, depth: int = 0
) -> tuple[bool, str, float]:
    """
    Recursively scan a value for threat patterns + base64-encoded threats.
    Returns (passed, reason, score).
    Score 1.0 = clean, 0.0 = threat found.
    """
    if depth > MAX_DEPTH:
        return False, "max_depth_exceeded", 0.0

    if isinstance(v, str):
        if len(v) > MAX_FIELD_LEN:
            return False, "field_too_long", 0.0
        # Scan raw value
        blob = v
        # Gate 4: decode base64 and rescan
        decoded = _try_decode_b64(v)
        if decoded:
            blob = v + " " + decoded
        for pattern in _COMPILED:
            if pattern.search(blob):
                return False, f"threat_pattern:{pattern.pattern[:40]}", 0.0
        return True, "ok", 1.0

    if isinstance(v, dict):
        if len(v) > MAX_KEYS:
            return False, "too_many_keys", 0.0
        for k, val in v.items():
            ok, reason, score = _scan_value(k, depth + 1)
            if not ok:
                return False, f"key:{reason}", 0.0
            ok, reason, score = _scan_value(val, depth + 1)
            if not ok:
                return False, f"value:{reason}", 0.0
        return True, "ok", 1.0

    if isinstance(v, list):
        for item in v:
            ok, reason, score = _scan_value(item, depth + 1)
            if not ok:
                return False, reason, 0.0
        return True, "ok", 1.0

    # Scalars (int, float, bool, None) — safe
    return True, "ok", 1.0


# ---------------------------------------------------------------------------
# Gate 5 — entropy check
# ---------------------------------------------------------------------------

def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string in bits per character."""
    if not s:
        return 0.0
    counts = collections.Counter(s)
    total = len(s)
    return -sum(
        (c / total) * math.log2(c / total) for c in counts.values()
    )


def gate_entropy(packet: dict) -> tuple[bool, str, float]:
    """
    G5: Check all string values for suspiciously high entropy.
    High entropy (> threshold) may indicate encrypted exfil data or obfuscated payloads.
    Returns (passed, reason, score).
    """
    max_entropy = 0.0
    worst_field = ""
    for key, val in packet.items():
        if isinstance(val, str) and len(val) >= _ENTROPY_MIN_LEN:
            e = _shannon_entropy(val)
            if e > max_entropy:
                max_entropy = e
                worst_field = key
    if max_entropy > _ENTROPY_THRESHOLD:
        score = max(0.0, 1.0 - (max_entropy - _ENTROPY_THRESHOLD) / 2.0)
        return (
            False,
            f"high_entropy_field:{worst_field}:{max_entropy:.2f}",
            round(score, 4),
        )
    score = 1.0 - (max_entropy / _ENTROPY_THRESHOLD) * 0.2
    return True, "ok", round(score, 4)


# ---------------------------------------------------------------------------
# Gate 6 — action schema validation
# ---------------------------------------------------------------------------

def gate_action_schema(packet: dict) -> tuple[bool, str, float]:
    """
    G6: Validate that the 'action' field is in the known action vocab.
    Deny-by-default: if no action field or not in allowlist, deny.
    Returns (passed, reason, score).
    """
    action = packet.get("action", "")
    if not action:
        return False, "missing_or_empty_action", 0.0
    action_str = str(action).strip().lower()
    if any(action_str.startswith(prefix) for prefix in _ALLOWED_ACTION_PREFIXES):
        return True, "ok", 1.0
    return False, f"action_not_in_allowlist:{action_str[:60]}", 0.0


# ---------------------------------------------------------------------------
# Gate 7 — payload digest verification
# ---------------------------------------------------------------------------

def gate_digest(packet: dict) -> tuple[bool, str, float]:
    """
    G7: If a 'digest' field is present, verify SHA3-256 content-addressed integrity.
    If no digest field: pass (not required, but checked if provided).
    Returns (passed, reason, score).
    """
    if "digest" not in packet:
        return True, "no_digest_field_skip", 1.0
    payload_without_digest = {k: v for k, v in packet.items() if k != "digest"}
    expected = hashlib.sha3_256(
        json.dumps(payload_without_digest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if packet["digest"] != expected:
        return (
            False,
            f"digest_mismatch:expected={expected[:16]}...",
            0.0,
        )
    return True, "digest_verified", 1.0


# ---------------------------------------------------------------------------
# Gate 8 — authorization claim check + rate limit + replay protection
# ---------------------------------------------------------------------------

_NONCE_STORE: dict[str, float] = {}   # nonce -> timestamp
_RATE_BUCKETS: dict[str, list[float]] = collections.defaultdict(list)  # client_id -> [timestamps]
_NONCE_LOCK = threading.Lock()


def _cleanup_nonces() -> None:
    """Evict expired nonces (called on every gate-8 invocation)."""
    now = time.time()
    expired = [n for n, t in _NONCE_STORE.items() if now - t > _NONCE_WINDOW_SECONDS]
    for n in expired:
        del _NONCE_STORE[n]
    # If store is still too large, evict oldest
    if len(_NONCE_STORE) > _NONCE_MAX_SIZE:
        oldest = sorted(_NONCE_STORE.items(), key=lambda x: x[1])
        for n, _ in oldest[:len(_NONCE_STORE) - _NONCE_MAX_SIZE]:
            del _NONCE_STORE[n]


def gate_auth_ratelimit(packet: dict) -> tuple[bool, str, float]:
    """
    G8: Authorization claim check + rate limit + replay protection.
    
    Checks:
    - If 'nonce' field present: reject replays (nonce seen within window)
    - If 'client_id' field present: enforce rate limit
    - If 'auth_claim' field present: verify it matches expected format
    
    Returns (passed, reason, score).
    """
    now = time.time()
    with _NONCE_LOCK:
        _cleanup_nonces()

        # Replay protection via nonce
        nonce = packet.get("nonce")
        if nonce is not None:
            nonce_str = str(nonce)[:256]
            if nonce_str in _NONCE_STORE:
                age = now - _NONCE_STORE[nonce_str]
                return False, f"replay_detected:nonce_seen_{age:.0f}s_ago", 0.0
            _NONCE_STORE[nonce_str] = now

        # Rate limit per client_id
        client_id = str(packet.get("client_id", packet.get("agent", "anonymous")))[:128]
        bucket = _RATE_BUCKETS[client_id]
        # Evict old entries
        _RATE_BUCKETS[client_id] = [t for t in bucket if now - t < _RATE_WINDOW_SECONDS]
        if len(_RATE_BUCKETS[client_id]) >= _RATE_LIMIT_MAX:
            return (
                False,
                f"rate_limit_exceeded:client={client_id[:30]}:{len(_RATE_BUCKETS[client_id])}/{_RATE_LIMIT_MAX}",
                0.0,
            )
        _RATE_BUCKETS[client_id].append(now)

        # Authorization claim check — if provided, must be a non-empty string
        auth_claim = packet.get("auth_claim")
        if auth_claim is not None:
            if not isinstance(auth_claim, str) or len(auth_claim.strip()) == 0:
                return False, "invalid_auth_claim:empty_or_wrong_type", 0.0
            # Must be plausible DSSE receipt format (starts with 'dsse:' or is a hex string)
            # Honest disclosure: full DSSE verification not yet wired (Sigstore CI pending)
            auth_str = auth_claim.strip()
            if not (auth_str.startswith("dsse:") or re.match(r"^[0-9a-f]{16,}$", auth_str)):
                return (
                    False,
                    "invalid_auth_claim:must_start_with_dsse:_or_be_hex",
                    0.0,
                )

    return True, "ok", 1.0


# ---------------------------------------------------------------------------
# G1 — size guard
# ---------------------------------------------------------------------------

def gate_size(packet: dict) -> tuple[bool, str, float]:
    """
    G1: Reject packets larger than MAX_PACKET_BYTES.
    Returns (passed, reason, score).
    """
    try:
        size = len(json.dumps(packet, separators=(",", ":")).encode("utf-8"))
    except Exception as e:
        return False, f"serialization_error:{e}", 0.0
    if size > MAX_PACKET_BYTES:
        return False, f"packet_too_large:{size}:{MAX_PACKET_BYTES}", 0.0
    score = 1.0 - (size / MAX_PACKET_BYTES) * 0.1
    return True, f"size_ok:{size}", round(score, 4)


# ---------------------------------------------------------------------------
# G2 — structural integrity
# ---------------------------------------------------------------------------

def gate_structure(packet: Any) -> tuple[bool, str, float]:
    """
    G2: Structural integrity — must be a dict with ≤ MAX_KEYS top-level keys.
    Returns (passed, reason, score).
    """
    if not isinstance(packet, dict):
        return False, f"not_a_dict:{type(packet).__name__}", 0.0
    if len(packet) > MAX_KEYS:
        return False, f"too_many_top_level_keys:{len(packet)}", 0.0
    if len(packet) == 0:
        return False, "empty_packet", 0.0
    return True, "ok", 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sentra_inspect_v2(packet: dict) -> dict:
    """
    Real deny-by-default 8-gate immune inspection.

    Gate order (fail-fast, deny on first failure):
      G1: Size guard
      G2: Structural integrity (depth/key count)
      G3: Recursive value scan (threat patterns)
      G4: Base64 decode-and-rescan (embedded in G3)
      G5: Entropy check (high-entropy string detection)
      G6: Action schema validation (allowlist, deny-by-default)
      G7: Payload digest verification (if digest field present)
      G8: Authorization claim + rate limit + replay protection

    Returns:
      {
        "allow": bool,
        "verdict": "allow" | "deny",
        "gates_passed": int,      # 0..8
        "reason": str,            # human-readable; full reason chain on deny
        "gate_scores": {          # per-gate float scores (1.0=clean, 0.0=failed)
          "G1": float, ..., "G8": float
        },
        "doctrine": "v11",
        "slsa": "L1",
        "lambda_status": "Conjecture 1 — NOT theorem"
      }

    HONEST DISCLOSURE:
    - Authorization claim check (G8) validates format only; full DSSE/Sigstore
      verification is pending (SZL Sigstore CI not yet wired — PLACEHOLDER).
    - Rate-limit and nonce store are in-memory per-process; reset on restart.
    - This is v2 pilot — not yet the production gate for all mesh traffic.
    """
    gate_scores: dict[str, float] = {}
    gates_passed = 0
    reason_chain: list[str] = []

    # G1: Size guard
    ok, reason, score = gate_size(packet)
    gate_scores["G1"] = score
    if not ok:
        return _deny(gates_passed, f"G1:{reason}", gate_scores, reason_chain)
    gates_passed += 1
    reason_chain.append(f"G1:pass:{reason}")

    # G2: Structural integrity
    ok, reason, score = gate_structure(packet)
    gate_scores["G2"] = score
    if not ok:
        return _deny(gates_passed, f"G2:{reason}", gate_scores, reason_chain)
    gates_passed += 1
    reason_chain.append(f"G2:pass")

    # G3+G4: Recursive value scan (includes base64 rescan)
    ok, reason, score = _scan_value(packet)
    gate_scores["G3"] = score
    gate_scores["G4"] = score  # G4 is embedded in G3 (base64 decode-rescan)
    if not ok:
        return _deny(gates_passed, f"G3:{reason}", gate_scores, reason_chain)
    gates_passed += 2  # G3 + G4
    reason_chain.append("G3:pass G4:pass(b64-rescan-embedded)")

    # G5: Entropy check
    ok, reason, score = gate_entropy(packet)
    gate_scores["G5"] = score
    if not ok:
        return _deny(gates_passed, f"G5:{reason}", gate_scores, reason_chain)
    gates_passed += 1
    reason_chain.append(f"G5:pass")

    # G6: Action schema validation
    ok, reason, score = gate_action_schema(packet)
    gate_scores["G6"] = score
    if not ok:
        return _deny(gates_passed, f"G6:{reason}", gate_scores, reason_chain)
    gates_passed += 1
    reason_chain.append("G6:pass")

    # G7: Payload digest verification
    ok, reason, score = gate_digest(packet)
    gate_scores["G7"] = score
    if not ok:
        return _deny(gates_passed, f"G7:{reason}", gate_scores, reason_chain)
    gates_passed += 1
    reason_chain.append(f"G7:pass:{reason}")

    # G8: Authorization claim + rate limit + replay protection
    ok, reason, score = gate_auth_ratelimit(packet)
    gate_scores["G8"] = score
    if not ok:
        return _deny(gates_passed, f"G8:{reason}", gate_scores, reason_chain)
    gates_passed += 1
    reason_chain.append("G8:pass")

    # All 8 gates passed — ALLOW
    return {
        "allow": True,
        "verdict": "allow",
        "gates_passed": gates_passed,
        "reason": "all_gates_passed",
        "reason_chain": reason_chain,
        "gate_scores": gate_scores,
        "doctrine": "v11",
        "slsa": "L1",
        "lambda_status": "Conjecture 1 — NOT theorem",
    }


def _deny(
    gates_passed: int,
    reason: str,
    gate_scores: dict[str, float],
    reason_chain: list[str],
) -> dict:
    """Return a deny verdict with full reason chain."""
    return {
        "allow": False,
        "verdict": "deny",
        "gates_passed": gates_passed,
        "reason": reason,
        "reason_chain": reason_chain + [f"DENY:{reason}"],
        "gate_scores": gate_scores,
        "doctrine": "v11",
        "slsa": "L1",
        "lambda_status": "Conjecture 1 — NOT theorem",
    }
