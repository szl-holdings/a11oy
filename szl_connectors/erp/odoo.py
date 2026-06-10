# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""Odoo ERP connector (open-source) — XML-RPC / JSON-RPC.

Targets Odoo's publicly documented External API shape (SZL's own original client
code, never proprietary SDK code):
  - authenticate: common.authenticate(db, login, password, {})  -> uid
  - read/list:    object.execute_kw(db, uid, pwd, model, 'search_read', [domain], {fields, limit})
  - write:        object.execute_kw(db, uid, pwd, model, 'create', [vals])  (Λ-gated + receipted)
Models: res.partner (contacts/accounts), crm.lead, sale.order, account.move.
Docs: https://www.odoo.com/documentation/18.0/developer/reference/external_api.html

Default state: CONNECTED vs an SZL self-hosted / public-demo Odoo when
SZL_ODOO_URL/DB/USER/PASSWORD are set; READY (provide credentials) otherwise.
Open-source + free demo DBs / Odoo Online trial exist, so free_tier=True.
"""
from __future__ import annotations

import os
import urllib.request as _ur
from typing import Any
from xml.sax.saxutils import escape as _xe

from ..base import Connector, Records, State, WriteResult, cred_fingerprint, _now
from ..registry import register
from ..governance import gate_write

_UA = "SZL-Connectors/1.0 (odoo xml-rpc)"


def _xmlrpc(url: str, method: str, params: list) -> Any:
    """Minimal XML-RPC client (stdlib only). Returns parsed result or raises."""
    import xmlrpc.client as xc
    transport = xc.SafeTransport() if url.startswith("https") else xc.Transport()
    proxy = xc.ServerProxy(url, transport=transport, allow_none=True)
    fn = getattr(proxy, method)
    return fn(*params)


@register
class OdooConnector(Connector):
    id = "odoo"
    label = "Odoo ERP (open-source)"
    category = "erp"
    auth_kind = "basic"
    free_tier = True   # open-source; self-host free; public demo DBs / Online trial
    writable = True
    mcp_tool = "szl_connector_read/write"
    env_vars = ["SZL_ODOO_URL", "SZL_ODOO_DB", "SZL_ODOO_USER", "SZL_ODOO_PASSWORD"]
    provider_base = "{SZL_ODOO_URL}/xmlrpc/2/{common,object}"
    docs_url = "https://www.odoo.com/documentation/18.0/developer/reference/external_api.html"
    schema_preview = ["id", "name", "email", "phone", "city", "country_id"]

    def _conf(self):
        return (os.environ.get("SZL_ODOO_URL"), os.environ.get("SZL_ODOO_DB"),
                os.environ.get("SZL_ODOO_USER"), os.environ.get("SZL_ODOO_PASSWORD"))

    def _authenticate(self):
        url, db, user, pwd = self._conf()
        uid = _xmlrpc(f"{url}/xmlrpc/2/common", "authenticate", [db, user, pwd, {}])
        return uid, url, db, pwd

    def _probe(self):
        url, db, user, pwd = self._conf()
        if not all([url, db, user, pwd]):
            return None, "no creds"
        try:
            uid = _xmlrpc(f"{url}/xmlrpc/2/common", "authenticate", [db, user, pwd, {}])
            return bool(uid), f"Odoo authenticate uid={uid}"
        except Exception as e:
            return False, f"Odoo authenticate failed: {type(e).__name__}"

    def read(self, query: dict | None = None) -> Records:
        url, db, user, pwd = self._conf()
        missing = [k for k in self.env_vars if not os.environ.get(k)]
        if missing:
            return self._ready_records(
                "provide credentials to activate — set " + ", ".join(missing) +
                " (Odoo is open-source; self-host free or use a public demo DB / Online trial)")
        model = (query or {}).get("model", "res.partner")
        limit = max(1, min(int((query or {}).get("limit", 12)), 50))
        fields = (query or {}).get("fields", self.schema_preview)
        domain = (query or {}).get("domain", [])
        try:
            uid = _xmlrpc(f"{url}/xmlrpc/2/common", "authenticate", [db, user, pwd, {}])
            if not uid:
                return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                               records=[], source=self.provider_base, live=False,
                               note="credentials present but Odoo authentication denied",
                               schema_preview=self.schema_preview)
            rows = _xmlrpc(f"{url}/xmlrpc/2/object", "execute_kw",
                           [db, uid, pwd, model, "search_read", [domain],
                            {"fields": list(fields), "limit": limit}])
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=list(rows), source=f"Odoo XML-RPC {model} @ {url}", live=True,
                           note=f"live · model={model} · {len(rows)} rows", schema_preview=list(fields))
        except Exception as e:
            return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                           records=[], source=self.provider_base, live=False,
                           note=f"credentials present but Odoo unreachable: {type(e).__name__}",
                           schema_preview=self.schema_preview)

    def write(self, action: dict | None = None) -> WriteResult:
        action = action or {}
        url, db, user, pwd = self._conf()
        connected = all([url, db, user, pwd])
        # normalize action shape for the gate (Odoo create)
        gate_action = {"method": action.get("method", "create"),
                       "object": action.get("model", "res.partner"),
                       "values_keys": sorted((action.get("values") or {}).keys())}
        creds_fp = {"password": cred_fingerprint(pwd)} if pwd else {}
        allowed, lam, receipt, quorum, detail = gate_write(
            connector_id=self.id, connected=connected, action=gate_action,
            cred_fingerprints=creds_fp, quorum_present=action.get("quorum_present"))
        if not allowed:
            return WriteResult(connector_id=self.id, ok=False, state=State.READY if not connected else State.CONNECTED,
                               receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                               quorum=quorum, detail=detail, dsse=receipt["dsse"])
        try:
            uid = _xmlrpc(f"{url}/xmlrpc/2/common", "authenticate", [db, user, pwd, {}])
            model = action.get("model", "res.partner")
            new_id = _xmlrpc(f"{url}/xmlrpc/2/object", "execute_kw",
                             [db, uid, pwd, model, action.get("method", "create"),
                              [action.get("values", {})]])
            return WriteResult(connector_id=self.id, ok=True, state=State.CONNECTED,
                               receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                               quorum=quorum, detail=f"Odoo {model} created id={new_id}",
                               dsse=receipt["dsse"])
        except Exception as e:
            return WriteResult(connector_id=self.id, ok=False, state=State.ERROR,
                               receipt_hash=receipt["receipt_hash"], lambda_value=lam,
                               quorum=quorum, detail=f"Odoo write failed: {type(e).__name__}",
                               dsse=receipt["dsse"])


__all__ = ["OdooConnector"]
