#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: bounded installed COPY-source equality for the first GDW cutover.

The protected canonical acquisition derives this record using the pinned Space
publisher's COPY expansion. This module verifies its shape and the actual local
source bytes. It does not attest the interpreter, installed dependency contents,
previously executed bytecode, the operating system, or later generated programs.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
from typing import Any

SCHEMA = "szl.gdw-installed-source/v1"
REPOSITORY = "szl-holdings/a11oy"
RUNTIME_ROOT = "/app"
RUNTIME_INSTALL_ROOT = Path("/tmp")
MAX_MANIFEST_BYTES = 384 * 1024
MAX_INSTALLED_FILES = 2048
MAX_SOURCE_PYTHON_FILES = 4096
MAX_PATH_BYTES = 512
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_COPY_INSTRUCTIONS = 256
MAX_COPY_SOURCES = 1024
MAX_SCAN_ENTRIES = 16_384
MAX_VERIFY_SECONDS = 30
PUBLISHER = {
    "repository": "szl-holdings/.github",
    "revision": "fc71ae973a0f31b8e9ee793fc8545a354448d451",
    "script_path": ".github/scripts/hf_deploy_from_dockerfile.py",
    "script_sha256": "f2f7a6c1296493d034eebed596f4176c2928470a4ed7e23620da6cacf19b16e7",
}
# This mandatory floor is additional to the complete derived inventory, not a
# replacement for the COPY/import closure or permission to omit other files.
REQUIRED_FILES = frozenset({
    "Dockerfile", "requirements-runtime.txt", "serve.py", "a11oy_signing_key.py",
    "ayllu/keys/council-runtime-2026-07-21.pub",
    "gdw_attention.py", "gdw_auth.py", "gdw_drain.py", "gdw_durable_artifacts.py",
    "gdw_durable_runtime.py", "gdw_durable_source.py", "gdw_durable_startup.py", "gdw_durable_guard.py",
    "gdw_durable_image.py",
    "gdw_durable_storage.py", "gdw_proofs.py", "gdw_runtime.py", "gdw_telemetry.py",
    "gdw_workspace.py", "routers/__init__.py", "routers/gdw_frontier.py",
    "routers/series_a_control_plane.py", "scripts/verify_installed_authority.py",
    "szl_codename_gate.py", "szl_colang_policy.py", "szl_content_address.py",
    "szl_corpus_publish.py", "szl_dsse.py", "szl_formulas.py", "szl_hf_bucket.py",
    "szl_sgh_scheduler.py",
})
_EXECUTABLE_SUFFIXES = frozenset({
    ".py", ".pyc", ".pyo", ".pyw", ".pyz", ".pth", ".so", ".pyd",
    ".dll", ".dylib", ".node", ".wasm", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".fish", ".whl", ".egg", ".zip",
})
_LOADER_NAMES = frozenset({
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml",
    "pnpm-workspace.yaml", "yarn.lock", ".npmrc", ".yarnrc", ".yarnrc.yml",
    ".pnp.data.json", "tsconfig.json",
})
_FIELDS = {"schema", "repository", "source_revision", "runtime_root", "publisher",
           "dockerfile", "copy_payload", "installed_files", "python_inventory",
           "absent_modules", "build_inputs", "overwrites"}
_IMPORT_POLICY = None
MANAGED_MODE = "private-dataset-v1"


class SourceBlocked(RuntimeError):
    """Only fixed source-metadata codes leave this boundary."""


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("ascii") + b"\n"
    except Exception:
        raise SourceBlocked("SOURCE_JSON_INVALID") from None


def _shape(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise SourceBlocked("SOURCE_FIELDS_INVALID")
    return value


def _fixed(value, expected):
    if type(value) is not type(expected) or value != expected:
        raise SourceBlocked("SOURCE_FACT_INVALID")


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise SourceBlocked("SOURCE_NUMBER_INVALID")


def _hex(value, length=64):
    if (type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is None
            or value == "0" * length):
        raise SourceBlocked("SOURCE_IDENTITY_INVALID")


def _path(value):
    if (type(value) is not str or not value.isascii() or not 1 <= len(value) <= MAX_PATH_BYTES
            or "\\" in value
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            or PurePosixPath(value).is_absolute() or str(PurePosixPath(value)) != value
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise SourceBlocked("SOURCE_PATH_INVALID")
    return value


def _identity_item(value, fields):
    _shape(value, fields)
    _path(value["source_path"])
    _integer(value["size"], 0, MAX_FILE_BYTES)
    _hex(value["sha256"])


def validate_manifest(value: Any, source_revision: str) -> dict:
    """Pure exact-key and bounded validation; no filesystem/provider access."""
    encoded = canonical(value)
    if not 1 <= len(encoded) <= MAX_MANIFEST_BYTES:
        raise SourceBlocked("SOURCE_MANIFEST_BOUND_INVALID")
    _shape(value, _FIELDS)
    _fixed(value["schema"], SCHEMA)
    _fixed(value["repository"], REPOSITORY)
    _hex(source_revision, 40)
    _fixed(value["source_revision"], source_revision)
    _fixed(value["runtime_root"], RUNTIME_ROOT)
    _shape(value["publisher"], set(PUBLISHER))
    _fixed(value["publisher"], PUBLISHER)
    docker = _shape(value["dockerfile"], {"source_path", "size", "sha256", "runtime_stage",
                                            "workdir", "copy_instruction_count"})
    _identity_item(docker, set(docker))
    _fixed(docker["source_path"], "Dockerfile")
    _fixed(docker["runtime_stage"], "runtime")
    _fixed(docker["workdir"], RUNTIME_ROOT)
    _integer(docker["copy_instruction_count"], 1, MAX_COPY_INSTRUCTIONS)
    payload = _shape(value["copy_payload"], {"scope", "source_count", "file_count", "total_bytes", "sha256"})
    _fixed(payload["scope"], "PINNED_PUBLISHER_COPY_EXPANSION")
    _integer(payload["source_count"], 1, MAX_COPY_SOURCES)
    _integer(payload["file_count"], 1, MAX_INSTALLED_FILES)
    _integer(payload["total_bytes"], 1, MAX_TOTAL_BYTES)
    _hex(payload["sha256"])
    entries = value["installed_files"]
    if type(entries) is not list or not 1 <= len(entries) <= MAX_INSTALLED_FILES:
        raise SourceBlocked("SOURCE_FILE_COUNT_INVALID")
    installed, total, python_paths = {}, 0, set()
    for entry in entries:
        _identity_item(entry, {"path", "source_path", "size", "sha256"})
        name = _path(entry["path"])
        if name in installed:
            raise SourceBlocked("SOURCE_PATH_DUPLICATE")
        if name.endswith(".py"):
            # The first-cutover source inventory deliberately excludes Python
            # relocations, whose import/absence mapping needs another contract.
            _fixed(entry["source_path"], name)
            python_paths.add(name)
        if PurePosixPath(name).suffix in {".pyc", ".pyo", ".pth"}:
            raise SourceBlocked("SOURCE_BYTECODE_NOT_ADMITTED")
        installed[name] = entry
        total += entry["size"]
    if list(installed) != sorted(installed) or not REQUIRED_FILES <= set(installed):
        raise SourceBlocked("SOURCE_INVENTORY_INCOMPLETE")
    _integer(total, 1, MAX_TOTAL_BYTES)
    if any(installed["Dockerfile"][key] != docker[key] for key in ("source_path", "size", "sha256")):
        raise SourceBlocked("SOURCE_DOCKER_BINDING_INVALID")
    absent = value["absent_modules"]
    if type(absent) is not list or len(absent) > MAX_SOURCE_PYTHON_FILES:
        raise SourceBlocked("SOURCE_ABSENCE_COUNT_INVALID")
    for name in absent:
        _path(name)
        if not name.endswith(".py") or name in installed:
            raise SourceBlocked("SOURCE_ABSENCE_INVALID")
    if absent != sorted(set(absent)):
        raise SourceBlocked("SOURCE_ABSENCE_INVALID")
    inventory = _shape(value["python_inventory"], {"scope", "source_count", "installed_count", "absent_count"})
    _fixed(inventory["scope"], "ALL_SOURCE_PYTHON_PATHS")
    _integer(inventory["source_count"], 1, MAX_SOURCE_PYTHON_FILES)
    _fixed(inventory["installed_count"], len(python_paths))
    _fixed(inventory["absent_count"], len(absent))
    _fixed(inventory["source_count"], len(python_paths) + len(absent))
    builds = value["build_inputs"]
    if type(builds) is not list or len(builds) != 2:
        raise SourceBlocked("SOURCE_BUILD_SCOPE_INVALID")
    build_contracts = (
        ("llama-build-1", "/tmp/fetch_owned_khipu_wheel.py", "BUILD_STAGE_ONLY", "scripts/fetch_owned_khipu_wheel.py"),
        ("runtime", "/tmp/requirements-runtime.txt", "RUNTIME_INSTALL_INPUT", "requirements-runtime.txt"),
    )
    for entry, expected in zip(builds, build_contracts):
        _identity_item(entry, {"stage", "destination", "scope", "source_path", "size", "sha256"})
        for key, wanted in zip(("stage", "destination", "scope", "source_path"), expected):
            _fixed(entry[key], wanted)
        if entry["scope"] == "RUNTIME_INSTALL_INPUT":
            target = installed[entry["source_path"]]
            for key in ("size", "sha256"):
                _fixed(entry[key], target[key])
    overwrites = value["overwrites"]
    if type(overwrites) is not list or len(overwrites) > MAX_COPY_INSTRUCTIONS:
        raise SourceBlocked("SOURCE_OVERWRITE_BOUND_INVALID")
    last, ordered, seen = {}, [], set()
    for overwrite in overwrites:
        _shape(overwrite, {"path", "before", "after"})
        name = _path(overwrite["path"])
        if name not in installed:
            raise SourceBlocked("SOURCE_OVERWRITE_INVALID")
        for key in ("before", "after"):
            item = overwrite[key]
            _identity_item(item, {"copy_index", "source_path", "size", "sha256"})
            _integer(item["copy_index"], 1, docker["copy_instruction_count"])
        before, after = overwrite["before"], overwrite["after"]
        if (before["copy_index"] >= after["copy_index"]
                or all(before[key] == after[key] for key in ("source_path", "size", "sha256"))):
            raise SourceBlocked("SOURCE_OVERWRITE_INVALID")
        pair = (after["copy_index"], name)
        if pair in seen:
            raise SourceBlocked("SOURCE_OVERWRITE_INVALID")
        seen.add(pair)
        ordered.append(pair)
        last[name] = after
    if ordered != sorted(ordered):
        raise SourceBlocked("SOURCE_OVERWRITE_ORDER_INVALID")
    for name, item in last.items():
        for key in ("source_path", "size", "sha256"):
            _fixed(item[key], installed[name][key])
    return json.loads(encoded)


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourceBlocked("SOURCE_VERIFICATION_DEADLINE_EXHAUSTED")


def _stat_identity(metadata):
    # Reads may update access time on the actual image filesystem.
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink,
            metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns,
            metadata.st_uid, metadata.st_gid)


def _directory_identity(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid, metadata.st_gid)


def _open_directory(base_fd, parts, deadline):
    descriptor = os.dup(base_fd)
    try:
        for part in parts:
            _deadline(deadline)
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK,
                              dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_root(root, deadline):
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts or str(root) != str(PurePosixPath(root)):
        raise SourceBlocked("SOURCE_ROOT_UNSAFE")
    base = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return _open_directory(base, root.parts[1:], deadline)
    finally:
        os.close(base)


def _read_identity(root_fd, entry, deadline):
    parts = entry["path"].split("/")
    parent = _open_directory(root_fd, parts[:-1], deadline)
    descriptor = None
    try:
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != entry["size"]:
            raise SourceBlocked("SOURCE_FILE_UNSAFE")
        digest, observed = hashlib.sha256(), 0
        while True:
            _deadline(deadline)
            chunk = os.read(descriptor, min(64 * 1024, entry["size"] + 1 - observed))
            if not chunk:
                break
            observed += len(chunk)
            if observed > entry["size"]:
                raise SourceBlocked("SOURCE_FILE_CHANGED")
            digest.update(chunk)
        if (observed != entry["size"] or digest.hexdigest() != entry["sha256"]
                or _stat_identity(os.fstat(descriptor)) != _stat_identity(before)
                or _stat_identity(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)) != _stat_identity(before)):
            raise SourceBlocked("SOURCE_FILE_CHANGED")
        _deadline(deadline)
        return _stat_identity(before)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)



def _require_absent(root_fd, name, deadline):
    parts = name.split("/")
    try:
        parent = _open_directory(root_fd, parts[:-1], deadline)
    except FileNotFoundError:
        return
    try:
        _deadline(deadline)
        try:
            os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise SourceBlocked("SOURCE_REQUIRED_ABSENCE_CHANGED")
    finally:
        os.close(parent)


def _scan_source_tree(root_fd, admitted, deadline):
    pending, count, directories = [""], 0, {}
    while pending:
        _deadline(deadline)
        name = pending.pop()
        descriptor = _open_directory(root_fd, name.split("/") if name else [], deadline)
        try:
            before = _stat_identity(os.fstat(descriptor))
            with os.scandir(descriptor) as entries:
                for item in entries:
                    _deadline(deadline)
                    count += 1
                    if count > MAX_SCAN_ENTRIES:
                        raise SourceBlocked("SOURCE_SCAN_BOUND_INVALID")
                    child = _path(name + "/" + item.name if name else item.name)
                    metadata = os.stat(item.name, dir_fd=descriptor, follow_symlinks=False)
                    if stat.S_ISDIR(metadata.st_mode):
                        pending.append(child)
                    elif not stat.S_ISREG(metadata.st_mode):
                        raise SourceBlocked("SOURCE_TREE_ENTRY_UNSAFE")
                    elif child not in admitted and (metadata.st_mode & 0o111
                            or PurePosixPath(child).suffix.lower() in _EXECUTABLE_SUFFIXES
                            or item.name in _LOADER_NAMES
                            or re.fullmatch(r"tsconfig\.[A-Za-z0-9_.-]+\.json", item.name)):
                        raise SourceBlocked("SOURCE_UNLISTED_EXECUTABLE")
            if _stat_identity(os.fstat(descriptor)) != before:
                raise SourceBlocked("SOURCE_DIRECTORY_CHANGED")
            directories[name] = before
        finally:
            os.close(descriptor)
    return directories


def verify_installed_source(manifest: dict, source_root: Path, source_revision: str, *,
                            runtime_install_root: Path = RUNTIME_INSTALL_ROOT,
                            deadline: float | None = None) -> dict:
    """Hash bounded regular files through no-follow descriptors, then reobserve.

    Roots are selected by canonical code, never by admission fields or an
    environment variable. Optional source absences and unlisted local code are
    checked independently of matching the listed files. No file is executed.
    """
    now = time.monotonic()
    if deadline is None:
        deadline = now + MAX_VERIFY_SECONDS
    if type(deadline) not in {float, int} or not now < deadline <= now + MAX_VERIFY_SECONDS:
        raise SourceBlocked("SOURCE_VERIFICATION_DEADLINE_INVALID")
    value = validate_manifest(manifest, source_revision)
    root_fd = install_fd = None
    try:
        _deadline(deadline)
        root_fd = _open_root(source_root, deadline)
        root_identity = _directory_identity(os.fstat(root_fd))
        install_fd = _open_root(runtime_install_root, deadline)
        install_identity = _directory_identity(os.fstat(install_fd))
        identities = {}
        for entry in value["installed_files"]:
            identities[entry["path"]] = _read_identity(root_fd, entry, deadline)
        build_input = value["build_inputs"][1]
        input_identity = _read_identity(install_fd, dict(build_input, path="requirements-runtime.txt"), deadline)
        for name in value["absent_modules"]:
            _require_absent(root_fd, name, deadline)
        directories = _scan_source_tree(root_fd, identities, deadline)
        entries = {entry["path"]: entry for entry in value["installed_files"]}
        # Re-hash at the final boundary rather than trusting timestamp-only
        # identity. Some supported filesystems can preserve a same-size
        # overwrite inside one timestamp tick.
        for name, identity in identities.items():
            if _read_identity(root_fd, entries[name], deadline) != identity:
                raise SourceBlocked("SOURCE_FILE_CHANGED")
        for name in value["absent_modules"]:
            _require_absent(root_fd, name, deadline)
        for name, identity in directories.items():
            descriptor = _open_directory(root_fd, name.split("/") if name else [], deadline)
            try:
                if _stat_identity(os.fstat(descriptor)) != identity:
                    raise SourceBlocked("SOURCE_DIRECTORY_CHANGED")
            finally:
                os.close(descriptor)
        if (_read_identity(install_fd, dict(build_input, path="requirements-runtime.txt"), deadline)
                != input_identity):
            raise SourceBlocked("SOURCE_INSTALL_INPUT_CHANGED")
        for root, expected in ((source_root, root_identity), (runtime_install_root, install_identity)):
            descriptor = _open_root(root, deadline)
            try:
                if _directory_identity(os.fstat(descriptor)) != expected:
                    raise SourceBlocked("SOURCE_ROOT_CHANGED")
            finally:
                os.close(descriptor)
        _deadline(deadline)
        return {"state": "ADMITTED_SOURCE_CONTENT_EQUALITY", "source_revision": source_revision,
                "manifest_sha256": hashlib.sha256(canonical(value)).hexdigest(),
                "installed_file_count": len(identities), "required_absence_count": len(value["absent_modules"]),
                "dependency_environment_attestation": "NOT_PERFORMED"}
    except SourceBlocked:
        raise
    except Exception:
        raise SourceBlocked("SOURCE_VERIFICATION_UNAVAILABLE") from None
    finally:
        if root_fd is not None:
            os.close(root_fd)
        if install_fd is not None:
            os.close(install_fd)


def install_import_policy(manifest: dict, source_root: Path) -> None:
    """Called only after the coordinator verifies the immutable record and bytes."""
    global _IMPORT_POLICY
    files = {item["path"]: dict(item) for item in manifest["installed_files"]}
    directories = {""}
    for name in files:
        parts = name.split("/")
        directories.update("/".join(parts[:index]) for index in range(1, len(parts)))
    _IMPORT_POLICY = (Path(source_root), files, frozenset(directories))


def clear_import_policy() -> None:
    global _IMPORT_POLICY
    _IMPORT_POLICY = None


def managed_mode() -> bool:
    return os.environ.get("GDW_DURABLE_STORAGE") == MANAGED_MODE


def _admitted_relative(value):
    if _IMPORT_POLICY is None:
        raise SourceBlocked("SOURCE_IMPORT_ADMISSION_UNAVAILABLE")
    root = _IMPORT_POLICY[0]
    if (type(value) is not str or not value.isascii() or not 1 <= len(value) <= MAX_PATH_BYTES
            or not Path(value).is_absolute() or str(Path(value)) != value):
        raise SourceBlocked("SOURCE_IMPORT_PATH_INVALID")
    try:
        relative = Path(value).relative_to(root).as_posix()
    except ValueError:
        raise SourceBlocked("SOURCE_IMPORT_ROOT_NOT_ADMITTED") from None
    if relative == ".":
        return ""
    return _path(relative)


def managed_import_paths(paths: list[str]) -> list[str]:
    """Keep legacy lookup unchanged; managed lookup uses verified payload dirs."""
    if not managed_mode():
        return paths
    if type(paths) is not list or not 1 <= len(paths) <= 32:
        raise SourceBlocked("SOURCE_IMPORT_PATH_COUNT_INVALID")
    names = [_admitted_relative(path) for path in paths]
    if any(name not in _IMPORT_POLICY[2] for name in names):
        raise SourceBlocked("SOURCE_IMPORT_DIRECTORY_NOT_ADMITTED")
    descriptor = None
    try:
        deadline = time.monotonic() + MAX_VERIFY_SECONDS
        descriptor = _open_root(_IMPORT_POLICY[0], deadline)
        for name in names:
            child = _open_directory(descriptor, name.split("/") if name else [], deadline)
            os.close(child)
    except SourceBlocked:
        raise
    except Exception:
        raise SourceBlocked("SOURCE_IMPORT_DIRECTORY_UNSAFE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return list(paths)


def managed_import_file(path: str) -> str:
    """Bind the discovered direct-path Python loader before it executes bytes."""
    if not managed_mode():
        return path
    name = _admitted_relative(path)
    entry = _IMPORT_POLICY[1].get(name)
    if entry is None or not name.endswith(".py"):
        raise SourceBlocked("SOURCE_IMPORT_FILE_NOT_ADMITTED")
    descriptor = None
    try:
        deadline = time.monotonic() + MAX_VERIFY_SECONDS
        descriptor = _open_root(_IMPORT_POLICY[0], deadline)
        _read_identity(descriptor, entry, deadline)
    except SourceBlocked:
        raise
    except Exception:
        raise SourceBlocked("SOURCE_IMPORT_FILE_UNSAFE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return path


def reject_managed_generated_source() -> None:
    if managed_mode():
        raise SourceBlocked("SOURCE_GENERATED_PROGRAM_NOT_ADMITTED")
