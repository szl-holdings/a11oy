#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Install the checksum-pinned official Cedar executable without a global install."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import tarfile
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    lock = json.loads(
        (Path(__file__).resolve().parents[1] / "toolchain-lock.json").read_text()
    )
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("only checksum-pinned amd64 assets are supported")
    key = {"Windows": "windows_amd64", "Linux": "ci_linux_amd64"}.get(platform.system())
    if key is None:
        parser.error("no checksum-pinned Cedar asset for this platform")
    asset = lock["cedar"][key]
    with urllib.request.urlopen(asset["url"], timeout=60) as response:
        data = response.read(150 * 1024 * 1024 + 1)
    if hashlib.sha256(data).hexdigest() != asset["sha256"]:
        raise SystemExit("Cedar archive checksum mismatch; refusing installation")
    if key == "windows_amd64":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [
                item
                for item in archive.infolist()
                if not item.is_dir() and Path(item.filename).name == "cedar.exe"
            ]
            if len(entries) != 1:
                raise SystemExit(
                    "Cedar archive does not contain exactly one executable"
                )
            binary = archive.read(entries[0])
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as archive:
            entries = [
                item
                for item in archive.getmembers()
                if item.isfile() and Path(item.name).name == "cedar"
            ]
            if len(entries) != 1:
                raise SystemExit(
                    "Cedar archive does not contain exactly one executable"
                )
            binary = archive.extractfile(entries[0]).read()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".download")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    os.replace(temporary, output)
    print(
        json.dumps(
            {
                "path": str(output),
                "version": lock["cedar"]["version"],
                "archiveSha256": asset["sha256"],
                "binarySha256": hashlib.sha256(binary).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
