"""szl_sentra_client — Rosie → Sentra mesh immune filter client.

ADDITIVE, Doctrine v11. Signed: Yachay. Co-Authored-By: Perplexity Computer Agent.

Founder directive 2026-06-01: Sentra is the MESH IMMUNE SYSTEM — it protects
every organ, every action. Rosie (the personal aide) routes every command
payload through Sentra's provenanced dual-use + prompt-injection filter
(POST /sentra/rosie/filter) before the command is dispatched.

Posture (honest):
  • verdict == "block"  -> Rosie refuses the command (HTTP 403 to the caller).
  • verdict == "warn"   -> Rosie proceeds but records Sentra's reasons + receipt.
  • verdict == "allow"  -> Rosie proceeds normally.

Resilience: if Sentra is unreachable or errors, this client FAILS OPEN with an
explicit "filter_unavailable" marker (never silently claims a clean verdict, and
never crashes Rosie's dispatcher). The immune posture is best-effort screening,
not a hard runtime dependency — Rosie's own Yuyay 2-person gate already guards
dispatch upstream of this call.
"""
from __future__ import annotations

import os
from typing import Any

# Sentra mesh immune system base URL (override via env for local/dev/mesh).
SENTRA_BASE_URL = os.environ.get(
    "SENTRA_BASE_URL", "https://szlholdings-sentra.hf.space"
).rstrip("/")
FILTER_PATH = "/sentra/rosie/filter"
# Short timeout: the filter is a fast substring screen; do not block dispatch.
FILTER_TIMEOUT_S = float(os.environ.get("SENTRA_FILTER_TIMEOUT_S", "4.0"))


def filter_payload(payload: Any, caller: str = "rosie", session_id: str | None = None) -> dict:
    """Call Sentra's /sentra/rosie/filter and return its verdict envelope.

    Returns a dict shaped like Sentra's response:
        {"verdict": "allow|warn|block", "reasons": [...],
         "filtered_payload": <any>, "signed_receipt": <DSSE envelope>}

    On any transport/parse failure, returns a FAIL-OPEN envelope:
        {"verdict": "allow", "reasons": ["filter_unavailable: <err>"],
         "filtered_payload": payload, "signed_receipt": {"signed": False, ...},
         "_filter_unavailable": True}
    """
    body = {"payload": payload, "caller": caller, "session_id": session_id}
    try:
        import httpx  # local import so a missing dep can never crash Rosie at import time

        url = f"{SENTRA_BASE_URL}{FILTER_PATH}"
        resp = httpx.post(url, json=body, timeout=FILTER_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        # Defensive normalisation — never trust shape blindly.
        verdict = data.get("verdict", "allow")
        if verdict not in ("allow", "warn", "block"):
            verdict = "warn"
        return {
            "verdict": verdict,
            "reasons": data.get("reasons", []),
            "filtered_payload": data.get("filtered_payload", payload),
            "signed_receipt": data.get("signed_receipt", {"signed": False}),
        }
    except Exception as e:  # fail open, but honestly flagged
        return {
            "verdict": "allow",
            "reasons": [f"filter_unavailable: {type(e).__name__}: {e}"],
            "filtered_payload": payload,
            "signed_receipt": {
                "signed": False,
                "honesty": "Sentra filter unreachable — failed open; no verdict fabricated.",
                "signatures": [],
            },
            "_filter_unavailable": True,
        }


def is_blocked(envelope: dict) -> bool:
    """True only when Sentra explicitly returned a 'block' verdict."""
    return envelope.get("verdict") == "block"
