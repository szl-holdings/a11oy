# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""Identity / IdP connectors — Okta, Microsoft Entra ID (Graph), Auth0.

REAL clients against documented endpoints. NO creds → READY + exact secret name;
NEVER fabricates a record. Creds present → CONNECTED → live directory data.

API refs (publicly documented shapes):
  Okta Users API     https://developer.okta.com/docs/reference/api/users/
  Microsoft Graph    https://learn.microsoft.com/graph/api/user-list
  Auth0 Mgmt API     https://auth0.com/docs/api/management/v2
"""
from __future__ import annotations

import os

from ..ready import ReadyConnector
from ..registry import register


# ── Okta (api_key SSWS token OR oauth2; free developer org) ───────────────────
@register
class OktaConnector(ReadyConnector):
    id = "okta"
    label = "Okta (Universal Directory)"
    category = "identity"
    auth_kind = "api_key"
    free_tier = True  # free developer org
    env_vars = ["SZL_OKTA_ORG_URL", "SZL_OKTA_API_TOKEN"]
    _primary_secret = "SZL_OKTA_API_TOKEN"
    provider_base = "{org_url}/api/v1"
    docs_url = "https://developer.okta.com/docs/reference/api/users/"
    schema_preview = ["id", "status", "profile.login", "profile.email"]
    _read_path = "users?limit=10"
    _record_path = ""

    def _base_url(self):
        return self.provider_base.replace("{org_url}",
                                          os.environ.get("SZL_OKTA_ORG_URL", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_OKTA_API_TOKEN")
        return {"Authorization": f"SSWS {tok}"} if tok else {}

    def _dig(self, raw):
        rows = raw if isinstance(raw, list) else []
        out = []
        for r in rows:
            if isinstance(r, dict):
                p = r.get("profile", {}) or {}
                out.append({"id": r.get("id"), "status": r.get("status"),
                            "login": p.get("login"), "email": p.get("email")})
        return out


# ── Microsoft Entra ID (Graph; oauth2 client-credentials) ─────────────────────
@register
class EntraConnector(ReadyConnector):
    id = "entra"
    label = "Microsoft Entra ID (Graph)"
    category = "identity"
    auth_kind = "oauth2"
    free_tier = True  # free Azure AD tier / dev tenant
    env_vars = ["SZL_ENTRA_ACCESS_TOKEN", "SZL_ENTRA_TENANT_ID",
                "SZL_ENTRA_CLIENT_ID", "SZL_ENTRA_CLIENT_SECRET"]
    _primary_secret = "SZL_ENTRA_ACCESS_TOKEN"
    provider_base = "https://graph.microsoft.com/v1.0"
    docs_url = "https://learn.microsoft.com/graph/api/user-list"
    schema_preview = ["id", "displayName", "userPrincipalName", "mail"]
    _read_path = "users?$top=10&$select=id,displayName,userPrincipalName,mail"
    _record_path = "value"

    def _auth_header(self):
        tok = os.environ.get("SZL_ENTRA_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


# ── Auth0 (oauth2 mgmt token; free tier) ──────────────────────────────────────
@register
class Auth0Connector(ReadyConnector):
    id = "auth0"
    label = "Auth0 (Management API)"
    category = "identity"
    auth_kind = "oauth2"
    free_tier = True
    env_vars = ["SZL_AUTH0_DOMAIN", "SZL_AUTH0_MGMT_TOKEN"]
    _primary_secret = "SZL_AUTH0_MGMT_TOKEN"
    provider_base = "https://{domain}/api/v2"
    docs_url = "https://auth0.com/docs/api/management/v2"
    schema_preview = ["user_id", "name", "email", "last_login"]
    _read_path = "users?per_page=10"
    _record_path = ""

    def _base_url(self):
        return self.provider_base.replace("{domain}",
                                          os.environ.get("SZL_AUTH0_DOMAIN", "").replace("https://", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_AUTH0_MGMT_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _dig(self, raw):
        rows = raw if isinstance(raw, list) else (raw.get("users", []) if isinstance(raw, dict) else [])
        return [{k: r.get(k) for k in self.schema_preview if k in r}
                for r in rows if isinstance(r, dict)]


__all__ = ["OktaConnector", "EntraConnector", "Auth0Connector"]
