from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.hf_existing_space_guard import (
    SpaceGuardError,
    guard_report,
    install_existing_space_guard,
)


class ProviderError(RuntimeError):
    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.response = SimpleNamespace(status_code=status)


def api_class(*, observed=None, error_status=None):
    class FakeApi:
        create_calls = []
        info_calls = []

        def repo_info(self, **kwargs):
            type(self).info_calls.append(kwargs)
            if error_status is not None:
                raise ProviderError(error_status)
            return observed

        def create_repo(self, *args, **kwargs):
            type(self).create_calls.append((args, kwargs))
            return {"created": True, "args": args, "kwargs": kwargs}

    return FakeApi


def test_existing_public_space_is_reused_without_create_call():
    FakeApi = api_class(
        observed=SimpleNamespace(id="SZLHOLDINGS/terra", private=False)
    )
    install_existing_space_guard(FakeApi)
    api = FakeApi()

    result = api.create_repo(
        repo_id="SZLHOLDINGS/terra",
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
        private=False,
    )

    assert result.id == "SZLHOLDINGS/terra"
    assert FakeApi.create_calls == []
    assert FakeApi.info_calls == [
        {
            "repo_id": "SZLHOLDINGS/terra",
            "repo_type": "space",
            "token": None,
        }
    ]
    report = guard_report(FakeApi)
    assert report["existing_spaces_reused"] == 1
    assert report["missing_spaces_delegated_to_create"] == 0


def test_only_exact_404_delegates_to_original_create():
    FakeApi = api_class(error_status=404)
    install_existing_space_guard(FakeApi)
    api = FakeApi()

    result = api.create_repo(
        "SZLHOLDINGS/new-space",
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
        private=False,
    )

    assert result["created"] is True
    assert len(FakeApi.create_calls) == 1
    assert guard_report(FakeApi)["missing_spaces_delegated_to_create"] == 1


@pytest.mark.parametrize("status", [401, 403, 409, 429, 500, 503])
def test_non_404_provider_failures_never_become_creation(status):
    FakeApi = api_class(error_status=status)
    install_existing_space_guard(FakeApi)
    api = FakeApi()

    with pytest.raises(ProviderError) as caught:
        api.create_repo(
            repo_id="SZLHOLDINGS/terra",
            repo_type="space",
            exist_ok=True,
        )

    assert caught.value.response.status_code == status
    assert FakeApi.create_calls == []


def test_model_dataset_and_strict_space_calls_are_untouched():
    FakeApi = api_class(observed=SimpleNamespace(id="unused", private=False))
    install_existing_space_guard(FakeApi)
    api = FakeApi()

    api.create_repo(
        repo_id="SZLHOLDINGS/model",
        repo_type="model",
        exist_ok=True,
    )
    api.create_repo(
        repo_id="SZLHOLDINGS/strict-space",
        repo_type="space",
        exist_ok=False,
        space_sdk="docker",
    )

    assert len(FakeApi.create_calls) == 2
    assert FakeApi.info_calls == []
    assert guard_report(FakeApi)["non_space_or_strict_calls_delegated"] == 2


def test_identity_mismatch_fails_closed():
    FakeApi = api_class(
        observed=SimpleNamespace(id="OTHER/terra", private=False)
    )
    install_existing_space_guard(FakeApi)

    with pytest.raises(SpaceGuardError, match="identity mismatch"):
        FakeApi().create_repo(
            repo_id="SZLHOLDINGS/terra",
            repo_type="space",
            exist_ok=True,
        )
    assert FakeApi.create_calls == []


def test_existing_private_space_is_not_silently_made_public():
    FakeApi = api_class(
        observed=SimpleNamespace(id="SZLHOLDINGS/terra", private=True)
    )
    install_existing_space_guard(FakeApi)

    with pytest.raises(SpaceGuardError, match="will not change visibility"):
        FakeApi().create_repo(
            repo_id="SZLHOLDINGS/terra",
            repo_type="space",
            exist_ok=True,
            private=False,
        )
    assert FakeApi.create_calls == []


def test_installation_is_idempotent():
    FakeApi = api_class(
        observed=SimpleNamespace(id="SZLHOLDINGS/terra", private=False)
    )
    first = install_existing_space_guard(FakeApi)
    method = FakeApi.create_repo
    second = install_existing_space_guard(FakeApi)

    assert first["installed"] is True
    assert second["installed"] is True
    assert FakeApi.create_repo is method


def test_invalid_repo_id_fails_before_provider_access():
    FakeApi = api_class(observed=None)
    install_existing_space_guard(FakeApi)

    with pytest.raises(SpaceGuardError, match="namespace/name"):
        FakeApi().create_repo(
            repo_id="not-a-namespaced-id",
            repo_type="space",
            exist_ok=True,
        )
    assert FakeApi.info_calls == []
    assert FakeApi.create_calls == []
