#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# parse-llama-pin.sh — single source of truth for extracting the pinned
# llama-cpp-python version out of the root Dockerfile. The llama-cpp wheel guard
# (.github/workflows/llama-wheel-guard.yml) calls this instead of inlining the
# grep, so the parser the guard relies on is the EXACT same one the negative-
# fixture self-test (parse-llama-pin.test.sh) validates. Without a shared script,
# a reshape of the Dockerfile install line could quietly desynchronise the
# guard's inline grep from reality and silently neuter the wheel guard.
#
# Usage:  parse-llama-pin.sh [DOCKERFILE]   (defaults to ./Dockerfile)
# Prints: the bare pinned version (e.g. 0.3.19) to stdout on success.
# Exits:  non-zero with a GitHub-annotated ::error:: when no 'llama-cpp-python==
#         <ver>' pin can be found (install line missing or reshaped).
#
# Signed-off-by: Forge <forge@szlholdings.ai>
set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"

if [ ! -f "${DOCKERFILE}" ]; then
  echo "::error::parse-llama-pin: Dockerfile not found at '${DOCKERFILE}'." >&2
  exit 1
fi

# Match the pinned, version-equality install: llama-cpp-python==<ver>.
# This is the exact contract the wheel guard re-builds from source.
VER="$(grep -oE 'llama-cpp-python==[0-9][0-9.]*' "${DOCKERFILE}" | head -n1 | sed 's/.*==//')"

if [ -z "${VER}" ]; then
  echo "::error::Could not parse the pinned 'llama-cpp-python==<ver>' install from '${DOCKERFILE}'. If the install line moved or changed shape, update this parser (scripts/parse-llama-pin.sh) in lockstep with the Dockerfile." >&2
  exit 1
fi

printf '%s\n' "${VER}"
