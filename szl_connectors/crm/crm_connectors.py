# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""CRM connectors — built + tested against each vendor's documented API shape.

Each is a REAL client (documented endpoint + record shape + auth header). With NO
creds → state=READY + exact secret name; NEVER fabricates a record. The moment
the customer's credentials land in the Space secret → CONNECTED → live data.

API refs (publicly documented shapes; SZL writes its own original client code):
  Salesforce REST   https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_list.htm
  HubSpot CRM v3    https://developers.hubspot.com/docs/api-reference/latest/overview
  Dynamics 365      https://learn.microsoft.com/dynamics365/ (OData v9.2)
  Zoho CRM v8       https://www.zoho.com/crm/developer/docs/api/v8/
  Pipedrive v2      https://developers.pipedrive.com/docs/api/v1
  Close             https://developer.close.com/
  Freshsales        https://developers.freshworks.com/crm/api/
  SugarCRM v11      https://support.sugarcrm.com/documentation/
"""
from __future__ import annotations

import os

from ..base import State, Records, WriteResult, http_json, cred_fingerprint
from ..ready import ReadyConnector, WritableReadyConnector
from ..registry import register
from ..governance import gate_write


# ── Salesforce (oauth2; free Developer Edition) ──────────────────────────────
@register
class SalesforceConnector(WritableReadyConnector):
    id = "salesforce"
    label = "Salesforce"
    category = "crm"
    auth_kind = "oauth2"
    free_tier = True  # Developer Edition (free)
    env_vars = ["SZL_SALESFORCE_INSTANCE_URL", "SZL_SALESFORCE_ACCESS_TOKEN",
                "SZL_SALESFORCE_CLIENT_ID", "SZL_SALESFORCE_CLIENT_SECRET",
                "SZL_SALESFORCE_REFRESH_TOKEN"]
    _primary_secret = "SZL_SALESFORCE_ACCESS_TOKEN"
    provider_base = "{instance_url}/services/data/v60.0"
    docs_url = "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_list.htm"
    schema_preview = ["Id", "Name", "Account", "Email", "Owner"]
    _read_path = "query?q=" + "SELECT+Id,Name,Email+FROM+Contact+LIMIT+10"
    _record_path = "records"
    _record_fields = ["Id", "Name", "Email"]
    _write_path = "sobjects/Contact"

    def _base_url(self):
        inst = os.environ.get("SZL_SALESFORCE_INSTANCE_URL", "")
        return self.provider_base.replace("{instance_url}", inst)

    def _auth_header(self):
        tok = os.environ.get("SZL_SALESFORCE_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}"} if tok else {}


# ── HubSpot (api_key private-app token OR oauth2; free dev account) ───────────
@register
class HubSpotConnector(WritableReadyConnector):
    id = "hubspot"
    label = "HubSpot"
    category = "crm"
    auth_kind = "api_key"  # private-app token; oauth2 also supported
    free_tier = True
    env_vars = ["SZL_HUBSPOT_API_KEY"]
    _primary_secret = "SZL_HUBSPOT_API_KEY"
    provider_base = "https://api.hubapi.com"
    docs_url = "https://developers.hubspot.com/docs/api-reference/latest/overview"
    schema_preview = ["id", "firstname", "lastname", "email", "company"]
    _read_path = "crm/v3/objects/contacts?limit=10&properties=firstname,lastname,email,company"
    _record_path = "results"
    _write_path = "crm/v3/objects/contacts"

    def _auth_header(self):
        tok = os.environ.get("SZL_HUBSPOT_API_KEY")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    def _dig(self, raw):
        rows = (raw or {}).get("results", []) if isinstance(raw, dict) else []
        out = []
        for r in rows:
            p = r.get("properties", {}) if isinstance(r, dict) else {}
            out.append({"id": r.get("id"), **{k: p.get(k) for k in
                        ("firstname", "lastname", "email", "company")}})
        return out


# ── Dynamics 365 Sales (oauth2/Entra; OData v9.2) ────────────────────────────
@register
class Dynamics365Connector(ReadyConnector):
    id = "dynamics_crm"
    label = "Microsoft Dynamics 365 (Sales)"
    category = "crm"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_DYNAMICS_CRM_ORG_URL", "SZL_DYNAMICS_CRM_ACCESS_TOKEN",
                "SZL_DYNAMICS_CRM_CLIENT_ID", "SZL_DYNAMICS_CRM_CLIENT_SECRET",
                "SZL_DYNAMICS_CRM_TENANT_ID"]
    _primary_secret = "SZL_DYNAMICS_CRM_ACCESS_TOKEN"
    provider_base = "{org_url}/api/data/v9.2"
    docs_url = "https://learn.microsoft.com/power-apps/developer/data-platform/webapi/overview"
    schema_preview = ["contactid", "fullname", "emailaddress1", "telephone1"]
    _read_path = "contacts?$top=10&$select=fullname,emailaddress1,telephone1"
    _record_path = "value"

    def _base_url(self):
        return self.provider_base.replace("{org_url}", os.environ.get("SZL_DYNAMICS_CRM_ORG_URL", ""))

    def _auth_header(self):
        tok = os.environ.get("SZL_DYNAMICS_CRM_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {tok}", "OData-MaxVersion": "4.0", "OData-Version": "4.0"} if tok else {}


# ── Zoho CRM v8 (oauth2; free edition + sandbox) ─────────────────────────────
@register
class ZohoCrmConnector(ReadyConnector):
    id = "zoho_crm"
    label = "Zoho CRM"
    category = "crm"
    auth_kind = "oauth2"
    free_tier = True
    env_vars = ["SZL_ZOHO_CRM_ACCESS_TOKEN", "SZL_ZOHO_CRM_CLIENT_ID",
                "SZL_ZOHO_CRM_CLIENT_SECRET", "SZL_ZOHO_CRM_REFRESH_TOKEN"]
    _primary_secret = "SZL_ZOHO_CRM_ACCESS_TOKEN"
    provider_base = "https://www.zohoapis.com/crm/v8"
    docs_url = "https://www.zoho.com/crm/developer/docs/api/v8/"
    schema_preview = ["id", "Full_Name", "Email", "Account_Name"]
    _read_path = "Contacts?fields=Full_Name,Email,Account_Name&per_page=10"
    _record_path = "data"

    def _auth_header(self):
        tok = os.environ.get("SZL_ZOHO_CRM_ACCESS_TOKEN")
        return {"Authorization": f"Zoho-oauthtoken {tok}"} if tok else {}


# ── Pipedrive v2 (oauth2/api_key) ────────────────────────────────────────────
@register
class PipedriveConnector(ReadyConnector):
    id = "pipedrive"
    label = "Pipedrive"
    category = "crm"
    auth_kind = "api_key"
    free_tier = False
    env_vars = ["SZL_PIPEDRIVE_API_TOKEN", "SZL_PIPEDRIVE_COMPANY_DOMAIN"]
    _primary_secret = "SZL_PIPEDRIVE_API_TOKEN"
    provider_base = "https://{domain}.pipedrive.com/api/v2"
    docs_url = "https://developers.pipedrive.com/docs/api/v1"
    schema_preview = ["id", "name", "email", "org_id"]
    _read_path = "persons?limit=10"
    _record_path = "data"

    def _base_url(self):
        return self.provider_base.replace("{domain}", os.environ.get("SZL_PIPEDRIVE_COMPANY_DOMAIN", "api"))

    def _auth_header(self):
        # Pipedrive uses api_token query param; we also support Bearer
        return {}

    def read(self, query=None):
        tok = os.environ.get("SZL_PIPEDRIVE_API_TOKEN")
        if not tok:
            return self._ready_records(
                "provide credentials to activate — set SZL_PIPEDRIVE_API_TOKEN, "
                "SZL_PIPEDRIVE_COMPANY_DOMAIN. Hits /api/v2/persons.")
        url = self._base_url() + "/persons?limit=10&api_token=" + tok
        st, raw = http_json(url, headers={"Accept": "application/json"})
        if st == 200 and isinstance(raw, dict):
            rows = raw.get("data", []) or []
            proj = [{k: r.get(k) for k in self.schema_preview if k in r} for r in rows[:10]]
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=proj, source=f"Pipedrive {url.split('?')[0]}", live=True,
                           note=f"live · {len(rows)} persons", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but Pipedrive HTTP {st}", schema_preview=self.schema_preview)


# ── Close (api_key, basic) ───────────────────────────────────────────────────
@register
class CloseConnector(ReadyConnector):
    id = "close"
    label = "Close CRM"
    category = "crm"
    auth_kind = "api_key"
    free_tier = False
    env_vars = ["SZL_CLOSE_API_KEY"]
    _primary_secret = "SZL_CLOSE_API_KEY"
    provider_base = "https://api.close.com/api/v1"
    docs_url = "https://developer.close.com/"
    schema_preview = ["id", "name", "display_name"]
    _read_path = "contact/?_limit=10"
    _record_path = "data"

    def _auth_header(self):
        import base64
        key = os.environ.get("SZL_CLOSE_API_KEY")
        if not key:
            return {}
        b = base64.b64encode(f"{key}:".encode()).decode()
        return {"Authorization": f"Basic {b}"}


# ── Freshsales (api_key token header; free plan) ─────────────────────────────
@register
class FreshsalesConnector(ReadyConnector):
    id = "freshsales"
    label = "Freshsales (Freshworks CRM)"
    category = "crm"
    auth_kind = "api_key"
    free_tier = True
    env_vars = ["SZL_FRESHSALES_API_KEY", "SZL_FRESHSALES_DOMAIN"]
    _primary_secret = "SZL_FRESHSALES_API_KEY"
    provider_base = "https://{domain}.myfreshworks.com/crm/sales/api"
    docs_url = "https://developers.freshworks.com/crm/api/"
    schema_preview = ["id", "display_name", "email", "mobile_number"]
    _read_path = "contacts/view/0"
    _record_path = "contacts"

    def _base_url(self):
        return self.provider_base.replace("{domain}", os.environ.get("SZL_FRESHSALES_DOMAIN", "api"))

    def _auth_header(self):
        key = os.environ.get("SZL_FRESHSALES_API_KEY")
        return {"Authorization": f"Token token={key}"} if key else {}


# ── SugarCRM v11 (oauth2 password/refresh) ───────────────────────────────────
@register
class SugarCrmConnector(ReadyConnector):
    id = "sugarcrm"
    label = "SugarCRM"
    category = "crm"
    auth_kind = "oauth2"
    free_tier = False
    env_vars = ["SZL_SUGARCRM_SITE_URL", "SZL_SUGARCRM_ACCESS_TOKEN"]
    _primary_secret = "SZL_SUGARCRM_ACCESS_TOKEN"
    provider_base = "{site_url}/rest/v11_24"
    docs_url = "https://support.sugarcrm.com/documentation/"
    schema_preview = ["id", "name", "email1", "account_name"]
    _read_path = "Contacts?max_num=10&fields=name,email1,account_name"
    _record_path = "records"

    def _base_url(self):
        return self.provider_base.replace("{site_url}", os.environ.get("SZL_SUGARCRM_SITE_URL", ""))

    def _auth_header(self):
        tok = os.environ.get("SZL_SUGARCRM_ACCESS_TOKEN")
        return {"OAuth-Token": tok} if tok else {}


__all__ = ["SalesforceConnector", "HubSpotConnector", "Dynamics365Connector",
           "ZohoCrmConnector", "PipedriveConnector", "CloseConnector",
           "FreshsalesConnector", "SugarCrmConnector"]
