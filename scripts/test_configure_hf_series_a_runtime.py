from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).with_name("configure_hf_series_a_runtime.py")
SPEC = importlib.util.spec_from_file_location(
    "configure_hf_series_a_runtime", SCRIPT
)
assert SPEC and SPEC.loader
config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config)


def volume(
    source: str,
    mount_path: str,
    *,
    volume_type: str = "bucket",
    read_only: bool = False,
):
    return SimpleNamespace(
        type=volume_type,
        source=source,
        mount_path=mount_path,
        read_only=read_only,
        path=None,
        revision=None,
    )


def test_plan_volumes_preserves_existing_and_adds_canonical_bucket() -> None:
    existing = volume("SZLHOLDINGS/model", "/models", volume_type="model", read_only=True)

    planned, changed = config.plan_volumes([existing])

    assert changed is True
    assert planned[0] == config.volume_record(existing)
    assert planned[1] == {
        "type": "bucket",
        "source": config.CANONICAL_BUCKET,
        "mount_path": "/data",
        "read_only": False,
        "path": None,
        "revision": None,
    }


def test_plan_volumes_is_idempotent_for_exact_read_write_mount() -> None:
    existing = volume(config.CANONICAL_BUCKET, "/data")

    planned, changed = config.plan_volumes([existing])

    assert changed is False
    assert planned == [config.volume_record(existing)]


@pytest.mark.parametrize(
    "existing",
    [
        volume("SZLHOLDINGS/other", "/data"),
        volume(config.CANONICAL_BUCKET, "/data", read_only=True),
        volume(
            config.CANONICAL_BUCKET,
            "/data",
            volume_type="dataset",
            read_only=True,
        ),
    ],
)
def test_plan_volumes_fails_closed_on_mount_conflict(existing) -> None:
    with pytest.raises(config.RuntimeConfigError, match="conflicts"):
        config.plan_volumes([existing])


def test_plan_variables_reports_only_drift_without_secret_values() -> None:
    desired = {
        "A11OY_REQUIRE_PERSISTENT_SIGNING": "1",
        "A11OY_REQUIRE_PERSISTENT_STORAGE": "1",
    }
    current = {
        "A11OY_REQUIRE_PERSISTENT_SIGNING": SimpleNamespace(value="1"),
    }

    changes = config.plan_variables(
        current,
        {config.CANONICAL_SIGNING_SECRET},
        desired,
    )

    assert changes == {"A11OY_REQUIRE_PERSISTENT_STORAGE": "1"}
    assert config.CANONICAL_SIGNING_SECRET not in changes


def test_plan_variables_fails_closed_on_secret_variable_collision() -> None:
    with pytest.raises(config.RuntimeConfigError, match="collide"):
        config.plan_variables(
            {},
            {"A11OY_REQUIRE_PERSISTENT_STORAGE"},
            {"A11OY_REQUIRE_PERSISTENT_STORAGE": "1"},
        )
