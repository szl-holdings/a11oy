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


class UnreachablePreActivationSession(Session):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.pre_activation = True

    def get(self, url: str, **kwargs):
        if self.pre_activation and url.endswith("/series-a/status"):
            self.pre_activation = False
            raise TimeoutError("pre-activation runtime returned no bytes")
        return super().get(url, **kwargs)


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

    def restart_space(self, **kwargs):
        self.calls.append(kwargs)
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
        origin="https://a-11-oy.com",
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
        origin="https://a-11-oy.com",
        source_sha=source,
        attempts=3,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert report["activation_restart_requested"] is True
    assert report["durability_restart_requested"] is True


def test_prove_restarts_before_probe_when_runtime_is_unreachable(
    monkeypatch,
) -> None:
    source = "a" * 40
    api = Api()
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=api,
        session=UnreachablePreActivationSession(source),
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=source,
        attempts=3,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert report["pre_activation_runtime_boot_id"] is None
    assert report["pre_activation_runtime_observed"] is False
    assert report["proof"]["activation_runtime_recovery_observed"] is True
    assert report["proof"]["activation_boot_identity_change_observed"] is False
    assert api.calls == [
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False},
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False},
    ]


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
        origin="https://a-11-oy.com",
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
            origin="https://a-11-oy.com",
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
        origin="https://a-11-oy.com",
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
        origin="https://a-11-oy.com",
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
        origin="https://a-11-oy.com",
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
            origin="https://a-11-oy.com",
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
            origin="https://a-11-oy.com",
            source_sha=source,
            attempts=3,
            retry_seconds=0,
        )

    assert api.calls == [
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False},
    ]


def test_failure_report_preserves_secret_free_restart_evidence() -> None:
    secret = "hf_example_secret_value"
    report = proof.failure_report(
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://a-11-oy.com",
        source_revision="a" * 40,
        evidence={
            "phase": "recover_post_restart_head",
            "before": {
                "runtime_boot_id": "boot_" + ("1" * 32),
                "storage": {
                    "chain_head": BEFORE_HASH,
                    "last_receipt_sequence": 1,
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
    assert report["secret_values_recorded"] is False
    assert report["evidence"]["before"]["storage"]["chain_head"] == BEFORE_HASH
    assert secret not in encoded
    assert "[REDACTED]" in encoded


def test_main_writes_failure_report_and_remains_nonzero(
    monkeypatch,
    tmp_path: pathlib.Path,
) -> None:
    secret = "hf_example_secret_value"
    output = tmp_path / "restart-proof.json"
    monkeypatch.setenv("HF_TOKEN", secret)
    monkeypatch.setattr(proof, "HfApi", lambda token: Api())

    def refuse(**kwargs):
        kwargs["evidence"]["phase"] = "verify_pre_restart_head"
        raise proof.RestartProofError("refused with " + secret)

    monkeypatch.setattr(proof, "prove", refuse)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--source-sha",
            "a" * 40,
            "--output",
            str(output),
        ],
    )

    with pytest.raises(proof.RestartProofError, match="refused"):
        proof.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["evidence"]["phase"] == "verify_pre_restart_head"
    assert secret not in output.read_text(encoding="utf-8")


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
            origin="https://a-11-oy.com",
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
        proof.capture(session, "https://a-11-oy.com", source)


@pytest.mark.parametrize(
    "value",
    [
        "http://a-11-oy.com",
        "https://user:pass@a-11-oy.com",
        "https://a-11-oy.com/path",
    ],
)
def test_origin_rejects_noncanonical_or_credentialed_values(value: str) -> None:
    with pytest.raises(proof.RestartProofError):
        proof.normalize_origin(value)
