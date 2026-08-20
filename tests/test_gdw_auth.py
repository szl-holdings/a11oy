"""Focused contract tests for stable GDW principal authentication."""

import dataclasses
import json

import pytest

import gdw_auth


def registry_json(credentials):
    return json.dumps({"version": 1, "credentials": credentials})


def credential(
    *,
    token="secret-alpha",
    owner_id="owner:alpha",
    namespace="a11oy",
    key_id="key-2026-01",
    scopes=None,
    revoked=False,
):
    return {
        "owner_id": owner_id,
        "namespace": namespace,
        "key_id": key_id,
        "token": token,
        "scopes": ["gdw:read", "gdw:write"] if scopes is None else scopes,
        "revoked": revoked,
    }


def test_authentication_returns_immutable_principal_without_token_material():
    registry = gdw_auth.parse_credential_registry(registry_json([credential()]))

    principal = gdw_auth.authenticate_bearer(
        "Bearer secret-alpha",
        registry,
        namespace="a11oy",
        required_scopes=("gdw:write",),
    )

    assert principal == gdw_auth.Principal(
        owner_id="owner:alpha",
        namespace="a11oy",
        key_id="key-2026-01",
        scopes=("gdw:read", "gdw:write"),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        principal.owner_id = "owner:other"
    assert "secret-alpha" not in repr(registry)
    assert "secret-alpha" not in repr(principal)


def test_owner_identity_is_stable_across_key_rotation():
    registry = gdw_auth.parse_credential_registry(
        registry_json(
            [
                credential(token="rotated-old", key_id="key-2026-01"),
                credential(token="rotated-new", key_id="key-2026-02"),
            ]
        )
    )

    old = registry.authenticate("Bearer rotated-old", namespace="a11oy")
    new = registry.authenticate("Bearer rotated-new", namespace="a11oy")

    assert old.owner_id == new.owner_id == "owner:alpha"
    assert old.namespace == new.namespace == "a11oy"
    assert old.key_id != new.key_id


def test_matching_scans_every_fixed_length_digest(monkeypatch):
    registry = gdw_auth.parse_credential_registry(
        registry_json(
            [
                credential(token="first-token", key_id="key-1"),
                credential(token="second-token", key_id="key-2"),
                credential(token="third-token", key_id="key-3"),
            ]
        )
    )
    calls = []
    original = gdw_auth.hmac.compare_digest

    def observed(left, right):
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(gdw_auth.hmac, "compare_digest", observed)
    principal = registry.authenticate("Bearer first-token", namespace="a11oy")

    assert principal.key_id == "key-1"
    assert len(calls) == registry.credential_count == 3
    assert all(len(left) == len(right) == 32 for left, right in calls)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{",
        "[]",
        '{"version":1,"credentials":[]}',
        '{"version":2,"credentials":[{}]}',
        '{"version":1,"version":1,"credentials":[{}]}',
        '{"version":1,"credentials":"not-an-array"}',
    ],
)
def test_malformed_and_empty_registries_are_rejected(raw):
    with pytest.raises(gdw_auth.AuthConfigurationError):
        gdw_auth.parse_credential_registry(raw)


def test_duplicate_tokens_are_rejected_without_echoing_the_token():
    duplicate = "duplicate-secret"
    raw = registry_json(
        [
            credential(token=duplicate, key_id="key-1"),
            credential(token=duplicate, key_id="key-2"),
        ]
    )

    with pytest.raises(gdw_auth.AuthConfigurationError) as exc_info:
        gdw_auth.parse_credential_registry(raw)

    assert "duplicate token" in str(exc_info.value)
    assert duplicate not in str(exc_info.value)
    assert duplicate not in repr(exc_info.value)


def test_duplicate_namespace_key_id_and_duplicate_scopes_are_rejected():
    with pytest.raises(gdw_auth.AuthConfigurationError, match="namespace/key_id"):
        gdw_auth.parse_credential_registry(
            registry_json(
                [
                    credential(token="one"),
                    credential(token="two"),
                ]
            )
        )
    with pytest.raises(gdw_auth.AuthConfigurationError, match="must not be empty"):
        gdw_auth.parse_credential_registry(
            registry_json([credential(scopes=[])])
        )
    with pytest.raises(gdw_auth.AuthConfigurationError, match="duplicates"):
        gdw_auth.parse_credential_registry(
            registry_json(
                [
                    credential(
                        scopes=["gdw:read", "gdw:read"],
                    )
                ]
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("owner_id", "Owner:Alpha"),
        ("owner_id", ""),
        ("namespace", "foreign namespace"),
        ("key_id", "../key"),
        ("scopes", ["GDW:read"]),
    ],
)
def test_registry_rejects_noncanonical_identifiers(field, value):
    row = credential()
    row[field] = value
    with pytest.raises(gdw_auth.AuthConfigurationError, match="canonical"):
        gdw_auth.parse_credential_registry(registry_json([row]))


def test_revoked_key_is_rejected():
    registry = gdw_auth.parse_credential_registry(
        registry_json([credential(revoked=True)])
    )

    with pytest.raises(gdw_auth.AuthenticationError) as exc_info:
        registry.authenticate("Bearer secret-alpha", namespace="a11oy")

    assert exc_info.value.code == "credential_revoked"
    assert "secret-alpha" not in str(exc_info.value)


def test_foreign_namespace_is_rejected():
    registry = gdw_auth.parse_credential_registry(registry_json([credential()]))

    with pytest.raises(gdw_auth.AuthenticationError) as exc_info:
        registry.authenticate("Bearer secret-alpha", namespace="other")

    assert exc_info.value.code == "foreign_namespace"


def test_missing_required_scopes_are_rejected():
    registry = gdw_auth.parse_credential_registry(
        registry_json([credential(scopes=["gdw:read"])])
    )

    with pytest.raises(gdw_auth.AuthenticationError) as exc_info:
        registry.authenticate(
            "Bearer secret-alpha",
            namespace="a11oy",
            required_scopes=("gdw:write",),
        )

    assert exc_info.value.code == "missing_scopes"


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic secret-alpha",
        "Bearer",
        "Bearer ",
        "Bearer secret-alpha extra",
        "Bearer secret-alpha\n",
    ],
)
def test_missing_or_malformed_bearer_headers_are_rejected(authorization):
    registry = gdw_auth.parse_credential_registry(registry_json([credential()]))
    with pytest.raises(gdw_auth.AuthenticationError):
        registry.authenticate(authorization, namespace="a11oy")


def test_invalid_token_error_never_echoes_token():
    registry = gdw_auth.parse_credential_registry(registry_json([credential()]))
    supplied = "not-the-secret"

    with pytest.raises(gdw_auth.AuthenticationError) as exc_info:
        registry.authenticate(f"Bearer {supplied}", namespace="a11oy")

    assert exc_info.value.code == "invalid_bearer_token"
    assert supplied not in str(exc_info.value)
    assert supplied not in repr(exc_info.value)


def test_legacy_mode_requires_explicit_enablement_and_identity_binding():
    with pytest.raises(gdw_auth.AuthConfigurationError, match="not enabled"):
        gdw_auth.load_credential_registry(
            None,
            legacy_token="legacy-secret",
            legacy_owner_id="owner:legacy",
            legacy_namespace="a11oy",
        )
    with pytest.raises(gdw_auth.AuthConfigurationError, match="requires"):
        gdw_auth.load_credential_registry(
            None,
            legacy_enabled=True,
            legacy_token="legacy-secret",
            legacy_scopes=("gdw:write",),
        )
    with pytest.raises(gdw_auth.AuthConfigurationError, match="must not be empty"):
        gdw_auth.load_credential_registry(
            None,
            legacy_enabled=True,
            legacy_token="legacy-secret",
            legacy_owner_id="owner:legacy",
            legacy_namespace="a11oy",
        )


def test_explicit_legacy_mode_returns_bound_principal():
    registry = gdw_auth.load_credential_registry(
        None,
        legacy_enabled=True,
        legacy_token="legacy-secret",
        legacy_owner_id="owner:legacy",
        legacy_namespace="a11oy",
        legacy_key_id="legacy-2026",
        legacy_scopes=("gdw:read", "gdw:write"),
    )

    principal = registry.authenticate(
        "Bearer legacy-secret",
        namespace="a11oy",
        required_scopes=("gdw:write",),
    )

    assert principal == gdw_auth.Principal(
        owner_id="owner:legacy",
        namespace="a11oy",
        key_id="legacy-2026",
        scopes=("gdw:read", "gdw:write"),
    )


def test_registry_and_legacy_configuration_cannot_be_combined():
    with pytest.raises(gdw_auth.AuthConfigurationError, match="cannot be configured"):
        gdw_auth.load_credential_registry(
            registry_json([credential()]),
            legacy_enabled=True,
            legacy_token="legacy-secret",
            legacy_owner_id="owner:legacy",
            legacy_namespace="a11oy",
            legacy_scopes=("gdw:write",),
        )
