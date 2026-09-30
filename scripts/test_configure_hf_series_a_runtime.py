from __future__ import annotations

import importlib.util
import json
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


class PublicReadProbe:
    def __init__(self, *, status=200, scopes="read:org", private=False,
                 organization="szl-holdings", transport_failure=False) -> None:
        self.status = status
        self.scopes = scopes
        self.private = private
        self.organization = organization
        self.transport_failure = transport_failure
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.transport_failure:
            raise ValueError("credential-value-must-not-escape")
        if url.endswith("/user"):
            headers = {} if self.scopes is None else {"X-OAuth-Scopes": self.scopes}
            payload = {"id": 1}
        else:
            headers = {}
            payload = [{"private": self.private, "visibility": "private" if self.private else "public",
                        "owner": {"login": self.organization}}]
        return SimpleNamespace(status_code=self.status, headers=headers, json=lambda: payload)


class ReaderBindingApi:
    def __init__(self, *, collision=False, readback=True) -> None:
        self.collision = collision
        self.readback = readback
        self.writes = []

    def get_space_variables(self, *, repo_id):
        return {config.GITHUB_PUBLIC_READ_SECRET: object()} if self.collision else {}

    def add_space_secret(self, **kwargs):
        self.writes.append(kwargs)

    def get_space_secrets(self, *, repo_id):
        return {config.GITHUB_PUBLIC_READ_SECRET: object()} if self.readback else {}


def test_authenticated_read_binding_has_exact_target_and_secret_free_receipt() -> None:
    probe = PublicReadProbe()
    api = ReaderBindingApi()
    token = "opaque-persistent-read-credential"
    report = config.bind_public_github_reader(api, repo_id=config.CANONICAL_SPACE,
                                             token=token, get=probe)
    assert [url for url, _ in probe.calls] == [
        "https://api.github.com/user",
        "https://api.github.com/orgs/szl-holdings/repos?type=public&per_page=1",
    ]
    for _, options in probe.calls:
        assert options["allow_redirects"] is False
        assert options["timeout"] == 20
        assert options["headers"]["Authorization"] == "Bearer " + token
    assert api.writes == [{"repo_id": config.CANONICAL_SPACE,
        "key": config.GITHUB_PUBLIC_READ_SECRET, "value": token,
        "description": "Verified read-only organization credential for public GitHub inventory."}]
    assert report["state"] == "VERIFIED_AUTHENTICATED_PUBLIC_READ"
    assert report["oauth_scopes"] == ["read:org"]
    assert token not in json.dumps(report)


@pytest.mark.parametrize("kwargs", [
    {"status": 401}, {"status": 403}, {"status": 302},
    {"scopes": "repo,read:org"}, {"scopes": "public_repo"},
    {"scopes": None}, {"private": True}, {"organization": "another-org"},
    {"transport_failure": True},
])
def test_unproved_reader_never_reaches_secret_writer_or_leaks_exception(kwargs) -> None:
    api = ReaderBindingApi()
    with pytest.raises(config.RuntimeConfigError) as error:
        config.bind_public_github_reader(api, repo_id=config.CANONICAL_SPACE,
                                         token="credential-value-must-not-escape", get=PublicReadProbe(**kwargs))
    assert api.writes == []
    assert "credential-value-must-not-escape" not in str(error.value)


@pytest.mark.parametrize("token", ["", "bad\nheader", "bad\rheader"])
def test_missing_or_malformed_read_token_is_rejected_before_network(token) -> None:
    probe = PublicReadProbe()
    with pytest.raises(config.RuntimeConfigError):
        config.verify_public_github_reader(token, get=probe)
    assert probe.calls == []


def test_public_variable_collision_and_noncanonical_binding_never_write() -> None:
    for repo_id, collision in ((config.CANONICAL_SPACE, True), ("SZLHOLDINGS/other", False)):
        api = ReaderBindingApi(collision=collision)
        with pytest.raises(config.RuntimeConfigError):
            config.bind_public_github_reader(api, repo_id=repo_id, token="read-token", get=PublicReadProbe())
        assert api.writes == []


def test_secret_name_readback_is_required_after_one_binding_attempt() -> None:
    api = ReaderBindingApi(readback=False)
    with pytest.raises(config.RuntimeConfigError, match="readback"):
        config.bind_public_github_reader(api, repo_id=config.CANONICAL_SPACE,
                                         token="read-token", get=PublicReadProbe())
    assert len(api.writes) == 1
