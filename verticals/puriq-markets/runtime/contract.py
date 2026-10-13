#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Versioned public read-API contract served by the canonical finance runtime.

Downstream projections (the SZLHOLDINGS/finance Space) bind to this contract,
not to the runtime's git revision, so an unrelated A11oy deploy cannot break
them. Bump the version, and keep serving the old one while consumers move,
whenever a response schema below or the meaning of an existing field changes
incompatibly. Additive fields keep the version. The source revision reported
beside the contract is evidence of what answered, never a compatibility key.
"""

NAME = "szl.finance.read-api"
HEADER = "X-SZL-Finance-Contract"
SCHEMA = "szl.finance.read-contract/v1"

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
VERSIONS = tuple(sorted(RESPONSE_SCHEMAS))


def header_value() -> str:
    return ",".join(f"{NAME}/{version}" for version in VERSIONS)


def descriptor(source_revision: str) -> dict:
    return {
        "schema": SCHEMA,
        "contract": NAME,
        "versions": list(VERSIONS),
        "response_schemas": {str(v): list(RESPONSE_SCHEMAS[v]) for v in VERSIONS},
        "header": HEADER,
        "source_revision": source_revision,
        "revision_role": "EVIDENCE_NOT_COMPATIBILITY_KEY",
        "read_only": True,
        "execution_enabled": False,
    }
