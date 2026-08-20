# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""Data-warehouse / database connectors — Snowflake, Databricks, BigQuery, Postgres.

REAL clients against documented endpoints. NO creds → READY + exact secret name;
NEVER fabricates a record. Reads are catalog/metadata-scoped by default (list
tables/datasets) — cheap, safe, and verifiable.

API refs (publicly documented shapes):
  Snowflake SQL API    https://docs.snowflake.com/developer-guide/sql-api/index
  Databricks REST 2.1  https://docs.databricks.com/api/workspace/statementexecution
  BigQuery REST v2     https://cloud.google.com/bigquery/docs/reference/rest
  Postgres (PostgREST) https://postgrest.org/  (or native via psycopg when available)
"""
from __future__ import annotations

import os

from ..base import State, Records, http_json
from ..ready import ReadyConnector
from ..registry import register


# ── Snowflake (SQL API v2; oauth2/keypair; free 30-day trial) ─────────────────
@register
class SnowflakeConnector(ReadyConnector):
    id = "snowflake"
    label = "Snowflake (SQL API)"
    category = "warehouse"
    auth_kind = "oauth2"
    free_tier = True  # 30-day trial
    env_vars = ["SZL_SNOWFLAKE_ACCOUNT", "SZL_SNOWFLAKE_ACCESS_TOKEN"]
    _primary_secret = "SZL_SNOWFLAKE_ACCESS_TOKEN"
    provider_base = "https://{account}.snowflakecomputing.com/api/v2"
    docs_url = "https://docs.snowflake.com/developer-guide/sql-api/index"
    schema_preview = ["database_name", "schema_name", "table_name", "row_count"]
    _read_path = "statements"

    def _base_url(self):
        return self.provider_base.replace("{account}",
                                          os.environ.get("SZL_SNOWFLAKE_ACCOUNT", ""))

    def _auth_header(self):
        tok = os.environ.get("SZL_SNOWFLAKE_ACCESS_TOKEN")
        return ({"Authorization": f"Bearer {tok}",
                 "X-Snowflake-Authorization-Token-Type": "OAUTH"} if tok else {})

    def read(self, query=None):
        if self._primary_missing():
            return self._ready_records(
                "provide credentials to activate — set SZL_SNOWFLAKE_ACCOUNT, "
                "SZL_SNOWFLAKE_ACCESS_TOKEN. POSTs SHOW TABLES via /api/v2/statements.")
        import json as _json
        body = {"statement": "SHOW TABLES LIMIT 10", "timeout": 30}
        url = self._base_url() + "/statements"
        st, raw = http_json(url, method="POST",
                            headers={"Content-Type": "application/json", **self._auth_header()},
                            data=_json.dumps(body).encode())
        if st in (200, 202) and isinstance(raw, dict):
            rows = raw.get("data", []) or []
            proj = [{"row": r} for r in rows[:10]] if rows else []
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=proj, source="Snowflake SQL API SHOW TABLES", live=True,
                           note=f"live · {len(rows)} rows", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but Snowflake HTTP {st}", schema_preview=self.schema_preview)


# ── Databricks (Statement Execution API 2.0; PAT; free Community/trial) ───────
@register
class DatabricksConnector(ReadyConnector):
    id = "databricks"
    label = "Databricks (SQL Statement API)"
    category = "warehouse"
    auth_kind = "api_key"
    free_tier = True
    env_vars = ["SZL_DATABRICKS_HOST", "SZL_DATABRICKS_TOKEN", "SZL_DATABRICKS_WAREHOUSE_ID"]
    _primary_secret = "SZL_DATABRICKS_TOKEN"
    provider_base = "{host}/api/2.0"
    docs_url = "https://docs.databricks.com/api/workspace/statementexecution"
    schema_preview = ["catalog", "schema", "tableName", "tableType"]
    _read_path = "unity-catalog/tables?max_results=10"
    _record_path = "tables"

    def _base_url(self):
        return self.provider_base.replace("{host}",
                                          os.environ.get("SZL_DATABRICKS_HOST", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_DATABRICKS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


# ── Google BigQuery (REST v2; oauth2 access token; free 1TB/mo query) ─────────
@register
class BigQueryConnector(ReadyConnector):
    id = "bigquery"
    label = "Google BigQuery"
    category = "warehouse"
    auth_kind = "oauth2"
    free_tier = True  # 1 TB/month free query tier
    env_vars = ["SZL_BIGQUERY_PROJECT_ID", "SZL_BIGQUERY_ACCESS_TOKEN"]
    _primary_secret = "SZL_BIGQUERY_ACCESS_TOKEN"
    provider_base = "https://bigquery.googleapis.com/bigquery/v2"
    docs_url = "https://cloud.google.com/bigquery/docs/reference/rest"
    schema_preview = ["datasetReference.datasetId", "id", "location"]
    _read_path = "projects/{project}/datasets?maxResults=10"
    _record_path = "datasets"

    def _base_url(self):
        return self.provider_base

    def _auth_header(self):
        tok = os.environ.get("SZL_BIGQUERY_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def read(self, query=None):
        if self._primary_missing():
            return self._ready_records(
                "provide credentials to activate — set SZL_BIGQUERY_PROJECT_ID, "
                "SZL_BIGQUERY_ACCESS_TOKEN. Lists datasets via REST v2.")
        proj = os.environ.get("SZL_BIGQUERY_PROJECT_ID", "")
        url = f"{self.provider_base}/projects/{proj}/datasets?maxResults=10"
        st, raw = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        if st == 200 and isinstance(raw, dict):
            rows = raw.get("datasets", []) or []
            out = [{"datasetId": (r.get("datasetReference") or {}).get("datasetId"),
                    "id": r.get("id"), "location": r.get("location")} for r in rows[:10]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=out, source="BigQuery datasets.list", live=True,
                           note=f"live · {len(rows)} datasets", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but BigQuery HTTP {st}", schema_preview=self.schema_preview)


# ── Postgres via PostgREST (api_key/jwt; widely self-hosted; free) ────────────
@register
class PostgresConnector(ReadyConnector):
    id = "postgres"
    label = "PostgreSQL (via PostgREST)"
    category = "warehouse"
    auth_kind = "api_key"
    free_tier = True  # open-source self-host
    env_vars = ["SZL_POSTGREST_URL", "SZL_POSTGREST_JWT"]
    _primary_secret = "SZL_POSTGREST_URL"
    provider_base = "{postgrest_url}"
    docs_url = "https://postgrest.org/"
    schema_preview = ["(table rows projected by selected resource)"]
    _read_path = ""

    def _base_url(self):
        return self.provider_base.replace("{postgrest_url}",
                                          os.environ.get("SZL_POSTGREST_URL", "").rstrip("/"))

    def _auth_header(self):
        jwt = os.environ.get("SZL_POSTGREST_JWT")
        return {"Authorization": f"Bearer {jwt}"} if jwt else {}

    def read(self, query=None):
        if not os.environ.get("SZL_POSTGREST_URL"):
            return self._ready_records(
                "provide credentials to activate — set SZL_POSTGREST_URL "
                "(and optional SZL_POSTGREST_JWT). GETs a configured resource path.")
        resource = (query or {}).get("resource", "")
        if not resource:
            return self._ready_records(
                "connected — pass query.resource (PostgREST table/view name) to read rows. "
                "Endpoint: " + self._base_url())
        url = self._base_url() + "/" + resource.lstrip("/") + "?limit=10"
        st, raw = http_json(url, headers={"Accept": "application/json", **self._auth_header()})
        if st == 200 and isinstance(raw, list):
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=raw[:10], source=f"PostgREST {resource}", live=True,
                           note=f"live · {len(raw)} rows", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but PostgREST HTTP {st}", schema_preview=self.schema_preview)


__all__ = ["SnowflakeConnector", "DatabricksConnector", "BigQueryConnector", "PostgresConnector"]
