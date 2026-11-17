# SPDX-License-Identifier: Apache-2.0
"""Local filesystem/protocol tests. OIDC verifier responses are synthetic here."""
import copy
import hashlib
import json
import threading
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
    transport = Mock(deadline=float("inf"))
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
    def popen(command, **kwargs):
        observed.append((command, kwargs))
        assert Path(command[3]).read_bytes() == b"subject bytes"
        kwargs["stdout"].write(json.dumps([{"verificationResult": {"signature": {"certificate": {
            "runInvocationURI": "https://github.com/szl-holdings/a11oy/actions/runs/123/attempts/2"
        }}}}]).encode())
        return SimpleNamespace(poll=lambda: 0)
    monkeypatch.setattr(identity.subprocess, "Popen", popen)
    marker = {"publisher_sha": "c" * 40, "source_sha": "a" * 40, "run_id": 123, "run_attempt": 2}
    identity.verify_attestation(b"subject bytes", marker, "read-token")
    command, kwargs = observed[0]
    for flag, value in [("--signer-workflow", identity.SIGNER), ("--signer-digest", "c" * 40),
                        ("--source-digest", "a" * 40), ("--source-ref", "refs/heads/main"),
                        ("--repo", identity.REPOSITORY), ("--hostname", "github.com"),
                        ("--cert-oidc-issuer", "https://token.actions.githubusercontent.com")]:
        assert command[command.index(flag) + 1] == value
    assert "--deny-self-hosted-runners" in command
    assert identity.VERIFIER_TIMEOUT == 45 and "HF_TOKEN" not in kwargs["env"]
    assert kwargs["stdin"] == identity.subprocess.DEVNULL
    assert kwargs["stderr"] == identity.subprocess.DEVNULL
    for field in ("run_id", "run_attempt"):
        with pytest.raises(identity.EvidenceBlocked, match="INVOCATION_MISMATCH"):
            identity.verify_attestation(b"subject bytes", {**marker, field: 999}, "read-token")
    monkeypatch.setattr(identity.subprocess, "Popen", lambda *a, **k: SimpleNamespace(poll=lambda: 1))
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
    with pytest.raises(identity.EvidenceBlocked, match="ARTIFACT_AMBIGUOUS"):
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


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def __call__(self):
        return self.now

    def wait(self, delay):
        self.waits.append(delay)
        self.now += delay
        return False


class VerifierProcess:
    def __init__(self, *, stubborn=False, unkillable=False):
        self.returncode = None
        self.stubborn, self.unkillable = stubborn, unkillable
        self.actions = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.actions.append("terminate")
        if not self.stubborn:
            self.returncode = -15

    def kill(self):
        self.actions.append("kill")
        if not self.unkillable:
            self.returncode = -9

    def wait(self, timeout):
        self.actions.append(("wait", timeout))
        if self.returncode is None:
            raise identity.subprocess.TimeoutExpired("gh", timeout)
        return self.returncode


@pytest.mark.parametrize("boundary", ["stop", "attempt", "recovery"])
def test_actual_verifier_boundary_cancels_and_reaps_child(monkeypatch, boundary):
    clock = Clock()
    stop = threading.Event()
    process = VerifierProcess(stubborn=True)
    monkeypatch.setattr(identity.time, "monotonic", clock)
    monkeypatch.setattr(identity.subprocess, "Popen", lambda *a, **k: process)
    def wait(delay):
        clock.wait(delay)
        if boundary == "stop":
            stop.set()
        return stop.is_set()
    monkeypatch.setattr(stop, "wait", wait)
    deadline = 3 if boundary == "recovery" else 100
    code = {"stop": "IDENTITY_STOPPED", "attempt": "VERIFIER_UNAVAILABLE",
            "recovery": "RECOVERY_EXHAUSTED"}[boundary]
    with pytest.raises(identity.EvidenceBlocked, match=code):
        identity.verify_attestation(b"subject", {"publisher_sha": "c" * 40, "source_sha": "a" * 40,
            "run_id": 123, "run_attempt": 2}, "read-token", stop=stop, deadline=deadline)
    assert process.actions == ["terminate", ("wait", 1), "kill", ("wait", 1)]
    assert clock.now <= min(deadline, 45)
    if boundary == "stop":
        assert clock.now == identity.VERIFIER_POLL


def test_verifier_cleanup_failure_is_terminal_and_bounded(monkeypatch):
    clock = Clock()
    stop = threading.Event()
    process = VerifierProcess(stubborn=True, unkillable=True)
    monkeypatch.setattr(identity.time, "monotonic", clock)
    monkeypatch.setattr(stop, "wait", lambda delay: stop.set())
    monkeypatch.setattr(identity.subprocess, "Popen", lambda *a, **k: process)
    with pytest.raises(identity.EvidenceBlocked, match="CLEANUP_INCOMPLETE"):
        identity.verify_attestation(b"subject", {"publisher_sha": "c" * 40, "source_sha": "a" * 40,
            "run_id": 123, "run_attempt": 2}, "read-token", stop=stop)
    assert process.actions == ["terminate", ("wait", 1), "kill", ("wait", 1)]
    assert "RUNTIME_VERIFIER_CLEANUP_INCOMPLETE" not in identity.RECOVERABLE_ERRORS


@pytest.mark.parametrize("moment", ["spawn", "parse"])
def test_verifier_success_returning_after_its_own_deadline_is_refused(monkeypatch, moment):
    clock = Clock()
    monkeypatch.setattr(identity.time, "monotonic", clock)
    def popen(*args, **kwargs):
        kwargs["stdout"].write(json.dumps([{"verificationResult": {"signature": {"certificate": {
            "runInvocationURI": "https://github.com/szl-holdings/a11oy/actions/runs/123/attempts/2"
        }}}}]).encode())
        if moment == "spawn":
            clock.now = 45
        return SimpleNamespace(poll=lambda: 0)
    monkeypatch.setattr(identity.subprocess, "Popen", popen)
    strict = identity.strict
    def parse(data, bound):
        result = strict(data, bound)
        clock.now = 45
        return result
    if moment == "parse":
        monkeypatch.setattr(identity, "strict", parse)
    with pytest.raises(identity.EvidenceBlocked, match="VERIFIER_UNAVAILABLE"):
        identity.verify_attestation(b"subject", {"publisher_sha": "c" * 40, "source_sha": "a" * 40,
            "run_id": 123, "run_attempt": 2}, "read-token")


def test_verifier_output_overflow_kills_child_without_parsing(monkeypatch):
    process = VerifierProcess()
    def popen(*args, **kwargs):
        kwargs["stdout"].write(b"x" * (identity.MAX_VERIFIER_OUTPUT + 1))
        kwargs["stdout"].flush()
        return process
    monkeypatch.setattr(identity.subprocess, "Popen", popen)
    parser = Mock(side_effect=AssertionError("oversize output reached parser"))
    monkeypatch.setattr(identity, "strict", parser)
    with pytest.raises(identity.EvidenceBlocked, match="OUTPUT_TOO_LARGE"):
        identity.verify_attestation(b"subject", {"publisher_sha": "c" * 40, "source_sha": "a" * 40,
            "run_id": 123, "run_attempt": 2}, "read-token")
    assert process.actions == ["terminate", ("wait", 1)]
    parser.assert_not_called()


def test_stopped_verifier_cannot_spawn_a_child(monkeypatch):
    stop = threading.Event()
    stop.set()
    spawn = Mock(side_effect=AssertionError("spawn after stop"))
    monkeypatch.setattr(identity.subprocess, "Popen", spawn)
    with pytest.raises(identity.EvidenceBlocked, match="IDENTITY_STOPPED"):
        identity.verify_attestation(b"subject", {}, "read-token", stop=stop)
    spawn.assert_not_called()


@pytest.fixture
def lifecycle(world, monkeypatch):
    clock = Clock()
    workers = []
    def thread(**kwargs):
        workers.append(kwargs["target"])
        return Mock()
    monkeypatch.setattr(identity.threading, "Thread", thread)
    monkeypatch.setattr(identity.time, "monotonic", clock)
    monkeypatch.setattr(world.subject._stop, "wait", clock.wait)
    return SimpleNamespace(clock=clock, workers=workers)


@pytest.mark.parametrize("pending", ["RUNTIME_BINDING_ARTIFACT_UNAVAILABLE", "RUNTIME_ATTESTATION_REJECTED"])
def test_late_publication_recovers_the_same_boot_without_rearming(world, lifecycle, pending):
    target = world.fetch if pending.endswith("ARTIFACT_UNAVAILABLE") else world.verifier
    def unavailable_until_published(*args, **kwargs):
        if lifecycle.clock.now < 600:
            assert world.subject.snapshot()["status"] == "BLOCKED"
            raise identity.EvidenceBlocked(pending)
        return canonical(world.body) if target is world.fetch else None
    target.side_effect = unavailable_until_published
    world.subject.start()
    world.subject.start()
    assert len(lifecycle.workers) == 1
    world.env.update(SZL_GIT_SHA="e" * 40, SZL_READINESS_GH_TOKEN="changed-credential")
    lifecycle.workers[0]()
    admitted = world.subject.admitted()
    assert admitted.runtime_boot_id == "boot-one"
    assert admitted.source_revision == "a" * 40 and admitted.hf_revision == "b" * 40
    assert admitted.marker_sha256 == hashlib.sha256(canonical(world.marker)).hexdigest()
    assert world.verifier.call_args.args[2] == "test-read-credential"
    assert world.subject.snapshot()["execution_authority"] is False
    count = world.fetch.call_count
    world.subject.snapshot()
    world.subject.admitted()
    world.subject.start()
    assert world.fetch.call_count == count and len(lifecycle.workers) == 1


def test_unresolved_attestation_never_admits_and_cannot_extend_window(world, lifecycle):
    world.verifier.side_effect = identity.EvidenceBlocked("RUNTIME_ATTESTATION_REJECTED")
    world.subject.start()
    deadline = world.subject._deadline
    lifecycle.workers[0]()
    assert world.fetch.call_count == world.verifier.call_count <= identity.MAX_RECOVERY_ATTEMPTS
    assert lifecycle.clock.waits[:5] == [10, 20, 40, 80, 120]
    assert max(lifecycle.clock.waits) == 120
    assert lifecycle.clock.now < deadline
    assert lifecycle.clock.now + lifecycle.clock.waits[-1] >= deadline
    assert world.subject.snapshot()["status"] == "BLOCKED"
    with pytest.raises(identity.EvidenceBlocked, match="IMMUTABLE_PROCESS"):
        world.subject.admitted()
    world.verifier.side_effect = None
    lifecycle.clock.now = deadline + 1
    world.subject.start()
    assert len(lifecycle.workers) == 1 and world.subject._deadline == deadline


@pytest.mark.parametrize("code", [
    "RUNTIME_PUBLICATION_BINDING_MISMATCH", "RUNTIME_PUBLISHER_RUN_MISMATCH",
    "RUNTIME_BINDING_ARTIFACT_AMBIGUOUS", "ARTIFACT_ARCHIVE_MISMATCH",
    "ARTIFACT_METADATA_MISMATCH", "RUNTIME_ATTESTATION_INVOCATION_MISMATCH",
    "RUNTIME_VERIFIER_OUTPUT_INVALID", "GITHUB_READ_AUTHENTICATION_FAILED",
    "GITHUB_READ_ACCESS_DENIED", "UNRECOGNIZED_FAILURE",
])
def test_identity_structure_policy_and_unknown_failures_are_terminal(world, lifecycle, code):
    world.fetch.side_effect = identity.EvidenceBlocked(code)
    world.subject.start()
    lifecycle.workers[0]()
    assert world.fetch.call_count == 1 and not lifecycle.clock.waits
    assert world.subject.error == code and world.subject.snapshot()["status"] == "BLOCKED"
    world.subject.start()
    assert len(lifecycle.workers) == 1


def test_error_changes_do_not_reset_deadline_or_attempt_cap(world, lifecycle, monkeypatch):
    monkeypatch.setattr(identity, "RECOVERY_WINDOW", 100000)
    failures = iter(["GITHUB_READ_RATE_LIMITED", "RUNTIME_BINDING_ARTIFACT_UNAVAILABLE",
                     "ARTIFACT_DOWNLOAD_TIMEOUT", "RUNTIME_ATTESTATION_REJECTED"] * 10)
    world.fetch.side_effect = lambda *a: (_ for _ in ()).throw(identity.EvidenceBlocked(next(failures)))
    world.subject.start()
    lifecycle.workers[0]()
    assert world.fetch.call_count == identity.MAX_RECOVERY_ATTEMPTS == 40
    assert len(lifecycle.clock.waits) == 39
    assert world.subject._deadline == 100000
    assert world.subject.snapshot()["status"] == "BLOCKED"


@pytest.mark.parametrize("retry_after", [4000, float("inf"), float("nan"), -1, True, "10"])
def test_invalid_or_unaffordable_retry_after_cannot_create_unbounded_work(world, lifecycle, retry_after):
    failure = identity.EvidenceBlocked("GITHUB_READ_RATE_LIMITED")
    failure.retry_after = retry_after
    world.fetch.side_effect = failure
    world.subject.start()
    lifecycle.workers[0]()
    assert world.fetch.call_count == 1 and not lifecycle.clock.waits
    assert world.subject.snapshot()["status"] == "BLOCKED"


def test_finite_retry_after_is_not_shortened(world, lifecycle):
    failure = identity.EvidenceBlocked("GITHUB_READ_RATE_LIMITED")
    failure.retry_after = 600
    world.fetch.side_effect = [failure, canonical(world.body)]
    world.subject.start()
    lifecycle.workers[0]()
    assert lifecycle.clock.waits == [600]
    assert world.subject.admitted().runtime_boot_id == "boot-one"


@pytest.mark.parametrize("retry_after,expected_attempts", [(600, 2), (4000, 1)])
def test_real_http_retry_delay_reaches_startup_worker(world, lifecycle, monkeypatch, retry_after, expected_attempts):
    import httpx
    from szl_readiness_artifact import Transport
    seen = []
    transports = []
    def respond(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(429, headers={"retry-after": str(retry_after)}, content=b"private body")
        return httpx.Response(200, json=world.body)
    def transport(token, stop):
        value = Transport(token, stop, clock=lifecycle.clock,
            client=httpx.Client(transport=httpx.MockTransport(respond)))
        transports.append(value)
        return value
    monkeypatch.setattr(identity, "Transport", transport)
    # Exercise the actual GET/error adapter; exact run/archive identity is
    # independently exercised by the existing fetch_binding fixtures above.
    world.fetch.side_effect = lambda transport, marker: canonical(transport.json("/fixture"))
    world.subject.start()
    lifecycle.workers[0]()
    assert len(seen) == expected_attempts
    assert all(request.method == "GET" for request in seen)
    assert all(value.client.is_closed for value in transports)
    if expected_attempts == 2:
        assert lifecycle.clock.waits == [600]
        assert world.subject.admitted().runtime_boot_id == "boot-one"
    else:
        assert not lifecycle.clock.waits
        assert world.subject.snapshot()["status"] == "BLOCKED"


@pytest.mark.parametrize("moment", ["fetch", "verifier", "measurement"])
@pytest.mark.parametrize("boundary", ["stop", "deadline"])
def test_late_success_cannot_latch_after_cancellation_or_deadline(world, lifecycle, monkeypatch, moment, boundary):
    def close():
        if boundary == "stop":
            world.subject.stop()
        else:
            lifecycle.clock.now = world.subject._deadline
    if moment == "fetch":
        def fetch(*a):
            close()
            return canonical(world.body)
        world.fetch.side_effect = fetch
    elif moment == "verifier":
        world.verifier.side_effect = lambda *a, **k: close()
    else:
        measure = identity.measure_catalog
        def measure_then_close(*a):
            measure(*a)
            close()
        monkeypatch.setattr(identity, "measure_catalog", measure_then_close)
    world.subject.start()
    lifecycle.workers[0]()
    assert world.subject.snapshot()["status"] == "BLOCKED"
    assert world.subject.error == ("RUNTIME_IDENTITY_STOPPED" if boundary == "stop"
                                    else "RUNTIME_IDENTITY_RECOVERY_EXHAUSTED")
    assert not lifecycle.clock.waits
    with pytest.raises(identity.EvidenceBlocked, match="IMMUTABLE_PROCESS"):
        world.subject.admitted()


def test_transport_and_verifier_share_the_fixed_remaining_budget(world, lifecycle):
    world.subject.start()
    lifecycle.clock.now = world.subject._deadline - 1
    world.subject.verify_once()
    assert world.transport.deadline == world.subject._deadline
    assert world.verifier.call_args.kwargs == {"stop": world.subject._stop,
                                               "deadline": world.subject._deadline}


def test_late_verifier_return_is_blocked_even_if_deadline_passes_during_call(world, lifecycle):
    def delayed_verification(*args, **kwargs):
        lifecycle.clock.now = 3601
    world.verifier.side_effect = delayed_verification
    world.subject.start()
    lifecycle.workers[0]()
    assert world.subject.snapshot()["status"] == "BLOCKED"
    with pytest.raises(identity.EvidenceBlocked, match="IMMUTABLE_PROCESS"):
        world.subject.admitted()


def test_stop_interrupts_backoff_and_prevents_restart(world, lifecycle, monkeypatch):
    world.fetch.side_effect = identity.EvidenceBlocked("GITHUB_READ_UPSTREAM_UNAVAILABLE")
    def wait(delay):
        world.subject.stop()
        return True
    monkeypatch.setattr(world.subject._stop, "wait", wait)
    world.subject.start()
    lifecycle.workers[0]()
    world.subject.start()
    assert world.fetch.call_count == 1 and len(lifecycle.workers) == 1
    assert world.subject._stop.is_set() and world.subject.snapshot()["status"] == "BLOCKED"


@pytest.mark.parametrize("invalid", ["marker", "credential", "stopped"])
def test_invalid_startup_inputs_cannot_be_repaired_into_a_worker(world, lifecycle, invalid):
    if invalid == "marker":
        (world.root / identity.MARKER).write_bytes(b"not JSON")
    elif invalid == "credential":
        world.env.pop("SZL_READINESS_GH_TOKEN")
    subject = identity.ProcessIdentity("boot", root=world.root, marker_root=world.root, environ=world.env)
    if invalid == "stopped":
        subject.stop()
    (world.root / identity.MARKER).write_bytes(canonical(world.marker))
    world.env["SZL_READINESS_GH_TOKEN"] = "later-credential"
    subject.start()
    subject.start()
    assert not lifecycle.workers and subject.snapshot()["status"] == "BLOCKED"
    world.fetch.assert_not_called()


def test_concurrent_start_creates_one_worker(world, monkeypatch):
    original_thread = threading.Thread
    barrier = threading.Barrier(9)
    workers = []
    def thread(**kwargs):
        workers.append(kwargs["target"])
        return Mock()
    monkeypatch.setattr(identity.threading, "Thread", thread)
    def start():
        barrier.wait(timeout=2)
        world.subject.start()
    callers = [original_thread(target=start) for _ in range(8)]
    for caller in callers:
        caller.start()
    barrier.wait(timeout=2)
    for caller in callers:
        caller.join(timeout=2)
        assert not caller.is_alive()
    assert len(workers) == 1


def test_stop_serializes_with_inflight_verifier_and_prevents_duplicate_io(world):
    entered = threading.Event()
    release = threading.Event()
    failures = []
    def verify(*a, **k):
        entered.set()
        assert release.wait(timeout=2)
    world.verifier.side_effect = verify
    def attempt():
        try:
            world.subject.verify_once()
        except identity.EvidenceBlocked as exc:
            failures.append(str(exc))
    first, second = threading.Thread(target=attempt), threading.Thread(target=attempt)
    first.start()
    assert entered.wait(timeout=2)
    second.start()
    world.subject.stop()
    release.set()
    for thread in (first, second):
        thread.join(timeout=2)
        assert not thread.is_alive()
    assert failures == ["RUNTIME_IDENTITY_STOPPED"] * 2
    assert world.fetch.call_count == world.verifier.call_count == 1
    assert world.subject.snapshot()["status"] == "BLOCKED"


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
