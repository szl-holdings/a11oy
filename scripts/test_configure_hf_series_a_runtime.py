from __future__ import annotations

from collections.abc import Mapping
import importlib.util
import json
from pathlib import Path
import sys
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


def test_authenticated_read_probe_has_exact_target_and_secret_free_receipt() -> None:
    probe = PublicReadProbe()
    token = "opaque-persistent-read-credential"
    report = config.verify_public_github_reader(token, get=probe)
    assert [url for url, _ in probe.calls] == [
        "https://api.github.com/user",
        "https://api.github.com/orgs/szl-holdings/repos?type=public&per_page=1",
    ]
    for _, options in probe.calls:
        assert options["allow_redirects"] is False
        assert options["timeout"] == 20
        assert options["headers"]["Authorization"] == "Bearer " + token
    assert report["state"] == "VERIFIED_AUTHENTICATED_PUBLIC_READ"
    assert report["oauth_scopes"] == ["read:org"]
    assert token not in json.dumps(report)


@pytest.mark.parametrize("kwargs", [
    {"status": 401}, {"status": 403}, {"status": 302},
    {"scopes": "repo,read:org"}, {"scopes": "public_repo"},
    {"scopes": None}, {"private": True}, {"organization": "another-org"},
    {"transport_failure": True},
])
def test_unproved_reader_does_not_leak_probe_exception(kwargs) -> None:
    with pytest.raises(config.RuntimeConfigError) as error:
        config.verify_public_github_reader(
            "credential-value-must-not-escape", get=PublicReadProbe(**kwargs))
    assert "credential-value-must-not-escape" not in str(error.value)


@pytest.mark.parametrize("token", ["", "bad\nheader", "bad\rheader"])
def test_missing_or_malformed_read_token_is_rejected_before_network(token) -> None:
    probe = PublicReadProbe()
    with pytest.raises(config.RuntimeConfigError):
        config.verify_public_github_reader(token, get=probe)
    assert probe.calls == []


class OpaqueMetadata:
    def __init__(self, attempts):
        self.attempts = attempts

    def fail(self):
        self.attempts.append("metadata value")
        raise AssertionError("metadata values must remain opaque")

    value = property(lambda self: self.fail())
    __str__ = lambda self: self.fail()
    __repr__ = lambda self: self.fail()


class NamesOnlyMetadata(dict):
    def __init__(self, names, attempts):
        super().__init__((name, OpaqueMetadata(attempts)) for name in names)
        self.attempts = attempts

    def fail(self, *_args, **_kwargs):
        self.attempts.append("metadata mapping values")
        raise AssertionError("only metadata names may be inspected")

    __getitem__ = fail
    get = fail
    values = fail
    items = fail


class BrokenNames(Mapping):
    def __init__(self, value_reads):
        self.value_reads = value_reads
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        raise RuntimeError("synthetic-provider-private-detail")

    def __len__(self):
        return 1

    def __getitem__(self, _key):
        self.value_reads.append("broken metadata value")
        raise AssertionError("metadata values must remain opaque")


class MetadataOnlyApi:
    def __init__(self, *, secret_names=None, variable_names=(), failing_read=None):
        self.value_reads = []
        self.reads = []
        self.writes = []
        required = {config.CANONICAL_SIGNING_SECRET, config.GITHUB_PUBLIC_READ_SECRET}
        self.secrets = NamesOnlyMetadata(required if secret_names is None else secret_names,
                                         self.value_reads)
        self.variables = NamesOnlyMetadata(variable_names, self.value_reads)
        self.failing_read = failing_read

    def metadata(self, kind, repo_id, result):
        self.reads.append((kind, repo_id))
        assert repo_id == config.CANONICAL_SPACE
        if self.failing_read == kind:
            raise RuntimeError("synthetic-provider-private-detail")
        return result

    def get_space_secrets(self, *, repo_id):
        return self.metadata("secrets", repo_id, self.secrets)

    def get_space_variables(self, *, repo_id):
        return self.metadata("variables", repo_id, self.variables)

    def space_info(self, *, repo_id):
        return self.metadata("volumes", repo_id, SimpleNamespace(
            runtime=SimpleNamespace(volumes=[volume(config.CANONICAL_BUCKET, "/data")])))

    def __getattr__(self, name):
        if name.startswith(("add_", "delete_", "set_", "update_", "restart_", "pause_")):
            def denied(*_args, **_kwargs):
                self.writes.append(name)
                raise AssertionError("prerequisites must not attempt provider mutations")
            return denied
        raise AttributeError(name)


def assert_setup_required(report, api, diagnostic_code="INSTALLED_AUTHORITY_UNKNOWN"):
    assert report["schema"] == "szl.hf-series-a-runtime-config/v1"
    assert report["repo_id"] == config.CANONICAL_SPACE
    assert report["state"] == "SETUP_REQUIRED"
    assert report["credential_authority_state"] == "UNKNOWN"
    assert report["diagnostic_code"] == diagnostic_code
    assert report["converged"] is False
    assert report["secret_values_read"] is False
    assert report["secret_values_written"] is False
    assert "synthetic-provider-private-detail" not in json.dumps(report)
    assert api.value_reads == []
    assert api.writes == []


@pytest.mark.parametrize("secret_names,variable_names", [
    (set(), ()),
    ({config.CANONICAL_SIGNING_SECRET}, ()),
    ({config.GITHUB_PUBLIC_READ_SECRET}, ()),
    (None, ()),
])
def test_manual_names_never_prove_authority(secret_names, variable_names):
    api = MetadataOnlyApi(secret_names=secret_names, variable_names=variable_names)
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert_setup_required(report, api)
    required = {config.CANONICAL_SIGNING_SECRET, config.GITHUB_PUBLIC_READ_SECRET}
    present = required if secret_names is None else secret_names
    assert report["required_secret_names"] == sorted(required)
    assert report["missing_secret_names"] == sorted(required - present)
    assert {kind for kind, _ in api.reads} == {"secrets", "variables", "volumes"}


@pytest.mark.parametrize("variable_name", [config.GITHUB_PUBLIC_READ_SECRET,
                                           config.CANONICAL_SIGNING_SECRET])
def test_public_required_secret_collision_fails_without_inspecting_value(variable_name):
    api = MetadataOnlyApi(variable_names=[variable_name])
    with pytest.raises(config.RuntimeConfigError, match="SETUP_REQUIRED") as error:
        config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert error.value.diagnostic_code == "PUBLIC_VARIABLE_COLLISION"
    assert api.value_reads == []
    assert api.writes == []


@pytest.mark.parametrize("failing_read", ["secrets", "variables"])
def test_manual_metadata_errors_are_sanitized_and_blocked(failing_read):
    api = MetadataOnlyApi(failing_read=failing_read)
    with pytest.raises(config.RuntimeConfigError, match="SETUP_REQUIRED") as error:
        config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert error.value.diagnostic_code == "CREDENTIAL_METADATA_UNAVAILABLE"
    assert "synthetic-provider-private-detail" not in str(error.value)
    assert api.value_reads == []
    assert api.writes == []


@pytest.mark.parametrize("kind,value", [
    ("secrets", None), ("secrets", [[]]), ("secrets", [True]),
    ("variables", None), ("variables", {1: object()}),
])
def test_malformed_metadata_never_reaches_a_value_or_provider_write(kind, value):
    api = MetadataOnlyApi()
    setattr(api, kind, value)
    with pytest.raises(config.RuntimeConfigError, match="SETUP_REQUIRED") as error:
        config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert error.value.diagnostic_code == ("CREDENTIAL_METADATA_MALFORMED" if value is None
                                           else "CREDENTIAL_NAMES_MALFORMED")
    assert api.value_reads == []
    assert api.writes == []


def test_public_variable_name_iterator_error_is_sanitized():
    api = MetadataOnlyApi()
    api.variables = BrokenNames(api.value_reads)
    with pytest.raises(config.RuntimeConfigError, match="SETUP_REQUIRED") as error:
        config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert error.value.diagnostic_code == "CREDENTIAL_NAMES_MALFORMED"
    assert "synthetic-provider-private-detail" not in str(error.value)
    assert api.variables.iterations > 0
    assert api.value_reads == []
    assert api.writes == []


def test_noncanonical_manual_prerequisite_target_fails_before_reads():
    api = MetadataOnlyApi()
    with pytest.raises(config.RuntimeConfigError) as error:
        config.manual_prerequisites(api, repo_id="SZLHOLDINGS/other")
    assert error.value.diagnostic_code == "CANONICAL_DESTINATION_REQUIRED"
    assert api.reads == []
    assert api.writes == []


@pytest.mark.parametrize("check_only", [True, False])
def test_configure_cannot_mutate_even_when_all_secret_names_are_present(monkeypatch, check_only):
    api = MetadataOnlyApi(variable_names=config.RUNTIME_VARIABLES)
    monkeypatch.setitem(sys.modules, "huggingface_hub",
                        SimpleNamespace(HfApi=lambda **_kwargs: api))
    kwargs = {"repo_id": config.CANONICAL_SPACE, "bucket": config.CANONICAL_BUCKET,
              "token": "synthetic-hf-control", "check_only": check_only}
    if check_only:
        assert_setup_required(config.configure(**kwargs), api)
    else:
        with pytest.raises(config.RuntimeConfigError) as error:
            config.configure(**kwargs)
        assert "synthetic-provider-private-detail" not in str(error.value)
    assert api.value_reads == []
    assert api.writes == []


@pytest.mark.parametrize("failing_read", [None, "secrets", "variables", "volumes", "client"])
def test_check_only_cli_emits_bounded_failed_report_without_read_token(monkeypatch, tmp_path, capsys,
                                                                      failing_read):
    api = MetadataOnlyApi(failing_read=failing_read)
    def client(**_kwargs):
        if failing_read == "client":
            raise RuntimeError("synthetic-provider-private-detail")
        return api

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=client))
    env_reads = []

    def environment(name, default=None):
        env_reads.append(name)
        if name == "HF_TOKEN":
            return "synthetic-hf-control"
        if name == config.GITHUB_PUBLIC_READ_SECRET:
            raise AssertionError("manual prerequisites must not read the GitHub credential")
        return default

    monkeypatch.setattr(config.os.environ, "get", environment)
    output = tmp_path / "series-prerequisites.json"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--check-only", "--output", str(output)])
    code = config.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert type(code) is int and code != 0
    assert json.loads(capsys.readouterr().out) == report
    assert output.stat().st_size < 16384
    assert config.GITHUB_PUBLIC_READ_SECRET not in env_reads
    expected = {None: "INSTALLED_AUTHORITY_UNKNOWN", "client": "SPACE_CLIENT_UNAVAILABLE",
                "secrets": "CREDENTIAL_METADATA_UNAVAILABLE",
                "variables": "CREDENTIAL_METADATA_UNAVAILABLE",
                "volumes": "PERSISTENT_STORAGE_UNAVAILABLE"}
    assert_setup_required(report, api, expected[failing_read])
