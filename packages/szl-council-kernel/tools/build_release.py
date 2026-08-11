#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

FIXED = (2026, 8, 3, 12, 0, 0)
FIXED_ISO = "2026-08-03T12:00:00Z"
SKIP_DIRS = {
    ".git",
    ".venv",
    ".tox",
    ".eggs",
    "build",
    "dist",
    "dist-repeat",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "run",
    "runtime",
}
SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".sqlite3",
    ".sqlite",
    ".db",
    ".wal",
    ".shm",
    ".key",
    ".pem",
}


def _safe_relative(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    posix = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or posix.is_absolute()
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise ValueError(f"unsafe release path: {relative!r}")
    return relative


def _normalized_mode(path: Path) -> int:
    """Normalize modes so archive bytes do not depend on the invoking umask."""
    return 0o755 if stat.S_IMODE(path.stat().st_mode) & 0o111 else 0o644


def _is_generated_or_private(relative_parts: tuple[str, ...], suffix: str) -> bool:
    return (
        bool(set(relative_parts) & SKIP_DIRS)
        or any(part.endswith(".egg-info") for part in relative_parts)
        or suffix.lower() in SKIP_SUFFIXES
    )


def files(root: Path, *, exclusions: Iterable[Path] = ()):
    excluded = {path.resolve(strict=False) for path in exclusions}
    for path in sorted(root.rglob("*")):
        relative_parts = path.relative_to(root).parts
        if _is_generated_or_private(relative_parts, path.suffix):
            continue
        # Reject links before resolving them. Otherwise a link to an excluded
        # output could be silently accepted as an exclusion.
        if path.is_symlink():
            raise ValueError(f"symbolic links are forbidden in release input: {path}")
        if not path.is_file():
            continue
        if path.resolve(strict=False) in excluded:
            continue
        if path.name == "MANIFEST.sha256":
            continue
        yield path


def _verify_archive(path: Path, expected: dict[str, bytes]) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"zip integrity failed at {bad}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("zip contains duplicate member names")
        if set(names) != set(expected):
            missing = sorted(set(expected) - set(names))
            extra = sorted(set(names) - set(expected))
            raise RuntimeError(f"zip inventory mismatch; missing={missing}, extra={extra}")
        for name, data in expected.items():
            if archive.read(name) != data:
                raise RuntimeError(f"zip readback mismatch: {name}")
        manifest_text = archive.read("MANIFEST.sha256").decode("utf-8")
        listed: dict[str, str] = {}
        for line_number, line in enumerate(manifest_text.splitlines(), 1):
            if "  " not in line:
                raise RuntimeError(f"malformed manifest line {line_number}")
            digest, name = line.split("  ", 1)
            if name in listed:
                raise RuntimeError(f"duplicate manifest path: {name}")
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise RuntimeError(f"invalid manifest digest at line {line_number}")
            listed[name] = digest
        payload_names = set(expected) - {"MANIFEST.sha256"}
        if set(listed) != payload_names:
            raise RuntimeError("manifest inventory does not match payload inventory")
        for name in payload_names:
            actual = hashlib.sha256(expected[name]).hexdigest()
            if listed[name] != actual:
                raise RuntimeError(f"manifest digest mismatch: {name}")
    return {
        "zip_test": True,
        "inventory_readback": True,
        "payload_digest_readback": True,
        "duplicate_member_count": 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a deterministic, manifest-bound source archive")
    ap.add_argument("root", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    root = args.root.resolve()
    output = args.output.resolve()
    report_path = args.report.resolve() if args.report else None
    if not root.is_dir() or root.is_symlink():
        raise SystemExit("release root must be a real directory")

    exclusions = [output]
    if report_path is not None:
        exclusions.append(report_path)

    entries: list[tuple[str, bytes, int]] = []
    for path in files(root, exclusions=exclusions):
        rel = _safe_relative(root, path)
        data = path.read_bytes()
        entries.append((rel, data, _normalized_mode(path)))

    manifest = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {rel}\n" for rel, data, _ in entries
    ).encode("utf-8")
    entries.append(("MANIFEST.sha256", manifest, 0o644))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for rel, data, mode in sorted(entries):
                info = zipfile.ZipInfo(rel, FIXED)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = ((stat.S_IFREG | mode) & 0xFFFF) << 16
                info.create_system = 3
                info.flag_bits |= 0x800  # UTF-8 names.
                archive.writestr(info, data)
        expected = {rel: data for rel, data, _ in entries}
        readback = _verify_archive(temporary, expected)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)

    raw = output.read_bytes()
    report = {
        "schema": "szl.deterministic-release-zip/v3",
        "status": "PASS",
        "zip": output.name,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "file_count": len(entries),
        "payload_file_count": len(entries) - 1,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "fixed_timestamp": FIXED_ISO,
        "normalized_modes": True,
        "unsafe_path_count": 0,
        "symlink_count": 0,
        "private_key_suffixes_excluded": True,
        "database_suffixes_excluded": True,
        "egg_info_excluded": True,
        **readback,
    }
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
