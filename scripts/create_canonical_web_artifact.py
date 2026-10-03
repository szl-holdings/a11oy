#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Stage a bounded canonical web build for review, with no deployment authority.

Plan: admit exact Git/submodule identity, regular bounded output and local index
references; exclude hidden Vite sourcemaps; copy checked bytes into a fresh path.
The manifest deliberately leaves API binding unavailable and deployment blocked.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from urllib.parse import unquote, urlsplit

BASE_PATH = "/a11oy/"
PLATFORM_PATH = "vendor/platform"
MAX_FILES = 4096
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
STATIC_EXTENSIONS = frozenset({
    ".js", ".mjs", ".css", ".html", ".json", ".txt", ".xml", ".svg",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".bmp", ".apng",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".wasm", ".webmanifest",
})
SHA = re.compile(r"[0-9a-f]{40}")
SEGMENT = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


class AdmissionError(ValueError):
    pass


def command(cwd, arguments):
    result = subprocess.run(arguments, cwd=cwd, check=True, capture_output=True,
                            text=True, timeout=30,
                            env={**os.environ, "GIT_NO_LAZY_FETCH": "1",
                                 "GIT_TERMINAL_PROMPT": "0"})
    if len(result.stdout) > 128 * 1024:
        raise AdmissionError("METADATA_TOO_LARGE")
    return result.stdout.strip()


def git(root, *arguments):
    return command(root, ["git", *arguments])


def collect_identity(root, expected_source):
    if not isinstance(expected_source, str) or not SHA.fullmatch(expected_source):
        raise AdmissionError("EXPECTED_SOURCE_REQUIRED")
    source = git(root, "rev-parse", "HEAD")
    if source != expected_source:
        raise AdmissionError("SOURCE_REVISION_MISMATCH")
    git(root, "diff", "--quiet", "HEAD", "--")
    submodule = root / PLATFORM_PATH
    revision = git(submodule, "rev-parse", "HEAD")
    entry = git(root, "ls-tree", "HEAD", "--", PLATFORM_PATH)
    if entry != f"160000 commit {revision}\t{PLATFORM_PATH}" or not SHA.fullmatch(revision):
        raise AdmissionError("PLATFORM_GITLINK_MISMATCH")
    git(submodule, "diff", "--quiet", "HEAD", "--")
    url = git(root, "config", "-f", ".gitmodules", "--get", "submodule.vendor/platform.url")
    if url != "https://github.com/szl-holdings/platform.git":
        raise AdmissionError("PLATFORM_SOURCE_MISMATCH")
    package = json.loads(git(submodule, "show", f"{revision}:package.json"))
    artifact = json.loads(git(submodule, "show", f"{revision}:artifacts/a11oy/package.json"))
    node = command(root, ["node", "--version"])
    pnpm = command(root, ["pnpm", "--version"])
    if (package.get("packageManager") != "pnpm@10.26.1"
            or artifact.get("name") != "@workspace/a11oy"
            or not re.fullmatch(r"v\d+\.\d+\.\d+", node)
            or int(node[1:].split(".")[0]) < 24 or pnpm != "10.26.1"):
        raise AdmissionError("TOOLCHAIN_OR_PACKAGE_MISMATCH")
    return {"repository": "szl-holdings/a11oy", "revision": source,
            "platform_repository": "szl-holdings/platform", "platform_revision": revision,
            "platform_gitlink": revision, "artifact": "artifacts/a11oy",
            "package": artifact["name"], "package_manager": package["packageManager"],
            "node": node, "pnpm": pnpm}


def safe_name(value):
    if not value or "\\" in value or PurePosixPath(value).is_absolute():
        raise AdmissionError("UNSAFE_PATH")
    parts = value.split("/")
    if any(not SEGMENT.fullmatch(part) or part.endswith(".")
           or part.split(".")[0].upper() in RESERVED for part in parts):
        raise AdmissionError("UNSAFE_PATH")
    return value


def fingerprint(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def regular_file(path):
    value = path.lstat()
    if (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
            or getattr(value, "st_file_attributes", 0) & 0x400):
        raise AdmissionError("FILE_NOT_SINGLE_REGULAR_FILE")
    return value


def reject_linked_parents(path):
    for candidate in (path, *path.parents):
        if candidate.exists() or candidate.is_symlink():
            value = candidate.lstat()
            if stat.S_ISLNK(value.st_mode) or getattr(value, "st_file_attributes", 0) & 0x400:
                raise AdmissionError("LINKED_PARENT")


def inventory(source):
    reject_linked_parents(source)
    if not source.is_dir():
        raise AdmissionError("BUILD_OUTPUT_MISSING")
    files, total, entries = {}, 0, 0
    def failed_scan(error):
        raise AdmissionError("OUTPUT_SCAN_FAILED") from error
    for directory, directories, names in os.walk(source, followlinks=False, onerror=failed_scan):
        parent = Path(directory)
        entries += len(directories) + len(names)
        if entries > MAX_FILES:
            raise AdmissionError("OUTPUT_LIMIT_EXCEEDED")
        for name in directories:
            child = parent / name
            safe_name(child.relative_to(source).as_posix())
            reject_linked_parents(child)
            if not stat.S_ISDIR(child.lstat().st_mode):
                raise AdmissionError("SPECIAL_DIRECTORY")
        for name in names:
            child = parent / name
            relative = safe_name(child.relative_to(source).as_posix())
            value = regular_file(child)
            if Path(relative).suffix.lower() not in STATIC_EXTENSIONS | {".map"}:
                raise AdmissionError("NON_STATIC_EXPORT_REJECTED")
            total += value.st_size
            if (value.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES
                    or len(files) >= MAX_FILES):
                raise AdmissionError("OUTPUT_LIMIT_EXCEEDED")
            files[relative] = fingerprint(value)
    if "index.html" not in files:
        raise AdmissionError("INDEX_MISSING")
    return files


def checked_bytes(path, expected):
    reject_linked_parents(path)
    if fingerprint(regular_file(path)) != expected:
        raise AdmissionError("SOURCE_CHANGED")
    reject_linked_parents(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0)
                         | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        value = os.fstat(stream.fileno())
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or fingerprint(value) != expected:
            raise AdmissionError("SOURCE_CHANGED")
        payload = stream.read(MAX_FILE_BYTES + 1)
        if len(payload) != expected[2] or fingerprint(os.fstat(stream.fileno())) != expected:
            raise AdmissionError("SOURCE_CHANGED")
    if fingerprint(regular_file(path)) != expected:
        raise AdmissionError("SOURCE_CHANGED")
    return payload


class IndexReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"script", "link"} and len(values) != len(attrs):
            raise AdmissionError("INDEX_REFERENCE_INVALID")
        if tag == "script" and "src" in values:
            self.references.append(values["src"])
        if tag == "link" and "stylesheet" in (values.get("rel") or "").lower().split():
            self.references.append(values.get("href"))


def validate_index(payload, admitted):
    parser = IndexReferences()
    parser.feed(payload.decode("utf-8", errors="strict"))
    if not parser.references:
        raise AdmissionError("INDEX_REFERENCES_MISSING")
    for value in parser.references:
        if not isinstance(value, str):
            raise AdmissionError("INDEX_REFERENCE_INVALID")
        parsed = urlsplit(value)
        path = unquote(parsed.path, errors="strict")
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not path.startswith(BASE_PATH):
            raise AdmissionError("INDEX_BASE_PATH_MISMATCH")
        relative = safe_name(path[len(BASE_PATH):])
        if relative not in admitted:
            raise AdmissionError("INDEX_REFERENCE_MISSING")


def stage_artifact(root, output, expected_source, identity_reader=collect_identity):
    root, output = Path(root).absolute(), Path(output).absolute()
    source = root / PLATFORM_PATH / "artifacts/a11oy/dist/public"
    reject_linked_parents(output)
    if output.exists() or output.is_symlink():
        raise AdmissionError("OUTPUT_ALREADY_EXISTS")
    if output == source or source in output.parents or output in source.parents:
        raise AdmissionError("OUTPUT_SOURCE_OVERLAP")
    identity = identity_reader(root, expected_source)
    if identity.get("revision") != expected_source:
        raise AdmissionError("SOURCE_REVISION_MISMATCH")
    observed = inventory(source)
    excluded = sorted(name for name in observed if name.lower().endswith(".map"))
    admitted = set(observed) - set(excluded)
    validate_index(checked_bytes(source / "index.html", observed["index.html"]), admitted)
    output.mkdir()
    records = []
    for relative in sorted(admitted):
        payload = checked_bytes(source / relative, observed[relative])
        destination = output / "public" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        reject_linked_parents(destination.parent)
        with destination.open("xb") as stream:
            stream.write(payload)
        copied = checked_bytes(destination, fingerprint(regular_file(destination)))
        if copied != payload:
            raise AdmissionError("STAGED_BYTES_MISMATCH")
        records.append({"path": relative, "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest()})
    reject_linked_parents(output)
    if inventory(source) != observed or identity_reader(root, expected_source) != identity:
        raise AdmissionError("SOURCE_CHANGED")
    manifest = {"schema": "szl.canonical-web-artifact/v1", "state": "STAGED_FOR_REVIEW",
                "generated_at": datetime.now(timezone.utc).isoformat(), "source": identity,
                "base_path": BASE_PATH, "files": records,
                "total_bytes": sum(item["size"] for item in records),
                "allowed_static_extensions": sorted(STATIC_EXTENSIONS),
                "embedded_content_security": "NOT_EVALUATED",
                "excluded_source_maps": excluded, "runtime_api_binding": "UNAVAILABLE",
                "deployment": "BLOCKED", "provider_writes": False,
                "required_runtime_apis": ["/api/graphql", "/api/graphql/ws",
                                           "/api/a11oy/v1/atelier/ask"]}
    with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-source-sha", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args()
    try:
        manifest = stage_artifact(args.root, args.output, args.expected_source_sha)
    except (AdmissionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"canonical web admission failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"state": manifest["state"], "files": len(manifest["files"]),
                      "deployment": manifest["deployment"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
