from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
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
    registry_text = config.principal_registry_value(token)
    registry = __import__("json").loads(registry_text)

    assert registry[config.PRINCIPAL_ID]["roles"] == ["admin", "user"]
    assert token not in registry_text
    assert config.PRINCIPAL_REGISTRY_SECRET not in variables
    assert variables["GDW_SQLITE_JOURNAL"] == "DELETE"
    assert variables["GDW_DB_PATH"].startswith("/data/")
    assert variables["GDW_PRODUCTION_MODE"] == "1"
    assert variables["GDW_REQUIRE_PERSISTENT_STORAGE"] == "1"
    assert variables["GDW_REQUIRED_MOUNT"] == "/data"
    assert variables["GDW_OUTBOX_ENABLED"] == "1"
    assert variables["GDW_OWNER_MAX_PENDING_EFFECTS"] == "2000"
    assert variables["GDW_EFFECT_MAX_ATTEMPTS"] == "20"
    assert variables["GDW_POLICY_ORIGIN"].startswith("https://")


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


def test_principal_registry_is_converged_as_digest_only_secret() -> None:
    token = "operator-token-" + ("x" * 48)
    calls: list[dict[str, object]] = []
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: calls.append(kwargs),
        get_space_secrets=lambda **kwargs: [config.PRINCIPAL_REGISTRY_SECRET],
    )

    assert config.converge_principal_registry(
        api,
        repo_id=config.CANONICAL_SPACE,
        current_variables={},
        current_secret_names=set(),
        operator_token=token,
    ) == {config.PRINCIPAL_REGISTRY_SECRET}
    assert len(calls) == 1
    assert calls[0]["key"] == config.PRINCIPAL_REGISTRY_SECRET
    registry_text = str(calls[0]["value"])
    assert token not in registry_text
    assert json.loads(registry_text) == {
        config.PRINCIPAL_ID: {
            "roles": ["admin", "user"],
            "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        }
    }


def test_principal_registry_convergence_fails_closed() -> None:
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: None,
        get_space_secrets=lambda **kwargs: [],
    )
    with pytest.raises(config.RuntimeConfigError, match="did not converge"):
        config.converge_principal_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables={},
            current_secret_names=set(),
            operator_token="x" * 48,
        )
    with pytest.raises(config.RuntimeConfigError, match="collides"):
        config.converge_principal_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables={
                config.PRINCIPAL_REGISTRY_SECRET: SimpleNamespace(value="bad")
            },
            current_secret_names=set(),
            operator_token="x" * 48,
        )


@pytest.mark.parametrize("location", ["variable", "secret"])
def test_competing_credential_registry_blocks_before_mutation(location: str) -> None:
    calls: list[dict[str, object]] = []
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: calls.append(kwargs),
        get_space_secrets=lambda **kwargs: [config.PRINCIPAL_REGISTRY_SECRET],
    )
    variables = (
        {"GDW_CREDENTIALS_JSON": SimpleNamespace(value="hidden")}
        if location == "variable"
        else {}
    )
    secret_names = {"GDW_CREDENTIALS_JSON"} if location == "secret" else set()

    with pytest.raises(config.RuntimeConfigError, match="competing"):
        config.converge_principal_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables=variables,
            current_secret_names=secret_names,
            operator_token="x" * 48,
        )
    assert calls == []


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
