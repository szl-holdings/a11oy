# SPDX-License-Identifier: Apache-2.0
"""Regression guard for deferred route annotations in the assembled app."""

from __future__ import annotations


def test_assembled_openapi_schema_resolves_all_route_annotations() -> None:
    import serve

    # Rebuild rather than accepting a schema cached before a late route was added.
    serve.app.openapi_schema = None
    schema = serve.app.openapi()

    assert schema["openapi"]
    assert "/api/a11oy/v1/numerics/status" in schema["paths"]
    assert "/api/a11oy/v1/frontier/surfaces" in schema["paths"]
    assert "/api/a11oy/v1/compute/capabilities" in schema["paths"]
    assert "/api/a11oy/v1/ayllu/model-binding" in schema["paths"]
