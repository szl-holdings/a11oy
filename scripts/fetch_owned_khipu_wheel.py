#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fetch the one pinned CPU wheel without a remote Docker ADD source.

Build-only supply-chain helper. No model, training, credential or provider
mutation authority. Bytes reach the final wheel path only after size and
SHA-256 verification. The Dockerfile separately verifies glibc linkage.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

WHEEL = "llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
URL = "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/" + WHEEL
EXPECTED_SIZE = 23912624
EXPECTED_SHA256 = "d172f3d3c8cdd194c3c47c71cb077ed6e61354a2d0f939ceeac0c8fd29999596"
ALLOWED_HOSTS = frozenset({"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"})
MAX_SECONDS = 120.0
SOCKET_TIMEOUT = 20.0


def validate_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443)):
        raise ValueError("wheel transport requires an approved HTTPS release host")


class ReleaseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validate before urllib makes the redirected request, not afterward.
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_wheel(directory: Path = Path("/wheels")) -> Path:
    validate_url(URL)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / WHEEL
    temporary: Path | None = None
    started = time.monotonic()
    digest = hashlib.sha256()
    total = 0
    opener = urllib.request.build_opener(ReleaseRedirects())
    request = urllib.request.Request(URL, headers={"User-Agent": "SZL-Owned-Wheel-Build/1.0"})
    try:
        with opener.open(request, timeout=SOCKET_TIMEOUT) as response:
            validate_url(response.geturl())
            if response.status != 200:
                raise ValueError("wheel transport did not return HTTP 200")
            with tempfile.NamedTemporaryFile(prefix=".owned-wheel-", dir=directory, delete=False) as out:
                temporary = Path(out.name)
                while True:
                    if time.monotonic() - started > MAX_SECONDS:
                        raise TimeoutError("wheel transport exceeded its elapsed-time budget")
                    chunk = response.read(min(1024 * 1024, EXPECTED_SIZE - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > EXPECTED_SIZE:
                        raise ValueError("wheel exceeds its pinned byte size")
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
        if total != EXPECTED_SIZE:
            raise ValueError("wheel is truncated or has an unexpected byte size")
        if digest.hexdigest() != EXPECTED_SHA256:
            raise ValueError("wheel SHA-256 does not match the pinned release")
        os.replace(temporary, target)
        temporary = None
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    result = fetch_wheel()
    print(f"[a11oy] verified CPU wheel transport: {result.name} sha256={EXPECTED_SHA256} bytes={EXPECTED_SIZE}")
