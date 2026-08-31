# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""ERPNext / Frappe ERP connector (open-source) — REST.

Targets the publicly documented Frappe REST shape (SZL's own original client):
  GET    {host}/api/resource/{DocType}?limit_page_length=&fields=
  POST   {host}/api/resource/{DocType}     (create; Λ-gated + receipted)
Auth: Authorization: token <api_key>:<api_secret>  (or basic).
DocTypes: Contact, Customer, Opportunity, Sales Order, Item.
Docs: https://docs.frappe.io/framework/user/en/api/rest

Default state: CONNECTED vs an SZL self-hosted ERPNext or public demo.erpnext.com
when SZL_ERPNEXT_URL + SZL_ERPNEXT_TOKEN are set; READY otherwise.
Open-source + public demo exist → free_tier=True.
"""
from __future__ import annotations

import json
import os
import urllib.parse as up
from typing import Any

from ..base import Connector, Records, State, WriteResult, http_json, cred_fingerprint
from ..registry import register
from ..governance import gate_write


@register
class ErpNextConnector(Connector):
    id = "erpnext"
    label = "ERPNext / Frappe (open-source)"
    category = "erp"
    auth_kind = "token"
    free_tier = True   # open-source; self-host free; public demo.erpnext.com
    writable = True
    mcp_tool = "szl_connector_read/write"
    env_vars = ["SZL_ERPNEXT_URL", "SZL_ERPNEXT_TOKEN"]
    provider_base = "{SZL_ERPNEXT_URL}/api/resource/{DocType}"
    docs_url = "https://docs.frappe.io/framework/user/en/api/rest"
    schema_preview = ["name", "customer_name", "email_id", "mobile_no", "territory"]

    def _conf(self):
        return os.environ.get("SZL_ERPNEXT_URL"), os.environ.get("SZL_ERPNEXT_TOKEN")

    def _headers(self):
        _, tok = self._conf()
        h = {"Accept": "application/json"}
        if tok:
            # token can be "key:secret"; pass as Frappe token scheme
            h["Authorization"] = f"token {tok}"
        return h

    def _probe(self):
        url, tok = self._conf()
        if not (url and tok):
            return None, "no creds"
        st, _ = http_json(f"{url}/api/method/frappe.auth.get_logged_user", headers=self._headers())
        return (st == 200), f"ERPNext HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        url, tok = self._conf()
        missing = [k for k in self.env_vars if not os.environ.get(k)]
        if missing:
            return self._ready_records(
                "provide credentials to activate — set " + ", ".join(missing) +
                " (ERPNext is open-source; self-host free or use public demo.erpnext.com; "
                "token format 'api_key:api_secret')")
        doctype = (query or {}).get("doctype", "Customer")
        limit = max(1, min(int((query or {}).get("limit", 12)), 50))
        fields = (query or {}).get("fields", self.schema_preview)
        params = {"limit_page_length": limit, "fields": json.dumps(list(fields))}
        st, raw = http_json(f"{url}/api/resource/{up.quote(doctype)}?" + up.urlencode(params),
                            headers=self._headers())
        if st == 200 and isinstance(raw, dict):
            rows = raw.get("data", []) or []
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=rows[:limit], source=f"ERPNext /api/resource/{doctype} @ {url}",
                           live=True, note=f"live · DocType={doctype} · {len(rows)} rows",
                           schema_preview=list(fields))
        return Records(connector_id=self.id, category=self.category,
                       state=State.ERROR if st else State.ERROR, records=[], source=self.provider_base,
                       live=False, note=f"credentials present but ERPNext returned HTTP {st}",
                       schema_preview=self.schema_preview)

    def write(self, action: dict | None = None) -> WriteResult:
        action = action or {}
        url, tok = self._conf()
        connected = bool(url and tok)
        doctype = action.get("doctype", "Contact")
        gate_action = {"method": "create", "doctype": doctype,
                       "values_keys": sorted((action.get("values") or {}).keys())}
        creds_fp = {"token": cred_fingerprint(tok)} if tok else {}
        allowed, lam, receipt, quorum, detail = gate_write(
            connector_id=self.id, connected=connected, action=gate_action,
            cred_fingerprints=creds_fp, quorum_present=action.get("quorum_present"))
        if not allowed:
            return WriteResult(connector_id=self.id, ok=False,
                               state=State.READY if not connected else State.CONNECTED,
                               receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                               quorum=quorum, detail=detail, dsse=receipt["dsse"])
        body = json.dumps(action.get("values", {})).encode()
        st, raw = http_json(f"{url}/api/resource/{up.quote(doctype)}", method="POST",
                            headers={**self._headers(), "Content-Type": "application/json"}, data=body)
        if st in (200, 201) and isinstance(raw, dict):
            new = raw.get("data", {}).get("name")
            return WriteResult(connector_id=self.id, ok=True, state=State.CONNECTED,
                               receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                               quorum=quorum, detail=f"ERPNext {doctype} created name={new}",
                               dsse=receipt["dsse"])
        return WriteResult(connector_id=self.id, ok=False, state=State.ERROR,
                           receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                           quorum=quorum, detail=f"ERPNext write HTTP {st}", dsse=receipt["dsse"])


__all__ = ["ErpNextConnector"]
