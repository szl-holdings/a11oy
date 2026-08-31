#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# parse-llama-pin.test.sh — negative-fixture self-test for parse-llama-pin.sh,
# the parser the llama-cpp wheel guard depends on. Proves the parser (a)
# extracts the right version from a representative known-good Dockerfile, (b)
# fails LOUDLY (non-zero) on known-bad fixtures where the pin is absent or
# reshaped, and (c) still extracts a plausible pin from the REAL root Dockerfile.
#
# Why this exists: the wheel guard re-builds the pinned llama-cpp-python version
# parsed from the Dockerfile. If a refactor reshapes/moves the install line, the
# parser would return empty and the guard step would error — but nothing checks
# the parser still matches the Dockerfile's actual shape, so a refactor could
# quietly disable the protection. This self-test (mirroring the box watch-alarm
# guards' negative-fixture convention) turns that silent breakage into a RED CI
# failure.
#
# Signed-off-by: Forge <forge@szlholdings.ai>
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PARSER="$HERE/parse-llama-pin.sh"
DOCKERFILE="$ROOT/Dockerfile"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

[ -f "$PARSER" ] || { echo "SELF-TEST FAIL: cannot find $PARSER" >&2; exit 1; }
[ -f "$DOCKERFILE" ] || { echo "SELF-TEST FAIL: cannot find $DOCKERFILE" >&2; exit 1; }

expect_version() { # <file> <expected-version> <label>
  local out
  if ! out="$(bash "$PARSER" "$1" 2>/dev/null)"; then
    echo "SELF-TEST FAIL: parser should PASS on $3 but it exited non-zero" >&2; exit 1
  fi
  if [ "$out" != "$2" ]; then
    echo "SELF-TEST FAIL: parser extracted '$out' from $3, expected '$2'" >&2; exit 1
  fi
  echo "ok: parser extracts '$2' from $3"
}

expect_fail() { # <file> <label>
  if bash "$PARSER" "$1" >/dev/null 2>&1; then
    echo "SELF-TEST FAIL: parser should FAIL (exit non-zero) on $2 but it passed" >&2; exit 1
  fi
  echo "ok: parser FAILS loudly on $2"
}

# --- Known-GOOD fixture: representative of the real Dockerfile install line. ---
cat > "$TMP/good.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build; \
    CMAKE_ARGS="-DGGML_NATIVE=OFF" pip install --no-cache-dir --no-binary llama-cpp-python "llama-cpp-python==0.3.19"; \
    rm -rf /var/lib/apt/lists/*
EOF
expect_version "$TMP/good.Dockerfile" "0.3.19" "known-good fixture"

# A different pinned version must be extracted verbatim (not hard-coded).
cat > "$TMP/good2.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install --no-binary llama-cpp-python "llama-cpp-python==0.4.1"
EOF
expect_version "$TMP/good2.Dockerfile" "0.4.1" "alternate-version fixture"

# --- Known-BAD fixtures: the pin is absent or reshaped to a non-== form. ---

# 1) Pin removed entirely (package no longer pinned at all).
cat > "$TMP/no-pin.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install --no-cache-dir requests numpy
EOF
expect_fail "$TMP/no-pin.Dockerfile" "no-pin fixture (package absent)"

# 2) Unpinned install (no version-equality) — guard cannot know what to rebuild.
cat > "$TMP/unpinned.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install --no-binary llama-cpp-python llama-cpp-python
EOF
expect_fail "$TMP/unpinned.Dockerfile" "unpinned fixture (no ==<ver>)"

# 3) Reshaped to a range/compatible pin instead of exact ==.
cat > "$TMP/range.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install "llama-cpp-python>=0.3.19,<0.4"
EOF
expect_fail "$TMP/range.Dockerfile" "range-pin fixture (>= instead of ==)"

# 4) Pin moved into a requirements var with a non-version token after ==.
cat > "$TMP/var.Dockerfile" <<'EOF'
FROM python:3.12-slim
ARG LLAMA_PIN=latest
RUN pip install "llama-cpp-python==${LLAMA_PIN}"
EOF
expect_fail "$TMP/var.Dockerfile" "indirected-pin fixture (==\${VAR})"

# 5) Missing Dockerfile path must also fail loudly (not silently pass).
expect_fail "$TMP/does-not-exist.Dockerfile" "missing-file fixture"

# --- The REAL root Dockerfile must yield a plausible semver pin. ---
real_ver="$(bash "$PARSER" "$DOCKERFILE")"
if ! printf '%s' "$real_ver" | grep -qE '^[0-9]+\.[0-9]+(\.[0-9]+)?$'; then
  echo "SELF-TEST FAIL: parser returned '$real_ver' from the real Dockerfile, which is not a plausible version. The install line may have been reshaped — update scripts/parse-llama-pin.sh in lockstep." >&2
  exit 1
fi
echo "ok: parser extracts a plausible pin ('$real_ver') from the real root Dockerfile"

echo "All parse-llama-pin self-tests passed."
