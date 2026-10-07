"""Cloudflare Access transport for the exact laptop joule-meter host.

This is an energy service helper. Missing credentials leave meter reads unauthenticated
and honestly unavailable behind Access. Credential values are never logged or returned.
"""

import os
import urllib.request
from urllib.parse import urlsplit


_HOST = "meter2.a-11-oy.com"
_ID_ENV = "A11OY_METER2_CF_ACCESS_CLIENT_ID"
_SECRET_ENV = "A11OY_METER2_CF_ACCESS_CLIENT_SECRET"


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
    """Open a GET, preserving ordinary transport when Access is not configured.

    An authenticated meter request cannot follow redirects, including same-host ones.
    The caller owns and closes the returned response.
    """
    auth = meter_access_headers(url)
    ordinary = {name: value for name, value in (headers or {}).items()
                if name.lower() not in ("cf-access-client-id", "cf-access-client-secret")}
    request = urllib.request.Request(url, headers={**ordinary, **auth}, method="GET")
    if auth:
        return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
