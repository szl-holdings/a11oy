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


class EventuallyConsistentApi:
    def __init__(self, volume_snapshots, variable_snapshots) -> None:
        self.volume_snapshots = list(volume_snapshots)
        self.variable_snapshots = list(variable_snapshots)

    def get_space_runtime(self, *, repo_id: str):
        assert repo_id == config.CANONICAL_SPACE
        value = self.volume_snapshots.pop(0)
        return SimpleNamespace(volumes=value)

    def get_space_variables(self, *, repo_id: str):
        assert repo_id == config.CANONICAL_SPACE
        return self.variable_snapshots.pop(0)


def exact_variables() -> dict:
    return {
        name: SimpleNamespace(value=value)
        for name, value in config.SERIES_A_VARIABLES.items()
    }


def test_await_readback_accepts_bounded_eventual_consistency() -> None:
    api = EventuallyConsistentApi(
        [[], [], [volume(config.CANONICAL_BUCKET, "/data")]],
        [{}, exact_variables(), exact_variables()],
    )
    sleeps = []

    observed, attempts = config.await_readback(
        api,
        repo_id=config.CANONICAL_SPACE,
        bucket=config.CANONICAL_BUCKET,
        secret_names={config.CANONICAL_SIGNING_SECRET},
        attempts=3,
        delay_seconds=0,
        sleep=sleeps.append,
    )

    assert attempts == 3
    assert config.volume_record(observed[0])["source"] == config.CANONICAL_BUCKET
    assert sleeps == [0, 0]


def test_await_readback_still_fails_closed_at_bound() -> None:
    api = EventuallyConsistentApi([[], []], [{}, {}])

    with pytest.raises(config.RuntimeConfigError, match="after 2 attempts"):
        config.await_readback(
            api,
            repo_id=config.CANONICAL_SPACE,
            bucket=config.CANONICAL_BUCKET,
            secret_names={config.CANONICAL_SIGNING_SECRET},
            attempts=2,
            delay_seconds=0,
            sleep=lambda _seconds: None,
        )
