#!/usr/bin/env bash
# =============================================================================
# check_weight_guard.test.sh — offline negative-fixture self-test for the
# GENERIC pinned-download weight guard (scripts/check_weight_guard.py).
#
# A guard that never fails when it should can rot into a no-op. This self-test
# builds throwaway fixtures and asserts the guard PASSES on an honest input and
# FAILS the moment the weight contract is broken in each way the guard is meant
# to catch:
#
#   assert-fail-closed (static Dockerfile check):
#     - honest fetch region                       -> PASS
#     - a best-effort `|| echo` mask reintroduced -> FAIL  (the original bug)
#     - a best-effort `|| true` mask reintroduced -> FAIL
#     - the `sys.exit(1)` fail-loud path dropped  -> FAIL
#     - the cache-cleanup line's own `|| true`    -> PASS  (correctly excluded)
#     - the fetch region cannot be located        -> FAIL
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
#     - the weight file is simply missing         -> FAIL
#
# The engine is GENERIC over a Dockerfile ARG prefix (`--arg-prefix`). To prove
# it is not silently hardcoded to the GGUF prefix, the whole suite runs TWICE:
# once with the default GGUF prefix (A11OY_ALLOY_GGUF — the existing guard's
# exact behavior) and once with an unrelated prefix (A11OY_ALLOY_ONNX — a
# stand-in for a future ONNX/tokenizer weight). A new download weight is thus a
# DECLARATIVE change (add pins + point a thin workflow at --arg-prefix), proven
# here, not a whole new copy of the guard.
#
# Everything here is network-free, so it runs the same in CI and locally.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/check_weight_guard.py"
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

# honest_dockerfile <path> <prefix> — a faithful minimal copy of the real fetch
# region for the weight identified by <prefix>: five pinned ARGs, an UNMASKED
# python heredoc fetch with a fail-loud `sys.exit(1)`, the legitimate `|| true`
# cache-cleanup line, and the closing `ENV <prefix>=` that bounds the region.
honest_dockerfile() {
  local path="$1" p="$2"
  cat > "$path" <<EOF
FROM python:3.12-slim
ARG ${p}_REPO=Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF
ARG ${p}_FILE=qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
ARG ${p}_REV=ebb2015119c907b064c512bf053e945850b5875f
ARG ${p}_SHA256=1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32
ARG ${p}_SIZE=491400064
ARG A11OY_REQUIRE_LOCAL_LLM=1
ENV A11OY_REQUIRE_LOCAL_LLM=\${A11OY_REQUIRE_LOCAL_LLM}
RUN python3 <<'WEIGHTPY'
import hashlib, os, sys
from huggingface_hub import hf_hub_download
p = hf_hub_download(repo_id=os.environ["${p}_REPO"],
                    filename=os.environ["${p}_FILE"],
                    revision=os.environ["${p}_REV"])
if not p or not os.path.exists(p):
    sys.stderr.write("FATAL: weight missing\n")
    sys.exit(1)
WEIGHTPY
RUN rm -rf /app/models/.cache /root/.cache/huggingface 2>/dev/null || true
ENV ${p}=/app/models/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
EOF
}

run_assert() { python3 "$GUARD" assert-fail-closed --dockerfile "$1" --arg-prefix "$2"; }
run_parse()  { python3 "$GUARD" parse --dockerfile "$1" --arg-prefix "$2"; }
run_verify() { python3 "$GUARD" verify --file "$1" --size "$2" --sha256 "$3"; }

# suite <prefix> — run the full assert/parse fixture battery for one ARG prefix.
suite() {
  local P="$1"
  local D="$TMP/$P"
  mkdir -p "$D"
  echo "--- prefix $P -------------------------------------------------------"

  # ----- assert-fail-closed ------------------------------------------------
  local HON="$D/Dockerfile.honest"; honest_dockerfile "$HON" "$P"
  expect_pass "[$P] assert: honest fetch region (unmasked + sys.exit(1), cache-cleanup '|| true' excluded)" \
    run_assert "$HON" "$P"

  # A `|| echo` mask reintroduced on the fetch — the original silent-degrade bug.
  local MASK_ECHO="$D/Dockerfile.mask_echo"; honest_dockerfile "$MASK_ECHO" "$P"
  sed -i "s#^ENV ${P}=/app/models#RUN python3 -c \"from huggingface_hub import hf_hub_download; hf_hub_download()\" || echo \"skip (best-effort)\"\n&#" "$MASK_ECHO"
  expect_fail "[$P] assert: '|| echo' mask reintroduced on the fetch" \
    run_assert "$MASK_ECHO" "$P"

  # A `|| true` mask reintroduced on the fetch (distinct from the cache-cleanup line).
  local MASK_TRUE="$D/Dockerfile.mask_true"; honest_dockerfile "$MASK_TRUE" "$P"
  sed -i "s#^ENV ${P}=/app/models#RUN python3 -m a11oy.fetch_weight || true\n&#" "$MASK_TRUE"
  expect_fail "[$P] assert: '|| true' mask reintroduced on the fetch" \
    run_assert "$MASK_TRUE" "$P"

  # The fail-loud `sys.exit(1)` path dropped.
  local NOEXIT="$D/Dockerfile.noexit"; honest_dockerfile "$NOEXIT" "$P"
  sed -i '/sys.exit(1)/d' "$NOEXIT"
  expect_fail "[$P] assert: 'sys.exit(1)' fail-loud path dropped" \
    run_assert "$NOEXIT" "$P"

  # Region cannot be located (pin block renamed/moved) -> fail closed.
  local NOREGION="$D/Dockerfile.noregion"
  printf 'FROM python:3.12-slim\nRUN echo hi\n' > "$NOREGION"
  expect_fail "[$P] assert: fetch region cannot be located" \
    run_assert "$NOREGION" "$P"

  # ----- parse (pin shape) -------------------------------------------------
  expect_pass "[$P] parse: honest five pinned ARGs" run_parse "$HON" "$P"

  # rev loosened to a branch/tag (not a 40-hex commit) — lets the weight move
  # under the digest, i.e. rev out of lockstep with size/sha.
  local REV_LOOSE="$D/Dockerfile.rev_loose"; honest_dockerfile "$REV_LOOSE" "$P"
  sed -i "s#${P}_REV=.*#${P}_REV=main#" "$REV_LOOSE"
  expect_fail "[$P] parse: rev loosened to a branch (not 40-hex commit)" \
    run_parse "$REV_LOOSE" "$P"

  # sha truncated by one character (not 64-hex).
  local SHA_SHORT="$D/Dockerfile.sha_short"; honest_dockerfile "$SHA_SHORT" "$P"
  sed -i "s#\(${P}_SHA256=[0-9a-f]\{63\}\)[0-9a-f]#\1#" "$SHA_SHORT"
  expect_fail "[$P] parse: sha256 truncated by one char (not 64-hex)" \
    run_parse "$SHA_SHORT" "$P"

  # size made non-integer.
  local SIZE_BAD="$D/Dockerfile.size_bad"; honest_dockerfile "$SIZE_BAD" "$P"
  sed -i "s#${P}_SIZE=.*#${P}_SIZE=491400064MB#" "$SIZE_BAD"
  expect_fail "[$P] parse: size made non-integer" \
    run_parse "$SIZE_BAD" "$P"

  # a pinned ARG removed entirely.
  local ARG_MISSING="$D/Dockerfile.arg_missing"; honest_dockerfile "$ARG_MISSING" "$P"
  sed -i "/${P}_SIZE=/d" "$ARG_MISSING"
  expect_fail "[$P] parse: a pinned ARG removed entirely" \
    run_parse "$ARG_MISSING" "$P"
}

# Run the full suite for the existing GGUF prefix AND an unrelated prefix, to
# prove the engine is genuinely generic (a new download weight = a few pins).
suite "A11OY_ALLOY_GGUF"
suite "A11OY_ALLOY_ONNX"

# =============================================================================
# verify (lockstep size + sha256) — prefix-independent, run once.
# =============================================================================
echo "--- verify (prefix-independent) -----------------------------------------"
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
echo "OK: the weight guard fails closed on every broken fixture (both prefixes)."
