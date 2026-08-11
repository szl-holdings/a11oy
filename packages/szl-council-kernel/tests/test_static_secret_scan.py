from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "static_secret_scan.py"
SPEC = importlib.util.spec_from_file_location("static_secret_scan", SCRIPT)
assert SPEC and SPEC.loader
SCANNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCANNER)


def test_scans_suffixless_and_shell_text_files(tmp_path: Path) -> None:
    secret_assignment = "api_key='" + ("A" * 32) + "'\n"
    (tmp_path / "Dockerfile").write_text(secret_assignment, encoding="utf-8")
    (tmp_path / "deploy.sh").write_text(secret_assignment, encoding="utf-8")

    findings = SCANNER.scan(tmp_path)

    assert {item["path"] for item in findings} == {"Dockerfile", "deploy.sh"}


def test_binary_file_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "artifact.bin").write_bytes(b"\xff\xfe\x00\x01")

    assert SCANNER.scan(tmp_path) == []
