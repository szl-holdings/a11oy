# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULES = [
    ("scripts/hf_publish_vertical_flagships_v4_impl.py", "flagship"),
    ("scripts/hf_publish_vertical_services.py", "combined"),
]

def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    fake_hub = ModuleType("huggingface_hub")
    fake_hub.HfApi = type("HfApi", (), {})
    previous = sys.modules.get("huggingface_hub")
    sys.modules["huggingface_hub"] = fake_hub
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("huggingface_hub", None)
        else:
            sys.modules["huggingface_hub"] = previous
    return module

class FakeApi:
    def __init__(self, exists=True, probe_error=None):
        self.exists = exists
        self.probe_error = probe_error
        self.created = []
        self.authorized = []
    def repo_exists(self, *, repo_id, repo_type):
        assert repo_type == "space"
        if self.probe_error:
            raise self.probe_error
        return self.exists
    def create_repo(self, **kwargs):
        self.created.append(kwargs)
    def auth_check(self, **kwargs):
        self.authorized.append(kwargs)

@pytest.mark.parametrize("path,name", MODULES)
def test_existing_space_avoids_creation_quota(path, name):
    module = load_module(path, name + "_existing")
    api = FakeApi(exists=True)
    assert module.ensure_space_repository(api, "SZLHOLDINGS/lyte") == "space_existing"
    assert api.created == []
    assert api.authorized == [{"repo_id": "SZLHOLDINGS/lyte", "repo_type": "space", "write": True}]

@pytest.mark.parametrize("path,name", MODULES)
def test_missing_space_is_created_once(path, name):
    module = load_module(path, name + "_missing")
    api = FakeApi(exists=False)
    assert module.ensure_space_repository(api, "SZLHOLDINGS/new-space") == "space_created"
    assert api.created == [{
        "repo_id": "SZLHOLDINGS/new-space",
        "repo_type": "space",
        "space_sdk": "docker",
        "exist_ok": True,
        "private": False,
    }]
    assert len(api.authorized) == 1

@pytest.mark.parametrize("path,name", MODULES)
def test_probe_failure_never_falls_through_to_creation(path, name):
    module = load_module(path, name + "_failure")
    api = FakeApi(probe_error=RuntimeError("provider unavailable"))
    with pytest.raises(RuntimeError, match="unable to determine"):
        module.ensure_space_repository(api, "SZLHOLDINGS/lyte")
    assert api.created == []
    assert api.authorized == []
