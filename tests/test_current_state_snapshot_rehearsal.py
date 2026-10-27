# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The current v2 snapshot rehearsal stays read-only and does not admit restore."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import a11oy_state_store as ss
from gdw_durable_storage import StorageBlocked

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-rehearse-current-state-snapshots.yml"


def load_rehearsal():
    spec = importlib.util.spec_from_file_location(
        "rehearse_current_state_snapshots",
        ROOT / "scripts" / "rehearse_current_state_snapshots.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rehearsal():
    return load_rehearsal()


def test_matching_heartbeat_verifies_without_admitting_restore(rehearsal, tmp_path, monkeypatch):
    def refuse_repair(*_args, **_kwargs):
        raise AssertionError("repair or publish")

    monkeypatch.setattr(ss.gdw_sqlite_repair, "repair_orphan_pages", refuse_repair)
    monkeypatch.setattr(ss, "cas_advance", refuse_repair)
    pinned, tip, objects = rehearsal.matching_fixture(tmp_path / "fixture")
    report = rehearsal.rehearse_pinned_head(
        head_body=pinned, tip_body=tip, objects=objects,
        scratch=tmp_path / "scratch", head_revision="a" * 40,
    )
    assert report["status"] == "SNAPSHOTS_VERIFIED"
    assert report["latest_snapshots_unchanged"] is True
    assert report["restore_admitted"] is False
    assert report["deployment_admitted"] is False
    assert report["execution_authorized"] is False
    assert report["space_paused"] is False
    assert report["lease_changed"] is False
    assert report["repairs"] == 0
    assert report["provider_writes"] == 0
    assert set(report["stores"]) == {spec.label for spec in ss.STORES}
    assert all(row["ok"] is True for row in report["stores"].values())
    assert not any((tmp_path / "scratch").rglob("*.sqlite3"))
    assert not any((tmp_path / "scratch").rglob("data.mdb"))


def test_advanced_snapshots_do_not_count_as_the_current_backup(rehearsal, tmp_path):
    pinned, tip, objects = rehearsal.matching_fixture(tmp_path / "fixture")
    head = ss.parse_head(pinned)
    moved = json.loads(json.dumps(head))
    spec = ss.STORES[0]
    blob, logical = rehearsal._sqlite_blob(tmp_path / "other.sqlite3", body="moved-snapshot")
    moved["snapshots"][spec.label] = rehearsal._entry(spec, blob, logical, seq=9)
    moved["sequence"] = 3
    moved["previous_manifest_sha256"] = "ab" * 32
    from gdw_durable_storage import canonical
    report = rehearsal.rehearse_pinned_head(
        head_body=pinned, tip_body=canonical(moved), objects=objects,
        scratch=tmp_path / "scratch", head_revision="b" * 40,
    )
    assert report["status"] == "SNAPSHOTS_ADVANCED"
    assert report["restore_admitted"] is False
    assert rehearsal._exit_code(report) == 3


def test_digest_logical_and_foreign_key_failures_stay_blocked(rehearsal, tmp_path):
    pinned, tip, objects = rehearsal.matching_fixture(tmp_path / "fixture")
    head = ss.parse_head(pinned)
    label = ss.STORES[0].label
    path = head["snapshots"][label]["path"]
    flipped = bytearray(objects[path])
    flipped[0] ^= 0x01
    objects[path] = bytes(flipped)
    mismatch = rehearsal.rehearse_pinned_head(
        head_body=pinned, tip_body=tip, objects=objects, scratch=tmp_path / "bad-digest")
    assert mismatch["status"] == "BLOCKED"
    assert mismatch["reason"] == "SNAPSHOT_DIGEST_MISMATCH"
    assert mismatch["restore_admitted"] is False

    pinned, tip, objects = rehearsal.matching_fixture(tmp_path / "logical")
    head = ss.parse_head(pinned)
    head["snapshots"][label]["logical_sha256"] = "ab" * 32
    from gdw_durable_storage import canonical
    logical = rehearsal.rehearse_pinned_head(
        head_body=canonical(head), tip_body=tip, objects=objects, scratch=tmp_path / "bad-logical")
    assert logical["reason"] == "SNAPSHOT_LOGICAL_MISMATCH"

    broken_root = tmp_path / "broken"
    snapshots = {}
    blobs = {}
    for index, spec in enumerate(ss.STORES, start=1):
        if spec.kind == "sqlite":
            blob, digest = rehearsal._sqlite_blob(
                broken_root / spec.label / "source.sqlite3",
                broken_foreign_key=(spec.label == label),
            )
        else:
            blob, digest = rehearsal._lmdb_blob(broken_root / spec.label / "env")
        entry = rehearsal._entry(spec, blob, digest, seq=index)
        snapshots[spec.label] = entry
        blobs[entry["path"]] = blob
    broken_head = rehearsal._head_document(
        snapshots, sequence=1, previous=None, renewed_at="2026-10-25T02:00:00Z")
    blocked = rehearsal.rehearse_pinned_head(
        head_body=broken_head, tip_body=broken_head, objects=blobs,
        scratch=tmp_path / "bad-fk")
    assert blocked["reason"] == "FOREIGN_KEY_CHECK_FAILED"
    assert blocked["repairs"] == 0


def test_incomplete_snapshot_set_is_not_a_pass(rehearsal, tmp_path):
    pinned, _tip, objects = rehearsal.matching_fixture(tmp_path / "fixture")
    head = ss.parse_head(pinned)
    removed = next(iter(head["snapshots"]))
    del head["snapshots"][removed]
    from gdw_durable_storage import canonical
    report = rehearsal.rehearse_pinned_head(
        head_body=canonical(head), tip_body=pinned, objects=objects,
        scratch=tmp_path / "scratch")
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "SNAPSHOT_SET_INCOMPLETE"


def test_public_view_omits_private_head_and_content_hashes(rehearsal, tmp_path):
    pinned, tip, objects = rehearsal.matching_fixture(tmp_path / "fixture")
    report = rehearsal.rehearse_pinned_head(
        head_body=pinned, tip_body=tip, objects=objects,
        scratch=tmp_path / "scratch", head_revision="c" * 40,
    )
    public = rehearsal.public_view(report)
    encoded = json.dumps(public)
    assert public["schema"] == rehearsal.PUBLIC_SCHEMA
    assert "head_revision" not in public
    assert report["head_revision"] not in encoded
    assert report["snapshot_map_sha256"] not in encoded
    assert ss.PREFIX not in encoded
    for row in report["stores"].values():
        assert row["logical_sha256"] not in encoded
        assert row["sha256"] not in encoded
        assert row["sha256"][:16] in encoded


def test_hub_wrapper_refuses_writes_before_the_provider(rehearsal):
    class Inner:
        def __init__(self):
            self.writes = 0

        def create_commit(self):
            self.writes += 1

        def dataset_info(self):
            return "read"

    inner = Inner()
    guard = rehearsal.ReadOnlyHub(inner)
    with pytest.raises(StorageBlocked) as caught:
        guard.create_commit()
    assert caught.value.code == "REHEARSAL_PROVIDER_WRITE_REFUSED"
    assert inner.writes == 0
    assert guard.dataset_info() == "read"
    with pytest.raises(StorageBlocked):
        rehearsal.rehearse_from_provider(inner, Path("unused"))


def test_cli_self_test_prints_only_the_public_view(tmp_path):
    script = ROOT / "scripts" / "rehearse_current_state_snapshots.py"
    env = os.environ.copy()
    env.pop("HF_TOKEN", None)
    completed = subprocess.run(
        [sys.executable, "-B", str(script), "--self-test",
         "--public", str(tmp_path / "public.json"),
         "--evidence", str(tmp_path / "private.json")],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    public = json.loads(completed.stdout)
    assert public["status"] == "SNAPSHOTS_VERIFIED"
    assert public["execution_authorized"] is False
    assert "logical_sha256" not in completed.stdout
    assert ss.PREFIX not in completed.stdout
    private = json.loads((tmp_path / "private.json").read_text(encoding="utf-8"))
    assert private["head_revision"] == "1" * 40
    assert private["head_revision"] not in completed.stdout


def test_cli_without_a_token_does_not_fetch(tmp_path):
    script = ROOT / "scripts" / "rehearse_current_state_snapshots.py"
    env = os.environ.copy()
    env.pop("HF_TOKEN", None)
    completed = subprocess.run(
        [sys.executable, "-B", str(script), "--fetch", "--public", str(tmp_path / "public.json")],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["reason"] == "HF_TOKEN_REQUIRED"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _assert_workflow(source: str) -> None:
    document = yaml.load(source, Loader=yaml.BaseLoader)
    assert set(document["on"]) == {"workflow_dispatch"}
    assert document["permissions"] == {"contents": "read"}
    assert document["concurrency"] == {
        "group": "a11oy-current-snapshot-rehearsal",
        "cancel-in-progress": "false",
    }
    assert "sync-relock-canonical-a11oy" not in source
    assert "pause" not in source.lower()
    assert "create_commit" not in source
    assert "open_deploy_window" not in source
    job = document["jobs"]["rehearse"]
    assert job["if"] == (
        "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
        "&& github.sha == inputs.expected_source_sha && github.run_attempt == 1 }}"
    )
    assert "huggingface_hub==1.33.0" in source
    assert 'python -B scripts/rehearse_current_state_snapshots.py --fetch' in source
    assert "${{ runner.temp }}/public-current-snapshot-rehearsal.json" in source
    assert "${{ runner.temp }}/private-current-snapshot-rehearsal.json" not in source.split(
        "path:", 1
    )[1]
    assert job["steps"][-1]["with"]["path"] == (
        "${{ runner.temp }}/public-current-snapshot-rehearsal.json"
    )


def test_workflow_is_manual_read_only_and_source_fenced():
    _assert_workflow(_workflow_text())


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("on:\n  workflow_dispatch:", "on:\n  push:\n    branches: [main]\n  workflow_dispatch:"),
        ("group: a11oy-current-snapshot-rehearsal", "group: sync-relock-canonical-a11oy"),
        ("contents: read", "contents: write"),
        ("${{ runner.temp }}/public-current-snapshot-rehearsal.json", "${{ runner.temp }}/**"),
    ),
)
def test_workflow_mutations_fail_closed(old, new):
    source = _workflow_text()
    with pytest.raises(AssertionError):
        _assert_workflow(source.replace(old, new, 1))
