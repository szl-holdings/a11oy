#!/usr/bin/env bash
# =============================================================================
# check_gguf_weight_guard.test.sh — offline negative-fixture self-test for the
# GGUF weight guard (scripts/check_gguf_weight_guard.py).
#
# A guard that never fails when it should can rot into a no-op. This self-test
# builds throwaway fixtures and asserts the guard PASSES on an honest input and
# FAILS the moment the GGUF weight contract is broken in each way the guard is
# meant to catch:
#
#   assert-fail-closed (static Dockerfile check):
#     - honest fetch region                       -> PASS
#     - a best-effort `|| echo` mask reintroduced -> FAIL  (the original bug)
#     - a best-effort `|| true` mask reintroduced -> FAIL
#     - the `sys.exit(1)` fail-loud path dropped  -> FAIL
#     - the cache-cleanup line's own `|| true`    -> PASS  (correctly excluded)
#
#   parse (pin shape — a malformed bump fails closed before a 25-min build):
#     - honest five ARGs                          -> PASS
#     - rev loosened to a branch/tag (not 40-hex) -> FAIL  (rev out of lockstep)
#     - sha truncated by one char (not 64-hex)    -> FAIL
#     - size made non-integer                     -> FAIL
#     - a pinned ARG removed entirely             -> FAIL
#
#   verify (the lockstep size+sha256 predicate the live download uses):
#     - correct size AND sha256                   -> PASS
#     - size bumped out of lockstep with the bytes-> FAIL
#     - sha256 bumped out of lockstep (one char)  -> FAIL
#
# Everything here is network-free, so it runs the same in CI and locally.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/check_gguf_weight_guard.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

expect_pass() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "[PASS] $desc (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $desc (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
    "$@" 2>&1 | sed 's/^/    /'
  fi
}

expect_fail() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "[FAIL] $desc (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $desc (failed as expected)"; PASS=$((PASS + 1))
  fi
}

# honest_dockerfile <path> — a faithful minimal copy of the real GGUF fetch
# region: five pinned ARGs, an UNMASKED python heredoc fetch with a fail-loud
# `sys.exit(1)`, the legitimate `|| true` cache-cleanup line, and the closing
# ENV that bounds the region.
honest_dockerfile() {
  cat > "$1" <<'EOF'
FROM python:3.12-slim
ARG A11OY_ALLOY_GGUF_REPO=Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF
ARG A11OY_ALLOY_GGUF_FILE=qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
ARG A11OY_ALLOY_GGUF_REV=ebb2015119c907b064c512bf053e945850b5875f
ARG A11OY_ALLOY_GGUF_SHA256=1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32
ARG A11OY_ALLOY_GGUF_SIZE=491400064
ARG A11OY_REQUIRE_LOCAL_LLM=1
ENV A11OY_REQUIRE_LOCAL_LLM=${A11OY_REQUIRE_LOCAL_LLM}
RUN python3 <<'GGUFPY'
import hashlib, os, sys
from huggingface_hub import hf_hub_download
p = hf_hub_download(repo_id=os.environ["A11OY_ALLOY_GGUF_REPO"],
                    filename=os.environ["A11OY_ALLOY_GGUF_FILE"],
                    revision=os.environ["A11OY_ALLOY_GGUF_REV"])
if not p or not os.path.exists(p):
    sys.stderr.write("FATAL: weight missing\n")
    sys.exit(1)
GGUFPY
RUN rm -rf /app/models/.cache /root/.cache/huggingface 2>/dev/null || true
ENV A11OY_ALLOY_GGUF=/app/models/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
EOF
}

run_assert() { python3 "$GUARD" assert-fail-closed --dockerfile "$1"; }
run_parse()  { python3 "$GUARD" parse --dockerfile "$1"; }
run_verify() { python3 "$GUARD" verify --file "$1" --size "$2" --sha256 "$3"; }

# =============================================================================
# assert-fail-closed
# =============================================================================
HON="$TMP/Dockerfile.honest"; honest_dockerfile "$HON"
expect_pass "assert-fail-closed: honest fetch region (unmasked + sys.exit(1), cache-cleanup '|| true' excluded)" \
  run_assert "$HON"

# A `|| echo` mask reintroduced on the fetch — the exact original silent-degrade bug.
MASK_ECHO="$TMP/Dockerfile.mask_echo"; honest_dockerfile "$MASK_ECHO"
# Insert a masked fetch line just before the closing ENV.
sed -i 's#^ENV A11OY_ALLOY_GGUF=/app/models#RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download()" || echo "skip (best-effort)"\n&#' "$MASK_ECHO"
expect_fail "assert-fail-closed: '|| echo' mask reintroduced on the fetch" \
  run_assert "$MASK_ECHO"

# A `|| true` mask reintroduced on the fetch (distinct from the cache-cleanup line).
MASK_TRUE="$TMP/Dockerfile.mask_true"; honest_dockerfile "$MASK_TRUE"
sed -i 's#^ENV A11OY_ALLOY_GGUF=/app/models#RUN python3 -m a11oy.fetch_weight || true\n&#' "$MASK_TRUE"
expect_fail "assert-fail-closed: '|| true' mask reintroduced on the fetch" \
  run_assert "$MASK_TRUE"

# The fail-loud `sys.exit(1)` path dropped.
NOEXIT="$TMP/Dockerfile.noexit"; honest_dockerfile "$NOEXIT"
sed -i '/sys.exit(1)/d' "$NOEXIT"
expect_fail "assert-fail-closed: 'sys.exit(1)' fail-loud path dropped" \
  run_assert "$NOEXIT"

# Region cannot be located (pin block renamed/moved) -> fail closed.
NOREGION="$TMP/Dockerfile.noregion"
printf 'FROM python:3.12-slim\nRUN echo hi\n' > "$NOREGION"
expect_fail "assert-fail-closed: GGUF fetch region cannot be located" \
  run_assert "$NOREGION"

# =============================================================================
# parse (pin shape)
# =============================================================================
expect_pass "parse: honest five pinned ARGs" run_parse "$HON"

# rev loosened to a branch/tag (not a 40-hex commit) — lets the weight move under
# the digest, i.e. rev out of lockstep with size/sha.
REV_LOOSE="$TMP/Dockerfile.rev_loose"; honest_dockerfile "$REV_LOOSE"
sed -i 's#A11OY_ALLOY_GGUF_REV=.*#A11OY_ALLOY_GGUF_REV=main#' "$REV_LOOSE"
expect_fail "parse: rev loosened to a branch (not 40-hex commit)" \
  run_parse "$REV_LOOSE"

# sha truncated by one character (not 64-hex).
SHA_SHORT="$TMP/Dockerfile.sha_short"; honest_dockerfile "$SHA_SHORT"
sed -i 's#\(A11OY_ALLOY_GGUF_SHA256=[0-9a-f]\{63\}\)[0-9a-f]#\1#' "$SHA_SHORT"
expect_fail "parse: sha256 truncated by one char (not 64-hex)" \
  run_parse "$SHA_SHORT"

# size made non-integer.
SIZE_BAD="$TMP/Dockerfile.size_bad"; honest_dockerfile "$SIZE_BAD"
sed -i 's#A11OY_ALLOY_GGUF_SIZE=.*#A11OY_ALLOY_GGUF_SIZE=491400064MB#' "$SIZE_BAD"
expect_fail "parse: size made non-integer" \
  run_parse "$SIZE_BAD"

# a pinned ARG removed entirely.
ARG_MISSING="$TMP/Dockerfile.arg_missing"; honest_dockerfile "$ARG_MISSING"
sed -i '/A11OY_ALLOY_GGUF_SIZE=/d' "$ARG_MISSING"
expect_fail "parse: a pinned ARG removed entirely" \
  run_parse "$ARG_MISSING"

# =============================================================================
# verify (lockstep size + sha256)
# =============================================================================
BLOB="$TMP/blob.bin"
head -c 4096 /dev/urandom > "$BLOB"
REAL_SIZE="$(wc -c < "$BLOB" | tr -d ' ')"
REAL_SHA="$(sha256sum "$BLOB" | awk '{print $1}')"

expect_pass "verify: correct size AND sha256" \
  run_verify "$BLOB" "$REAL_SIZE" "$REAL_SHA"

# size bumped out of lockstep with the actual bytes.
expect_fail "verify: size bumped out of lockstep with the bytes" \
  run_verify "$BLOB" "$((REAL_SIZE + 1))" "$REAL_SHA"

# sha256 bumped out of lockstep (flip the first hex nibble).
FIRST="${REAL_SHA:0:1}"
if [ "$FIRST" = "0" ]; then FLIP="1"; else FLIP="0"; fi
BAD_SHA="${FLIP}${REAL_SHA:1}"
expect_fail "verify: sha256 bumped out of lockstep (one char flipped)" \
  run_verify "$BLOB" "$REAL_SIZE" "$BAD_SHA"

# a referenced weight that is simply missing.
expect_fail "verify: weight file missing" \
  run_verify "$TMP/does-not-exist.gguf" "$REAL_SIZE" "$REAL_SHA"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
echo "OK: the GGUF weight guard fails closed on every broken fixture."
