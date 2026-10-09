"""Energy service transport: per-client HMAC reads, plus exact-host Access headers.

Missing or invalid HMAC configuration denies a meter read before network access.
Request authentication is not a receipt signature, Tailscale identity, or measurement
attestation. Keys must be installed separately; this module generates no production key.
"""

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import threading
import time
import urllib.request
from urllib.parse import urlsplit


_HOST = "meter2.a-11-oy.com"
_ID_ENV = "A11OY_METER2_CF_ACCESS_CLIENT_ID"
_SECRET_ENV = "A11OY_METER2_CF_ACCESS_CLIENT_SECRET"
_CLIENT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_HEX_KEY = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_STAMP = re.compile(r"[0-9]{19}\Z")
_AUTH_HEADERS = ("X-SZL-Meter-Client", "X-SZL-Meter-Time", "X-SZL-Meter-Nonce",
                 "X-SZL-Meter-Signature")
_RESERVED = {name.lower() for name in _AUTH_HEADERS} | {
    "cf-access-client-id", "cf-access-client-secret", "host"}
_WINDOW_NS = 30_000_000_000


class MeterAuthConfigurationError(ValueError):
    """Redacted configuration failure, never containing a key or configured URL."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MeterAuthConfigurationError("invalid meter authentication configuration")
        result[key] = value
    return result


def _config(raw):
    try:
        if not isinstance(raw, str) or len(raw) > 16384:
            raise ValueError
        value = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(value, dict) or not 1 <= len(value) <= 16:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise MeterAuthConfigurationError("invalid meter authentication configuration") from None


def _origin_and_target(url):
    """Only HTTPS or exact loopback HTTP; preserve the raw origin-form target."""
    try:
        if (not isinstance(url, str) or not url or not url.isascii()
                or any(ord(c) <= 32 or ord(c) == 127 for c in url)):
            raise ValueError
        parsed = urlsplit(url)
        if parsed.fragment or parsed.username is not None or parsed.password is not None:
            raise ValueError
        host = parsed.hostname
        if not host or parsed.scheme not in ("http", "https"):
            raise ValueError
        if parsed.scheme == "http" and not ipaddress.ip_address(host).is_loopback:
            raise ValueError
        port = parsed.port
        authority = f"[{host}]" if ":" in host else host
        if port is not None and port != (443 if parsed.scheme == "https" else 80):
            authority += f":{port}"
        origin = f"{parsed.scheme}://{authority}"
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        if not target.startswith("/") or target.startswith("//"):
            raise ValueError
        return origin, target
    except (TypeError, ValueError):
        raise MeterAuthConfigurationError("invalid meter authentication target") from None


def _message(method, target, audience, client, stamp, nonce):
    return "\n".join(("szl-meter-hmac-v1", method, target, audience, client, stamp, nonce)).encode("ascii")


def meter_request_headers(url: str) -> dict[str, str]:
    """Sign one exact GET with a fresh nonce; never send keys or follow redirects.

    SZL_METER_HMAC_TARGETS is an origin-keyed JSON object, each entry containing
    exactly client_id and key_hex (32 private bytes in lower-case hex). HTTP is
    restricted to loopback; remote meters require HTTPS. No implicit host match.
    """
    origin, target = _origin_and_target(url)
    entries = _config(os.environ.get("SZL_METER_HMAC_TARGETS", ""))
    for configured_origin, configured_entry in entries.items():
        entry_origin, entry_target = _origin_and_target(configured_origin)
        if (configured_origin != entry_origin or entry_target != "/"
                or not isinstance(configured_entry, dict)
                or set(configured_entry) != {"client_id", "key_hex"}
                or not isinstance(configured_entry["client_id"], str)
                or not _CLIENT.fullmatch(configured_entry["client_id"])
                or not isinstance(configured_entry["key_hex"], str)
                or not _HEX_KEY.fullmatch(configured_entry["key_hex"])):
            raise MeterAuthConfigurationError("invalid meter authentication target configuration")
    entry = entries.get(origin)
    if (not isinstance(entry, dict) or set(entry) != {"client_id", "key_hex"}
            or not isinstance(entry["client_id"], str) or not _CLIENT.fullmatch(entry["client_id"])
            or not isinstance(entry["key_hex"], str) or not _HEX_KEY.fullmatch(entry["key_hex"])):
        raise MeterAuthConfigurationError("meter authentication target is not configured")
    stamp, nonce = str(time.time_ns()), secrets.token_hex(16)
    signature = hmac.new(bytes.fromhex(entry["key_hex"]),
                         _message("GET", target, origin, entry["client_id"], stamp, nonce),
                         hashlib.sha256).hexdigest()
    return {**meter_access_headers(url), **dict(zip(_AUTH_HEADERS, (entry["client_id"], stamp, nonce, signature)))}


class MeterRequestVerifier:
    """Atomic bounded replay protection for a process-scoped read capability.

    Timestamps must be no earlier than this process's start and never in the future.
    This rejects a captured request after a restart, with no persistent GET writes.
    Client/server clocks therefore must be synchronized; clock skew fails closed.
    """

    def __init__(self, audience, keys, *, clock=time.time_ns, capacity=4096):
        origin, target = _origin_and_target(audience)
        if audience != origin or target != "/":
            raise MeterAuthConfigurationError("invalid meter authentication audience")
        keys = _config(keys)
        if (any(not isinstance(k, str) or not _CLIENT.fullmatch(k) or not isinstance(v, str)
                or not _HEX_KEY.fullmatch(v) for k, v in keys.items())
                or len(set(keys.values())) != len(keys)):
            raise MeterAuthConfigurationError("invalid meter authentication keys")
        self._audience = audience
        self._scheme = urlsplit(audience).scheme
        self._keys = {k: bytes.fromhex(v) for k, v in keys.items()}
        self._clock = clock
        self._started = clock()
        self._last_clock = self._started
        self._capacity = capacity
        self._seen = {}
        self._lock = threading.Lock()

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get("SZL_METER_HMAC_AUDIENCE", ""),
                   os.environ.get("SZL_METER_HMAC_CLIENT_KEYS", ""))

    def accepts(self, method, target, headers):
        if method != "GET" or target not in ("/", "/metrics"):
            return False
        hosts = headers.get_all("Host", [])
        if len(hosts) != 1:
            return False
        try:
            origin, host_target = _origin_and_target(self._scheme + "://" + hosts[0])
        except MeterAuthConfigurationError:
            return False
        if origin != self._audience or host_target != "/":
            return False
        values = []
        for name in _AUTH_HEADERS:
            matches = headers.get_all(name, [])
            if len(matches) != 1 or not isinstance(matches[0], str):
                return False
            values.append(matches[0])
        client, stamp, nonce, signature = values
        key = self._keys.get(client)
        if (key is None or not _STAMP.fullmatch(stamp) or not _NONCE.fullmatch(nonce)
                or not _HEX_KEY.fullmatch(signature)):
            return False
        now, signed_at = self._clock(), int(stamp)
        if not self._started <= signed_at <= now or now - signed_at > _WINDOW_NS:
            return False
        expected = hmac.new(key, _message(method, target, self._audience, client, stamp, nonce),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        with self._lock:
            # Read again under the lock: concurrent requests may validate their MACs
            # out of order, but real time at cache insertion must not go backwards.
            now = self._clock()
            if (now < self._last_clock or not self._started <= signed_at <= now
                    or now - signed_at > _WINDOW_NS):
                return False
            self._last_clock = now
            self._seen = {k: deadline for k, deadline in self._seen.items() if deadline >= now}
            replay_key = (client, nonce)
            if replay_key in self._seen or len(self._seen) >= self._capacity:
                return False
            self._seen[replay_key] = signed_at + _WINDOW_NS
        return True


def meter_access_headers(url: str) -> dict[str, str]:
    """Return service-token headers only for HTTPS on the exact meter2 host."""
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != _HOST
                or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None):
            return {}
    except (TypeError, ValueError):
        return {}
    client_id = os.environ.get(_ID_ENV, "")
    client_secret = os.environ.get(_SECRET_ENV, "")
    if not client_id or not client_secret:
        return {}
    if "\r" in client_id or "\n" in client_id or "\r" in client_secret or "\n" in client_secret:
        return {}
    return {"CF-Access-Client-Id": client_id,
            "CF-Access-Client-Secret": client_secret}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward a meter credential to a redirect destination."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def open_meter_get(url: str, *, timeout: float, headers: dict[str, str] | None = None):
    """Open an authenticated GET without redirects; caller closes the response."""
    auth = meter_request_headers(url)
    ordinary = {name: value for name, value in (headers or {}).items()
                if name.lower() not in _RESERVED}
    request = urllib.request.Request(url, headers={**ordinary, **auth}, method="GET")
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)
