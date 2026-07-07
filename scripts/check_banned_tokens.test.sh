#!/usr/bin/env bash
# =============================================================================
# check_banned_tokens.test.sh — negative-fixture self-test for the robust
# Doctrine v7 §1 banned-token scanner (scripts/check_banned_tokens.py).
#
# Proves the gate:
#   * STILL catches genuine SZL-authored marketing prose (positive control),
#   * does NOT red-gate verbatim third-party / harvested corpus text that is
#     allowlisted (the exact failure mode that red-gated the org),
#   * is not fooled by line-WRAPS, allowlist ORDERING, regex-special chars in
#     allowlist paths, or Tailwind `leading-*` utility classes.
#
# This self-test is what keeps the gate from being silently neutered or from
# silently over-firing again.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_banned_tokens.py"

PASS=0
FAIL=0

run() { python3 "$GUARD" --root "$1" --allowlist "$1/.doctrine-allowlist" >/dev/null 2>&1; }

expect_pass() {
  if run "$2"; then echo "[PASS] $1 (exit 0 as expected)"; PASS=$((PASS+1));
  else echo "[FAIL] $1 (expected exit 0, got non-zero)"; FAIL=$((FAIL+1)); fi
}
expect_fail() {
  if run "$2"; then echo "[FAIL] $1 (expected non-zero, got exit 0)"; FAIL=$((FAIL+1));
  else echo "[PASS] $1 (failed as expected)"; PASS=$((PASS+1)); fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Fixture A: clean tree, no banned tokens --------------------------------
A="$TMP/clean"; mkdir -p "$A"
: > "$A/.doctrine-allowlist"
echo "This page renders an honest verification receipt." > "$A/ok.md"
echo '<div class="leading-tight leading-6">honest</div>' > "$A/tailwind.html"
expect_pass "clean tree (no hits, Tailwind leading-* ignored)" "$A"

# --- Fixture B: genuine marketing prose MUST fail (positive control) --------
B="$TMP/marketing"; mkdir -p "$B"
: > "$B/.doctrine-allowlist"
echo "Our revolutionary, world-class platform is truly seamless." > "$B/hype.md"
expect_fail "genuine marketing prose is caught" "$B"

# --- Fixture C: harvested third-party corpus, ALLOWLISTED → must pass -------
# Reproduces the real failure: brain/harvest/*.jsonl carries verbatim GitHub
# repo descriptions ("seamless", "state-of-the-art", "breakthrough", repo names
# containing JARVIS) with real source URLs. Allowlisting the dir must green it.
C="$TMP/harvest"; mkdir -p "$C/brain/harvest"
echo "brain/harvest/" > "$C/.doctrine-allowlist"
cat > "$C/brain/harvest/energy_defense.jsonl" <<'JSONL'
{"kind":"repo","label":"crewAIInc/crewAI","url":"https://github.com/crewAIInc/crewAI","desc":"empowers agents to work together seamlessly, tackling complex tasks."}
{"kind":"repo","label":"NVIDIA/TensorRT-LLM","url":"https://github.com/NVIDIA/TensorRT-LLM","desc":"state-of-the-art optimizations to perform inference efficiently"}
{"kind":"repo","label":"aimagelab/JARVIS","url":"https://github.com/aimagelab/JARVIS","desc":"a breakthrough attention algorithm"}
JSONL
expect_pass "harvested third-party corpus (allowlisted dir) does not red-gate" "$C"

# --- Fixture D: same harvested corpus but NOT allowlisted → must fail --------
# (Proves the exemption is doing the work, not a blanket skip.)
D="$TMP/harvest_noallow"; mkdir -p "$D/brain/harvest"
: > "$D/.doctrine-allowlist"
cp "$C/brain/harvest/energy_defense.jsonl" "$D/brain/harvest/energy_defense.jsonl"
expect_fail "un-allowlisted third-party corpus is still caught (gate not weakened)" "$D"

# --- Fixture E: line-WRAP must not hide a marketing token -------------------
# A banned token on its own physical line is still caught (line-based scanning
# is per-line; wrapping does not smuggle a token past the gate).
E="$TMP/wrap"; mkdir -p "$E"
: > "$E/.doctrine-allowlist"
printf 'This product is\nunprecedented in scope.\n' > "$E/wrap.md"
expect_fail "line-wrapped marketing token is still caught" "$E"

# --- Fixture F: allowlist ORDERING + regex-special chars are robust ---------
# Path with a dot; an unrelated entry listed FIRST must not shadow it, and the
# '.' must be treated literally (old grep prefix match treated it as a wildcard).
F="$TMP/order"; mkdir -p "$F/a.b"
printf 'z/unrelated\na.b/\n' > "$F/.doctrine-allowlist"   # unrelated entry first
echo '{"desc":"a seamless, state-of-the-art breakthrough"}' > "$F/a.b/data.jsonl"
echo "This is a game-changing claim." > "$F/hype.md"        # NOT allowlisted
# a.b/ is exempt (must not fire), hype.md must still fire → overall FAIL:
expect_fail "ordering-robust: exempt dir honoured, non-exempt still caught" "$F"
# And a version where the ONLY hit is inside the exempt dir → PASS:
G="$TMP/order_ok"; mkdir -p "$G/a.b"
printf 'z/unrelated\na.b/\n' > "$G/.doctrine-allowlist"
echo '{"desc":"a seamless, state-of-the-art breakthrough"}' > "$G/a.b/data.jsonl"
: > "$G/clean.md"
expect_pass "regex-dot in allowlist path treated literally (a.b/ exempt)" "$G"

# --- Fixture H: exact-file allowlist entry (no trailing slash) --------------
H="$TMP/exactfile"; mkdir -p "$H"
echo "wayra_snapshot.json" > "$H/.doctrine-allowlist"
echo '{"abstract":"a seamless breakthrough with unprecedented results"}' > "$H/wayra_snapshot.json"
: > "$H/clean.md"
expect_pass "exact-file allowlist entry exempts just that file" "$H"

echo "-----------------------------------------------------------------------"
echo "banned-token guard self-test: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ] || exit 1
