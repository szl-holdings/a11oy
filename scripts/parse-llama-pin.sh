#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# parse-llama-pin.sh — single source of truth for extracting the exact
# llama-cpp-python version from the root Dockerfile. The supported contracts are:
#   1. a literal source/install pin: llama-cpp-python==<version>; or
#   2. a literal official wheel asset: llama_cpp_python-<version>-...whl.
#
# Repeated references to the same wheel are allowed. Missing, indirect, ranged,
# malformed, or conflicting versions fail closed.
#
# Usage:  parse-llama-pin.sh [DOCKERFILE]   (defaults to ./Dockerfile)
# Prints: the one bare pinned version (for example 0.3.35) on success.
#
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"

if [ ! -f "${DOCKERFILE}" ]; then
  echo "::error::parse-llama-pin: Dockerfile not found at '${DOCKERFILE}'." >&2
  exit 1
fi

python3 - "${DOCKERFILE}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    text = path.read_text(encoding="utf-8")
except (OSError, UnicodeError) as exc:
    print(
        f"::error::parse-llama-pin: could not read '{path}': {type(exc).__name__}",
        file=sys.stderr,
    )
    raise SystemExit(1)

version = r"[0-9]+(?:[.][0-9]+){1,2}"
source_versions = set(
    re.findall(rf"llama-cpp-python==({version})(?![0-9A-Za-z.+-])", text)
)
wheel_versions = set(
    re.findall(
        rf"llama_cpp_python-({version})-py3-none-manylinux2014_x86_64[.]manylinux_2_17_x86_64[.]whl",
        text,
    )
)
versions = source_versions | wheel_versions

if len(versions) != 1:
    detail = ",".join(sorted(versions)) if versions else "none"
    print(
        "::error::parse-llama-pin: expected exactly one literal exact "
        f"llama-cpp-python version in '{path}', found {detail}. "
        "Update the Dockerfile and parser tests in lockstep.",
        file=sys.stderr,
    )
    raise SystemExit(1)

print(next(iter(versions)))
PY
