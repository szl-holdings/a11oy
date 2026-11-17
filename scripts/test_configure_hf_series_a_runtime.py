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
verifier = config.load_authority_verifier()
ROOT = SCRIPT.resolve().parent.parent
PINNED_PEM = (ROOT / verifier.PINNED_SIGNING_PUBLIC_KEY_PATH).read_bytes()


@pytest.mark.parametrize("mode", ["private-dataset-v1", "unknown-successor"])
def test_legacy_plan_cannot_downgrade_activated_durable_storage(mode):
    with pytest.raises(config.RuntimeConfigError, match="cannot be replaced"):
        config.plan_variables({"GDW_DURABLE_STORAGE": {"value": mode}}, set())


def offline_get(_url):
    raise OSError("offline fixture: no network")


def pinned_get(url):
    if url.endswith("/cosign.pub"):
        return 200, {"content-type": "text/plain"}, PINNED_PEM
    if url.endswith("/api/a11oy/v1/honest"):
        return 200, {}, json.dumps({"git_sha": "c" * 40}).encode()
    return 404, {}, b""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # Every test is offline unless it injects an explicit fixture getter.
    monkeypatch.setattr(verifier, "default_get", offline_get)
    monkeypatch.setattr(config, "read_storage_status", lambda: pytest.fail("storage fixture required"))


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


def test_managed_runtime_binds_atelier_receipts_to_existing_data_mount() -> None:
    assert config.SERIES_A_VARIABLES["A11OY_ATELIER_LEDGER_PATH"] == (
        "/data/a11oy/atelier/turn-receipts-v1.jsonl"
    )
    assert config.SERIES_A_VARIABLES["A11OY_ATELIER_REQUIRED_MOUNT"] == "/data"
    assert config.SERIES_A_VARIABLES["A11OY_ATELIER_LEDGER_PATH"].startswith(
        config.SERIES_A_VARIABLES["A11OY_ATELIER_REQUIRED_MOUNT"] + "/"
    )


def test_managed_inference_receipts_use_the_required_writable_mount() -> None:
    path = Path(config.SERIES_A_VARIABLES["SZL_GOVERN_INFER_LOG"])
    assert path.parent == Path(config.DATA_MOUNT)
    assert path.name == ".szl_govern_infer.jsonl"
    assert config.plan_variables({}, {config.CANONICAL_SIGNING_SECRET})[
        "SZL_GOVERN_INFER_LOG"
    ] == path.as_posix()


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


@pytest.mark.parametrize("secret_names,diagnostic", [
    (set(), "SIGNING_SECRET_MISSING"),
    ({config.CANONICAL_SIGNING_SECRET}, "AUTHORITY_ORIGIN_UNAVAILABLE"),
    ({config.GITHUB_PUBLIC_READ_SECRET}, "SIGNING_SECRET_MISSING"),
    (None, "AUTHORITY_ORIGIN_UNAVAILABLE"),
])
def test_manual_names_never_prove_authority(secret_names, diagnostic):
    # Names alone never verify authority: the live key match is unavailable offline.
    api = MetadataOnlyApi(secret_names=secret_names)
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert_setup_required(report, api, diagnostic)
    required = {config.CANONICAL_SIGNING_SECRET}
    present = {config.CANONICAL_SIGNING_SECRET, config.GITHUB_PUBLIC_READ_SECRET} if secret_names is None else secret_names
    assert report["required_secret_names"] == sorted(required)
    assert report["optional_secret_names"] == [config.GITHUB_PUBLIC_READ_SECRET]
    assert report["missing_secret_names"] == sorted(required - present)
    assert {kind for kind, _ in api.reads} == {"secrets", "variables", "volumes"}


def verified_names(*extra):
    return {config.CANONICAL_SIGNING_SECRET, "GDW_CREDENTIALS_JSON", *extra}


@pytest.mark.parametrize("reader_present", [False, True])
def test_pinned_runtime_key_verifies_installed_authority(reader_present):
    extra = (config.GITHUB_PUBLIC_READ_SECRET,) if reader_present else ()
    api = MetadataOnlyApi(secret_names=verified_names(*extra))
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE, authority_get=pinned_get)
    assert report["state"] == "READY"
    assert report["converged"] is True
    assert report["credential_authority_state"] == "VERIFIED"
    assert report["diagnostic_code"] == "INSTALLED_AUTHORITY_VERIFIED"
    assert report["missing_secret_names"] == []
    assert report["optional_secret_names_present"] == sorted(extra)
    authority = report["installed_authority"]
    assert authority["signing"]["state"] == "VERIFIED_PINNED_RUNTIME_KEY"
    assert authority["signing"]["served_fingerprint_sha256"] == verifier.PINNED_SIGNING_KEY_DER_SHA256
    assert authority["github_public_reader"]["state"] == ("INSTALLED_NAME_ONLY" if reader_present else "PUBLIC_ANONYMOUS")
    assert authority["github_public_reader"]["blocking"] is False
    assert authority["live_git_sha"] == "c" * 40
    assert report["secret_values_read"] is False and report["secret_values_written"] is False
    assert api.value_reads == [] and api.writes == []
    assert len(json.dumps(report).encode()) < 16 * 1024


def test_pinned_key_without_gdw_name_stays_blocked():
    api = MetadataOnlyApi(secret_names={config.CANONICAL_SIGNING_SECRET})
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE, authority_get=pinned_get)
    assert_setup_required(report, api, "GDW_CREDENTIALS_MISSING")


def test_static_fallback_or_foreign_key_stays_blocked():
    tree = verifier.ast.parse((ROOT / "szl_dsse.py").read_text(encoding="utf-8"))
    static = next(node.value.value for node in tree.body if isinstance(node, verifier.ast.Assign)
                  and getattr(node.targets[0], "id", "") == "COSIGN_PUBLIC_PEM")
    for body, diagnostic in ((static.strip().encode(), "SIGNING_KEY_NOT_INSTALLED"),
                             (foreign_pem(), "SIGNING_KEY_MISMATCH")):
        api = MetadataOnlyApi(secret_names=verified_names())
        report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE,
                                             authority_get=lambda url, body=body: (200, {}, body))
        assert_setup_required(report, api, diagnostic)


def foreign_pem():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    return ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


class Value(SimpleNamespace):
    pass


class ConvergedApi:
    """Converged metadata: configure() must pass the hold without any write."""

    def __init__(self):
        self.writes = []
        self.secrets = dict.fromkeys(verified_names())
        self.variables = {name: Value(value=value) for name, value in config.RUNTIME_VARIABLES.items()}

    def get_space_secrets(self, *, repo_id):
        return self.secrets

    def get_space_variables(self, *, repo_id):
        return self.variables

    def space_info(self, *, repo_id):
        return SimpleNamespace(runtime=SimpleNamespace(volumes=[volume(config.CANONICAL_BUCKET, "/data")]))

    def __getattr__(self, name):
        if name.startswith(("add_", "delete_", "set_", "update_", "restart_", "pause_")):
            def record(*_args, **_kwargs):
                self.writes.append(name)
            return record
        raise AttributeError(name)


def test_configure_proceeds_only_when_installed_authority_is_verified(monkeypatch):
    api = ConvergedApi()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda **_kwargs: api))
    kwargs = {"repo_id": config.CANONICAL_SPACE, "bucket": config.CANONICAL_BUCKET,
              "token": "synthetic-hf-control", "check_only": False,
              "expected_source_sha": "a" * 40, "main_reader": lambda: "a" * 40}
    report = config.configure(**kwargs, authority_get=pinned_get)
    assert report["converged"] is True
    assert report["credential_authority_state"] == "VERIFIED"
    assert report["variables_changed"] == [] and report["volume_changed"] is False
    assert api.writes == []
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)  # offline: authority unavailable -> held
    assert error.value.diagnostic_code == "AUTHORITY_ORIGIN_UNAVAILABLE"
    assert api.writes == []


def test_verified_check_only_cli_exits_zero(monkeypatch, tmp_path, capsys):
    api = ConvergedApi()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda **_kwargs: api))
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    monkeypatch.delenv("CANONICAL_ORIGIN", raising=False)
    output = tmp_path / "series.json"
    code = config.main(["--check-only", "--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert report["state"] == "READY" and report["credential_authority_state"] == "VERIFIED"
    assert json.loads(capsys.readouterr().out) == report
    assert "synthetic-hf-control" not in output.read_text(encoding="utf-8")


def test_noncanonical_origin_is_never_verified(monkeypatch):
    api = MetadataOnlyApi(secret_names=verified_names())
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE,
                                         origin="https://attacker.hf.space", authority_get=pinned_get)
    assert_setup_required(report, api, "AUTHORITY_ORIGIN_NOT_CANONICAL")


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
              "token": "synthetic-hf-control", "check_only": check_only,
              "expected_source_sha": "a" * 40, "main_reader": lambda: "a" * 40}
    if check_only:
        assert_setup_required(config.configure(**kwargs), api, "AUTHORITY_ORIGIN_UNAVAILABLE")
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
    expected = {None: "AUTHORITY_ORIGIN_UNAVAILABLE", "client": "SPACE_CLIENT_UNAVAILABLE",
                "secrets": "CREDENTIAL_METADATA_UNAVAILABLE",
                "variables": "CREDENTIAL_METADATA_UNAVAILABLE",
                "volumes": "PERSISTENT_STORAGE_UNAVAILABLE"}
    assert_setup_required(report, api, expected[failing_read])


@pytest.mark.parametrize("mode", ["durable-private-dataset-v1", "unknown-successor"])
def test_legacy_plan_preserves_guard_before_managed_variables_exist(mode):
    with pytest.raises(config.RuntimeConfigError, match="cannot be replaced"):
        config.plan_variables(
            {"GDW_PROOF_EXPORT_MODE": {"value": mode}}, set(),
            {"GDW_PROOF_EXPORT_MODE": "outbox"},
        )


@pytest.mark.parametrize("arguments", [["--source-sha", "a" * 40], ["--managed-acquisition", "missing.json"]])
def test_incomplete_managed_cli_cannot_reach_legacy_or_alternative_managed_entry(monkeypatch, capsys, arguments):
    monkeypatch.setattr(config, "configure", lambda **_kw: pytest.fail("legacy configuration reached"))
    monkeypatch.setattr(config, "configure_managed", lambda *_a, **_kw: pytest.fail("incomplete managed request reached"))
    assert config.main(arguments) == 1
    assert json.loads(capsys.readouterr().out)["diagnostic_code"] == "MANAGED_STORAGE_UNAVAILABLE"


@pytest.mark.parametrize("field,value", [("repo_id", "other/space"), ("bucket", "other/bucket")])
def test_managed_alternative_entry_rejects_resource_change_before_loading_helper(monkeypatch, field, value):
    kwargs = {"repo_id": config.CANONICAL_SPACE, "bucket": config.CANONICAL_BUCKET}
    kwargs[field] = value
    monkeypatch.setattr(config.importlib.util, "spec_from_file_location", lambda *_a: pytest.fail("invalid scope loaded helper"))
    with pytest.raises(config.RuntimeConfigError):
        config.configure_managed(Path("absent"), source_revision="a" * 40,
            deadline=config.time.monotonic() + 2, check_only=False, **kwargs)


def test_managed_alternative_entry_delegates_one_pair_attempt(monkeypatch, capsys):
    calls = []
    def admitted(*args, **kwargs):
        calls.append((args, kwargs))
        return {"state": "CONFIGURATION_VERIFIED", "converged": True, "runtime_proven": False}
    monkeypatch.setattr(config, "configure_managed", admitted)
    monkeypatch.setattr(config, "configure", lambda **_kw: pytest.fail("legacy configuration reached"))
    assert config.main(["--managed-acquisition", "locator.json", "--source-sha", "a" * 40]) == 0
    assert len(calls) == 1 and calls[0][0] == (Path("locator.json"),)
    assert calls[0][1]["source_revision"] == "a" * 40 and calls[0][1]["check_only"] is False
    assert calls[0][1]["repo_id"] == config.CANONICAL_SPACE and calls[0][1]["bucket"] == config.CANONICAL_BUCKET


class CadenceApi(ConvergedApi):
    """Observe the installed drift and only acknowledge writes when requested."""

    def __init__(self, *, accept_write=True):
        super().__init__()
        self.accept_write = accept_write
        self.variables["A11OY_STATE_PERIODIC_SECONDS"] = Value(value="1800")
        self.variables["UNRELATED_OPERATOR_SETTING"] = Value(value="preserve")

    def add_space_variable(self, *, repo_id, key, value, description):
        assert repo_id == config.CANONICAL_SPACE
        self.writes.append((key, value))
        if self.accept_write:
            self.variables[key] = Value(value=value)


def install_cadence_api(monkeypatch, api):
    import httpx
    state = config.load_state_store()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda **_kwargs: api))
    monkeypatch.setattr(config, "read_storage_status", lambda: {
        "schema": state.STATUS_SCHEMA, "mode": "DISABLED", "role": "DISABLED", "writable": True})
    original_writer = config.RuntimeMutationClient
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/variables"
        api.add_space_variable(repo_id=config.CANONICAL_SPACE, **json.loads(request.content))
        return httpx.Response(200, json={})
    monkeypatch.setattr(config, "RuntimeMutationClient", lambda token: original_writer(
        token, transport=httpx.MockTransport(handler)))
    return {"repo_id": config.CANONICAL_SPACE, "bucket": config.CANONICAL_BUCKET,
            "token": "synthetic-hf-control", "authority_get": pinned_get,
            "expected_source_sha": "a" * 40, "main_reader": lambda: "a" * 40}


def test_canonical_cadence_convergence_corrects_1800_and_is_idempotent(monkeypatch):
    api = CadenceApi()
    kwargs = install_cadence_api(monkeypatch, api)
    report = config.configure(**kwargs)
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert report["variables_changed"] == ["A11OY_STATE_PERIODIC_SECONDS"]
    assert report["volume_changed"] is False and report["converged"] is True
    assert api.variables["UNRELATED_OPERATOR_SETTING"].value == "preserve"
    assert "A11OY_STATE_STORE" not in api.variables
    assert "A11OY_STATE_ALERT_SECONDS" not in api.variables
    repeated = config.configure(**kwargs)
    assert repeated["variables_changed"] == [] and repeated["converged"] is True
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]


def test_cadence_write_acknowledgement_without_readback_is_not_convergence(monkeypatch):
    api = CadenceApi(accept_write=False)
    kwargs = install_cadence_api(monkeypatch, api)
    readback = config.await_readback
    monkeypatch.setattr(config, "await_readback", lambda *args, **options: readback(
        *args, **options, attempts=2, delay_seconds=0, sleep=lambda _seconds: None))
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_DRIFT"
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert api.variables["A11OY_STATE_PERIODIC_SECONDS"].value == "1800"


@pytest.mark.parametrize("observed", [None, "1800"])
def test_verified_check_only_rejects_cadence_drift_without_writes(monkeypatch, observed):
    api = ConvergedApi()
    if observed is None:
        api.variables.pop("A11OY_STATE_PERIODIC_SECONDS")
    else:
        api.variables["A11OY_STATE_PERIODIC_SECONDS"] = Value(value=observed)
    kwargs = install_cadence_api(monkeypatch, api)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=True)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_DRIFT"
    assert api.writes == []


def test_check_only_cadence_read_failure_is_sanitized(monkeypatch):
    api = ConvergedApi()
    kwargs = install_cadence_api(monkeypatch, api)
    reads = 0

    def fail_readback(*, repo_id):
        nonlocal reads
        reads += 1
        if reads == 2:
            raise RuntimeError("synthetic-provider-private-detail")
        return api.variables

    monkeypatch.setattr(api, "get_space_variables", fail_readback)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=True)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_UNAVAILABLE"
    assert "synthetic-provider-private-detail" not in str(error.value)
    assert api.writes == []


@pytest.mark.parametrize("check_only", [False, True])
@pytest.mark.parametrize("name", [
    "A11OY_STATE_PERIODIC_SECONDS", "A11OY_STATE_ALERT_SECONDS", "A11OY_STATE_DEBOUNCE_SECONDS",
])
@pytest.mark.parametrize("public_value_present", [False, True])
def test_cadence_secret_collision_fails_without_value_access_or_write(
    monkeypatch, check_only, name, public_value_present
):
    api = CadenceApi()
    if public_value_present:
        api.variables[name] = Value(value="900" if name.endswith("ALERT_SECONDS") else "30")
    else:
        api.variables.pop(name, None)
    secret_reads = []
    api.secrets = NamesOnlyMetadata(verified_names(name), secret_reads)
    kwargs = install_cadence_api(monkeypatch, api)
    with pytest.raises(config.RuntimeConfigError, match="collide"):
        config.configure(**kwargs, check_only=check_only)
    assert secret_reads == [] and api.writes == []


def test_check_only_cli_reports_cadence_drift_as_not_converged(monkeypatch, capsys):
    api = CadenceApi()
    install_cadence_api(monkeypatch, api)
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    monkeypatch.delenv("CANONICAL_ORIGIN", raising=False)
    assert config.main(["--check-only"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "SETUP_REQUIRED" and report["converged"] is False
    assert report["diagnostic_code"] == "RUNTIME_CONFIG_DRIFT"
    assert report["secret_values_read"] is False and report["secret_values_written"] is False
    assert "synthetic-hf-control" not in json.dumps(report)
    assert "1800" not in json.dumps(report)
    assert api.writes == []


class CadencePrewriteApi(CadenceApi):
    """Plan a volume and unrelated variable write before cadence validation."""

    def __init__(self):
        super().__init__()
        self.volume_reads = 0
        self.variables["A11OY_REQUIRE_PERSISTENT_STORAGE"] = Value(value="0")

    def space_info(self, *, repo_id):
        self.volume_reads += 1
        # Authority sees the existing mount; a later planning read needs it
        # reconciled. Invalid cadence must stop that first effect as well.
        volumes = [] if self.volume_reads == 2 else [volume(config.CANONICAL_BUCKET, "/data")]
        return SimpleNamespace(runtime=SimpleNamespace(volumes=volumes))


@pytest.mark.parametrize("check_only", [False, True])
@pytest.mark.parametrize("name,raw", [
    ("A11OY_STATE_ALERT_SECONDS", "300"),
    ("A11OY_STATE_ALERT_SECONDS", "60"),
    ("A11OY_STATE_ALERT_SECONDS", "299.9"),
    ("A11OY_STATE_ALERT_SECONDS", "59.9"),
    ("A11OY_STATE_ALERT_SECONDS", "86400.1"),
    ("A11OY_STATE_DEBOUNCE_SECONDS", "0"),
    ("A11OY_STATE_DEBOUNCE_SECONDS", "3600.1"),
    *[(name, raw)
      for name in ("A11OY_STATE_ALERT_SECONDS", "A11OY_STATE_DEBOUNCE_SECONDS")
      for raw in ("not-a-number", "NaN", "inf", "-inf", "1e9999")],
])
def test_cadence_preserved_settings_reject_invalid_values_before_any_write(
    monkeypatch, check_only, name, raw
):
    api = CadencePrewriteApi()
    api.variables[name] = Value(value=raw)
    kwargs = install_cadence_api(monkeypatch, api)
    monkeypatch.setattr(sys.modules["huggingface_hub"], "Volume", SimpleNamespace, raising=False)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=check_only)
    assert error.value.diagnostic_code == "STATE_STORE_CADENCE_INVALID"
    assert raw not in str(error.value)
    assert api.writes == []


@pytest.mark.parametrize("check_only", [False, True])
@pytest.mark.parametrize("name,raw", [
    ("A11OY_STATE_ALERT_SECONDS", None),
    ("A11OY_STATE_ALERT_SECONDS", 900),
    ("A11OY_STATE_DEBOUNCE_SECONDS", False),
    ("A11OY_STATE_DEBOUNCE_SECONDS", {}),
])
def test_cadence_preserved_metadata_must_contain_string_values(
    monkeypatch, check_only, name, raw
):
    api = CadencePrewriteApi()
    api.variables[name] = Value(value=raw)
    kwargs = install_cadence_api(monkeypatch, api)
    monkeypatch.setattr(sys.modules["huggingface_hub"], "Volume", SimpleNamespace, raising=False)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=check_only)
    assert error.value.diagnostic_code == "STATE_STORE_CADENCE_INVALID"
    assert api.writes == []


@pytest.mark.parametrize("alert,debounce", [
    (None, None),
    ("900", "30"),
    ("  ", ""),
    ("300.1", "1"),
    ("900", "3600"),
    ("86400", "3600"),
])
def test_cadence_repair_preserves_effective_runtime_settings(monkeypatch, alert, debounce):
    # The deployed parser owns defaults and bounds. Test against it without
    # constructing a StateStore or importing it in the deployment helper.
    from a11oy_state_store import Settings

    api = CadenceApi()
    preserved = {}
    for name, raw in (("A11OY_STATE_ALERT_SECONDS", alert),
                      ("A11OY_STATE_DEBOUNCE_SECONDS", debounce)):
        if raw is not None:
            api.variables[name] = Value(value=raw)
            preserved[name] = raw
    kwargs = install_cadence_api(monkeypatch, api)
    result = config.configure(**kwargs)
    actual = Settings.from_environ({
        "A11OY_STATE_PERIODIC_SECONDS": api.variables["A11OY_STATE_PERIODIC_SECONDS"].value,
        **{name: api.variables[name].value for name in preserved},
    })
    expected = Settings.from_environ({"A11OY_STATE_PERIODIC_SECONDS": "300", **preserved})
    assert actual == expected and actual.periodic_s < actual.alert_s
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert result["converged"] is True
    assert {name: api.variables[name].value for name in preserved} == preserved
    assert config.configure(**kwargs, check_only=True)["converged"] is True
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]


@pytest.mark.parametrize("observed", [None, "1800", "not-a-number", "NaN", "inf", "", "300.0"])
def test_managed_periodic_drift_is_repairable_but_never_passes_check_only(monkeypatch, observed):
    api = CadenceApi()
    if observed is None:
        api.variables.pop("A11OY_STATE_PERIODIC_SECONDS")
    else:
        api.variables["A11OY_STATE_PERIODIC_SECONDS"] = Value(value=observed)
    kwargs = install_cadence_api(monkeypatch, api)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=True)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_DRIFT"
    assert api.writes == []
    assert config.configure(**kwargs)["converged"] is True
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert config.configure(**kwargs, check_only=True)["converged"] is True


def test_cadence_readback_revalidates_preserved_alert(monkeypatch):
    api = CadenceApi()
    kwargs = install_cadence_api(monkeypatch, api)
    write = api.add_space_variable

    def changed_alert(**options):
        write(**options)
        api.variables["A11OY_STATE_ALERT_SECONDS"] = Value(value="300")

    monkeypatch.setattr(api, "add_space_variable", changed_alert)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "STATE_STORE_CADENCE_INVALID"
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]


def test_cadence_invalid_cli_report_is_sanitized_and_read_only(monkeypatch, capsys):
    api = ConvergedApi()
    canary = "synthetic-private-provider-detail"
    api.variables["A11OY_STATE_ALERT_SECONDS"] = Value(value=canary)
    install_cadence_api(monkeypatch, api)
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    assert config.main(["--check-only"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "SETUP_REQUIRED" and report["converged"] is False
    assert report["diagnostic_code"] == "STATE_STORE_CADENCE_INVALID"
    assert report["secret_values_read"] is False and report["secret_values_written"] is False
    assert canary not in json.dumps(report)
    assert api.writes == []


@pytest.mark.parametrize("alert", [None, "", "  ", "600"])
def test_cadence_relation_tracks_the_runtime_alert_default(alert):
    from a11oy_state_store import Settings

    values = {} if alert is None else {"A11OY_STATE_ALERT_SECONDS": alert}
    runtime = Settings.from_environ(values)
    current = {name: Value(value=value) for name, value in values.items()}
    # Derive the boundary from the real runtime parser, including blank defaults,
    # rather than asserting that a second copy of the literal default is equal.
    with pytest.raises(config.RuntimeConfigError) as error:
        config.plan_variables(
            current, set(), {"A11OY_STATE_PERIODIC_SECONDS": str(runtime.alert_s)}
        )
    assert error.value.diagnostic_code == "STATE_STORE_CADENCE_INVALID"
    assert config.plan_variables(
        current, set(), {"A11OY_STATE_PERIODIC_SECONDS": str(runtime.alert_s - 0.5)}
    ) == {"A11OY_STATE_PERIODIC_SECONDS": str(runtime.alert_s - 0.5)}


# State-store v2 configuration admission is a refusal gate. These fixtures use
# the real canonical manifest parser and fake current-tip observations only.
class ReleasedFixture:
    def __init__(self, api=None, *, claim_kind="CLEAN"):
        self.ss = config.load_state_store()
        self.api = api or CadenceApi()
        self.api.variables[self.ss.ENABLE_ENV] = Value(value=self.ss.ENABLED_VALUE)
        entries = {}
        for index, spec in enumerate(self.ss.STORES, 1):
            digest = format(index, "x") * 64
            extension = "sqlite3" if spec.kind == "sqlite" else "mdb"
            entries[spec.label] = {
                "path": self.ss.PREFIX + "/" + spec.label + "/20261117T010000Z-10-1-" + digest[:16] + "." + extension,
                "sha256": digest, "size": 512, "kind": spec.kind,
                "integrity": "integrity_check" if spec.kind == "sqlite" else "lmdb_read",
                "logical_sha256": "f" * 64, "taken_at": "2026-11-17T01:00:00Z", "epoch": 10, "seq": 1,
            }
        self.head = {
            "schema": self.ss.HEAD_SCHEMA, "operation_id": "a" * 32, "sequence": 43,
            "previous_manifest_sha256": "b" * 64, "epoch": 10, "writer_id": "c" * 32,
            "boot_id": "d" * 32, "state": "RELEASED", "transition": "RELEASE", "handover": None,
            "claim": {"kind": claim_kind, "at": "2026-11-17T00:00:00Z",
                      "origins": {label: "RESTORED" for label in entries}, "previous_epoch": 9},
            "lease": {"renewed_at": "2026-11-17T01:00:02Z", "heartbeat_path": self.ss.HEARTBEAT_PATH,
                      "stale_after_seconds": 120},
            "source_revision": "a" * 40, "bucket": config.CANONICAL_BUCKET,
            "snapshots": entries, "history": {},
        }
        self.revision = "1" * 40
        self.status = {
            "schema": self.ss.STATUS_SCHEMA, "mode": "FENCED", "role": "RELEASED", "writable": False,
            "epoch": 10, "claim": claim_kind, "lease": {"state": "RELEASED", "sequence": 43},
            "active_errors": {}, "pending_publish": [], "last_error": None, "alert": False,
            "stores": {spec.label: {"health": "OK", "kind": spec.kind, "snapshot_failures": 0,
                                    "blocked_code": None, "last_error_code": None,
                                    "sha16": entries[spec.label]["sha256"][:16],
                                    "integrity": entries[spec.label]["integrity"]}
                       for spec in self.ss.STORES},
        }
        self.reads = 0
        self.clock = 100.0

    def observe(self):
        self.reads += 1
        return self.ss.Observation(self.revision, self.ss.canonical(self.ss.validate_head(self.head)))

    def guard(self, **kwargs):
        return config.ReleasedStateGuard(
            self.api, status_get=lambda: self.status,
            observe=kwargs.pop("observe", self.observe),
            clock=kwargs.pop("clock", lambda: self.clock), **kwargs)


def install_release_transport(monkeypatch, fixture, *, handler=None, guard=None):
    import httpx
    real_writer = config.RuntimeMutationClient
    kwargs = install_cadence_api(monkeypatch, fixture.api)
    selected = guard or fixture.guard()
    monkeypatch.setattr(config, "ReleasedStateGuard", lambda _api: selected)
    writers = []

    def default_handler(request):
        assert str(request.url) == "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/variables"
        payload = json.loads(request.content)
        fixture.api.add_space_variable(repo_id=config.CANONICAL_SPACE, **payload)
        return httpx.Response(200, json={})

    def writer_factory(token):
        writer = real_writer(token, transport=httpx.MockTransport(handler or default_handler),
                             clock=lambda: fixture.clock)
        writers.append(writer)
        return writer
    monkeypatch.setattr(config, "RuntimeMutationClient", writer_factory)
    return kwargs, selected, writers


@pytest.mark.parametrize("claim_kind", ["CLEAN", "UNCLEAN_HANDOVER"])
def test_release_guard_preserves_exact_incumbent_claim_without_recovery_claim(claim_kind):
    fixture = ReleasedFixture(claim_kind=claim_kind)
    guard = fixture.guard()
    assert guard.admit() == 105
    assert guard.summary["claim"] == claim_kind
    assert guard.summary["state"] == "RELEASED"
    assert fixture.reads == 2
    original = guard.pinned
    assert guard.admit() == 105
    assert guard.pinned == original


@pytest.mark.parametrize("changes", [
    {"role": "WRITER", "writable": True, "lease": {"state": "ACTIVE", "sequence": 43}},
    {"role": "HANDING_OVER", "lease": {"state": "HANDOVER_REQUESTED", "sequence": 43}},
    {"role": "BOOTING"}, {"role": "BLOCKED"}, {"mode": "UNFENCED"}, {"mode": "UNKNOWN"},
])
def test_active_or_unknown_writer_cannot_reach_private_probe_or_config_write(changes):
    fixture = ReleasedFixture()
    fixture.status.update(changes)
    with pytest.raises(config.RuntimeConfigError) as error:
        fixture.guard(observe=lambda: pytest.fail("unsafe public state reached private probe")).admit()
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_REQUIRED"
    assert fixture.api.writes == []


@pytest.mark.parametrize("configured", [None, True, "unexpected", "", "0"])
def test_fenced_status_cannot_authorize_when_activation_configuration_disagrees(configured):
    fixture = ReleasedFixture()
    fixture.api.variables[fixture.ss.ENABLE_ENV] = Value(value=configured)
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()
    assert fixture.api.writes == []


def test_secret_activation_flag_is_not_read_or_inferred():
    fixture = ReleasedFixture()
    reads = []
    fixture.api.secrets = NamesOnlyMetadata(verified_names(fixture.ss.ENABLE_ENV), reads)
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()
    assert reads == []


def test_explicit_disabled_path_matches_actual_state_store_status_contract():
    fixture = ReleasedFixture()
    fixture.api.variables.pop(fixture.ss.ENABLE_ENV)
    fixture.status = {"schema": fixture.ss.STATUS_SCHEMA, "mode": "DISABLED",
                      "role": "DISABLED", "writable": True}
    assert fixture.guard(observe=lambda: pytest.fail("disabled mode read private HEAD")).admit() == 105


@pytest.mark.parametrize("configured", ["v2", "unknown", None, 0])
def test_disabled_status_requires_explicit_consistent_configuration(configured):
    fixture = ReleasedFixture()
    fixture.api.variables[fixture.ss.ENABLE_ENV] = Value(value=configured)
    fixture.status = {"schema": fixture.ss.STATUS_SCHEMA, "mode": "DISABLED",
                      "role": "DISABLED", "writable": True}
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()


@pytest.mark.parametrize("field,value", [
    ("epoch", 11), ("epoch", True), ("claim", "FIRST_BOOT"),
    ("active_errors", {"capture": {}}), ("pending_publish", ["series_a"]),
    ("last_error", {"code": "private-detail"}), ("alert", True),
])
def test_public_release_must_match_exact_healthy_private_state(field, value):
    fixture = ReleasedFixture()
    fixture.status[field] = value
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()


@pytest.mark.parametrize("field,value", [
    ("health", "BLOCKED"), ("snapshot_failures", 1), ("snapshot_failures", False),
    ("blocked_code", "BLOCKED"), ("last_error_code", "FAILURE"),
    ("sha16", "0" * 16), ("integrity", "unknown"), ("kind", "lmdb"),
])
def test_each_store_must_agree_with_the_pinned_release(field, value):
    fixture = ReleasedFixture()
    fixture.status["stores"]["series_a"][field] = value
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()


def test_incomplete_snapshot_map_is_refused():
    fixture = ReleasedFixture()
    fixture.head["snapshots"].pop("unay")
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()


def test_active_private_tip_cannot_be_hidden_by_old_released_public_status():
    fixture = ReleasedFixture()
    fixture.head.update(state="ACTIVE", transition="SNAPSHOT")
    with pytest.raises(config.RuntimeConfigError):
        fixture.guard().admit()


def test_second_tip_read_refuses_intervening_successor():
    fixture = ReleasedFixture()
    original = fixture.observe()
    reads = []
    def observe():
        reads.append(True)
        return original if len(reads) == 1 else fixture.ss.Observation("2" * 40, original.body)
    with pytest.raises(config.RuntimeConfigError) as error:
        fixture.guard(observe=observe).admit()
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_CHANGED"


def test_later_write_cannot_switch_to_another_released_tip():
    fixture = ReleasedFixture()
    guard = fixture.guard()
    guard.admit()
    fixture.revision = "2" * 40
    with pytest.raises(config.RuntimeConfigError) as error:
        guard.admit()
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_CHANGED"


def test_slow_release_observation_cannot_admit_a_write():
    fixture = ReleasedFixture()
    def slow_observe():
        fixture.clock += 16
        return fixture.observe()
    with pytest.raises(config.RuntimeConfigError) as error:
        fixture.guard(observe=slow_observe).admit()
    assert error.value.diagnostic_code == "STATE_STORE_OBSERVATION_EXPIRED"


def test_immutable_head_read_errors_are_sanitized():
    fixture = ReleasedFixture()
    def broken():
        raise RuntimeError("provider-private-detail synthetic-hf-control")
    with pytest.raises(config.RuntimeConfigError) as error:
        fixture.guard(observe=broken).admit()
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_UNVERIFIED"
    assert "provider-private-detail" not in str(error.value)
    assert "synthetic-hf-control" not in str(error.value)


def test_released_cadence_write_uses_actual_local_transport_guard(monkeypatch):
    fixture = ReleasedFixture()
    kwargs, guard, writers = install_release_transport(monkeypatch, fixture)
    report = config.configure(**kwargs)
    assert fixture.api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert report["state_store_admission"] == guard.summary
    assert report["runtime_boot_verified"] is False
    assert report["storage_preservation_verified"] is False
    assert report["mutation_deadline_scope"] == "REQUEST_DISPATCH_NOT_PROVIDER_EXECUTION"
    assert writers[0].attempted == ["A11OY_STATE_PERIODIC_SECONDS"]
    assert writers[0].acknowledged == writers[0].attempted


def test_active_v2_configure_refuses_before_any_provider_write(monkeypatch):
    fixture = ReleasedFixture()
    fixture.status.update(role="WRITER", writable=True, lease={"state": "ACTIVE", "sequence": 43})
    kwargs, _guard, writers = install_release_transport(monkeypatch, fixture)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_REQUIRED"
    assert error.value.mutation_outcome["attempted"] == []
    assert writers[0].attempted == [] and fixture.api.writes == []


def test_next_configuration_write_rechecks_release_and_stops_after_successor(monkeypatch):
    import httpx
    fixture = ReleasedFixture()
    fixture.api.variables["GDW_NAMESPACE"] = Value(value="drift")
    def handler(request):
        payload = json.loads(request.content)
        fixture.api.add_space_variable(repo_id=config.CANONICAL_SPACE, **payload)
        fixture.status.update(role="WRITER", writable=True,
                              lease={"state": "ACTIVE", "sequence": 44})
        return httpx.Response(200, json={})
    kwargs, _guard, writers = install_release_transport(monkeypatch, fixture, handler=handler)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_REQUIRED"
    assert fixture.api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert error.value.mutation_outcome["possible_partial_configuration"] is True
    assert writers[0].attempted == ["A11OY_STATE_PERIODIC_SECONDS"]


def test_protected_main_gate_is_still_checked_before_each_write(monkeypatch):
    fixture = ReleasedFixture()
    fixture.api.variables["GDW_NAMESPACE"] = Value(value="drift")
    kwargs, _guard, writers = install_release_transport(monkeypatch, fixture)
    calls = []
    def main_reader():
        calls.append(True)
        return "a" * 40 if len(calls) < 5 else "b" * 40
    kwargs["main_reader"] = main_reader
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "SOURCE_NOT_CURRENT_MAIN"
    assert writers[0].attempted == ["A11OY_STATE_PERIODIC_SECONDS"]
    assert error.value.mutation_outcome["acknowledged"] == writers[0].attempted


def test_uncertain_configuration_response_is_not_retried_or_followed_by_other_write(monkeypatch):
    import httpx
    fixture = ReleasedFixture()
    fixture.api.variables["GDW_NAMESPACE"] = Value(value="drift")
    attempts = []
    def handler(request):
        attempts.append(request)
        raise httpx.ReadTimeout("provider-private-detail", request=request)
    kwargs, _guard, writers = install_release_transport(monkeypatch, fixture, handler=handler)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_OUTCOME_UNCERTAIN"
    assert len(attempts) == 1 and writers[0].acknowledged == []
    assert error.value.mutation_outcome["possible_partial_configuration"] is True
    assert "provider-private-detail" not in str(error.value)


def test_cli_persists_uncertain_outcome_and_cleanup_cannot_mask_it(monkeypatch, tmp_path, capsys):
    import httpx
    fixture = ReleasedFixture()
    def handler(request):
        raise httpx.ReadTimeout("synthetic-provider-secret", request=request)
    _kwargs, guard, _writers = install_release_transport(monkeypatch, fixture, handler=handler)
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setattr(config, "require_current_main", lambda *_args: None)
    monkeypatch.setattr(guard, "close", lambda: (_ for _ in ()).throw(OSError("cleanup-private-detail")))
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    output = tmp_path / "outcome.json"
    assert config.main(["--expected-source-sha", "a" * 40, "--output", str(output)]) == 1
    report = json.loads(output.read_text())
    assert report["diagnostic_code"] == "RUNTIME_CONFIG_OUTCOME_UNCERTAIN"
    assert report["mutation_outcome"]["attempted"] == ["A11OY_STATE_PERIODIC_SECONDS"]
    assert report["mutation_outcome"]["acknowledged"] == []
    assert report["mutation_outcome"]["automatic_retry"] is False
    assert "synthetic-provider-secret" not in output.read_text()
    assert "synthetic-hf-control" not in output.read_text()
    assert "cleanup-private-detail" not in capsys.readouterr().out


@pytest.mark.parametrize("check_only", [False, True])
def test_noop_and_check_only_never_construct_a_mutation_guard_or_client(monkeypatch, check_only):
    api = ConvergedApi()
    kwargs = install_cadence_api(monkeypatch, api)
    monkeypatch.setattr(config, "ReleasedStateGuard", lambda *_a: pytest.fail("read-only path created guard"))
    monkeypatch.setattr(config, "RuntimeMutationClient", lambda *_a: pytest.fail("read-only path created client"))
    report = config.configure(**kwargs, check_only=check_only)
    assert report["converged"] is True and api.writes == []


def test_transport_deadline_is_rechecked_after_request_preparation():
    import httpx
    clock = [100.0]
    calls = []
    writer = config.RuntimeMutationClient("fixture-token", clock=lambda: clock[0],
                                         transport=httpx.MockTransport(lambda request: calls.append(request)))
    original_stream = writer.client.stream
    def delayed_stream(*args, **kwargs):
        clock[0] = 106.0
        return original_stream(*args, **kwargs)
    writer.client.stream = delayed_stream
    try:
        with pytest.raises(config.RuntimeConfigError) as error:
            writer.submit("POST", "variables", {"key": "fixture", "value": "value"},
                          deadline=105.0, label="fixture")
        assert error.value.diagnostic_code == "STATE_STORE_OBSERVATION_EXPIRED"
        assert calls == [] and writer.attempted == []
    finally:
        writer.close()


@pytest.mark.parametrize("method,suffix", [("POST", "restart"), ("DELETE", "variables"), ("PUT", "secrets")])
def test_mutation_transport_cannot_target_another_operation(method, suffix):
    import httpx
    writer = config.RuntimeMutationClient("fixture-token", clock=lambda: 100,
        transport=httpx.MockTransport(lambda _request: pytest.fail("forbidden request dispatched")))
    try:
        with pytest.raises(config.RuntimeConfigError) as error:
            writer.submit(method, suffix, {}, deadline=105, label="forbidden")
        assert error.value.diagnostic_code == "RUNTIME_CONFIG_REQUEST_REFUSED"
        assert writer.attempted == []
    finally:
        writer.close()


def test_mutation_redirect_is_not_followed():
    import httpx
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(307, headers={"location": "https://other.example/steal"})
    writer = config.RuntimeMutationClient("fixture-token", transport=httpx.MockTransport(handler),
                                         clock=lambda: 100)
    try:
        with pytest.raises(config.RuntimeConfigError):
            writer.submit("POST", "variables", {"key": "fixture", "value": "value"},
                          deadline=105, label="fixture")
        assert len(requests) == 1 and str(requests[0].url).startswith("https://huggingface.co/")
        assert writer.attempted == ["fixture"] and writer.acknowledged == []
    finally:
        writer.close()


def test_mutation_volume_payload_matches_installed_sdk_contract():
    import httpx
    from huggingface_hub import Volume
    values = [Volume(type="bucket", source=config.CANONICAL_BUCKET, mount_path="/data", read_only=False)]
    payload = {"volumes": [item.to_dict() for item in values]}
    assert payload == {"volumes": [{"type": "bucket", "source": config.CANONICAL_BUCKET,
                                   "mountPath": "/data", "readOnly": False}]}
    requests = []
    writer = config.RuntimeMutationClient("fixture-token", clock=lambda: 100,
        transport=httpx.MockTransport(lambda request: (requests.append(request) or httpx.Response(200))))
    try:
        writer.submit("PUT", "volumes", payload, deadline=105, label="volumes")
        assert requests[0].method == "PUT" and json.loads(requests[0].content) == payload
    finally:
        writer.close()


def test_state_parser_loads_under_real_isolated_python_without_activation():
    import subprocess
    command = (
        "import importlib.util,socket,sys;"
        "socket.socket.connect=lambda *a: (_ for _ in ()).throw(AssertionError('network forbidden'));"
        "p=" + repr(str(SCRIPT)) + ";"
        "s=importlib.util.spec_from_file_location('isolated_config',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "before=list(sys.path);state=m.load_state_store();"
        "assert sys.path==before;assert state.active() is None;"
        "print('ISOLATED_PARSER_LOADED_NO_ACTIVATION')"
    )
    result = subprocess.run([sys.executable, "-I", "-B", "-c", command],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ISOLATED_PARSER_LOADED_NO_ACTIVATION"

def test_main_advancing_during_release_observation_stops_before_transport(monkeypatch):
    fixture = ReleasedFixture()
    current_main = ["a" * 40]
    guard = fixture.guard()
    def observe_status():
        current_main[0] = "b" * 40
        return fixture.status
    guard.status_get = observe_status
    kwargs, _guard, writers = install_release_transport(monkeypatch, fixture, guard=guard)
    kwargs["main_reader"] = lambda: current_main[0]
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert guard.summary["state"] == "RELEASED"
    assert error.value.diagnostic_code == "SOURCE_NOT_CURRENT_MAIN"
    assert error.value.mutation_outcome["attempted"] == []
    assert writers[0].attempted == [] and fixture.api.writes == []


def test_slow_final_main_read_cannot_refresh_the_release_dispatch_deadline(monkeypatch):
    fixture = ReleasedFixture()
    kwargs, _guard, writers = install_release_transport(monkeypatch, fixture)
    reads = []
    def main_reader():
        reads.append(True)
        if len(reads) == 3:
            fixture.clock += config.CONFIG_SUBMISSION_SECONDS + 1
        return "a" * 40
    kwargs["main_reader"] = main_reader
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert len(reads) == 3
    assert error.value.diagnostic_code == "STATE_STORE_OBSERVATION_EXPIRED"
    assert error.value.mutation_outcome["attempted"] == []
    assert writers[0].attempted == [] and fixture.api.writes == []
