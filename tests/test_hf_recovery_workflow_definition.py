# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/hf-free-tier-recovery.yml")
CANONICAL_WORKFLOW = Path(".github/workflows/hf-sync.yml")
TOKEN_VALUE = "${{ github.token }}"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: UniqueKeyLoader, node, deep: bool = False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load(path: Path) -> dict:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    assert isinstance(value, dict)
    return value


def test_workflow_parses_with_unique_mapping_keys() -> None:
    workflow = _load(WORKFLOW)
    assert "jobs" in workflow
    assert set(workflow["jobs"]) == {"contract", "recover"}


def test_recover_job_exposes_each_github_token_alias_exactly_once() -> None:
    workflow = _load(WORKFLOW)
    environment = workflow["jobs"]["recover"]["env"]
    assert environment["GITHUB_TOKEN"] == TOKEN_VALUE
    assert environment["GH_TOKEN"] == TOKEN_VALUE
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("GITHUB_TOKEN: ${{ github.token }}") == 1
    assert text.count("GH_TOKEN: ${{ github.token }}") == 1


def test_write_capable_recovery_serializes_with_canonical_hf_writer() -> None:
    recovery = _load(WORKFLOW)
    canonical = _load(CANONICAL_WORKFLOW)
    recovery_group = recovery["jobs"]["recover"]["concurrency"]["group"]
    canonical_group = canonical["concurrency"]["group"]
    assert recovery_group == canonical_group == "sync-relock-canonical-a11oy"
    assert recovery["jobs"]["recover"]["concurrency"]["cancel-in-progress"] is False
    assert canonical["concurrency"]["cancel-in-progress"] is False
