from __future__ import annotations

import hashlib
import json

from routers import gdw_frontier


def test_principal_registry_accepts_namespace_when_legacy_auth_is_disabled(
    monkeypatch,
) -> None:
    token = "gdw-principal-regression-token-32-bytes-minimum"
    principal_registry = {
        "gdw-operator": {
            "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            "roles": ["admin", "user"],
        }
    }

    monkeypatch.delenv("GDW_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("GDW_PRINCIPALS_JSON", json.dumps(principal_registry))
    monkeypatch.setenv("GDW_NAMESPACE", "a11oy")
    monkeypatch.delenv("GDW_ALLOW_LEGACY_AUTH", raising=False)
    monkeypatch.delenv("GDW_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("GDW_OWNER_ID", raising=False)
    monkeypatch.delenv("GDW_LEGACY_SCOPES", raising=False)
    monkeypatch.setattr(gdw_frontier, "_AUTH_FINGERPRINT", None)
    monkeypatch.setattr(gdw_frontier, "_AUTH_REGISTRY", None)

    registry = gdw_frontier._credential_registry()

    assert registry.credential_count == 1
