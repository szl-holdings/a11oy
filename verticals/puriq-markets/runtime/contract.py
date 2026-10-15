#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Versioned public read-API contract served by the canonical finance runtime.

Downstream projections (the SZLHOLDINGS/finance Space) bind to this contract,
not to the runtime's git revision, so an unrelated A11oy deploy cannot break
them. A released version's routes and response schemas never change: adding a
route or schema, or changing one incompatibly, defines a new version. A response
declares every version whose rules it satisfies, so a purely additive version
is served beside the old one; an incompatible change drops the old version and
needs a coordinated Finance republish (READ_API_CONTRACT.md). The source
revision reported beside the contract is evidence of what answered, never a
compatibility key. The analytics and signed-price component identities are
declared too: they are exact pins that a version number does not cover.
"""
import json
from pathlib import Path

NAME = "szl.finance.read-api"
HEADER = "X-SZL-Finance-Contract"
SCHEMA = "szl.finance.read-contract/v1"
_COMPONENTS = Path(__file__).parent / "components"

# Top-level response schemas each served contract version covers.
RESPONSE_SCHEMAS = {
    1: (
        "szl.finance.providers/v1",
        "szl.finance.overview/v1",
        "szl.finance.observation/v1",
        "szl.finance.analytics/v2",
        "szl.finance.research/v1",
        "szl.finance.signed-price/v1",
    ),
}

# Finance routes (under /api/a11oy/v1/finance) each served version covers.
ROUTES = {
    1: (
        ("GET", "/contract"),
        ("GET", "/providers"),
        ("GET", "/overview"),
        ("GET", "/observations/{source}"),
        ("GET", "/analytics/v2/signals/{symbol_name}"),
        ("GET", "/analytics/v2/quote/{symbol_name}"),
        ("POST", "/analytics/v2/portfolio"),
        ("GET", "/analytics/v2/receipts"),
        ("GET", "/analytics/v2/receipts/verify"),
        ("POST", "/analytics/v2/receipts/verify"),
        ("POST", "/research/audit"),
        ("GET", "/signed-prices/model"),
        ("GET", "/signed-prices/{symbol_name}"),
    ),
}
VERSIONS = tuple(sorted(RESPONSE_SCHEMAS))
if VERSIONS != tuple(sorted(ROUTES)):
    raise RuntimeError("every finance contract version declares both routes and schemas")


def header_value() -> str:
    return ",".join(f"{NAME}/{version}" for version in VERSIONS)


def components() -> dict:
    """The exact component bindings the analytics and signed-price bodies carry."""
    def load(name):
        return json.loads((_COMPONENTS / name / "source.json").read_text(encoding="utf-8"))
    return {"analytics": load("finance_v2"), "signed_price": load("puriq_verity")}


def descriptor(source_revision: str) -> dict:
    return {
        "schema": SCHEMA,
        "contract": NAME,
        "versions": list(VERSIONS),
        "response_schemas": {str(v): list(RESPONSE_SCHEMAS[v]) for v in VERSIONS},
        "header": HEADER,
        "components": components(),
        "source_revision": source_revision,
        "revision_role": "EVIDENCE_NOT_COMPATIBILITY_KEY",
        "read_only": True,
        "execution_enabled": False,
    }
