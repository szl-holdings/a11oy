#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Derive bounded COPY-source metadata without publishing or admitting a runtime.

The external publisher's exact pinned parser and expander are reused as pure
functions. This tool never loads its mutation functions, runs Docker, acquires
provider data, imports application modules, or reads credentials. Dependency
packages, model downloads and dynamic generated code need separate admission.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import posixpath
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from types import SimpleNamespace


SCHEMA = "szl.gdw-installed-source/v1"
REPOSITORY = "szl-holdings/a11oy"
RUNTIME_ROOT = "/app"
PUBLISHER = {
    "repository": "szl-holdings/.github",
    "revision": "e3ec47ad2e99a535839afe0f30fefbd8973d52da",
    "script_path": ".github/scripts/hf_deploy_from_dockerfile.py",
    "script_sha256": "eecf0ad2095ff345e009a24ba22a574efc974925fc88dd492377628c13b8e663",
}
MAX_MANIFEST_BYTES = 384 * 1024
MAX_FILES = 2048
MAX_PYTHON_PATHS = 4096
MAX_PATH_BYTES = 512
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_COPY_INSTRUCTIONS = 256
MAX_COPY_SOURCES = 1024
MAX_TREE_ENTRIES = 16384
MAX_TREE_BYTES = 8 * 1024 * 1024
MAX_DOCKERFILE_BYTES = 128 * 1024
MAX_SECONDS = 120
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_PATH = re.compile(r"[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)*\Z")
_HEREDOC = re.compile(r"<<(-?)(?:'([A-Za-z_][A-Za-z0-9_]*)'|\"([A-Za-z_][A-Za-z0-9_]*)\"|([A-Za-z_][A-Za-z0-9_]*))")
_BUILD_INPUTS = {
    ("llama-build-1", "/tmp/fetch_owned_khipu_wheel.py", "scripts/fetch_owned_khipu_wheel.py"): "BUILD_STAGE_ONLY",
    ("runtime", "/tmp/requirements-runtime.txt", "requirements-runtime.txt"): "RUNTIME_INSTALL_INPUT",
}
# These exact logical RUN blocks were read at 84fbd5be. None rewrites a copied
# source file. They install external dependencies, create directories, or fetch
# the separately pinned GGUF. An altered/new command requires source review.
_REVIEWED_RUNS = frozenset({
    "390f3679f990ada5d981c2b137675744fda09c39bdceb5f39daae3177e0b5881",
    "a35a26a82f617413b433151e190dd1e9b95c26cdc7a12ca335dc0b058e649fea",
    "e39a2e3ea22b3b11ca25c0ff9a315699c10fab38fa5c724c4fd8531f9fa90e52",
    "9bc7b45b7cfa01134562baf3556bdb838699015be5fec064bac8b6c59a692b3c",
    "3601742ada1aed23b68016307b3e64138bad11f1ed8227705b62e6debaefb4b0",
    "315a524e14424b87687a4404d3ab12142dba6c6c029aa1c3afc0dc535520c6b9",
    "3f4dd596d561b1a19f2aa80bb0e7b1d4a0f511bb09febff19e69392358ab03f5",
    "d81f48914c378947ed4284cb8d33454cc5552daff8a181f924aa775d5feee8d0",
    "dfdf191884b3aa09fb1cc6670fc54d449290d58d911806743c70cc2317b054e6",
    "2b8bd6242edf7388d66f7cd14f3cd6732cc2ee22df61021ff2eb2b7d7b5782b5",
})


class InstalledSourceError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical(value) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise InstalledSourceError("INVALID_SOURCE_METADATA") from None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _remaining(deadline: float) -> float:
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise InstalledSourceError("INVALID_DEADLINE")
    value = deadline - time.monotonic()
    if value <= 0:
        raise InstalledSourceError("SOURCE_DEADLINE_EXCEEDED")
    return min(value, MAX_SECONDS)


def _relative(value: str) -> str:
    if (type(value) is not str or _PATH.fullmatch(value) is None or not 1 <= len(value) <= MAX_PATH_BYTES
            or any(part in {".", ".."} for part in value.split("/"))
            or any(part.casefold() == ".git" for part in value.split("/"))):
        raise InstalledSourceError("INVALID_SOURCE_PATH")
    return value


def _root_fd(path: Path) -> int:
    value = os.fspath(path)
    if not os.path.isabs(value) or str(Path(value)) != value or any(p in {".", ".."} for p in value.split("/")[1:]):
        raise InstalledSourceError("INVALID_SOURCE_ROOT")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in Path(value).parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError:
        os.close(descriptor)
        raise InstalledSourceError("SOURCE_DIRECTORY_UNAVAILABLE") from None


def _parent_fd(root: Path, relative: str) -> tuple[int, str]:
    parts = _relative(relative).split("/")
    descriptor = _root_fd(root)
    try:
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except OSError:
        os.close(descriptor)
        raise InstalledSourceError("SOURCE_DIRECTORY_UNAVAILABLE") from None


def _identity(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _read_file(root: Path, relative: str, limit: int, deadline: float) -> bytes:
    _remaining(deadline)
    parent, name = _parent_fd(root, relative)
    descriptor = None
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 <= before.st_size <= limit:
            raise InstalledSourceError("SOURCE_FILE_UNQUALIFIED")
        def read_once() -> bytes:
            data = bytearray()
            while True:
                _remaining(deadline)
                chunk = os.read(descriptor, min(1024 * 1024, limit + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > limit:
                    raise InstalledSourceError("SOURCE_FILE_LIMIT_EXCEEDED")
            return bytes(data)

        data = read_once()
        after = os.fstat(descriptor)
        path_after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if len(data) != before.st_size or _identity(before) != _identity(after) or _identity(before) != _identity(path_after):
            raise InstalledSourceError("SOURCE_FILE_CHANGED")

        # Metadata timestamps can have coarse granularity. Re-read the same
        # no-follow descriptor so a same-size overwrite cannot hide inside an
        # unchanged inode/mtime/ctime tuple.
        _remaining(deadline)
        os.lseek(descriptor, 0, os.SEEK_SET)
        confirmed = read_once()
        final = os.fstat(descriptor)
        path_final = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (confirmed != data or _identity(before) != _identity(final)
                or _identity(before) != _identity(path_final)):
            raise InstalledSourceError("SOURCE_FILE_CHANGED")
        _remaining(deadline)
        return data
    except OSError:
        raise InstalledSourceError("SOURCE_FILE_UNAVAILABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _publisher_contract(data: bytes):
    if type(data) is not bytes or len(data) > 64 * 1024 or _sha(data) != PUBLISHER["script_sha256"]:
        raise InstalledSourceError("PUBLISHER_SOURCE_IDENTITY_MISMATCH")
    # Compile only the three exact definitions: no deployment/API functions,
    # module imports, main(), filesystem reader or source materializer is loaded.
    wanted = {"DeployContractError", "parse_copy_sources", "expand_sources"}
    nodes = [node for node in ast.parse(data).body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in wanted]
    if {node.name for node in nodes} != wanted or len(nodes) != 3:
        raise InstalledSourceError("PUBLISHER_SOURCE_UNQUALIFIED")
    namespace = {"__name__": "pinned_readonly_copy_contract", "fnmatch": fnmatch, "re": re, "json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<pinned-readonly-copy-contract>", "exec"), namespace)
    return SimpleNamespace(parse=namespace["parse_copy_sources"], expand=namespace["expand_sources"],
                           error=namespace["DeployContractError"])


def _instructions(data: bytes):
    if not 1 <= len(data) <= MAX_DOCKERFILE_BYTES:
        raise InstalledSourceError("DOCKERFILE_LIMIT_EXCEEDED")
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise InstalledSourceError("DOCKERFILE_ENCODING_INVALID") from None
    if "\r" in text or "\x00" in text or re.search(r"(?im)^\s*#\s*escape\s*=", text):
        raise InstalledSourceError("UNSUPPORTED_DOCKER_ESCAPE")
    lines, position, result = text.splitlines(), 0, []
    while position < len(lines):
        line = lines[position]
        position += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        while line.rstrip().endswith("\\"):
            if position == len(lines) or lines[position].lstrip().startswith("#"):
                raise InstalledSourceError("AMBIGUOUS_DOCKER_CONTINUATION")
            line = line.rstrip()[:-1] + " " + lines[position]
            position += 1
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            raise InstalledSourceError("DOCKER_INSTRUCTION_INVALID")
        instruction, arguments = parts[0].upper(), parts[1]
        raw = line + "\n"
        if instruction == "RUN":
            matches = list(_HEREDOC.finditer(line))
            if line.count("<<") != len(matches) or len(matches) > 4:
                raise InstalledSourceError("UNSUPPORTED_DOCKER_HEREDOC")
            for match in matches:
                dash, single, double, bare = match.groups()
                marker = single or double or bare
                while position < len(lines):
                    part = lines[position]
                    position += 1
                    raw += part + "\n"
                    if (part.lstrip("\t") if dash else part) == marker:
                        break
                else:
                    raise InstalledSourceError("UNTERMINATED_DOCKER_HEREDOC")
            if _sha(raw.encode()) not in _REVIEWED_RUNS:
                raise InstalledSourceError("UNREVIEWED_DOCKER_RUN")
        elif "<<" in line:
            raise InstalledSourceError("UNSUPPORTED_DOCKER_HEREDOC")
        if instruction not in {"FROM", "WORKDIR", "COPY", "RUN", "ARG", "ENV", "LABEL", "EXPOSE", "VOLUME", "CMD"}:
            raise InstalledSourceError("UNSUPPORTED_DOCKER_INSTRUCTION")
        result.append((instruction, arguments, line))
    return text, result


def _copy_parts(arguments: str) -> tuple[list[str], str]:
    if arguments.startswith("["):
        try:
            parts = json.loads(arguments)
        except (ValueError, TypeError):
            raise InstalledSourceError("COPY_ARGUMENTS_INVALID") from None
        if type(parts) is not list or len(parts) < 2 or any(type(part) is not str for part in parts):
            raise InstalledSourceError("COPY_ARGUMENTS_INVALID")
    else:
        if any(char in arguments for char in "\"'\\"):
            raise InstalledSourceError("AMBIGUOUS_COPY_QUOTING")
        parts = arguments.split()
    if len(parts) < 2 or any(part.startswith("--") for part in parts):
        raise InstalledSourceError("UNSUPPORTED_COPY_FLAGS")
    sources = []
    for source in parts[:-1]:
        while source.startswith("./"):
            source = source[2:]
        if any(char in source for char in "*?["):
            raise InstalledSourceError("AMBIGUOUS_COPY_GLOB")
        sources.append(_relative(source.rstrip("/")))
    destination = parts[-1]
    if (not destination or any(char in destination for char in "$\\\x00")
            or ".." in destination.split("/") or len(sources) > 1 and not destination.endswith("/")):
        raise InstalledSourceError("COPY_DESTINATION_INVALID")
    return sources, destination


def _derive(source_revision: str, tree: dict, read_source, publisher, deadline: float) -> dict:
    if type(source_revision) is not str or _HEX40.fullmatch(source_revision) is None or source_revision == "0" * 40:
        raise InstalledSourceError("INVALID_SOURCE_REVISION")
    if not 1 <= len(tree) <= MAX_TREE_ENTRIES:
        raise InstalledSourceError("SOURCE_TREE_LIMIT_EXCEEDED")
    for path in tree:
        _relative(path)
    docker = read_source("Dockerfile")
    text, instructions = _instructions(docker)
    try:
        sources = publisher.parse(text)
        targets, unresolved = publisher.expand(sources, tree)
    except publisher.error:
        raise InstalledSourceError("PUBLISHER_COPY_CONTRACT_REJECTED") from None
    if not 1 <= len(sources) <= MAX_COPY_SOURCES or not 1 <= len(targets) <= MAX_FILES or unresolved:
        raise InstalledSourceError("COPY_PAYLOAD_UNQUALIFIED")
    metadata, payload, total = {}, [], 0
    for path in sorted(targets):
        _remaining(deadline)
        info = tree[path]
        if info["mode"] not in {"100644", "100755"} or not 0 <= info["size"] <= MAX_FILE_BYTES:
            raise InstalledSourceError("SOURCE_FILE_UNQUALIFIED")
        data = read_source(path)
        if len(data) != info["size"]:
            raise InstalledSourceError("SOURCE_FILE_CHANGED")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise InstalledSourceError("COPY_PAYLOAD_LIMIT_EXCEEDED")
        metadata[path] = {"source_path": path, "size": len(data), "sha256": _sha(data)}
        payload.append(dict(metadata[path], copy_source=targets[path]))
    installed, positions, build_inputs, overwrites = {}, {}, [], []
    expanded_paths, parsed_sources, stage_names = set(), [], set()
    stage, workdir, copy_index, saw_runtime, command_count = None, None, 0, False, 0
    for instruction, arguments, _ in instructions:
        _remaining(deadline)
        if instruction == "FROM":
            parts = arguments.split()
            if len(parts) != 3 or parts[1].upper() != "AS" or not re.fullmatch(r"[a-z][a-z0-9-]*", parts[2]):
                raise InstalledSourceError("UNSUPPORTED_DOCKER_STAGE")
            stage, workdir = parts[2], None
            if stage in stage_names or saw_runtime:
                raise InstalledSourceError("DOCKER_RUNTIME_STAGE_AMBIGUOUS")
            stage_names.add(stage)
            saw_runtime = stage == "runtime"
        elif instruction == "WORKDIR":
            if stage != "runtime" or arguments != RUNTIME_ROOT or workdir is not None:
                raise InstalledSourceError("UNSUPPORTED_DOCKER_WORKDIR")
            workdir = arguments
        elif instruction == "CMD":
            command_count += 1
            try:
                command = json.loads(arguments)
            except ValueError:
                raise InstalledSourceError("UNSUPPORTED_RUNTIME_COMMAND") from None
            if stage != "runtime" or command not in (["python", "gdw_runtime.py"], ["python", "-B", "gdw_runtime.py"]):
                raise InstalledSourceError("UNSUPPORTED_RUNTIME_COMMAND")
        elif instruction == "COPY":
            copy_index += 1
            if copy_index > MAX_COPY_INSTRUCTIONS or stage is None:
                raise InstalledSourceError("COPY_INSTRUCTION_LIMIT_EXCEEDED")
            copy_sources, destination = _copy_parts(arguments)
            base = posixpath.normpath(posixpath.join(workdir or "/", destination))
            for source in copy_sources:
                parsed_sources.append(source)
                matches, missing = publisher.expand([source], tree)
                if missing:
                    raise InstalledSourceError("COPY_SOURCE_MISSING")
                directory = source not in tree
                for path in sorted(matches):
                    expanded_paths.add(path)
                    suffix = path[len(source) + 1:] if directory else posixpath.basename(path)
                    target = posixpath.join(base, suffix) if directory or destination.endswith("/") else base
                    record = metadata[path]
                    if stage != "runtime" or not target.startswith(RUNTIME_ROOT + "/"):
                        scope = _BUILD_INPUTS.get((stage, target, path))
                        if scope is None:
                            raise InstalledSourceError("UNQUALIFIED_BUILD_INPUT_DESTINATION")
                        build_inputs.append(dict(record, stage=stage, destination=target, scope=scope))
                        continue
                    if workdir != RUNTIME_ROOT:
                        raise InstalledSourceError("DOCKER_RUNTIME_WORKDIR_MISSING")
                    relative = _relative(target[len(RUNTIME_ROOT) + 1:])
                    if relative.endswith(".py") != path.endswith(".py") or relative.endswith(".py") and relative != path:
                        raise InstalledSourceError("PYTHON_SOURCE_RELOCATION_UNQUALIFIED")
                    if any(relative.startswith(existing + "/") or existing.startswith(relative + "/") for existing in installed):
                        raise InstalledSourceError("COPY_FILE_DIRECTORY_CONFLICT")
                    current = dict(record, path=relative)
                    if relative in installed and installed[relative] != current:
                        before = {key: installed[relative][key] for key in ("source_path", "size", "sha256")}
                        overwrites.append({"path": relative, "before": dict(before, copy_index=positions[relative]),
                                           "after": dict(record, copy_index=copy_index)})
                    installed[relative], positions[relative] = current, copy_index
    if not saw_runtime or workdir != RUNTIME_ROOT or command_count != 1 or expanded_paths != set(targets):
        raise InstalledSourceError("COPY_DERIVATION_DISAGREES_WITH_PUBLISHER")
    if {source.rstrip("/") for source in sources} != set(parsed_sources):
        raise InstalledSourceError("COPY_DERIVATION_DISAGREES_WITH_PUBLISHER")
    if not {"Dockerfile", "requirements-runtime.txt", "gdw_runtime.py", "serve.py"} <= set(installed):
        raise InstalledSourceError("RUNTIME_ENTRY_SOURCE_MISSING")
    if len(installed) > MAX_FILES or sum(record["size"] for record in installed.values()) > MAX_TOTAL_BYTES:
        raise InstalledSourceError("INSTALLED_SOURCE_LIMIT_EXCEEDED")
    python_paths = {path for path in tree if path.endswith(".py")}
    if len(python_paths) > MAX_PYTHON_PATHS or any(tree[path]["mode"] not in {"100644", "100755"} for path in python_paths):
        raise InstalledSourceError("PYTHON_SOURCE_INVENTORY_UNQUALIFIED")
    present_python = {path for path in installed if path.endswith(".py")}
    absent = sorted(python_paths - present_python)
    result = {
        "schema": SCHEMA, "repository": REPOSITORY, "source_revision": source_revision, "runtime_root": RUNTIME_ROOT,
        "publisher": dict(PUBLISHER),
        "dockerfile": {"source_path": "Dockerfile", "size": len(docker), "sha256": _sha(docker),
                       "runtime_stage": "runtime", "workdir": RUNTIME_ROOT, "copy_instruction_count": copy_index},
        "copy_payload": {"scope": "PINNED_PUBLISHER_COPY_EXPANSION", "source_count": len(sources),
                         "file_count": len(targets), "total_bytes": total, "sha256": _sha(canonical(payload))},
        "installed_files": [installed[path] for path in sorted(installed)],
        "python_inventory": {"scope": "ALL_SOURCE_PYTHON_PATHS", "source_count": len(python_paths),
                             "installed_count": len(present_python), "absent_count": len(absent)},
        "absent_modules": absent, "build_inputs": build_inputs, "overwrites": overwrites,
    }
    if len(canonical(result)) > MAX_MANIFEST_BYTES:
        raise InstalledSourceError("SOURCE_MANIFEST_LIMIT_EXCEEDED")
    _remaining(deadline)
    return result


def _git(root: Path, arguments: list[str], limit: int, deadline: float) -> bytes:
    environment = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1",
                   "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": ""}
    process = subprocess.Popen(["git", "-C", str(root), "-c", "core.fsmonitor=false", *arguments],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=environment, start_new_session=True)
    output = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                if not selector.select(_remaining(deadline)):
                    raise InstalledSourceError("SOURCE_DEADLINE_EXCEEDED")
                chunk = os.read(process.stdout.fileno(), min(65536, limit + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > limit:
                    raise InstalledSourceError("SOURCE_TREE_LIMIT_EXCEEDED")
        if process.wait(timeout=_remaining(deadline)) != 0:
            raise InstalledSourceError("SOURCE_GIT_OBJECT_UNAVAILABLE")
        return bytes(output)
    except (OSError, subprocess.TimeoutExpired):
        raise InstalledSourceError("SOURCE_GIT_READ_UNAVAILABLE") from None
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        process.stdout.close()


def _checkout_scope(root: Path, source: str, deadline: float) -> set[str]:
    parent, name = _parent_fd(root, source)
    found, stack = set(), []
    count = 0
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            return {source}
        if not stat.S_ISDIR(info.st_mode):
            raise InstalledSourceError("COPY_CHECKOUT_ENTRY_UNQUALIFIED")
        stack.append((os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent), source))
        while stack:
            descriptor, prefix = stack.pop()
            try:
                with os.scandir(descriptor) as children:
                    for child in children:
                        _remaining(deadline)
                        count += 1
                        if count > MAX_TREE_ENTRIES:
                            raise InstalledSourceError("COPY_CHECKOUT_LIMIT_EXCEEDED")
                        relative = _relative(prefix + "/" + child.name)
                        info = child.stat(follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            stack.append((os.open(child.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                                  dir_fd=descriptor), relative))
                        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                            found.add(relative)
                        else:
                            raise InstalledSourceError("COPY_CHECKOUT_ENTRY_UNQUALIFIED")
            finally:
                os.close(descriptor)
        return found
    except OSError:
        raise InstalledSourceError("COPY_CHECKOUT_UNAVAILABLE") from None
    finally:
        for descriptor, _ in stack:
            os.close(descriptor)
        os.close(parent)


def build_manifest(repo_root: Path, source_revision: str, publisher_script: Path, *, deadline: float | None = None) -> dict:
    if deadline is not None:
        _remaining(deadline)
    deadline = min(deadline, time.monotonic() + MAX_SECONDS) if deadline is not None else time.monotonic() + MAX_SECONDS
    _remaining(deadline)
    root = Path(repo_root)
    descriptor = _root_fd(root)
    os.close(descriptor)
    if type(source_revision) is not str or _HEX40.fullmatch(source_revision) is None or source_revision == "0" * 40:
        raise InstalledSourceError("INVALID_SOURCE_REVISION")
    if _git(root, ["cat-file", "-t", source_revision], 64, deadline) != b"commit\n":
        raise InstalledSourceError("SOURCE_REVISION_IS_NOT_COMMIT")
    raw_tree = _git(root, ["ls-tree", "-rz", "-l", source_revision], MAX_TREE_BYTES, deadline)
    tree = {}
    try:
        for item in raw_tree.split(b"\0"):
            if not item:
                continue
            meta, raw_path = item.split(b"\t", 1)
            mode, kind, oid, raw_size = meta.split()
            path = _relative(raw_path.decode("ascii"))
            if path in tree or len(tree) >= MAX_TREE_ENTRIES:
                raise InstalledSourceError("SOURCE_TREE_LIMIT_EXCEEDED")
            tree[path] = {"mode": mode.decode(), "oid": oid.decode(),
                          "size": int(raw_size) if kind == b"blob" else -1}
    except (ValueError, UnicodeError):
        raise InstalledSourceError("SOURCE_TREE_UNQUALIFIED") from None
    publisher_path = Path(publisher_script)
    publisher = _publisher_contract(_read_file(publisher_path.parent, publisher_path.name, 64 * 1024, deadline))

    def read_source(path):
        info = tree.get(path)
        if info is None or info["mode"] not in {"100644", "100755"}:
            raise InstalledSourceError("SOURCE_FILE_UNQUALIFIED")
        data = _read_file(root, path, MAX_FILE_BYTES, deadline)
        blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if len(data) != info["size"] or blob != info["oid"]:
            raise InstalledSourceError("CHECKOUT_DIFFERS_FROM_SOURCE_REVISION")
        return data

    docker = read_source("Dockerfile")
    try:
        sources = publisher.parse(docker.decode("utf-8"))
    except (publisher.error, UnicodeError):
        raise InstalledSourceError("PUBLISHER_COPY_CONTRACT_REJECTED") from None
    _instructions(docker)
    for source in sources:
        normalized = _relative(source.rstrip("/"))
        expected, missing = publisher.expand([source], tree)
        if missing or _checkout_scope(root, normalized, deadline) != set(expected):
            raise InstalledSourceError("COPY_CHECKOUT_MEMBERSHIP_CHANGED")
    result = _derive(source_revision, tree, read_source, publisher, deadline)
    # Re-read the complete bounded payload at the final boundary. An untracked
    # file in a directory COPY is rejected without reading its possible data.
    targets, _ = publisher.expand(sources, tree)
    for path in sorted(targets):
        read_source(path)
    for source in sources:
        expected, _ = publisher.expand([source], tree)
        if _checkout_scope(root, source.rstrip("/"), deadline) != set(expected):
            raise InstalledSourceError("COPY_CHECKOUT_MEMBERSHIP_CHANGED")
    _remaining(deadline)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--publisher-script", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        deadline = time.monotonic() + MAX_SECONDS
        result = build_manifest(args.repo_root, args.source_revision, args.publisher_script, deadline=deadline)
        data = canonical(result)
        _remaining(deadline)
        if args.output is None:
            sys.stdout.buffer.write(data)
        else:
            output = args.output.absolute()
            if output == args.repo_root or args.repo_root in output.parents:
                raise InstalledSourceError("OUTPUT_MUST_NOT_MUTATE_SOURCE_CHECKOUT")
            parent, name = _parent_fd(output.parent, output.name)
            try:
                descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
            finally:
                os.close(parent)
        _remaining(deadline)
        return 0
    except (InstalledSourceError, OSError) as error:
        code = error.code if isinstance(error, InstalledSourceError) else "SOURCE_OUTPUT_UNAVAILABLE"
        print("GDW_INSTALLED_SOURCE_BUILD_FAILED:" + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
