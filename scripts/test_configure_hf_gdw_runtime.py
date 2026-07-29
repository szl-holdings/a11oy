from __future__ import annotations

import importlib.util
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


def test_principal_registry_converges_digest_without_bearer_material() -> None:
    calls = []
    api = SimpleNamespace(
        add_space_secret=lambda **kwargs: calls.append(kwargs),
    )
    token = "operator-token-" + ("x" * 40)
    config.converge_principal_registry(
        api,
        repo_id=config.CANONICAL_SPACE,
        current_variables={},
        operator_token=token,
    )

    assert len(calls) == 1
    written = calls[0]
    assert written["key"] == config.PRINCIPAL_REGISTRY_SECRET
    assert token not in written["value"]
    assert __import__("json").loads(written["value"])[config.PRINCIPAL_ID][
        "token_sha256"
    ] == __import__("hashlib").sha256(token.encode("utf-8")).hexdigest()


def test_principal_registry_rejects_variable_collision() -> None:
    api = SimpleNamespace(add_space_secret=lambda **kwargs: None)
    with pytest.raises(config.RuntimeConfigError, match="collides"):
        config.converge_principal_registry(
            api,
            repo_id=config.CANONICAL_SPACE,
            current_variables={
                config.PRINCIPAL_REGISTRY_SECRET: SimpleNamespace(value="bad")
            },
            operator_token="x" * 48,
        )


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
