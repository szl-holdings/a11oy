#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Emit a process-local request budget for Sentra's public verifier manifest.

This is a bounded observation cache, not a receipt verifier or durable evidence
store. No request, provider write, or receipt emission happens during import.
"""

APP_SUFFIX = r'''

# A shared process-local budget covers both /api/live and /readyz. A cached
# manifest describes an earlier GET, never a successful receipt verification.
if CFG.get("slug") == "sentra":
    import copy as _sentra_copy
    import math as _sentra_math
    from email.utils import parsedate_to_datetime as _sentra_parse_date
    from threading import Lock as _SentraLock

    SENTRA_MIN_INTERVAL_SECONDS = 30
    SENTRA_LAST_GOOD_TTL_SECONDS = 120
    SENTRA_MAX_BACKOFF_SECONDS = 300

    class SentraUpstreamBudget:
        def __init__(self):
            self._lock = _SentraLock()
            self._next_attempt = 0.0
            self._failures = 0
            self._good = None
            self._good_clock = None
            self._attempt = {}

        @staticmethod
        def _retry_after(value):
            try:
                seconds = float(value)
            except (TypeError, ValueError):
                try:
                    parsed = _sentra_parse_date(value)
                    seconds = parsed.timestamp() - time.time() if parsed.tzinfo else 0
                except (TypeError, ValueError, OverflowError, AttributeError):
                    seconds = 0
            if not _sentra_math.isfinite(seconds):
                return 0
            return min(SENTRA_MAX_BACKOFF_SECONDS, max(0, seconds))

        @staticmethod
        def _manifest_reason(body):
            if not isinstance(body, dict):
                return "UPSTREAM_PAYLOAD_INVALID"
            if body.get("status") == "UNAVAILABLE" or body.get("state") == "UNAVAILABLE" or body.get("ok") is False:
                return "UPSTREAM_DATA_UNAVAILABLE"
            handoff = body.get("try")
            evidence = body.get("evidence")
            if (body.get("schema") != "szl.public-receipt-verifier/manifest/v1"
                    or body.get("state") != "LIVE"
                    or not isinstance(handoff, dict)
                    or handoff.get("method") != "POST"
                    or handoff.get("endpoint") != "/api/a11oy/v1/verify/receipt"
                    or not isinstance(evidence, list)
                    or not all(item in evidence for item in ("signature", "payload_digest", "hash_chain"))):
                return "UPSTREAM_PAYLOAD_INVALID"
            return None

        @staticmethod
        def _rate_limit_fingerprint(response):
            # Diagnostic only: no raw body, request identity, or arbitrary
            # headers are exposed, and this never changes admission/backoff.
            unknown = {"evidence_class": "UNKNOWN", "fingerprint": None}
            try:
                if len(response.content) > 4096:
                    return unknown
                body = response.json()
                error = body.get("error") if isinstance(body, dict) else None
                if (isinstance(error, dict) and error.get("code") == "rate_limited"
                        and response.headers.get("x-ratelimit-policy") == "sliding-window;w=60"):
                    return {"evidence_class": "REPORTED", "fingerprint": "A11OY_SHARED_IP_LIMIT"}
            except (AttributeError, TypeError, ValueError):
                pass
            return unknown

        def observe(self):
            # Holding the lock across the bounded request provides single-flight:
            # concurrent callers use its result, never send duplicate requests.
            with self._lock:
                now = time.monotonic()
                fetched = False
                if now >= self._next_attempt:
                    started = now
                    attempt = {"http_status": None, "reason": "UPSTREAM_UNAVAILABLE"}
                    body = None
                    retry = 0
                    try:
                        response = httpx.get(CFG["upstream"], timeout=15,
                            headers={"User-Agent": "SZLHOLDINGS-Flagship/4.0"})
                        attempt["http_status"] = response.status_code
                        retry = self._retry_after(response.headers.get("retry-after"))
                        if response.status_code == 429:
                            attempt["rate_limit"] = self._rate_limit_fingerprint(response)
                        if response.is_success:
                            if "json" not in response.headers.get("content-type", "").lower():
                                attempt["reason"] = "UPSTREAM_NOT_JSON"
                            else:
                                try:
                                    body = response.json()
                                    attempt["reason"] = self._manifest_reason(body)
                                except (TypeError, ValueError):
                                    attempt["reason"] = "UPSTREAM_PAYLOAD_INVALID"
                        elif response.status_code != 429 and not 500 <= response.status_code < 600:
                            attempt["reason"] = "UPSTREAM_REJECTED"
                    except Exception as exc:
                        # Do not expose an exception message that may contain
                        # credentials or network internals to a public caller.
                        attempt["error_type"] = type(exc).__name__
                    now = time.monotonic()
                    attempt["observed_at"] = time.time()
                    attempt["latency_ms"] = round(max(0, now - started) * 1000, 1)
                    self._attempt = attempt
                    if attempt["reason"] is None:
                        self._failures = 0
                        self._good_clock = now
                        self._good = {"data": body, "http_status": attempt["http_status"],
                            "observed_at": attempt["observed_at"], "latency_ms": attempt["latency_ms"]}
                        fetched = True
                    else:
                        self._failures = min(self._failures + 1, 5)
                        # An explicit invalid contract revokes the earlier
                        # observation immediately; transport failures do not
                        # extend its original finite lifetime.
                        if attempt["reason"] != "UPSTREAM_UNAVAILABLE":
                            self._good = None
                            self._good_clock = None
                    backoff = SENTRA_MIN_INTERVAL_SECONDS * 2 ** max(0, self._failures - 1)
                    delay = min(SENTRA_MAX_BACKOFF_SECONDS, max(backoff, retry))
                    self._next_attempt = now + delay

                age = max(0, now - self._good_clock) if self._good_clock is not None else None
                valid = self._good is not None and age < SENTRA_LAST_GOOD_TTL_SECONDS
                result = {"status": "REACHABLE" if valid and fetched else "SNAPSHOT" if valid else "UNAVAILABLE",
                    "honesty": "HTTP success is reachability, not MEASURED", "receipt_verified": False,
                    "source": CFG["upstream"], "last_attempt": _sentra_copy.deepcopy(self._attempt),
                    "retry_after_seconds": round(max(0, self._next_attempt - now), 3)}
                if valid:
                    result.update({"http_status": self._good["http_status"],
                        "data": _sentra_copy.deepcopy(self._good["data"]), "latency_ms": self._good["latency_ms"],
                        "observation": {"observed_at": self._good["observed_at"], "age_seconds": age,
                            "ttl_seconds": SENTRA_LAST_GOOD_TTL_SECONDS, "cached": not fetched, "scope": "process"}})
                else:
                    result.update({"http_status": self._attempt.get("http_status"),
                        "reason": self._attempt.get("reason") or "UPSTREAM_UNAVAILABLE", "data": None})
                return result

    _sentra_upstream_budget = SentraUpstreamBudget()

    def probe():
        return _sentra_upstream_budget.observe()
'''


def augment(app: str) -> str:
    """Append the isolated Sentra override without modifying the base renderer."""
    if APP_SUFFIX in app:
        raise ValueError("Sentra request budget already installed")
    return app + APP_SUFFIX
