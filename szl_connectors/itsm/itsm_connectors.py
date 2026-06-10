# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""ITSM / ticketing connectors — Jira, ServiceNow, Zendesk, Linear.

REAL clients against documented endpoints. NO creds → READY + exact secret name.
Jira is WRITABLE (create issue) — every write is Λ-gated + DSSE-receipted.

API refs (publicly documented shapes):
  Jira Cloud REST v3  https://developer.atlassian.com/cloud/jira/platform/rest/v3/
  ServiceNow Table    https://developer.servicenow.com/dev.do#!/reference/api/
  Zendesk Tickets     https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
  Linear GraphQL      https://developers.linear.app/docs/graphql/working-with-the-graphql-api
"""
from __future__ import annotations

import base64
import os

from ..base import State, Records, http_json
from ..ready import ReadyConnector, WritableReadyConnector
from ..registry import register


# ── Jira Cloud (api_key basic email:token; free tier) — WRITABLE ──────────────
@register
class JiraConnector(WritableReadyConnector):
    id = "jira"
    label = "Atlassian Jira (Cloud)"
    category = "itsm"
    auth_kind = "api_key"
    free_tier = True
    env_vars = ["SZL_JIRA_SITE_URL", "SZL_JIRA_EMAIL", "SZL_JIRA_API_TOKEN"]
    _primary_secret = "SZL_JIRA_API_TOKEN"
    provider_base = "{site_url}/rest/api/3"
    docs_url = "https://developer.atlassian.com/cloud/jira/platform/rest/v3/"
    schema_preview = ["key", "fields.summary", "fields.status", "fields.assignee"]
    _read_path = "search?maxResults=10&fields=summary,status,assignee"
    _record_path = "issues"
    _write_path = "issue"

    def _base_url(self):
        return self.provider_base.replace("{site_url}",
                                          os.environ.get("SZL_JIRA_SITE_URL", "").rstrip("/"))

    def _auth_header(self):
        email = os.environ.get("SZL_JIRA_EMAIL", "")
        tok = os.environ.get("SZL_JIRA_API_TOKEN", "")
        if not tok:
            return {}
        b = base64.b64encode(f"{email}:{tok}".encode()).decode()
        return {"Authorization": f"Basic {b}"}

    def _dig(self, raw):
        rows = (raw or {}).get("issues", []) if isinstance(raw, dict) else []
        out = []
        for r in rows:
            f = r.get("fields", {}) if isinstance(r, dict) else {}
            out.append({"key": r.get("key"), "summary": f.get("summary"),
                        "status": (f.get("status") or {}).get("name"),
                        "assignee": (f.get("assignee") or {}).get("displayName")})
        return out


# ── ServiceNow (Table API; basic auth; no free tier — PDI dev instance) ───────
@register
class ServiceNowConnector(ReadyConnector):
    id = "servicenow"
    label = "ServiceNow (Table API)"
    category = "itsm"
    auth_kind = "basic"
    free_tier = True  # free Personal Developer Instance
    env_vars = ["SZL_SERVICENOW_INSTANCE", "SZL_SERVICENOW_USER", "SZL_SERVICENOW_PASSWORD"]
    _primary_secret = "SZL_SERVICENOW_PASSWORD"
    provider_base = "https://{instance}.service-now.com/api/now"
    docs_url = "https://developer.servicenow.com/dev.do#!/reference/api/"
    schema_preview = ["number", "short_description", "state", "priority"]
    _read_path = "table/incident?sysparm_limit=10&sysparm_fields=number,short_description,state,priority"
    _record_path = "result"

    def _base_url(self):
        return self.provider_base.replace("{instance}",
                                          os.environ.get("SZL_SERVICENOW_INSTANCE", ""))

    def _auth_header(self):
        u = os.environ.get("SZL_SERVICENOW_USER", "")
        p = os.environ.get("SZL_SERVICENOW_PASSWORD", "")
        if not p:
            return {}
        b = base64.b64encode(f"{u}:{p}".encode()).decode()
        return {"Authorization": f"Basic {b}"}


# ── Zendesk (api_key email/token basic; free trial) ───────────────────────────
@register
class ZendeskConnector(ReadyConnector):
    id = "zendesk"
    label = "Zendesk Support"
    category = "itsm"
    auth_kind = "api_key"
    free_tier = False
    env_vars = ["SZL_ZENDESK_SUBDOMAIN", "SZL_ZENDESK_EMAIL", "SZL_ZENDESK_API_TOKEN"]
    _primary_secret = "SZL_ZENDESK_API_TOKEN"
    provider_base = "https://{subdomain}.zendesk.com/api/v2"
    docs_url = "https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/"
    schema_preview = ["id", "subject", "status", "priority"]
    _read_path = "tickets.json?per_page=10"
    _record_path = "tickets"

    def _base_url(self):
        return self.provider_base.replace("{subdomain}",
                                          os.environ.get("SZL_ZENDESK_SUBDOMAIN", ""))

    def _auth_header(self):
        email = os.environ.get("SZL_ZENDESK_EMAIL", "")
        tok = os.environ.get("SZL_ZENDESK_API_TOKEN", "")
        if not tok:
            return {}
        b = base64.b64encode(f"{email}/token:{tok}".encode()).decode()
        return {"Authorization": f"Basic {b}"}


# ── Linear (api_key personal token; GraphQL; free tier) ───────────────────────
@register
class LinearConnector(ReadyConnector):
    id = "linear"
    label = "Linear"
    category = "itsm"
    auth_kind = "api_key"
    free_tier = True
    env_vars = ["SZL_LINEAR_API_KEY"]
    _primary_secret = "SZL_LINEAR_API_KEY"
    provider_base = "https://api.linear.app/graphql"
    docs_url = "https://developers.linear.app/docs/graphql/working-with-the-graphql-api"
    schema_preview = ["id", "identifier", "title", "state"]

    def _auth_header(self):
        tok = os.environ.get("SZL_LINEAR_API_KEY")
        return {"Authorization": tok} if tok else {}

    def read(self, query=None):
        if self._primary_missing():
            return self._ready_records(
                "provide credentials to activate — set SZL_LINEAR_API_KEY. "
                "POSTs GraphQL { issues } to api.linear.app/graphql.")
        import json as _json
        gql = {"query": "{ issues(first: 10) { nodes { id identifier title state { name } } } }"}
        st, raw = http_json(self.provider_base, method="POST",
                            headers={"Content-Type": "application/json", **self._auth_header()},
                            data=_json.dumps(gql).encode())
        if st == 200 and isinstance(raw, dict):
            nodes = (((raw.get("data") or {}).get("issues") or {}).get("nodes")) or []
            proj = [{"id": n.get("id"), "identifier": n.get("identifier"),
                     "title": n.get("title"), "state": (n.get("state") or {}).get("name")}
                    for n in nodes]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=proj, source="Linear GraphQL issues", live=True,
                           note=f"live · {len(nodes)} issues", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but Linear HTTP {st}", schema_preview=self.schema_preview)


__all__ = ["JiraConnector", "ServiceNowConnector", "ZendeskConnector", "LinearConnector"]
