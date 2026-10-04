#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline derivation and native descriptor/Git boundary controls.

Unit fixtures supply fixed expansion results without changing production pins.
The real external publisher is exercised separately by the source-owner command;
it is not vendored here and no application module or provider is imported.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest

from scripts import build_gdw_installed_source_manifest as builder


REVISION = "a" * 40
ROOT = Path(__file__).resolve().parents[1]
DOCKER = ("FROM python:3.14 AS runtime\nWORKDIR /app\n"
          "COPY Dockerfile requirements-runtime.txt gdw_runtime.py serve.py ./\n"
          "COPY assets/ ./static/\nCMD [\"python\",\"-B\",\"gdw_runtime.py\"]\n")
SOURCES = ["Dockerfile", "requirements-runtime.txt", "gdw_runtime.py", "serve.py", "assets/"]


class FixedExpansion:
    """A fixture dependency, not another Docker parser or publisher."""
    class error(Exception):
        pass

    def __init__(self, sources):
        self.sources = list(sources)

    def parse(self, text):
        assert isinstance(text, str)
        return list(self.sources)

    @staticmethod
    def expand(sources, tree):
        matched, missing = {}, []
        for source in sources:
            normalized = source.rstrip("/")
            paths = [normalized] if normalized in tree else [p for p in tree if p.startswith(normalized + "/")]
            if not paths:
                missing.append(source)
            for path in paths:
                matched[path] = normalized
        return matched, missing


def source_files(docker=DOCKER):
    return {"Dockerfile": docker.encode(), "requirements-runtime.txt": b"pinned==1\n",
            "gdw_runtime.py": b"raise AssertionError('application must never be imported')\n",
            "serve.py": b"import optional_surface\n", "optional_surface.py": b"optional = True\n",
            "assets/page.html": b"old page\n", "assets/empty.txt": b""}


def derive(files=None, *, sources=SOURCES, deadline=None):
    files = source_files() if files is None else files
    tree = {path: {"mode": "100644", "size": len(data)} for path, data in files.items()}
    return builder._derive(REVISION, tree, files.__getitem__, FixedExpansion(sources),
                           time.monotonic() + 10 if deadline is None else deadline)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("network forbidden in builder tests")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def test_complete_copy_payload_destinations_and_absences_are_canonical():
    files = source_files()
    report = derive(files)
    present = {row["path"]: row for row in report["installed_files"]}
    assert set(present) == {"Dockerfile", "requirements-runtime.txt", "gdw_runtime.py", "serve.py",
                            "static/page.html", "static/empty.txt"}
    assert present["static/page.html"] == {"path": "static/page.html", "source_path": "assets/page.html",
                                           "size": 9, "sha256": hashlib.sha256(b"old page\n").hexdigest()}
    assert present["static/empty.txt"]["size"] == 0
    assert report["absent_modules"] == ["optional_surface.py"]
    assert report["python_inventory"] == {"scope": "ALL_SOURCE_PYTHON_PATHS", "source_count": 3,
                                           "installed_count": 2, "absent_count": 1}
    assert report["copy_payload"]["file_count"] == 6
    assert report["copy_payload"]["total_bytes"] == sum(len(v) for p, v in files.items() if p != "optional_surface.py")
    assert report["source_revision"] == REVISION and report["publisher"] == builder.PUBLISHER
    assert report["build_inputs"] == report["overwrites"] == []
    assert builder.canonical(report) == builder.canonical(derive(dict(reversed(list(files.items())))))
    assert b"application must never" not in builder.canonical(report)


def test_overwrite_retains_both_source_identities_and_copy_order():
    docker = DOCKER.replace("CMD ", "COPY replacement.html ./static/page.html\nCMD ")
    files = source_files(docker)
    files["replacement.html"] = b"final page\n"
    report = derive(files, sources=[*SOURCES, "replacement.html"])
    row = next(row for row in report["installed_files"] if row["path"] == "static/page.html")
    assert row["source_path"] == "replacement.html"
    assert report["overwrites"] == [{"path": "static/page.html",
        "before": {"copy_index": 2, "source_path": "assets/page.html", "size": 9,
                   "sha256": hashlib.sha256(b"old page\n").hexdigest()},
        "after": {"copy_index": 3, "source_path": "replacement.html", "size": 11,
                  "sha256": hashlib.sha256(b"final page\n").hexdigest()}}]
    assert report["copy_payload"]["file_count"] == 7
    repeated = derive(source_files(DOCKER.replace("CMD ", "COPY assets/ ./static/\nCMD ")))
    assert repeated["overwrites"] == [] and repeated["dockerfile"]["copy_instruction_count"] == 3


def test_build_stage_only_and_runtime_install_input_are_explicit():
    docker = ("FROM python:3.14 AS llama-build-1\n"
              "COPY scripts/fetch_owned_khipu_wheel.py /tmp/fetch_owned_khipu_wheel.py\n" + DOCKER)
    docker = docker.replace("WORKDIR /app\n", "WORKDIR /app\nCOPY requirements-runtime.txt /tmp/requirements-runtime.txt\n")
    files = source_files(docker)
    files["scripts/fetch_owned_khipu_wheel.py"] = b"build_input = True\n"
    report = derive(files, sources=["scripts/fetch_owned_khipu_wheel.py", *SOURCES])
    assert [(item["stage"], item["destination"], item["scope"]) for item in report["build_inputs"]] == [
        ("llama-build-1", "/tmp/fetch_owned_khipu_wheel.py", "BUILD_STAGE_ONLY"),
        ("runtime", "/tmp/requirements-runtime.txt", "RUNTIME_INSTALL_INPUT")]
    assert "scripts/fetch_owned_khipu_wheel.py" in report["absent_modules"]
    installed = {row["path"]: row for row in report["installed_files"]}
    assert installed["requirements-runtime.txt"]["sha256"] == report["build_inputs"][1]["sha256"]


def test_json_and_continued_copy_keep_the_same_destination_contract():
    docker = DOCKER.replace("COPY assets/ ./static/", 'COPY ["assets/", "./static/"]')
    assert any(row["path"] == "static/page.html" for row in derive(source_files(docker))["installed_files"])
    docker = DOCKER.replace("gdw_runtime.py serve.py", "gdw_runtime.py " + chr(92) + "\n    serve.py")
    assert derive(source_files(docker))["python_inventory"]["installed_count"] == 2


def test_complete_absences_cover_dynamic_imports_and_namespace_package_candidates():
    files = source_files()
    files.update({"szl_chaski.py": b"optional = True\n", "szl_wasi_rikuq.py": b"optional = True\n",
                  "brain/__init__.py": b"", "a11oy_code/__init__.py": b""})
    assert derive(files)["absent_modules"] == ["a11oy_code/__init__.py", "brain/__init__.py", "optional_surface.py",
                                                "szl_chaski.py", "szl_wasi_rikuq.py"]


@pytest.mark.parametrize("value", ["", "0" * 40, "a" * 39, "A" * 40, True, None])
def test_source_revision_is_exact_nonzero_lowercase(value):
    with pytest.raises(builder.InstalledSourceError, match="INVALID_SOURCE_REVISION"):
        builder._derive(value, {}, lambda _: pytest.fail("source read"), FixedExpansion([]), time.monotonic() + 10)


@pytest.mark.parametrize("path", ["../secret", "/secret", "a/../secret", "a/./b", "a\\b", ".git/config",
                                  "a/.GIT/config", "https://example.invalid/a", "x\x00y", "x\ny", "x" * 513, "\ud800"])
def test_invalid_paths_never_reach_a_reader(path):
    with pytest.raises(builder.InstalledSourceError, match="INVALID_SOURCE_PATH"):
        builder._derive(REVISION, {path: {}}, lambda _: pytest.fail("source read"), FixedExpansion([]), time.monotonic() + 10)


@pytest.mark.parametrize("arguments", ["--from=other file ./", "--exclude=x assets/ ./", "*.py ./", "../file ./",
                                       "file ../../escape", "one two target", "'file' ./", "[true,\"./\"]"])
def test_ambiguous_copy_is_rejected(arguments):
    with pytest.raises(builder.InstalledSourceError):
        builder._copy_parts(arguments)


@pytest.mark.parametrize("instruction", ["ADD assets/ ./static/", "RUN printf changed > /app/serve.py",
                                         "ENTRYPOINT [\"sh\"]", "ONBUILD COPY other /app/", "SHELL [\"bash\"]"])
def test_unreviewed_post_copy_mutation_is_rejected(instruction):
    docker = DOCKER.replace("CMD ", instruction + "\nCMD ")
    with pytest.raises(builder.InstalledSourceError, match="UNREVIEWED_DOCKER_RUN|UNSUPPORTED_DOCKER_INSTRUCTION"):
        derive(source_files(docker))


def test_native_docker_heredocs_preserve_stages_and_bind_generated_model_destination():
    original = (ROOT / "Dockerfile").read_bytes()
    _, instructions = builder._instructions(original)
    assert [arguments.split()[-1] for kind, arguments, _ in instructions if kind == "FROM"] == [
        "llama-build-1", "llama-build-0", "llama-build", "runtime"]
    assert sum(kind == "RUN" for kind, _, _ in instructions) == 10
    assert any("GGUFPY" in arguments for kind, arguments, _ in instructions if kind == "RUN")
    changed = original.replace(b'dest      = "/app/models"', b'dest      = "/app"')
    with pytest.raises(builder.InstalledSourceError, match="UNREVIEWED_DOCKER_RUN"):
        builder._instructions(changed)


@pytest.mark.parametrize("docker", ["# escape=`\nFROM python AS runtime\n",
                                    "FROM python AS runtime\nCOPY x " + chr(92) + "\n",
                                    "FROM python AS runtime\nRUN python <<'PY'\nfrom x import y\n"])
def test_bad_escape_continuation_or_heredoc_fails(docker):
    with pytest.raises(builder.InstalledSourceError):
        builder._instructions(docker.encode())


@pytest.mark.parametrize("copy_line,code", [("COPY serve.py ./renamed.py", "PYTHON_SOURCE_RELOCATION_UNQUALIFIED"),
                                           ("COPY requirements-runtime.txt ./static", "COPY_FILE_DIRECTORY_CONFLICT"),
                                           ("COPY requirements-runtime.txt /outside", "UNQUALIFIED_BUILD_INPUT_DESTINATION")])
def test_relocation_conflict_and_external_destinations_fail(copy_line, code):
    docker = DOCKER.replace("CMD ", copy_line + "\nCMD ")
    with pytest.raises(builder.InstalledSourceError, match=code):
        derive(source_files(docker))


@pytest.mark.parametrize("bound,value", [("MAX_FILES", 2), ("MAX_TOTAL_BYTES", 20), ("MAX_PYTHON_PATHS", 2),
                                         ("MAX_COPY_INSTRUCTIONS", 1), ("MAX_COPY_SOURCES", 2), ("MAX_MANIFEST_BYTES", 100)])
def test_independent_bounds_are_enforced(monkeypatch, bound, value):
    monkeypatch.setattr(builder, bound, value)
    with pytest.raises(builder.InstalledSourceError):
        derive()


@pytest.mark.parametrize("deadline", [True, float("nan"), float("inf"), 0])
def test_invalid_or_expired_deadline_fails(deadline):
    with pytest.raises(builder.InstalledSourceError):
        derive(deadline=deadline)


def test_expiration_after_last_read_never_returns_success(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(builder.time, "monotonic", lambda: clock[0])
    files = source_files()
    tree = {path: {"mode": "100644", "size": len(data)} for path, data in files.items()}
    def read(path):
        if path == "serve.py":
            clock[0] = 111.0
        return files[path]
    with pytest.raises(builder.InstalledSourceError, match="SOURCE_DEADLINE_EXCEEDED"):
        builder._derive(REVISION, tree, read, FixedExpansion(SOURCES), 110.0)


@pytest.mark.parametrize("data", [b"", b"def deploy(): pass\n", b"x" * 65537, "not bytes"])
def test_unpinned_publisher_fails_before_definition_execution(data, monkeypatch):
    monkeypatch.setattr(builder, "exec", lambda *_: pytest.fail("untrusted exec"), raising=False)
    with pytest.raises(builder.InstalledSourceError, match="PUBLISHER_SOURCE_IDENTITY_MISMATCH"):
        builder._publisher_contract(data)


@pytest.mark.parametrize("kind", ["file_symlink", "ancestor_symlink", "fifo", "directory", "hardlink"])
def test_native_reader_never_follows_or_blocks_on_special_inputs(tmp_path, kind):
    original = tmp_path / "source"
    original.write_bytes(b"synthetic source")
    relative = "input"
    if kind == "file_symlink":
        (tmp_path / relative).symlink_to(original)
    elif kind == "ancestor_symlink":
        (tmp_path / "alias").symlink_to(tmp_path, target_is_directory=True)
        relative = "alias/source"
    elif kind == "fifo":
        os.mkfifo(tmp_path / relative)
    elif kind == "directory":
        (tmp_path / relative).mkdir()
    else:
        os.link(original, tmp_path / relative)
    started = time.monotonic()
    with pytest.raises(builder.InstalledSourceError):
        builder._read_file(tmp_path, relative, 1024, started + 1)
    assert time.monotonic() - started < 0.5


def test_native_reader_detects_post_read_replacement(tmp_path, monkeypatch):
    path = tmp_path / "source"
    path.write_bytes(b"original")
    native = builder.os.read
    def changed(descriptor, size):
        value = native(descriptor, size)
        if value == b"":
            path.write_bytes(b"changed!")
        return value
    monkeypatch.setattr(builder.os, "read", changed)
    with pytest.raises(builder.InstalledSourceError, match="SOURCE_FILE_CHANGED"):
        builder._read_file(tmp_path, "source", 1024, time.monotonic() + 2)


@pytest.fixture
def git_source(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    for path, data in source_files().items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    commands = [["init", "-q"], ["add", "."], ["-c", "user.name=Offline", "-c", "user.email=offline@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "synthetic source"]]
    for command in commands:
        subprocess.run(["git", "-C", str(root), *command], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
    publisher = tmp_path / "publisher-fixture.py"
    publisher.write_bytes(b"fixed expansion dependency; no publisher is vendored\n")
    monkeypatch.setattr(builder, "_publisher_contract", lambda _: FixedExpansion(SOURCES))
    return root, revision, publisher


def test_native_git_bytes_must_match_exact_source_commit(git_source):
    root, revision, publisher = git_source
    assert builder.build_manifest(root, revision, publisher)["source_revision"] == revision
    (root / "serve.py").write_bytes(b"changed after commit\n")
    with pytest.raises(builder.InstalledSourceError, match="CHECKOUT_DIFFERS_FROM_SOURCE_REVISION"):
        builder.build_manifest(root, revision, publisher)


def test_git_metadata_read_cannot_fetch_missing_promisor_objects(git_source, tmp_path):
    upstream, revision, _ = git_source
    reader = tmp_path / "promisor-reader"
    reader.mkdir()
    commands = [["init", "-q"], ["config", "remote.origin.url", str(upstream)],
                ["config", "remote.origin.promisor", "true"],
                ["config", "remote.origin.partialclonefilter", "blob:none"]]
    for command in commands:
        subprocess.run(["git", "-C", str(reader), *command], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    objects = reader / ".git" / "objects"
    before = {path.relative_to(objects) for path in objects.rglob("*") if path.is_file()}
    # Without the production transport fence, even cat-file fetches this valid
    # missing commit from the owned local promisor and writes a new object pack.
    with pytest.raises(builder.InstalledSourceError, match="SOURCE_GIT_OBJECT_UNAVAILABLE"):
        builder._git(reader, ["cat-file", "-t", revision], 64, time.monotonic() + 5)
    assert {path.relative_to(objects) for path in objects.rglob("*") if path.is_file()} == before
    assert not (reader / ".git" / "FETCH_HEAD").exists()


def test_untracked_payload_is_rejected_without_reading_its_contents(git_source, monkeypatch):
    root, revision, publisher = git_source
    (root / "assets/untracked-private.db").write_bytes(b"synthetic unread payload sentinel")
    native = builder._read_file
    def read(directory, relative, *args):
        assert relative != "assets/untracked-private.db"
        return native(directory, relative, *args)
    monkeypatch.setattr(builder, "_read_file", read)
    with pytest.raises(builder.InstalledSourceError, match="COPY_CHECKOUT_MEMBERSHIP_CHANGED"):
        builder.build_manifest(root, revision, publisher)


def test_cli_preserves_existing_output_and_redacts_os_errors(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "existing.json"
    destination.write_bytes(b"retain old evidence")
    monkeypatch.setattr(builder, "build_manifest", lambda *_, **__: {"fixture": True})
    result = builder.main(["--repo-root", str(tmp_path / "repo"), "--source-revision", REVISION,
                           "--publisher-script", str(tmp_path / "publisher"), "--output", str(destination)])
    assert result == 2 and destination.read_bytes() == b"retain old evidence"
    assert capsys.readouterr().err == "GDW_INSTALLED_SOURCE_BUILD_FAILED:SOURCE_OUTPUT_UNAVAILABLE\n"


def test_cli_cannot_add_output_to_source_checkout(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(builder, "build_manifest", lambda *_, **__: {"fixture": True})
    result = builder.main(["--repo-root", str(tmp_path), "--source-revision", REVISION,
                           "--publisher-script", str(tmp_path / "publisher"), "--output", str(tmp_path / "output.json")])
    assert result == 2 and not (tmp_path / "output.json").exists()
    assert "OUTPUT_MUST_NOT_MUTATE_SOURCE_CHECKOUT" in capsys.readouterr().err
