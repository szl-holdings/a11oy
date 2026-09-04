# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ENTRYPOINT = Path("scripts/hf_publish_vertical_flagships_v4.py")


def load_entrypoint():
    spec = importlib.util.spec_from_file_location("szl_hf_vertical_entrypoint", ENTRYPOINT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_space_secret_reader_is_left_untouched(monkeypatch) -> None:
    fake_hub = ModuleType("huggingface_hub")

    class NativeApi:
        def get_space_secrets(self, repo_id: str):
            return {repo_id: object()}

    fake_hub.HfApi = NativeApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.delitem(sys.modules, "huggingface_hub.utils", raising=False)

    module = load_entrypoint()
    original = NativeApi.get_space_secrets
    assert module.ensure_space_secret_reader() == "native"
    assert NativeApi.get_space_secrets is original


def test_pre_v114_client_gets_metadata_only_backport(monkeypatch) -> None:
    calls: dict[str, object] = {}
    fake_hub = ModuleType("huggingface_hub")
    fake_utils = ModuleType("huggingface_hub.utils")

    class Response:
        def json(self) -> dict[str, dict[str, object]]:
            return {
                "SENTRA_SIGNING_KEY": {
                    "description": "persistent signer",
                    "updatedAt": "2026-09-04T00:00:00Z",
                }
            }

    class Session:
        def get(self, url: str, *, headers: dict[str, str]) -> Response:
            calls["url"] = url
            calls["headers"] = headers
            return Response()

    class LegacyApi:
        endpoint = "https://huggingface.example"

        def _build_hf_headers(self, *, token=None) -> dict[str, str]:
            calls["token"] = token
            return {"authorization": "Bearer [masked]"}

    def hf_raise_for_status(response: Response) -> None:
        calls["status_checked"] = response

    fake_hub.HfApi = LegacyApi
    fake_utils.get_session = lambda: Session()
    fake_utils.hf_raise_for_status = hf_raise_for_status
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", fake_utils)

    module = load_entrypoint()
    assert module.ensure_space_secret_reader() == "backported-metadata-only"

    metadata = LegacyApi().get_space_secrets(
        "SZLHOLDINGS/vertical-services",
        token="masked-test-token",
    )
    assert set(metadata) == {"SENTRA_SIGNING_KEY"}
    assert calls["url"] == (
        "https://huggingface.example/api/spaces/"
        "SZLHOLDINGS/vertical-services/secrets"
    )
    assert calls["token"] == "masked-test-token"
    assert calls["status_checked"] is not None


def test_backport_fails_closed_on_malformed_metadata(monkeypatch) -> None:
    fake_hub = ModuleType("huggingface_hub")
    fake_utils = ModuleType("huggingface_hub.utils")

    class Response:
        def json(self) -> list[str]:
            return ["unexpected"]

    class Session:
        def get(self, url: str, *, headers: dict[str, str]) -> Response:
            del url, headers
            return Response()

    class LegacyApi:
        endpoint = "https://huggingface.example"

        def _build_hf_headers(self, *, token=None) -> dict[str, str]:
            del token
            return {}

    fake_hub.HfApi = LegacyApi
    fake_utils.get_session = lambda: Session()
    fake_utils.hf_raise_for_status = lambda response: None
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", fake_utils)

    module = load_entrypoint()
    module.ensure_space_secret_reader()

    try:
        LegacyApi().get_space_secrets("SZLHOLDINGS/vertical-services")
    except RuntimeError as exc:
        assert "non-object" in str(exc)
    else:
        raise AssertionError("malformed secret metadata must fail closed")
