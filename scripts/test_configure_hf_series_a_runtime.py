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

    def space_info(self, *, repo_id: str):
        assert repo_id == config.CANONICAL_SPACE
        value = self.volume_snapshots.pop(0)
        return SimpleNamespace(runtime=SimpleNamespace(volumes=value))

    def get_space_variables(self, *, repo_id: str):
        assert repo_id == config.CANONICAL_SPACE
        return self.variable_snapshots.pop(0)


def exact_variables() -> dict:
    return {
        name: SimpleNamespace(value=value)
        for name, value in config.RUNTIME_VARIABLES.items()
    }


def test_managed_runtime_enables_periodic_freshness_before_ttl() -> None:
    assert (
        config.SERIES_A_VARIABLES["A11OY_SERIES_A_DB"]
        == "/data/a11oy/series-a/control-plane-v2.sqlite3"
    )
    assert config.SERIES_A_VARIABLES["A11OY_SERIES_A_STARTUP_REFRESH"] == "1"
    assert int(
        config.SERIES_A_VARIABLES["A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS"]
    ) < 300


def test_managed_runtime_sets_durable_outbox_only_gdw_contract() -> None:
    assert config.GDW_VARIABLES == {
        "GDW_PRODUCTION_MODE": "1",
        "GDW_NAMESPACE": "a11oy",
        "GDW_SERVICE_OWNER_ID": "gdw-runtime",
        "GDW_DB_PATH": "/data/a11oy/gdw/gdw.sqlite3",
        "GDW_PROOF_DIR": "/data/a11oy/gdw/proofs",
        "GDW_RECEIPT_PROJECTION_DIR": "/data/a11oy/gdw/receipts",
        "GDW_REQUIRE_PERSISTENT_STORAGE": "1",
        "GDW_REQUIRED_MOUNT": "/data",
        "GDW_SQLITE_JOURNAL": "DELETE",
        "GDW_SQLITE_SYNCHRONOUS": "FULL",
        "GDW_PROOF_EXPORT_MODE": "outbox",
        "GDW_OUTBOX_ENABLED": "1",
        "GDW_OUTBOX_INTERVAL_SECONDS": "5",
        "GDW_OUTBOX_RETRY_MAX_SECONDS": "60",
        "GDW_OUTBOX_BATCH_SIZE": "100",
        "GDW_OUTBOX_LEASE_SECONDS": "300",
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


def test_volume_readback_fails_closed_when_space_info_omits_metadata() -> None:
    api = SimpleNamespace(
        space_info=lambda *, repo_id: SimpleNamespace(runtime=None)
    )

    with pytest.raises(config.RuntimeConfigError, match="runtime metadata"):
        config.read_space_volumes(api, repo_id=config.CANONICAL_SPACE)
