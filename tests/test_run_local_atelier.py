"""Isolated checks for the manual, loopback-only Atelier launcher."""

import hashlib
import json
import os
import socket
from types import SimpleNamespace

import pytest

from scripts import run_local_atelier as local


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, count):
        assert count == local.MAX_TAGS_BYTES + 1
        return self.payload


class FakeOpener:
    def __init__(self, models):
        self.models = models
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, request.get_method(), timeout))
        return FakeResponse(json.dumps({"models": self.models}).encode())


def _paths(tmp_path):
    return local._storage_paths(tmp_path)


def test_exact_installed_tag_and_digest_without_pull():
    digest = "a" * 64
    opener = FakeOpener([{"name": "qwen3:4b", "model": "qwen3:4b", "digest": "b" * 64},
                         {"name": local.DEFAULT_MODEL, "model": local.DEFAULT_MODEL,
                          "digest": digest}])
    assert local._installed_model_digest(local.DEFAULT_MODEL, digest, opener) == digest
    assert opener.requests == [(local.OLLAMA_TAGS_URL, "GET", 3)]
    with pytest.raises(local.LocalHold, match="LOCAL_MODEL_NOT_INSTALLED"):
        local._installed_model_digest("qwen3:4b-instruct-2507", opener=opener)
    with pytest.raises(local.LocalHold, match="LOCAL_MODEL_DIGEST_MISMATCH"):
        local._installed_model_digest(local.DEFAULT_MODEL, "c" * 64, opener)


def test_vault_is_encrypted_and_reused_without_changing_identity(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setattr(local, "_check_free_space", lambda _base: None)
    monkeypatch.setattr(local.enroll, "_dpapi_protect",
                        lambda plain: bytes(byte ^ 0xA5 for byte in plain))
    monkeypatch.setattr(local.enroll, "_dpapi_unprotect",
                        lambda sealed: bytes(byte ^ 0xA5 for byte in sealed))
    local._prepare_storage(paths)
    first = local._ensure_vault(paths)
    second = local._ensure_vault(paths)
    stored = paths.vault.read_bytes()
    assert first == second
    assert stored.startswith(local.VAULT_MAGIC)
    assert first["token"].encode() not in stored
    assert first["signer_pem"].encode() not in stored
    assert not (paths.data / "signer.pem").exists()


def test_unsafe_link_and_low_disk_fail_before_vault_write(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setattr(local.shutil, "disk_usage",
                        lambda _path: SimpleNamespace(free=local.MIN_FREE_BYTES - 1))
    with pytest.raises(local.LocalHold, match="LOCAL_STORAGE_LOW"):
        local._prepare_storage(paths)
    assert not paths.vault.exists()
    monkeypatch.setattr(local.shutil, "disk_usage",
                        lambda _path: SimpleNamespace(free=local.MIN_FREE_BYTES))
    original = local._is_link
    monkeypatch.setattr(local, "_is_link",
                        lambda path: path == paths.vault or original(path))
    with pytest.raises(local.LocalHold, match="LOCAL_STORAGE_LINK_UNSAFE"):
        local._prepare_storage(paths)
    assert not paths.vault.exists()


def test_runtime_registry_has_only_digest_and_disables_ambient_xai(tmp_path):
    paths = _paths(tmp_path)
    record = local._new_record()
    env = {"XAI_API_KEY": "ambient-sentinel",
           "A11OY_ATELIER_XAI_API_KEY": "ambient-sentinel",
           "SZL_GIT_SHA": "f" * 40}
    local._configure_runtime(record, paths, local.DEFAULT_MODEL, "a" * 64, env)
    registry = json.loads(env["A11OY_ATELIER_CREDENTIALS_JSON"])
    credential = registry["credentials"][0]
    assert registry["version"] == 1
    assert credential["token_sha256"] == hashlib.sha256(record["token"].encode()).hexdigest()
    assert record["token"] not in env["A11OY_ATELIER_CREDENTIALS_JSON"]
    assert env["SZL_COSIGN_PRIVATE_PEM"] == record["signer_pem"]
    assert env["A11OY_REQUIRE_PERSISTENT_SIGNING"] == "1"
    assert env["A11OY_ATELIER_LOCAL_URL"] == "http://127.0.0.1:11434/api/chat"
    assert env["A11OY_ATELIER_LOCAL_MODEL"] == local.DEFAULT_MODEL
    assert env["A11OY_ATELIER_LOCAL_MODEL_DIGEST"] == "a" * 64
    assert env["A11OY_ATELIER_LEDGER_PATH"] == str(paths.ledger)
    assert env["A11OY_COMMAND_CENTRE_PREVIEW"] == "1"
    assert env["XAI_API_KEY"] == env["A11OY_ATELIER_XAI_API_KEY"] == ""
    assert env["SZL_GIT_SHA"] == ""


def test_minimal_app_registers_local_routes_with_generated_identity(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    env = {}
    local._configure_runtime(local._new_record(), paths, local.DEFAULT_MODEL, "a" * 64, env)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    app = local._build_app()
    paths_on_app = {route.path for route in app.router.routes}
    assert "/a11oy/atelier" in paths_on_app
    assert "/api/a11oy/v1/atelier/local/health" in paths_on_app
    assert "/api/a11oy/v1/atelier/local/turn" in paths_on_app


def test_conflicting_listener_is_denied(monkeypatch):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind((local.HOST, 0))
        occupied.listen(1)
        monkeypatch.setattr(local, "PORT", occupied.getsockname()[1])
        with pytest.raises(local.LocalHold, match="LOCAL_PORT_IN_USE"):
            local._reserve_listener()


@pytest.mark.skipif(os.name != "nt", reason="Windows clipboard action")
def test_copy_is_explicit_and_never_prints_token(tmp_path, monkeypatch, capsys):
    record = local._new_record()
    copied = []
    paths = _paths(tmp_path)
    monkeypatch.setattr(local, "_storage_paths", lambda: paths)
    monkeypatch.setattr(local, "_prepare_storage", lambda _paths: None)
    monkeypatch.setattr(local, "_ensure_vault", lambda _paths: record)
    monkeypatch.setattr(local.enroll, "_copy_to_clipboard", copied.append)
    assert local.main(["--copy-operator-token"]) == 0
    assert copied == [record["token"]]
    assert record["token"] not in capsys.readouterr().out
    assert local.main(["--copy-operator-token", "--expected-model-digest", "a" * 64]) == 2
