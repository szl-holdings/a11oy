# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path("scripts/hf_recover_vertical_estate_personal_runtime.py")
spec = importlib.util.spec_from_file_location("hf_personal_runtime_target_binding", SCRIPT)
assert spec and spec.loader
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)

SOURCE = "7a84e34a05c7342bd32b56f6519fe51ce240f577"
VERSION = "2.2.0"


def test_deferred_base_load_receives_the_personal_target(
    monkeypatch,
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "personal-runtime-receipt.json"
    observed: dict[str, object] = {}

    base = SimpleNamespace(
        HF_REPOSITORY="SZLHOLDINGS/vertical-services",
        ORIGIN="https://szlholdings-vertical-services.hf.space",
        RECEIPT_PATH=tmp_path / "wrong-receipt.json",
        SOURCE_REVISION="stale",
        EXPECTED_VERSION="stale",
    )

    def base_main() -> int:
        observed.update(
            hf_repository=base.HF_REPOSITORY,
            origin=base.ORIGIN,
            receipt_path=base.RECEIPT_PATH,
            source_revision=base.SOURCE_REVISION,
            expected_version=base.EXPECTED_VERSION,
        )
        receipt = {
            "complete": True,
            "hf_repository": base.HF_REPOSITORY,
            "origin": base.ORIGIN,
            "source_revision": base.SOURCE_REVISION,
        }
        Path(base.RECEIPT_PATH).write_text(json.dumps(receipt), encoding="utf-8")
        return 0

    base.main = base_main

    publisher = SimpleNamespace(
        SOURCE_REVISION="stale",
        EXPECTED_VERSION="stale",
        USER_AGENT="stale",
    )
    publisher.load_base = lambda: base

    def configure(candidate: SimpleNamespace) -> SimpleNamespace:
        candidate.SOURCE_REVISION = publisher.SOURCE_REVISION
        candidate.EXPECTED_VERSION = publisher.EXPECTED_VERSION
        candidate.USER_AGENT = publisher.USER_AGENT
        return candidate

    publisher.configure = configure
    publisher.main = lambda: int(publisher.configure(publisher.load_base()).main())

    wrapper = SimpleNamespace(SOURCE_REVISION="old", EXPECTED_VERSION="old")
    wrapper.load_v3 = lambda: publisher

    def configure_v4(candidate: SimpleNamespace) -> SimpleNamespace:
        candidate.SOURCE_REVISION = wrapper.SOURCE_REVISION
        candidate.EXPECTED_VERSION = wrapper.EXPECTED_VERSION
        return candidate

    wrapper.configure_v4 = configure_v4

    recovery = SimpleNamespace(
        load_module=lambda *_args: wrapper,
        INTELLIGENCE_PUBLISHER=Path("unused-v4.py"),
        RUNTIME_SOURCE_REVISION=SOURCE,
        RUNTIME_VERSION=VERSION,
        RUNTIME_SLUG="szl-vertical-services-runtime",
        RUNTIME_RECEIPT_PATH=receipt_path,
        USER_AGENT="SZL-HF-Free-Tier-Recovery-Test/1.0",
        space_origin=lambda repo_id: "https://" + repo_id.lower().replace("/", "-") + ".hf.space",
    )

    adapter.install_personal_runtime_deployer(recovery)
    result = recovery.deploy_personal_runtime(
        "hf-token-never-recorded",
        "stephenlutar2-hash",
    )

    expected_repo = "stephenlutar2-hash/szl-vertical-services-runtime"
    expected_origin = "https://stephenlutar2-hash-szl-vertical-services-runtime.hf.space"
    assert observed == {
        "hf_repository": expected_repo,
        "origin": expected_origin,
        "receipt_path": receipt_path,
        "source_revision": SOURCE,
        "expected_version": VERSION,
    }
    assert result["repo_id"] == expected_repo
    assert result["origin"] == expected_origin
    assert result["source_revision"] == SOURCE
    assert result["version"] == VERSION
    assert "hf-token-never-recorded" not in json.dumps(result, sort_keys=True)


def test_binding_occurs_before_the_frontier_wrapper_configures_the_base() -> None:
    events: list[str] = []
    recovery = SimpleNamespace(RUNTIME_RECEIPT_PATH=Path("receipt.json"))
    base = SimpleNamespace(
        HF_REPOSITORY="organization/runtime",
        ORIGIN="https://organization-runtime.hf.space",
        RECEIPT_PATH=Path("organization.json"),
    )
    publisher = SimpleNamespace()

    def load_base() -> SimpleNamespace:
        events.append("load-base")
        return base

    publisher.load_base = load_base
    adapter.bind_deferred_personal_base(
        recovery,
        publisher,
        repo_id="person/runtime",
        origin="https://person-runtime.hf.space",
    )
    loaded = publisher.load_base()
    events.append("configure-base")

    assert events == ["load-base", "configure-base"]
    assert loaded.HF_REPOSITORY == "person/runtime"
    assert loaded.ORIGIN == "https://person-runtime.hf.space"
    assert loaded.RECEIPT_PATH == Path("receipt.json")


def test_adapter_never_logs_or_persists_the_hf_token() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "print(token" not in text
    assert '"token": token' not in text
    assert "token_value" not in text
    assert 'os.environ["HF_TOKEN"] = token' in text
    assert "publisher.load_base = load_personal_base" in text
