"""Offline checks that a superseded source cannot continue HF configuration."""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a" * 40
NEW_MAIN = "b" * 40


def load_helper(name: str):
    path = ROOT / "scripts" / f"configure_hf_{name}_runtime.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}_runtime_config", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSeriesApi:
    def __init__(self):
        self.effects = []
        self.volumes = []

    def space_info(self, *, repo_id):
        assert repo_id == "SZLHOLDINGS/a11oy"
        return SimpleNamespace(runtime=SimpleNamespace(volumes=self.volumes))

    def get_space_secrets(self, *, repo_id):
        assert repo_id == "SZLHOLDINGS/a11oy"
        return {"SZL_COSIGN_PRIVATE_PEM": None}

    def get_space_variables(self, *, repo_id):
        assert repo_id == "SZLHOLDINGS/a11oy"
        return {}

    def set_space_volumes(self, *, repo_id, volumes):
        assert repo_id == "SZLHOLDINGS/a11oy" and len(volumes) == 1
        self.effects.append("volume")

    def add_space_variable(self, *, repo_id, key, value, description):
        assert repo_id == "SZLHOLDINGS/a11oy"
        self.effects.append(("variable", key))


class FakeGdwApi:
    def __init__(self):
        self.effects = []

    def space_info(self, *, repo_id):
        assert repo_id == "SZLHOLDINGS/a11oy"
        volume = SimpleNamespace(mount_path="/data", read_only=False)
        return SimpleNamespace(runtime=SimpleNamespace(volumes=[volume]))

    def get_space_secrets(self, *, repo_id):
        assert repo_id == "SZLHOLDINGS/a11oy"
        return {"GDW_CREDENTIALS_JSON": None}

    def get_space_variables(self, *, repo_id):
        assert repo_id == "SZLHOLDINGS/a11oy"
        return {}

    def add_space_variable(self, *, repo_id, key, value, description):
        assert repo_id == "SZLHOLDINGS/a11oy"
        self.effects.append(("variable", key))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*_args, **_kwargs):
        pytest.fail("ownership fixtures must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", denied)


def install_fakes(monkeypatch, helper, api):
    is_series = isinstance(api, FakeSeriesApi)

    def metadata_client(*, token, endpoint=None):
        assert token == "offline-fixture"
        assert endpoint == "https://huggingface.co"
        return api

    class Volume(SimpleNamespace):
        def to_dict(self):
            return {
                "type": self.type, "source": self.source,
                "mountPath": self.mount_path, "readOnly": self.read_only,
                **({"path": self.path} if self.path is not None else {}),
                **({"revision": self.revision} if self.revision is not None else {}),
            }

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(
        HfApi=metadata_client, Volume=Volume))
    monkeypatch.setattr(helper, "manual_prerequisites", lambda *_args, **_kwargs: {
        "state": "READY", "converged": True,
        "credential_authority_state": "VERIFIED",
        "installed_authority": {"github_public_reader": {"state": "VERIFIED"}},
    })
    import httpx

    owner = helper if is_series else helper.load_runtime_mutation_owner()
    if not is_series:
        monkeypatch.setattr(helper, "load_runtime_mutation_owner", lambda: owner)
    state = owner.load_state_store()
    monkeypatch.setattr(owner, "read_storage_status", lambda: {
        "schema": state.STATUS_SCHEMA, "mode": "DISABLED",
        "role": "DISABLED", "writable": True,
    })
    writer = owner.RuntimeMutationClient

    def handle(request):
        payload = json.loads(request.content)
        root = "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/"
        if request.method == "PUT" and str(request.url) == root + "volumes":
            api.set_space_volumes(repo_id=helper.CANONICAL_SPACE, **payload)
        elif request.method == "POST" and str(request.url) == root + "variables":
            api.add_space_variable(repo_id=helper.CANONICAL_SPACE, **payload)
        else:
            pytest.fail("unexpected configuration fixture operation")
        return httpx.Response(200, json={})

    monkeypatch.setattr(owner, "RuntimeMutationClient", lambda token: writer(
        token, transport=httpx.MockTransport(handle)))


def changing_reader(values):
    observed = iter(values)
    return lambda: next(observed)


def test_series_a_stops_between_volume_and_variable_writes(monkeypatch):
    helper, api = load_helper("series_a"), FakeSeriesApi()
    install_fakes(monkeypatch, helper, api)
    # The binding and both pre-write reads admit the volume. The next read
    # observes supersession before any variable can be written.
    with pytest.raises(helper.RuntimeConfigError) as caught:
        helper.configure(repo_id=helper.CANONICAL_SPACE, bucket=helper.CANONICAL_BUCKET,
                         token="offline-fixture", expected_source_sha=SOURCE,
                         main_reader=changing_reader([SOURCE, SOURCE, SOURCE, NEW_MAIN]))
    assert caught.value.diagnostic_code == "SOURCE_NOT_CURRENT_MAIN"
    assert api.effects == ["volume"]


def test_series_a_stops_between_variable_writes_when_volume_exists(monkeypatch):
    helper, api = load_helper("series_a"), FakeSeriesApi()
    api.volumes = [SimpleNamespace(type="bucket", source=helper.CANONICAL_BUCKET,
                                   mount_path="/data", read_only=False,
                                   path=None, revision=None)]
    install_fakes(monkeypatch, helper, api)
    with pytest.raises(helper.RuntimeConfigError) as caught:
        helper.configure(repo_id=helper.CANONICAL_SPACE, bucket=helper.CANONICAL_BUCKET,
                         token="offline-fixture", expected_source_sha=SOURCE,
                         main_reader=changing_reader([SOURCE, SOURCE, SOURCE, NEW_MAIN]))
    assert caught.value.diagnostic_code == "SOURCE_NOT_CURRENT_MAIN"
    assert len(api.effects) == 1 and api.effects[0][0] == "variable"


def test_gdw_stops_between_variable_writes(monkeypatch):
    helper, api = load_helper("gdw"), FakeGdwApi()
    install_fakes(monkeypatch, helper, api)
    with pytest.raises(helper.RuntimeConfigError) as caught:
        helper.configure(repo_id=helper.CANONICAL_SPACE, hf_token="offline-fixture",
                         expected_source_sha=SOURCE,
                         main_reader=changing_reader([SOURCE, SOURCE, SOURCE, NEW_MAIN]))
    assert caught.value.diagnostic_code == "SOURCE_NOT_CURRENT_MAIN"
    assert len(api.effects) == 1


@pytest.mark.parametrize("name", ["series_a", "gdw"])
def test_unbound_default_writer_fails_before_provider_client(monkeypatch, name):
    helper = load_helper(name)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(
        HfApi=lambda **_kwargs: pytest.fail("provider client created")))
    kwargs = ({"bucket": helper.CANONICAL_BUCKET, "token": "offline-fixture"}
              if name == "series_a" else {"hf_token": "offline-fixture"})
    with pytest.raises(helper.RuntimeConfigError) as caught:
        helper.configure(repo_id=helper.CANONICAL_SPACE, **kwargs)
    assert caught.value.diagnostic_code == "SOURCE_OWNERSHIP_UNAVAILABLE"


@pytest.mark.parametrize("name", ["series_a", "gdw"])
def test_reader_failure_after_first_effect_is_fixed_diagnostic(monkeypatch, name):
    helper = load_helper(name)
    api = FakeSeriesApi() if name == "series_a" else FakeGdwApi()
    install_fakes(monkeypatch, helper, api)
    calls = 0

    def reader():
        nonlocal calls
        calls += 1
        if calls == 4:
            raise RuntimeError("private-provider-secret-canary")
        return SOURCE

    kwargs = ({"bucket": helper.CANONICAL_BUCKET, "token": "offline-fixture"}
              if name == "series_a" else {"hf_token": "offline-fixture"})
    with pytest.raises(helper.RuntimeConfigError) as caught:
        helper.configure(repo_id=helper.CANONICAL_SPACE, expected_source_sha=SOURCE,
                         main_reader=reader, **kwargs)
    assert caught.value.diagnostic_code == "SOURCE_OWNERSHIP_UNAVAILABLE"
    assert "private-provider-secret-canary" not in str(caught.value)
    assert len(api.effects) == 1


@pytest.mark.parametrize("name", ["series_a", "gdw"])
def test_cli_passes_expected_source_to_default_helper(monkeypatch, capsys, name):
    helper = load_helper(name)
    captured = {}

    def configure(**kwargs):
        captured.update(kwargs)
        return {"state": "READY", "converged": True}

    monkeypatch.setattr(helper, "configure", configure)
    monkeypatch.setenv("HF_TOKEN", "offline-fixture")
    assert helper.main(["--expected-source-sha", SOURCE]) == 0
    assert captured["expected_source_sha"] == SOURCE
    assert captured["check_only"] is False
    assert "READY" in capsys.readouterr().out
