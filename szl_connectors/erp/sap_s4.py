# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 · Perplexity Computer Agent.
"""SAP S/4HANA connector — OData (public API Business Hub sandbox read).

Targets the publicly documented OData entity sets (SZL's own original client):
  GET {base}/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner?$top=
  GET .../API_SALES_ORDER_SRV/A_SalesOrder
Public sandbox: https://sandbox.api.sap.com/s4hanacloud/...  (free APIKey header).
Docs: https://api.sap.com  /  https://community.sap.com (S/4HANA Cloud sandbox)

Default state: READY → CONNECTED (read-only) vs the public sandbox once
SZL_SAP_S4_API_KEY is set. Writes stay READY until a customer tenant + OAuth.
"""
from __future__ import annotations

import os
from typing import Any

from ..base import Connector, Records, State, http_json
from ..registry import register

_SANDBOX = "https://sandbox.api.sap.com/s4hanacloud"


@register
class SapS4Connector(Connector):
    id = "sap_s4"
    label = "SAP S/4HANA (OData)"
    category = "erp"
    auth_kind = "api_key"
    free_tier = True   # public read-only sandbox (free APIKey)
    env_vars = ["SZL_SAP_S4_API_KEY"]
    provider_base = "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_BUSINESS_PARTNER"
    docs_url = "https://api.sap.com/api/API_BUSINESS_PARTNER/overview"
    schema_preview = ["BusinessPartner", "BusinessPartnerName", "BusinessPartnerCategory", "OrganizationBPName1"]

    def _headers(self):
        key = os.environ.get("SZL_SAP_S4_API_KEY")
        h = {"Accept": "application/json"}
        if key:
            h["APIKey"] = key
        return h

    def _probe(self):
        key = os.environ.get("SZL_SAP_S4_API_KEY")
        if not key:
            return None, "no key"
        st, _ = http_json(self.provider_base + "/A_BusinessPartner?$top=1&$format=json",
                          headers=self._headers())
        return (st == 200), f"SAP sandbox HTTP {st}"

    def read(self, query: dict | None = None) -> Records:
        key = os.environ.get("SZL_SAP_S4_API_KEY")
        if not key:
            return self._ready_records(
                "provide credentials to activate — set SZL_SAP_S4_API_KEY "
                "(free read-only APIKey from the SAP Business Accelerator Hub: https://api.sap.com). "
                "Reads A_BusinessPartner / A_SalesOrder OData entity sets.")
        entity = (query or {}).get("entity", "A_BusinessPartner")
        top = max(1, min(int((query or {}).get("limit", 12)), 50))
        st, raw = http_json(f"{self.provider_base}/{entity}?$top={top}&$format=json",
                            headers=self._headers())
        if st == 200 and isinstance(raw, dict):
            results = raw.get("d", {}).get("results") if isinstance(raw.get("d"), dict) else raw.get("value", [])
            rows = []
            for r in (results or [])[:top]:
                rows.append({k: r.get(k) for k in self.schema_preview if k in r} or
                            {k: v for k, v in list(r.items())[:6] if not isinstance(v, dict)})
            return Records(connector_id=self.id, category=self.category, state=State.CONNECTED,
                           records=rows, source=f"SAP S/4HANA sandbox OData {entity}", live=True,
                           note=f"live (read-only sandbox) · {entity}", schema_preview=self.schema_preview)
        return Records(connector_id=self.id, category=self.category, state=State.ERROR,
                       records=[], source=self.provider_base, live=False,
                       note=f"credentials present but SAP sandbox HTTP {st}", schema_preview=self.schema_preview)


__all__ = ["SapS4Connector"]
