# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACES = ("terra-assurance", "puriq-markets", "counsel-assurance")
RETIRED = ("aegis-assurance", "terra-assurance", "puriq-markets", "counsel-assurance")
SUBSTRATE_SHA = "ad2e04374717ef79dbf7dbb91aea5a8480ed10c3"
LOCKED = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
PUBLISHER = ROOT / ".github" / "scripts" / "publish_packet8_vertical_spaces.py"


def test_archived_packet8_adapters_retain_pinned_substrate_and_brain() -> None:
    canonical_app = None
    canonical_brain = None
    for name in SPACES:
        folder = ROOT / "huggingface" / "spaces" / name
        dockerfile = (folder / "Dockerfile").read_text(encoding="utf-8")
        app = (folder / "app.py").read_text(encoding="utf-8")
        brain = (folder / "szl_space_brain.py").read_text(encoding="utf-8")
        assert SUBSTRATE_SHA in dockerfile
        assert "szl_space_brain.py" in dockerfile
        assert "/api/second-brain" in app
        assert "/api/formulas" in app
        assert '"formula_authority":"NONE"' in brain or '"formula_authority": "NONE"' in brain
        assert '"Conjecture 1"' in brain
        for formula_id in LOCKED:
            assert formula_id in brain
        if canonical_app is None:
            canonical_app = app
            canonical_brain = brain
        else:
            assert app == canonical_app
            assert brain == canonical_brain
        py_compile.compile(str(folder / "app.py"), doraise=True)
        py_compile.compile(str(folder / "szl_space_brain.py"), doraise=True)


def test_packet8_second_brain_never_claims_production_or_formula_authority() -> None:
    for name in SPACES:
        folder = ROOT / "huggingface" / "spaces" / name
        brain = (folder / "szl_space_brain.py").read_text(encoding="utf-8")
        app = (folder / "app.py").read_text(encoding="utf-8")
        assert '"product_certified":False' in brain or '"product_certified": False' in brain
        assert '"proven_trust":False' in brain or '"proven_trust": False' in brain
        assert 'formula authority NONE' in app
        assert 'status":"OPEN"' in brain or '"status": "OPEN"' in brain


def test_packet8_sources_are_preserved_but_cannot_be_republished(tmp_path: Path) -> None:
    for name in RETIRED:
        assert (ROOT / "huggingface" / "spaces" / name).is_dir()
    publisher = PUBLISHER.read_text(encoding="utf-8")
    assert "SPACES = []" in publisher
    assert '"state": "WRITER_RETIRED"' in publisher
    assert not (ROOT / ".github" / "workflows" / "hf-packet8-vertical-spaces.yml").exists()
    for forbidden_call in ("create_repo(", "upload_folder(", "update_repo_settings(", "restart_space("):
        assert forbidden_call not in publisher
    for name in RETIRED:
        assert f'"SZLHOLDINGS/{name}"' in publisher
        assert f'"space_id": "SZLHOLDINGS/{name}"' not in publisher.split("SPACES = [", 1)[1]
    assert "Packet 8 writer inventory is no longer retired" in publisher
    py_compile.compile(str(PUBLISHER), doraise=True)

    output = tmp_path / "packet8-archive.json"
    source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    subprocess.run(
        [sys.executable, str(PUBLISHER), "--root", str(ROOT),
         "--source-sha", source_sha, "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["state"] == "WRITER_RETIRED"
    assert receipt["source_sha"] == source_sha
    assert receipt["provider_mutations"] == 0
    assert receipt["provider_deletion_claimed"] is False
    assert {row["space_id"] for row in receipt["archives"]} == {
        f"SZLHOLDINGS/{name}" for name in RETIRED
    }
    assert all(row["files"] for row in receipt["archives"])


def test_archive_receipt_hashes_the_declared_commit_not_working_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.autocrlf", "false"], check=True,
    )
    for name in RETIRED:
        folder = repo / "huggingface" / "spaces" / name
        folder.mkdir(parents=True)
        (folder / "archive.txt").write_bytes(b"committed source\n")
    subprocess.run(["git", "-C", str(repo), "add", "huggingface/spaces"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Fixture",
         "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "archive fixture"],
        check=True,
    )
    source_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty_folder = repo / "huggingface" / "spaces" / RETIRED[0]
    (dirty_folder / "archive.txt").write_bytes(b"uncommitted change\n")
    (dirty_folder / "untracked.txt").write_bytes(b"untracked\n")

    output = tmp_path / "receipt.json"
    subprocess.run(
        [sys.executable, str(PUBLISHER), "--root", str(repo),
         "--source-sha", source_sha, "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    files = receipt["archives"][0]["files"]
    assert files == [{
        "path": "archive.txt",
        "bytes": len(b"committed source\n"),
        "sha256": hashlib.sha256(b"committed source\n").hexdigest(),
    }]

    nonexistent = tmp_path / "nonexistent.json"
    result = subprocess.run(
        [sys.executable, str(PUBLISHER), "--root", str(repo),
         "--source-sha", "a" * 40, "--output", str(nonexistent)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert not nonexistent.exists()
