# SPDX-License-Identifier: Apache-2.0
"""Services/finance: bounded GET-only transport. No broker, signing or write client.

No redirect, environment proxy, caller URL, response logging, or exception-text
serialization. Retrieval freshness and provider market timestamps are distinct.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import hashlib
import hmac
import http.client
import json
import os
import re
import ssl
import threading
import time
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

VERSION = "1.0.1"
PROVIDER_WAIT_SECONDS = 0.25
ALLOWED_HOSTS = frozenset({
    "gamma-api.polymarket.com", "clob.polymarket.com", "external-api.kalshi.com",
    "api.exchange.coinbase.com", "data.sec.gov", "api.fiscaldata.treasury.gov",
    "api.bls.gov", "api.stlouisfed.org", "data.alpaca.markets",
})


class FinanceError(ValueError):
    """Only stable, non-secret codes may leave the source boundary."""
    def __init__(self, code: str, retry_after: float = 15):
        self.code = code
        self.retry_after = max(1.0, min(float(retry_after), 3600.0))
        super().__init__(code)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_revision(env: Mapping[str, str]) -> str:
    """Resolve the canonical runtime convention without hiding conflicting aliases.

    SZL_GIT_SHA is the existing production build-info convention. The two
    earlier finance aliases remain supported only when every supplied identity
    is a full, non-placeholder SHA and all agree. This is reported process
    identity, not a verified signature or publication receipt.
    """
    observed: set[str] = set()
    for name in ("SZL_GIT_SHA", "SZL_SOURCE_REVISION", "A11OY_GIT_SHA"):
        value = env.get(name, "")
        if not isinstance(value, str):
            return "UNBOUND"
        value = value.strip()
        if not value:
            continue
        if re.fullmatch(r"[0-9a-f]{40}", value) is None or value == "0" * 40:
            return "UNBOUND"
        observed.add(value)
    return next(iter(observed)) if len(observed) == 1 else "UNBOUND"


def stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")


def strict_json(raw: bytes) -> Any:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise FinanceError("DUPLICATE_JSON_KEY")
            out[key] = value
        return out
    def invalid(_):
        raise FinanceError("NONFINITE_JSON")
    try:
        return json.loads(raw, parse_float=Decimal, parse_constant=invalid,
                          object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, FinanceError):
            raise
        raise FinanceError("INVALID_JSON") from None


@dataclass(frozen=True)
class Plan:
    source: str
    provider: str
    url: str = field(repr=False)
    public_url: str
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    ttl: int = 30
    max_bytes: int = 4_000_000
    min_interval: float = 0.3
    # Secret-derived cache partition; never exported in evidence.
    partition: str = field(default="public", repr=False)


def retry_seconds(value: str | None, now: float) -> float:
    try:
        if value is None:
            return 30.0
        if value.isdigit():
            return max(1.0, min(float(value), 3600.0))
        return max(1.0, min(parsedate_to_datetime(value).timestamp() - now, 3600.0))
    except (ValueError, TypeError, OverflowError):
        return 30.0


def fetch_bytes(plan: Plan) -> bytes:
    """Single bounded HTTPS GET; ignores proxy env and does not follow redirects."""
    parsed = urlsplit(plan.url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.fragment):
        raise FinanceError("DESTINATION_DENIED")
    target = parsed.path + ("?" + parsed.query if parsed.query else "")
    headers = {"Accept": "application/json", "Accept-Encoding": "identity",
               "User-Agent": "SZL-Finance-ReadOnly/1.0 (+https://a-11-oy.com)",
               **plan.headers}
    conn = http.client.HTTPSConnection(parsed.hostname, timeout=6,
                                      context=ssl.create_default_context())
    conn.set_debuglevel(0)
    deadline = time.monotonic() + 12
    try:
        conn.request("GET", target, headers=headers)
        res = conn.getresponse()
        if res.status != 200:
            delay = retry_seconds(res.getheader("Retry-After"), time.time())
            raise FinanceError("UPSTREAM_HTTP_" + str(res.status), delay)
        mime = (res.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        if mime != "application/json" and not mime.endswith("+json"):
            raise FinanceError("NON_JSON_RESPONSE")
        if (res.getheader("Content-Encoding") or "identity").lower() not in ("", "identity"):
            raise FinanceError("ENCODED_RESPONSE_DENIED")
        declared = res.getheader("Content-Length")
        if declared and (not declared.isdigit() or int(declared) > plan.max_bytes):
            raise FinanceError("RESPONSE_TOO_LARGE")
        chunks, length = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FinanceError("RESPONSE_DEADLINE")
            if conn.sock is not None:
                conn.sock.settimeout(min(6, remaining))
            chunk = res.read(min(65_536, plan.max_bytes + 1 - length))
            if not chunk:
                break
            length += len(chunk)
            if length > plan.max_bytes:
                raise FinanceError("RESPONSE_TOO_LARGE")
            chunks.append(chunk)
        return b"".join(chunks)
    except (OSError, http.client.HTTPException):
        raise FinanceError("TRANSPORT_UNAVAILABLE") from None
    finally:
        conn.close()


class FinanceClient:
    """Bounded process cache and single-flight per provider, never a trade ledger.

    Returned data are deep copies. Expired data retain their original fetch time
    on refresh failure and are labeled STALE with ok=false. Source cooldowns also
    apply to different instruments; a new symbol cannot bypass an HTTP 429.
    """
    def __init__(self, *, fetch: Callable[[Plan], bytes] = fetch_bytes,
                 clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic,
                 environ: Mapping[str, str] | None = None, capacity: int = 128):
        if not 1 <= capacity <= 128:
            raise ValueError("capacity must be 1..128")
        self.fetch, self.clock, self.monotonic = fetch, clock, monotonic
        self.environ = os.environ if environ is None else environ
        self.capacity = capacity
        self._cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._guard = threading.RLock()
        self._provider_locks = {p: threading.Lock() for p in (
            "polymarket", "kalshi", "coinbase", "sec", "treasury", "bls", "fred", "alpaca")}
        self._next: dict[str, float] = {}
        self._last: dict[str, dict] = {}
        self._last_cache_expiry: dict[str, float] = {}

    def registry(self) -> dict:
        from .sources import SOURCES
        with self._guard:
            observations = deepcopy(self._last)
            expiries = dict(self._last_cache_expiry)
            tick = self.monotonic()

        def observed_state(source: str) -> str:
            state = observations.get(source, {}).get("state", "NOT_PROBED")
            if state in ("SNAPSHOT", "CACHED") and tick >= expiries.get(source, float("-inf")):
                return "EXPIRED"
            return state

        return {"schema": "szl.finance.providers/v1", "read_only": True,
                "execution_enabled": False, "canonical_repository": "szl-holdings/a11oy",
                "source_revision": source_revision(self.environ),
                "status_as_of": stamp(self.clock()),
                "observation_scope": "LAST_REQUEST_ONLY_NOT_ALL_INSTRUMENTS",
                "freshness_note": "Registry expiry concerns retrieval TTL, not exchange-price freshness.",
                "vertical": "verticals/puriq-markets", "adapter_version": VERSION,
                "sources": [{"id": source, **spec,
                    "configuration": "PRESENT" if all(self.environ.get(k, "").strip()
                         for k in spec["required_environment"]) else "MISSING",
                    "last_attempt": observations.get(source),
                    "observed_connection": observed_state(source)}
                    for source, spec in SOURCES.items()]}

    def observe(self, source: str, parameters: Mapping[str, str] | None = None,
                *, access_token: str | None = None) -> dict:
        from .sources import SOURCES, build_plan, normalize
        if source not in SOURCES:
            raise FinanceError("UNKNOWN_SOURCE")
        spec = SOURCES[source]
        if spec["private"]:
            expected = self.environ.get("SZL_FINANCE_PRIVATE_READ_TOKEN", "")
            if len(expected) < 32 or not access_token or not hmac.compare_digest(
                    hashlib.sha256(expected.encode()).digest(),
                    hashlib.sha256(access_token.encode()).digest()):
                raise FinanceError("PRIVATE_SOURCE_ACCESS_REQUIRED")
        now = self.clock()
        try:
            plan = build_plan(source, dict(parameters or {}), self.environ, now)
        except FinanceError as exc:
            if exc.code == "INVALID_PARAMETERS":
                raise
            out = self._unavailable(source, now, exc.code)
            self._record(source, out)
            return out
        key = digest([source, dict(plan.parameters), plan.partition])
        lock = self._provider_locks[plan.provider]
        if not lock.acquire(timeout=PROVIDER_WAIT_SECONDS):
            with self._guard:
                old = self._cache.get(key)
            now = self.clock()
            if old is not None and self.monotonic() < old[0]:
                result = deepcopy(old[1])
                result.update(state="CACHED", served_at=stamp(now),
                              retrieval_age_seconds=max(0.0, now - result["retrieved_at_epoch"]))
            else:
                result = self._failure(source, now, "PROVIDER_BUSY", old)
                result["retry_after_seconds"] = 1.0
            self._record(source, result, expires_at=old[0] if result["ok"] else None)
            return result
        try:
            now = self.clock()
            with self._guard:
                old = self._cache.get(key)
                tick = self.monotonic()
                if old is not None and tick < old[0]:
                    self._cache.move_to_end(key)
                    result = deepcopy(old[1])
                    result.update(state="CACHED", served_at=stamp(now))
                    result["retrieval_age_seconds"] = max(0.0, now - result["retrieved_at_epoch"])
                    self._record(source, result, expires_at=old[0])
                    return result
                next_allowed = self._next.get(plan.provider, 0.0)
                if tick < next_allowed:
                    result = self._failure(source, now, "PROVIDER_COOLDOWN", old)
                    result["retry_after_seconds"] = round(next_allowed - tick, 3)
                    self._record(source, result)
                    return result
                self._next[plan.provider] = tick + plan.min_interval
            expires_at = None
            try:
                raw = self.fetch(plan)
                if len(raw) > plan.max_bytes:
                    raise FinanceError("RESPONSE_TOO_LARGE")
                payload = strict_json(raw)
                retrieved = self.clock()
                data = normalize(source, payload, dict(plan.parameters), retrieved)
                identity = source_revision(self.environ)
                proof = {"source": source, "source_url": plan.public_url,
                         "query": dict(plan.parameters), "retrieved_at": stamp(retrieved),
                         "source_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                         "normalized_data_sha256": digest(data), "adapter_version": VERSION,
                         "runtime_reported_source_revision": identity, "signed": False}
                proof["observation_id"] = digest(proof)
                result = {"schema": "szl.finance.observation/v1", "source": source,
                          "state": "SNAPSHOT", "ok": True, "truth_label": "REPORTED",
                          "source_revision": identity,
                          "retrieved_at": stamp(retrieved), "retrieved_at_epoch": retrieved,
                          "served_at": stamp(retrieved), "retrieval_age_seconds": 0.0,
                          "cache_ttl_seconds": plan.ttl,
                          "freshness_note": "Retrieval TTL is not exchange-price freshness or execution eligibility.",
                          "data": data, "provenance": proof, "execution_enabled": False}
                with self._guard:
                    expires_at = self.monotonic() + plan.ttl
                    self._cache[key] = (expires_at, deepcopy(result))
                    self._cache.move_to_end(key)
                    while len(self._cache) > self.capacity:
                        self._cache.popitem(last=False)
            except FinanceError as exc:
                with self._guard:
                    self._next[plan.provider] = max(self._next[plan.provider], self.monotonic() + exc.retry_after)
                result = self._failure(source, self.clock(), exc.code, old)
                result["retry_after_seconds"] = exc.retry_after
            self._record(source, result, expires_at=expires_at)
            return result
        finally:
            lock.release()

    def _record(self, source: str, result: dict, *, expires_at: float | None = None) -> None:
        with self._guard:
            self._last[source] = {"state": result["state"], "ok": result["ok"],
                "served_at": result.get("served_at"), "error": result.get("error"),
                "retrieved_at": result.get("retrieved_at")}
            if expires_at is not None:
                self._last_cache_expiry[source] = expires_at
            else:
                self._last_cache_expiry.pop(source, None)

    def _unavailable(self, source: str, now: float, code: str) -> dict:
        return {"schema": "szl.finance.observation/v1", "source": source,
                "state": "UNAVAILABLE", "ok": False, "truth_label": "UNAVAILABLE",
                "source_revision": source_revision(self.environ),
                "data": None, "provenance": None, "retrieved_at": None,
                "served_at": stamp(now), "error": code, "execution_enabled": False}

    def _failure(self, source: str, now: float, code: str, old) -> dict:
        if old is None:
            return self._unavailable(source, now, code)
        result = deepcopy(old[1])
        result.update(state="STALE", ok=False, served_at=stamp(now), error=code,
                      retrieval_age_seconds=max(0.0, now - result["retrieved_at_epoch"]))
        return result
