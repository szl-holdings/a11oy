# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors — SZL's sovereign Enterprise Connector Framework.

ONE honest Connector abstraction (base.py) → every CRM / ERP / identity / comms /
ITSM / warehouse / storage / observability / data-source provider is a thin
subclass. Importing this package registers every connector into the registry.

DOCTRINE (woven throughout):
  • No fabricated records — honest CONNECTED / READY / SAMPLE / ERROR only.
  • No committed keys — env/Space-secret only; receipts carry fingerprint hashes.
  • Every write() is Λ-gated (Λ never 1.0) + DSSE/Khipu-receipted.
  • Trust never 100%. 0 runtime CDN. GitHub ↔ HF byte-identical.

LIVE NOW (free / no-signup, keyless): CISA KEV, NVD CVE, EPSS, MITRE ATT&CK,
SEC EDGAR, GitHub public, arXiv, HF Hub, Wikidata, USGS, NOAA, Overpass/OSM,
OpenSky (air). Free ERPs Odoo + ERPNext wired live (XML-RPC / REST).

CREDENTIAL-READY (genuine clients, awaiting customer secrets): Salesforce,
HubSpot, Dynamics 365, Zoho, Pipedrive, Close, Freshsales, SugarCRM, NetSuite,
Dynamics F&O/BC, Sage, Acumatica, Infor, SAP S/4HANA, Okta, Entra, Auth0,
Slack, Teams, Jira, ServiceNow, Zendesk, Linear, Snowflake, Databricks,
BigQuery, Postgres, S3, GCS, Azure Blob, Datadog, Splunk, Grafana.

SAMPLE (no free tier; clearly labelled): historical AIS positions.
"""
from __future__ import annotations

# importing each submodule runs its @register decorators
from . import data_sources  # noqa: F401  (security, macro, research, maritime_air, geo)
from . import crm           # noqa: F401
from . import erp           # noqa: F401
from . import identity      # noqa: F401
from . import comms         # noqa: F401
from . import itsm          # noqa: F401
from . import warehouse     # noqa: F401
from . import storage       # noqa: F401
from . import observability  # noqa: F401

from .base import (AuthKind, State, HealthReport, Records, WriteResult,  # noqa: F401
                   Connector, resolve_state, http_json, http_text, cred_fingerprint)
from .registry import REGISTRY, register, get, all_ids, manifest, health  # noqa: F401
from .governance import gate_write, lambda_score, quorum_status  # noqa: F401
from . import oauth         # noqa: F401
from . import bindings      # noqa: F401

__version__ = "1.0.0"

__all__ = [
    "REGISTRY", "register", "get", "all_ids", "manifest", "health",
    "Connector", "State", "HealthReport", "Records", "WriteResult",
    "resolve_state", "http_json", "http_text", "cred_fingerprint",
    "gate_write", "lambda_score", "quorum_status", "oauth", "bindings",
    "__version__",
]
