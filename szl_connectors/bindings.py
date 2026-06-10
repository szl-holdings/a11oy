# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors.bindings — which tab/vertical binds to which connector(s).

A tab declares its connector binding here; the tab renders from each connector's
`Records` and its honest `state`. A tab bound to a keyless data source is LIVE on
first paint; a tab bound to a CRM/ERP shows the READY "connect to enable" state
with the real schema preview until the customer meshes in.
"""
from __future__ import annotations

TAB_BINDINGS: dict[str, list[str]] = {
    # a11oy governed-AI / security verticals (keyless → CONNECTED now)
    "vuln":      ["nvd_cve", "cisa_kev", "epss"],
    "attack":    ["mitre_attack"],
    "macro":     ["fred", "sec_edgar"],
    "research":  ["arxiv", "hf_hub", "github"],
    "ontology":  ["wikidata"],
    # enterprise CRM / ERP / platform verticals (READY until customer creds)
    "crm":       ["salesforce", "hubspot", "dynamics_crm", "zoho_crm", "pipedrive",
                  "close", "freshsales", "sugarcrm"],
    "erp":       ["odoo", "erpnext", "sap_s4", "netsuite", "dynamics_erp",
                  "sage", "acumatica", "infor"],
    "identity":  ["okta", "entra", "auth0"],
    "comms":     ["slack", "teams", "email"],
    "tickets":   ["jira", "servicenow", "zendesk", "linear"],
    "warehouse": ["snowflake", "databricks", "bigquery", "postgres"],
    "storage":   ["s3", "gcs", "azure_blob"],
    "observ":    ["datadog", "splunk", "grafana"],
    # killinchu maritime / air / geo verticals
    "maritime":  ["opensky", "aisstream", "noaa"],
    "geo":       ["overpass", "usgs", "wikidata"],
}


def tabs_for(connector_id: str) -> list[str]:
    return [t for t, ids in TAB_BINDINGS.items() if connector_id in ids]


__all__ = ["TAB_BINDINGS", "tabs_for"]
