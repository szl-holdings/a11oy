#!/usr/bin/env python3
"""Build or verify the A11oy operational payload tarball."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path


REPO_ROOT = Path.cwd()
DIST_DIR = REPO_ROOT / "dist" / "payload"
STAGE_DIR = DIST_DIR / "stage" / "a11oy-operational-payload"
ARCHIVE = DIST_DIR / "a11oy-operational-payload.tar.gz"
SHA256 = DIST_DIR / "a11oy-operational-payload.tar.gz.sha256"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: str, target: str) -> None:
    destination = STAGE_DIR / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / source, destination)


def copy_tree(source: str, target: str) -> None:
    destination = STAGE_DIR / target
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(REPO_ROOT / source, destination)


def collect_stage_files() -> list[Path]:
    return sorted(path for path in STAGE_DIR.rglob("*") if path.is_file())


def write_stage_manifest() -> None:
    files = []
    for path in collect_stage_files():
        rel = path.relative_to(STAGE_DIR).as_posix()
        if rel == "PAYLOAD-MANIFEST.json":
            continue
        files.append(
            {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    aggregate_input = "\n".join(
        f"{entry['path']}\0{entry['size']}\0{entry['sha256']}" for entry in files
    ).encode("utf-8")

    manifest = {
        "manifestVersion": 1,
        "name": "a11oy-operational-payload",
        "sourceRepository": "https://github.com/szl-holdings/a11oy",
        "fileCount": len(files),
        "aggregateSha256": hashlib.sha256(aggregate_input).hexdigest(),
        "files": files,
        "verification": {
            "doctrine": [
                "pnpm test:doctrine",
                "pnpm typecheck:doctrine",
                "pnpm build:doctrine",
                "pnpm ecosystem:audit",
                "pnpm ecosystem:os:audit",
            ],
            "payload": [
                "pnpm payload:verify",
                "pnpm payload:bundle:verify",
            ],
        },
    }

    (STAGE_DIR / "PAYLOAD-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def stage_payload() -> None:
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True)

    for source in [
        "README.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "LICENSE",
        "CITATION.cff",
        "package.json",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "tsconfig.base.json",
    ]:
        copy_file(source, source)

    if (REPO_ROOT / "NOTICE").exists():
        copy_file("NOTICE", "NOTICE")

    for source in [
        "docs/org-repo-map.md",
        "docs/ECOSYSTEM.md",
        "docs/PROVENANCE.md",
        "docs/SERIES_A_DILIGENCE.md",
        "docs/INVESTOR_DEMO.md",
        "docs/ECOSYSTEM_OPERATING_SYSTEM.md",
        "docs/AUTONOMOUS_LEARNING_DOCTRINE.md",
        "docs/benchmark-evolution-doctrine.md",
        "docs/ANCIENT_TEXTS_FORMULA_LINEAGE.md",
        "docs/UDS_FRONTIER_GAP_MAP.md",
        "docs/WARHACKER_UDS_PROOF_POINT.md",
        "docs/PERPLEXITY_BRIEF.md",
        "docs/ecosystem-registry.json",
        "docs/ecosystem-readiness-report.json",
        "docs/anatomy-formula-runtime-map.json",
        "docs/theorem-runtime-manifest.json",
        "docs/huggingface.md",
        "docs/regulatory_to_lambda.md",
        "benchmarks",
        ".github/workflows/doctrine.yml",
        ".github/workflows/huggingface.yml",
        "scripts",
        "deploy",
        "huggingface",
        "dist/huggingface/a11oy",
        "web/packages/a11oy-core/package.json",
        "web/packages/a11oy-core/tsconfig.json",
        "web/packages/a11oy-core/src",
        "web/packages/a11oy-core/dist",
        "web/packages/a11oy-connection/package.json",
        "web/packages/a11oy-connection/tsconfig.json",
        "web/packages/a11oy-connection/src",
        "web/packages/a11oy-connection/dist",
    ]:
        target = source
        if source == "dist/huggingface/a11oy":
            target = "publish/huggingface/a11oy"
        if (REPO_ROOT / source).is_dir():
            copy_tree(source, target)
        else:
            copy_file(source, target)

    write_stage_manifest()


def deterministic_tar() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in collect_stage_files():
                    rel = path.relative_to(STAGE_DIR.parent).as_posix()
                    data = path.read_bytes()
                    info = tarfile.TarInfo(rel)
                    info.size = len(data)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(data))

    digest = sha256_file(ARCHIVE)
    SHA256.write_text(f"{digest}  {ARCHIVE.name}\n", encoding="utf-8")


def verify_bundle() -> int:
    if not ARCHIVE.exists() or not SHA256.exists():
        print("Operational payload bundle is missing. Run: pnpm payload:bundle")
        return 1

    expected = SHA256.read_text(encoding="utf-8").split()[0]
    actual = sha256_file(ARCHIVE)
    if expected != actual:
        print(f"Bundle checksum mismatch: expected {expected}, got {actual}")
        return 1

    required = {
        "a11oy-operational-payload/PAYLOAD-MANIFEST.json",
        "a11oy-operational-payload/deploy/MANIFEST.json",
        "a11oy-operational-payload/publish/huggingface/a11oy/README.md",
        "a11oy-operational-payload/web/packages/a11oy-core/dist/index.js",
        "a11oy-operational-payload/web/packages/a11oy-connection/dist/index.js",
    }

    with tarfile.open(ARCHIVE, mode="r:gz") as tar:
        names = set(tar.getnames())
        missing = sorted(required - names)
        if missing:
            print("Bundle is missing required files:")
            for name in missing:
                print(f"  - {name}")
            return 1

    print(f"Verified operational payload bundle: {ARCHIVE.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        return verify_bundle()

    stage_payload()
    deterministic_tar()
    print(f"Built operational payload bundle: {ARCHIVE.relative_to(REPO_ROOT)}")
    print(f"Wrote checksum sidecar: {SHA256.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
