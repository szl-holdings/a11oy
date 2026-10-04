#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline synthetic image controls; no fixture is an operational admission."""

import copy
import hashlib
import os
from pathlib import Path
import time

import pytest

import gdw_durable_source as source


def manifest(*, contents=None, absent=None):
    files = {name: ("# offline source fixture " + name + "\n").encode()
             for name in source.REQUIRED_FILES}
    files.update(contents or {})
    entries = [{"path": name, "source_path": name, "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())]
    by_path = {item["path"]: item for item in entries}
    absences = sorted(absent if absent is not None else ["brain/__init__.py", "szl_chaski.py", "szl_wasi_rikuq.py"])
    py_count = sum(item["path"].endswith(".py") for item in entries)
    docker = by_path["Dockerfile"]
    requirements = by_path["requirements-runtime.txt"]
    return {"schema": source.SCHEMA, "repository": source.REPOSITORY, "source_revision": "b" * 40,
            "runtime_root": source.RUNTIME_ROOT, "publisher": dict(source.PUBLISHER),
            "dockerfile": {key: docker[key] for key in ("source_path", "size", "sha256")} |
                          {"runtime_stage": "runtime", "workdir": "/app", "copy_instruction_count": len(entries) + 1},
            "copy_payload": {"scope": "PINNED_PUBLISHER_COPY_EXPANSION", "source_count": len(entries) + 1,
                             "file_count": len(entries) + 1, "total_bytes": sum(len(v) for v in files.values()) + 10,
                             "sha256": hashlib.sha256(source.canonical(entries)).hexdigest()},
            "installed_files": entries,
            "python_inventory": {"scope": "ALL_SOURCE_PYTHON_PATHS", "source_count": py_count + len(absences),
                                 "installed_count": py_count, "absent_count": len(absences)},
            "absent_modules": absences,
            "build_inputs": [
                {"stage": "llama-build-1", "destination": "/tmp/fetch_owned_khipu_wheel.py",
                 "scope": "BUILD_STAGE_ONLY", "source_path": "scripts/fetch_owned_khipu_wheel.py",
                 "size": 10, "sha256": "a" * 64},
                {"stage": "runtime", "destination": "/tmp/requirements-runtime.txt",
                 "scope": "RUNTIME_INSTALL_INPUT", "source_path": "requirements-runtime.txt",
                 "size": requirements["size"], "sha256": requirements["sha256"]},
            ], "overwrites": []}


def install_image(directory, *, contents=None, absent=None):
    app, inputs = directory / "app", directory / "tmp"
    app.mkdir(parents=True)
    inputs.mkdir()
    files = {name: ("# offline source fixture " + name + "\n").encode()
             for name in source.REQUIRED_FILES}
    files.update(contents or {})
    for name, data in files.items():
        target = app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (inputs / "requirements-runtime.txt").write_bytes(files["requirements-runtime.txt"])
    return manifest(contents=files, absent=absent), app, inputs


def verify(value, app, inputs, **kwargs):
    return source.verify_installed_source(value, app, "b" * 40, runtime_install_root=inputs, **kwargs)


def test_exact_source_inventory_and_absences_have_no_payload_or_environment_claim(tmp_path):
    value, app, inputs = install_image(tmp_path, contents={"empty/__init__.py": b""})
    before = copy.deepcopy(value)
    result = verify(value, app, inputs)
    assert result == {"state": "ADMITTED_SOURCE_CONTENT_EQUALITY", "source_revision": "b" * 40,
                      "manifest_sha256": hashlib.sha256(source.canonical(value)).hexdigest(),
                      "installed_file_count": len(value["installed_files"]),
                      "required_absence_count": len(value["absent_modules"]),
                      "dependency_environment_attestation": "NOT_PERFORMED"}
    assert value == before


def test_parser_detaches_without_filesystem_io(monkeypatch):
    value = manifest()
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("schema validation performed I/O"))
    parsed = source.validate_manifest(value, "b" * 40)
    value["installed_files"][0]["sha256"] = "c" * 64
    assert parsed["installed_files"][0]["sha256"] != "c" * 64


@pytest.mark.parametrize("path,new", [
    (("schema",), "other"), (("repository",), "unrelated/repo"), (("source_revision",), "0" * 40),
    (("runtime_root",), "/tmp/private"), (("publisher", "revision"), "c" * 40),
    (("publisher", "script_sha256"), "0" * 64), (("dockerfile", "source_path"), "OtherDockerfile"),
    (("dockerfile", "runtime_stage"), "builder"), (("dockerfile", "workdir"), "/"),
    (("dockerfile", "copy_instruction_count"), True), (("dockerfile", "copy_instruction_count"), 257),
    (("dockerfile", "sha256"), "c" * 64), (("copy_payload", "scope"), "BEST_EFFORT"),
    (("copy_payload", "file_count"), 2049), (("copy_payload", "source_count"), 1025),
    (("copy_payload", "total_bytes"), 128 * 1024 * 1024 + 1),
    (("python_inventory", "source_count"), 4097), (("python_inventory", "installed_count"), 1),
    (("python_inventory", "absent_count"), True), (("python_inventory", "scope"), "SELECTED_IMPORTS"),
    (("build_inputs", 0, "destination"), "/app/unreviewed.py"),
    (("build_inputs", 1, "scope"), "BUILD_STAGE_ONLY"),
    (("build_inputs", 1, "sha256"), "c" * 64),
])
def test_unknown_or_unbounded_manifest_fact_rejected(path, new):
    value = manifest()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = new
    with pytest.raises(source.SourceBlocked):
        source.validate_manifest(value, "b" * 40)


@pytest.mark.parametrize("name", ["../escape.py", "/root/escape.py", "a//b.py", "a/./b.py", "a/../b.py",
                                  "a\\b.py", "a\n.py", "a\x7f.py", "é.py", "\ud800.py", "a" * 513])
def test_path_normalization_or_escape_is_rejected(name):
    value = manifest()
    value["absent_modules"][0] = name
    with pytest.raises(source.SourceBlocked):
        source.validate_manifest(value, "b" * 40)


@pytest.mark.parametrize("defect", ["unknown", "missing_serve", "missing_source", "duplicate", "unsorted",
                                    "absent_duplicate", "absent_present", "absent_nonmodule", "relocated_python",
                                    "bytecode", "oversized", "file_bytes", "source_fields", "absent_fields"])
def test_incomplete_or_loose_manifest_rejected(defect):
    value = manifest()
    if defect == "unknown": value["best_effort"] = True
    if defect in {"missing_serve", "missing_source"}:
        name = "serve.py" if defect == "missing_serve" else "gdw_durable_source.py"
        value["installed_files"] = [item for item in value["installed_files"] if item["path"] != name]
    if defect == "duplicate": value["installed_files"].append(dict(value["installed_files"][0]))
    if defect == "unsorted": value["installed_files"].reverse()
    if defect == "absent_duplicate": value["absent_modules"].append(value["absent_modules"][0])
    if defect == "absent_present": value["absent_modules"][0] = "serve.py"
    if defect == "absent_nonmodule": value["absent_modules"][0] = "source.txt"
    if defect == "relocated_python":
        next(item for item in value["installed_files"] if item["path"] == "serve.py")["source_path"] = "elsewhere.py"
    if defect == "bytecode":
        value["installed_files"].append({"path": "stale.pyc", "source_path": "stale.pyc", "size": 1, "sha256": "c" * 64})
    if defect == "oversized": value["extra"] = "x" * source.MAX_MANIFEST_BYTES
    if defect == "file_bytes": value["installed_files"][0]["size"] = source.MAX_FILE_BYTES + 1
    if defect == "source_fields": value["installed_files"][0]["mode"] = "optional"
    if defect == "absent_fields": del value["python_inventory"]["scope"]
    with pytest.raises(source.SourceBlocked):
        source.validate_manifest(value, "b" * 40)


def test_deterministic_overwrite_binds_final_source_identity():
    value = manifest()
    last = next(item for item in value["installed_files"] if item["path"] == "serve.py")
    value["overwrites"] = [{"path": "serve.py", "before": {"copy_index": 1, "source_path": "old/serve.py",
        "size": 1, "sha256": "a" * 64}, "after": {key: last[key] for key in ("source_path", "size", "sha256")} | {"copy_index": 2}}]
    source.validate_manifest(value, "b" * 40)
    value["overwrites"][0]["after"]["sha256"] = "c" * 64
    with pytest.raises(source.SourceBlocked): source.validate_manifest(value, "b" * 40)


@pytest.mark.parametrize("relative", ["szl_chaski.py", "brain/__init__.py", "never_seen.py", "stale.pyc",
                                       "__pycache__/serve.cpython-314.pyc", "optional.so", "addon.node", "addon.wasm", "backend.ts", "extra.mjs",
                                       "node_modules/pkg/index.js", "plugin.pth", "payload.whl",
                                       "packages/package.json", "package-lock.json", ".npmrc",
                                       "nested/tsconfig.node.json", "nested/.pnp.data.json"])
def test_optional_absence_and_unlisted_executable_rejected(tmp_path, relative):
    value, app, inputs = install_image(tmp_path)
    file = app / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"PRIVATE_FIXTURE_MUST_NOT_ESCAPE")
    with pytest.raises(source.SourceBlocked) as blocked:
        verify(value, app, inputs)
    assert "PRIVATE_FIXTURE" not in str(blocked.value)


def test_unknown_executable_bit_rejected_but_generated_non_source_model_data_is_scoped(tmp_path):
    value, app, inputs = install_image(tmp_path)
    file = app / "model.gguf"
    file.write_bytes(b"synthetic model data, not an executable source attestation")
    verify(value, app, inputs)
    file.chmod(0o700)
    with pytest.raises(source.SourceBlocked, match="UNLISTED_EXECUTABLE"):
        verify(value, app, inputs)


@pytest.mark.parametrize("defect", ["file_symlink", "directory_symlink", "root_symlink", "fifo", "hardlink",
                                    "changed", "missing", "input_changed", "input_symlink", "unknown_symlink"])
def test_unsafe_or_changed_image_rejected_without_blocking(tmp_path, defect):
    value, app, inputs = install_image(tmp_path)
    file = app / "serve.py"
    if defect == "file_symlink":
        outside = tmp_path / "outside"; file.rename(outside); file.symlink_to(outside)
    if defect == "directory_symlink":
        original = app / "routers"; outside = tmp_path / "routers"; original.rename(outside); original.symlink_to(outside)
    if defect == "root_symlink":
        other = tmp_path / "alias"; other.symlink_to(app); app = other
    if defect == "fifo": file.unlink(); os.mkfifo(file)
    if defect == "hardlink": os.link(file, tmp_path / "extra_link")
    if defect == "changed": file.write_bytes(b"changed source")
    if defect == "missing": file.unlink()
    if defect == "input_changed": (inputs / "requirements-runtime.txt").write_bytes(b"unreviewed dependencies")
    if defect == "input_symlink":
        (inputs / "requirements-runtime.txt").unlink(); (inputs / "requirements-runtime.txt").symlink_to(app / "requirements-runtime.txt")
    if defect == "unknown_symlink": (app / "unseen").symlink_to(tmp_path)
    started = time.monotonic()
    with pytest.raises(source.SourceBlocked): verify(value, app, inputs)
    assert time.monotonic() - started < 1


def test_file_changed_after_its_hash_is_rejected_by_final_identity(tmp_path, monkeypatch):
    value, app, inputs = install_image(tmp_path)
    original = source._scan_source_tree
    def scan(*args):
        result = original(*args)
        file = app / "serve.py"
        metadata = file.stat()
        file.write_bytes(b"X" * metadata.st_size)
        os.utime(file, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        return result
    monkeypatch.setattr(source, "_scan_source_tree", scan)
    with pytest.raises(source.SourceBlocked, match="FILE_CHANGED"):
        verify(value, app, inputs)


def test_missing_optional_parent_cannot_be_a_symlink(tmp_path):
    value, app, inputs = install_image(tmp_path)
    (app / "brain").symlink_to(inputs)
    with pytest.raises(source.SourceBlocked): verify(value, app, inputs)


def test_read_access_time_change_does_not_reject_unchanged_source(tmp_path):
    value, app, inputs = install_image(tmp_path)
    file = app / "serve.py"
    before = file.stat()
    os.utime(file, ns=(1, before.st_mtime_ns))
    verify(value, app, inputs)
    assert file.stat().st_atime_ns > 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, True])
def test_invalid_or_expired_deadline_rejected_before_file_io(tmp_path, monkeypatch, value):
    record = manifest()
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("invalid deadline reached file I/O"))
    with pytest.raises(source.SourceBlocked): verify(record, tmp_path, tmp_path, deadline=value)


def test_expired_during_hash_never_reports_equality(tmp_path, monkeypatch):
    value, app, inputs = install_image(tmp_path)
    original = source._read_identity
    clock = [time.monotonic()]
    monkeypatch.setattr(source.time, "monotonic", lambda: clock[0])
    def read(*args):
        result = original(*args)
        clock[0] += 31
        return result
    monkeypatch.setattr(source, "_read_identity", read)
    with pytest.raises(source.SourceBlocked, match="DEADLINE"):
        verify(value, app, inputs)


def test_source_scan_has_independent_entry_bound(tmp_path, monkeypatch):
    value, app, inputs = install_image(tmp_path)
    monkeypatch.setattr(source, "MAX_SCAN_ENTRIES", 1)
    with pytest.raises(source.SourceBlocked, match="SCAN_BOUND"):
        verify(value, app, inputs)


def test_equal_bytes_from_different_source_preserve_ordered_overwrite_evidence():
    value = manifest()
    item = next(entry for entry in value["installed_files"] if entry["path"] == "serve.py")
    before = {key: item[key] for key in ("source_path", "size", "sha256")}
    before.update(copy_index=1, source_path="earlier/serve.py")
    after = {key: item[key] for key in ("source_path", "size", "sha256")}
    after["copy_index"] = 2
    value["overwrites"] = [{"path": "serve.py", "before": before, "after": after}]
    source.validate_manifest(value, "b" * 40)
    before["source_path"] = after["source_path"]
    with pytest.raises(source.SourceBlocked): source.validate_manifest(value, "b" * 40)
