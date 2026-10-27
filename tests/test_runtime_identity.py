# SPDX-License-Identifier: Apache-2.0
"""Local filesystem/protocol tests. OIDC verifier responses are synthetic here."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import szl_runtime_identity as identity
FETCH_BINDING = identity.fetch_binding


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@pytest.fixture
def world(tmp_path, monkeypatch):
    marker = {"schema": "szl.runtime-source-marker/v1", "source_repository": identity.REPOSITORY,
              "source_sha": "a" * 40, "target": identity.TARGET, "run_id": 123,
              "run_attempt": 2, "publisher_sha": "c" * 40, "nonce": "d" * 64, "catalog": {}}
    for name in identity.REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = ("uses: " + identity.SIGNER + "@" + "c" * 40 + "\n").encode() if name.endswith(".yml") else b"# fixture\n"
        path.write_bytes(raw)
        marker["catalog"][name] = {"source_path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
    (tmp_path / identity.MARKER).write_bytes(canonical(marker))
    env = {"SZL_GIT_SHA": "a" * 40, "SZL_READINESS_GH_TOKEN": "test-read-credential"}
    body = {"schema": "szl.runtime-source-binding/v1", "marker": marker, "hf_revision": "b" * 40,
            "scope": "FINAL_APP_SOURCE_COPY_FILES", "image_attestation": False,
            "hardware_attestation": False, "execution_authority": False}
    transport = Mock()
    monkeypatch.setattr(identity, "Transport", lambda *a: transport)
    fetch = Mock(side_effect=lambda *a: canonical(body))
    verifier = Mock(return_value=None)
    monkeypatch.setattr(identity, "fetch_binding", fetch)
    monkeypatch.setattr(identity, "verify_attestation", verifier)
    subject = identity.ProcessIdentity("boot-one", root=tmp_path, marker_root=tmp_path, environ=env)
    return SimpleNamespace(root=tmp_path, marker=marker, body=body, env=env, subject=subject,
                           verifier=verifier, fetch=fetch, transport=transport)


def test_authenticated_binding_latches_and_environment_cannot_replace_it(world):
    observed = world.subject.verify_once()
    assert observed.source_revision == "a" * 40 and observed.hf_revision == "b" * 40
    assert observed.publication_evidence == "REPORTED" and observed.local_bytes_evidence == "MEASURED"
    world.env["SZL_GIT_SHA"] = "e" * 40
    world.body["hf_revision"] = "e" * 40
    assert world.subject.verify_once() is observed
    assert world.subject.admitted() is observed
    assert world.fetch.call_count == 1 and world.verifier.call_count == 1
    assert world.subject.snapshot()["execution_authority"] is False


@pytest.mark.parametrize("field,value", [("target", "SZLHOLDINGS/other"), ("run_attempt", 1),
    ("run_id", 124), ("source_sha", "e" * 40), ("publisher_sha", "e" * 40), ("nonce", "e" * 64)])
def test_old_or_wrong_publication_cannot_bind_this_boot(world, field, value):
    world.body["marker"] = copy.deepcopy(world.marker)
    world.body["marker"][field] = value
    with pytest.raises(identity.EvidenceBlocked, match="PUBLICATION_BINDING_MISMATCH"):
        world.subject.verify_once()
    world.verifier.assert_not_called()


def test_rejected_attestation_leaves_execution_closed(world):
    world.verifier.side_effect = identity.EvidenceBlocked("RUNTIME_ATTESTATION_REJECTED")
    with pytest.raises(identity.EvidenceBlocked, match="ATTESTATION_REJECTED"):
        world.subject.verify_once()
    with pytest.raises(identity.EvidenceBlocked, match="IMMUTABLE_PROCESS"):
        world.subject.admitted()


def test_missing_artifact_is_not_replaced_by_environment(world, monkeypatch):
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "b" * 40)
    world.fetch.side_effect = identity.EvidenceBlocked("RUNTIME_BINDING_ARTIFACT_UNAVAILABLE")
    with pytest.raises(identity.EvidenceBlocked, match="ARTIFACT_UNAVAILABLE"):
        world.subject.verify_once()
    assert world.subject.snapshot()["status"] == "BLOCKED"


@pytest.mark.parametrize("moment", ["before_verify", "after_verify"])
def test_tampered_local_bytes_block_and_cannot_be_repaired_into_admission(world, moment):
    path = world.root / "serve.py"
    old = path.read_bytes()
    if moment == "after_verify":
        world.subject.verify_once()
    path.write_bytes(b"# changed\n")
    with pytest.raises(identity.EvidenceBlocked, match="BYTES_MISMATCH"):
        world.subject.admitted() if moment == "after_verify" else world.subject.verify_once()
    path.write_bytes(old)
    with pytest.raises(identity.EvidenceBlocked, match="DRIFT_LATCHED"):
        world.subject.verify_once()


def test_marker_tamper_is_refused(world):
    world.subject.verify_once()
    (world.root / identity.MARKER).write_bytes(canonical({**world.marker, "nonce": "f" * 64}))
    with pytest.raises(identity.EvidenceBlocked, match="MARKER_CHANGED"):
        world.subject.admitted()


@pytest.mark.parametrize("path", ["../escape", "/etc/passwd", "nested/../../x", "C:/secrets", "x\\y", "./serve.py"])
def test_catalog_cannot_escape_root(world, path):
    with pytest.raises(identity.EvidenceBlocked, match="PATH"):
        identity.regular(world.root, path, 100)


def test_symlinked_parent_is_refused(world):
    link = world.root / "link"
    try:
        link.symlink_to(world.root, target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(identity.EvidenceBlocked, match="SYMLINK"):
        identity.regular(world.root, "link/serve.py", 100)


def test_wrong_publisher_pin_cannot_start(world):
    world.marker["publisher_sha"] = "f" * 40
    (world.root / identity.MARKER).write_bytes(canonical(world.marker))
    subject = identity.ProcessIdentity("boot", root=world.root, marker_root=world.root, environ=world.env)
    assert subject.error == "RUNTIME_PUBLISHER_PIN_MISMATCH"


def test_verifier_enforces_source_and_signer_certificate_policy(tmp_path, monkeypatch):
    # Actual subprocess boundary; no synthetic JSON return value is trusted.
    observed = []
    def run(command, **kwargs):
        observed.append((command, kwargs))
        assert Path(command[3]).read_bytes() == b"subject bytes"
        kwargs["stdout"].write(json.dumps([{"verificationResult": {"signature": {"certificate": {
            "runInvocationURI": "https://github.com/szl-holdings/a11oy/actions/runs/123/attempts/2"
        }}}}]).encode())
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(identity.subprocess, "run", run)
    marker = {"publisher_sha": "c" * 40, "source_sha": "a" * 40, "run_id": 123, "run_attempt": 2}
    identity.verify_attestation(b"subject bytes", marker, "read-token")
    command, kwargs = observed[0]
    for flag, value in [("--signer-workflow", identity.SIGNER), ("--signer-digest", "c" * 40),
                        ("--source-digest", "a" * 40), ("--source-ref", "refs/heads/main"),
                        ("--repo", identity.REPOSITORY)]:
        assert command[command.index(flag) + 1] == value
    assert "--deny-self-hosted-runners" in command
    assert kwargs["timeout"] == 45 and "HF_TOKEN" not in kwargs["env"]
    for field in ("run_id", "run_attempt"):
        with pytest.raises(identity.EvidenceBlocked, match="INVOCATION_MISMATCH"):
            identity.verify_attestation(b"subject bytes", {**marker, field: 999}, "read-token")
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    with pytest.raises(identity.EvidenceBlocked, match="ATTESTATION_REJECTED"):
        identity.verify_attestation(b"subject bytes", marker, "read-token")


@pytest.mark.parametrize("field,value", [("run_attempt", 1), ("head_sha", "f" * 40),
    ("path", ".github/workflows/untrusted.yml"), ("event", "pull_request"), ("head_branch", "feature")])
def test_fetch_rejects_wrong_run_attempt_workflow_or_source(world, field, value):
    run = {"id": 123, "run_attempt": 2, "head_sha": "a" * 40, "head_branch": "main",
           "path": identity.WORKFLOW, "event": "push", "repository": {"id": identity.REPOSITORY_ID},
           "head_repository": {"id": identity.REPOSITORY_ID}}
    run[field] = value
    transport = Mock()
    transport.json.return_value = run
    with pytest.raises(identity.EvidenceBlocked, match="PUBLISHER_RUN_MISMATCH"):
        FETCH_BINDING(transport, world.marker)
    transport.archive.assert_not_called()


def test_fetch_rejects_foreign_repository_and_duplicate_artifact(world):
    run = {"id": 123, "run_attempt": 2, "head_sha": "a" * 40, "head_branch": "main",
           "path": identity.WORKFLOW, "event": "push", "repository": {"id": identity.REPOSITORY_ID},
           "head_repository": {"id": 1}}
    transport = Mock()
    transport.json.return_value = run
    with pytest.raises(identity.EvidenceBlocked, match="RUN_MISMATCH"):
        FETCH_BINDING(transport, world.marker)
    run["head_repository"]["id"] = identity.REPOSITORY_ID
    item = {"id": 7, "name": "hf-runtime-identity-123-2"}
    transport.json.side_effect = [run, {"artifacts": [item, item], "total_count": 2}]
    with pytest.raises(identity.EvidenceBlocked, match="ARTIFACT_UNAVAILABLE"):
        FETCH_BINDING(transport, world.marker)


def test_fetch_binds_exact_attempt_artifact_and_validates_zip(world):
    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as writer:
        writer.writestr("hf-runtime-binding.json", canonical(world.body))
    archive = buffer.getvalue()
    run = {"id": 123, "run_attempt": 2, "head_sha": "a" * 40, "head_branch": "main",
           "path": identity.WORKFLOW, "event": "push", "repository": {"id": identity.REPOSITORY_ID},
           "head_repository": {"id": identity.REPOSITORY_ID}}
    meta = {"id": 7, "expired": False, "name": "hf-runtime-identity-123-2",
            "digest": "sha256:" + hashlib.sha256(archive).hexdigest(), "size_in_bytes": len(archive),
            "workflow_run": {"id": 123, "head_sha": "a" * 40, "head_branch": "main",
                             "repository_id": identity.REPOSITORY_ID, "head_repository_id": identity.REPOSITORY_ID}}
    transport = Mock()
    transport.json.side_effect = [run, {"artifacts": [meta], "total_count": 1}, meta]
    transport.archive.return_value = archive
    assert FETCH_BINDING(transport, world.marker) == canonical(world.body)
    transport.archive.assert_called_once_with(7)
    transport.json.side_effect = [run, {"artifacts": [meta], "total_count": 1}, {**meta, "expired": True}]
    with pytest.raises(identity.EvidenceBlocked, match="METADATA_MISMATCH"):
        FETCH_BINDING(transport, world.marker)
    for name in ["hf-runtime-identity-123-1", "other"]:
        transport.json.side_effect = [run, {"artifacts": [{**meta, "name": name}], "total_count": 1}]
        with pytest.raises(identity.EvidenceBlocked, match="ARTIFACT_UNAVAILABLE"):
            FETCH_BINDING(transport, world.marker)


def test_duplicate_json_selector_and_oversized_file_are_refused(world):
    with pytest.raises(identity.EvidenceBlocked, match="DUPLICATE"):
        identity.marker_document(b'{"schema":"x","schema":"y"}')
    (world.root / "serve.py").write_bytes(b"x" * 100)
    with pytest.raises(identity.EvidenceBlocked, match="TOO_LARGE"):
        identity.measure_catalog(world.root, world.marker)


def test_lifecycle_retries_only_in_bounded_startup_window(world, monkeypatch):
    threads = []
    def thread(**kwargs):
        threads.append(kwargs["target"])
        return Mock()
    monkeypatch.setattr(identity.threading, "Thread", thread)
    times = iter([0, 1, 301])
    monkeypatch.setattr(identity.time, "monotonic", lambda: next(times))
    world.subject.verify_once = Mock(side_effect=identity.EvidenceBlocked("RUNTIME_BINDING_ARTIFACT_UNAVAILABLE"))
    world.subject._stop.wait = Mock()
    world.subject.start()
    world.subject.start()
    assert len(threads) == 1
    threads[0]()
    assert world.subject.verify_once.call_count == 1
    world.subject.snapshot()
    assert world.subject.verify_once.call_count == 1
    world.subject.stop()
    assert world.subject._stop.is_set()


def test_opened_file_is_bounded_even_if_it_grows_after_path_check(world, monkeypatch):
    original = identity.os.open
    path = world.root / "serve.py"
    def racing_open(name, *args, **kwargs):
        if str(name) in ("serve.py", str(path)):
            path.write_bytes(b"x" * 100)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(identity.os, "open", racing_open)
    with pytest.raises(identity.EvidenceBlocked, match="TOO_LARGE"):
        identity.regular(world.root, "serve.py", 10)
