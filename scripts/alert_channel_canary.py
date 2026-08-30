#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Protocol-aware, secret-safe shared alert-channel canary.

The endpoint value is consumed only from the process environment. Receipts record
scheme, hostname, port, protocol mode, status, and error class; they never record
the URL path, query, webhook token, response body, or secret value.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

VALID_MODES = {"auto", "slack", "ntfy", "generic-json"}
NTFY_RELAY_HOSTS = {"ntfy.sh"}
NON_RECEIVING_ALERT_HOSTS = {
    "a11oy.net": "a11oy.net is a static proof registry and cannot receive alert-channel POST requests",
    "ntfy.a11oy.net": "ntfy.a11oy.net is not a POST-capable alert receiver",
}
FAILURE_STATES = {
    "MISSING",
    "INVALID_CONFIGURATION",
    "FAILING",
    "TIMED_OUT",
    "UNAVAILABLE",
    "INVALID_RESPONSE",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class EndpointContractError(ValueError):
    """The endpoint cannot safely be used by the production canary."""


@dataclass(frozen=True)
class EndpointIdentity:
    scheme: str
    hostname: str
    port: int | None
    mode: str


@dataclass(frozen=True)
class CanaryResult:
    schema: str
    generated_at: str
    state: str
    endpoint: EndpointIdentity | None
    http_status: int | None
    response_bytes: int
    error_class: str | None
    error_detail: str | None
    secret_present: bool
    secret_value_recorded: bool
    canary_attempted: bool
    attempt_count: int

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["endpoint"] = asdict(self.endpoint) if self.endpoint else None
        return value


def infer_mode(url: str) -> str:
    hostname = (urllib.parse.urlsplit(url).hostname or "").lower()
    if hostname == "hooks.slack.com" or hostname.endswith(".hooks.slack.com"):
        return "slack"
    if hostname in NTFY_RELAY_HOSTS:
        return "ntfy"
    return "generic-json"


def validate_endpoint(
    url: str,
    *,
    requested_mode: str = "auto",
    allow_insecure_loopback: bool = False,
) -> tuple[str, EndpointIdentity]:
    if not isinstance(url, str) or not url.strip():
        raise EndpointContractError("alert endpoint must be a non-empty string")
    normalized = url.strip()
    if len(normalized) > 4096:
        raise EndpointContractError("alert endpoint exceeds the length bound")
    parsed = urllib.parse.urlsplit(normalized)
    if parsed.scheme not in {"https", "http"}:
        raise EndpointContractError("alert endpoint must use HTTP(S)")
    if not parsed.hostname:
        raise EndpointContractError("alert endpoint has no hostname")
    hostname = parsed.hostname.lower()
    if hostname in NON_RECEIVING_ALERT_HOSTS:
        raise EndpointContractError(NON_RECEIVING_ALERT_HOSTS[hostname])
    if parsed.username or parsed.password:
        raise EndpointContractError("embedded URL credentials are forbidden")
    if parsed.fragment:
        raise EndpointContractError("URL fragments are forbidden")
    if parsed.scheme != "https":
        loopback = False
        if allow_insecure_loopback:
            if parsed.hostname == "localhost":
                loopback = True
            else:
                try:
                    loopback = ipaddress.ip_address(parsed.hostname).is_loopback
                except ValueError:
                    loopback = False
        if not loopback:
            raise EndpointContractError("production alert endpoint must use HTTPS")

    selected = (requested_mode or "auto").strip().lower()
    if selected not in VALID_MODES:
        raise EndpointContractError(f"unsupported alert mode: {selected}")
    if selected == "auto":
        selected = infer_mode(normalized)

    return normalized, EndpointIdentity(
        scheme=parsed.scheme,
        hostname=parsed.hostname.lower(),
        port=parsed.port,
        mode=selected,
    )


def build_request(
    *, url: str, mode: str, title: str, message: str
) -> urllib.request.Request:
    if mode == "slack":
        body = json.dumps(
            {"text": f"*{title}*\n{message}"}, separators=(",", ":")
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/plain, */*",
        }
    elif mode == "ntfy":
        body = message.encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "Title": title,
            "Tags": "satellite,shield",
            "Priority": "3",
        }
    else:
        body = json.dumps(
            {
                "schema": "szl.alert-channel-canary/v2",
                "title": title,
                "message": message,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/plain, */*",
        }
    headers["User-Agent"] = "szl-alert-channel-canary/2"
    return urllib.request.Request(url, data=body, headers=headers, method="POST")


def evaluate(
    *,
    url: str | None,
    should_send: bool,
    requested_mode: str = "auto",
    timeout_seconds: float = 8.0,
    max_response_bytes: int = 64 * 1024,
    allow_insecure_loopback: bool = False,
    opener: urllib.request.OpenerDirector | None = None,
) -> CanaryResult:
    if not url:
        return CanaryResult(
            schema="szl.alert-channel-canary/v2",
            generated_at=_now(),
            state="MISSING",
            endpoint=None,
            http_status=None,
            response_bytes=0,
            error_class="MissingSecret",
            error_detail="Required endpoint secret is absent.",
            secret_present=False,
            secret_value_recorded=False,
            canary_attempted=False,
            attempt_count=0,
        )

    try:
        normalized, identity = validate_endpoint(
            url,
            requested_mode=requested_mode,
            allow_insecure_loopback=allow_insecure_loopback,
        )
    except EndpointContractError as exc:
        return CanaryResult(
            schema="szl.alert-channel-canary/v2",
            generated_at=_now(),
            state="INVALID_CONFIGURATION",
            endpoint=None,
            http_status=None,
            response_bytes=0,
            error_class=type(exc).__name__,
            error_detail=str(exc),
            secret_present=True,
            secret_value_recorded=False,
            canary_attempted=False,
            attempt_count=0,
        )

    if not should_send:
        return CanaryResult(
            schema="szl.alert-channel-canary/v2",
            generated_at=_now(),
            state="PRESENT_UNPROBED",
            endpoint=identity,
            http_status=None,
            response_bytes=0,
            error_class=None,
            error_detail=(
                "Secret presence was observed, but no delivery attempt was scheduled. "
                "This state cannot close a prior delivery incident."
            ),
            secret_present=True,
            secret_value_recorded=False,
            canary_attempted=False,
            attempt_count=0,
        )

    request = build_request(
        url=normalized,
        mode=identity.mode,
        title="SZL alert-channel canary",
        message=(
            "[canary-ignore] One-attempt delivery check for the shared "
            "receipt-failure channel. No production payload or secret is included."
        ),
    )
    client = opener or urllib.request.build_opener()
    try:
        with client.open(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", response.getcode()))
            data = response.read(max_response_bytes + 1)
            if len(data) > max_response_bytes:
                state = "INVALID_RESPONSE"
                error_class = "ResponseTooLarge"
                detail = "Response exceeded the configured byte bound."
            elif 200 <= status < 300:
                state = "HEALTHY"
                error_class = None
                detail = None
            else:
                state = "FAILING"
                error_class = "Non2xxResponse"
                detail = f"HTTP {status}"
            return CanaryResult(
                schema="szl.alert-channel-canary/v2",
                generated_at=_now(),
                state=state,
                endpoint=identity,
                http_status=status,
                response_bytes=len(data),
                error_class=error_class,
                error_detail=detail,
                secret_present=True,
                secret_value_recorded=False,
                canary_attempted=True,
                attempt_count=1,
            )
    except urllib.error.HTTPError as exc:
        try:
            data = exc.read(max_response_bytes + 1)
        except Exception:
            data = b""
        return CanaryResult(
            schema="szl.alert-channel-canary/v2",
            generated_at=_now(),
            state="FAILING",
            endpoint=identity,
            http_status=int(exc.code),
            response_bytes=min(len(data), max_response_bytes + 1),
            error_class="HTTPError",
            error_detail=f"HTTP {int(exc.code)}",
            secret_present=True,
            secret_value_recorded=False,
            canary_attempted=True,
            attempt_count=1,
        )
    except (TimeoutError, socket.timeout) as exc:
        return CanaryResult(
            schema="szl.alert-channel-canary/v2",
            generated_at=_now(),
            state="TIMED_OUT",
            endpoint=identity,
            http_status=None,
            response_bytes=0,
            error_class=type(exc).__name__,
            error_detail="Canary request exceeded the timeout.",
            secret_present=True,
            secret_value_recorded=False,
            canary_attempted=True,
            attempt_count=1,
        )
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        return CanaryResult(
            schema="szl.alert-channel-canary/v2",
            generated_at=_now(),
            state="UNAVAILABLE",
            endpoint=identity,
            http_status=None,
            response_bytes=0,
            error_class=type(exc).__name__,
            error_detail="Endpoint could not be reached or negotiated.",
            secret_present=True,
            secret_value_recorded=False,
            canary_attempted=True,
            attempt_count=1,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", default=os.environ.get("ALERT_CHANNEL_MODE", "auto"))
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    result = evaluate(
        url=os.environ.get("SLACK_WEBHOOK_URL"),
        should_send=args.send,
        requested_mode=args.mode,
        timeout_seconds=args.timeout,
    )
    payload = result.to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["state"] in FAILURE_STATES else 0


if __name__ == "__main__":
    raise SystemExit(main())
