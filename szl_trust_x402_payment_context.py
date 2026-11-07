#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-4.0
# Offline x402 PAYMENT-CONTEXT validator. Not a payment gateway and not charging.

"""Canonical Python validator for Cloudflare Monetization Gateway PAYMENT-CONTEXT.

This is the one Python implementation for the estate. Its Workers-runtime twin
is ``ops/evidence-snapshot-worker/src/payment-context.mjs``. Both run the shared
vectors in ``tests/vectors/x402-payment-context.v1.json`` and must return the
same decision and reason code for every vector. ``science_evidence/payment.py``
in governed-receipt-spec is deprecated in favour of this module.

Contract (Cloudflare "Payment validation", page last updated 2026-09-30):

* EdDSA over Ed25519 only. Keys come only from the pinned JWKS
  ``https://payments.cloudflare.com/certs``. A token-supplied ``jku``, ``jwk``,
  ``x5u`` or ``x5c`` is rejected and never requested. A key set that cannot be
  fetched or parsed fails closed, and expired keys are never reused.
* Required claims: ``iat``, ``nbf`` and ``exp`` (integer NumericDate), ``aud``
  (one string equal to the exact resource URL), ``scheme`` (``exact`` or
  ``upto``) and ``amount`` (atomic units as a canonical decimal string).
* The caller states the price it expects. For ``exact`` the signed amount must
  equal it. For ``upto`` the signed maximum must not exceed it, and the origin
  must keep its work and its settlement within the signed maximum. A payment
  made under a cheaper rule, or under the other scheme, is rejected.
* Clock leeway defaults to 5 seconds and is bounded to 0..30 seconds. It
  applies to ``exp``, ``nbf`` and a future ``iat``.
* Cloudflare's documented claims define no ``jti`` or nonce. The optional
  replay guard keys on ``jti`` when one is present, else on the SHA-256 of the
  token, and only within one process.

Production charging cannot be enabled by a boolean in this module.
"""

from __future__ import annotations

import base64
import binascii
import email.utils
import hashlib
import json
import re
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jwt.exceptions import InvalidAlgorithmError, InvalidSignatureError, PyJWTError

PINNED_JWKS_URL = "https://payments.cloudflare.com/certs"
SCHEMES = frozenset({"exact", "upto"})
MIN_ATOMIC = 1_000
MAX_ATOMIC = 100_000_000
DEFAULT_LEEWAY_SECONDS = 5
MAX_LEEWAY_SECONDS = 30
MAX_TOKEN_LENGTH = 8_192
MAX_JWKS_BYTES = 64 * 1024
MAX_JWKS_KEYS = 32
FETCH_TIMEOUT_SECONDS = 5
MAX_SAFE_INTEGER = 2**53 - 1

# Evidence snapshot SKU. Price and audience follow
# docs/monetization/evidence-snapshot-activation-2026-11-02.md and the Worker
# constants in ops/evidence-snapshot-worker/src/index.mjs
# (tests/test_x402_price_alignment.py keeps the three in step). Not offered yet:
# no Monetization Gateway rule exists for this path, the Worker is not
# deployed, and the apex host is a free website under the 2026-11-06 owner
# policy, so the endpoint has to move to an API host before activation.
EVIDENCE_SNAPSHOT_AUDIENCE = "https://a-11-oy.com/api/v1/evidence-snapshot"
EVIDENCE_SNAPSHOT_AMOUNT_ATOMIC = 1_000_000
EVIDENCE_SNAPSHOT_SCHEME = "exact"
PAID_PATH = "/api/v1/evidence-snapshot"
FREE_PATHS = frozenset({
    "/",
    "/healthz",
    "/api/build-info",
    "/api/a11oy/healthz",
    "/.well-known/szl-source.json",
    "/robots.txt",
    "/sitemap.xml",
    "/.well-known/security.txt",
    "/security.txt",
    "/.well-known/mcp.json",
})

FORBIDDEN_HEADER_PARAMS = frozenset({"jku", "jwk", "x5u", "x5c"})
UNSUPPORTED_HEADER_PARAMS = frozenset({"crit", "b64"})

# ASCII-only patterns; the JavaScript twin uses the same expressions.
_AMOUNT = re.compile(r"0|[1-9][0-9]*")
_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
_PATH_CHARS = r"[A-Za-z0-9._~!$&'()*+,;=:@%/-]*"
_AUDIENCE = re.compile(r"https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?/" + _PATH_CHARS)
_REQUEST_URL = re.compile(
    r"([A-Za-z][A-Za-z0-9+.-]*)://([A-Za-z0-9.-]+)(?::([0-9]{1,5}))?(/" + _PATH_CHARS + r")?"
    r"(?:\?[\x21\x22\x24-\x7e]*)?(?:#[\x21-\x7e]*)?"
)
_KEY_X = re.compile(r"[A-Za-z0-9_-]{43}")
_CONTENT_TYPE = re.compile(r"application/(?:json|jwk-set\+json)(?:\s*;|\Z)", re.IGNORECASE)
_DIGITS = re.compile(r"[0-9]+")
_QUOTED_DIGITS = re.compile(r'"([0-9]+)"')


class PaymentHold(Exception):
    """A rejected payment context or configuration. ``reason`` is a stable code."""

    def __init__(self, reason: str, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def production_charging_enabled(_record: Mapping | None = None) -> bool:
    """This source revision cannot turn charging on."""
    return False


def is_free_path(path: str) -> bool:
    return path in FREE_PATHS


def is_explicit_paid_path(path: str, method: str) -> bool:
    return method == "GET" and path == PAID_PATH


def reject_blanket_rule(path: str) -> None:
    if path in {"/*", "/api/*", "/mcp", "/mcp/*"} or path.endswith("/*"):
        raise PaymentHold("BLANKET_PAYMENT_RULE")


# --- strict decoding helpers -------------------------------------------------

def _reject_constant(name: str) -> None:
    raise ValueError(f"non-standard JSON constant {name}")


def _parse_int(text: str) -> int | float:
    # A longer literal cannot be a safe integer; keep it out of int() limits.
    return int(text) if len(text) <= 17 else float(text)


def _strict_json(data: bytes, *, encoding: str = "utf-8") -> object:
    text = data.decode(encoding)  # strict; in tokens a byte-order mark is not JSON whitespace
    return json.loads(text, parse_constant=_reject_constant, parse_int=_parse_int)


def _canonical_segment(segment: str) -> bytes:
    if not segment or _SEGMENT.fullmatch(segment) is None or len(segment) % 4 == 1:
        raise PaymentHold("MALFORMED_TOKEN")
    try:
        decoded = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (binascii.Error, ValueError) as exc:
        raise PaymentHold("MALFORMED_TOKEN") from exc
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != segment:
        raise PaymentHold("MALFORMED_TOKEN")
    return decoded


def _numeric_date(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER else None
    if isinstance(value, float) and value.is_integer() and abs(value) <= MAX_SAFE_INTEGER:
        return int(value)
    return None


def _atomic_text(value: str, reason: str) -> int:
    if _AMOUNT.fullmatch(value) is None:
        raise PaymentHold(reason)
    if len(value) > len(str(MAX_ATOMIC)):
        return MAX_ATOMIC + 1  # canonical but certainly above the maximum
    return int(value)


# --- configuration -----------------------------------------------------------

def _check_config(*, scheme: object, leeway: object, expected_audience: object,
                  expected_amount: object, now: object) -> int:
    if not isinstance(scheme, str) or scheme not in SCHEMES:
        raise PaymentHold("UNKNOWN_SCHEME")
    if type(leeway) is not int or not 0 <= leeway <= MAX_LEEWAY_SECONDS:
        raise PaymentHold("BAD_LEEWAY")
    if not isinstance(expected_audience, str) or _AUDIENCE.fullmatch(expected_audience) is None:
        raise PaymentHold("BAD_AUDIENCE")
    if isinstance(expected_amount, int) and not isinstance(expected_amount, bool):
        expected = expected_amount
    elif isinstance(expected_amount, str):
        expected = _atomic_text(expected_amount, "BAD_EXPECTED_AMOUNT")
    else:
        raise PaymentHold("BAD_EXPECTED_AMOUNT")
    if not MIN_ATOMIC <= expected <= MAX_ATOMIC:
        raise PaymentHold("BAD_EXPECTED_AMOUNT")
    if type(now) is not int or not -MAX_SAFE_INTEGER <= now <= MAX_SAFE_INTEGER:
        raise PaymentHold("BAD_NOW")
    return expected


def request_matches_audience(request_url: object, expected_audience: str) -> bool:
    """Compare scheme, lowercased host, port (443 dropped) and exact path; ignore the query."""
    if not isinstance(request_url, str):
        return False
    match = _REQUEST_URL.fullmatch(request_url)
    if match is None:
        return False
    scheme, host, port, path = match.groups()
    scheme = scheme.lower()
    port_part = f":{port}" if port is not None and not (scheme == "https" and port == "443") else ""
    return f"{scheme}://{host.lower()}{port_part}{path or '/'}" == expected_audience


# --- key sets ----------------------------------------------------------------

@dataclass(frozen=True)
class KeyFetchResponse:
    """What a JWKS retrieval returned. Header names are lowercase."""

    status: int
    headers: Mapping[str, str]
    body: bytes
    url: str = PINNED_JWKS_URL
    redirected: bool = False


def _keys_error(detail: str) -> PaymentHold:
    return PaymentHold("KEYS_UNAVAILABLE", detail)


def _key_set_from_jwks(jwks: object) -> tuple[tuple[str | None, Ed25519PublicKey], ...]:
    if (not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list)
            or not 1 <= len(jwks["keys"]) <= MAX_JWKS_KEYS):
        raise _keys_error("PAYMENT_KEYS_SET_INVALID")
    keys = []
    for key in jwks["keys"]:
        if (not isinstance(key, dict) or key.get("kty") != "OKP" or key.get("crv") != "Ed25519"
                or not isinstance(key.get("x"), str) or _KEY_X.fullmatch(key["x"]) is None
                or "d" in key
                or ("alg" in key and key["alg"] != "EdDSA")
                or ("use" in key and key["use"] != "sig")
                or ("kid" in key and not isinstance(key["kid"], str))
                or ("key_ops" in key and key["key_ops"] != ["verify"])):
            raise _keys_error("PAYMENT_KEYS_ED25519_REQUIRED")
        try:
            public = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(key["x"] + "="))
        except (ValueError, binascii.Error) as exc:
            raise _keys_error("PAYMENT_KEYS_ED25519_REQUIRED") from exc
        keys.append((key.get("kid"), public))
    return tuple(keys)


class StaticKeySet:
    """Keys from a JWKS document already in hand, checked like a fetched set."""

    def __init__(self, jwks: Mapping) -> None:
        self._keys = _key_set_from_jwks(jwks)

    def current_keys(self) -> tuple[tuple[str | None, Ed25519PublicKey], ...]:
        return self._keys


def freshness_seconds(headers: Mapping[str, str], started_at: float, received_at: float) -> float:
    """Seconds the response may be reused: explicit max-age less corrected age."""
    directives: dict[str, str] = {}
    for part in (headers.get("cache-control") or "").split(","):
        name, _, value = part.strip().lower().partition("=")
        if name in directives:
            return 0
        directives[name] = value.strip()
    if "no-cache" in directives or "no-store" in directives:
        return 0
    max_age = directives.get("max-age")
    if max_age is not None:
        quoted = _QUOTED_DIGITS.fullmatch(max_age)
        max_age = quoted.group(1) if quoted else max_age
    age = headers.get("age")
    if age is None:
        age = "0"
    if max_age is None or _DIGITS.fullmatch(max_age) is None or _DIGITS.fullmatch(age) is None:
        return 0
    if len(max_age) > 15 or len(age) > 15:
        return 0  # cannot be a safe millisecond count
    lifetime, age_seconds = int(max_age), int(age)
    if lifetime * 1000 > MAX_SAFE_INTEGER or age_seconds * 1000 > MAX_SAFE_INTEGER:
        return 0
    apparent_age = 0.0
    date_header = headers.get("date")
    if date_header:
        try:
            date = email.utils.parsedate_to_datetime(date_header).timestamp()
        except (TypeError, ValueError, IndexError, OverflowError):
            date = None
        if date is not None:
            apparent_age = max(0.0, received_at - date)
    corrected_age = max(apparent_age, age_seconds + max(0.0, received_at - started_at))
    return max(0.0, lifetime - corrected_age)


def _parse_key_set_response(response: KeyFetchResponse) -> tuple[tuple[str | None, Ed25519PublicKey], ...]:
    if response.status != 200 or response.redirected or (response.url and response.url != PINNED_JWKS_URL):
        raise _keys_error("PAYMENT_KEYS_RESPONSE_INVALID")
    if _CONTENT_TYPE.match(response.headers.get("content-type") or "") is None:
        raise _keys_error("PAYMENT_KEYS_CONTENT_TYPE_INVALID")
    if len(response.body) > MAX_JWKS_BYTES:
        raise _keys_error("PAYMENT_KEYS_BODY_TOO_LARGE")
    try:
        # The Worker's TextDecoder drops one leading byte-order mark; so does utf-8-sig.
        jwks = _strict_json(response.body, encoding="utf-8-sig")
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _keys_error("PAYMENT_KEYS_SET_INVALID") from exc
    return _key_set_from_jwks(jwks)


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
        return None  # urllib then raises HTTPError for the 3xx


def _read_bounded(url: str, *, timeout: float, max_bytes: int,
                  proxies: Mapping[str, str] | None = None) -> KeyFetchResponse:
    handlers: list = [_RefuseRedirects()]
    if proxies is not None:
        handlers.append(urllib.request.ProxyHandler(dict(proxies)))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    deadline = time.monotonic() + timeout
    with opener.open(request, timeout=timeout) as response:
        chunks, size = [], 0
        while True:
            if time.monotonic() > deadline:
                raise _keys_error("PAYMENT_KEYS_FETCH_TIMEOUT")
            chunk = response.read(4096)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise _keys_error("PAYMENT_KEYS_BODY_TOO_LARGE")
            chunks.append(chunk)
        names = {name.lower() for name in response.headers.keys()}
        headers = {name: ", ".join(response.headers.get_all(name) or []) for name in names}
        final_url = response.geturl()
        return KeyFetchResponse(status=response.status, headers=headers, body=b"".join(chunks),
                                url=final_url, redirected=final_url != url)


def fetch_pinned_jwks(url: str, *, timeout: float = FETCH_TIMEOUT_SECONDS,
                      max_bytes: int = MAX_JWKS_BYTES) -> KeyFetchResponse:
    """Default retrieval. Only the pinned URL; redirects refused; size and time bounded."""
    if url != PINNED_JWKS_URL:
        raise _keys_error("PAYMENT_KEYS_URL_NOT_PINNED")
    return _read_bounded(url, timeout=timeout, max_bytes=max_bytes)


@dataclass
class _Flight:
    done: threading.Event
    keys: tuple | None = None
    expires_at: float = 0.0
    error: BaseException | None = None


class PaymentKeyResolver:
    """Fail-closed retrieval of the pinned Cloudflare JWKS.

    Keys are reused only for the response's explicit ``max-age`` reduced by
    ``Age``, the retrieval delay and the apparent age from ``Date``. A failed
    retrieval never falls back to expired keys. Concurrent callers share one
    retrieval. An unknown ``kid`` does not trigger another retrieval while the
    cached set is fresh. ``fetch`` and ``clock`` are testing seams; there is no
    setting that changes the pinned URL or the trust policy.
    """

    def __init__(self, *, fetch: Callable[..., KeyFetchResponse] | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._fetch = fetch or fetch_pinned_jwks
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: tuple[tuple, float] | None = None
        self._flight: _Flight | None = None

    def _retrieve(self) -> tuple[tuple, float]:
        started_at = self._clock()
        try:
            response = self._fetch(PINNED_JWKS_URL, timeout=FETCH_TIMEOUT_SECONDS, max_bytes=MAX_JWKS_BYTES)
        except PaymentHold:
            raise
        except Exception as exc:  # any transport failure means no keys: fail closed
            raise _keys_error("PAYMENT_KEYS_FETCH_FAILED") from exc
        received_at = self._clock()
        keys = _parse_key_set_response(response)
        return keys, received_at + freshness_seconds(response.headers, started_at, received_at)

    def current_keys(self) -> tuple[tuple[str | None, Ed25519PublicKey], ...]:
        with self._lock:
            if self._cached is not None and self._clock() < self._cached[1]:
                return self._cached[0]
            self._cached = None  # never fall back to stale keys
            flight = self._flight
            leader = flight is None
            if leader:
                flight = self._flight = _Flight(done=threading.Event())
        if leader:
            try:
                flight.keys, flight.expires_at = self._retrieve()
            except Exception as exc:  # recorded for every waiter, then raised below
                flight.error = exc
            finally:
                if flight.keys is None and flight.error is None:
                    flight.error = _keys_error("PAYMENT_KEYS_FETCH_FAILED")
                with self._lock:
                    if flight.error is None and self._clock() < flight.expires_at:
                        self._cached = (flight.keys, flight.expires_at)
                    self._flight = None
                flight.done.set()
        elif not flight.done.wait(timeout=2 * FETCH_TIMEOUT_SECONDS + 1):
            raise _keys_error("PAYMENT_KEYS_FETCH_TIMEOUT")
        if flight.error is not None:
            if isinstance(flight.error, PaymentHold):
                raise PaymentHold(flight.error.reason, flight.error.detail) from flight.error
            raise _keys_error("PAYMENT_KEYS_FETCH_FAILED") from flight.error
        return flight.keys


def _candidate_keys(keys: object) -> tuple:
    if isinstance(keys, (PaymentKeyResolver, StaticKeySet)):
        return keys.current_keys()
    if isinstance(keys, Mapping):
        return tuple(keys.items())
    raise PaymentHold("KEYS_UNAVAILABLE", "PAYMENT_KEYS_SOURCE_INVALID")


def _select_key(keys: object, header: Mapping) -> Ed25519PublicKey:
    candidates = _candidate_keys(keys)
    if "kid" in header:
        matches = [key for kid, key in candidates if kid == header["kid"]]
    else:
        matches = [key for _, key in candidates] if len(candidates) == 1 else []
    if len(matches) != 1 or not isinstance(matches[0], Ed25519PublicKey):
        raise PaymentHold("UNKNOWN_KEY")
    return matches[0]


# --- replay guard --------------------------------------------------------------

class MemoryReplayGuard:
    """Remembers accepted contexts until they expire. One process only.

    Cloudflare's documented claims carry no ``jti`` or nonce, so the key is the
    ``jti`` when present and otherwise the SHA-256 of the token. Whether the
    gateway ever re-sends one context (for example on an origin retry) is
    unverified, so this guard is opt-in. When full of unexpired entries it
    rejects new contexts instead of forgetting old ones.
    """

    def __init__(self, *, max_entries: int = 10_000) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self._max_entries = max_entries
        self._seen: dict[str, int] = {}
        self._lock = threading.Lock()

    def check_and_remember(self, key: str, *, expires_at: int, now: int) -> str | None:
        with self._lock:
            for seen_key, seen_expiry in list(self._seen.items()):
                if seen_expiry <= now:
                    del self._seen[seen_key]
            if key in self._seen:
                return "REPLAYED"
            if len(self._seen) >= self._max_entries:
                return "REPLAY_CACHE_FULL"
            self._seen[key] = expires_at
            return None


# --- validation ----------------------------------------------------------------

def _parse_header(token: object) -> tuple[dict, list[str]]:
    if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:
        raise PaymentHold("MALFORMED_TOKEN")
    segments = token.split(".")
    if len(segments) != 3:
        raise PaymentHold("MALFORMED_TOKEN")
    decoded = [_canonical_segment(segment) for segment in segments]
    try:
        header = _strict_json(decoded[0])
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise PaymentHold("MALFORMED_TOKEN") from exc
    if not isinstance(header, dict):
        raise PaymentHold("MALFORMED_TOKEN")
    return header, segments


def _check_header(header: Mapping) -> None:
    if header.get("alg") != "EdDSA":
        raise PaymentHold("WRONG_ALGORITHM")
    if FORBIDDEN_HEADER_PARAMS.intersection(header):
        raise PaymentHold("TOKEN_SUPPLIED_KEY_MATERIAL")
    if UNSUPPORTED_HEADER_PARAMS.intersection(header):
        raise PaymentHold("UNSUPPORTED_HEADER")
    if "kid" in header and (not isinstance(header["kid"], str) or not header["kid"]):
        raise PaymentHold("MALFORMED_TOKEN")


def _verified_payload(token: str, key: Ed25519PublicKey) -> bytes:
    try:
        return jwt.PyJWS().decode_complete(token, key, algorithms=["EdDSA"])["payload"]
    except InvalidSignatureError as exc:
        raise PaymentHold("BAD_SIGNATURE") from exc
    except InvalidAlgorithmError as exc:
        raise PaymentHold("WRONG_ALGORITHM") from exc
    except PyJWTError as exc:
        raise PaymentHold("MALFORMED_TOKEN") from exc


def _check_times(claims: Mapping, *, now: int, leeway: int) -> tuple[int, int, int]:
    iat, nbf, exp = (_numeric_date(claims.get(name)) for name in ("iat", "nbf", "exp"))
    if iat is None or nbf is None or exp is None:
        raise PaymentHold("TIME_CLAIMS_INVALID")
    if iat > exp or nbf > exp:
        raise PaymentHold("TIME_CLAIMS_INVALID")
    if exp <= now - leeway:
        raise PaymentHold("EXPIRED")
    if nbf > now + leeway or iat > now + leeway:
        raise PaymentHold("NOT_YET_VALID")
    return iat, nbf, exp


def validate_payment_context(
    token: object,
    *,
    keys: object,
    expected_audience: str,
    now: int,
    scheme: str,
    expected_amount: int | str,
    leeway: int = DEFAULT_LEEWAY_SECONDS,
    request_url: str | None = None,
    replay_guard: MemoryReplayGuard | None = None,
) -> dict:
    """Return verified claims, or raise ``PaymentHold`` with a stable reason code.

    ``keys`` is a ``PaymentKeyResolver`` (production), a ``StaticKeySet``, or a
    mapping of ``kid`` to ``Ed25519PublicKey``. ``expected_amount`` is the
    catalog price in atomic units: the fixed price for ``exact``, the maximum
    for ``upto``. ``request_url``, when given, must name the audience.
    """
    expected = _check_config(scheme=scheme, leeway=leeway, expected_audience=expected_audience,
                             expected_amount=expected_amount, now=now)
    if token is None or token == "":
        raise PaymentHold("ABSENT")
    header, _segments = _parse_header(token)
    _check_header(header)
    key = _select_key(keys, header)
    payload = _verified_payload(token, key)
    try:
        claims = _strict_json(payload)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise PaymentHold("MALFORMED_TOKEN") from exc
    if not isinstance(claims, dict):
        raise PaymentHold("MALFORMED_TOKEN")
    iat, nbf, exp = _check_times(claims, now=now, leeway=leeway)
    if not isinstance(claims.get("aud"), str) or claims["aud"] != expected_audience:
        raise PaymentHold("WRONG_AUDIENCE")
    if request_url is not None and not request_matches_audience(request_url, expected_audience):
        raise PaymentHold("REQUEST_NOT_AUDIENCE")
    if claims.get("scheme") != scheme:
        raise PaymentHold("WRONG_SCHEME")
    if not isinstance(claims.get("amount"), str):
        raise PaymentHold("MALFORMED_AMOUNT")
    amount = _atomic_text(claims["amount"], "MALFORMED_AMOUNT")
    if not MIN_ATOMIC <= amount <= MAX_ATOMIC:
        raise PaymentHold("AMOUNT_OUT_OF_BOUNDS")
    if scheme == "exact" and amount != expected:
        raise PaymentHold("AMOUNT_MISMATCH")
    if scheme == "upto" and amount > expected:
        raise PaymentHold("AMOUNT_ABOVE_MAXIMUM")
    token_sha256 = hashlib.sha256(token.encode("ascii")).hexdigest()
    if replay_guard is not None:
        jti = claims.get("jti")
        replay_key = f"jti:{jti}" if isinstance(jti, str) and jti else f"sha256:{token_sha256}"
        refusal = replay_guard.check_and_remember(replay_key, expires_at=exp + leeway, now=now)
        if refusal is not None:
            raise PaymentHold(refusal)
    return {
        "audience": claims["aud"],
        "scheme": scheme,
        "amount": amount,
        "iat": iat,
        "nbf": nbf,
        "exp": exp,
        "kid": header.get("kid"),
        "token_sha256": token_sha256,
        "settlement_evidence": False,
    }


def settlement_value(*, scheme: str, status_code: int, actual: int, authorized: int) -> str | None:
    """Header value for a future activated upto response. Exact pricing sets nothing."""
    if type(status_code) is not int:
        raise PaymentHold("BAD_STATUS")
    if status_code >= 400 or scheme == "exact":
        return None
    if scheme != "upto":
        raise PaymentHold("UNKNOWN_SCHEME")
    if type(actual) is not int or type(authorized) is not int:
        raise PaymentHold("INTEGER_ATOMIC_AMOUNTS_REQUIRED")
    if not 0 <= actual <= authorized:
        raise PaymentHold("AMOUNT_OUT_OF_BOUNDS")
    return json.dumps({"amount": str(actual)}, separators=(",", ":"))


def emit_production_settlement(**_kwargs: object) -> None:
    if production_charging_enabled() is not False:
        raise PaymentHold("ACTIVATION_PATH_INVALID")
    raise PaymentHold("COMMERCIAL_NOT_ENABLED")


def decide_delivery(*, path: str, method: str, context: dict | None) -> dict:
    """Fail closed. A valid context still does not deliver paid bytes."""
    reject_blanket_rule(path)
    if production_charging_enabled() is not False:
        raise PaymentHold("ACTIVATION_PATH_INVALID")
    if method == "OPTIONS" and (is_free_path(path) or path == PAID_PATH):
        return {
            "http_status": 204,
            "state": "DISCOVERY",
            "body": None,
            "cache_control": "private, no-store",
            "settlement": None,
        }
    if is_free_path(path) and method in {"GET", "HEAD"}:
        return {
            "http_status": 200,
            "state": "FREE",
            "body": None if method == "HEAD" else "PUBLIC",
            "cache_control": "public, max-age=60",
            "settlement": None,
        }
    if path == PAID_PATH and method in {"GET", "HEAD"}:
        state = "COMMERCIAL_NOT_ENABLED" if context else "UNPAID"
        return {
            "http_status": 403 if context else 402,
            "state": state,
            "body": None,
            "cache_control": "private, no-store",
            "settlement": None,
        }
    return {
        "http_status": 404,
        "state": "NOT_A_PAID_ROUTE",
        "body": None,
        "cache_control": "no-store",
        "settlement": None,
    }
