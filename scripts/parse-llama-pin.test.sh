#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Negative-fixture contract for scripts/parse-llama-pin.sh. It proves the
# parser accepts one literal exact source pin or one literal official manylinux
# wheel version, accepts repeated references to the same wheel, and fails closed
# on absent, ranged, indirect, malformed, or conflicting versions.
#
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
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
    echo "SELF-TEST FAIL: parser should PASS on $3 but it exited non-zero" >&2
    exit 1
  fi
  if [ "$out" != "$2" ]; then
    echo "SELF-TEST FAIL: parser extracted '$out' from $3, expected '$2'" >&2
    exit 1
  fi
  echo "ok: parser extracts '$2' from $3"
}

expect_fail() { # <file> <label>
  if bash "$PARSER" "$1" >/dev/null 2>&1; then
    echo "SELF-TEST FAIL: parser should FAIL on $2 but it passed" >&2
    exit 1
  fi
  echo "ok: parser FAILS loudly on $2"
}

cat > "$TMP/source-good.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install --no-cache-dir --no-binary llama-cpp-python \
    "llama-cpp-python==0.3.19"
EOF
expect_version "$TMP/source-good.Dockerfile" "0.3.19" "literal source-install fixture"

cat > "$TMP/wheel-good.Dockerfile" <<'EOF'
FROM python:3.12-slim
ADD --checksum=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl \
    /wheels/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
EOF
expect_version "$TMP/wheel-good.Dockerfile" "0.3.35" "official manylinux wheel fixture"

cat > "$TMP/wheel-repeated.Dockerfile" <<'EOF'
FROM python:3.12-slim
ARG LLAMA_CPP_WHEEL=llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
ADD --checksum=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl \
    /wheels/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
RUN test -f /wheels/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
EOF
expect_version "$TMP/wheel-repeated.Dockerfile" "0.3.35" "repeated identical wheel references"

cat > "$TMP/no-pin.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install requests numpy
EOF
expect_fail "$TMP/no-pin.Dockerfile" "no-pin fixture"

cat > "$TMP/unpinned.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install llama-cpp-python
EOF
expect_fail "$TMP/unpinned.Dockerfile" "unpinned source install"

cat > "$TMP/range.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install "llama-cpp-python>=0.3.19,<0.4"
EOF
expect_fail "$TMP/range.Dockerfile" "range pin"

cat > "$TMP/indirect.Dockerfile" <<'EOF'
FROM python:3.12-slim
ARG LLAMA_PIN=0.3.35
RUN pip install "llama-cpp-python==${LLAMA_PIN}"
EOF
expect_fail "$TMP/indirect.Dockerfile" "indirect source pin"

cat > "$TMP/conflicting.Dockerfile" <<'EOF'
FROM python:3.12-slim
RUN pip install "llama-cpp-python==0.3.19"
ADD --checksum=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl \
    /wheels/llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
EOF
expect_fail "$TMP/conflicting.Dockerfile" "conflicting source and wheel versions"

cat > "$TMP/malformed-wheel.Dockerfile" <<'EOF'
FROM python:3.12-slim
ADD --checksum=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/llama_cpp_python-0.3.35-cp312-cp312-linux_x86_64.whl \
    /wheels/llama_cpp_python-0.3.35-cp312-cp312-linux_x86_64.whl
EOF
expect_fail "$TMP/malformed-wheel.Dockerfile" "unsupported wheel shape"

expect_fail "$TMP/does-not-exist.Dockerfile" "missing file"

real_ver="$(bash "$PARSER" "$DOCKERFILE")"
if ! printf '%s' "$real_ver" | grep -qE '^[0-9]+\.[0-9]+(\.[0-9]+)?$'; then
  echo "SELF-TEST FAIL: parser returned '$real_ver' from the real Dockerfile" >&2
  exit 1
fi
echo "ok: parser extracts exact real-Dockerfile pin '$real_ver'"

echo "All parse-llama-pin self-tests passed."
