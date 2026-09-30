# SPDX-License-Identifier: Apache-2.0
"""Deterministic tests for the vertical-services deployment source resolver."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hf_publish_vertical_flagships_v4.py"

spec = importlib.util.spec_from_file_location(
    "hf_publish_vertical_flagships_v4_tip_test",
    SCRIPT,
)
assert spec is not None and spec.loader is not None
publisher = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = publisher
spec.loader.exec_module(publisher)

SOURCE_SHA = "7a84e34a05c7342bd32b56f6519fe51ce240f577"


class FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def install_github_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    contract_conclusion: str = "success",
) -> None:
    def fake_urlopen(request: Any, timeout: int = 0) -> FakeResponse:
        assert timeout == 30
        url = request.full_url
        assert "api.github.com/repos/szl-holdings/vertical-services" in url
        if url.endswith("/git/ref/heads/main"):
            return FakeResponse({"object": {"sha": SOURCE_SHA}})
        if url.endswith(f"/commits/{SOURCE_SHA}/check-runs?per_page=100"):
            return FakeResponse(
                {
                    "check_runs": [
                        {
                            "name": "Python contract suite",
                            "head_sha": SOURCE_SHA,
                            "status": "completed",
                            "conclusion": contract_conclusion,
                        },
                        {
                            "name": "healthz",
                            "head_sha": SOURCE_SHA,
                            "status": "completed",
                            "conclusion": "failure",
                        },
                    ]
                }
            )
        raise AssertionError(f"unexpected GitHub request: {url}")

    monkeypatch.setattr(publisher.urllib.request, "urlopen", fake_urlopen)


def test_resolver_admits_the_green_source_contract_even_when_live_health_is_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_github_fixture(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "workflow-token-not-recorded")

    revision, proof = publisher.resolve_tested_vertical_services_tip()

    assert revision == SOURCE_SHA
    assert proof["revision"] == SOURCE_SHA
    assert proof["python_contract_suite"] == "success"
    assert proof["check_run_count"] == 2
    assert proof["live_health_check_used_as_source_gate"] is False
    assert proof["default_branch_tip_rechecked_by_deployer"] is True
    assert proof["token_value_recorded"] is False
    assert "workflow-token-not-recorded" not in json.dumps(proof)


def test_resolver_fails_closed_without_a_green_python_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_github_fixture(monkeypatch, contract_conclusion="failure")
    with pytest.raises(RuntimeError, match="lacks a successful Python contract suite"):
        publisher.resolve_tested_vertical_services_tip()


def test_run_publisher_overrides_the_loaded_module_before_main(tmp_path: Path) -> None:
    implementation = tmp_path / "synthetic_publisher.py"
    implementation.write_text(
        "SOURCE_REVISION = '0' * 40\n"
        f"EXPECTED = '{SOURCE_SHA}'\n"
        "def main():\n"
        "    return 0 if SOURCE_REVISION == EXPECTED else 1\n",
        encoding="utf-8",
    )

    code, error, admitted = publisher.run_publisher(
        "synthetic_combined",
        implementation,
        source_revision_override=SOURCE_SHA,
    )

    assert code == 0
    assert error is None
    assert admitted is None


def test_source_resolution_uses_only_fixed_repository_and_branch() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'VERTICAL_SERVICES_REPOSITORY = "szl-holdings/vertical-services"' in source
    assert "/git/ref/heads/main" in source
    assert "Python contract suite" in source
    assert "source_revision_override=resolved_revision" in source
    assert "default_branch_tip_rechecked_by_deployer" in source
    assert "caller_supplied" not in publisher.resolve_tested_vertical_services_tip.__doc__.lower()
