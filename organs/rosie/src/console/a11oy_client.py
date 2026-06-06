"""rosie.console.a11oy_client — typed client for a11oy's HTTP surface.

rosie is the operator console; it commands a11oy, which enforces. This module
is the rosie-side network client for a11oy's `serve` endpoints, so the operator
console can evaluate policy, verify receipt chains, and display the proof ledger
straight from the substrate.

Source of this instillation: the cross-repo mining wire-gap finding (§4 #1) —
"rosie commands a11oy" was declared in rosie-api's own description, but no
rosie -> a11oy HTTP client existed in rosie source. This module is that client.
Strategy: C (wire over a11oy's existing HTTP server).

a11oy endpoints consumed (from packages/receipt-substrate/src/serve.ts):
    GET  /v1/ledger?limit=N        -> {count, total, receipts:[...]}
    GET  /v1/ledger/{hash}         -> {receipt:{...}}
    POST /v1/verify {ledger:[...]} -> {valid, broken_at, errors}
    POST /v1/policy/evaluate       -> {decision, gate, receipt_hash, ...}
    GET  /healthz / /readyz        -> liveness / readiness

Dependency posture: standard library only (urllib). rosie pins its CI deps with
hashes; adding a third-party HTTP client would change that surface, so this
client uses urllib.request to stay zero-new-dependency.

No mocked data path: every method issues a real HTTP request and parses the
real JSON response. The accompanying test boots a real stdlib HTTP server and
exercises every method over real TCP.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class A11oyError(RuntimeError):
    """Raised when a11oy returns a non-2xx status or is unreachable."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class PolicyDecision:
    """Result of POST /v1/policy/evaluate."""

    decision: str  # "allow" | "deny"
    gate: str
    receipt_hash: str
    rationale: str | None = None
    lambda_score: float | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


@dataclass(frozen=True)
class VerifyResult:
    """Result of POST /v1/verify."""

    valid: bool
    broken_at: int | None
    errors: list[str]


class A11oyClient:
    """Client for the a11oy `serve` HTTP surface.

    Args:
        base_url: a11oy base URL, e.g. ``http://a11oy:8080``.
        timeout:  per-request timeout in seconds.
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # --- transport ---------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.base_url + path
        data = None
        headers = {"accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["content-type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:  # non-2xx
            detail = exc.read().decode("utf-8", "replace")
            raise A11oyError(f"{method} {path} -> {exc.code}: {detail}", status=exc.code) from exc
        except urllib.error.URLError as exc:  # connection / timeout / DNS
            raise A11oyError(f"{method} {path} failed: {exc.reason}") from exc

    # --- health ------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """GET /healthz."""
        return self._request("GET", "/healthz")

    def ready(self) -> dict[str, Any]:
        """GET /readyz. Raises A11oyError(status=503) when a11oy is not ready."""
        return self._request("GET", "/readyz")

    # --- ledger (display receipts from a11oy) ------------------------------

    def ledger(self, limit: int = 20) -> dict[str, Any]:
        """GET /v1/ledger?limit=N. Returns {count, total, receipts:[...]}."""
        return self._request("GET", f"/v1/ledger?limit={int(limit)}")

    def receipt(self, hash_: str) -> dict[str, Any]:
        """GET /v1/ledger/{hash}. Returns {receipt:{...}}."""
        from urllib.parse import quote

        return self._request("GET", f"/v1/ledger/{quote(hash_, safe='')}")

    # --- verify ------------------------------------------------------------

    def verify(self, ledger: list[dict[str, Any]]) -> VerifyResult:
        """POST /v1/verify {ledger:[...]}."""
        out = self._request("POST", "/v1/verify", {"ledger": ledger})
        return VerifyResult(
            valid=bool(out.get("valid")),
            broken_at=out.get("broken_at"),
            errors=list(out.get("errors", [])),
        )

    # --- policy ------------------------------------------------------------

    def evaluate_policy(
        self,
        *,
        action_id: str,
        severity: str = "medium",
        decision_class: str | None = None,
        confidence: float = 0.0,
        witnesses: list[Any] | None = None,
    ) -> PolicyDecision:
        """POST /v1/policy/evaluate. Returns the real allow/deny decision."""
        action: dict[str, Any] = {
            "actionId": action_id,
            "severity": severity,
            "confidence": confidence,
            "witnesses": witnesses or [],
        }
        if decision_class is not None:
            action["decisionClass"] = decision_class
        out = self._request("POST", "/v1/policy/evaluate", {"action": action})
        return PolicyDecision(
            decision=str(out.get("decision")),
            gate=str(out.get("gate", "")),
            receipt_hash=str(out.get("receipt_hash", "")),
            rationale=out.get("rationale"),
            lambda_score=out.get("lambda_score"),
        )


def client_from_env(env: dict[str, str] | None = None) -> A11oyClient | None:
    """Build an A11oyClient from ROSIE_A11OY_URL; None if unset."""
    import os

    source = env if env is not None else dict(os.environ)
    url = (source.get("ROSIE_A11OY_URL") or "").strip()
    return A11oyClient(url) if url else None
