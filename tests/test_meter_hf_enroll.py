"""Synthetic-only meter reader enrollment tests; never contact a provider or DPAPI."""

import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "box-scripts" / "enroll_meter_hf.py"
spec = importlib.util.spec_from_file_location("enroll_meter_hf", SOURCE)
enroll = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enroll)

OLD_CANONICAL = "a" * 64
LOCAL_CHECK = "b" * 64
NEW_KEY = "c" * 64


class FakeDpapi:
    def protect(self, value):
        return b"dpapi:" + value

    def unprotect(self, value):
        assert value.startswith(b"dpapi:")
        return value[6:]


class FakeSupervisor:
    def __init__(self):
        self.restarts = 0

    def _identity(self):
        return object(), object()

    def restart(self):
        self.restarts += 1


class FakeProbe:
    def __init__(self, *, fail_at=None):
        self.fail_at = fail_at
        self.proofs = 0
        self.rejections = 0
        self.live_checks = 0
        self.preflight_checks = 0

    def route_preflight(self):
        self.preflight_checks += 1
        if self.fail_at == "route":
            raise enroll.EnrollmentError("route unavailable")

    def source_preflight(self, revision):
        self.preflight_checks += 1
        assert revision == "1" * 40
        if self.fail_at == "source":
            raise enroll.EnrollmentError("source unavailable")

    def prove(self, client_id, key_hex):
        self.proofs += 1
        assert client_id.startswith("canonical-a11oy-v2-")
        assert key_hex == NEW_KEY
        if self.fail_at == "local":
            raise enroll.EnrollmentError("local proof failed")

    def wait_live(self, revision, client_id):
        self.live_checks += 1
        assert revision == "1" * 40
        assert client_id.startswith("canonical-a11oy-v2-")
        if self.fail_at == "live":
            raise enroll.EnrollmentError("runtime unavailable")

    def reject(self, client_id, key_hex):
        self.rejections += 1
        assert client_id == "canonical-a11oy"
        assert key_hex == OLD_CANONICAL
        if self.fail_at == "retirement":
            raise enroll.EnrollmentError("old key still accepted")


class FakeHub:
    def __init__(self, *, existing=False, fail_add=False,
                 fail_add_after_commit=False, lag_reads_after_add=0):
        self.existing = existing
        self.fail_add = fail_add
        self.fail_add_after_commit = fail_add_after_commit
        self.lag_reads_after_add = lag_reads_after_add
        self.value = None
        self.name = None
        self.adds = 0
        self.deletes = 0

    def preflight(self, revision, secret_name):
        assert revision == "2" * 40
        assert secret_name.startswith(enroll.SECRET_PREFIX)
        assert len(secret_name) == len(enroll.SECRET_PREFIX) + 32
        if self.existing:
            raise enroll.EnrollmentError("secret exists")

    def add(self, client_id, key_hex, secret_name):
        self.adds += 1
        if self.fail_add:
            raise enroll.EnrollmentError("add failed")
        self.name = secret_name
        self.value = {enroll.AUDIENCE: {"client_id": client_id, "key_hex": key_hex}}
        self.existing = True
        if self.fail_add_after_commit:
            raise enroll.EnrollmentError("provider response lost after commit")

    def secret_exists(self, secret_name):
        assert secret_name == self.name
        if self.lag_reads_after_add:
            self.lag_reads_after_add -= 1
            return False
        return self.existing

    def delete(self):
        self.deletes += 1
        self.existing = False
        self.value = None

    def wait_running(self):
        return None


@pytest.fixture
def private_meter(tmp_path):
    root = tmp_path / "Meter"
    program = root / "program"
    program.mkdir(parents=True)
    names = ("omen_joule_exporter.py", "szl_meter_access.py", "run_meter_windows.ps1")
    hashes = {}
    for name in names:
        payload = f"synthetic source: {name}".encode()
        (program / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    receipt = {"schema": "szl.meter.installation/v1", "audience": enroll.AUDIENCE,
               "configuration_protection": "DPAPI_CURRENT_USER", "source_revision": "0" * 40,
               "python": "python", "files": hashes}
    (root / "installation.json").write_text(json.dumps(receipt), encoding="utf-8")
    config = {"schema": enroll.SCHEMA, "audience": enroll.AUDIENCE,
              "clients": {"canonical-a11oy": OLD_CANONICAL,
                          "local-healthcheck": LOCAL_CHECK}}
    (root / "settings.dpapi").write_bytes(FakeDpapi().protect(enroll._json_bytes(config)))
    return root


def run(private_meter, *, hub=None, probe=None, supervisor=None):
    hub = hub or FakeHub()
    probe = probe or FakeProbe()
    supervisor = supervisor or FakeSupervisor()
    result = enroll.enroll(private_meter, dpapi=FakeDpapi(), supervisor=supervisor,
                           probe=probe, hub=hub, source_revision="1" * 40,
                           space_revision="2" * 40, maintenance_window="MW-TEST-1",
                           key_factory=lambda n: NEW_KEY)
    return result, hub, probe, supervisor


def current_config(private_meter):
    data = (private_meter / "settings.dpapi").read_bytes()
    return json.loads(FakeDpapi().unprotect(data))


def test_success_enrolls_only_new_reader_then_retires_prior_key(private_meter):
    original = (private_meter / "settings.dpapi").read_bytes()
    result, hub, probe, supervisor = run(private_meter)
    clients = current_config(private_meter)["clients"]
    assert "canonical-a11oy" not in clients
    assert clients["local-healthcheck"] == LOCAL_CHECK
    assert clients[result["new_client_id"]] == NEW_KEY
    assert hub.value == {enroll.AUDIENCE: {"client_id": result["new_client_id"],
                                            "key_hex": NEW_KEY}}
    assert hub.name == result["secret_name"]
    assert probe.proofs == 2 and probe.rejections == 1 and probe.live_checks == 2
    assert supervisor.restarts == 2
    assert Path(result["encrypted_rollback_copy"]).read_bytes() == original
    assert NEW_KEY not in json.dumps(result)
    assert NEW_KEY not in (private_meter / f"meter-enrollment-{result['new_client_id'].split('-')[-1]}.json").read_text()


def test_existing_hf_secret_stops_before_local_change(private_meter):
    original = (private_meter / "settings.dpapi").read_bytes()
    hub = FakeHub(existing=True)
    with pytest.raises(enroll.EnrollmentError, match="secret exists"):
        run(private_meter, hub=hub)
    assert (private_meter / "settings.dpapi").read_bytes() == original
    assert not list((private_meter).glob("meter-enrollment-*.json"))


@pytest.mark.parametrize("failure", ["route", "source"])
def test_route_or_source_preflight_stops_before_local_change(private_meter, failure):
    original = (private_meter / "settings.dpapi").read_bytes()
    with pytest.raises(enroll.EnrollmentError):
        run(private_meter, probe=FakeProbe(fail_at=failure))
    assert (private_meter / "settings.dpapi").read_bytes() == original


def test_local_proof_failure_restores_encrypted_configuration(private_meter):
    original = (private_meter / "settings.dpapi").read_bytes()
    hub, supervisor = FakeHub(), FakeSupervisor()
    with pytest.raises(enroll.EnrollmentError, match="local enrollment failed"):
        run(private_meter, hub=hub, probe=FakeProbe(fail_at="local"), supervisor=supervisor)
    assert (private_meter / "settings.dpapi").read_bytes() == original
    assert hub.adds == 0 and supervisor.restarts == 2


def test_provider_live_failure_preserves_new_key_and_partial_receipt(private_meter):
    hub = FakeHub()
    with pytest.raises(enroll.PartialActivation, match="new local key retained"):
        run(private_meter, hub=hub, probe=FakeProbe(fail_at="live"))
    assert hub.adds == 1 and hub.deletes == 0 and hub.existing
    assert any(v == NEW_KEY for v in current_config(private_meter)["clients"].values())
    assert json.loads(next(private_meter.glob("meter-enrollment-*.json")).read_text())["status"] == "PARTIAL_HF_OUTCOME_UNCERTAIN"


def test_add_commits_then_errors_keeps_new_key_to_avoid_remote_lockout(private_meter):
    hub = FakeHub(fail_add_after_commit=True)
    with pytest.raises(enroll.PartialActivation, match="outcome uncertain"):
        run(private_meter, hub=hub)
    clients = current_config(private_meter)["clients"]
    assert clients["canonical-a11oy"] == OLD_CANONICAL
    assert any(k.startswith("canonical-a11oy-v2-") and v == NEW_KEY
               for k, v in clients.items())
    assert hub.existing and hub.deletes == 0
    assert json.loads(next(private_meter.glob("meter-enrollment-*.json")).read_text())["status"] == "PARTIAL_HF_OUTCOME_UNCERTAIN"


def test_hf_name_readback_lag_keeps_new_key_and_partial_state(private_meter):
    hub = FakeHub(lag_reads_after_add=1)
    with pytest.raises(enroll.PartialActivation, match="outcome uncertain"):
        run(private_meter, hub=hub)
    assert hub.existing and hub.deletes == 0
    assert any(v == NEW_KEY for v in current_config(private_meter)["clients"].values())
    assert json.loads(next(private_meter.glob("meter-enrollment-*.json")).read_text())["status"] == "PARTIAL_HF_OUTCOME_UNCERTAIN"


def test_wrong_meter_live_readback_cannot_retire_old_key(monkeypatch):
    probe = enroll.MeterProbe()

    def fake_get(url, headers=None):
        if url.endswith("/api/build-info"):
            return 200, json.dumps({"build": {"revision": "1" * 40}}).encode()
        return 200, json.dumps({"meter_status": "ok", "meter_url": "https://meter.a-11-oy.com",
                                "joules_label": "UNAVAILABLE", "total_joules": None}).encode()

    monkeypatch.setattr(probe, "_get", fake_get)
    with pytest.raises(enroll.EnrollmentError, match="select the exact meter2 reader"):
        probe.live("1" * 40, "canonical-a11oy-v2-test")


def test_old_backend_reader_cannot_qualify_new_key_retirement(monkeypatch):
    probe = enroll.MeterProbe()

    def fake_get(url, headers=None):
        if url.endswith("/api/build-info"):
            return 200, json.dumps({"build": {"revision": "1" * 40}}).encode()
        return 200, json.dumps({"meter_status": "ok", "meter_url": enroll.AUDIENCE,
                                "meter_request_client_id": "canonical-a11oy",
                                "joules_label": "UNAVAILABLE", "total_joules": None}).encode()

    monkeypatch.setattr(probe, "_get", fake_get)
    with pytest.raises(enroll.EnrollmentError, match="select the exact meter2 reader"):
        probe.live("1" * 40, "canonical-a11oy-v2-test")


def test_real_hf_versioned_apply_is_blocked_without_atomic_create():
    class ReadOnlyApi:
        def whoami(self):
            return {"orgs": [{"name": "SZLHOLDINGS"}]}

        def repo_info(self, **kwargs):
            return SimpleNamespace(sha="2" * 40)

        def get_space_secrets(self, **kwargs):
            return {}

        def add_space_secret(self, **kwargs):
            pytest.fail("versioned provider write must not be attempted")

    hub = object.__new__(enroll.HfSpace)
    hub.api = ReadOnlyApi()
    with pytest.raises(enroll.EnrollmentError, match="no atomic create-only guard"):
        hub.preflight("2" * 40, enroll.SECRET_PREFIX + "A" * 32)
    with pytest.raises(enroll.EnrollmentError, match="no guarded create-only"):
        hub.add("canonical-a11oy-v2-test", NEW_KEY, enroll.SECRET_PREFIX + "A" * 32)


def test_receipt_write_failure_after_retirement_restores_overlap(private_meter, monkeypatch):
    original_write = enroll._atomic_write

    def fail_success_receipt(path, data):
        if path.name.startswith("meter-enrollment-") and b"ENROLLED_AND_OLD_KEY_RETIRED" in data:
            raise OSError("synthetic receipt disk failure")
        return original_write(path, data)

    monkeypatch.setattr(enroll, "_atomic_write", fail_success_receipt)
    with pytest.raises(enroll.PartialActivation, match="overlap restored"):
        run(private_meter)
    clients = current_config(private_meter)["clients"]
    assert clients["canonical-a11oy"] == OLD_CANONICAL
    assert any(v == NEW_KEY for v in clients.values())
    assert json.loads(next(private_meter.glob("meter-enrollment-*.json")).read_text())["status"] == "PARTIAL_OVERLAP_RESTORED"


def test_signature_binds_method_target_audience_and_new_client():
    headers = enroll.MeterProbe._headers("canonical-a11oy-v2-test", NEW_KEY, local=True)
    fields = ("szl-meter-hmac-v1", "GET", "/metrics", enroll.AUDIENCE,
              headers["X-SZL-Meter-Client"], headers["X-SZL-Meter-Time"],
              headers["X-SZL-Meter-Nonce"])
    expected = hmac.new(bytes.fromhex(NEW_KEY), "\n".join(fields).encode(),
                        hashlib.sha256).hexdigest()
    assert headers["Host"] == "meter2.a-11-oy.com"
    assert hmac.compare_digest(headers["X-SZL-Meter-Signature"], expected)


def test_default_cli_plan_never_constructs_provider_or_supervisor(private_meter, monkeypatch, capsys):
    monkeypatch.setattr(enroll, "_private_root", lambda: private_meter)
    monkeypatch.setattr(enroll, "HfSpace", lambda: pytest.fail("provider touched"))
    monkeypatch.setattr(enroll, "ExporterSupervisor", lambda *a: pytest.fail("exporter touched"))
    assert enroll.main([]) == 0
    assert json.loads(capsys.readouterr().out)["effects"] == "NONE"
