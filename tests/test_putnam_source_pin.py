from __future__ import annotations

import pathlib
import re

import scripts.check_putnam_drift as drift
import szl_putnam


ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def test_putnam_source_uses_one_immutable_commit() -> None:
    assert SHA40.fullmatch(szl_putnam._SHA)
    assert szl_putnam._CANONICAL_REF == szl_putnam._SHA
    assert drift.DEFAULT_REF == szl_putnam._SHA
    assert drift.DEFAULT_BRANCH == szl_putnam._SHA
    assert f"/tree/{szl_putnam._SHA}/" in szl_putnam._TREE
    assert f"/blob/{szl_putnam._SHA}/" in szl_putnam._BASE
    assert szl_putnam._BRANCH not in szl_putnam._TREE
    assert szl_putnam._BRANCH not in szl_putnam._BASE


def test_payload_exposes_pin_and_every_artifact_url_uses_it() -> None:
    payload = szl_putnam._payload("a11oy")
    assert payload["canonical_ref"] == szl_putnam._SHA
    assert payload["sha"] == szl_putnam._SHA
    rows = payload["putnam"]["problems"] + payload["szl_originals"]["items"]
    assert len(rows) == 15
    assert all(f"/blob/{szl_putnam._SHA}/" in row["url"] for row in rows)


def test_workflow_and_guard_describe_the_source_as_immutable() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "putnam-drift-guard.yml"
    ).read_text(encoding="utf-8")
    guard = (ROOT / "scripts" / "check_putnam_drift.py").read_text(
        encoding="utf-8"
    )
    assert szl_putnam._SHA in workflow
    assert "immutable canonical Lean labels" in workflow
    assert "immutable canonical lutar-lean commit" in guard
