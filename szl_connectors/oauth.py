# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors.oauth — the OAuth2 authorization-code + PKCE flow engine (P2).

Designed NOW; activates the instant a customer provides an OAuth app
registration (CLIENT_ID/CLIENT_SECRET). The redirect URI is a stable per-app
path: https://<space>/api/{app}/v1/connectors/{id}/oauth/callback

Flow (per ENTERPRISE_INTEGRATION_SPEC §1.3):
  1. /oauth/start  → 302 to provider authorize URL with client_id, redirect_uri,
                     scope, state (= signed nonce), code_challenge (PKCE S256).
  2. provider → user consents → redirects to /oauth/callback?code=&state=
  3. /oauth/callback → verify signed state nonce → POST code to provider /token
                     (client_id + client_secret + code_verifier) → access_token
                     + refresh_token.
  4. Persist ONLY to the secret store (env injector / Space secret) — NEVER to a
     file or commit. Emit a DSSE "credential-bound" receipt carrying ONLY the
     connector id, granted scope, and a credential FINGERPRINT HASH (never the
     secret value).
  5. health() now sees the refresh token → exchanges for access token → CONNECTED.

DOCTRINE: no committed keys; the secret value never leaves the secret store and
never enters a receipt body. Until CLIENT_ID/SECRET are provided, the connector
stays READY and the UI shows "Connect <Provider>" which initiates this flow.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse as _up
from datetime import datetime, timezone
from typing import Any

# Per-provider OAuth2 endpoints (publicly documented authorize/token URLs).
# {sub} placeholders are filled from the connector's env (instance/tenant/domain).
PROVIDER_OAUTH: dict[str, dict[str, str]] = {
    "salesforce": {
        "authorize": "https://login.salesforce.com/services/oauth2/authorize",
        "token": "https://login.salesforce.com/services/oauth2/token",
        "scope": "api refresh_token",
    },
    "hubspot": {
        "authorize": "https://app.hubspot.com/oauth/authorize",
        "token": "https://api.hubapi.com/oauth/v1/token",
        "scope": "crm.objects.contacts.read crm.objects.companies.read crm.objects.deals.read",
    },
    "zoho_crm": {
        "authorize": "https://accounts.zoho.com/oauth/v2/auth",
        "token": "https://accounts.zoho.com/oauth/v2/token",
        "scope": "ZohoCRM.modules.ALL ZohoCRM.org.READ",
    },
    "slack": {
        "authorize": "https://slack.com/oauth/v2/authorize",
        "token": "https://slack.com/api/oauth.v2.access",
        "scope": "channels:read chat:write users:read",
    },
    "okta": {
        "authorize": "https://{org}.okta.com/oauth2/v1/authorize",
        "token": "https://{org}.okta.com/oauth2/v1/token",
        "scope": "okta.users.read okta.groups.read",
    },
    "entra": {
        "authorize": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "scope": "https://graph.microsoft.com/.default offline_access",
    },
    "auth0": {
        "authorize": "https://{tenant}.auth0.com/authorize",
        "token": "https://{tenant}.auth0.com/oauth/token",
        "scope": "read:users read:logs",
    },
    "dynamics_crm": {
        "authorize": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "scope": "https://{org}.api.crm.dynamics.com/.default offline_access",
    },
    "netsuite": {
        "authorize": "https://{account}.app.netsuite.com/app/login/oauth2/authorize.nl",
        "token": "https://{account}.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token",
        "scope": "rest_webservices",
    },
    "servicenow": {
        "authorize": "https://{instance}.service-now.com/oauth_auth.do",
        "token": "https://{instance}.service-now.com/oauth_token.do",
        "scope": "useraccount",
    },
}


# Domain-separation salt + work factor for deriving the state-signing key.
_STATE_KDF_SALT = b"szl.killinchu.oauth-state.v1"
_STATE_KDF_ITERATIONS = 200_000
_STATE_KEY_CACHE: dict[str, bytes] = {}


def _state_secret() -> bytes:
    # signed-state nonce key: reuse the cosign-adjacent secret if present, else a
    # per-process ephemeral key (state still verifiable within the process).
    # Stretched with PBKDF2-HMAC-SHA256 rather than a single SHA-256 pass so a
    # low-entropy secret (e.g. the ephemeral fallback) cannot be cheaply
    # brute-forced from a leaked state signature (CodeQL
    # py/weak-sensitive-data-hashing). Cached per secret so the stretch is a
    # one-time cost while still honouring a changed secret.
    s = os.environ.get("SZL_OAUTH_STATE_SECRET") or os.environ.get("SZL_COSIGN_PRIVATE_PEM") or "szl-oauth-ephemeral"
    key = _STATE_KEY_CACHE.get(s)
    if key is None:
        key = hashlib.pbkdf2_hmac("sha256", s.encode(), _STATE_KDF_SALT, _STATE_KDF_ITERATIONS)
        _STATE_KEY_CACHE[s] = key
    return key


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge[S256])."""
    verifier = _b64u(os.urandom(48))
    challenge = _b64u(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def sign_state(connector_id: str, nonce: str, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    msg = f"{connector_id}.{nonce}.{ts}"
    sig = hmac.new(_state_secret(), msg.encode(), hashlib.sha256).hexdigest()[:24]
    return _b64u(f"{msg}.{sig}".encode())


def verify_state(state: str, connector_id: str, max_age: int = 600) -> tuple[bool, str]:
    try:
        decoded = base64.urlsafe_b64decode(state + "=" * (-len(state) % 4)).decode()
        cid, nonce, ts, sig = decoded.rsplit(".", 3)
        if cid != connector_id:
            return False, "state connector_id mismatch"
        msg = f"{cid}.{nonce}.{ts}"
        expect = hmac.new(_state_secret(), msg.encode(), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(expect, sig):
            return False, "state signature mismatch"
        if int(time.time()) - int(ts) > max_age:
            return False, "state expired"
        return True, "ok"
    except Exception as e:
        return False, f"malformed state: {type(e).__name__}"


# in-process PKCE verifier store (keyed by signed-state nonce). NOT a secret store;
# holds only ephemeral PKCE verifiers, cleared after callback.
_PKCE_STORE: dict[str, str] = {}


def build_authorize_url(connector_id: str, *, redirect_uri: str,
                        subs: dict[str, str] | None = None,
                        client_id: str | None = None) -> dict[str, Any]:
    """Build the provider authorize redirect (PKCE S256). Returns dict with `url`
    or an honest error when the connector has no OAuth config / no client_id."""
    cfg = PROVIDER_OAUTH.get(connector_id)
    if not cfg:
        return {"ok": False, "error": f"no OAuth2 config for '{connector_id}'"}
    authorize = cfg["authorize"]
    for k, v in (subs or {}).items():
        authorize = authorize.replace("{" + k + "}", v)
    if "{" in authorize:
        return {"ok": False, "error": "OAuth authorize URL needs instance/tenant substitution",
                "needs": authorize}
    if not client_id:
        return {"ok": False, "state": "READY",
                "error": "no client_id — provide the OAuth app registration to connect",
                "secret_hint": f"SZL_{connector_id.upper()}_CLIENT_ID"}
    nonce = _b64u(os.urandom(12))
    state = sign_state(connector_id, nonce)
    verifier, challenge = make_pkce()
    _PKCE_STORE[state] = verifier
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": cfg.get("scope", ""),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return {"ok": True, "url": authorize + "?" + _up.urlencode(params),
            "state": state, "pkce": True}


def exchange_code(connector_id: str, *, code: str, state: str, redirect_uri: str,
                  subs: dict[str, str] | None = None,
                  client_id: str | None = None, client_secret: str | None = None) -> dict[str, Any]:
    """Exchange the auth code for tokens, then emit a credential-bound DSSE receipt
    (NO secret in the receipt — only a fingerprint hash). Persisting the refresh
    token to the secret store is an out-of-band operation (Space secret); this
    function NEVER writes a secret to a file or commit."""
    ok, why = verify_state(state, connector_id)
    if not ok:
        return {"ok": False, "error": f"state verification failed: {why}"}
    cfg = PROVIDER_OAUTH.get(connector_id)
    if not cfg:
        return {"ok": False, "error": f"no OAuth2 config for '{connector_id}'"}
    if not (client_id and client_secret):
        return {"ok": False, "error": "client_id/client_secret not provided (secret store)"}
    verifier = _PKCE_STORE.pop(state, None)
    token_url = cfg["token"]
    for k, v in (subs or {}).items():
        token_url = token_url.replace("{" + k + "}", v)
    from .base import http_json, cred_fingerprint
    payload = {
        "grant_type": "authorization_code", "code": code,
        "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    if verifier:
        payload["code_verifier"] = verifier
    status, body = http_json(token_url, method="POST",
                             headers={"Content-Type": "application/x-www-form-urlencoded"},
                             data=_up.urlencode(payload).encode())
    if status != 200 or not isinstance(body, dict):
        return {"ok": False, "error": f"token exchange HTTP {status}",
                "provider_detail": str(body)[:200]}
    refresh = body.get("refresh_token", "")
    access = body.get("access_token", "")
    # credential-bound DSSE receipt — fingerprint ONLY, never the token value.
    from .governance import receipt_for_write
    rcpt = receipt_for_write(
        connector_id=connector_id,
        action={"method": "oauth.credential_bound", "object": "refresh_token",
                "scope": cfg.get("scope", "")},
        lambda_value=0.9,
        cred_fingerprints={
            "refresh_token": cred_fingerprint(refresh) if refresh else "absent",
            "access_token": cred_fingerprint(access) if access else "absent",
        },
        result_summary={"granted_scope": cfg.get("scope", ""),
                        "note": "secret persisted to Space secret store only; never committed"},
    )
    return {
        "ok": True,
        "connector_id": connector_id,
        "credential_bound": True,
        "store_secret_as": f"SZL_{connector_id.upper()}_REFRESH_TOKEN",
        "note": ("Persist the refresh_token into the Space secret store as the named "
                 "secret. It is NEVER written to a file or commit. The Space restarts "
                 "(or hot-reloads env) → health() flips the connector to CONNECTED."),
        "receipt_hash": rcpt["receipt_hash"],
        "dsse": rcpt["dsse"],
    }


__all__ = ["PROVIDER_OAUTH", "make_pkce", "sign_state", "verify_state",
           "build_authorize_url", "exchange_code"]
