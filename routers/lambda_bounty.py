"""routers/lambda_bounty.py — Λ-BOUNTY INTAKE receiver (moved verbatim from serve.py).

Wave-K Dev4 refactor-only extraction. Route group:
    GET  /api/lambda-bounty/healthz
    POST /api/lambda-bounty/submit
    GET  /api/lambda-bounty/receipts

Mirrors szl-holdings/lambda-bounty/webhook/intake.py so the endpoint advertised in
lutar-lean/BOUNTY.md is REAL, not a 404.

HONESTY: a receipt acknowledges INTAKE only. Award eligibility is decided SOLELY by
the verify-proof CI on a PR to szl-holdings/lambda-bounty. This receiver never
declares a winner and never moves money. Λ = Conjecture 1, NOT a theorem. Registered
BEFORE the SPA catch-all /{full_path:path}.

DSSE/HMAC receipts are REAL when LAMBDA_BOUNTY_HMAC_KEY is present; an honest
"dev-key" placeholder hmac is emitted (and flagged) when absent. The ledger is
in-memory (ring buffer) on the Space — honest disclosure; durable receipts land in
the repo via the bounty-webhook GitHub Action. ADDITIVE ONLY.

This module is fully self-contained: it uses only stdlib + FastAPI response types.
The state (ring buffer + keys) lives here now instead of at serve.py module scope.
Behavior is byte-identical to the pre-refactor inline block.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import collections as _pr_col
import hashlib as _lb_hashlib
import hmac as _lb_hmac
import json
import os
import re as _lb_re
import threading as _pr_thr

from fastapi import Request
from fastapi.responses import JSONResponse

# --- module state (was serve.py module-scope) --------------------------------
_LB_SIGN_KEY = os.environ.get("LAMBDA_BOUNTY_HMAC_KEY", "dev-key-not-for-prod")
_LB_HMAC_IS_DEV = _LB_SIGN_KEY == "dev-key-not-for-prod"
_LB_PR_RE = _lb_re.compile(r"^https://github\.com/szl-holdings/lambda-bounty/pull/\d+$")
_LB_ALLOWED_AXIOMS = ("propext", "Quot.sound", "Classical.choice")
_LB_LEDGER: _pr_col.deque = _pr_col.deque(maxlen=500)
_LB_LEDGER_LOCK = _pr_thr.Lock()
_LB_CONJECTURE = {
    "id": "Conjecture 1",
    "formula": "F23",
    "status": "OPEN — NOT a theorem",
    "statement": "Any two 9-axis aggregators satisfying A1 idempotence, A2 monotonicity, "
                 "A3 symmetry, A4 zero-absorption agree on every input.",
    "arbiter": "verify-proof CI on a PR to szl-holdings/lambda-bounty (sole, no-bypass)",
}


def _lb_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lb_validate(payload: dict) -> list:
    errs = []
    for k in ("submitter", "pr_url", "lean_toolchain", "axiom_print", "sorry_free_claim"):
        if k not in payload:
            errs.append(f"missing required field: {k}")
    if "pr_url" in payload and not _LB_PR_RE.match(str(payload.get("pr_url", ""))):
        errs.append("pr_url must be https://github.com/szl-holdings/lambda-bounty/pull/<n>")
    if payload.get("lean_toolchain") not in (None, "leanprover/lean4:v4.13.0"):
        errs.append("lean_toolchain must be leanprover/lean4:v4.13.0")
    if payload.get("sorry_free_claim") is not True:
        errs.append("sorry_free_claim must be true (CI verifies independently)")
    sub = payload.get("submitter")
    if not isinstance(sub, dict) or not sub.get("name"):
        errs.append("submitter.name is required")
    ap = payload.get("axiom_print", "")
    if ap and "sorryAx" in str(ap):
        errs.append("axiom_print contains sorryAx — proof is incomplete")
    return errs


def _lb_prev_hash() -> str:
    if not _LB_LEDGER:
        return "genesis"
    return _LB_LEDGER[-1].get("hash", "genesis")


def _lb_make_receipt(payload: dict, accepted: bool, errors: list) -> dict:
    body = {
        "receipt_type": "lambda_bounty_intake",
        "conjecture": "Conjecture 1 (F23 Λ-aggregator uniqueness)",
        "ts": _lb_now(),
        "submitter": (payload.get("submitter") or {}).get("name", "?"),
        "pr_url": payload.get("pr_url"),
        "accepted_intake": accepted,
        "errors": errors,
        "eligibility_note": "Intake acknowledgement only. Award eligibility = verify-proof CI green on the PR.",
        "prev": _lb_prev_hash(),
    }
    digest = _lb_hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    sig = _lb_hmac.new(_LB_SIGN_KEY.encode(), digest.encode(), _lb_hashlib.sha256).hexdigest()
    body["hash"] = digest
    body["hmac_sha256"] = sig
    body["hmac_key"] = "dev-key-placeholder (set LAMBDA_BOUNTY_HMAC_KEY for a real signature)" if _LB_HMAC_IS_DEV else "env-provided"
    return body


def register(app) -> dict:
    """Attach the Λ-bounty intake route group to `app`, identically to the prior
    inline serve.py block. Called BEFORE the SPA catch-all."""

    @app.get("/api/lambda-bounty/healthz")
    async def _lb_healthz():
        """Λ-bounty intake liveness + live Conjecture-1 status. Λ = NOT a theorem."""
        return JSONResponse({"status": "ok", "service": "lambda-bounty-intake",
                             "conjecture": _LB_CONJECTURE, "doctrine": "v11",
                             "receipts_buffered": len(_LB_LEDGER)})

    @app.post("/api/lambda-bounty/submit")
    async def _lb_submit(request: Request):
        """Validate a Conjecture-1 submission payload, emit a hash-chained Khipu
        intake receipt. 200 + receipt (accepted) or 422 + errors (rejected); a
        receipt is appended either way. Eligibility is decided ONLY by verify-proof
        CI on the PR — this never declares a winner."""
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse({"error": "payload must be a JSON object"}, status_code=400)
        errors = _lb_validate(payload)
        accepted = len(errors) == 0
        receipt = _lb_make_receipt(payload, accepted, errors)
        with _LB_LEDGER_LOCK:
            _LB_LEDGER.append(receipt)
        return JSONResponse(status_code=(200 if accepted else 422), content={
            "accepted_intake": accepted, "errors": errors, "receipt": receipt,
            "next_step": "Open a PR to szl-holdings/lambda-bounty; verify-proof CI is the sole arbiter.",
        })

    @app.get("/api/lambda-bounty/receipts")
    async def _lb_receipts():
        """Append-only intake receipt ledger as NDJSON. In-memory ring buffer
        (maxlen=500); resets on Space rebuild (honest disclosure). Durable receipts
        are committed to the repo by the bounty-webhook GitHub Action."""
        from fastapi.responses import PlainTextResponse as _LBPlain
        with _LB_LEDGER_LOCK:
            lines = "\n".join(json.dumps(r) for r in _LB_LEDGER)
        return _LBPlain(lines, media_type="application/x-ndjson")

    return {"ok": True, "ns": "lambda-bounty", "routes": [
        "/api/lambda-bounty/healthz",
        "/api/lambda-bounty/submit",
        "/api/lambda-bounty/receipts",
    ]}
