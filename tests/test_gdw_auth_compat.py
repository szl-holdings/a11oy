"""Adversarial coverage for digest-native GDW authentication compatibility."""

import hashlib
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import gdw_auth
from routers import gdw_frontier


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _credential(*, token=None, token_sha256=None, key_id="key-1", scopes=None):
    row = {
        "owner_id": "owner:alpha",
        "namespace": "a11oy",
        "key_id": key_id,
        "scopes": scopes or ["session:read"],
        "revoked": False,
    }
    if token is not None:
        row["token"] = token
    if token_sha256 is not None:
        row["token_sha256"] = token_sha256
    return row


def _registry(*credentials):
    return json.dumps({"version": 1, "credentials": list(credentials)})


def test_prehashed_credential_authenticates_without_retaining_raw_secret():
    secret = "digest-only-secret"
    registry = gdw_auth.parse_credential_registry(
        _registry(_credential(token_sha256=_digest(secret)))
    )

    principal = registry.authenticate(
        f"Bearer {secret}",
        namespace="a11oy",
        required_scopes=("session:read",),
    )

    assert principal.owner_id == "owner:alpha"
    assert secret not in repr(registry)
    assert secret not in repr(principal)
    assert all(
        isinstance(value.token_digest, bytes)
        for value in registry._credentials
    )


@pytest.mark.parametrize(
    "token_sha256",
    [
        "",
        "0" * 63,
        "0" * 65,
        "g" * 64,
        "A" * 64,
        hashlib.sha256(b"").hexdigest(),
        None,
        123,
    ],
)
def test_malformed_prehashed_credentials_fail_closed(token_sha256):
    row = _credential()
    row["token_sha256"] = token_sha256

    with pytest.raises(gdw_auth.AuthConfigurationError, match="token_sha256"):
        gdw_auth.parse_credential_registry(_registry(row))


def test_raw_and_prehashed_token_bindings_are_mutually_exclusive():
    with pytest.raises(gdw_auth.AuthConfigurationError, match="invalid shape"):
        gdw_auth.parse_credential_registry(
            _registry(
                _credential(
                    token="same-secret",
                    token_sha256=_digest("same-secret"),
                )
            )
        )


def test_raw_and_prehashed_duplicate_token_collision_is_rejected():
    secret = "same-secret"
    with pytest.raises(gdw_auth.AuthConfigurationError, match="duplicate token"):
        gdw_auth.parse_credential_registry(
            _registry(
                _credential(token=secret, key_id="raw-key"),
                _credential(
                    token_sha256=_digest(secret),
                    key_id="digest-key",
                ),
            )
        )


def test_legacy_principal_roles_map_to_existing_scopes_and_stable_keys():
    registry_json = json.dumps(
        {
            "owner:user": {
                "token_sha256": _digest("user-secret"),
                "roles": ["user"],
            },
            "owner:admin": {
                "token_sha256": _digest("admin-secret"),
                "roles": ["admin"],
            },
        }
    )
    first = gdw_auth.parse_legacy_principal_registry(
        registry_json,
        namespace="a11oy",
    )
    second = gdw_auth.parse_legacy_principal_registry(
        registry_json,
        namespace="a11oy",
    )

    user = first.authenticate(
        "Bearer user-secret",
        namespace="a11oy",
        required_scopes=("step:write",),
    )
    admin = first.authenticate(
        "Bearer admin-secret",
        namespace="a11oy",
        required_scopes=("integrity:global",),
    )
    repeated_admin = second.authenticate(
        "Bearer admin-secret",
        namespace="a11oy",
    )

    assert "integrity:global" not in user.scopes
    assert {
        "integrity:global",
        "integrity:read",
        "step:write",
    }.issubset(
        admin.scopes
    )
    assert "effects:recover" not in admin.scopes
    assert admin.key_id == repeated_admin.key_id
    with pytest.raises(gdw_auth.AuthenticationError) as exc_info:
        first.authenticate(
            "Bearer user-secret",
            namespace="a11oy",
            required_scopes=("integrity:global",),
        )
    assert exc_info.value.code == "missing_scopes"
    with pytest.raises(gdw_auth.AuthenticationError) as recovery_exc:
        first.authenticate(
            "Bearer admin-secret",
            namespace="a11oy",
            required_scopes=("effects:recover",),
        )
    assert recovery_exc.value.code == "missing_scopes"


def test_legacy_principal_registry_rejects_digest_collisions():
    token_sha256 = _digest("shared-secret")
    with pytest.raises(gdw_auth.AuthConfigurationError, match="duplicate token"):
        gdw_auth.parse_legacy_principal_registry(
            json.dumps(
                {
                    "owner:one": {
                        "token_sha256": token_sha256,
                        "roles": ["user"],
                    },
                    "owner:two": {
                        "token_sha256": token_sha256,
                        "roles": ["admin"],
                    },
                }
            ),
            namespace="a11oy",
        )


def test_credential_registry_and_principal_registry_cannot_be_combined():
    with pytest.raises(
        gdw_auth.AuthConfigurationError,
        match="cannot be configured together",
    ):
        gdw_auth.load_credential_registry(
            _registry(_credential(token="raw-secret")),
            principal_registry_json=json.dumps(
                {
                    "owner:legacy": {
                        "token_sha256": _digest("legacy-secret"),
                        "roles": ["user"],
                    }
                }
            ),
            principal_registry_namespace="a11oy",
        )


@pytest.mark.parametrize(
    "legacy_kwargs",
    [
        {"legacy_owner_id": "owner:stale"},
        {"legacy_namespace": "a11oy"},
        {"legacy_key_id": "stale-key"},
        {"legacy_scopes": ("session:read",)},
    ],
)
def test_registry_rejects_every_stale_legacy_binding(legacy_kwargs):
    with pytest.raises(
        gdw_auth.AuthConfigurationError,
        match="cannot be configured together",
    ):
        gdw_auth.load_credential_registry(
            _registry(_credential(token="raw-secret")),
            **legacy_kwargs,
        )


@pytest.mark.parametrize(
    "legacy_kwargs",
    [
        {"legacy_owner_id": "owner:stale"},
        {"legacy_namespace": "a11oy"},
        {"legacy_key_id": "stale-key"},
        {"legacy_scopes": ("session:read",)},
    ],
)
def test_unenabled_legacy_rejects_every_partial_binding(legacy_kwargs):
    with pytest.raises(
        gdw_auth.AuthConfigurationError,
        match="not enabled",
    ):
        gdw_auth.load_credential_registry(None, **legacy_kwargs)


def test_global_integrity_requires_global_scope_and_preserves_owner_view(
    monkeypatch,
):
    registry = gdw_auth.parse_credential_registry(
        _registry(
            _credential(
                token="owner-secret",
                key_id="owner-key",
                scopes=["integrity:read"],
            ),
            _credential(
                token_sha256=_digest("admin-secret"),
                key_id="admin-key",
                scopes=["integrity:global"],
            ),
            _credential(
                token_sha256=_digest("recovery-secret"),
                key_id="recovery-key",
                scopes=["effects:recover", "integrity:global"],
            ),
        )
    )

    workspace_recoveries = []

    class Workspace:
        database_generation_id = "a" * 32

        def integrity(self, *, global_scope=False):
            return {
                "scope": "global" if global_scope else "owner",
                "ok": True,
                "database_generation_id": "a" * 32,
            }

        def recover_retry_scheduled_effects(
            self,
            *,
            recovery_id,
            credential_key_id,
            expected_source_revision,
            expected_database_generation_id,
            governance,
            limit,
        ):
            assert limit == 100
            assert recovery_id == "auth-compat-recovery"
            assert credential_key_id == "recovery-key"
            assert expected_source_revision == "b" * 40
            assert expected_database_generation_id == "a" * 32
            assert governance["decision"] == "ALLOW"
            assert governance["binding"]["recovery_id"] == recovery_id
            workspace_recoveries.append(recovery_id)
            return {
                "schema": "szl.gdw.transient-effect-recovery/v2",
                "status": "NO_ELIGIBLE_EFFECTS",
                "recovery_id": recovery_id,
                "source_revision": expected_source_revision,
                "requested_limit": limit,
                "failure_class": "hf-hard-link-enotsup/v1",
                "database_generation_id": "a" * 32,
                "inspected_pending_effects": 0,
                "eligible_effects": 0,
                "rescheduled_effects": 0,
                "attempts_before": 0,
                "attempts_after": 0,
                "selection_sha256": hashlib.sha256(b"[]").hexdigest(),
                "sqlite_integrity": "ok",
                "claimed_effects": 0,
                "dead_letter_effects": 0,
                "invalid_effect_bindings": 0,
                "invalid_exported_artifacts": 0,
                "invalid_recovery_audits": 0,
                "audit_receipt": {
                    "schema": (
                        "szl.gdw.transient-effect-recovery-receipt/v1"
                    ),
                    "receipt_sha256": "b" * 64,
                },
                "replayed": False,
            }

    monkeypatch.setattr(gdw_frontier, "_credential_registry", lambda: registry)
    monkeypatch.setattr(gdw_frontier, "_workspace", lambda principal: Workspace())
    monkeypatch.setattr(gdw_frontier, "_require_write_ready", lambda ns: None)
    monkeypatch.setattr(
        gdw_frontier,
        "_require_transient_recovery_runtime",
        lambda ns, revision: "a" * 32,
    )
    monkeypatch.setattr(
        gdw_frontier,
        "_canonical_policy_evaluate",
        lambda action: {
            "decision": "allow",
            "gate": "ThresholdPolicySeverity",
            "receipt_hash": "c" * 64,
            "receipt_signed": True,
            "receipts_in_eq_out": True,
        },
    )
    monkeypatch.setattr(
        gdw_frontier,
        "drain_once",
        lambda limit: {
            "attempted": 0,
            "exported": 0,
            "failed": 0,
            "pending_effects": 0,
            "legacy_pending_proofs": 0,
            "sqlite_integrity": "ok",
            "errors": [],
        },
    )
    app = FastAPI()
    gdw_frontier.register(app)

    with TestClient(app) as client:
        owner = client.get(
            "/api/a11oy/v1/gdw/integrity",
            headers={"Authorization": "Bearer owner-secret"},
        )
        denied = client.get(
            "/api/a11oy/v1/gdw/integrity/global",
            headers={"Authorization": "Bearer owner-secret"},
        )
        global_view = client.get(
            "/api/a11oy/v1/gdw/integrity/global",
            headers={"Authorization": "Bearer admin-secret"},
        )
        denied_drain = client.post(
            "/api/a11oy/v1/gdw/drain",
            headers={"Authorization": "Bearer owner-secret"},
        )
        first_drain = client.post(
            "/api/a11oy/v1/gdw/drain",
            headers={"Authorization": "Bearer admin-secret"},
        )
        repeated_drain = client.post(
            "/api/a11oy/v1/gdw/drain",
            headers={"Authorization": "Bearer admin-secret"},
        )
        denied_recovery = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer admin-secret",
                "X-Expected-Source-Revision": "b" * 40,
            },
        )
        recovery = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "auth-compat-recovery",
            },
        )
        missing_idempotency = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
            },
        )
        malformed_idempotency = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "not canonical",
            },
        )
        zero_limit = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects?limit=0",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "zero-limit",
            },
        )
        excessive_limit = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects?limit=1001",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "excessive-limit",
            },
        )

    assert owner.status_code == 200
    assert owner.json()["scope"] == "owner"
    assert denied.status_code == 403
    assert denied.json()["detail"] == "missing_scopes"
    assert global_view.status_code == 200
    assert global_view.json()["scope"] == "global"
    assert denied_drain.status_code == 403
    assert first_drain.status_code == 200
    assert first_drain.json() == repeated_drain.json()
    assert first_drain.json()["schema"] == "szl.gdw.drain-report/v1"
    assert denied_recovery.status_code == 403
    assert denied_recovery.json()["detail"] == "missing_scopes"
    assert recovery.status_code == 200
    assert recovery.json()["schema"] == (
        "szl.gdw.transient-effect-recovery/v2"
    )
    assert recovery.json()["status"] == "NO_ELIGIBLE_EFFECTS"
    assert missing_idempotency.status_code == 422
    assert malformed_idempotency.status_code == 422
    assert zero_limit.status_code == 422
    assert excessive_limit.status_code == 422

    class StaleWorkspace(Workspace):
        database_generation_id = "c" * 32

    monkeypatch.setattr(
        gdw_frontier,
        "_workspace",
        lambda principal: StaleWorkspace(),
    )
    with TestClient(app) as client:
        stale_generation = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "stale-generation",
            },
        )
    assert stale_generation.status_code == 503
    assert stale_generation.json()["detail"] == (
        "GDW recovery database generation changed"
    )

    monkeypatch.setattr(gdw_frontier, "_workspace", lambda principal: Workspace())
    monkeypatch.setattr(
        gdw_frontier,
        "_canonical_policy_evaluate",
        lambda action: {
            "decision": "deny",
            "gate": "ThresholdPolicySeverity",
            "receipt_hash": "d" * 64,
            "receipt_signed": True,
            "receipts_in_eq_out": True,
        },
    )
    with TestClient(app) as client:
        denied_by_policy = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "policy-denied-recovery",
            },
        )
    assert denied_by_policy.status_code == 403
    assert denied_by_policy.json()["detail"] == (
        "GDW recovery denied by canonical policy"
    )

    def unavailable(_action):
        raise RuntimeError("policy gateway unavailable")

    monkeypatch.setattr(
        gdw_frontier,
        "_canonical_policy_evaluate",
        unavailable,
    )
    with TestClient(app) as client:
        unavailable_policy = client.post(
            "/api/a11oy/v1/gdw/recovery/transient-effects",
            headers={
                "Authorization": "Bearer recovery-secret",
                "X-Expected-Source-Revision": "b" * 40,
                "Idempotency-Key": "policy-unavailable-recovery",
            },
        )
    assert unavailable_policy.status_code == 503
    assert unavailable_policy.json()["detail"] == (
        "GDW recovery canonical policy unavailable"
    )
    assert workspace_recoveries == ["auth-compat-recovery"]


def test_transient_recovery_runtime_requires_exact_source_and_storage(
    monkeypatch,
):
    generation = "a" * 32
    source_sha = "b" * 40
    monkeypatch.setenv("SZL_GIT_SHA", source_sha)
    monkeypatch.setattr(gdw_frontier, "_governance_ready", lambda: True)
    monkeypatch.setattr(
        gdw_frontier,
        "_canonical_policy_ready",
        lambda: True,
    )
    runtime = {
        "startup_state": "READY",
        "evidence_label": "VERIFIED",
        "storage": {
            "persistence_required": True,
            "mount_verified": True,
            "journal_mode_requested": "DELETE",
            "journal_mode_observed": "DELETE",
            "synchronous_requested": "FULL",
            "synchronous_observed": 2,
            "sqlite_integrity": "ok",
            "proof_export_mode": "outbox",
            "schema_version": gdw_frontier.GDWWorkspace.schema_version(),
            "database_generation_id": generation,
        },
        "drain": {
            "enabled": True,
            "running": True,
            "last_outcome": "RETRY_SCHEDULED",
        },
    }
    monkeypatch.setattr(
        gdw_frontier,
        "runtime_health",
        lambda: runtime,
    )

    assert gdw_frontier._require_transient_recovery_runtime(
        "a11oy",
        source_sha,
    ) == generation
    with pytest.raises(HTTPException) as mismatch:
        gdw_frontier._require_transient_recovery_runtime(
            "a11oy",
            "c" * 40,
        )
    assert mismatch.value.status_code == 409

    runtime["storage"]["sqlite_integrity"] = "corrupt"
    with pytest.raises(HTTPException) as unavailable:
        gdw_frontier._require_transient_recovery_runtime(
            "a11oy",
            source_sha,
        )
    assert unavailable.value.status_code == 503
