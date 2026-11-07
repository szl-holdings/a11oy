#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Origin admission for routes that already have a monetized handler.

This module does not implement signature checks. Configured requests call
``szl_trust_x402_payment_context.validate_payment_context``, the estate copy of
szl-trust ``scripts/x402_payment_context.py``. It does not choose prices, turn
on Cloudflare rules, or emit a settlement receipt.

Enforcement is per family and comes only from process environment:

* ``A11OY_X402_PUBLIC_BASE`` — ``https://host`` with no path. The audience is
  this base plus the request path. ``Host`` and ``X-Forwarded-Host`` are not read.
* ``A11OY_X402_SCHEME`` — ``exact`` or ``upto``.
* ``A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC``, ``A11OY_X402_DATA_AMOUNT_ATOMIC``,
  ``A11OY_X402_EXPERIMENTAL_AMOUNT_ATOMIC`` — the caller's expected atomic price.
* ``A11OY_X402_LEEWAY_SECONDS`` — optional, 0..30, default 5.

A family whose amount is unset is ``UNCONFIGURED``, including when another
family is configured: the handler still runs, spoofed payment headers are not
authority, and no settlement header is written. A family whose amount is set
but whose base, scheme, amount, or leeway is missing or invalid is
``CONFIGURATION_INCOMPLETE`` and that handler does not run. A configured family
verifies ``PAYMENT-CONTEXT`` before the handler. ``exact`` and ``upto`` both
leave settlement to the gateway; this origin does not mint one.

Keys come from ``app.state.x402_keys`` when a test or a deployment injects a
``StaticKeySet``. Otherwise the trust resolver fetches only the pinned
Cloudflare JWKS. There is no token-selected key URL and no JWT replay blacklist.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from starlette.responses import JSONResponse

# Same numeric bounds as szl_trust_x402_payment_context. A test locks the equality.
MIN_ATOMIC = 1_000
MAX_ATOMIC = 100_000_000
DEFAULT_LEEWAY_SECONDS = 5
MAX_LEEWAY_SECONDS = 30

_BASE = re.compile(r"https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?\Z")
_AMOUNT = re.compile(r"[1-9][0-9]*")

_ACOUSTIC = (
    "/v1/acoustic/",
    "/v1/acoustic/burgers",
    "/v1/acoustic/duffing",
    "/v1/acoustic/ns-pathway",
)
_FAMILIES = {
    "acoustic": "A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC",
    "data": "A11OY_X402_DATA_AMOUNT_ATOMIC",
    "experimental": "A11OY_X402_EXPERIMENTAL_AMOUNT_ATOMIC",
}


@dataclass(frozen=True)
class _Policy:
    base: str
    scheme: str
    amount: int
    leeway: int


@dataclass(frozen=True)
class _Outcome:
    kind: str
    status: int = 200
    reason: str = ""

    def response(self) -> JSONResponse:
        body = {
            "state": "UNAVAILABLE" if self.status == 503 else "BLOCKED",
            "reason": self.reason,
            "payment_enforcement": "CONFIGURED" if self.reason != "CONFIGURATION_INCOMPLETE" else "CONFIGURATION_INCOMPLETE",
            "settlement_evidence": False,
            "admission": "DENIED",
        }
        response = JSONResponse(body, status_code=self.status)
        return _stamp(response, self.kind)


def family_for(method: str, path: str) -> str | None:
    """Supported monetized handlers only. Health and proof routes are not here."""
    if (method or "").upper() != "GET":
        return None
    if path in _ACOUSTIC:
        return "acoustic"
    if path == "/v1/data" or path.startswith("/v1/data/"):
        return "data"
    if path == "/api/a11oy/v1/experimental/":
        return "experimental"
    return None


def _raw(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def policy_for(family: str) -> tuple[str, _Policy | None]:
    """Return ``(UNCONFIGURED|CONFIGURATION_INCOMPLETE|CONFIGURED, policy)``.

    An unset family amount stays unconfigured. Shared base and scheme do not
    conscript a family that has no price.
    """
    amount_text = _raw(_FAMILIES[family])
    if not amount_text:
        return "UNCONFIGURED", None
    base = _raw("A11OY_X402_PUBLIC_BASE")
    scheme = _raw("A11OY_X402_SCHEME")
    leeway_text = _raw("A11OY_X402_LEEWAY_SECONDS")
    try:
        leeway = DEFAULT_LEEWAY_SECONDS if not leeway_text else int(leeway_text)
    except ValueError:
        return "CONFIGURATION_INCOMPLETE", None
    if not (0 <= leeway <= MAX_LEEWAY_SECONDS):
        return "CONFIGURATION_INCOMPLETE", None
    if _BASE.fullmatch(base) is None or scheme not in {"exact", "upto"}:
        return "CONFIGURATION_INCOMPLETE", None
    if _AMOUNT.fullmatch(amount_text) is None:
        return "CONFIGURATION_INCOMPLETE", None
    amount = int(amount_text)
    if not MIN_ATOMIC <= amount <= MAX_ATOMIC:
        return "CONFIGURATION_INCOMPLETE", None
    return "CONFIGURED", _Policy(base, scheme, amount, leeway)


def _validator():
    import szl_trust_x402_payment_context as validator
    return validator


def _keys(request, validator):
    override = getattr(getattr(request.app, "state", None), "x402_keys", None)
    if override is not None:
        return override
    return validator.PaymentKeyResolver()


def _now(request) -> int:
    clock = getattr(getattr(request.app, "state", None), "x402_now", None)
    if callable(clock):
        return int(clock())
    return int(time.time())


def evaluate(request) -> _Outcome:
    family = family_for(request.method, request.url.path)
    if family is None:
        return _Outcome("skip")
    state, policy = policy_for(family)
    if state == "UNCONFIGURED":
        return _Outcome("unconfigured")
    if state != "CONFIGURED" or policy is None:
        return _Outcome("reject", 503, "CONFIGURATION_INCOMPLETE")
    try:
        validator = _validator()
    except ImportError:
        return _Outcome("reject", 503, "VALIDATOR_UNAVAILABLE")
    presented = request.headers.getlist("payment-context")
    if len(presented) > 1:
        return _Outcome("reject", 403, "AMBIGUOUS_CONTEXT")
    token = presented[0] if presented else None
    audience = policy.base + request.url.path
    try:
        validator.validate_payment_context(
            token,
            keys=_keys(request, validator),
            expected_audience=audience,
            now=_now(request),
            scheme=policy.scheme,
            expected_amount=policy.amount,
            leeway=policy.leeway,
            request_url=audience,
        )
    except validator.PaymentHold as hold:
        status = 503 if hold.reason == "KEYS_UNAVAILABLE" else 403
        return _Outcome("reject", status, hold.reason)
    return _Outcome("verified")


def _stamp(response, kind: str):
    if kind == "skip":
        return response
    label = {
        "unconfigured": "unconfigured",
        "verified": "context-verified",
    }.get(kind, "rejected")
    response.headers["x-a11oy-payment-enforcement"] = label
    response.headers["x-a11oy-settlement-evidence"] = "false"
    for name in ("payment-settlement", "payment-response"):
        if name in response.headers:
            del response.headers[name]
    return response


async def payment_gate(request, call_next):
    """Reject a configured paid route before its handler. Never mint settlement."""
    outcome = evaluate(request)
    if outcome.kind == "reject":
        return outcome.response()
    response = await call_next(request)
    return _stamp(response, outcome.kind)
