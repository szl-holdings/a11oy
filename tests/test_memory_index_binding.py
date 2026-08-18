# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11

import pytest

import routers.memory_index_binding as binding
from routers.memory_index_worker import WorkerConfig, WorkerContractError


IDENTITY = {
    "provider": "reviewed-provider",
    "model": "embedding-model",
    "revision": "revision-1",
    "dimension": 1024,
    "metric": "cosine",
    "normalization": "l2",
}


class Adapter:
    def __init__(self, identity=None) -> None:
        self._identity = dict(identity or IDENTITY)

    def identity(self):
        return dict(self._identity)

    def upsert(self, event):
        return {"accepted": True}

    def delete(self, event):
        return {"deleted": True}


def _config(digest: str) -> WorkerConfig:
    return WorkerConfig(
        worker_id="worker-1",
        generation_id="generation-1",
        generation_identity_digest=digest,
    )


def test_generation_identity_digest_is_canonical_and_deterministic() -> None:
    first = binding.generation_identity_digest(IDENTITY)
    reordered = dict(reversed(list(IDENTITY.items())))
    second = binding.generation_identity_digest(reordered)
    assert first == second
    assert len(first) == 64


def test_bound_run_requires_exact_adapter_digest(monkeypatch) -> None:
    digest = binding.generation_identity_digest(IDENTITY)
    captured = {}

    def fake_run(connect_factory, adapter, config):
        captured["adapter"] = adapter
        captured["config"] = config
        return {"state": "BATCH_COMPLETE", "leased": 0}

    monkeypatch.setattr(binding, "run_once", fake_run)
    adapter = Adapter()
    result = binding.run_bound_once(lambda: object(), adapter, _config(digest))
    assert captured["adapter"] is adapter
    assert captured["config"].generation_identity_digest == digest
    assert result["binding"] == "EXACT_ADAPTER_TO_ACTIVE_GENERATION"
    assert result["adapter_identity"]["identity_digest"] == digest
    assert result["adapter_identity"]["schema"] == binding.IDENTITY_SCHEMA


def test_mismatched_adapter_is_blocked_before_worker_execution(monkeypatch) -> None:
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(binding, "run_once", fake_run)
    with pytest.raises(WorkerContractError, match="does not match"):
        binding.run_bound_once(lambda: object(), Adapter(), _config("f" * 64))
    assert called is False


@pytest.mark.parametrize(
    "identity",
    [
        {**IDENTITY, "dimension": 0},
        {**IDENTITY, "metric": "invented"},
        {**IDENTITY, "normalization": "invented"},
        {key: value for key, value in IDENTITY.items() if key != "revision"},
        {**IDENTITY, "extra": "field"},
    ],
)
def test_identity_contract_fails_closed(identity) -> None:
    with pytest.raises(WorkerContractError):
        binding.generation_identity_digest(identity)


def test_adapter_identity_read_failure_is_sanitized() -> None:
    class Broken(Adapter):
        def identity(self):
            raise RuntimeError("credential-shaped provider detail")

    with pytest.raises(WorkerContractError, match="could not be read") as error:
        binding.run_bound_once(lambda: object(), Broken(), _config("f" * 64))
    assert "credential-shaped" not in str(error.value)
