# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""ERP connectors (credential-READY) — NetSuite, Dynamics F&O/BC, Sage, Acumatica, Infor.

Each is a REAL client (documented endpoint + record shape + auth header). With NO
creds → state=READY + exact secret name; NEVER fabricates a record. The moment
credentials land in the Space secret → CONNECTED → live data.

API refs (publicly documented shapes; SZL writes its own original client code):
  NetSuite SuiteTalk REST  https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1540391670.html
  Dynamics 365 F&O OData   https://learn.microsoft.com/dynamics365/fin-ops-core/dev-itpro/data-entities/odata
  Dynamics 365 BC API      https://learn.microsoft.com/dynamics365/business-central/dev-itpro/api-reference/v2.0/
  Sage Intacct / Sage 200  https://developer.sage.com/
  Acumatica REST           https://help.acumatica.com/Help?ScreenId=ShowWiki&pageid=...
  Infor ION API            https://docs.infor.com/
"""
from __future__ import annotations

import os

from ..ready import ReadyConnector
from ..registry import register


# ── NetSuite SuiteTalk REST (oauth2 / token-based auth; no free tier) ─────────
@register
class NetSuiteConnector(ReadyConnector):
    id = "netsuite"
    label = "Oracle NetSuite (SuiteTalk REST)"
    category = "erp"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_NETSUITE_ACCOUNT_ID", "SZL_NETSUITE_ACCESS_TOKEN"]
    _primary_secret = "SZL_NETSUITE_ACCESS_TOKEN"
    provider_base = "https://{account}.suitetalk.api.netsuite.com/services/rest/record/v1"
    docs_url = "https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1540391670.html"
    schema_preview = ["id", "entityId", "companyName", "email"]
    _read_path = "customer?limit=10"
    _record_path = "items"

    def _base_url(self):
        acct = os.environ.get("SZL_NETSUITE_ACCOUNT_ID", "").lower().replace("_", "-")
        return self.provider_base.replace("{account}", acct)

    def _auth_header(self):
        tok = os.environ.get("SZL_NETSUITE_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


# ── Dynamics 365 Finance & Operations (OData; Entra oauth2; no free tier) ─────
@register
class DynamicsFOConnector(ReadyConnector):
    id = "dynamics_fo"
    label = "Microsoft Dynamics 365 Finance & Operations"
    category = "erp"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_DYNAMICS_FO_RESOURCE_URL", "SZL_DYNAMICS_FO_ACCESS_TOKEN",
                "SZL_DYNAMICS_FO_TENANT_ID", "SZL_DYNAMICS_FO_CLIENT_ID",
                "SZL_DYNAMICS_FO_CLIENT_SECRET"]
    _primary_secret = "SZL_DYNAMICS_FO_ACCESS_TOKEN"
    provider_base = "{resource_url}/data"
    docs_url = "https://learn.microsoft.com/dynamics365/fin-ops-core/dev-itpro/data-entities/odata"
    schema_preview = ["CustomerAccount", "Name", "SalesCurrencyCode", "CustomerGroupId"]
    _read_path = "CustomersV3?$top=10&$select=CustomerAccount,Name,SalesCurrencyCode"
    _record_path = "value"

    def _base_url(self):
        return self.provider_base.replace("{resource_url}",
                                          os.environ.get("SZL_DYNAMICS_FO_RESOURCE_URL", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_DYNAMICS_FO_ACCESS_TOKEN")
        return ({"Authorization": f"Bearer {tok}", "OData-MaxVersion": "4.0",
                 "OData-Version": "4.0"} if tok else {})


# ── Dynamics 365 Business Central (API v2.0; Entra oauth2; no free tier) ──────
@register
class DynamicsBCConnector(ReadyConnector):
    id = "dynamics_bc"
    label = "Microsoft Dynamics 365 Business Central"
    category = "erp"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_DYNAMICS_BC_ENV_URL", "SZL_DYNAMICS_BC_ACCESS_TOKEN",
                "SZL_DYNAMICS_BC_TENANT_ID", "SZL_DYNAMICS_BC_COMPANY_ID"]
    _primary_secret = "SZL_DYNAMICS_BC_ACCESS_TOKEN"
    provider_base = "{env_url}/api/v2.0"
    docs_url = "https://learn.microsoft.com/dynamics365/business-central/dev-itpro/api-reference/v2.0/"
    schema_preview = ["id", "number", "displayName", "email"]
    _read_path = "customers?$top=10"
    _record_path = "value"

    def _base_url(self):
        return self.provider_base.replace("{env_url}",
                                          os.environ.get("SZL_DYNAMICS_BC_ENV_URL", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_DYNAMICS_BC_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


# ── Sage Intacct (REST/oauth2; no free tier) ──────────────────────────────────
@register
class SageConnector(ReadyConnector):
    id = "sage"
    label = "Sage Intacct"
    category = "erp"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_SAGE_ACCESS_TOKEN", "SZL_SAGE_COMPANY_ID"]
    _primary_secret = "SZL_SAGE_ACCESS_TOKEN"
    provider_base = "https://api.intacct.com/ia/api/v1"
    docs_url = "https://developer.sage.com/"
    schema_preview = ["key", "id", "name", "status"]
    _read_path = "objects/accounts-receivable/customer?size=10"
    _record_path = "ia::result"

    def _auth_header(self):
        tok = os.environ.get("SZL_SAGE_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


# ── Acumatica Cloud ERP (REST; basic/oauth2; no free tier) ────────────────────
@register
class AcumaticaConnector(ReadyConnector):
    id = "acumatica"
    label = "Acumatica Cloud ERP"
    category = "erp"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_ACUMATICA_SITE_URL", "SZL_ACUMATICA_ACCESS_TOKEN"]
    _primary_secret = "SZL_ACUMATICA_ACCESS_TOKEN"
    provider_base = "{site_url}/entity/Default/24.200.001"
    docs_url = "https://help.acumatica.com/"
    schema_preview = ["CustomerID", "CustomerName", "Email", "Status"]
    _read_path = "Customer?$top=10"
    _record_path = ""

    def _base_url(self):
        return self.provider_base.replace("{site_url}",
                                          os.environ.get("SZL_ACUMATICA_SITE_URL", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_ACUMATICA_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _dig(self, raw):
        # Acumatica returns a bare JSON array of entity objects
        if isinstance(raw, list):
            out = []
            for r in raw:
                if isinstance(r, dict):
                    out.append({k: (r.get(k, {}) or {}).get("value")
                                if isinstance(r.get(k), dict) else r.get(k)
                                for k in self.schema_preview})
            return out
        return []


# ── Infor (ION API gateway; oauth2; no free tier) ─────────────────────────────
@register
class InforConnector(ReadyConnector):
    id = "infor"
    label = "Infor (ION API / M3 / LN)"
    category = "erp"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_INFOR_ION_URL", "SZL_INFOR_ACCESS_TOKEN", "SZL_INFOR_TENANT"]
    _primary_secret = "SZL_INFOR_ACCESS_TOKEN"
    provider_base = "{ion_url}"
    docs_url = "https://docs.infor.com/"
    schema_preview = ["CustomerNumber", "Name", "Country", "Currency"]
    _read_path = "M3/m3api-rest/v2/execute/CRS610MI/LstByNumber?maxrecs=10"
    _record_path = "MIRecord"

    def _base_url(self):
        return self.provider_base.replace("{ion_url}",
                                          os.environ.get("SZL_INFOR_ION_URL", "").rstrip("/"))

    def _auth_header(self):
        tok = os.environ.get("SZL_INFOR_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


__all__ = ["NetSuiteConnector", "DynamicsFOConnector", "DynamicsBCConnector",
           "SageConnector", "AcumaticaConnector", "InforConnector"]
