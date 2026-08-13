#!/usr/bin/env python3
"""Fetch one immutable, digest-bound Hugging Face parity verifier."""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path
from typing import Any, Callable


PINNED_URL = (
    "https://raw.githubusercontent.com/szl-holdings/.github/"
    "0816263f1e83734658d6e5a8a7cd3834f36a2054/"
    ".github/scripts/hf_module_drift_check.py"
)
PINNED_SHA256 = "b463cdcb3f4790f1e01d5f5010f8c39d14a2980227baebfc3a4c93a6710a2099"
MAX_TOOL_BYTES = 100_000


class FetchError(RuntimeError):
    """Raised when immutable tool retrieval cannot be proved."""


def fetch_tool(
    output: Path,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise FetchError("output path must not already exist")
    request = urllib.request.Request(
        PINNED_URL,
        headers={"User-Agent": "szl-protected-hf-admission/1"},
    )
    try:
        with opener(request, timeout=30) as response:
            if getattr(response, "status", 200) != 200:
                raise FetchError(f"unexpected HTTP status: {response.status}")
            raw = response.read(MAX_TOOL_BYTES + 1)
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"immutable tool retrieval failed: {exc}") from exc
    if not raw or len(raw) > MAX_TOOL_BYTES:
        raise FetchError(f"immutable tool size is invalid: {len(raw)}")
    observed = hashlib.sha256(raw).hexdigest()
    if observed != PINNED_SHA256:
        raise FetchError(f"immutable tool digest mismatch: {observed}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as destination:
        destination.write(raw)
    return {"url": PINNED_URL, "sha256": observed, "bytes": len(raw)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = fetch_tool(args.output.resolve())
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
