from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_release.py"
SBOM = ROOT / "tools" / "build_sbom.py"


def _run_builder(source: Path, output: Path, report: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(BUILDER), str(source), "--output", str(output)]
    if report is not None:
        command.extend(["--report", str(report)])
    return subprocess.run(command, capture_output=True, text=True)


def test_release_builder_is_repeatable_and_excludes_generated_private_state(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "safe.txt").write_text("frontier\n", encoding="utf-8")
    executable = source / "tool.py"
    executable.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    executable.chmod(0o700)
    for relative in (
        "build/generated.txt",
        "dist/package.whl",
        "dist-repeat/package.whl",
        "src/demo.egg-info/PKG-INFO",
        ".eggs/cache.txt",
        "runtime/state.txt",
        "run/output.txt",
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("excluded\n", encoding="utf-8")
    for relative in ("state.db", "state.sqlite3", "signer.key", "signer.pem"):
        (source / relative).write_text("excluded\n", encoding="utf-8")

    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    report = tmp_path / "report.json"
    result_a = _run_builder(source, first, report)
    result_b = _run_builder(source, second)
    assert result_a.returncode == 0, result_a.stdout + result_a.stderr
    assert result_b.returncode == 0, result_b.stdout + result_b.stderr
    assert first.read_bytes() == second.read_bytes()

    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == {"MANIFEST.sha256", "safe.txt", "tool.py"}
        assert archive.read("safe.txt") == b"frontier\n"
        # Executable input is normalized to 0755; regular input to 0644.
        modes = {name: archive.getinfo(name).external_attr >> 16 for name in archive.namelist()}
        assert modes["tool.py"] & 0o777 == 0o755
        assert modes["safe.txt"] & 0o777 == 0o644
        manifest = archive.read("MANIFEST.sha256").decode("utf-8")
        assert "safe.txt" in manifest and "tool.py" in manifest
        assert "egg-info" not in manifest and "state.db" not in manifest

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"
    assert data["egg_info_excluded"] is True
    assert data["inventory_readback"] is True
    assert data["payload_digest_readback"] is True


def test_release_builder_rejects_symbolic_links(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    target = source / "target.txt"
    target.write_text("content\n", encoding="utf-8")
    link = source / "link.txt"
    try:
        os.symlink(target.name, link)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable on this platform")
    output = tmp_path / "release.zip"
    result = _run_builder(source, output)
    assert result.returncode != 0
    assert "symbolic links are forbidden" in result.stderr
    assert not output.exists()


def test_sbom_build_is_deterministic(tmp_path: Path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    base = [
        sys.executable,
        str(SBOM),
        "--source-revision",
        "1" * 40,
        "--source-tree",
        "2" * 40,
    ]
    a = subprocess.run([*base, "--output", str(first)], capture_output=True, text=True)
    b = subprocess.run([*base, "--output", str(second)], capture_output=True, text=True)
    assert a.returncode == b.returncode == 0
    assert first.read_bytes() == second.read_bytes()
    document = json.loads(first.read_text(encoding="utf-8"))
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.6"
    properties = {
        item["name"]: item["value"]
        for item in document["metadata"]["component"]["properties"]
    }
    assert properties["szl.source.revision"] == "1" * 40
    assert properties["szl.vulnerability.audit"].startswith("NOT_PERFORMED")


def test_packaging_includes_apache_notice():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert 'license-files = ["LICENSE", "NOTICE"]' in pyproject
    assert "include NOTICE" in manifest
