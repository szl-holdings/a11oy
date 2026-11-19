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


@pytest.mark.parametrize("mode", ["private-dataset-v1", "unknown-successor"])
def test_legacy_plan_cannot_downgrade_activated_durable_storage(mode):
    with pytest.raises(config.RuntimeConfigError, match="cannot be replaced"):
        config.plan_variables({"GDW_DURABLE_STORAGE": {"value": mode}}, set(), config.desired_variables())


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
    api = ConvergedRuntimeApi()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda **_kwargs: api))
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    output = tmp_path / "gdw.json"
    assert config.main(["--check-only", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["state"] == "READY" and report["credential_authority_state"] == "VERIFIED"
    assert report["variables_managed"] == sorted(config.STATIC_VARIABLES)
    assert report["readback_attempts"] == 1 and api.writes == []


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
              "check_only": check_only, "expected_source_sha": "a" * 40,
              "main_reader": lambda: "a" * 40}
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


@pytest.mark.parametrize("mode", ["durable-private-dataset-v1", "unknown-successor"])
def test_legacy_plan_preserves_guard_before_managed_variables_exist(mode):
    with pytest.raises(config.RuntimeConfigError, match="cannot be replaced"):
        config.plan_variables(
            {"GDW_PROOF_EXPORT_MODE": {"value": mode}}, set(),
            {"GDW_PROOF_EXPORT_MODE": "outbox"},
        )


def test_managed_observation_reads_secret_names_only():
    api = MetadataOnlyApi(secret_names=config.MANAGED_SECRET_NAMES)
    api.variables = {"GDW_PROOF_EXPORT_MODE": SimpleNamespace(value="outbox")}
    api.space_info = lambda **_kwargs: SimpleNamespace(
        sha="c" * 40, runtime=SimpleNamespace(stage="PAUSED"))
    observed = config.managed_space_observation(api)
    assert observed["stage"] == "PAUSED"
    assert observed["secret_names"] == sorted(config.MANAGED_SECRET_NAMES)
    assert observed["variables"] == {"GDW_PROOF_EXPORT_MODE": "outbox"}
    assert len(observed["variables_sha256"]) == 64
    assert not api.value_reads and not api.writes


@pytest.mark.parametrize("credential", sorted(config.MANAGED_SECRET_NAMES))
def test_managed_observation_rejects_public_credential_without_reading_value(credential):
    api = MetadataOnlyApi(secret_names=config.MANAGED_SECRET_NAMES,
                          variable_names=[credential])
    api.space_info = lambda **_kwargs: SimpleNamespace(
        sha="c" * 40, runtime=SimpleNamespace(stage="PAUSED"))
    with pytest.raises(config.RuntimeConfigError):
        config.managed_space_observation(api)
    assert not api.value_reads and not api.writes


@pytest.mark.parametrize("worker_request", [
    {"operation": "set_variable"}, {"operation": "observe", "apply": True},
    {"operation": "restart"}, {"operation": "observe", "repo_id": "other/space"},
])
def test_unadmitted_worker_operations_rejected_before_process(worker_request, monkeypatch):
    monkeypatch.setattr(config.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("unadmitted process"))
    with pytest.raises(config.RuntimeConfigError):
        config.managed_worker_call(worker_request, deadline=config.time.monotonic() + 2)


def _native_worker(monkeypatch, source):
    original = config.subprocess.Popen
    observed = []
    def launch(command, **kwargs):
        observed.append(command)
        assert command == [sys.executable, "-I", "-B", str(SCRIPT.resolve()), "--managed-worker"]
        assert kwargs["start_new_session"] is True
        return original([sys.executable, "-I", "-B", "-c", source], **kwargs)
    monkeypatch.setattr(config.subprocess, "Popen", launch)
    return observed


def test_native_managed_worker_success_uses_fixed_entrypoint_and_protocol(monkeypatch):
    observed = _native_worker(monkeypatch, '''import sys,json
assert json.load(sys.stdin)=={"operation":"observe"}
print('{"ok":true,"value":{"fixture":"metadata"}}')
''')
    assert config.managed_worker_call({"operation": "observe"},
        deadline=config.time.monotonic() + 2) == {"fixture": "metadata"}
    assert len(observed) == 1


@pytest.mark.parametrize("source", [
    "import time; time.sleep(10)",
    "import sys; sys.stdout.write('x'*200000); sys.stdout.flush()",
    "print('{\"ok\":true,\"ok\":true,\"value\":{}}')",
    "print('private-provider-error-canary'); raise SystemExit(1)",
])
def test_native_managed_worker_timeout_oversize_and_bad_output_never_retry(monkeypatch, source):
    observed = _native_worker(monkeypatch, source)
    started = config.time.monotonic()
    with pytest.raises(config.RuntimeConfigError) as caught:
        config.managed_worker_call({"operation": "observe"}, deadline=started + .15)
    assert config.time.monotonic() - started < 2
    assert "private-provider-error-canary" not in str(caught.value)
    assert len(observed) == 1


def test_native_managed_worker_kills_descendant_after_parent_exit(monkeypatch, tmp_path):
    target = tmp_path / "escaped"
    child = "import time,pathlib; time.sleep(.5); pathlib.Path(" + repr(str(target)) + ").write_text('unsafe')"
    source = "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr(child) + "])"
    _native_worker(monkeypatch, source)
    with pytest.raises(config.RuntimeConfigError):
        config.managed_worker_call({"operation": "observe"}, deadline=config.time.monotonic() + .1)
    config.time.sleep(.6)
    assert not target.exists()


def _managed_proof_fixture():
    admission = {"source": {"revision": "a" * 40},
                 "qualification": {"report_sha256": "b" * 64},
                 "snapshots": {"gdw": {"generation": "c" * 32},
                               "series_a": {"generation": "store_" + "d" * 32}}}
    value = {"operation_id": "e" * 32, "kind": "COMMIT", "epoch": 2,
             "qualification_sha256": "f" * 64, "source_revision": "a" * 40,
             "snapshots": admission["snapshots"]}
    head = SimpleNamespace(revision="1" * 40, body=b"exact-native-manifest", value=value)
    calls = []
    def read_at(revision, operation, deadline):
        calls.append((revision, operation, deadline))
        return head, head.body
    backend = SimpleNamespace(read_at=read_at)
    context = config.ManagedProofContext(admission, "f" * 64, backend,
                                        deadline=config.time.monotonic() + 10)
    witness = {"schema": "szl.gdw-managed-runtime/v1", "mode": config.MANAGED_MODE,
               **context.identity, "dataset_revision": head.revision,
               "operation_id": value["operation_id"], "writer_epoch": 2,
               "actual_host_full_state_ack_ms": 500,
               "startup_state": "RESTORED_AND_ACKNOWLEDGED", "throughput_claim": "NOT_CLAIMED"}
    return context, witness, head, backend, calls


def test_managed_proof_reads_exact_immutable_history_and_detaches_result():
    context, witness, head, backend, calls = _managed_proof_fixture()
    result = context.validate(witness, label="gdw", generation="c" * 32)
    assert calls[0][:2] == (head.revision, head.value["operation_id"])
    result["generations"]["gdw"] = "changed"
    assert context.identity["generations"]["gdw"] == "c" * 32
    assert context.latest_witness["generations"]["gdw"] == "c" * 32
    context.close()
    with pytest.raises(config.RuntimeConfigError):
        context.validate(witness, label="gdw", generation="c" * 32)
    assert len(calls) == 1


@pytest.mark.parametrize("field,value", [
    ("mode", "legacy"), ("source_revision", "2" * 40),
    ("admission_sha256", "3" * 64), ("qualification_sha256", "f" * 64),
    ("dataset_revision", "0" * 40), ("operation_id", "short"),
    ("writer_epoch", True), ("writer_epoch", 0),
    ("actual_host_full_state_ack_ms", True), ("actual_host_full_state_ack_ms", 60001),
    ("startup_state", "PLANNED"), ("throughput_claim", "MEASURED"),
    ("generations", {"gdw": "c" * 32, "series_a": "store_" + "9" * 32}),
])
def test_unqualified_managed_witness_rejected_before_provider_read(field, value):
    context, witness, head, backend, calls = _managed_proof_fixture()
    witness[field] = value
    with pytest.raises(config.RuntimeConfigError):
        context.validate(witness, label="gdw", generation="c" * 32)
    assert calls == []


@pytest.mark.parametrize("mismatch", ["history", "revision", "operation", "epoch", "admission", "source", "generation", "bootstrap"])
def test_managed_witness_must_match_native_acknowledged_head(mismatch):
    context, witness, head, backend, calls = _managed_proof_fixture()
    if mismatch == "history":
        backend.read_at = lambda *_args: (head, b"other-history")
    elif mismatch == "revision": head.revision = "2" * 40
    elif mismatch == "operation": head.value["operation_id"] = "2" * 32
    elif mismatch == "epoch": head.value["epoch"] = 3
    elif mismatch == "admission": head.value["qualification_sha256"] = "2" * 64
    elif mismatch == "source": head.value["source_revision"] = "2" * 40
    elif mismatch == "generation": head.value["snapshots"]["series_a"]["generation"] = "store_" + "2" * 32
    else: head.value["kind"] = "BOOTSTRAP"
    with pytest.raises(config.RuntimeConfigError):
        context.validate(witness, label="gdw", generation="c" * 32)
    assert context.latest_witness is None


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "oversize", "empty", "directory"])
def test_acquisition_locator_must_be_bounded_owned_regular_file(tmp_path, monkeypatch, kind):
    path = tmp_path / "locator.json"
    if kind == "directory": path.mkdir()
    else:
        original = tmp_path / "original.json"
        original.write_bytes(b'x' * (16385 if kind == "oversize" else 1))
        if kind == "symlink": path.symlink_to(original)
        elif kind == "hardlink": path.hardlink_to(original)
        else:
            original.rename(path)
            if kind == "empty": path.write_bytes(b'')
    monkeypatch.setattr(config, "_load_managed_module", lambda *_a: pytest.fail("unsafe locator parsed"))
    monkeypatch.setattr(config, "_verified_managed_admission", lambda *_a, **_kw: pytest.fail("unsafe locator caused provider read"))
    with pytest.raises(config.RuntimeConfigError):
        config.load_managed_proof_context(path, source_revision="a" * 40,
                                          deadline=config.time.monotonic() + 2)


def test_local_locator_without_source_owned_parser_cannot_grant_managed_authority(tmp_path, monkeypatch):
    path = tmp_path / "locator.json"
    path.write_bytes(b'{"state":"BOOTSTRAP_ACKNOWLEDGED"}\n')
    def unavailable(*_args):
        raise OSError("synthetic-private-error")
    monkeypatch.setattr(config, "_load_managed_module", unavailable)
    monkeypatch.setattr(config, "_verified_managed_admission", lambda *_a, **_kw: pytest.fail("unparsed locator caused provider read"))
    with pytest.raises(config.RuntimeConfigError) as caught:
        config.load_managed_proof_context(path, source_revision="a" * 40,
                                          deadline=config.time.monotonic() + 2)
    assert "synthetic-private-error" not in str(caught.value)


def _admitted_configuration_fixture(monkeypatch):
    import hashlib
    import gdw_durable_guard as guard
    monkeypatch.setattr(config, "_managed_require_main", lambda *_a: None)
    variables = {"GDW_PROOF_EXPORT_MODE": "outbox", "GDW_SQLITE_JOURNAL": "DELETE"}
    names = sorted(guard.REQUIRED_SECRETS)
    sha = lambda value: hashlib.sha256(guard.canonical(value)).hexdigest()
    legacy = {"schema": guard.SCHEMA, "state": "QUALIFIED_LEGACY_STARTUP_GUARD", "space_revision": guard.SPACE_REVISION,
        "image": guard.IMAGE, "command": ["python", "gdw_runtime.py"], "working_directory": "/app",
        "source_files_sha256": dict(guard.SOURCE_FILES),
        "observation": {"stage": "PAUSED", "observed_at": "2026-10-04T20:00:00Z", "public_variables_sha256": sha(variables),
            "secret_names_sha256": sha(names), "startup_overrides_absent": True},
        "native_probe": {"state": "PREWRITE_REJECTION_VERIFIED", "scope": guard.PROBE_SCOPE, "python_version": "3.14.0",
            "case_count": len(guard.CASES), "case_results_sha256": "1" * 64, "report_sha256": "2" * 64,
            "source_closure_sha256": sha(guard.SOURCE_FILES), "forbidden_effect_count": 0,
            "unguarded_control": "PREPARATION_WRITE_OBSERVED"}}
    admission = {"legacy_guard": legacy}
    locator = {"source_revision": "a" * 40, "admission_sha256": "b" * 64, "qualification_sha256": "c" * 64,
        "generations": {"gdw": "d" * 32, "series_a": "store_" + "e" * 32}, "source_manifest_sha256": "f" * 64,
        "dataset_revision": "1" * 40, "operation_id": "2" * 32, "legacy_guard_sha256": sha(legacy)}
    head = SimpleNamespace(body=b"immutable-bootstrap", value={"kind": "BOOTSTRAP"})
    backend = SimpleNamespace(read_at=lambda *_a: (head, head.body), observe=lambda *_a: head)
    class Api:
        stage = "PAUSED"
        source = guard.SPACE_REVISION
        def __init__(self): self.variables = dict(variables); self.names = list(names); self.writes = []; self.uncertain = False
        def space_info(self, **kwargs): return SimpleNamespace(sha=self.source, runtime=SimpleNamespace(stage=self.stage))
        def get_space_variables(self, **kwargs): return {k: SimpleNamespace(value=v) for k,v in self.variables.items()}
        def get_space_secrets(self, **kwargs): return NamesOnlyMetadata(self.names, [])
        def add_space_variable(self, **kwargs):
            assert kwargs["repo_id"] == config.CANONICAL_SPACE
            self.writes.append((kwargs["key"], kwargs["value"]))
            self.variables[kwargs["key"]] = kwargs["value"]
            self.stage = "RUNTIME_ERROR"
            if self.uncertain: raise OSError("synthetic-provider-private-detail")
    return Api(), admission, locator, head, backend, guard


def test_managed_configuration_installs_guard_first_and_never_claims_runtime_authority(monkeypatch):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    result = config._configure_admitted_managed_storage(api, admission, locator, head, backend,
        deadline=config.time.monotonic() + 3, check_only=False)
    assert api.writes[0] == ("GDW_PROOF_EXPORT_MODE", guard.EXPORT_GUARD)
    assert dict(api.writes) == {k:v for k,v in guard.MANAGED_VARIABLES.items() if k != "GDW_SQLITE_JOURNAL"}
    assert result["state"] == "CONFIGURATION_VERIFIED" and result["converged"] is True
    assert result["credential_authority_state"] == "SIGNING_AUTHORITY_UNPROVEN_UNTIL_STARTUP"
    assert result["legacy_resume_allowed"] is False and result["runtime_proven"] is False
    assert result["persistent_export_guard"] == guard.EXPORT_GUARD
    assert not result["secret_values_read"] and not result["secret_values_written"] and not result["volumes_mutated"]
    assert "variables" not in result


def test_managed_configuration_check_only_never_constructs_runtime_proof(monkeypatch):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    result = config._configure_admitted_managed_storage(api, admission, locator, head, backend,
        deadline=config.time.monotonic() + 3, check_only=True)
    assert result["state"] == "ADMISSION_VERIFIED_CONFIGURATION_PENDING"
    assert result["converged"] is False and result["runtime_proven"] is False
    assert api.writes == []


@pytest.mark.parametrize("defect", ["running", "source", "missing_secret", "already_claimed", "history", "changed_head", "expired", "local_python_only"])
def test_managed_configuration_refuses_unqualified_baseline_before_guard(monkeypatch, defect):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    deadline = config.time.monotonic() + 3
    if defect == "running": api.stage = "RUNNING"
    elif defect == "source": api.source = "f" * 40
    elif defect == "missing_secret": api.names.remove("HF_TOKEN")
    elif defect == "already_claimed": head.value["kind"] = "CLAIM"
    elif defect == "history": backend.read_at = lambda *_a: (head, b"other-history")
    elif defect == "changed_head": backend.observe = lambda *_a: SimpleNamespace(body=b"other-head")
    elif defect == "expired": deadline = config.time.monotonic() - 1
    else: admission["legacy_guard"]["native_probe"]["python_version"] = "3.12.14"
    with pytest.raises(RuntimeError):
        config._configure_admitted_managed_storage(api, admission, locator, head, backend,
            deadline=deadline, check_only=False)
    assert api.writes == []


def test_accepted_variable_with_lost_reply_is_not_retried_or_rolled_back(monkeypatch):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    api.uncertain = True
    with pytest.raises(config.RuntimeConfigError) as caught:
        config._configure_admitted_managed_storage(api, admission, locator, head, backend,
            deadline=config.time.monotonic() + 3, check_only=False)
    assert caught.value.diagnostic_code == "MANAGED_OUTCOME_UNCERTAIN"
    assert api.writes == [("GDW_PROOF_EXPORT_MODE", guard.EXPORT_GUARD)]
    assert api.variables["GDW_PROOF_EXPORT_MODE"] == guard.EXPORT_GUARD
    assert "synthetic-provider-private-detail" not in str(caught.value)


def test_post_guard_source_change_stops_all_remaining_configuration(monkeypatch):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    original = api.add_space_variable
    def change_source(**kwargs): original(**kwargs); api.source = "f" * 40
    api.add_space_variable = change_source
    with pytest.raises(RuntimeError):
        config._configure_admitted_managed_storage(api, admission, locator, head, backend,
            deadline=config.time.monotonic() + 3, check_only=False)
    assert api.writes == [("GDW_PROOF_EXPORT_MODE", guard.EXPORT_GUARD)]


@pytest.fixture
def legacy_source_directory():
    # Provider-source bytes are an explicit external fixture, never fetched by
    # the unit suite. Canonical acquisition supplies and revalidates these bytes.
    supplied = config.os.environ.get("GDW_LEGACY_TEST_SOURCE_DIRECTORY")
    if not supplied:
        pytest.skip("exact deployed source fixture requires GDW_LEGACY_TEST_SOURCE_DIRECTORY")
    directory = Path(supplied)
    assert directory.is_dir()
    return directory


def test_native_legacy_guard_all_cases_and_control_use_exact_deployed_bytes(legacy_source_directory):
    rules = config._legacy_guard_rules()
    result = config.legacy_guard_probe(legacy_source_directory,
        variables={}, secret_names=sorted(rules.REQUIRED_SECRETS), deadline=config.time.monotonic() + 15)
    assert result["schema"] == "szl.gdw-legacy-guard-probe/v1"
    assert result["state"] == "PREWRITE_REJECTION_VERIFIED"
    assert result["python_version"] == ".".join(str(v) for v in sys.version_info[:3])
    assert result["scope"] == "SOURCE_IMPORTS_AND_ENTRYPOINT_AFTER_INTERPRETER_INITIALIZATION"
    assert result["source_files_sha256"] == rules.SOURCE_FILES
    assert result["source_closure_sha256"] == config.hashlib.sha256(rules.canonical(rules.SOURCE_FILES)).hexdigest()
    assert result["cases"] == [{"name": name, "state": "PREWRITE_REJECTION_VERIFIED",
                                "forbidden_effect_count": 0} for name in rules.CASES]
    assert result["unguarded_control"] == "PREPARATION_WRITE_OBSERVED"
    assert result["total_forbidden_effect_count"] == 0


@pytest.mark.parametrize("defect", ["changed", "missing", "symlink", "hardlink"])
def test_legacy_source_drift_rejected_before_worker(legacy_source_directory, tmp_path, monkeypatch, defect):
    rules = config._legacy_guard_rules()
    for name in rules.SOURCE_FILES:
        (tmp_path / name).write_bytes((legacy_source_directory / name).read_bytes())
    target = tmp_path / "gdw_runtime.py"
    if defect == "changed":
        target.write_bytes(target.read_bytes() + b"\n# changed source\n")
    elif defect == "missing":
        target.unlink()
    else:
        original = tmp_path / "original.py"
        target.rename(original)
        if defect == "symlink": target.symlink_to(original)
        else: target.hardlink_to(original)
    monkeypatch.setattr(config, "_legacy_guard_child", lambda *_a, **_k: pytest.fail("drifted source executed"))
    with pytest.raises(config.RuntimeConfigError):
        config.legacy_guard_probe(tmp_path, variables={}, secret_names=sorted(rules.REQUIRED_SECRETS),
                                  deadline=config.time.monotonic() + 2)


@pytest.mark.parametrize("name", ["PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "LD_PRELOAD",
                                  "PATH", "HOME", "USER", "SHELL", "ENV", "BASH_ENV"])
@pytest.mark.parametrize("location", ["variables", "secret_names"])
def test_legacy_probe_startup_overrides_rejected_before_sources_or_worker(monkeypatch, tmp_path, name, location):
    names = sorted(config.MANAGED_SECRET_NAMES)
    variables = {}
    if location == "variables": variables[name] = "untrusted"
    else: names.append(name)
    monkeypatch.setattr(config, "_legacy_guard_sources", lambda *_a: pytest.fail("unsafe environment read source"))
    monkeypatch.setattr(config, "_legacy_guard_child", lambda *_a, **_k: pytest.fail("unsafe environment executed"))
    with pytest.raises(config.RuntimeConfigError):
        config.legacy_guard_probe(tmp_path, variables=variables, secret_names=names,
                                  deadline=config.time.monotonic() + 2)


def _native_legacy_worker(monkeypatch, source):
    original = config.subprocess.Popen
    observed = []

    def launch(command, **kwargs):
        observed.append(command)
        assert command == [sys.executable, "-I", "-B", str(SCRIPT.resolve()), "--legacy-guard-worker"]
        assert kwargs["start_new_session"] is True
        assert kwargs["env"] == {"PATH": config.os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        return original([sys.executable, "-I", "-B", "-c", source], **kwargs)

    monkeypatch.setattr(config.subprocess, "Popen", launch)
    return observed


def test_native_legacy_worker_does_not_inherit_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_TOKEN", "inherited-secret-canary")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "another-secret-canary")
    source = '''import sys,json,os
assert 'HF_TOKEN' not in os.environ and 'AWS_SECRET_ACCESS_KEY' not in os.environ
assert json.load(sys.stdin)=={"case":"fixture"}
print('{"ok":true,"value":{"fixture":"clean"}}')
'''
    observed = _native_legacy_worker(monkeypatch, source)
    assert config._legacy_guard_child({"case": "fixture"}, directory=tmp_path,
                                     deadline=config.time.monotonic() + 2) == {"fixture": "clean"}
    assert len(observed) == 1


@pytest.mark.parametrize("source", [
    "import time; time.sleep(10)",
    "import sys; sys.stdout.write('x'*20000); sys.stdout.flush()",
    "print('{\"ok\":true,\"ok\":true,\"value\":{}}')",
    "print('private-provider-error-canary'); raise SystemExit(1)",
])
def test_native_legacy_worker_time_output_and_protocol_are_bounded(monkeypatch, tmp_path, source):
    observed = _native_legacy_worker(monkeypatch, source)
    started = config.time.monotonic()
    with pytest.raises(config.RuntimeConfigError) as caught:
        config._legacy_guard_child({}, directory=tmp_path, deadline=started + .15)
    assert config.time.monotonic() - started < 2
    assert "private-provider-error-canary" not in str(caught.value)
    assert len(observed) == 1


def test_native_legacy_worker_kills_descendant_after_parent_exit(monkeypatch, tmp_path):
    target = tmp_path / "escaped"
    child = "import time,pathlib; time.sleep(.5); pathlib.Path(" + repr(str(target)) + ").write_text('unsafe')"
    source = "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr(child) + "])"
    _native_legacy_worker(monkeypatch, source)
    with pytest.raises(config.RuntimeConfigError):
        config._legacy_guard_child({}, directory=tmp_path, deadline=config.time.monotonic() + .1)
    config.time.sleep(.6)
    assert not target.exists()


@pytest.mark.parametrize("effect", [
    "", "open('forbidden', 'w').write('x')", "import os; os.mkdir('forbidden')",
    "import sqlite3; sqlite3.connect(':memory:')", "import socket; socket.socket()",
    "import subprocess; subprocess.Popen(['not-an-authorized-program'])", "import os; os.fork()",
    "import threading; threading.Thread(target=lambda: None).start()",
    "import _thread; _thread.start_new_thread(lambda: None, ())",
])
@pytest.mark.parametrize("stage", ["entrypoint", "import"])
def test_native_guard_audit_and_thread_interception_precede_entrypoint_effects(tmp_path, effect, stage):
    # Only this test launches an alternate Python bootstrap and patches source
    # pins to synthetic fixtures. The production dispatch accepts no such input.
    guard_error = "GDW_PROOF_EXPORT_MODE must be 'outbox'; synchronous export is not transaction-safe"
    if stage == "import":
        (tmp_path / "gdw_proofs.py").write_text(effect + "\n")
    execution = "import gdw_proofs" if stage == "import" else effect
    source = ("import os\nassert 'HF_TOKEN' not in os.environ\n" + execution + "\n"
              + "class GDWRuntimeError(RuntimeError): pass\nraise GDWRuntimeError(" + repr(guard_error) + ")\n")
    fixture = tmp_path / "gdw_runtime.py"
    fixture.write_text(source)
    pins = {"gdw_runtime.py": config.hashlib.sha256(fixture.read_bytes()).hexdigest()}
    if stage == "import":
        pins["gdw_proofs.py"] = config.hashlib.sha256((tmp_path / "gdw_proofs.py").read_bytes()).hexdigest()
    bootstrap = '''import importlib.util,json,pathlib,sys
spec=importlib.util.spec_from_file_location('legacy_fixture',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rules=module._legacy_guard_rules();rules.SOURCE_FILES=json.loads(sys.argv[2])
module._legacy_guard_rules=lambda:rules
raise SystemExit(module._legacy_guard_worker())
'''
    request = {"case": "default", "variables": {}, "secret_names": sorted(config.MANAGED_SECRET_NAMES)}
    result = config.subprocess.run([sys.executable, "-I", "-B", "-c", bootstrap, str(SCRIPT.resolve()), json.dumps(pins)],
        input=json.dumps(request).encode(), stdout=config.subprocess.PIPE, stderr=config.subprocess.PIPE,
        cwd=tmp_path, env={"PATH": config.os.defpath, "HF_TOKEN": "ambient-value-must-be-cleared"}, timeout=3)
    report = json.loads(result.stdout)
    if effect:
        assert result.returncode == 1 and report == {"ok": False, "code": "LEGACY_GUARD_PROBE_FAILED"}
        assert not (tmp_path / "forbidden").exists()
    else:
        assert result.returncode == 0 and report["ok"] is True
        assert report["value"]["state"] == "PREWRITE_REJECTION_VERIFIED"
        assert report["value"]["forbidden_effect_count"] == 0
    assert b"ambient-value" not in result.stdout + result.stderr


@pytest.mark.parametrize("remaining", [-1, 0, 121, float("nan"), float("inf")])
def test_legacy_probe_deadline_is_bounded_before_source_read(monkeypatch, tmp_path, remaining):
    monkeypatch.setattr(config, "_legacy_guard_sources", lambda *_a: pytest.fail("unbounded deadline read source"))
    with pytest.raises(config.RuntimeConfigError):
        config.legacy_guard_probe(tmp_path, variables={}, secret_names=sorted(config.MANAGED_SECRET_NAMES),
                                  deadline=config.time.monotonic() + remaining)


@pytest.mark.parametrize("arguments", [["--source-sha", "a" * 40], ["--managed-acquisition", "missing.json"]])
def test_incomplete_managed_cli_never_falls_back_to_legacy(monkeypatch, capsys, arguments):
    monkeypatch.setattr(config, "configure", lambda **_kw: pytest.fail("legacy configuration reached"))
    monkeypatch.setattr(config, "configure_managed", lambda *_a, **_kw: pytest.fail("incomplete managed request reached"))
    assert config.main(arguments) == 1
    assert json.loads(capsys.readouterr().out)["diagnostic_code"] == "MANAGED_STORAGE_UNAVAILABLE"


def test_managed_cli_uses_single_explicit_pair_attempt_and_pending_is_not_success(monkeypatch, capsys):
    calls = []
    def admitted(*args, **kwargs):
        calls.append((args, kwargs))
        return {"state": "ADMISSION_VERIFIED_CONFIGURATION_PENDING", "converged": False}
    monkeypatch.setattr(config, "configure_managed", admitted)
    monkeypatch.setattr(config, "configure", lambda **_kw: pytest.fail("legacy configuration reached"))
    assert config.main(["--managed-acquisition", "locator.json", "--source-sha", "a" * 40, "--check-only"]) == 1
    assert len(calls) == 1 and calls[0][0] == (Path("locator.json"),)
    assert calls[0][1]["source_revision"] == "a" * 40 and calls[0][1]["check_only"] is True
    assert calls[0][1]["repo_id"] == config.CANONICAL_SPACE


@pytest.mark.parametrize("defect", ["source", "destination", "flag", "past", "future", "nan"])
def test_managed_parent_refuses_invalid_scope_before_locator_read(monkeypatch, defect):
    kwargs = {"source_revision": "a" * 40, "repo_id": config.CANONICAL_SPACE,
              "check_only": False, "deadline": config.time.monotonic() + 2}
    if defect == "source": kwargs["source_revision"] = "0" * 40
    elif defect == "destination": kwargs["repo_id"] = "other/space"
    elif defect == "flag": kwargs["check_only"] = "false"
    elif defect == "past": kwargs["deadline"] = config.time.monotonic() - 1
    elif defect == "future": kwargs["deadline"] = config.time.monotonic() + 121
    else: kwargs["deadline"] = float("nan")
    monkeypatch.setattr(config, "_read_acquisition_locator", lambda *_a: pytest.fail("invalid scope read locator"))
    with pytest.raises(config.RuntimeConfigError): config.configure_managed(Path("absent"), **kwargs)


@pytest.mark.parametrize("code", ["MANAGED_STORAGE_UNAVAILABLE", "MANAGED_OUTCOME_UNCERTAIN"])
def test_native_managed_worker_fixed_failure_retains_uncertainty(monkeypatch, code):
    calls = _native_worker(monkeypatch, f'import sys; print(\'{{"ok":false,"code":"{code}"}}\'); sys.exit(1)')
    with pytest.raises(config.RuntimeConfigError) as caught:
        config.managed_worker_call({"operation": "observe"}, deadline=config.time.monotonic() + 2)
    assert caught.value.diagnostic_code == code and len(calls) == 1


def test_changed_worker_deadline_is_rejected_before_process(monkeypatch):
    deadline = config.time.monotonic() + 2
    request = {"operation": "configure", "locator": {}, "source_revision": "a" * 40,
               "check_only": False, "deadline": deadline + 1}
    monkeypatch.setattr(config.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("deadline changed"))
    with pytest.raises(config.RuntimeConfigError): config.managed_worker_call(request, deadline=deadline)


def test_guarded_configuration_cannot_be_retried_against_old_baseline(monkeypatch):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    config._configure_admitted_managed_storage(api, admission, locator, head, backend,
        deadline=config.time.monotonic() + 3, check_only=False)
    first_writes = list(api.writes)
    with pytest.raises(RuntimeError):
        config._configure_admitted_managed_storage(api, admission, locator, head, backend,
            deadline=config.time.monotonic() + 3, check_only=False)
    assert api.writes == first_writes


def test_native_managed_worker_receives_only_existing_control_credential(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "synthetic-control")
    monkeypatch.setenv("GDW_CREDENTIALS_JSON", "synthetic-must-not-inherit")
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", "synthetic-must-not-inherit")
    monkeypatch.setenv("PYTHONPATH", "synthetic-must-not-inherit")
    source = ('import os,json; assert os.environ.get("HF_TOKEN")=="synthetic-control"; '
              'assert not any(k in os.environ for k in ("GDW_CREDENTIALS_JSON","SZL_COSIGN_PRIVATE_PEM","PYTHONPATH")); '
              'print(json.dumps({"ok":True,"value":{"credential_scope":"CONTROL_ONLY"}}))')
    calls = _native_worker(monkeypatch, source)
    assert config.managed_worker_call({"operation": "observe"}, deadline=config.time.monotonic() + 2) == {
        "credential_scope": "CONTROL_ONLY"}
    assert len(calls) == 1


@pytest.mark.parametrize("when", [0, 1, 2, 14])
def test_managed_configuration_rechecks_main_before_each_effect_and_final_success(monkeypatch, when):
    api, admission, locator, head, backend, guard = _admitted_configuration_fixture(monkeypatch)
    observed = []
    def ownership(source, deadline):
        assert source == locator["source_revision"]
        observed.append(len(api.writes))
        if len(observed) - 1 == when:
            raise config.RuntimeConfigError("synthetic main movement")
    monkeypatch.setattr(config, "_managed_require_main", ownership)
    with pytest.raises(config.RuntimeConfigError) as caught:
        config._configure_admitted_managed_storage(api, admission, locator, head, backend,
            deadline=config.time.monotonic() + 3, check_only=False)
    if when < 2: assert not api.writes
    else:
        assert api.writes[0] == ("GDW_PROOF_EXPORT_MODE", guard.EXPORT_GUARD)
        assert caught.value.diagnostic_code == "MANAGED_OUTCOME_UNCERTAIN"
    assert len(observed) == when + 1


@pytest.mark.parametrize("fault", ["missing_token", "moved", "error", "expired"])
def test_managed_main_requires_exact_fixed_repository_and_sanitizes_failure(monkeypatch, fault):
    monkeypatch.setenv("GH_TOKEN", "synthetic-existing-github-token" if fault != "missing_token" else "")
    calls = []
    def fetch(repository, token):
        calls.append(repository)
        assert repository == "szl-holdings/a11oy" and token == "synthetic-existing-github-token"
        if fault == "error": raise OSError("synthetic-secret-provider-detail")
        return "b" * 40 if fault == "moved" else "a" * 40
    monkeypatch.setattr(config, "_load_managed_module", lambda *_a: SimpleNamespace(fetch_main_sha=fetch))
    with pytest.raises(config.RuntimeConfigError) as caught:
        config._managed_require_main("a" * 40, config.time.monotonic() + (-1 if fault == "expired" else 2))
    assert "synthetic" not in str(caught.value)
    assert len(calls) == (0 if fault in {"missing_token", "expired"} else 1)


def test_native_configuration_worker_inherits_only_two_existing_control_credentials(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    monkeypatch.setenv("GH_TOKEN", "synthetic-gh-read")
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", "synthetic-must-not-inherit")
    source = ('import os,json; assert os.environ.get("HF_TOKEN")=="synthetic-hf-control"; '
              'assert os.environ.get("GH_TOKEN")=="synthetic-gh-read"; '
              'assert "GDW_OPERATOR_TOKEN" not in os.environ; '
              'print(json.dumps({"ok":True,"value":{"credential_scope":"CONTROL_AND_MAIN_READ"}}))')
    calls = _native_worker(monkeypatch, source)
    deadline = config.time.monotonic() + 2
    request = {"operation": "configure", "locator": {}, "source_revision": "a" * 40,
               "check_only": False, "deadline": deadline}
    assert config.managed_worker_call(request, deadline=deadline) == {"credential_scope": "CONTROL_AND_MAIN_READ"}
    assert len(calls) == 1



class ConvergedRuntimeApi(MetadataOnlyApi):
    def __init__(self):
        super().__init__()
        self.variables = {name: SimpleNamespace(value=value)
                          for name, value in config.STATIC_VARIABLES.items()}


def install_runtime_api(monkeypatch, api):
    def client(**kwargs):
        assert kwargs == {"endpoint": "https://huggingface.co", "token": "synthetic-hf-control"}
        return api
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=client))
    return {"repo_id": config.CANONICAL_SPACE, "hf_token": "synthetic-hf-control",
            "authority_get": pinned_get, "expected_source_sha": "a" * 40,
            "main_reader": lambda: "a" * 40}


def install_gdw_release_transport(monkeypatch, api, *, handler=None):
    import httpx
    # Reuse the owner's complete seven-store release fixture. The admitted
    # guard and transport below are its real production classes, not stubs.
    path = SCRIPT.with_name("test_configure_hf_series_a_runtime.py")
    spec = importlib.util.spec_from_file_location("_gdw_release_test_fixtures", path)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    owner = fixtures.config
    fixture = fixtures.ReleasedFixture(api)
    guard = fixture.guard()
    real_writer = owner.RuntimeMutationClient
    kwargs = install_runtime_api(monkeypatch, api)
    monkeypatch.setattr(config, "load_runtime_mutation_owner", lambda: owner)
    monkeypatch.setattr(owner, "ReleasedStateGuard", lambda observed_api: guard
                        if observed_api is api else pytest.fail("wrong metadata owner"))
    requests, writers = [], []

    def dispatch(request):
        assert request.method == "POST"
        assert str(request.url) == "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/variables"
        requests.append(request)
        if handler is not None:
            return handler(request, fixture)
        payload = json.loads(request.content)
        assert set(payload) == {"key", "value", "description"}
        assert payload["key"] in config.STATIC_VARIABLES
        api.variables[payload["key"]] = SimpleNamespace(value=payload["value"])
        api.writes.append((payload["key"], payload["value"]))
        return httpx.Response(200, json={})

    def writer_factory(token):
        writer = real_writer(token, transport=httpx.MockTransport(dispatch),
                             clock=lambda: fixture.clock)
        writers.append(writer)
        return writer
    monkeypatch.setattr(owner, "RuntimeMutationClient", writer_factory)
    return kwargs, fixture, guard, requests, writers


@pytest.mark.parametrize("name", sorted(config.STATIC_VARIABLES))
def test_verified_check_only_rejects_each_missing_gdw_variable_without_writes(monkeypatch, name):
    api = ConvergedRuntimeApi()
    del api.variables[name]
    kwargs = install_runtime_api(monkeypatch, api)
    monkeypatch.setattr(config, "load_runtime_mutation_owner",
                        lambda: pytest.fail("check-only created a mutation owner"))
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=True)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_DRIFT"
    assert name in str(error.value)
    assert [kind for kind, _ in api.reads].count("variables") == 2
    assert api.writes == [] and api.value_reads == []


@pytest.mark.parametrize("name", [
    "GDW_OWNER_MAX_ACTIVE_SESSIONS", "GDW_RETENTION_SECONDS", "GDW_TOMBSTONE_SECONDS",
    "GDW_EFFECT_MAX_ATTEMPTS", "GDW_EFFECT_BACKOFF_SECONDS", "GDW_POLICY_ORIGIN",
])
def test_check_only_verifies_gdw_contract_beyond_series_a_subset(monkeypatch, name):
    api = ConvergedRuntimeApi()
    api.variables[name] = SimpleNamespace(value="synthetic-private-drift")
    kwargs = install_runtime_api(monkeypatch, api)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=True)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_DRIFT"
    assert "synthetic-private-drift" not in str(error.value)
    assert api.writes == [] and api.value_reads == []


def test_check_only_readback_failure_is_sanitized(monkeypatch):
    api = ConvergedRuntimeApi()
    kwargs = install_runtime_api(monkeypatch, api)
    read = api.get_space_variables
    calls = []
    def unavailable(**arguments):
        calls.append(True)
        if len(calls) == 2:
            raise OSError("synthetic-provider-private-detail")
        return read(**arguments)
    monkeypatch.setattr(api, "get_space_variables", unavailable)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs, check_only=True)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_UNAVAILABLE"
    assert "synthetic-provider-private-detail" not in str(error.value)
    assert len(calls) == 2 and api.writes == []


@pytest.mark.parametrize("check_only", [False, True])
@pytest.mark.parametrize("barrier", ["secret-collision", "durable-storage", "export-mode"])
def test_full_parity_preserves_secret_and_legacy_barriers(monkeypatch, check_only, barrier):
    api = ConvergedRuntimeApi()
    if barrier == "secret-collision":
        api.secrets = NamesOnlyMetadata(
            [config.CREDENTIAL_REGISTRY_SECRET, SIGNING_SECRET, "GDW_POLICY_ORIGIN"], api.value_reads)
    elif barrier == "durable-storage":
        api.variables["GDW_DURABLE_STORAGE"] = SimpleNamespace(value="private-dataset-v1")
    else:
        api.variables["GDW_PROOF_EXPORT_MODE"] = SimpleNamespace(value="durable-private-dataset-v1")
    kwargs = install_runtime_api(monkeypatch, api)
    monkeypatch.setattr(config, "load_runtime_mutation_owner",
                        lambda: pytest.fail("blocked planning created a mutation owner"))
    with pytest.raises(config.RuntimeConfigError):
        config.configure(**kwargs, check_only=check_only)
    assert api.writes == [] and api.value_reads == []


def test_runtime_mutation_loader_reuses_exact_existing_owner():
    owner = config.load_runtime_mutation_owner()
    assert Path(owner.__file__).resolve() == SCRIPT.with_name("configure_hf_series_a_runtime.py").resolve()
    assert owner.CANONICAL_SPACE == config.CANONICAL_SPACE
    assert callable(owner.ReleasedStateGuard) and callable(owner.RuntimeMutationClient)



@pytest.mark.parametrize("check_only", [False, True])
def test_converged_active_runtime_needs_no_release_or_mutation(monkeypatch, check_only):
    api = ConvergedRuntimeApi()
    kwargs, fixture, _guard, requests, writers = install_gdw_release_transport(monkeypatch, api)
    fixture.status.update(role="WRITER", writable=True, lease={"state": "ACTIVE", "sequence": 43})
    monkeypatch.setattr(config, "load_runtime_mutation_owner",
                        lambda: pytest.fail("converged ACTIVE runtime constructed a mutation owner"))
    report = config.configure(**kwargs, check_only=check_only)
    assert report["converged"] is True
    assert report["variables_managed"] == sorted(config.STATIC_VARIABLES)
    assert report["readback_attempts"] == 1
    if not check_only:
        assert report["state_store_admission"] == {"state": "NO_CHANGES"}
        assert report["variables_changed"] == []
    assert requests == writers == api.writes == []
    assert fixture.reads == 0 and api.value_reads == []


def test_active_runtime_drift_cannot_dispatch_a_configuration_write(monkeypatch):
    api = ConvergedRuntimeApi()
    api.variables["GDW_POLICY_ORIGIN"] = SimpleNamespace(value="drift")
    kwargs, fixture, _guard, requests, writers = install_gdw_release_transport(monkeypatch, api)
    fixture.status.update(role="WRITER", writable=True, lease={"state": "ACTIVE", "sequence": 43})
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "STATE_STORE_RELEASE_REQUIRED"
    assert error.value.mutation_outcome == {
        "attempted": [], "acknowledged": [], "possible_partial_configuration": False,
        "automatic_retry": False,
    }
    assert requests == api.writes == []
    assert fixture.reads == 0 and writers[0].client.is_closed


def test_released_runtime_uses_shared_transport_and_preserves_honest_scope(monkeypatch):
    api = ConvergedRuntimeApi()
    api.variables["GDW_POLICY_ORIGIN"] = SimpleNamespace(value="drift")
    kwargs, fixture, guard, requests, writers = install_gdw_release_transport(monkeypatch, api)
    report = config.configure(**kwargs)
    assert api.writes == [("GDW_POLICY_ORIGIN", "http://127.0.0.1:7860")]
    assert len(requests) == 1 and fixture.reads == 2
    assert writers[0].attempted == writers[0].acknowledged == ["GDW_POLICY_ORIGIN"]
    assert report["state_store_admission"] == guard.summary
    assert report["runtime_boot_verified"] is False
    assert report["storage_preservation_verified"] is False
    assert report["mutation_deadline_scope"] == "REQUEST_DISPATCH_NOT_PROVIDER_EXECUTION"
    assert report["variables_changed"] == ["GDW_POLICY_ORIGIN"]
    assert report["converged"] is True and writers[0].client.is_closed
    assert api.value_reads == []


@pytest.mark.parametrize("successor,diagnostic", [
    ("public-active", "STATE_STORE_RELEASE_REQUIRED"),
    ("private-active", "STATE_STORE_RELEASE_UNVERIFIED"),
    ("different-release", "STATE_STORE_RELEASE_CHANGED"),
])
def test_each_actual_write_rechecks_the_same_release(monkeypatch, successor, diagnostic):
    import httpx
    api = ConvergedRuntimeApi()
    for name in ("GDW_EFFECT_MAX_ATTEMPTS", "GDW_POLICY_ORIGIN"):
        api.variables[name] = SimpleNamespace(value="drift")
    def handler(request, fixture):
        payload = json.loads(request.content)
        api.variables[payload["key"]] = SimpleNamespace(value=payload["value"])
        api.writes.append((payload["key"], payload["value"]))
        if successor == "public-active":
            fixture.status.update(role="WRITER", writable=True,
                                  lease={"state": "ACTIVE", "sequence": 44})
        elif successor == "private-active":
            fixture.head.update(state="ACTIVE", transition="SNAPSHOT")
        else:
            fixture.revision = "2" * 40
        return httpx.Response(200, json={})
    kwargs, _fixture, _guard, requests, writers = install_gdw_release_transport(
        monkeypatch, api, handler=handler)
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == diagnostic
    assert len(requests) == 1
    assert api.writes == [("GDW_EFFECT_MAX_ATTEMPTS", "20")]
    assert error.value.mutation_outcome == {
        "attempted": ["GDW_EFFECT_MAX_ATTEMPTS"], "acknowledged": ["GDW_EFFECT_MAX_ATTEMPTS"],
        "possible_partial_configuration": True, "automatic_retry": False,
    }
    assert writers[0].client.is_closed


@pytest.mark.parametrize("change_at", [3, 4, 5])
def test_protected_main_still_brackets_each_release_admission(monkeypatch, change_at):
    api = ConvergedRuntimeApi()
    for name in ("GDW_EFFECT_MAX_ATTEMPTS", "GDW_POLICY_ORIGIN"):
        api.variables[name] = SimpleNamespace(value="drift")
    kwargs, _fixture, _guard, requests, writers = install_gdw_release_transport(monkeypatch, api)
    calls = []
    def main_reader():
        calls.append(True)
        return "a" * 40 if len(calls) < change_at else "b" * 40
    kwargs["main_reader"] = main_reader
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "SOURCE_NOT_CURRENT_MAIN"
    expected = [] if change_at == 3 else ["GDW_EFFECT_MAX_ATTEMPTS"]
    assert writers[0].attempted == writers[0].acknowledged == expected
    assert len(requests) == len(expected)
    assert error.value.mutation_outcome["acknowledged"] == expected
    assert writers[0].client.is_closed


def test_final_main_read_cannot_extend_release_submission_deadline(monkeypatch):
    api = ConvergedRuntimeApi()
    api.variables["GDW_POLICY_ORIGIN"] = SimpleNamespace(value="drift")
    kwargs, fixture, _guard, requests, writers = install_gdw_release_transport(monkeypatch, api)
    calls = []
    def main_reader():
        calls.append(True)
        if len(calls) == 3:
            fixture.clock += 6
        return "a" * 40
    kwargs["main_reader"] = main_reader
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "STATE_STORE_OBSERVATION_EXPIRED"
    assert error.value.mutation_outcome["attempted"] == []
    assert requests == [] and writers[0].client.is_closed


def test_uncertain_dispatch_is_not_retried_and_survives_cli_cleanup(monkeypatch, tmp_path, capsys):
    import httpx
    api = ConvergedRuntimeApi()
    for name in ("GDW_EFFECT_MAX_ATTEMPTS", "GDW_POLICY_ORIGIN"):
        api.variables[name] = SimpleNamespace(value="drift")
    def handler(request, _fixture):
        raise httpx.ReadTimeout("synthetic-provider-private-detail", request=request)
    _kwargs, _fixture, guard, requests, writers = install_gdw_release_transport(
        monkeypatch, api, handler=handler)
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setattr(config, "require_current_main", lambda *_args: None)
    monkeypatch.setattr(guard, "close",
                        lambda: (_ for _ in ()).throw(OSError("synthetic-cleanup-private-detail")))
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    output = tmp_path / "uncertain-gdw.json"
    assert config.main(["--expected-source-sha", "a" * 40, "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostic_code"] == "RUNTIME_CONFIG_OUTCOME_UNCERTAIN"
    assert report["mutation_outcome"] == {
        "attempted": ["GDW_EFFECT_MAX_ATTEMPTS"], "acknowledged": [],
        "possible_partial_configuration": True, "automatic_retry": False,
    }
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == report
    for private in ("synthetic-provider-private-detail", "synthetic-cleanup-private-detail",
                    "synthetic-hf-control"):
        assert private not in stdout
    assert len(requests) == 1 and api.writes == []
    assert writers[0].client.is_closed


def test_acknowledged_write_without_readback_remains_drift(monkeypatch):
    import httpx
    api = ConvergedRuntimeApi()
    api.variables["GDW_POLICY_ORIGIN"] = SimpleNamespace(value="drift")
    kwargs, _fixture, _guard, requests, writers = install_gdw_release_transport(
        monkeypatch, api, handler=lambda _request, _fixture: httpx.Response(200, json={}))
    readback = config.await_readback
    monkeypatch.setattr(config, "await_readback",
                        lambda *args, **kwargs: readback(*args, **kwargs, attempts=1, delay_seconds=0))
    with pytest.raises(config.RuntimeConfigError) as error:
        config.configure(**kwargs)
    assert error.value.diagnostic_code == "RUNTIME_CONFIG_DRIFT"
    assert error.value.mutation_outcome["acknowledged"] == ["GDW_POLICY_ORIGIN"]
    assert len(requests) == 1 and writers[0].client.is_closed


def test_check_only_cli_reports_gdw_only_drift_without_secret_values(monkeypatch, tmp_path, capsys):
    api = ConvergedRuntimeApi()
    api.variables["GDW_POLICY_ORIGIN"] = SimpleNamespace(value="synthetic-private-drift")
    install_runtime_api(monkeypatch, api)
    monkeypatch.setattr(verifier, "default_get", pinned_get)
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-control")
    output = tmp_path / "gdw-drift.json"
    assert config.main(["--check-only", "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostic_code"] == "RUNTIME_CONFIG_DRIFT"
    assert report["state"] == "SETUP_REQUIRED" and report["converged"] is False
    assert "mutation_outcome" not in report
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == report
    assert "synthetic-private-drift" not in stdout and "synthetic-hf-control" not in stdout
    assert api.writes == [] and api.value_reads == []


def test_state_store_configure_corrects_cadence_and_waits_for_readback(monkeypatch):
    class CadenceApi(MetadataOnlyApi):
        def __init__(self):
            super().__init__()
            self.variables = {name: SimpleNamespace(value=value)
                              for name, value in config.desired_variables().items()}
            self.variables.update({
                "A11OY_STATE_STORE": SimpleNamespace(value="v2"),
                "A11OY_STATE_DEBOUNCE_SECONDS": SimpleNamespace(value="30"),
                "A11OY_STATE_PERIODIC_SECONDS": SimpleNamespace(value="1800"),
                "A11OY_STATE_ALERT_SECONDS": SimpleNamespace(value="900"),
            })
            self.readbacks = 0

        def add_space_variable(self, *, repo_id, key, value, description):
            assert repo_id == config.CANONICAL_SPACE
            self.writes.append((key, value))
            self.variables[key] = SimpleNamespace(value=value)

        def get_space_variables(self, *, repo_id):
            values = super().get_space_variables(repo_id=repo_id)
            if self.writes:
                self.readbacks += 1
                if self.readbacks == 1:
                    return {**values, "A11OY_STATE_PERIODIC_SECONDS": SimpleNamespace(value="1800")}
            return values

    api = CadenceApi()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda **_kwargs: api))
    real_readback = config.await_readback
    sleeps = []
    monkeypatch.setattr(config, "await_readback", lambda api, **kwargs: real_readback(
        api, **kwargs, attempts=3, delay_seconds=0, sleep=sleeps.append))
    admissions = []

    def main_reader():
        admissions.append(tuple(api.writes))
        return "a" * 40

    report = config.configure(repo_id=config.CANONICAL_SPACE, hf_token="synthetic-hf-control",
                              expected_source_sha="a" * 40, main_reader=main_reader,
                              authority_get=pinned_get)
    assert api.writes == [("A11OY_STATE_PERIODIC_SECONDS", "300")]
    assert admissions == [(), ()]
    assert report["variables_changed"] == ["A11OY_STATE_PERIODIC_SECONDS"]
    assert {"A11OY_STATE_DEBOUNCE_SECONDS", "A11OY_STATE_PERIODIC_SECONDS",
            "A11OY_STATE_ALERT_SECONDS"} <= set(report["variables_managed"])
    assert report["readback_attempts"] == 2 and api.readbacks == 2
    assert sleeps == [0]
    assert report["converged"] is True
    assert report["secret_values_read"] is False
    assert report["secret_values_mutated"] is False
    assert api.variables["A11OY_STATE_ALERT_SECONDS"].value == "900"
    assert api.variables["A11OY_STATE_DEBOUNCE_SECONDS"].value == "30"
