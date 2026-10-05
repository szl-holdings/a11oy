# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("preserve_hf_gdw_store", ROOT / "scripts/preserve_hf_gdw_store.py")
assert SPEC and SPEC.loader
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
SOURCE = "a" * 40
NONCE = "b" * 32
PRIVATE_ROW = "PRIVATE_PAYLOAD_MUST_NEVER_ENTER_PUBLIC_EVIDENCE"
PROVIDER_SECRET = "private_provider_error_with_token_hf_do_not_record"


def sqlite_fixture(path: Path, label: str) -> bytes:
    db = sqlite3.connect(path)
    if label == "gdw":
        db.execute("CREATE TABLE schema_meta(schema_name TEXT PRIMARY KEY, schema_version INTEGER, database_generation_id TEXT)")
        db.execute("INSERT INTO schema_meta VALUES('gdw',4,?)", ("c" * 32,))
        tables = [name for name in p.TABLES[label] if name != "schema_meta"]
    else:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)")
        db.execute("INSERT INTO metadata VALUES('storage_instance_id',?)", ("store_" + "d" * 32,))
        tables = [name for name in p.TABLES[label] if name != "metadata"]
    for name in tables:
        db.execute(f'CREATE TABLE "{name}"(id INTEGER PRIMARY KEY,payload TEXT)')
        db.execute(f'INSERT INTO "{name}"(payload) VALUES(?)', (PRIVATE_ROW,))
    db.commit()
    db.close()
    return path.read_bytes()


class FakeHub:
    endpoint = p.ENDPOINT

    def __init__(self, files: dict[str, bytes]):
        self.files = dict(files)
        self.objects = {hashlib.sha256(data).hexdigest(): data for data in files.values()}
        self.stage = "RUNTIME_ERROR"
        self.private = True
        self.revision = "e" * 40
        self.volumes = [SimpleNamespace(type="bucket", source=p.BUCKET, mount_path="/data",
                                        read_only=False, path=None, revision=None)]
        self.calls = []
        self.batch_calls = []
        self.download_calls = []
        self.original_observations = 0
        self.after_original_observation = None
        self.batch_behavior = None
        self.corrupt_copy_download = False
        self.download_size_mismatch = False
        self.duplicate = False
        self.extra_path = False

    def bucket_info(self, *, bucket_id):
        assert bucket_id == p.BUCKET
        self.calls.append("bucket_info")
        return SimpleNamespace(id=bucket_id, private=self.private)

    def space_info(self, *, repo_id):
        assert repo_id == p.SPACE
        self.calls.append("space_info")
        return SimpleNamespace(id=repo_id, sha=self.revision, runtime=SimpleNamespace(volumes=self.volumes))

    def get_space_runtime(self, *, repo_id):
        assert repo_id == p.SPACE
        self.calls.append("get_space_runtime")
        return SimpleNamespace(stage=self.stage)

    def metadata(self, path):
        data = self.files[path]
        digest = hashlib.sha256(data).hexdigest()
        self.objects[digest] = data
        return SimpleNamespace(type="file", path=path, size=len(data), xet_hash=digest,
                               mtime=datetime(2026, 10, 4, tzinfo=timezone.utc), uploaded_at=None)

    def get_bucket_paths_info(self, *, bucket_id, paths):
        assert bucket_id == p.BUCKET
        self.calls.append("get_bucket_paths_info")
        if tuple(paths) == p.SOURCE_PATHS:
            self.original_observations += 1
        result = [self.metadata(path) for path in paths if path in self.files]
        if self.duplicate and result:
            result.append(result[0])
        if self.extra_path and result:
            extra = copy.copy(result[0])
            extra.path = "unrequested/private.db"
            result.append(extra)
        if tuple(paths) == p.SOURCE_PATHS and self.after_original_observation:
            self.after_original_observation(self)
        return iter(result)

    def download_bucket_files(self, *, bucket_id, files, raise_on_missing_files):
        assert bucket_id == p.BUCKET and raise_on_missing_files is True
        self.download_calls.append(files)
        for info, path in files:
            # Passing observed BucketFile objects is essential. Resolving a
            # string path here would silently read a changed mutable object.
            assert not isinstance(info, str)
            data = self.objects[info.xet_hash]
            if self.corrupt_copy_download and "/originals/" in info.path:
                data = bytes([data[0] ^ 1]) + data[1:] if data else data
            if self.download_size_mismatch:
                data += b"unexpected"
            Path(path).write_bytes(data)

    def batch_bucket_files(self, *, bucket_id, copy=None, add=None):
        assert bucket_id == p.BUCKET
        self.batch_calls.append({"copy": copy, "add": add})
        if self.batch_behavior:
            self.batch_behavior(self, copy, add)
            return
        self.apply_batch(copy, add)

    def apply_batch(self, copies, additions):
        for kind, source_bucket, digest, target in copies or []:
            assert kind == "bucket" and source_bucket == p.BUCKET
            assert target.startswith(p.PRIVATE_PREFIX + "/") and target not in p.SOURCE_PATHS
            assert target not in self.files, "the helper must not overwrite an existing destination"
            self.files[target] = self.objects[digest]
        for data, target in additions or []:
            assert target.startswith(p.PRIVATE_PREFIX + "/") and target not in self.files
            self.files[target] = bytes(data)


@pytest.fixture
def hub(tmp_path):
    files = {path: sqlite_fixture(tmp_path / f"{label}.db", label) for label, path in p.DATABASES.items()}
    # Preserve companions even when SQLite does not need their contents.
    files[p.DATABASES["gdw"] + "-journal"] = b"\x00" * 512
    return FakeHub(files)


def run(hub, tmp_path, *, checker=lambda: None, sleep=lambda seconds: None):
    return p.preserve(hub, source_sha=SOURCE, run_id="37216937874", run_attempt="1",
                      nonce=NONCE, workspace=tmp_path / "capture", require_owned_source=checker, sleep=sleep)


def test_preserves_exact_originals_and_sidecar_absences_then_inspects_real_sqlite(hub, tmp_path):
    originals = dict(hub.files)
    report = run(hub, tmp_path)
    assert report["preservation_state"] == "VERIFIED"
    assert report["state"] == "BLOCKED"
    assert report["deployment_admitted"] is False and report["restore_admitted"] is False
    assert report["diagnostic_code"] == "STORAGE_RECOVERY_REQUIRED"
    assert {path: hub.files[path] for path in originals} == originals
    assert report["captured_originals_unchanged_after_inspection"] is True
    assert len(report["files"]) == 8
    assert sum(row["present"] for row in report["files"]) == 3
    assert len(hub.batch_calls) == 2
    for label in p.DATABASES:
        inspection = report["databases"][label]
        assert inspection["integrity"] == "OK" and inspection["inspection_state"] == "COMPLETE"
        assert inspection["table_counts"]["receipts"] == 1
        assert inspection["expected_tables_present"] is True
        assert inspection["journal_mode_observed_on_copy"] == "delete"
        assert inspection["header"]["write_version"] == 1
        assert inspection["header"]["sqlite_version_number_last_modified"] > 0
        assert inspection["runtime_sqlite_version"] == "UNAVAILABLE"
    assert report["databases"]["gdw"]["database_generation_id"] == "c" * 32
    assert report["databases"]["series_a"]["database_generation_id"] == "store_" + "d" * 32
    assert PRIVATE_ROW not in json.dumps(report)
    manifest = hub.files[report["private_manifest"]["path"]]
    assert hashlib.sha256(manifest).hexdigest() == report["private_manifest"]["sha256"]
    assert json.loads(manifest)["restore_admitted"] is False


def test_unreferenced_pages_are_preserved_and_classified_without_repair(hub, tmp_path):
    path = p.DATABASES["gdw"]
    data = bytearray(hub.files[path])
    page_size = int.from_bytes(data[16:18], "big")
    pages = len(data) // page_size
    data[28:32] = (pages + 2).to_bytes(4, "big")
    data.extend(b"\x00" * (2 * page_size))
    hub.files[path] = bytes(data)
    original = hub.files[path]
    report = run(hub, tmp_path)
    assert report["preservation_state"] == "VERIFIED"
    assert report["databases"]["gdw"]["integrity"] == "FAILED"
    assert report["databases"]["gdw"]["integrity_classification"] == "UNREFERENCED_PAGES"
    assert report["databases"]["gdw"]["table_counts"]["receipts"] == 1
    assert hub.files[path] == original
    preserved = next(row for row in report["files"] if row["source_path"] == path)
    assert hub.files[preserved["private_copy_path"]] == original
    assert report["restore_admitted"] is False


def test_sqlite_only_opens_disposable_inspection_paths(hub, tmp_path, monkeypatch):
    connect = sqlite3.connect
    opened = []
    def guarded(database, *args, **kwargs):
        opened.append(database)
        assert "/inspection/" in database
        assert "/captured/" not in database and "/verification/" not in database
        assert database.endswith("?mode=ro") and kwargs.get("uri") is True
        return connect(database, *args, **kwargs)
    monkeypatch.setattr(p.sqlite3, "connect", guarded)
    assert run(hub, tmp_path)["preservation_state"] == "VERIFIED"
    assert len(opened) == 2


@pytest.mark.parametrize("stage", ["RUNNING", "BUILDING", "STARTING", "SLEEPING", "UNKNOWN", None])
def test_refuses_capture_when_provider_has_not_reported_stopped(hub, tmp_path, stage):
    hub.stage = stage
    report = run(hub, tmp_path)
    assert report["diagnostic_code"] == "STOPPED_RUNTIME_REQUIRED"
    assert not hub.download_calls and not hub.batch_calls


def test_public_bucket_is_rejected_before_data_access(hub, tmp_path):
    hub.private = False
    assert run(hub, tmp_path)["diagnostic_code"] == "PRIVATE_BUCKET_REQUIRED"
    assert not hub.download_calls and not hub.batch_calls


def test_wrong_space_response_identity_is_rejected(hub, tmp_path):
    original = hub.space_info
    def wrong(**kwargs):
        info = original(**kwargs)
        info.id = "SZLHOLDINGS/other-space"
        return info
    hub.space_info = wrong
    assert run(hub, tmp_path)["diagnostic_code"] == "SPACE_IDENTITY_MISMATCH"
    assert not hub.download_calls and not hub.batch_calls


@pytest.mark.parametrize("change", ["source", "subfolder", "nested_mount", "read_only", "missing"])
def test_mount_identity_must_match_exact_source_paths(hub, tmp_path, change):
    if change == "source":
        hub.volumes[0].source = "SZLHOLDINGS/another-bucket"
    elif change == "subfolder":
        hub.volumes[0].path = "subfolder"
    elif change == "nested_mount":
        hub.volumes.append(SimpleNamespace(mount_path="/data/a11oy/gdw"))
    elif change == "read_only":
        hub.volumes[0].read_only = True
    else:
        hub.volumes = []
    assert run(hub, tmp_path)["diagnostic_code"] == "MOUNT_TOPOLOGY_CONFLICT"
    assert not hub.download_calls and not hub.batch_calls


@pytest.mark.parametrize("change", ["database", "new_sidecar", "removed_sidecar"])
def test_second_identity_observation_detects_mutation_before_copy(hub, tmp_path, change):
    def mutate(_seconds):
        if change == "database":
            hub.files[p.DATABASES["gdw"]] += b"changed"
        elif change == "new_sidecar":
            hub.files[p.DATABASES["gdw"] + "-wal"] = b"new"
        else:
            del hub.files[p.DATABASES["gdw"] + "-journal"]
    report = run(hub, tmp_path, sleep=mutate)
    assert report["diagnostic_code"] == "ORIGINAL_IDENTITIES_CHANGED"
    assert not hub.download_calls and not hub.batch_calls


def test_missing_database_never_becomes_an_empty_generation(hub, tmp_path):
    del hub.files[p.DATABASES["gdw"]]
    assert run(hub, tmp_path)["diagnostic_code"] == "ORIGINAL_DATABASE_MISSING"
    assert not hub.download_calls and not hub.batch_calls


@pytest.mark.parametrize("attribute", ["duplicate", "extra_path"])
def test_unrequested_or_duplicate_provider_identities_are_blocked(hub, tmp_path, attribute):
    setattr(hub, attribute, True)
    assert run(hub, tmp_path)["diagnostic_code"] == "OBJECT_IDENTITY_MALFORMED"
    assert not hub.batch_calls


def test_capture_destination_collision_never_overwrites(hub, tmp_path):
    prefix = f"{p.PRIVATE_PREFIX}/37216937874-1-{SOURCE}-{NONCE}/originals/"
    collision = prefix + p.DATABASES["gdw"]
    hub.files[collision] = b"retained preexisting evidence"
    assert run(hub, tmp_path)["diagnostic_code"] == "CAPTURE_DESTINATION_EXISTS"
    assert hub.files[collision] == b"retained preexisting evidence"
    assert not hub.batch_calls


def test_source_ownership_is_rechecked_immediately_before_private_write(hub, tmp_path):
    calls = 0
    def check():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise p.PreservationError("SOURCE_NO_LONGER_CURRENT_MAIN")
    assert run(hub, tmp_path, checker=check)["diagnostic_code"] == "SOURCE_NO_LONGER_CURRENT_MAIN"
    assert not hub.batch_calls


def test_partial_batch_is_retained_honestly_without_retry_or_rollback(hub, tmp_path):
    def partial(api, copies, additions):
        api.apply_batch(copies[:1], additions)
        raise RuntimeError(PROVIDER_SECRET)
    hub.batch_behavior = partial
    originals = dict(hub.files)
    report = run(hub, tmp_path)
    assert report["diagnostic_code"] == "PRIVATE_COPY_INCOMPLETE"
    assert report["private_copy_count"] == 1
    assert len(hub.batch_calls) == 1
    assert {path: hub.files[path] for path in originals} == originals
    assert PROVIDER_SECRET not in json.dumps(report)


def test_lost_successful_response_requires_identity_and_byte_readback(hub, tmp_path):
    def lost(api, copies, additions):
        api.apply_batch(copies, additions)
        raise RuntimeError(PROVIDER_SECRET)
    hub.batch_behavior = lost
    report = run(hub, tmp_path)
    assert report["copy_response"] == "UNAVAILABLE"
    assert report["preservation_state"] == "VERIFIED"
    assert len(hub.batch_calls) == 2
    assert PROVIDER_SECRET not in json.dumps(report)


def test_byte_verification_rejects_wrong_download_despite_matching_metadata(hub, tmp_path):
    hub.corrupt_copy_download = True
    report = run(hub, tmp_path)
    assert report["diagnostic_code"] == "PRIVATE_COPY_DIGEST_MISMATCH"
    assert report["preservation_state"] != "VERIFIED"
    assert len(hub.batch_calls) == 1


def test_size_mismatch_fails_before_private_copy(hub, tmp_path):
    hub.download_size_mismatch = True
    assert run(hub, tmp_path)["diagnostic_code"] == "CAPTURE_FILE_MISMATCH"
    assert not hub.batch_calls


def test_provider_transition_after_download_blocks_copy(hub, tmp_path):
    original = hub.download_bucket_files
    def download(**kwargs):
        original(**kwargs)
        hub.stage = "RUNNING"
    hub.download_bucket_files = download
    assert run(hub, tmp_path)["diagnostic_code"] == "STOPPED_RUNTIME_REQUIRED"
    assert not hub.batch_calls


def test_exception_text_never_enters_report(hub, tmp_path):
    def unavailable(**_kwargs):
        raise RuntimeError(PROVIDER_SECRET)
    hub.bucket_info = unavailable
    report = run(hub, tmp_path)
    assert report["diagnostic_code"] == "PROVIDER_OPERATION_UNAVAILABLE"
    assert PROVIDER_SECRET not in json.dumps(report)


def test_deadline_during_copy_is_not_swallowed_as_a_lost_response(hub, tmp_path):
    def expire(_api, _copies, _additions):
        raise p.PreservationError("PRESERVATION_DEADLINE_EXHAUSTED")
    hub.batch_behavior = expire
    report = run(hub, tmp_path)
    assert report["diagnostic_code"] == "PRESERVATION_DEADLINE_EXHAUSTED"
    assert report["preservation_state"] != "VERIFIED"
    assert len(hub.batch_calls) == 1


def test_authoritative_deadline_survives_sqlite_exception_translation(hub, tmp_path, monkeypatch):
    now = [0.0]
    def interrupted(*_args, **_kwargs):
        now[0] = 1000.0
        # This is the shape sqlite3 returns after swallowing a Python exception
        # inside a progress callback, rather than propagating PreservationError.
        return {"inspection_state": "SQLITE_READ_UNAVAILABLE", "sqlite_error_code": "SQLITE_INTERRUPT"}
    monkeypatch.setattr(p, "inspect_database", interrupted)
    report = p.preserve(hub, source_sha=SOURCE, run_id="37216937874", run_attempt="1",
                        nonce=NONCE, workspace=tmp_path / "capture", require_owned_source=lambda: None,
                        sleep=lambda _: None, clock=lambda: now[0], deadline=100.0)
    assert report["diagnostic_code"] == "PRESERVATION_DEADLINE_EXHAUSTED"
    assert len(hub.batch_calls) == 1  # no manifest write after the expired inspection
    assert report["preservation_state"] != "VERIFIED"


@pytest.mark.parametrize("outcome", [429, 500, 502, 503, 504, 302, "timeout"])
def test_http_boundary_prevents_sdk_retry_classification(outcome):
    import httpx
    attempts = []
    def handler(request):
        attempts.append(request)
        if outcome == "timeout":
            raise httpx.ReadTimeout(PROVIDER_SECRET, request=request)
        return httpx.Response(outcome, content=PROVIDER_SECRET.encode())
    with p.hub_http_client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(p.BatchOutcomeUnknown) as exc:
            client.post(f"{p.ENDPOINT}/api/buckets/{p.BUCKET}/batch", content=b"fixed-private-copy")
        assert not isinstance(exc.value, httpx.HTTPError)
        assert str(exc.value) == ""
    assert len(attempts) == 1


def test_http_boundary_keeps_successful_batch_and_read_responses():
    import httpx
    def handler(request):
        return httpx.Response(200 if request.url.path.endswith("/batch") else 503)
    with p.hub_http_client(transport=httpx.MockTransport(handler)) as client:
        assert client.post(f"{p.ENDPOINT}/api/buckets/{p.BUCKET}/batch").status_code == 200
        assert client.get(f"{p.ENDPOINT}/api/buckets/{p.BUCKET}").status_code == 503


def test_native_and_python_diagnostic_output_are_suppressed(capfd):
    with p._private_output():
        print(PRIVATE_ROW)
        os.write(1, PROVIDER_SECRET.encode())
        os.write(2, PRIVATE_ROW.encode())
    print("safe-public-summary")
    captured = capfd.readouterr()
    assert captured.out == "safe-public-summary\n"
    assert captured.err == ""


def test_corrupt_header_is_preserved_without_attempting_automatic_recovery(hub, tmp_path):
    hub.files[p.DATABASES["gdw"]] = b"malformed database containing " + PRIVATE_ROW.encode()
    report = run(hub, tmp_path)
    assert report["preservation_state"] == "VERIFIED"
    assert report["databases"]["gdw"]["header"]["state"] == "SQLITE_HEADER_INVALID"
    assert report["databases"]["gdw"]["inspection_state"] == "SQLITE_READ_UNAVAILABLE"
    assert PRIVATE_ROW not in json.dumps(report)


def test_main_refuses_non_github_invocation_and_emits_only_blocked_metadata(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    output = tmp_path / "public.json"
    monkeypatch.setattr("sys.argv", ["preserve_hf_gdw_store.py", "--output", str(output)])
    assert p.main() == 2
    assert json.loads(output.read_text())["deployment_admitted"] is False
    assert "BLOCKED" in capsys.readouterr().out


def assert_preflight_order(source: str) -> None:
    from tests.test_hf_sync_supersession_contract import assert_manual_dependency_graph
    jobs = assert_manual_dependency_graph(source)
    job = jobs["manual-prerequisites"]
    assert job["env"] == {"HF_TOKEN": "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}"}
    steps = job["steps"]
    capture = [index for index, step in enumerate(steps) if "scripts/preserve_hf_gdw_store.py" in step.get("run", "")]
    qualify = [index for index, step in enumerate(steps) if "scripts/qualify_gdw_store_recovery.py" in step.get("run", "")]
    classify = [index for index, step in enumerate(steps) if "scripts/acquire_gdw_durable_storage.py" in step.get("run", "")]
    manual = [index for index, step in enumerate(steps) if "scripts/configure_hf_series_a_runtime.py" in step.get("run", "")]
    assert len(capture) == len(qualify) == len(classify) == len(manual) == 1
    assert capture[0] < qualify[0] < classify[0] < manual[0]
    preservation, qualification = steps[capture[0]], steps[qualify[0]]
    classifier, metadata = steps[classify[0]], steps[manual[0]]
    assert "if" not in preservation and preservation.get("continue-on-error") is True
    assert preservation["id"] == "preserve_stores"
    assert "--supervised-acquisition" in preservation["run"].split()
    assert qualification["id"] == "qualify_stores" and qualification.get("continue-on-error") is True
    assert qualification["if"] == "${{ always() && steps.preserve_stores.outcome == 'failure' }}"
    assert set(classifier) == {"name", "id", "if", "run"}
    assert classifier["id"] == "recovery_mode" and classifier["if"] == "${{ always() }}"
    assert " ".join(classifier["run"].split()) == (
        "python -B scripts/acquire_gdw_durable_storage.py --classify-prerequisites "
        '--preservation "${{ runner.temp }}/gdw-store-preservation.json" '
        '--qualification "${{ runner.temp }}/gdw-store-recovery-qualification.json" '
        '--github-output "$GITHUB_OUTPUT" '
        '--output "${{ runner.temp }}/manual-prerequisites.json"'
    )
    assert set(metadata) == {"name", "if", "shell", "run"}
    assert metadata["shell"] == "bash" and metadata["run"].count("--check-only") == 2
    assert metadata["if"] == "${{ steps.recovery_mode.outputs.mode != 'managed-recovery' && steps.recovery_mode.outcome == 'success' }}"
    uploads = [step for step in steps if "actions/upload-artifact@" in step.get("uses", "")]
    assert len(uploads) == 1 and uploads[0]["if"] == "always()"
    assert uploads[0]["with"]["if-no-files-found"] == "error"
    assert tuple(uploads[0]["with"]["path"].splitlines()) == (
        "${{ runner.temp }}/manual-prerequisites.json",
        "${{ runner.temp }}/gdw-store-preservation.json",
        "${{ runner.temp }}/gdw-store-recovery-qualification.json",
    )


@pytest.mark.parametrize("reject_at", [None, 1, 2])
def test_supervised_preservation_reconciles_before_each_batch(hub, tmp_path, monkeypatch, reject_at):
    originals = dict(hub.files)
    observed = []
    def reconcile(api, evidence, deadline):
        assert api is hub and evidence.source == SOURCE and deadline > time.monotonic()
        evidence.require_current_main()
        observed.append(len(hub.batch_calls))
        if len(observed) == reject_at:
            raise RuntimeError(PROVIDER_SECRET)
    import scripts as script_package
    replacement = SimpleNamespace(require_expected_absent=reconcile)
    monkeypatch.setitem(sys.modules, "scripts.reconcile_gdw_supervised_acquisition", replacement)
    monkeypatch.setattr(script_package, "reconcile_gdw_supervised_acquisition", replacement, raising=False)
    owned = []
    guarded = p._SupervisedPreservationHub(hub, SOURCE, lambda: owned.append(True), time.monotonic() + 30)
    report = p.preserve(guarded, source_sha=SOURCE, run_id="123", run_attempt="1",
        workspace=tmp_path / "guarded", require_owned_source=lambda: owned.append(True),
        sleep=lambda _: None, nonce=NONCE)
    assert observed == ([0, 1] if reject_at != 1 else [0])
    assert len(hub.batch_calls) == (2 if reject_at is None else reject_at - 1)
    assert all(hub.files[path] == data for path, data in originals.items())
    assert report["deployment_admitted"] is report["restore_admitted"] is False
    if reject_at is None:
        assert report["preservation_state"] == "VERIFIED"
    else:
        assert report["diagnostic_code"] == "SUPERVISED_RECONCILIATION_REQUIRED"
    assert PROVIDER_SECRET.encode() not in p._json_bytes(report)
    for name in ("pause_space", "create_commit", "delete_file", "restart_space"):
        with pytest.raises(p.PreservationError, match="SUPERVISED_OPERATION_UNADMITTED"):
            getattr(guarded, name)


@pytest.mark.parametrize("name,value", [
    ("GITHUB_JOB", "durable-acquisition"), ("GITHUB_EVENT_NAME", "workflow_dispatch"),
    ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_WORKFLOW_SHA", "f" * 40),
])
def test_supervised_preservation_rerun_or_wrong_job_holds_before_sdk(tmp_path, monkeypatch, name, value):
    environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "szl-holdings/a11oy",
        "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE,
        "GITHUB_JOB": "manual-prerequisites", "GITHUB_EVENT_NAME": "push",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_SHA": SOURCE,
        "GITHUB_WORKFLOW_REF": "szl-holdings/a11oy/.github/workflows/hf-sync.yml@refs/heads/main",
        "HF_TOKEN": PROVIDER_SECRET, "GH_TOKEN": PROVIDER_SECRET}
    for key, item in environment.items(): monkeypatch.setenv(key, item)
    monkeypatch.setenv(name, value)
    target = tmp_path / "held.json"
    monkeypatch.setattr(sys, "argv", ["preserve_hf_gdw_store.py", "--supervised-acquisition", "--output", str(target)])
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    assert p.main() == 2
    raw = target.read_bytes()
    assert json.loads(raw)["diagnostic_code"] == "SOURCE_CONTEXT_INVALID"
    assert PROVIDER_SECRET.encode() not in raw


@pytest.mark.parametrize("value", [
    {"name": "main", "protected": True, "commit": {"sha": SOURCE}},
    {"name": "main", "protected": False, "commit": {"sha": SOURCE}},
    {"name": "main", "protected": 1, "commit": {"sha": SOURCE}},
    {"name": "other", "protected": True, "commit": {"sha": SOURCE}},
    {"name": "main", "protected": True, "commit": {"sha": "e" * 40}},
    {}, None,
])
def test_supervised_manual_owner_requires_actual_protected_main(monkeypatch, value):
    calls = []
    def request(path, token):
        calls.append((path, token))
        return value
    monkeypatch.setitem(sys.modules, "hf_exact_main_ownership", SimpleNamespace(request_json=request))
    if value == {"name": "main", "protected": True, "commit": {"sha": SOURCE}} and value["protected"] is True:
        p._require_supervised_main(SOURCE, "synthetic-token")
    else:
        with pytest.raises(p.PreservationError, match="SOURCE_NO_LONGER_CURRENT_MAIN"):
            p._require_supervised_main(SOURCE, "synthetic-token")
    assert calls == [("/repos/szl-holdings/a11oy/branches/main", "synthetic-token")]


def test_existing_native_dependency_gate_and_private_artifact_boundary():
    assert_preflight_order((ROOT / ".github/workflows/hf-sync.yml").read_text())
    workflow = (ROOT / ".github/workflows/tests.yml").read_text()
    assert "tests/test_hf_gdw_preservation.py" in workflow


def test_workflow_rejects_preflight_after_live_runtime_qualification():
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    start = source.index("      - name: Preserve stopped private stores")
    end = source.index("      - name: Retain metadata checks", start)
    capture = source[start:end]
    source = source[:start] + source[end:]
    position = source.index("      - name: Retain bounded prerequisite decision")
    changed = source[:position] + capture + source[position:]
    with pytest.raises(AssertionError):
        assert_preflight_order(changed)


@pytest.mark.parametrize(("moving", "before"), [
    ("Qualify the pinned private capture without admitting restore",
     "Preserve stopped private stores before any runtime mutation"),
    ("Classify the exact native candidate without admitting deployment",
     "Qualify the pinned private capture without admitting restore"),
    ("Retain metadata checks and fail closed on UNKNOWN authority",
     "Classify the exact native candidate without admitting deployment"),
])
def test_workflow_rejects_each_reversed_prerequisite_boundary(moving, before):
    from tests.test_hf_sync_supersession_contract import job_block, step_block
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    job = job_block(source, "Check manual authority prerequisites before provider writes")
    moved, target = step_block(job, moving), step_block(job, before)
    changed = job.replace(moved, "", 1).replace(target, moved + "\n" + target, 1)
    assert changed != job
    with pytest.raises(AssertionError):
        assert_preflight_order(source.replace(job, changed, 1))


@pytest.mark.parametrize(("original", "replacement"), [
    ("--classify-prerequisites", "--acquire"),
    ('--preservation "${{ runner.temp }}/gdw-store-preservation.json"',
     '--preservation "${{ runner.temp }}/unreviewed-preservation.json"'),
    ('--qualification "${{ runner.temp }}/gdw-store-recovery-qualification.json"',
     '--qualification "${{ runner.temp }}/unreviewed-qualification.json"'),
    ('--github-output "$GITHUB_OUTPUT"', '--github-output "$GITHUB_OUTPUT" || true'),
    ("        if: ${{ always() }}\n", "        if: success()\n"),
])
def test_workflow_rejects_classifier_effects_substitution_and_skip(original, replacement):
    from tests.test_hf_sync_supersession_contract import job_block, step_block
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    job = job_block(source, "Check manual authority prerequisites before provider writes")
    classifier = step_block(job, "Classify the exact native candidate without admitting deployment")
    assert original in classifier
    changed = source.replace(classifier, classifier.replace(original, replacement, 1), 1)
    with pytest.raises(AssertionError):
        assert_preflight_order(changed)


@pytest.mark.parametrize("replacement", [
    "",
    "        if: ${{ steps.recovery_mode.outputs.mode != 'managed-recovery' }}\n",
    "        if: ${{ steps.recovery_mode.outputs.mode == 'managed-recovery' && steps.recovery_mode.outcome == 'success' }}\n",
    "        if: ${{ always() }}\n",
])
def test_workflow_requires_successful_nonmanaged_classification_before_metadata_checks(replacement):
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    original = "        if: ${{ steps.recovery_mode.outputs.mode != 'managed-recovery' && steps.recovery_mode.outcome == 'success' }}\n"
    assert original in source
    with pytest.raises(AssertionError):
        assert_preflight_order(source.replace(original, replacement, 1))


@pytest.mark.parametrize("step_name", [
    "Preserve stopped private stores before any runtime mutation",
    "Qualify the pinned private capture without admitting restore",
])
def test_workflow_requires_both_reviewed_blocked_steps_to_reach_the_classifier(step_name):
    from tests.test_hf_sync_supersession_contract import job_block, step_block
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    job = job_block(source, "Check manual authority prerequisites before provider writes")
    step = step_block(job, step_name)
    assert "        continue-on-error: true\n" in step
    changed = source.replace(step, step.replace("        continue-on-error: true\n", "", 1), 1)
    with pytest.raises(AssertionError):
        assert_preflight_order(changed)


def test_workflow_rejects_wildcard_private_artifact_upload():
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    changed = source.replace("${{ runner.temp }}/gdw-store-preservation.json", "${{ runner.temp }}/**")
    with pytest.raises(AssertionError):
        assert_preflight_order(changed)


@pytest.mark.parametrize("replacement", [
    "            ${{ runner.temp }}/**\n",
    "            ${{ runner.temp }}/gdw-store-recovery-qualification.json\n"
    "            ${{ runner.temp }}/candidate.sqlite3\n",
    "            ${{ runner.temp }}/gdw-store-recovery-qualification.json\n"
    "            ${{ runner.temp }}/gdw-store-recovery-qualification.json\n",
])
def test_workflow_rejects_widened_or_duplicate_recovery_artifacts(replacement):
    source = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    original = "            ${{ runner.temp }}/gdw-store-recovery-qualification.json\n"
    assert original in source
    with pytest.raises(AssertionError):
        assert_preflight_order(source.replace(original, replacement, 1))


@pytest.mark.parametrize("mode", ["script", "module"])
@pytest.mark.parametrize("reject_at", [None, 1, 2])
def test_preservation_native_import_context_and_per_batch_fence(tmp_path, mode, reject_at):
    """Real subprocess import semantics; synthetic fence and no remote effects."""
    import subprocess
    checkout = tmp_path / "checkout"
    scripts = checkout / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    (scripts / "preserve_hf_gdw_store.py").write_bytes((ROOT / "scripts/preserve_hf_gdw_store.py").read_bytes())
    (checkout / "root_marker.py").write_text("VALUE = 'SOURCE_ROOT'\n", encoding="utf-8")
    (scripts / "reconcile_gdw_supervised_acquisition.py").write_text(
        "from root_marker import VALUE\n"
        "calls = []\n"
        "reject_at = None\n"
        "def require_expected_absent(api, evidence, deadline):\n"
        "    assert VALUE == 'SOURCE_ROOT'\n"
        "    evidence.require_current_main()\n"
        "    calls.append(len(api.calls))\n"
        "    if len(calls) == reject_at:\n"
        "        raise RuntimeError('SYNTHETIC_PRIVATE_ERROR_MUST_NOT_ESCAPE')\n",
        encoding="utf-8",
    )
    imported = "import preserve_hf_gdw_store as p" if mode == "script" else "from scripts import preserve_hf_gdw_store as p"
    driver = imported + "\n" + r'''
import json, sys, time

def no_network(event, args):
    if event.startswith('socket.'):
        raise AssertionError('NETWORK_NOT_PERMITTED')
sys.addaudithook(no_network)
class Fake:
    def __init__(self): self.calls = []
    def batch_bucket_files(self, **kwargs):
        self.calls.append(kwargs)
        return 'SYNTHETIC_ONLY'
fake = Fake()
owned = []
try:
    from scripts import reconcile_gdw_supervised_acquisition as fence
    fence.reject_at = json.loads(sys.argv[1])
    guarded = p._SupervisedPreservationHub(fake, 'a'*40, lambda: owned.append(True), time.monotonic()+30)
    errors = []
    for _ in range(2):
        try: guarded.batch_bucket_files(bucket_id='fixture-only', copy=[])
        except Exception as error:
            errors.append({'type':type(error).__name__, 'code':str(error)})
            break
    print(json.dumps({'fences':fence.calls,'provider_calls':len(fake.calls),'owned':len(owned),'errors':errors}))
except Exception as error:
    print(json.dumps({'import_error':type(error).__name__}))
'''
    (scripts / "entrypoint_probe.py").write_text(driver, encoding="utf-8")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "root_marker.py").write_text("raise AssertionError('CWD_SHADOW_IMPORTED')\n", encoding="utf-8")
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    command = [sys.executable, "-B"]
    command += [str(scripts / "entrypoint_probe.py")] if mode == "script" else ["-m", "scripts.entrypoint_probe"]
    command.append(json.dumps(reject_at))
    result = subprocess.run(command, cwd=unrelated if mode == "script" else checkout,
                            env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and not result.stderr
    value = json.loads(result.stdout)
    assert value.get("fences") == ([0] if reject_at == 1 else [0, 1]), value
    assert value["owned"] == (1 if reject_at == 1 else 2)
    assert value["provider_calls"] == (2 if reject_at is None else reject_at - 1)
    assert value["errors"] == ([] if reject_at is None else [{"type":"PreservationError", "code":"SUPERVISED_RECONCILIATION_REQUIRED"}])
    assert "SYNTHETIC_PRIVATE_ERROR_MUST_NOT_ESCAPE" not in result.stdout
