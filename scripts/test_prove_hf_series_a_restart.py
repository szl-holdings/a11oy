from __future__ import annotations

import importlib.util
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


class Response:
    def __init__(self, url: str, *, value=None, content: bytes = b"") -> None:
        self.url = url
        self.value = value
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.value


def status(source: str, *, receipts: int, head: str) -> dict:
    return {
        "schema": "szl.series-a-status/v1",
        "state": "OBSERVED",
        "terminal": True,
        "source_revision": source,
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
        self.statuses = [
            status(source, receipts=1, head="2" * 64),
            status(source, receipts=2, head="3" * 64),
        ]
        self.headers = {}

    def get(self, url: str, **_kwargs):
        if url.endswith("/series-a/status"):
            return Response(url, value=self.statuses.pop(0))
        if url.endswith("/api/build-info"):
            return Response(url, value={"build": {"revision": self.source}})
        if url.endswith("/series-a/public-key"):
            return Response(
                url,
                content=b"-----BEGIN PUBLIC KEY-----\nkey\n-----END PUBLIC KEY-----\n",
            )
        if "/series-a/receipts?" in url:
            return Response(
                url,
                value={
                    "items": [
                        {"receipt_hash": "3" * 64},
                        {"receipt_hash": "2" * 64},
                    ]
                },
            )
        raise AssertionError(url)


class StartupReceiptSession(Session):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.statuses = [
            status(source, receipts=0, head=None),
            status(source, receipts=1, head="2" * 64),
            status(source, receipts=2, head="3" * 64),
        ]
        self.posts = 0

    def post(self, *_args, **_kwargs):
        self.posts += 1
        raise AssertionError("public restart proof must not bypass passports")


class TransientStartupSession(StartupReceiptSession):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.status_calls = 0

    def get(self, url: str, **kwargs):
        if url.endswith("/series-a/status"):
            self.status_calls += 1
            if self.status_calls == 2:
                raise TimeoutError("startup runtime is still settling")
        return super().get(url, **kwargs)


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
    assert report["proof"]["database_instance_stable"] is True
    assert report["proof"]["pre_restart_chain_head_recovered"] is True
    assert api.calls == [
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False}
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


def test_prove_retries_transient_startup_capture_failure(monkeypatch) -> None:
    source = "a" * 40
    api = Api()
    session = TransientStartupSession(source)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        api=api,
        session=session,
        repo_id="SZLHOLDINGS/a11oy",
        origin="https://a-11-oy.com",
        source_sha=source,
        attempts=3,
        retry_seconds=0,
    )

    assert report["ok"] is True
    assert session.status_calls == 4
    assert report["before"]["storage"]["receipt_count"] == 1


def test_prove_uses_one_deadline_across_pre_and_post_restart(monkeypatch) -> None:
    source = "a" * 40
    api = Api()
    clock = {"now": 0.0}

    monkeypatch.setattr(proof.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        proof.time,
        "sleep",
        lambda seconds: clock.__setitem__("now", clock["now"] + seconds),
    )

    with pytest.raises(
        proof.RestartProofError,
        match="shared restart-proof deadline expired after restart",
    ):
        proof.prove(
            api=api,
            session=StartupReceiptSession(source),
            repo_id="SZLHOLDINGS/a11oy",
            origin="https://a-11-oy.com",
            source_sha=source,
            attempts=2,
            retry_seconds=10,
        )

    assert clock["now"] == 20.0
    assert api.calls == [
        {"repo_id": "SZLHOLDINGS/a11oy", "factory_reboot": False}
    ]


def test_validate_restart_rejects_key_or_database_identity_change() -> None:
    before = {
        "source_revision": "a" * 40,
        "signing_key_source": proof.EXPECTED_SIGNER,
        "public_key_sha256": "b" * 64,
        "storage": {
            "instance_id": "store_" + ("1" * 32),
            "created_at": "2026-07-28T15:00:00.000Z",
            "receipt_count": 1,
            "chain_head": "2" * 64,
        },
    }
    for update in (
        {"public_key_sha256": "c" * 64},
        {"storage": {**before["storage"], "instance_id": "store_" + ("4" * 32)}},
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
