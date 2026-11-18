"""Bounded, fail-closed HTTP JSON transport for provider control planes.

This module is deliberately independent from the provider registry so every
provider adapter can share one outbound-security boundary.  It does not log
URLs, headers, request bodies, response bodies, or exception text.  Failures
return stable error codes and never synthesize a document.

Public destinations are allowed by default.  Operator-controlled self-hosted
destinations (loopback, RFC1918/ULA, and CGNAT/Tailscale space) require the
caller to pass ``allow_private=True`` explicitly.  Link-local destinations,
including cloud metadata ranges, remain forbidden even with that opt-in.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import math
import queue
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote, urljoin, urlsplit


DEFAULT_TIMEOUT_S = 4.0
MAX_TIMEOUT_S = 120.0
DEFAULT_MAX_RESPONSE_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 8_388_608
MAX_REQUEST_BYTES = 8_388_608
DEFAULT_MAX_REDIRECTS = 2
MAX_REDIRECTS = 5
MAX_LOCATION_BYTES = 8_192

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_SENSITIVE_REDIRECT_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "cookie",
     "cf-access-client-id", "cf-access-client-secret"}
)
_RESERVED_REQUEST_HEADERS = frozenset(
    {"host", "content-length", "transfer-encoding", "connection"}
)


@dataclass(frozen=True)
class _Target:
    """A parsed target pinned to the addresses validated for this hop."""

    url: str
    scheme: str
    hostname: str
    port: int
    request_target: str
    host_header: str
    origin: tuple[str, str, int]
    addresses: tuple[str, ...]


class _SocketDeadline:
    """Interrupt socket I/O at the absolute deadline, including buffered framing.

    A per-recv timeout alone is an inactivity timeout: a peer can keep it alive
    by dripping header or chunk-framing bytes. Keep the actual socket reference
    because HTTPConnection may clear .sock after a Connection: close response.
    """

    def __init__(self, sock: socket.socket | None, deadline: float) -> None:
        self.sock = sock
        self.deadline = deadline
        self.expired = threading.Event()
        self._cancelled = threading.Event()
        self._timer = threading.Timer(_remaining(deadline), self._interrupt)
        self._timer.name = "provider-http-deadline"
        self._timer.daemon = True
        self._timer.start()

    def _interrupt(self) -> None:
        if self._cancelled.is_set():
            return
        self.expired.set()
        if self.sock is not None:
            try:
                # shutdown wakes a buffered read; closing its file object from
                # this thread could block on the reader's BufferedReader lock.
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def check(self) -> None:
        if self.expired.is_set() or _remaining(self.deadline) <= 0:
            self._interrupt()
            raise TimeoutError("provider deadline exceeded")

    def refresh_timeout(self) -> None:
        self.check()
        if self.sock is not None:
            self.sock.settimeout(_remaining(self.deadline))

    def cancel(self) -> None:
        self._cancelled.set()
        self._timer.cancel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that uses a validated IP while verifying the URL host."""

    def __init__(
        self,
        hostname: str,
        address: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
        deadline: float | None = None,
    ) -> None:
        super().__init__(hostname, port=port, timeout=timeout, context=context)
        self._validated_address = address
        self._absolute_deadline = deadline if deadline is not None else time.monotonic() + timeout

    def connect(self) -> None:
        remaining = _remaining(self._absolute_deadline)
        if remaining <= 0:
            raise TimeoutError("provider deadline exceeded")
        self.sock = socket.create_connection(
            (self._validated_address, self.port),
            remaining,
            self.source_address,
        )
        # Assign the SSL socket before its handshake so the timer can interrupt
        # it, and retain hostname verification against the original URL host.
        self.sock = self._context.wrap_socket(
            self.sock, server_hostname=self.host, do_handshake_on_connect=False,
        )
        handshake_deadline = _SocketDeadline(self.sock, self._absolute_deadline)
        try:
            handshake_deadline.refresh_timeout()
            self.sock.do_handshake()
            handshake_deadline.check()
        finally:
            handshake_deadline.cancel()


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _contains_control(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _resolve_bounded(hostname: str, port: int, deadline: float) -> tuple[Any, str | None]:
    """Run DNS in a daemon thread so a resolver stall cannot exceed the call budget."""

    remaining = _remaining(deadline)
    if remaining <= 0:
        return None, "TIMEOUT"

    result: queue.Queue[tuple[Any, str | None]] = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            infos = socket.getaddrinfo(
                hostname,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
            item: tuple[Any, str | None] = (infos, None)
        except Exception:  # DNS details can contain a secret-bearing URL on some stacks.
            item = (None, "DNS_RESOLUTION_FAILED")
        try:
            result.put_nowait(item)
        except queue.Full:
            pass

    threading.Thread(target=_worker, name="provider-dns", daemon=True).start()
    try:
        return result.get(timeout=remaining)
    except queue.Empty:
        return None, "TIMEOUT"


def _classify_address(value: str, *, allow_private: bool) -> str | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "DNS_INVALID_ADDRESS"

    # Apply the IPv4 policy to IPv4-mapped IPv6 values as well.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped

    # Link-local is always denied: it includes the common cloud metadata path.
    # ``ipaddress`` also classifies IPv6 loopback (``::1``) as reserved on some
    # Python versions.  Loopback is an explicitly supported self-hosted target,
    # so do not let that implementation detail override ``allow_private=True``.
    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_link_local
        or (address.is_reserved and not address.is_loopback)
    ):
        return "DESTINATION_FORBIDDEN"

    # is_global=False covers loopback, RFC1918/ULA, and CGNAT/Tailscale space.
    if not address.is_global and not allow_private:
        return "PRIVATE_DESTINATION_REQUIRES_OPT_IN"
    return None


def _validate_target(
    url: str,
    *,
    allow_private: bool,
    deadline: float,
) -> tuple[_Target | None, str | None]:
    if not isinstance(url, str) or not url or _contains_control(url):
        return None, "INVALID_URL"
    try:
        parts = urlsplit(url)
    except (TypeError, ValueError):
        return None, "INVALID_URL"

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return None, "INVALID_URL_SCHEME"
    if parts.username is not None or parts.password is not None:
        return None, "URL_CREDENTIALS_FORBIDDEN"
    if parts.fragment:
        return None, "URL_FRAGMENT_FORBIDDEN"
    if not parts.hostname or "\\" in parts.netloc:
        return None, "INVALID_URL"

    try:
        hostname = parts.hostname.encode("idna").decode("ascii").lower()
        port = parts.port or (443 if scheme == "https" else 80)
    except (UnicodeError, ValueError):
        return None, "INVALID_URL"

    infos, resolve_error = _resolve_bounded(hostname, port, deadline)
    if resolve_error:
        return None, resolve_error

    addresses: list[str] = []
    for family, _socktype, _proto, _canonname, sockaddr in infos or []:
        if family not in {socket.AF_INET, socket.AF_INET6} or not sockaddr:
            continue
        address = str(sockaddr[0])
        policy_error = _classify_address(address, allow_private=allow_private)
        if policy_error:
            # Reject a mixed public/private DNS answer; never select only its safe half.
            return None, policy_error
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        return None, "DNS_NO_ADDRESSES"

    path = quote(parts.path or "/", safe="/%:@-._~!$&'()*+,;=")
    query = quote(parts.query, safe="/%?:@-._~!$&'()*+,;=")
    request_target = path + (("?" + query) if query else "")
    default_port = 443 if scheme == "https" else 80
    display_host = "[" + hostname + "]" if ":" in hostname else hostname
    host_header = display_host if port == default_port else f"{display_host}:{port}"
    return (
        _Target(
            url=url,
            scheme=scheme,
            hostname=hostname,
            port=port,
            request_target=request_target,
            host_header=host_header,
            origin=(scheme, hostname, port),
            addresses=tuple(addresses),
        ),
        None,
    )


def _prepare_headers(headers: Mapping[str, str] | None) -> tuple[dict[str, str] | None, str | None]:
    prepared = {
        "Accept": "application/json",
        "User-Agent": "a11oy-provider-http/1.0",
    }
    if headers is None:
        return prepared, None
    if not isinstance(headers, Mapping):
        return None, "INVALID_HEADERS"
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            return None, "INVALID_HEADERS"
        normalized = name.strip().lower()
        if (
            not normalized
            or normalized in _RESERVED_REQUEST_HEADERS
            or ":" in name
            or _contains_control(name)
            or _contains_control(value)
        ):
            return None, "INVALID_HEADERS"
        prepared[name] = value
    return prepared, None


def _request_once(
    target: _Target,
    *,
    method: str,
    body: bytes | None,
    headers: Mapping[str, str],
    deadline: float,
) -> tuple[http.client.HTTPResponse | None, http.client.HTTPConnection | None, str | None]:
    last_error = "NETWORK_FAILURE"
    for address in target.addresses:
        remaining = _remaining(deadline)
        if remaining <= 0:
            return None, None, "TIMEOUT"
        connection: http.client.HTTPConnection | None = None
        response: http.client.HTTPResponse | None = None
        guard: _SocketDeadline | None = None
        try:
            if target.scheme == "https":
                connection = _PinnedHTTPSConnection(
                    target.hostname,
                    address,
                    target.port,
                    timeout=remaining,
                    context=ssl.create_default_context(),
                    deadline=deadline,
                )
            else:
                connection = http.client.HTTPConnection(
                    address,
                    port=target.port,
                    timeout=remaining,
                )
            # Connect explicitly so the watchdog owns the socket before request
            # writes or response-header parsing. A TCP connect retains its own
            # bounded timeout; HTTPS also bounds its separate handshake.
            connection.connect()
            guard = _SocketDeadline(connection.sock, deadline)
            connection._szl_deadline_guard = guard
            guard.refresh_timeout()
            hop_headers = dict(headers)
            hop_headers["Host"] = target.host_header
            connection.request(
                method,
                target.request_target,
                body=body,
                headers=hop_headers,
            )
            guard.refresh_timeout()
            response = connection.getresponse()
            guard.check()
            return response, connection, None
        except (TimeoutError, socket.timeout):
            last_error = "TIMEOUT"
        except ssl.SSLError:
            last_error = "TIMEOUT" if _remaining(deadline) <= 0 else "TLS_FAILURE"
        except Exception:
            last_error = (
                "TIMEOUT" if _remaining(deadline) <= 0 or (guard and guard.expired.is_set())
                else "NETWORK_FAILURE"
            )
        if guard is not None:
            guard.cancel()
        if response is not None:
            response.close()
        if connection is not None:
            connection.close()
        # A lost POST acknowledgement leaves the remote outcome unknown. Trying
        # another resolved address could duplicate the inference or other effect.
        if method == "POST":
            break
    return None, None, last_error


def _read_response_bounded(
    response: http.client.HTTPResponse,
    guard: _SocketDeadline,
    max_response_bytes: int,
) -> tuple[bytes | None, str | None]:
    raw = bytearray()
    while not response.isclosed():
        guard.refresh_timeout()
        # read1 performs at most one body recv. Chunk headers/trailers can still
        # require multiple internal reads; the absolute watchdog covers those.
        chunk = response.read1(min(65_536, max_response_bytes + 1 - len(raw)))
        guard.check()
        if not chunk:
            break
        raw.extend(chunk)
        if len(raw) > max_response_bytes:
            return None, "RESPONSE_TOO_LARGE"
    guard.check()
    return bytes(raw), None


def http_json(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    allow_private: bool = False,
    error_body_statuses: tuple[int, ...] = (),
    success_status: int | None = None,
) -> tuple[Any, str | None]:
    """Fetch one JSON document through the bounded provider transport.

    Returns ``(document, None)`` only after a real 2xx response containing valid
    UTF-8 JSON. By default, failures return ``(None, STABLE_ERROR_CODE)``.
    An explicit ``error_body_statuses`` allowlist preserves a bounded JSON error
    document alongside ``HTTP_STATUS:N``; it never turns that status into success.
    This lets governed callers validate ABSTAIN/REVIEW bodies. Setting
    ``success_status`` requires that exact 2xx status; other 2xx responses retain
    their HTTP error code instead of being promoted to success. The caller
    must set ``allow_private=True`` only for an operator-controlled self-hosted
    base URL (for example local Ollama at ``127.0.0.1:11434``).
    """

    method = method.upper() if isinstance(method, str) else ""
    if method not in {"GET", "POST"}:
        return None, "INVALID_METHOD"
    # Private routing is an explicit capability grant, not a truthy option.
    if not isinstance(allow_private, bool):
        return None, "INVALID_PRIVATE_OPT_IN"
    if body is not None and not isinstance(body, (bytes, bytearray)):
        return None, "INVALID_BODY"
    body_bytes = bytes(body) if body is not None else None
    if body_bytes is not None and len(body_bytes) > MAX_REQUEST_BYTES:
        return None, "REQUEST_TOO_LARGE"
    try:
        timeout_value = float(timeout)
    except (TypeError, ValueError):
        return None, "INVALID_TIMEOUT"
    if (
        isinstance(timeout, bool)
        or not math.isfinite(timeout_value)
        or timeout_value <= 0
        or timeout_value > MAX_TIMEOUT_S
    ):
        return None, "INVALID_TIMEOUT"
    if (
        isinstance(max_response_bytes, bool)
        or not isinstance(max_response_bytes, int)
        or max_response_bytes <= 0
        or max_response_bytes > MAX_RESPONSE_BYTES
    ):
        return None, "INVALID_RESPONSE_LIMIT"
    if (
        isinstance(max_redirects, bool)
        or not isinstance(max_redirects, int)
        or max_redirects < 0
        or max_redirects > MAX_REDIRECTS
    ):
        return None, "INVALID_REDIRECT_LIMIT"

    if (not isinstance(error_body_statuses, tuple) or len(error_body_statuses) > 8
            or any(type(status) is not int or not 400 <= status <= 599
                   for status in error_body_statuses)):
        return None, "INVALID_ERROR_BODY_STATUSES"

    if success_status is not None and (type(success_status) is not int
                                       or not 200 <= success_status < 300):
        return None, "INVALID_SUCCESS_STATUS"

    active_headers, header_error = _prepare_headers(headers)
    if header_error or active_headers is None:
        return None, header_error or "INVALID_HEADERS"
    if body_bytes is not None and not any(k.lower() == "content-type" for k in active_headers):
        active_headers["Content-Type"] = "application/json"

    deadline = time.monotonic() + timeout_value
    current_url = url
    current_method = method
    current_body = body_bytes
    redirects_followed = 0
    previous_origin: tuple[str, str, int] | None = None

    while True:
        target, validation_error = _validate_target(
            current_url,
            allow_private=allow_private,
            deadline=deadline,
        )
        if validation_error or target is None:
            return None, validation_error or "INVALID_URL"

        if previous_origin is not None and target.origin != previous_origin:
            active_headers = {
                key: value
                for key, value in active_headers.items()
                if key.lower() not in _SENSITIVE_REDIRECT_HEADERS
            }

        response, connection, request_error = _request_once(
            target,
            method=current_method,
            body=current_body,
            headers=active_headers,
            deadline=deadline,
        )
        if request_error or response is None or connection is None:
            return None, request_error or "NETWORK_FAILURE"
        guard = getattr(connection, "_szl_deadline_guard", None)
        try:
            # A malformed transport handoff must still release the connection.
            if guard is None:
                return None, "NETWORK_FAILURE"
            guard.check()
            status = int(response.status)
            if status in _REDIRECT_STATUSES:
                location = response.getheader("Location")
                if not location:
                    return None, "REDIRECT_MISSING_LOCATION"
                if len(location.encode("utf-8", "ignore")) > MAX_LOCATION_BYTES:
                    return None, "REDIRECT_LOCATION_TOO_LARGE"
                if redirects_followed >= max_redirects:
                    return None, "REDIRECT_LIMIT_EXCEEDED"
                next_url = urljoin(current_url, location)
                if status == 303:
                    current_method = "GET"
                    current_body = None
                    active_headers = {
                        key: value
                        for key, value in active_headers.items()
                        if key.lower() != "content-type"
                    }
                previous_origin = target.origin
                current_url = next_url
                redirects_followed += 1
                continue

            success = 200 <= status < 300 and (success_status is None or status == success_status)
            status_error = None if success else f"HTTP_STATUS:{status}"
            if status_error and status not in error_body_statuses:
                return None, status_error

            content_length = response.getheader("Content-Length")
            if content_length:
                try:
                    parsed_length = int(content_length)
                    if parsed_length < 0:
                        return None, "INVALID_CONTENT_LENGTH"
                    if parsed_length > max_response_bytes:
                        return None, "RESPONSE_TOO_LARGE"
                except ValueError:
                    return None, "INVALID_CONTENT_LENGTH"
            raw, read_error = _read_response_bounded(response, guard, max_response_bytes)
            if read_error or raw is None:
                return None, read_error or "NETWORK_FAILURE"
            try:
                document = json.loads(raw.decode("utf-8"))
                guard.check()
                return document, status_error
            except (UnicodeDecodeError, json.JSONDecodeError):
                guard.check()
                return None, "INVALID_JSON"
        except (TimeoutError, socket.timeout):
            return None, "TIMEOUT"
        except Exception:
            if (guard is not None and guard.expired.is_set()) or _remaining(deadline) <= 0:
                return None, "TIMEOUT"
            return None, "NETWORK_FAILURE"
        finally:
            try:
                if guard is not None:
                    guard.cancel()
                close_response = getattr(response, "close", None)
                if callable(close_response):
                    close_response()
            finally:
                connection.close()


__all__ = [
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_TIMEOUT_S",
    "MAX_REDIRECTS",
    "MAX_RESPONSE_BYTES",
    "MAX_TIMEOUT_S",
    "http_json",
]
