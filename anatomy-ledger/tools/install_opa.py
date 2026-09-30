#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Install only the checksum-pinned OPA asset for this host."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import urllib.request


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
        parser.error("no checksum-pinned OPA asset for this platform")
    asset = lock["opa"][key]
    with urllib.request.urlopen(asset["url"], timeout=60) as response:
        data = response.read(150 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != asset["sha256"]:
        raise SystemExit("OPA checksum mismatch; refusing installation")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".download")
    temporary.write_bytes(data)
    temporary.chmod(0o755)
    os.replace(temporary, output)
    print(
        json.dumps(
            {
                "path": str(output),
                "version": lock["opa"]["version"],
                "sha256": asset["sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
