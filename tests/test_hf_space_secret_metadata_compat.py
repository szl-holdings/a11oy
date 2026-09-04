# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

ENTRYPOINT = Path("scripts/hf_publish_vertical_flagships_v4.py")


def load_entrypoint() -> Any:
    spec = importlib.util.spec_from_file_location("hf_vertical_entrypoint_test", ENTRYPOINT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalizes_metadata_without_requiring_secret_values() -> None:
    module = load_entrypoint()
    payload = {
        "secrets": [
            {
                "key": "SENTRA_SIGNING_KEY",
                "description": "persistent signer",
                "updatedAt": "2026-09-04T00:00:00Z",
            }
        ]
    }
    normalized = module.normalize_space_secret_metadata(payload)
    assert set(normalized) == {"SENTRA_SIGNING_KEY"}
    assert "value" not in normalized["SENTRA_SIGNING_KEY"]


def test_backport_uses_authenticated_metadata_only_endpoint(monkeypatch: Any) -> None:
    module = load_entrypoint()

    class FakeHfApi:
        def __init__(self, token: str) -> None:
            self.token = token
            self.endpoint = "https://huggingface.example"

    fake_package = types.ModuleType("huggingface_hub")
    fake_package.HfApi = FakeHfApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_package)

    captured: dict[str, Any] = {}

    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        @staticmethod
        def read() -> bytes:
            return json.dumps(
                [{"key": "SENTRA_SIGNING_KEY", "description": "present"}]
            ).encode()

    def fake_urlopen(request: Any, timeout: int) -> Response:
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    module.install_hf_space_secret_metadata_compat()

    api = FakeHfApi(token="test-token")
    result = api.get_space_secrets("SZLHOLDINGS/vertical-services")

    assert result == {
        "SENTRA_SIGNING_KEY": {
            "key": "SENTRA_SIGNING_KEY",
            "description": "present",
        }
    }
    assert captured == {
        "url": (
            "https://huggingface.example/api/spaces/"
            "SZLHOLDINGS/vertical-services/secrets"
        ),
        "authorization": "Bearer test-token",
        "timeout": 30,
    }
