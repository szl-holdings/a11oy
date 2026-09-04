# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path("scripts/hf_recover_vertical_estate_free_tier.py")
spec = importlib.util.spec_from_file_location("hf_free_tier_recovery", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_runtime_source_and_topology_are_exact() -> None:
    assert module.RUNTIME_SOURCE_REVISION == "7a84e34a05c7342bd32b56f6519fe51ce240f577"
    assert module.RUNTIME_VERSION == "2.2.0"
    assert set(module.STATIC_SPACES) == {"vertical-services", "terra", "counsel", "finance", "lyte"}
    assert module.STATIC_SPACES["finance"][2] == "/experience/puriq"
    assert module.STATIC_SPACES["counsel"][2] == "/experience/prism"
    assert module.REQUIRED_GATEWAY_PATHS == (
        "/",
        "/healthz",
        "/api/build-info",
        "/api/source",
    )


def test_personal_owner_is_validated_and_org_owner_is_rejected() -> None:
    assert module.owner_from_identity({"name": "stephen-lutar"}) == "stephen-lutar"
    for value in ({}, {"name": ""}, {"name": "SZLHOLDINGS"}, {"name": "bad/name"}):
        try:
            module.owner_from_identity(value)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"invalid owner accepted: {value}")


def test_space_origin_is_deterministic() -> None:
    assert module.space_origin("Example_User/Runtime.One") == "https://example-user-runtime-one.hf.space"


def test_static_card_selects_free_static_sdk() -> None:
    card = module.static_card("Terra", "Parcel intelligence")
    assert "sdk: static" in card
    assert "app_file: index.html" in card
    assert "license: apache-2.0" in card
    assert "docker" not in card.lower()


def test_static_page_has_mobile_accessibility_and_honest_runtime_binding() -> None:
    build = {
        "runtime_source_revision": module.RUNTIME_SOURCE_REVISION,
        "effectors_enabled": False,
        "human_approval_required": True,
    }
    page = module.static_page(
        "Terra",
        "Parcel intelligence",
        "https://owner-runtime.hf.space/experience/terra",
        build,
    )
    for fragment in (
        'data-szl-domain-experience-v4="true"',
        'name="viewport"',
        "viewport-fit=cover",
        "min-height:48px",
        "prefers-reduced-motion:reduce",
        "forced-colors:active",
        "Human authority required",
        module.RUNTIME_SOURCE_REVISION[:12],
        "location.replace",
    ):
        assert fragment in page
    assert json.dumps(build, sort_keys=True, separators=(",", ":")) in page


def test_personal_runtime_rebinds_wrapper_before_configuration(
    monkeypatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, str] = {}
    publisher = SimpleNamespace()
    wrapper = SimpleNamespace(
        SOURCE_REVISION="c24ef61716f173e48d95dad61408d9fa065f0204",
        EXPECTED_VERSION="2.1.0",
    )

    def load_v3() -> object:
        return object()

    def configure_v4(_base: object) -> SimpleNamespace:
        observed["source_revision"] = wrapper.SOURCE_REVISION
        observed["runtime_version"] = wrapper.EXPECTED_VERSION
        publisher.SOURCE_REVISION = wrapper.SOURCE_REVISION
        publisher.EXPECTED_VERSION = wrapper.EXPECTED_VERSION
        return publisher

    def publish() -> int:
        receipt = {
            "complete": True,
            "source_revision": observed["source_revision"],
        }
        Path(publisher.RECEIPT_PATH).write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )
        return 0

    wrapper.load_v3 = load_v3
    wrapper.configure_v4 = configure_v4
    publisher.main = publish
    receipt_path = tmp_path / "runtime-receipt.json"
    monkeypatch.setattr(module, "RUNTIME_RECEIPT_PATH", receipt_path)
    monkeypatch.setattr(module, "load_module", lambda *_args: wrapper)

    result = module.deploy_personal_runtime("token-not-read", "stephen-lutar")

    assert observed == {
        "source_revision": module.RUNTIME_SOURCE_REVISION,
        "runtime_version": module.RUNTIME_VERSION,
    }
    assert result["source_revision"] == module.RUNTIME_SOURCE_REVISION
    assert result["version"] == module.RUNTIME_VERSION
    assert result["repo_id"] == "stephen-lutar/szl-vertical-services-runtime"


def gateway_json(source_revision: str, runtime_repository: str) -> bytes:
    return module.canonical_json_bytes(
        {
            "source_repository": module.GATEWAY_SOURCE_REPOSITORY,
            "source_revision": source_revision,
            "runtime_repository": runtime_repository,
            "runtime_source_revision": module.RUNTIME_SOURCE_REVISION,
            "effectors_enabled": False,
            "human_approval_required": True,
        }
    )


def test_gateway_live_verification_requires_route_parity_and_source_binding(
    monkeypatch,
) -> None:
    gateway_revision = "c" * 40
    runtime_repository = "stephen-lutar/szl-vertical-services-runtime"
    responses = {
        "/": (200, b'<html data-szl-domain-experience-v4="true"></html>'),
        "/healthz": (200, gateway_json(gateway_revision, runtime_repository)),
        "/api/build-info": (200, gateway_json(gateway_revision, runtime_repository)),
        "/api/source": (200, gateway_json(gateway_revision, runtime_repository)),
    }

    def anonymous_get(url: str, attempts: int = 30) -> tuple[int, bytes]:
        del attempts
        path = "/" + url.split("/", 3)[-1] if url.count("/") >= 3 else "/"
        return responses[path]

    monkeypatch.setattr(module, "anonymous_get", anonymous_get)
    result = module.verify_gateway(
        "https://szlholdings-terra.hf.space",
        {
            "source_revision": gateway_revision,
            "runtime_repository": runtime_repository,
        },
    )
    assert result["complete"] is True
    assert result["failures"] == []
    assert set(result["observations"]) == set(module.REQUIRED_GATEWAY_PATHS)

    responses["/api/source"] = (404, b"")
    failed = module.verify_gateway(
        "https://szlholdings-terra.hf.space",
        {
            "source_revision": gateway_revision,
            "runtime_repository": runtime_repository,
        },
    )
    assert failed["complete"] is False
    assert "/api/source: HTTP 404" in failed["failures"]


def test_gateway_live_verification_rejects_wrong_source_and_authority(
    monkeypatch,
) -> None:
    gateway_revision = "d" * 40
    runtime_repository = "stephen-lutar/szl-vertical-services-runtime"
    bad = {
        "source_repository": "other/repository",
        "source_revision": "e" * 40,
        "runtime_repository": "other/runtime",
        "runtime_source_revision": "f" * 40,
        "effectors_enabled": True,
        "human_approval_required": False,
    }

    def anonymous_get(url: str, attempts: int = 30) -> tuple[int, bytes]:
        del attempts
        if url.endswith("/"):
            return 200, b'<html data-szl-domain-experience-v4="true"></html>'
        return 200, module.canonical_json_bytes(bad)

    monkeypatch.setattr(module, "anonymous_get", anonymous_get)
    result = module.verify_gateway(
        "https://szlholdings-terra.hf.space",
        {
            "source_revision": gateway_revision,
            "runtime_repository": runtime_repository,
        },
    )
    assert result["complete"] is False
    assert len(result["failures"]) >= 6
    assert any("gateway source repository mismatch" in row for row in result["failures"])
    assert any("effector boundary drift" in row for row in result["failures"])


def test_script_preserves_single_writer_and_secret_boundaries() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for fragment in (
        "wrapper.SOURCE_REVISION = RUNTIME_SOURCE_REVISION",
        "wrapper.EXPECTED_VERSION = RUNTIME_VERSION",
        "publisher.HF_REPOSITORY = repo_id",
        "publisher.ORIGIN = origin",
        "publisher.RECEIPT_PATH = RUNTIME_RECEIPT_PATH",
        '"healthz": canonical_json_bytes(health)',
        '"api/build-info": canonical_json_bytes(build)',
        '"api/source": canonical_json_bytes(source)',
        "token_value_recorded\": False",
        "HF_ORG_DYNAMIC_REQUIRES_TEAM_OR_ENTERPRISE",
        "CommitOperationDelete",
        "source_revision",
    ):
        assert fragment in text
    assert "print(token" not in text
    assert "delete_repo" not in text
    assert "force=True" not in text


def test_workflow_exposes_exact_tip_token_contract_without_secret_expansion() -> None:
    workflow = Path(".github/workflows/hf-free-tier-recovery.yml").read_text(encoding="utf-8")
    recover = workflow.split("\n  recover:\n", 1)[1]
    assert "GH_TOKEN: ${{ github.token }}" in recover
    assert "GITHUB_TOKEN: ${{ github.token }}" in recover
    assert "GITHUB_TOKEN: ${{ secrets." not in recover
