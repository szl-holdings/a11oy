# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import json
import sys

import pytest

from scripts.payload_manifest import build_manifest, collect_files, file_fingerprint, main


def test_text_payload_hashes_are_stable_across_lf_and_crlf(tmp_path):
    lf_root = tmp_path / "lf"
    crlf_root = tmp_path / "crlf"
    lf_root.mkdir()
    crlf_root.mkdir()
    (lf_root / "policy.yaml").write_bytes(b"mode: warn\nstatus: prepared\n")
    (crlf_root / "policy.yaml").write_bytes(b"mode: warn\r\nstatus: prepared\r\n")
    lf_output = lf_root / "MANIFEST.json"
    crlf_output = crlf_root / "MANIFEST.json"
    assert collect_files(lf_root, lf_output) == collect_files(crlf_root, crlf_output)


def test_binary_payload_remains_byte_exact(tmp_path):
    left = tmp_path / "left.bin"
    right = tmp_path / "right.bin"
    left.write_bytes(b"\x00\r\n\xff")
    right.write_bytes(b"\x00\n\xff")
    assert file_fingerprint(left) != file_fingerprint(right)


def test_payload_paths_use_platform_independent_posix_order(tmp_path):
    (tmp_path / "README.md").write_text("upper\n", encoding="utf-8")
    (tmp_path / "cluster.yaml").write_text("lower\n", encoding="utf-8")
    output = tmp_path / "MANIFEST.json"
    assert [entry["path"] for entry in collect_files(tmp_path, output)] == [
        "README.md",
        "cluster.yaml",
    ]


@pytest.mark.parametrize("root_kind", ["missing", "file"])
def test_invalid_payload_root_is_rejected_by_library(tmp_path, root_kind):
    root = tmp_path / "payload"
    if root_kind == "file":
        root.write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Payload directory must exist and be a directory"):
        build_manifest(root, tmp_path / "MANIFEST.json")


@pytest.mark.parametrize("root_kind", ["missing", "file"])
@pytest.mark.parametrize("existing_output", [False, True])
@pytest.mark.parametrize("verify", [False, True])
def test_cli_invalid_root_never_creates_or_overwrites_output(
    tmp_path, monkeypatch, capsys, root_kind, existing_output, verify
):
    root = tmp_path / "payload"
    if root_kind == "file":
        root.write_text("not a directory\n", encoding="utf-8")
    output = tmp_path / "MANIFEST.json"
    sentinel = b"existing manifest must survive\n"
    if existing_output:
        output.write_bytes(sentinel)
    argv = ["payload_manifest.py", str(root), "--output", str(output)]
    if verify:
        argv.append("--verify")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "Payload directory must exist and be a directory" in captured.err
    assert "Wrote" not in captured.out
    assert "Verified" not in captured.out
    if existing_output:
        assert output.read_bytes() == sentinel
    else:
        assert not output.exists()


def test_existing_empty_payload_directory_remains_valid(tmp_path):
    result = build_manifest(tmp_path, tmp_path / "MANIFEST.json")
    assert result["fileCount"] == 0
    assert result["files"] == []


@pytest.mark.parametrize("external_output", [False, True])
def test_cli_write_and_verify_accept_output_outside_working_directory(
    tmp_path, monkeypatch, capsys, external_output
):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    root = tmp_path / "payload"
    root.mkdir()
    (root / "README.md").write_bytes(b"payload\n")
    output = (tmp_path if external_output else cwd) / "MANIFEST.json"
    monkeypatch.chdir(cwd)
    argv = ["payload_manifest.py", str(root), "--output", str(output)]
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 0
    written = output.read_bytes()
    assert json.loads(written)["fileCount"] == 1
    expected_display = str(output) if external_output else output.name
    assert capsys.readouterr().out == f"Wrote payload manifest: {expected_display}\n"

    monkeypatch.setattr(sys, "argv", argv + ["--verify"])
    assert main() == 0
    assert output.read_bytes() == written
    assert capsys.readouterr().out == f"Verified payload manifest: {expected_display}\n"

    (root / "README.md").write_bytes(b"changed payload\n")
    assert main() == 1
    assert output.read_bytes() == written
    assert f"Payload manifest is stale: {expected_display}" in capsys.readouterr().out
