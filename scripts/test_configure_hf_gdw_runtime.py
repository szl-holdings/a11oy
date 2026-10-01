from __future__ import annotations

from collections.abc import Mapping
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
verifier = config.load_authority_verifier()
ROOT = SCRIPT.resolve().parent.parent
PINNED_PEM = (ROOT / verifier.PINNED_SIGNING_PUBLIC_KEY_PATH).read_bytes()
SIGNING_SECRET = "SZL_COSIGN_PRIVATE_PEM"


def offline_get(_url):
    raise OSError("offline fixture: no network")


def pinned_get(url):
    if url.endswith("/cosign.pub"):
        return 200, {}, PINNED_PEM
    return 503, {}, b""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(verifier, "default_get", offline_get)


def test_desired_variables_preserve_nonsecret_storage_and_resource_contract() -> None:
    variables = config.desired_variables()
    assert config.CREDENTIAL_REGISTRY_SECRET not in variables
    assert variables["GDW_SQLITE_JOURNAL"] == "DELETE"
    assert variables["GDW_DB_PATH"].startswith("/data/")
    assert variables["GDW_PRODUCTION_MODE"] == "1"
    assert variables["GDW_REQUIRE_PERSISTENT_STORAGE"] == "1"
    assert variables["GDW_REQUIRED_MOUNT"] == "/data"
    assert variables["GDW_OUTBOX_ENABLED"] == "1"
    assert variables["GDW_OWNER_MAX_PENDING_EFFECTS"] == "2000"
    # The promotion probe opens one session and one request per deployment and
    # holds them for the 7-day retention window; the ceilings must stay above
    # that working set or the sync fails on 429 instead of on real evidence.
    assert int(variables["GDW_OWNER_MAX_ACTIVE_SESSIONS"]) >= 5000
    assert int(variables["GDW_OWNER_MAX_ACTIVE_REQUESTS"]) >= 50000
    assert int(variables["GDW_GLOBAL_MAX_ACTIVE_SESSIONS"]) >= int(
        variables["GDW_OWNER_MAX_ACTIVE_SESSIONS"]
    )
    assert int(variables["GDW_GLOBAL_MAX_ACTIVE_REQUESTS"]) >= int(
        variables["GDW_OWNER_MAX_ACTIVE_REQUESTS"]
    )
    # The real storage guard is unchanged: capacity is still bounded.
    assert variables["GDW_OWNER_MAX_STORED_BYTES"] == "268435456"
    assert variables["GDW_EFFECT_MAX_ATTEMPTS"] == "20"
    assert variables["GDW_POLICY_ORIGIN"] == "http://127.0.0.1:7860"


def test_plan_variables_reports_only_drift_and_rejects_collisions() -> None:
    desired = {"GDW_DB_PATH": "/data/gdw.sqlite3", "GDW_SQLITE_JOURNAL": "DELETE"}
    current = {"GDW_SQLITE_JOURNAL": SimpleNamespace(value="DELETE")}
    assert config.plan_variables(current, set(), desired) == {
        "GDW_DB_PATH": "/data/gdw.sqlite3"
    }
    with pytest.raises(config.RuntimeConfigError, match="collide"):
        config.plan_variables({}, {"GDW_DB_PATH"}, desired)


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
        required = {config.CREDENTIAL_REGISTRY_SECRET, SIGNING_SECRET}
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
        return self.metadata("volumes", repo_id, SimpleNamespace(runtime=SimpleNamespace(
            volumes=[SimpleNamespace(type="bucket", source="SZLHOLDINGS/szl-evidence",
                                     mount_path="/data", read_only=False)])))

    def __getattr__(self, name):
        if name.startswith(("add_", "delete_", "set_", "update_", "restart_", "pause_")):
            def denied(*_args, **_kwargs):
                self.writes.append(name)
                raise AssertionError("prerequisites must not attempt provider mutations")
            return denied
        raise AttributeError(name)


def assert_setup_required(report, api, diagnostic_code="INSTALLED_AUTHORITY_UNKNOWN"):
    assert report["schema"] == "szl.hf-gdw-runtime-config/v1"
    assert report["repo_id"] == config.CANONICAL_SPACE
    assert report["state"] == "SETUP_REQUIRED"
    assert report["credential_authority_state"] == "UNKNOWN"
    assert report["diagnostic_code"] == diagnostic_code
    assert report["converged"] is False
    assert report["secret_values_read"] is False
    assert report["secret_values_written"] is False
    assert report.get("credential_registry_converged") is not True
    assert "synthetic-provider-private-detail" not in json.dumps(report)
    assert api.value_reads == []
    assert api.writes == []


@pytest.mark.parametrize("secret_names,diagnostic", [
    (set(), "SIGNING_SECRET_MISSING"),
    (None, "AUTHORITY_ORIGIN_UNAVAILABLE"),
    ({config.CREDENTIAL_REGISTRY_SECRET, "GDW_DB_PATH"}, "SIGNING_SECRET_MISSING"),
    ({SIGNING_SECRET}, "AUTHORITY_ORIGIN_UNAVAILABLE"),
])
def test_manual_registry_names_never_prove_authority(secret_names, diagnostic):
    api = MetadataOnlyApi(secret_names=secret_names)
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert_setup_required(report, api, diagnostic)
    present = {config.CREDENTIAL_REGISTRY_SECRET} if secret_names is None else secret_names
    assert report["required_secret_names"] == [config.CREDENTIAL_REGISTRY_SECRET]
    assert report["missing_secret_names"] == ([] if config.CREDENTIAL_REGISTRY_SECRET in present
                                               else [config.CREDENTIAL_REGISTRY_SECRET])
    assert {kind for kind, _ in api.reads} == {"secrets", "variables", "volumes"}


def test_pinned_runtime_key_and_registry_name_are_ready():
    api = MetadataOnlyApi()
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE, authority_get=pinned_get)
    assert report["state"] == "READY"
    assert report["converged"] is True
    assert report["credential_authority_state"] == "VERIFIED"
    assert report["diagnostic_code"] == "INSTALLED_AUTHORITY_VERIFIED"
    assert report["gdw_authority"]["state"] == "NAME_PRESENT_RUNTIME_PROVEN_DOWNSTREAM"
    assert report["installed_authority"]["github_public_reader"]["state"] == "PUBLIC_ANONYMOUS"
    assert report["installed_authority"]["live_git_sha"] is None  # /honest unavailable: informational only
    assert api.value_reads == [] and api.writes == []


def test_pinned_key_without_registry_name_is_blocking():
    api = MetadataOnlyApi(secret_names={SIGNING_SECRET})
    report = config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE, authority_get=pinned_get)
    assert_setup_required(report, api, "GDW_CREDENTIALS_MISSING")
    assert report["missing_secret_names"] == [config.CREDENTIAL_REGISTRY_SECRET]


def test_verified_gdw_check_only_cli_exits_zero(monkeypatch, tmp_path):
    api = MetadataOnlyApi()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda **_kwargs: api))
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    output = tmp_path / "gdw.json"
    assert config.main(["--check-only", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["state"] == "READY" and report["credential_authority_state"] == "VERIFIED"


@pytest.mark.parametrize("secret_names,variable_names", [
    (None, (config.CREDENTIAL_REGISTRY_SECRET,)),
    (None, (config.PRINCIPAL_REGISTRY_SECRET,)),
    ({config.PRINCIPAL_REGISTRY_SECRET}, ()),
    ({config.CREDENTIAL_REGISTRY_SECRET, config.PRINCIPAL_REGISTRY_SECRET}, ()),
])
def test_public_registry_collisions_and_legacy_conflicts_require_owner_resolution(secret_names,
                                                                                variable_names):
    api = MetadataOnlyApi(secret_names=secret_names, variable_names=variable_names)
    with pytest.raises(config.RuntimeConfigError, match="SETUP_REQUIRED") as error:
        config.manual_prerequisites(api, repo_id=config.CANONICAL_SPACE)
    assert error.value.diagnostic_code == ("PUBLIC_VARIABLE_COLLISION" if variable_names
                                           else "LEGACY_PRINCIPAL_CONFLICT")
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
def test_configure_refuses_unknown_authority_before_any_mutation(monkeypatch, check_only):
    api = MetadataOnlyApi(variable_names=config.STATIC_VARIABLES)
    monkeypatch.setitem(sys.modules, "huggingface_hub",
                        SimpleNamespace(HfApi=lambda **_kwargs: api))
    kwargs = {"repo_id": config.CANONICAL_SPACE, "hf_token": "synthetic-hf-control",
              "check_only": check_only}
    if check_only:
        assert_setup_required(config.configure(**kwargs), api, "AUTHORITY_ORIGIN_UNAVAILABLE")
    else:
        with pytest.raises(config.RuntimeConfigError) as error:
            config.configure(**kwargs)
        assert "synthetic-provider-private-detail" not in str(error.value)
    assert api.value_reads == []
    assert api.writes == []


@pytest.mark.parametrize("failing_read", [None, "secrets", "variables", "volumes", "client"])
def test_check_only_cli_emits_bounded_failed_report_without_operator_token(monkeypatch, tmp_path,
                                                                          capsys, failing_read):
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
        if name == "GDW_OPERATOR_TOKEN":
            raise AssertionError("manual prerequisites must not read the operator credential")
        return default

    monkeypatch.setattr(config.os.environ, "get", environment)
    output = tmp_path / "gdw-prerequisites.json"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--check-only", "--output", str(output)])
    code = config.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert type(code) is int and code != 0
    assert json.loads(capsys.readouterr().out) == report
    assert output.stat().st_size < 16384
    assert "GDW_OPERATOR_TOKEN" not in env_reads
    expected = {None: "AUTHORITY_ORIGIN_UNAVAILABLE", "client": "SPACE_CLIENT_UNAVAILABLE",
                "secrets": "CREDENTIAL_METADATA_UNAVAILABLE",
                "variables": "CREDENTIAL_METADATA_UNAVAILABLE",
                "volumes": "PERSISTENT_STORAGE_UNAVAILABLE"}
    assert_setup_required(report, api, expected[failing_read])


def test_nonsecret_readback_accepts_only_bounded_convergence():
    desired = {"GDW_DB_PATH": "/data/gdw.sqlite3"}
    snapshots = [{}, {"GDW_DB_PATH": SimpleNamespace(value=desired["GDW_DB_PATH"])}]
    api = SimpleNamespace(get_space_variables=lambda **_kwargs: snapshots.pop(0))
    sleeps = []
    assert config.await_readback(api, repo_id=config.CANONICAL_SPACE,
                                 secret_names=set(), desired=desired, attempts=2,
                                 delay_seconds=0, sleep=sleeps.append) == 2
    assert sleeps == [0]
    assert snapshots == []


def test_nonsecret_readback_preserves_failure_at_attempt_bound():
    reads = []
    api = SimpleNamespace(get_space_variables=lambda **kwargs: reads.append(kwargs) or {})
    sleeps = []
    with pytest.raises(config.RuntimeConfigError, match="did not converge"):
        config.await_readback(api, repo_id=config.CANONICAL_SPACE, secret_names=set(),
                              desired={"GDW_DB_PATH": "/data/gdw.sqlite3"}, attempts=2,
                              delay_seconds=0, sleep=sleeps.append)
    assert len(reads) == 2
    assert sleeps == [0]


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


@pytest.mark.parametrize("volumes", [
    [SimpleNamespace(mount_path="/data", read_only=True)],
    [SimpleNamespace(mount_path="/data", read_only=None)],
    [SimpleNamespace(mount_path="/data")],
    [SimpleNamespace(mount_path="/data", read_only=False),
     SimpleNamespace(mount_path="/data", read_only=False)],
])
def test_data_mount_writable_state_must_be_known_and_single(volumes):
    api = SimpleNamespace(space_info=lambda **_kwargs:
                          SimpleNamespace(runtime=SimpleNamespace(volumes=volumes)))
    with pytest.raises(config.RuntimeConfigError):
        config.require_data_mount(api, repo_id=config.CANONICAL_SPACE)


def test_data_mount_report_never_inspects_unneeded_topology_values():
    value_reads = []
    volume = SimpleNamespace(mount_path="/data", read_only=False,
                             type=OpaqueMetadata(value_reads), source=OpaqueMetadata(value_reads))
    api = SimpleNamespace(space_info=lambda **_kwargs:
                          SimpleNamespace(runtime=SimpleNamespace(volumes=[volume])))
    assert config.require_data_mount(api, repo_id=config.CANONICAL_SPACE) == {
        "mount_path": "/data", "read_only": False}
    assert value_reads == []
