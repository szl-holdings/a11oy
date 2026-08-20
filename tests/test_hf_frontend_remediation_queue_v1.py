from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_hf_frontend_remediation_queue_v1.py"
SPEC = importlib.util.spec_from_file_location("hf_frontend_queue_v1", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fixture() -> dict:
    return {
        "schema": "fixture.hf-estate/v1",
        "generated_at": "2026-08-17T00:00:00Z",
        "spaces": [
            {
                "repo_id": "SZLHOLDINGS/good-space",
                "kind": "space",
                "short_description": "Governed canary",
                "sdk": "docker",
                "runtime_stage": "RUNNING",
                "source_revision": "a" * 40,
                "responsive_contract": "v1",
            },
            {
                "repo_id": "SZLHOLDINGS/problem-space",
                "kind": "space",
                "short_description": "x" * 61,
                "runtime_stage": "PAUSED",
            },
            {
                "kind": "space",
                "status": "UNAVAILABLE",
            },
        ],
        "models": [
            {
                "repo_id": "SZLHOLDINGS/model-one",
                "kind": "model",
                "description": "Bounded model card",
                "revision": "b" * 40,
            }
        ],
        "datasets": [
            {
                "repo_id": "SZLHOLDINGS/dataset-one",
                "kind": "dataset",
                "description": "Evidence dataset",
                "license": "apache-2.0",
                "revision": "c" * 40,
                "card_data": {"present": True},
                "mobile_evidence": "viewport-pass",
            }
        ],
    }


def _actions(queue: dict, asset_id: str) -> set[str]:
    for asset in queue["assets"]:
        if asset["asset_id"] == asset_id:
            return {action["code"] for action in asset["actions"]}
    return set()


def test_queue_is_deterministic_and_digest_bound() -> None:
    manifest = _fixture()
    raw = json.dumps(manifest, sort_keys=True).encode()
    first = MODULE.build_queue(manifest, raw)
    second = MODULE.build_queue(manifest, raw)
    assert first == second
    assert first["source_manifest_sha256"] == hashlib.sha256(raw).hexdigest()
    assert first["remote_mutation"] is False
    assert first["status"] == "OPEN"


def test_good_space_does_not_enter_the_queue() -> None:
    manifest = _fixture()
    raw = json.dumps(manifest, sort_keys=True).encode()
    queue = MODULE.build_queue(manifest, raw)
    assert not _actions(queue, "SZLHOLDINGS/good-space")


def test_problem_space_receives_bounded_actions() -> None:
    manifest = _fixture()
    raw = json.dumps(manifest, sort_keys=True).encode()
    queue = MODULE.build_queue(manifest, raw)
    codes = _actions(queue, "SZLHOLDINGS/problem-space")
    assert {
        "SHORT_DESCRIPTION_TOO_LONG",
        "SOURCE_BINDING_REVIEW_REQUIRED",
        "SPACE_SDK_REVIEW_REQUIRED",
        "SPACE_RUNTIME_NOT_RUNNING",
        "RESPONSIVE_EVIDENCE_REQUIRED",
    }.issubset(codes)


def test_unresolved_identity_is_p0_and_never_guessed() -> None:
    manifest = _fixture()
    raw = json.dumps(manifest, sort_keys=True).encode()
    queue = MODULE.build_queue(manifest, raw)
    unresolved = [
        asset for asset in queue["assets"] if asset["asset_id"].startswith("UNRESOLVED::")
    ]
    assert len(unresolved) == 1
    actions = unresolved[0]["actions"]
    identity = next(action for action in actions if action["code"] == "IDENTITY_UNRESOLVED")
    assert identity["priority"] == "P0"
    assert identity["evidence_state"] == "UNAVAILABLE"


def test_model_license_and_card_evidence_remain_explicit() -> None:
    manifest = _fixture()
    raw = json.dumps(manifest, sort_keys=True).encode()
    queue = MODULE.build_queue(manifest, raw)
    codes = _actions(queue, "SZLHOLDINGS/model-one")
    assert "LICENSE_EVIDENCE_REQUIRED" in codes
    assert "CARD_METADATA_REVIEW_REQUIRED" in codes
    assert "RESPONSIVE_EVIDENCE_REQUIRED" in codes


def test_dataset_with_evidence_avoids_license_and_mobile_actions() -> None:
    manifest = _fixture()
    raw = json.dumps(manifest, sort_keys=True).encode()
    queue = MODULE.build_queue(manifest, raw)
    codes = _actions(queue, "SZLHOLDINGS/dataset-one")
    assert "LICENSE_EVIDENCE_REQUIRED" not in codes
    assert "RESPONSIVE_EVIDENCE_REQUIRED" not in codes
    assert "CARD_METADATA_REVIEW_REQUIRED" not in codes


def test_cli_write_and_check_are_exact(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "queue.json"
    manifest.write_text(json.dumps(_fixture()), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--output", str(output)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
            "--check",
        ],
        cwd=ROOT,
        check=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "szl.huggingface-frontend-remediation-queue/v1"


def test_current_repository_manifest_is_parseable() -> None:
    manifest_path = ROOT / "docs" / "huggingface-ecosystem-manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    queue = MODULE.build_queue(manifest, raw)
    assert queue["summary"]["assets_discovered"] > 0
    assert queue["source_manifest_sha256"] == hashlib.sha256(raw).hexdigest()
    assert isinstance(queue["assets"], list)
