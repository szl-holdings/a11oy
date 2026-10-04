from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest


if "huggingface_hub" not in sys.modules:
    hub_stub = types.ModuleType("huggingface_hub")
    hub_stub.HfApi = object
    sys.modules["huggingface_hub"] = hub_stub

SCRIPT = pathlib.Path(__file__).with_name("prove_hf_series_a_restart.py")
SPEC = importlib.util.spec_from_file_location("prove_hf_series_a_restart", SCRIPT)
assert SPEC and SPEC.loader
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)

BEFORE_ENVELOPE = {"payload": "before"}
AFTER_ENVELOPE = {"payload": "after"}


def envelope_hash(value: dict) -> str:
    return proof.hashlib.sha256(
        proof.json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


BEFORE_HASH = envelope_hash(BEFORE_ENVELOPE)
AFTER_HASH = envelope_hash(AFTER_ENVELOPE)
PUBLIC_KEY = b"-----BEGIN PUBLIC KEY-----\nkey\n-----END PUBLIC KEY-----\n"
PUBLIC_KEY_HASH = proof.hashlib.sha256(PUBLIC_KEY).hexdigest()


class Response:
    def __init__(
        self,
        url: str,
        *,
        value=None,
        content: bytes = b"",
        status_code: int = 200,
    ) -> None:
        self.url = url
        self.value = value
        self.content = content
        self.status = status_code

    def raise_for_status(self) -> None:
        if not 200 <= self.status < 300:
            raise proof.RestartProofError(
                f"{self.url} returned HTTP {self.status}"
            )

    def json(self):
        return self.value


def status(
    source: str,
    *,
    receipts: int,
    head: str,
    boot: str = "boot_" + ("1" * 32),
) -> dict:
    return {
        "schema": "szl.series-a-status/v1",
        "state": "OBSERVED",
        "terminal": True,
        "source_revision": source,
        "runtime_boot_id": boot,
        "signing_key_source": proof.EXPECTED_SIGNER,
        "database": proof.EXPECTED_DATABASE,
        "storage": {
            "persistence_required": True,
            "required_mount": "/data",
            "mount_verified": True,
            "journal_mode": "DELETE",
            "instance_id": "store_" + ("1" * 32),
            "created_at": "2026-07-28T15:00:00.000Z",
            "receipt_count": receipts,
            "last_receipt_sequence": receipts,
            "chain_head": head,
        },
    }


class Session:
    def __init__(self, source: str) -> None:
        self.source = source
        self.current_boot = "boot_" + ("1" * 32)
        self.statuses = [
            status(source, receipts=1, head=BEFORE_HASH),
            status(
                source,
                receipts=1,
                head=BEFORE_HASH,
                boot="boot_" + ("2" * 32),
            ),
            status(
                source,
                receipts=2,
                head=AFTER_HASH,
                boot="boot_" + ("3" * 32),
            ),
        ]
        self.headers = {}

    def recovery_record(self) -> dict:
        before_restart = self.current_boot != "boot_" + ("3" * 32)
        receipts = 1 if before_restart else 2
        head = BEFORE_HASH if before_restart else AFTER_HASH
        return {
            "schema": "szl.series-a-receipt-recovery/v1",
            "source_revision": self.source,
            "runtime_boot_id": self.current_boot,
            "signing_key_source": proof.EXPECTED_SIGNER,
            "public_key_sha256": PUBLIC_KEY_HASH,
            "database": proof.EXPECTED_DATABASE,
            "storage": status(
                self.source,
                receipts=receipts,
                head=head,
                boot=self.current_boot,
            )["storage"],
            "item": {
                "sequence": 1,
                "receipt_hash": BEFORE_HASH,
                "envelope": BEFORE_ENVELOPE,
            },
        }

    def get(self, url: str, **_kwargs):
        if url.endswith("/series-a/status"):
            value = self.statuses.pop(0)
            if isinstance(value, dict) and value.get("runtime_boot_id"):
                self.current_boot = value["runtime_boot_id"]
            return Response(url, value=value)
        if url.endswith("/api/build-info"):
            return Response(url, value={"build": {"revision": self.source}})
        if url.endswith("/api/a11oy/v1/honest"):
            return Response(url, value={"git_sha": self.source})
        if url.endswith("/series-a/public-key"):
            return Response(
                url,
                content=PUBLIC_KEY,
            )
        if url.endswith("/series-a/receipts?receipt_hash=" + BEFORE_HASH):
            return Response(url, value=self.recovery_record())
        raise AssertionError(url)


class StartupReceiptSession(Session):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.statuses = [
            status(source, receipts=0, head=None),
            status(
                source,
                receipts=0,
                head=None,
                boot="boot_" + ("2" * 32),
            ),
            status(
                source,
                receipts=1,
                head=BEFORE_HASH,
                boot="boot_" + ("2" * 32),
            ),
            status(
                source,
                receipts=2,
                head=AFTER_HASH,
                boot="boot_" + ("3" * 32),
            ),
        ]
        self.posts = 0

    def post(self, *_args, **_kwargs):
        self.posts += 1
        raise AssertionError("public restart proof must not bypass passports")


class DrainingSession(Session):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.statuses = [
            status(source, receipts=1, head=BEFORE_HASH),
            status(source, receipts=1, head=BEFORE_HASH),
            status(
                source,
                receipts=1,
                head=BEFORE_HASH,
                boot="boot_" + ("2" * 32),
            ),
            status(
                source,
                receipts=1,
                head=BEFORE_HASH,
                boot="boot_" + ("2" * 32),
            ),
            status(
                source,
                receipts=2,
                head=AFTER_HASH,
                boot="boot_" + ("3" * 32),
            ),
        ]


class TransientStartupSession(StartupReceiptSession):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.status_calls = 0

    def get(self, url: str, **kwargs):
        if url.endswith("/series-a/status"):
            self.status_calls += 1
            if self.status_calls == 2:
                raise TimeoutError("transient startup status timeout")
        return super().get(url, **kwargs)


class PreActivationSession(Session):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.statuses.insert(
            0,
            {
                "ok": False,
                "label": "UNAVAILABLE",
                "reason": "DatabaseError: database disk image is malformed",
            },
        )


class LaggingReceiptSession(Session):
    def __init__(self, source: str, *, recover: bool) -> None:
        super().__init__(source)
        self.recover = recover
        self.receipt_calls = 0

    def recovery_record(self) -> dict:
        self.receipt_calls += 1
        if self.receipt_calls > 1 and (
            self.receipt_calls == 2 or not self.recover
        ):
            raise proof.RestartProofError(
                "exact receipt recovery returned HTTP 404"
            )
        return super().recovery_record()


class MissingPreRestartReceiptSession(Session):
    def recovery_record(self) -> dict:
        raise proof.RestartProofError(
            "exact receipt recovery returned HTTP 404"
        )


class Api:
    def __init__(self) -> None:
        self.calls = []
        self.pause_calls = []
        self.runtime_calls = []
        self.stage = "RUNNING"

    def pause_space(self, **kwargs):
        self.pause_calls.append(kwargs)
        self.stage = "PAUSED"
        return SimpleNamespace(stage=SimpleNamespace(value="PAUSING"))

    def get_space_runtime(self, **kwargs):
        self.runtime_calls.append(kwargs)
        return SimpleNamespace(stage=SimpleNamespace(value=self.stage))

    def restart_space(self, **kwargs):
        self.calls.append(kwargs)
        self.stage = "RUNNING"
        return SimpleNamespace(
            runtime=SimpleNamespace(stage=SimpleNamespace(value="RESTARTING"))
        )


def test_prove_requires_same_key_database_and_chain_after_restart(monkeypatch) -> None:
    source = "a" * 40
    api = Api()
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=api,
        session=Session(source),
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=2,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert report["restart_requested"] is True
    assert report["proof"]["runtime_boot_identity_changed"] is True
    assert report["proof"]["database_instance_stable"] is True
    assert report["proof"]["pre_restart_chain_head_recovered"] is True
    assert api.calls == [
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False},
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False}
    ]


def test_prove_polls_past_pre_activation_runtime(monkeypatch) -> None:
    source = "a" * 40
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=Api(),
        session=PreActivationSession(source),
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=3,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert report["activation_restart_requested"] is True
    assert report["durability_restart_requested"] is True


def test_prove_waits_for_startup_receipt_without_direct_refresh(
    monkeypatch,
) -> None:
    source = "a" * 40
    api = Api()
    session = StartupReceiptSession(source)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=api,
        session=session,
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=2,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert session.posts == 0
    assert report["before"]["storage"]["receipt_count"] == 1
    assert report["before"]["runtime_boot_id"] != report["after"]["runtime_boot_id"]


def test_prove_rejects_successful_capture_from_same_runtime(monkeypatch) -> None:
    source = "a" * 40
    api = Api()
    session = Session(source)
    session.statuses[2]["runtime_boot_id"] = session.statuses[1][
        "runtime_boot_id"
    ]
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        proof.RestartProofError,
        match="runtime restart was not observed",
    ):
        proof.prove(
            api=api,
            session=session,
            repo_id="SZLHOLDINGS/a11oy",
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=source,
            attempts=2,
            retry_seconds=0,
        )


def test_prove_polls_past_draining_old_runtime(monkeypatch) -> None:
    source = "a" * 40
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=Api(),
        session=DrainingSession(source),
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=2,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert report["pre_activation_runtime_boot_id"] == "boot_" + ("1" * 32)
    assert report["before"]["runtime_boot_id"] == "boot_" + ("2" * 32)
    assert report["after"]["runtime_boot_id"] == "boot_" + ("3" * 32)


def test_prove_retries_transient_startup_capture(monkeypatch) -> None:
    source = "a" * 40
    session = TransientStartupSession(source)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=Api(),
        session=session,
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=3,
        retry_seconds=0,
    )

    assert report["ok"] is True


def test_prove_polls_until_pre_restart_head_is_recovered(monkeypatch) -> None:
    source = "a" * 40
    session = LaggingReceiptSession(source, recover=True)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=Api(),
        session=session,
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=3,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert session.receipt_calls == 3
    assert report["proof"]["pre_restart_chain_head_recovered"] is True


def test_prove_fails_closed_when_pre_restart_head_never_recovers(
    monkeypatch,
) -> None:
    source = "a" * 40
    session = LaggingReceiptSession(source, recover=False)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        proof.RestartProofError,
        match="not recovered after bounded polling",
    ):
        proof.prove(
            api=Api(),
            session=session,
            repo_id="SZLHOLDINGS/a11oy",
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=source,
            attempts=3,
            retry_seconds=0,
        )
    assert session.receipt_calls == 4


def test_prove_refuses_missing_head_before_durability_restart(
    monkeypatch,
) -> None:
    source = "a" * 40
    api = Api()
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        proof.RestartProofError,
        match="exact receipt recovery returned HTTP 404",
    ):
        proof.prove(
            api=api,
            session=MissingPreRestartReceiptSession(source),
            repo_id="SZLHOLDINGS/a11oy",
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=source,
            attempts=3,
            retry_seconds=0,
        )

    assert api.calls == [
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False},
    ]


def test_failure_report_carries_only_fixed_codes_and_bounded_evidence() -> None:
    secret = "hf_example_secret_value"
    report = proof.failure_report(
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_revision="a" * 40,
        evidence={
            "phase": "recover_post_restart_head",
            "before": {
                "runtime_boot_id": "boot_" + ("1" * 32),
                "storage": {
                    "chain_head": BEFORE_HASH,
                    "last_receipt_sequence": 1,
                    "provider_note": "Traceback: internal error body",
                },
            },
        },
        error=proof.RestartProofError(
            "head unavailable while using " + secret
        ),
        secrets=(secret,),
    )

    encoded = proof.json.dumps(report, sort_keys=True)
    assert report["ok"] is False
    assert report["status"] == "FAIL"
    assert report["diagnostic_code"] == "RESTART_CONTRACT_FAILED"
    assert report["error"] == {"type": "RestartProofError", "code": "RESTART_CONTRACT_FAILED"}
    assert report["secret_values_recorded"] is False
    assert report["evidence"]["before"]["storage"]["chain_head"] == BEFORE_HASH
    assert secret not in encoded
    assert "head unavailable" not in encoded
    assert "Traceback" not in encoded


def test_main_reports_setup_required_by_name_without_provider_effects(
    monkeypatch,
    tmp_path: pathlib.Path,
) -> None:
    output = tmp_path / "restart-proof.json"
    monkeypatch.delenv("HF_TOKEN", raising=False)
    attempts = []

    def refuse(*args, **kwargs):
        attempts.append("provider effect")
        raise AssertionError("SETUP_REQUIRED must stop before any provider call")

    monkeypatch.setattr(proof, "prove", refuse)
    monkeypatch.setattr(proof.bounds, "BoundedTransport", refuse)

    code = proof.main(["--source-sha", "a" * 40, "--output", str(output)])

    raw = output.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert code == 1
    assert report["state"] == "SETUP_REQUIRED"
    assert report["diagnostic_code"] == "SETUP_REQUIRED"
    assert report["missing_secret_names"] == ["HF_TOKEN"]
    assert report["ok"] is False
    assert report["credential_authority_state"] == "UNKNOWN"
    assert attempts == []


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["--repo-id", "SZLHOLDINGS/other"], "SPACE_SCOPE_REJECTED"),
        (["--repo-id", "szlholdings/a11oy"], "SPACE_SCOPE_REJECTED"),
        (["--origin", "https://a-11-oy.com"], "DESTINATION_REJECTED"),
        (["--origin", "https://szlholdings-a11oy.hf.space.evil.example"], "DESTINATION_REJECTED"),
    ],
)
def test_main_rejects_wrong_space_or_origin_before_credentials(
    monkeypatch, tmp_path: pathlib.Path, argv, code
) -> None:
    secret = "hf_example_secret_value_long_enough"
    monkeypatch.setenv("HF_TOKEN", secret)
    output = tmp_path / "restart-proof.json"
    monkeypatch.setattr(proof, "prove", lambda **_k: (_ for _ in ()).throw(AssertionError("no")))
    assert proof.main(["--source-sha", "a" * 40, "--output", str(output), *argv]) == 1
    raw = output.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert report["diagnostic_code"] == code
    assert secret not in raw


def test_prove_uses_one_shared_deadline(monkeypatch) -> None:
    source = "a" * 40
    session = StartupReceiptSession(source)
    clock = iter((0.0, 0.0, 0.0, 0.0, 0.0, 1.1))
    monkeypatch.setattr(proof.time, "monotonic", lambda: next(clock, 1.1))
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    with pytest.raises(proof.RestartProofError, match="deadline exhausted"):
        proof.prove(
            api=Api(),
            session=session,
            repo_id="SZLHOLDINGS/a11oy",
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=source,
            attempts=90,
            retry_seconds=10,
            deadline_seconds=1,
        )


def test_validate_restart_rejects_key_or_database_identity_change() -> None:
    before = {
        "source_revision": "a" * 40,
        "runtime_boot_id": "boot_" + ("1" * 32),
        "signing_key_source": proof.EXPECTED_SIGNER,
        "public_key_sha256": "b" * 64,
        "storage": {
            "instance_id": "store_" + ("1" * 32),
            "created_at": "2026-07-28T15:00:00.000Z",
            "receipt_count": 1,
            "chain_head": "2" * 64,
        },
    }
    restarted = {"runtime_boot_id": "boot_" + ("2" * 32)}
    for update in (
        {"runtime_boot_id": before["runtime_boot_id"]},
        {**restarted, "public_key_sha256": "c" * 64},
        {
            **restarted,
            "storage": {
                **before["storage"],
                "instance_id": "store_" + ("4" * 32),
            },
        },
    ):
        after = {**before, **update}
        with pytest.raises(proof.RestartProofError):
            proof.validate_restart(before, after, {"2" * 64})


def test_capture_rejects_missing_database_creation_identity() -> None:
    source = "a" * 40
    session = Session(source)
    session.statuses[0]["storage"]["created_at"] = None
    with pytest.raises(proof.RestartProofError):
        proof.capture(session, "https://szlholdings-a11oy.hf.space", source)


@pytest.mark.parametrize(
    "value",
    [
        "http://szlholdings-a11oy.hf.space",
        "https://user:pass@szlholdings-a11oy.hf.space",
        "https://szlholdings-a11oy.hf.space/path",
        "https://a-11-oy.com",
        "https://SZLHOLDINGS-A11OY.hf.space",
        "https://szlholdings-a11oy.hf.space.evil.example",
        "https://szlholdings-a11oy.hf.space:8443",
    ],
)
def test_origin_rejects_noncanonical_or_credentialed_values(value: str) -> None:
    with pytest.raises(proof.RestartProofError):
        proof.normalize_origin(value)


# --- Bounded live-proof admission -----------------------------------------


def _load_checker():
    import importlib.util

    path = pathlib.Path(__file__).with_name("check_hf_manual_prerequisites.py")
    spec = importlib.util.spec_from_file_location("checker_for_series_a", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prove_records_running_stage_and_deployed_source(monkeypatch) -> None:
    source = "a" * 40
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    report = proof.prove(
        api=Api(), session=Session(source), repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space", source_sha=source,
        attempts=2, retry_seconds=0,
    )
    assert report["proof"]["running_stage_and_source_observed"] is True
    assert report["durability_running"]["stage"] == "RUNNING"
    assert report["durability_running"]["git_sha"] == source


class StaleHonestSession(Session):
    def get(self, url: str, **kwargs):
        if url.endswith("/api/a11oy/v1/honest"):
            return Response(url, value={"git_sha": "b" * 40})
        return super().get(url, **kwargs)


def test_restart_proof_times_out_when_the_deployed_source_never_serves(monkeypatch) -> None:
    source = "a" * 40
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    with pytest.raises(proof.RestartProofError) as excinfo:
        proof.prove(
            api=Api(), session=StaleHonestSession(source), repo_id="SZLHOLDINGS/a11oy",
            origin="https://szlholdings-a11oy.hf.space", source_sha=source,
            attempts=2, retry_seconds=0,
        )
    assert proof._code(excinfo.value) == "RESTART_PROOF_TIMEOUT"


class NotRunningApi(Api):
    def restart_space(self, **kwargs):
        value = super().restart_space(**kwargs)
        self.stage = "BUILDING"
        return value


def test_restart_proof_times_out_when_the_space_never_reaches_running(monkeypatch) -> None:
    source = "a" * 40
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    with pytest.raises(proof.RestartProofError) as excinfo:
        proof.prove(
            api=NotRunningApi(), session=Session(source), repo_id="SZLHOLDINGS/a11oy",
            origin="https://szlholdings-a11oy.hf.space", source_sha=source,
            attempts=2, retry_seconds=0,
        )
    assert proof._code(excinfo.value) == "RESTART_PROOF_TIMEOUT"


@pytest.mark.parametrize("phase", ["activation", "durability"])
@pytest.mark.parametrize("stage", ["RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "NO_APP_FILE"])
def test_terminal_provider_stage_ends_existing_read_loop_without_more_calls(monkeypatch, phase, stage):
    calls = []
    evidence = {}

    class RuntimeApi:
        def get_space_runtime(self, **kwargs):
            calls.append(kwargs)
            return {"runtime": {"stage": stage, "errorMessage": "private provider traceback"}}

    class NoApplicationReads:
        def get(self, *_args, **_kwargs):
            pytest.fail("terminal provider state must not read the application")

    monkeypatch.setattr(proof.time, "sleep", lambda _s: pytest.fail("terminal state must not sleep"))
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof.await_running_source(
            RuntimeApi(), NoApplicationReads(), repo_id=proof.bounds.CANONICAL_SPACE,
            origin=proof.bounds.CANONICAL_ORIGIN, expected_source="a" * 40,
            deadline=proof.time.monotonic() + 60, attempts=30, retry_seconds=10,
            phase=phase, evidence=evidence,
        )
    assert excinfo.value.code == "PROVIDER_TERMINAL_STATE"
    assert calls == [{"repo_id": proof.bounds.CANONICAL_SPACE}]
    terminal = evidence["terminal_provider_state"]
    assert terminal["stage"] == stage and terminal["phase"] == phase
    assert terminal["attempt"] == 1
    assert terminal["expected_source_revision"] == "a" * 40
    assert terminal["runtime_source_verified"] is False
    assert "private provider" not in json.dumps(evidence)


@pytest.mark.parametrize("stage", [
    "BUILDING", "APP_STARTING", "RUNNING_BUILDING", "RUNNING_APP_STARTING",
    "PAUSED", "STOPPED", "UNKNOWN", "RUNTIME_ERROR_ADDITIONAL", "unrecognized stage",
])
def test_intermediate_or_unrecognized_stage_keeps_source_verification(monkeypatch, stage):
    stages = iter([stage, "RUNNING"])
    reads = []
    evidence = {}

    class RuntimeApi:
        def get_space_runtime(self, **_kwargs):
            reads.append("runtime")
            return {"stage": next(stages)}

    class HonestSession:
        def get(self, url, **_kwargs):
            reads.append("honest")
            assert url == proof.bounds.CANONICAL_ORIGIN + proof.HONEST_ROUTE
            return Response(url, value={"git_sha": "a" * 40})

    monkeypatch.setattr(proof.time, "sleep", lambda _s: None)
    result = proof.await_running_source(
        RuntimeApi(), HonestSession(), repo_id=proof.bounds.CANONICAL_SPACE,
        origin=proof.bounds.CANONICAL_ORIGIN, expected_source="a" * 40,
        deadline=proof.time.monotonic() + 60, attempts=2, retry_seconds=0,
        phase="activation", evidence=evidence,
    )
    assert result == {"stage": "RUNNING", "git_sha": "a" * 40, "attempts": 2}
    assert reads == ["runtime", "runtime", "honest"]
    assert "terminal_provider_state" not in evidence


def test_expired_deadline_does_not_become_a_terminal_provider_observation(monkeypatch):
    clock = iter([0.0, 2.0])
    monkeypatch.setattr(proof.time, "monotonic", lambda: next(clock))
    evidence = {}
    api = SimpleNamespace(get_space_runtime=lambda **_k: {"stage": "RUNTIME_ERROR"})
    with pytest.raises(proof.RestartProofError) as excinfo:
        proof.await_running_source(
            api, None, repo_id=proof.bounds.CANONICAL_SPACE,
            origin=proof.bounds.CANONICAL_ORIGIN, expected_source="a" * 40,
            deadline=1.0, attempts=30, retry_seconds=10, phase="activation", evidence=evidence,
        )
    assert excinfo.value.code == "RESTART_PROOF_TIMEOUT"
    assert "terminal_provider_state" not in evidence


def test_terminal_evidence_survives_a_full_observation_buffer(monkeypatch):
    stages = iter(["APP_STARTING"] * 32 + ["RUNTIME_ERROR"])
    api = SimpleNamespace(get_space_runtime=lambda **_k: {"stage": next(stages)})
    evidence = {"activation_running_source_observations": [
        {"stage": "APP_STARTING", "detail": "a" * 150} for _ in range(32)
    ]}
    monkeypatch.setattr(proof.time, "sleep", lambda _s: None)
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof.await_running_source(
            api, None, repo_id=proof.bounds.CANONICAL_SPACE,
            origin=proof.bounds.CANONICAL_ORIGIN, expected_source="a" * 40,
            deadline=proof.time.monotonic() + 60, attempts=90, retry_seconds=0,
            phase="durability", evidence=evidence,
        )
    report = proof.failure_report(
        repo_id=proof.bounds.CANONICAL_SPACE, origin=proof.bounds.CANONICAL_ORIGIN,
        source_revision="a" * 40, evidence=evidence, error=excinfo.value,
    )
    assert len(evidence["durability_running_source_observations"]) == 32
    assert report["evidence"]["terminal_provider_state"]["attempt"] == 33
    assert report["diagnostic_code"] == "PROVIDER_TERMINAL_STATE"
    assert len(json.dumps(report).encode()) <= proof.MAX_REPORT_BYTES


def test_pass_report_is_admitted_only_as_an_exact_bounded_pass(monkeypatch, tmp_path) -> None:
    source = "a" * 40
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    api = Api()
    result = proof.prove(
        api=api, session=Session(source), repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space", source_sha=source,
        attempts=2, retry_seconds=0,
    )
    effects = [{"effect": "pause_space", "repo_id": "SZLHOLDINGS/a11oy"},
               {"effect": "restart_space", "repo_id": "SZLHOLDINGS/a11oy"}] * 2
    report = proof.pass_report(result, deadline_seconds=1200, effects=effects)
    report["source_revision"] = source
    output = tmp_path / "series-a.json"
    encoded = proof.bounds.write_json(output, report)
    assert len(encoded.encode("utf-8")) <= 16 * 1024
    checker = _load_checker()
    assert checker.inspect_live_proof(output, "series_a", 0, source) == {
        "report_valid": True, "state": "PROVEN"}
    assert checker.inspect_live_proof(output, "series_a", 1, source)["state"] == "UNPROVEN"
    # An effect on any other Space makes the report inadmissible.
    report["effects"].append({"effect": "restart_space", "repo_id": "SZLHOLDINGS/other"})
    proof.bounds.write_json(output, report)
    assert checker.inspect_live_proof(output, "series_a", 0, source)["state"] == "UNPROVEN"


class _Resp:
    def __init__(self, url, payload, status=200):
        self._url, self._body, self.status = url, json.dumps(payload).encode(), status

    def read(self, *_a):
        return self._body

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def test_main_redirect_on_space_control_is_a_fixed_code_without_body(monkeypatch, tmp_path) -> None:
    import io
    from urllib.error import HTTPError

    secret = "hf_example_secret_value_long_enough"
    monkeypatch.setenv("HF_TOKEN", secret)
    seen = []

    class Opener:
        def open(self, request, timeout=None):
            seen.append(request.full_url)
            raise HTTPError(request.full_url, 307, "redirect", {"Location": "https://evil.example/"},
                            io.BytesIO(b"<html>provider page " + secret.encode() + b"</html>"))

    def factory(**kwargs):
        return proof.bounds.BoundedTransport(opener=Opener(), sleep=lambda _s: None, **kwargs)

    output = tmp_path / "series-a.json"
    code = proof.main(["--source-sha", "a" * 40, "--output", str(output)], transport_factory=factory)
    raw = output.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert code == 1
    assert report["diagnostic_code"] == "REDIRECT_REJECTED"
    assert secret not in raw and "provider page" not in raw and "evil.example" not in raw
    assert len(seen) == 1
    assert all(url.startswith(("https://szlholdings-a11oy.hf.space/api/",
                               "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy"))
               for url in seen)
