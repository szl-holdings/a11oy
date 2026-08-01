from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_huggingface_payload.py"
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
