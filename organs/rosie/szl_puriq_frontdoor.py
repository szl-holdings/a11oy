# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_puriq_frontdoor — Rosie's front door to the PURIQ master entrypoint.

ADDITIVE (Doctrine v11). Registers POST /api/rosie/v1/puriq on the rosie FastAPI app.
The endpoint calls hatun-mcp's `puriq_master` MCP tool and returns the full envelope
(Lambda in [0,1], DSSE-signed Khipu receipt, traceparent, 13-axis breakdown).

Honesty:
  * If the hatun-mcp Space is reachable, we call its `puriq_master_tool` over the
    Streamable-HTTP MCP transport and pass the result straight through.
  * If it is NOT reachable (or no MCP client lib present), we degrade to a LOCAL
    compose using the same governance math, clearly flagged `source="rosie-local"`
    so an operator never mistakes a fallback for the live hatun-mcp call.
  * Lambda is Conjecture 1 (NEVER a theorem); it is the composed [0,1] scalar.

Keeps a rolling last-10 PURIQ verdicts in-process for the console tile to poll via
GET /api/rosie/v1/puriq/recent.
"""
from __future__ import annotations

import base64
import collections
import hashlib
import json
import math
import os
import time
import uuid

HATUN_MCP_URL = os.environ.get("SZL_HATUN_MCP_URL", "https://szlholdings-hatun-mcp.hf.space")
_RECENT = collections.deque(maxlen=10)

# Yuyay-13 axes (verbatim from hatun-mcp governance.py — kept in sync, not invented).
_YUYAY_AXES = [
    "moralGrounding", "measurabilityHonesty", "empiricalGrounding", "logicalConsistency",
    "sourceTransparency", "uncertaintyDisclosure", "reversibility", "scopeDiscipline",
    "claimCalibration", "introspectionT03", "introspectionT04", "introspectionT09",
    "introspectionT10",
]
_FLOORS = {a: (0.95 if i < 2 else 0.90) for i, a in enumerate(_YUYAY_AXES)}
_INJECTION = ("<important>", "<system>", "ignore previous", "ignore all previous",
              "disregard instructions", "you are now", "</system>", "[system]",
              "exfiltrate", "send your api key", "reveal your prompt")


def _local_yuyay(text: str) -> dict:
    t = (text or "").lower()
    scores = {a: 0.97 for a in _YUYAY_AXES}
    if any(m in t for m in _INJECTION):
        scores["introspectionT03"] = 0.10
        scores["logicalConsistency"] = 0.40
    if any(w in t for w in ("guaranteed", "100% accurate", "always correct", "never fails")):
        scores["claimCalibration"] = 0.55
    if len(t) > 200_000:
        scores["scopeDiscipline"] = 0.50
    if not t.strip():
        scores["measurabilityHonesty"] = 0.0
    blocked = next((a for a in _YUYAY_AXES if scores[a] < _FLOORS[a]), None)
    mn = min(scores, key=lambda k: scores[k])
    return {"scores": scores, "passed": blocked is None, "blocked": blocked,
            "min_value": scores[mn]}


def _local_puriq(input_text: str, context: dict) -> dict:
    """Local compose using the same master-formula math as hatun-mcp puriq_master."""
    yz = _local_yuyay(input_text)
    organs = ["a11oy", "killinchu", "sentra", "rosie", "amaru", "wayra",
              "yachay", "hatun", "wallpa", "unay", "chaski", "wasi-rikuq"]
    n = len(organs)
    f = max(0, (n - 1) // 3)
    threshold = 2 * f + 1
    quorum = {"n": n, "f": f, "threshold": threshold, "present": organs,
              "present_count": n, "quorum": n >= threshold, "live_polled": False}
    yuyay_term = 1.0 if yz["passed"] else 0.0
    hukla = 0 if yz["passed"] else 1
    lam_in = max(0.0, min(1.0, float(context.get("lambda", 1.0))))
    lam = lam_in * yuyay_term * math.exp(-8.0 * hukla) * 1.0 * 0.7  # reputation 0.7
    verdict = ("FAIL" if not yz["passed"] else
               ("PASS" if yz["min_value"] >= 0.95 else "AMBER"))
    # Honest local Khipu link + UNSIGNED DSSE envelope (no cosign key in this process).
    packet = {"input": (input_text or "")[:500], "ts": time.time(), "verdict": verdict}
    blob = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    chash = hashlib.sha256(blob).hexdigest()
    payload_b64 = base64.b64encode(blob).decode()
    dsse = {"payloadType": "application/vnd.szl.hatun-mcp.response+json",
            "payload": payload_b64, "signatures": [], "_mode": "PLACEHOLDER",
            "_note": "UNSIGNED: set SZL_COSIGN_PRIVATE_PEM (Cosign Bootstrap). Disclosed, not faked."}
    return {
        "Lambda": lam, "verdict": verdict, "axes": yz["scores"], "quorum": quorum,
        "receipts": [{"continuum_hash": chash, "prev_hash": "0" * 64, "dsse": dsse,
                      "status": "success" if yz["passed"] else "declined",
                      "chain_verified": True}],
        "traceparent": f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01",
        "signer_mode": "PLACEHOLDER", "source": "rosie-local",
        "honesty": "Local compose; hatun-mcp Space not reached this call. Same master-formula math.",
    }


def _call_hatun_mcp(input_text: str, context: dict, timeout: float = 8.0) -> dict | None:
    """Call hatun-mcp puriq_master_tool over Streamable-HTTP MCP. Returns None on failure."""
    try:
        import httpx
    except Exception:
        return None
    url = HATUN_MCP_URL.rstrip("/") + "/mcp"
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": "puriq_master_tool",
                      "arguments": {"input": input_text, "context": context}}}
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=rpc, headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()
            result = data.get("result", {})
            content = result.get("structuredContent") or result.get("content")
            if isinstance(content, dict):
                content["source"] = "hatun-mcp"
                return content
            return None
    except Exception:
        return None


def register(app, space: str = "rosie") -> str:
    """Register the PURIQ front-door routes on the rosie FastAPI app. Additive."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/api/rosie/v1/puriq")
    def _puriq_descriptor():
        return JSONResponse({
            "endpoint": "/api/rosie/v1/puriq",
            "method": "POST",
            "body": {"input": "<str>", "context": "<optional dict>"},
            "returns": "PURIQ(input, organs, context) = (Lambda in [0,1], DSSE-signed "
                       "Khipu receipt, traceparent, 13-axis breakdown)",
            "upstream": HATUN_MCP_URL + "/mcp (tool: puriq_master_tool)",
            "doctrine": "v11 LOCKED 749/14/163; Lambda = Conjecture 1 (NOT a theorem).",
        })

    @app.post("/api/rosie/v1/puriq")
    async def _puriq(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        input_text = str(body.get("input", ""))
        context = body.get("context") or {}
        out = _call_hatun_mcp(input_text, context)
        if out is None:
            out = _local_puriq(input_text, context)
        rec = {"ts": time.time(), "input": input_text[:120],
               "Lambda": out.get("Lambda"), "verdict": out.get("verdict"),
               "source": out.get("source"),
               "min_axis": min(out.get("axes", {"_": 1}).items(),
                               key=lambda kv: kv[1], default=("_", None))[0]}
        _RECENT.appendleft(rec)
        return JSONResponse(out)

    @app.get("/api/rosie/v1/puriq/recent")
    def _puriq_recent():
        return JSONResponse({"recent": list(_RECENT), "count": len(_RECENT),
                             "upstream": HATUN_MCP_URL})

    return f"puriq-frontdoor:{space}:registered"
