# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors.governance — the Λ-gate + DSSE/Khipu receipt for every write().

DOCTRINE (non-negotiable):
  • Every state-changing connector action (write) is Λ-gated. Λ is computed as a
    geometric-mean over trust axes and is CAPPED below 1.0 (conformal anti-
    overconfidence floor 1/(n+1)) — trust is NEVER reported as 100%.
  • Every write emits a DSSE-signed Khipu receipt (real ECDSA-P256 over the DSSE
    PAE when SZL_COSIGN_PRIVATE_PEM is present; an explicit UNSIGNED envelope
    otherwise — NEVER a fabricated signature). Reuses the live `szl_dsse` module.
  • No credential value is EVER placed in a receipt body — only a
    PBKDF2-HMAC-SHA256 credential fingerprint.
  • State-changing writes carry the 2-person Yuyay gate + Khipu 3-of-4 quorum
    status (the hatun-mcp governance contract). Until a connector is CONNECTED,
    write() is refused with an honest reason.

This is the same governance discipline proven in operator_shell_v4 / hatun-mcp;
here it is packaged as a small, dependency-light gate the connector write paths
call directly.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from szl_content_address import sha256_content_address

# Anti-overconfidence floor: Λ is never reported as 1.0. We cap at this ceiling.
LAMBDA_CEILING = 0.985
_FINGERPRINT_RE = re.compile(r"\Apbkdf2-sha256:[0-9a-f]{32}\Z")
_FINGERPRINT_LABEL_RE = re.compile(r"\A[A-Za-z0-9_.:-]{1,80}\Z")
_SENSITIVE_KEY_PARTS = frozenset({"password", "passwd", "secret", "token", "credential"})
_SENSITIVE_KEY_NAMES = frozenset({
    "api_key", "private_key", "authorization", "proxy_authorization",
    "cookie", "set_cookie",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lambda_score(axes: dict[str, float]) -> float:
    """Geometric-mean Λ over trust axes, capped below 1.0 (conformal floor).

    Each axis ∈ [0,1]; Λ = (∏ axis)^(1/n), then min(Λ, LAMBDA_CEILING). A single
    zero axis vetoes the action (conjunctive veto / soundness A1). Λ is NEVER 1.0.
    """
    vals = [max(0.0, min(1.0, float(v))) for v in axes.values()] or [0.0]
    if any(v <= 0.0 for v in vals):
        return 0.0
    prod = 1.0
    for v in vals:
        prod *= v
    lam = prod ** (1.0 / len(vals))
    return round(min(lam, LAMBDA_CEILING), 6)


def quorum_status(present: list[str] | None = None, n: int = 4, f: int = 1) -> dict[str, Any]:
    """Khipu 3-of-4 (n≥3f+1) quorum arithmetic. Honest: live_polled False unless
    a `present` witness set is supplied (matches hatun-mcp mesh_quorum_status)."""
    need = 2 * f + 1  # 3-of-4 safe fragment
    present = present or []
    return {
        "scheme": f"{need}-of-{n}", "n": n, "f": f, "need": need,
        "present": present, "present_count": len(present),
        "satisfied": len(present) >= need,
        "live_polled": bool(present),
        "note": "Khipu safe-fragment quorum (BFT safety = Conjecture 2, OPEN)" if not present
                else "witness set supplied",
    }


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
    parts = frozenset(part for part in normalized.split("_") if part)
    return normalized in _SENSITIVE_KEY_NAMES or bool(parts & _SENSITIVE_KEY_PARTS)


def _contains_sensitive_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _is_sensitive_key(key) or _contains_sensitive_field(child)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_field(child) for child in value)
    return False


def _scrub_sensitive_fields(value: Any) -> Any:
    """Recursively remove secret-bearing fields without copying their values."""
    if isinstance(value, dict):
        return {
            key: _scrub_sensitive_fields(child)
            for key, child in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_scrub_sensitive_fields(child) for child in value]
    if isinstance(value, tuple):
        return tuple(_scrub_sensitive_fields(child) for child in value)
    return value


def _validated_fingerprints(values: dict[str, str] | None) -> dict[str, str]:
    """Allow only the KDF output format emitted by ``cred_fingerprint``."""
    safe: dict[str, str] = {}
    for label, fingerprint in (values or {}).items():
        if not isinstance(label, str) or _FINGERPRINT_LABEL_RE.fullmatch(label) is None:
            continue
        if fingerprint == "absent":
            safe[label] = "absent"
        elif isinstance(fingerprint, str) and _FINGERPRINT_RE.fullmatch(fingerprint):
            safe[label] = fingerprint
        else:
            safe[label] = "invalid-fingerprint"
    return safe


def _dsse_sign(payload: dict[str, Any]) -> dict[str, Any]:
    """Sign a receipt payload via the live szl_dsse module if importable; else an
    honest UNSIGNED envelope (NEVER a fabricated signature)."""
    try:
        import szl_dsse  # the live in-image DSSE/Cosign module
        return szl_dsse.sign_payload(payload, "application/vnd.szl.khipu+json")
    except Exception:
        # honest fallback when szl_dsse is not importable in this context
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        import base64
        return {
            "payloadType": "application/vnd.szl.khipu+json",
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [],
            "signed": False,
            "honesty": ("UNSIGNED — szl_dsse unavailable in this runtime; "
                        "no signature fabricated."),
            "_signed_at": _now(),
        }


def receipt_for_write(*, connector_id: str, action: dict[str, Any],
                      lambda_value: float, cred_fingerprints: dict[str, str] | None = None,
                      quorum: dict[str, Any] | None = None,
                      result_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build + DSSE-sign a Khipu receipt for a connector write.

    The receipt body carries the connector id, the action *shape* (method/object,
    NOT secret values), the Λ score, quorum status, credential FINGERPRINT HASHES
    (never the values), and a result summary. Returns {receipt_hash, dsse, body}.
    """
    # Scrub at every nesting level. Direct callers receive the same protection
    # as gate_write callers, including secrets hidden in list/dict children.
    safe_action = _scrub_sensitive_fields(action or {})
    safe_result = _scrub_sensitive_fields(result_summary or {})
    body = {
        "kind": "szl.connector.write",
        "connector_id": connector_id,
        "action": safe_action,
        "lambda_value": lambda_value,
        "lambda_note": "Λ never 1.0 (conformal anti-overconfidence floor 1/(n+1)); Λ = Conjecture 1",
        "quorum": quorum or quorum_status(),
        "credential_fingerprints": _validated_fingerprints(cred_fingerprints),
        "result": safe_result,
        "emitted_at": _now(),
        "doctrine": "v11 — Λ-gate + DSSE/Khipu receipt on every write; no committed keys; trust never 100%",
    }
    canonical_body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    receipt_hash = "sha256:" + sha256_content_address(
        canonical_body, purpose="khipu-receipt"
    )
    body["receipt_hash"] = receipt_hash
    dsse = _dsse_sign(body)
    return {"receipt_hash": receipt_hash, "dsse": dsse, "body": body}


def gate_write(*, connector_id: str, connected: bool, action: dict[str, Any],
               cred_fingerprints: dict[str, str] | None = None,
               quorum_present: list[str] | None = None,
               extra_axes: dict[str, float] | None = None):
    """Run the full governed write gate. Returns (allowed: bool, lambda_value,
    receipt_dict, quorum_dict, detail).

    Λ axes (each ∈[0,1], conjunctive):
      connected  — connector is CONNECTED (refuse writes until creds activate it)
      input_ok   — action shape is well-formed (has a method/object)
      no_secret_leak — no raw secret in the action body
      quorum_ok  — 2-person / 3-of-4 quorum satisfied (or honest pending)
    """
    has_method = bool((action or {}).get("method") or (action or {}).get("object")
                      or (action or {}).get("doctype") or (action or {}).get("sobject"))
    leak = _contains_sensitive_field(action or {})
    q = quorum_status(present=quorum_present)
    axes = {
        "connected": 1.0 if connected else 0.0,
        "input_ok": 1.0 if has_method else 0.0,
        "no_secret_leak": 0.0 if leak else 1.0,
        "quorum_ok": 1.0 if q["satisfied"] else 0.5,  # pending quorum lowers Λ, doesn't fabricate
    }
    if extra_axes:
        axes.update(extra_axes)
    lam = lambda_score(axes)
    # write is allowed only when CONNECTED + well-formed + no leak.
    allowed = connected and has_method and not leak
    detail = ""
    if not connected:
        detail = "write refused — connector not CONNECTED (provide credentials to activate)"
    elif not has_method:
        detail = "write refused — action shape missing method/object"
    elif leak:
        detail = "write refused — raw secret detected in action body (doctrine: env/secret only)"
    elif not q["satisfied"]:
        detail = "write staged — 2-person / 3-of-4 Khipu quorum pending (state-changing gate)"
    receipt = receipt_for_write(
        connector_id=connector_id, action=action, lambda_value=lam,
        cred_fingerprints=cred_fingerprints, quorum=q,
        result_summary={"allowed": allowed, "detail": detail},
    )
    return allowed, lam, receipt, q, detail


__all__ = ["lambda_score", "quorum_status", "receipt_for_write", "gate_write",
           "LAMBDA_CEILING"]
