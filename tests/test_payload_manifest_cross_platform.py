# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from scripts.payload_manifest import collect_files, file_fingerprint


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
