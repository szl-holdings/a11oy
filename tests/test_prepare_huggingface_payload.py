from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
SCRIPT = SCRIPTS_DIR / "prepare_huggingface_payload.py"
SPEC = importlib.util.spec_from_file_location("prepare_huggingface_payload", SCRIPT)
assert SPEC and SPEC.loader
payload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(payload)


def test_prepared_payload_closes_deploy_manifest(tmp_path, monkeypatch) -> None:
    output = payload.REPO_ROOT / "dist" / "pytest-hf-payload" / tmp_path.name
    monkeypatch.setattr(payload, "OUT_DIR", output)

    try:
        assert payload.main() == 0

        manifest = json.loads(
            (output / "payloads" / "deploy" / "MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["fileCount"] == len(manifest["files"])
        for item in manifest["files"]:
            published = output / "payloads" / "deploy" / item["path"]
            contents = published.read_bytes()
            assert len(contents) == item["size"]
            assert hashlib.sha256(contents).hexdigest() == item["sha256"]

        assert (output / "payloads" / "deploy" / "peat-node.yaml").is_file()
        assert (output / "payloads" / "deploy" / "uds-package.yaml").is_file()
    finally:
        shutil.rmtree(output, ignore_errors=True)

def test_deploy_manifest_copy_canonicalizes_text_and_preserves_binary(
    tmp_path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    deploy = repo / "deploy"
    deploy.mkdir(parents=True)

    canonical_text = b"alpha\nbeta\n"
    source_text = b"alpha\r\nbeta\r\n"
    source_binary = b"\x00\r\n\xff\r"
    (deploy / "config.yaml").write_bytes(source_text)
    (deploy / "weights.bin").write_bytes(source_binary)
    (deploy / "MANIFEST.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "config.yaml",
                        "size": len(canonical_text),
                        "sha256": hashlib.sha256(canonical_text).hexdigest(),
                    },
                    {
                        "path": "weights.bin",
                        "size": len(source_binary),
                        "sha256": hashlib.sha256(source_binary).hexdigest(),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "output"
    monkeypatch.setattr(payload, "REPO_ROOT", repo)
    monkeypatch.setattr(payload, "OUT_DIR", output)
    payload.copy_deploy_manifest_closure()

    assert (
        output / "payloads" / "deploy" / "config.yaml"
    ).read_bytes() == canonical_text
    assert (
        output / "payloads" / "deploy" / "weights.bin"
    ).read_bytes() == source_binary


def test_deploy_manifest_copy_rejects_non_posix_relative_paths(
    tmp_path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    deploy = repo / "deploy"
    deploy.mkdir(parents=True)
    output = tmp_path / "output"
    monkeypatch.setattr(payload, "REPO_ROOT", repo)
    monkeypatch.setattr(payload, "OUT_DIR", output)

    unsafe_paths = (
        r"\Users\me\config.yaml",
        r"C:\Users\me\config.yaml",
        r"\\server\share\config.yaml",
        "/etc/config.yaml",
        "../config.yaml",
    )
    for unsafe in unsafe_paths:
        (deploy / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "path": unsafe,
                            "size": 0,
                            "sha256": hashlib.sha256(b"").hexdigest(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unsafe deploy manifest path"):
            payload.copy_deploy_manifest_closure()

    assert not output.exists()
