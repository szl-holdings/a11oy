# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""Observability connectors — Datadog, Splunk, Grafana.

REAL clients against documented endpoints. NO creds → READY + exact secret name;
NEVER fabricates a record. Reads are monitor/alert/dashboard listings.

API refs (publicly documented shapes):
  Datadog API v1     https://docs.datadoghq.com/api/latest/monitors/
  Splunk REST        https://docs.splunk.com/Documentation/Splunk/latest/RESTREF/RESTsearch
  Grafana HTTP API   https://grafana.com/docs/grafana/latest/developers/http_api/
"""
from __future__ import annotations

import base64
import os

from ..base import State, Records, http_json
from ..ready import ReadyConnector
from ..registry import register


# ── Datadog (api_key + app key headers; free tier) ────────────────────────────
@register
class DatadogConnector(ReadyConnector):
    id = "datadog"
    label = "Datadog"
    category = "observability"
    auth_kind = "api_key"
    free_tier = True  # free monitoring tier
    env_vars = ["SZL_DATADOG_API_KEY", "SZL_DATADOG_APP_KEY", "SZL_DATADOG_SITE"]
    _primary_secret = "SZL_DATADOG_API_KEY"
    provider_base = "https://api.{site}/api/v1"
    docs_url = "https://docs.datadoghq.com/api/latest/monitors/"
    schema_preview = ["id", "name", "type", "overall_state"]

    def _base_url(self):
        site = os.environ.get("SZL_DATADOG_SITE", "datadoghq.com")
        return self.provider_base.replace("{site}", site)

    def _auth_header(self):
        api = os.environ.get("SZL_DATADOG_API_KEY", "")
        app = os.environ.get("SZL_DATADOG_APP_KEY", "")
        if not api:
            return {}
        return {"DD-API-KEY": api, "DD-APPLICATION-KEY": app}

    def read(self, query=None):
        if self._primary_missing():
            return self._ready_records(
                "provide credentials to activate — set SZL_DATADOG_API_KEY, "
                "SZL_DATADOG_APP_KEY (+ optional SZL_DATADOG_SITE). Lists monitors.")
        url = self._base_url() + "/monitor?page_size=10"
        st, raw = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        if st == 200 and isinstance(raw, list):
            out = [{k: r.get(k) for k in self.schema_preview if k in r} for r in raw[:10]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=out, source="Datadog monitors", live=True,
                           note=f"live · {len(raw)} monitors", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but Datadog HTTP {st}", schema_preview=self.schema_preview)


# ── Splunk (REST; basic/token auth; free trial) ───────────────────────────────
@register
class SplunkConnector(ReadyConnector):
    id = "splunk"
    label = "Splunk"
    category = "observability"
    auth_kind = "api_key"  # bearer token or basic
    free_tier = False
    env_vars = ["SZL_SPLUNK_HOST", "SZL_SPLUNK_TOKEN"]
    _primary_secret = "SZL_SPLUNK_TOKEN"
    provider_base = "{host}/services"
    docs_url = "https://docs.splunk.com/Documentation/Splunk/latest/RESTREF/RESTsearch"
    schema_preview = ["title", "disabled", "search"]
    _read_path = "saved/searches?output_mode=json&count=10"
    _record_path = "entry"

    def _base_url(self):
        return self.provider_base.replace("{host}",
                                          os.environ.get("SZL_SPLUNK_HOST", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_SPLUNK_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _dig(self, raw):
        rows = (raw or {}).get("entry", []) if isinstance(raw, dict) else []
        out = []
        for r in rows:
            c = r.get("content", {}) if isinstance(r, dict) else {}
            out.append({"title": r.get("name"), "disabled": c.get("disabled"),
                        "search": c.get("search")})
        return out


# ── Grafana (api_key service-account token; free OSS/Cloud) ───────────────────
@register
class GrafanaConnector(ReadyConnector):
    id = "grafana"
    label = "Grafana"
    category = "observability"
    auth_kind = "api_key"
    free_tier = True  # OSS + free cloud tier
    env_vars = ["SZL_GRAFANA_URL", "SZL_GRAFANA_TOKEN"]
    _primary_secret = "SZL_GRAFANA_TOKEN"
    provider_base = "{url}/api"
    docs_url = "https://grafana.com/docs/grafana/latest/developers/http_api/"
    schema_preview = ["id", "uid", "title", "type"]
    _read_path = "search?limit=10"
    _record_path = ""

    def _base_url(self):
        return self.provider_base.replace("{url}",
                                          os.environ.get("SZL_GRAFANA_URL", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_GRAFANA_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _dig(self, raw):
        rows = raw if isinstance(raw, list) else []
        return [{k: r.get(k) for k in self.schema_preview if k in r}
                for r in rows if isinstance(r, dict)]


__all__ = ["DatadogConnector", "SplunkConnector", "GrafanaConnector"]
