#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services-layer model Access configuration; no transport, signing or storage.

The Access pair authenticates one declared HTTPS origin. The model bearer remains
a separate credential. Configuration is not provider authentication or inference
qualification, and this module never reads credentials from another subsystem.
"""

import ipaddress
import os
import re
import socket
from urllib.parse import urlsplit, urlunsplit


ACCESS_ORIGIN_ENV = "A11OY_MODEL_CF_ACCESS_ORIGIN"
ACCESS_ID_ENV = "A11OY_MODEL_CF_ACCESS_CLIENT_ID"
ACCESS_SECRET_ENV = "A11OY_MODEL_CF_ACCESS_CLIENT_SECRET"
_ACCESS_ENVS = (ACCESS_ORIGIN_ENV, ACCESS_ID_ENV, ACCESS_SECRET_ENV)
_HEADER_VALUE = re.compile(r"[A-Za-z0-9._~+/\-]+=*\Z")
_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")


class ModelAccessConfigurationError(ValueError):
    """Fixed diagnostic codes only; never include a URL or credential value."""


def model_access_configured(*, env=None) -> bool:
    """Presence includes blank/partial configuration so it cannot become anonymous."""
    env = os.environ if env is None else env
    return any(env.get(name) is not None for name in _ACCESS_ENVS)


def _https_origin(url: str, *, origin_only: bool = False):
    try:
        if (not isinstance(url, str) or not url or len(url) > 4096 or not url.isascii()
                or any(ord(char) <= 32 or ord(char) == 127 for char in url)
                or any(char in url for char in ("\\", "?", "#"))):
            raise ValueError
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        # inet_aton parses legacy numeric/hex IPv4 spellings without DNS. Those
        # spellings can resolve to loopback even though ipaddress rejects them.
        try:
            socket.inet_aton(host)
        except OSError:
            pass
        else:
            raise ValueError
        labels = host.split(".")
        if (parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or len(host) > 253
                or len(labels) < 2 or not all(_DNS_LABEL.fullmatch(x) for x in labels)
                or parsed.netloc.lower() not in {host, host + ":443"}
                or host == "router.huggingface.co"
                or (origin_only and parsed.path not in ("", "/"))):
            raise ValueError
        return parsed, ("https", host, 443)
    except (TypeError, ValueError):
        raise ModelAccessConfigurationError("MODEL_ACCESS_ORIGIN_INVALID") from None


def _credential(value, code):
    if (not isinstance(value, str) or not 1 <= len(value) <= 4096
            or _HEADER_VALUE.fullmatch(value) is None):
        raise ModelAccessConfigurationError(code)
    return value


def model_access_headers(url: str, *, env=None) -> dict[str, str]:
    """Return the complete Access pair for the exact configured origin, or refuse.

    All settings absent preserves legacy behavior. Any setting present requires
    the complete pair and origin; a mismatch never silently drops authentication.
    Callers must reject redirects and must not return these headers to clients.
    """
    env = os.environ if env is None else env
    values = {name: env.get(name) for name in _ACCESS_ENVS}
    if all(value is None for value in values.values()):
        return {}
    if any(value is None or value == "" for value in values.values()):
        raise ModelAccessConfigurationError("MODEL_ACCESS_CONFIGURATION_INCOMPLETE")
    _, expected = _https_origin(values[ACCESS_ORIGIN_ENV], origin_only=True)
    _, observed = _https_origin(url)
    if observed != expected:
        raise ModelAccessConfigurationError("MODEL_ACCESS_ORIGIN_MISMATCH")
    client_id = _credential(values[ACCESS_ID_ENV], "MODEL_ACCESS_CREDENTIAL_INVALID")
    client_secret = _credential(values[ACCESS_SECRET_ENV], "MODEL_ACCESS_CREDENTIAL_INVALID")
    return {"CF-Access-Client-Id": client_id,
            "CF-Access-Client-Secret": client_secret}


def model_access_headers_for_origin(url: str, *, env=None) -> dict[str, str]:
    """Access pair for this URL only when its exact origin IS the configured one.

    Single-origin callers fail on any mismatch (they never silently drop
    authentication; that is model_access_headers). Multi-node callers probe
    both this declared public origin and private tailnet nodes through one code
    path, and a tailnet node is not behind the declared origin's Access gate:
    it must neither receive these credentials nor be blocked on their absence,
    so it gets an empty dict instead of an error.

    The fail-closed contract is unchanged in the states that matter: an
    all-absent configuration preserves legacy behavior ({}) and a PARTIAL
    configuration always raises MODEL_ACCESS_CONFIGURATION_INCOMPLETE whatever
    the URL, because a half-configured trio makes the origin's protection
    unknowable. A matching-origin decision still requires the complete valid
    pair (model_access_headers enforces credentials and exact-origin equality).
    """
    env = os.environ if env is None else env
    values = {name: env.get(name) for name in _ACCESS_ENVS}
    if all(value is None for value in values.values()):
        return {}
    if any(value is None or value == "" for value in values.values()):
        raise ModelAccessConfigurationError("MODEL_ACCESS_CONFIGURATION_INCOMPLETE")
    _, expected = _https_origin(values[ACCESS_ORIGIN_ENV], origin_only=True)
    try:
        _, observed = _https_origin(url)
    except ModelAccessConfigurationError:
        # A URL that is not a valid https origin cannot be the declared
        # Access origin; it is another (private) node, not a config error.
        # An INVALID origin env or partial trio has already raised above.
        return {}
    if observed != expected:
        return {}
    return model_access_headers(url, env=env)


def model_access_catalog_request(base: str) -> tuple[str, dict[str, str]]:
    """Build one explicit catalog GET using the protected code endpoint's bearer.

    This helper is only for the opt-in model Access contract. Legacy sovereign
    key names and model-generation protocols remain separate.
    """
    parsed, _ = _https_origin(base)
    if parsed.path not in ("", "/", "/v1", "/v1/"):
        raise ModelAccessConfigurationError("MODEL_ACCESS_CATALOG_BASE_INVALID")
    url = urlunsplit(("https", parsed.hostname, "/v1/models", "", ""))
    headers = model_access_headers(url)
    if not headers:
        raise ModelAccessConfigurationError("MODEL_ACCESS_CONFIGURATION_REQUIRED")
    bearer = os.environ.get("A11OY_MODEL_API_KEY")
    if bearer is not None:
        headers["Authorization"] = "Bearer " + _credential(
            bearer, "MODEL_CREDENTIAL_INVALID")
    return url, headers
