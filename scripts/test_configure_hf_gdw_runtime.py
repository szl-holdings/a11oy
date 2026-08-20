from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).with_name("configure_hf_gdw_runtime.py")
SPEC = importlib.util.spec_from_file_location("configure_hf_gdw_runtime", SCRIPT)
assert SPEC and SPEC.loader
config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config)


def test_desired_variables_digest_token_without_recording_it() -> None:
    token = "x" * 48
    variables = config.desired_variables(token)
    registry_text = config.credential_registry_value(token)
    registry = __import__("json").loads(registry_text)

    assert registry == {
        "version": 1,
        "credentials": [
            {
                "owner_id": config.PRINCIPAL_ID,
                "namespace": "a11oy",
                "key_id": config.CREDENTIAL_KEY_ID,
                "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "scopes": config.OPERATOR_SCOPES,
                "revoked": False,
            }
        ],
    }
    assert "effects:recover" in registry["credentials"][0]["scopes"]
    assert token not in registry_text
    assert config.CREDENTIAL_REGISTRY_SECRET not in variables
    assert variables["GDW_SQLITE_JOURNAL"] == "DELETE"
    assert variables["GDW_DB_PATH"].startswith("/data/")
    assert variables["GDW_PRODUCTION_MODE"] == "1"
    assert variables["GDW_REQUIRE_PERSISTENT_STORAGE"] == "1"
    assert variables["GDW_REQUIRED_MOUNT"] == "/data"
    assert variables["GDW_OUTBOX_ENABLED"] == "1"
    assert variables["GDW_OWNER_MAX_PENDING_EFFECTS"] == "2000"
    assert variables["GDW_EFFECT_MAX_ATTEMPTS"] == "20"
    assert variables["GDW_POLICY_ORIGIN"] == "http://127.0.0.1:7860"


def test_desired_variables_rejects_weak_operator_token() -> None:
    with pytest.raises(config.RuntimeConfigError, match="at least 32"):
        config.desired_variables("too-short")


def test_plan_variables_reports_only_drift_and_rejects_collisions() -> None:
    desired = {"GDW_DB_PATH": "/data/gdw.sqlite3", "GDW_SQLITE_JOURNAL": "DELETE"}
    current = {"GDW_SQLITE_JOURNAL": SimpleNamespace(value="DELETE")}
    assert config.plan_variables(current, set(), desired) == {
        "GDW_DB_PATH": "/data/gdw.sqlite3"
    }
    with pytest.raises(config.RuntimeConfigError, match="collide"):
        config.plan_variables({}, {"GDW_DB_PATH"}, desired)


def test_credential_registry_converges_explicit_scope_without_bearer_material() -> None:
    token = "operator-token-" + ("x" * 48)
    calls: list[dict[str, object]] = []
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: calls.append(kwargs),
        delete_space_secret=lambda **kwargs: calls.append(kwargs),
        get_space_secrets=lambda **kwargs: [config.CREDENTIAL_REGISTRY_SECRET],
    )

    secret_names, changed = config.converge_credential_registry(
        api,
        repo_id=config.CANONICAL_SPACE,
        current_variables={},
        secret_names=set(),
        operator_token=token,
    )
    assert secret_names == {config.CREDENTIAL_REGISTRY_SECRET}
    assert changed is True
    assert len(calls) == 1
    assert calls[0]["key"] == config.CREDENTIAL_REGISTRY_SECRET
    registry_text = str(calls[0]["value"])
    assert token not in registry_text
    credential = json.loads(registry_text)["credentials"][0]
    assert credential["owner_id"] == config.PRINCIPAL_ID
    assert credential["scopes"] == config.OPERATOR_SCOPES
    assert credential["token_sha256"] == hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def test_credential_registry_convergence_fails_closed() -> None:
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: None,
        delete_space_secret=lambda **kwargs: None,
        get_space_secrets=lambda **kwargs: [],
    )
    with pytest.raises(config.RuntimeConfigError, match="did not converge"):
        config.converge_credential_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables={},
        secret_names=set(),
            operator_token="x" * 48,
        )
    with pytest.raises(config.RuntimeConfigError, match="collides"):
        config.converge_credential_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables={
                config.PRINCIPAL_REGISTRY_SECRET: SimpleNamespace(value="bad")
            },
            secret_names=set(),
            operator_token="x" * 48,
        )


@pytest.mark.parametrize(
    "variable_name",
    [config.CREDENTIAL_REGISTRY_SECRET, config.PRINCIPAL_REGISTRY_SECRET],
)
def test_registry_variable_collisions_block_before_mutation(
    variable_name: str,
) -> None:
    calls: list[dict[str, object]] = []
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: calls.append(kwargs),
        delete_space_secret=lambda **kwargs: calls.append(kwargs),
        get_space_secrets=lambda **kwargs: [config.CREDENTIAL_REGISTRY_SECRET],
    )
    variables = {variable_name: SimpleNamespace(value="hidden")}
    secret_names = set()

    with pytest.raises(config.RuntimeConfigError, match="collides"):
        config.converge_credential_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables=variables,
            secret_names=secret_names,
            operator_token="x" * 48,
        )
    assert calls == []


def test_managed_variable_secret_collision_blocks_before_auth_mutation(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    api = SimpleNamespace(
        space_info=lambda **kwargs: SimpleNamespace(
            runtime=SimpleNamespace(
                volumes=[
                    SimpleNamespace(
                        type="bucket",
                        source="SZLHOLDINGS/szl-evidence",
                        mount_path="/data",
                        read_only=False,
                    )
                ]
            )
        ),
        get_space_secrets=lambda **kwargs: ["GDW_DB_PATH"],
        get_space_variables=lambda **kwargs: {},
        add_space_secret=lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(HfApi=lambda **kwargs: api),
    )

    with pytest.raises(config.RuntimeConfigError, match="collide"):
        config.configure(
            repo_id=config.CANONICAL_SPACE,
            hf_token="hf-control-token",
            operator_token="x" * 48,
        )
    assert calls == []


def test_legacy_registry_is_retired_before_explicit_registry_is_published() -> None:
    calls: list[tuple[str, str]] = []
    secret_names = {config.PRINCIPAL_REGISTRY_SECRET}

    def delete_space_secret(*, repo_id, key):
        del repo_id
        calls.append(("delete", key))
        secret_names.remove(key)

    def add_space_secret(*, repo_id, key, value, description):
        del repo_id, value, description
        calls.append(("add", key))
        secret_names.add(key)

    api = SimpleNamespace(
        add_space_secret=add_space_secret,
        delete_space_secret=delete_space_secret,
        get_space_secrets=lambda **kwargs: sorted(secret_names),
    )
    converged, changed = config.converge_credential_registry(
        api,
        repo_id=config.CANONICAL_SPACE,
        current_variables={},
        secret_names={config.PRINCIPAL_REGISTRY_SECRET},
        operator_token="x" * 48,
    )

    assert converged == {config.CREDENTIAL_REGISTRY_SECRET}
    assert changed is True
    assert calls == [
        ("delete", config.PRINCIPAL_REGISTRY_SECRET),
        ("add", config.CREDENTIAL_REGISTRY_SECRET),
    ]


def test_require_data_mount_is_fail_closed() -> None:
    good = SimpleNamespace(
        runtime=SimpleNamespace(
            volumes=[
                SimpleNamespace(
                    type="bucket",
                    source="SZLHOLDINGS/szl-evidence",
                    mount_path="/data",
                    read_only=False,
                )
            ]
        )
    )
    api = SimpleNamespace(space_info=lambda *, repo_id: good)
    assert config.require_data_mount(api, repo_id=config.CANONICAL_SPACE)[
        "mount_path"
    ] == "/data"

    missing = SimpleNamespace(runtime=SimpleNamespace(volumes=[]))
    api = SimpleNamespace(space_info=lambda *, repo_id: missing)
    with pytest.raises(config.RuntimeConfigError, match="read-write"):
        config.require_data_mount(api, repo_id=config.CANONICAL_SPACE)
