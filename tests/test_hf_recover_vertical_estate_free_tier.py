# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

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


def test_script_preserves_single_writer_and_secret_boundaries() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for fragment in (
        "publisher.HF_REPOSITORY = repo_id",
        "publisher.ORIGIN = origin",
        "publisher.RECEIPT_PATH = RUNTIME_RECEIPT_PATH",
        "token_value_recorded\": False",
        "HF_ORG_DYNAMIC_REQUIRES_TEAM_OR_ENTERPRISE",
        "CommitOperationDelete",
        "source_revision",
    ):
        assert fragment in text
    assert "print(token" not in text
    assert "delete_repo" not in text
    assert "force=True" not in text
