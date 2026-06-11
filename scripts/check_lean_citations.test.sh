#!/usr/bin/env bash
# =============================================================================
# check_lean_citations.test.sh — negative-fixture self-test for the Lean
# citation guard (scripts/check_lean_citations.py).
#
# Builds throwaway a11oy-shaped trees + offline existence fixtures and asserts
# the guard PASSES on honest trees and FAILS on a phantom real-proof citation.
# Runs fully offline via LEAN_CITATION_FIXTURE (no network). This is what keeps
# the guard from silently being neutered.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_lean_citations.py"

PASS=0
FAIL=0

run() {
  # $1 = root, $2 = fixture json path
  LEAN_CITATION_FIXTURE="$2" python3 "$GUARD" --root "$1" >/dev/null 2>&1
}

expect_pass() {
  local name="$1" root="$2" fix="$3"
  if run "$root" "$fix"; then
    echo "[PASS] $name (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $name (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
  fi
}

expect_fail() {
  local name="$1" root="$2" fix="$3"
  if run "$root" "$fix"; then
    echo "[FAIL] $name (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $name (failed as expected)"; PASS=$((PASS + 1))
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

make_root() {
  # $1 = root dir
  mkdir -p "$1/packages/policy/src/gates" "$1/docs"
}

write_gate_ts() {
  # $1 = path, $2 = lean_file, $3 = lean_commit
  cat > "$1" <<EOF
// test gate
const LEAN_FILE    = "$2";
const LEAN_COMMIT  = "$3";
export const x = 1;
EOF
}

# ---------------------------------------------------------------------------
# Fixture A: honest tree — a real citation that exists at its pinned commit.
# ---------------------------------------------------------------------------
A="$TMP/A"; make_root "$A"
cat > "$A/gates_manifest.json" <<'EOF'
[
  {"name":"good","file":"good_gate.ts","lean_file":"Lutar/DPI/DPIBound.lean","lean_commit_sha":"deadbeef","lean_status":"real"},
  {"name":"honest-phantom","file":"phantom_gate.ts","lean_file":"Lutar/Gate/NeverExisted.lean","lean_commit_sha":"deadbeef","lean_status":"phantom"}
]
EOF
write_gate_ts "$A/packages/policy/src/gates/good_gate.ts" "Lutar/DPI/DPIBound.lean" "deadbeef"
write_gate_ts "$A/packages/policy/src/gates/phantom_gate.ts" "Lutar/Gate/NeverExisted.lean" "deadbeef"
cat > "$A/fixture.json" <<'EOF'
{ "deadbeef:Lutar/DPI/DPIBound.lean": true,
  "main:Lutar/DPI/DPIBound.lean": true }
EOF
expect_pass "honest tree (real exists at pinned commit; phantom honestly marked)" "$A" "$A/fixture.json"

# ---------------------------------------------------------------------------
# Fixture B: phantom regression — a citation marked REAL whose file exists
# nowhere. The guard MUST fail.
# ---------------------------------------------------------------------------
B="$TMP/B"; make_root "$B"
cat > "$B/gates_manifest.json" <<'EOF'
[
  {"name":"bad","file":"bad_gate.ts","lean_file":"Lutar/Gate/BekensteinEntropyMeasure.lean","lean_commit_sha":"deadbeef","lean_status":"real"}
]
EOF
write_gate_ts "$B/packages/policy/src/gates/bad_gate.ts" "Lutar/Gate/BekensteinEntropyMeasure.lean" "deadbeef"
echo '{}' > "$B/fixture.json"   # nothing exists
expect_fail "phantom real citation (file exists nowhere)" "$B" "$B/fixture.json"

# ---------------------------------------------------------------------------
# Fixture C: stale pin — real file absent at pinned commit but present on the
# default branch. Honest-but-stale => PASS (with a warning), not a failure.
# ---------------------------------------------------------------------------
C="$TMP/C"; make_root "$C"
cat > "$C/gates_manifest.json" <<'EOF'
[
  {"name":"stale","file":"stale_gate.ts","lean_file":"Lutar/DP/GaussianMechanism.lean","lean_commit_sha":"oldsha","lean_status":"real"}
]
EOF
write_gate_ts "$C/packages/policy/src/gates/stale_gate.ts" "Lutar/DP/GaussianMechanism.lean" "oldsha"
cat > "$C/fixture.json" <<'EOF'
{ "main:Lutar/DP/GaussianMechanism.lean": true }
EOF
expect_pass "stale pin (exists on default branch, not pinned commit)" "$C" "$C/fixture.json"

# ---------------------------------------------------------------------------
# Fixture D: phantom introduced ONLY in a gate .ts that has no manifest entry.
# Must still be caught.
# ---------------------------------------------------------------------------
D="$TMP/D"; make_root "$D"
echo '[]' > "$D/gates_manifest.json"
write_gate_ts "$D/packages/policy/src/gates/orphan_gate.ts" "Lutar/Gate/Fabricated.lean" "deadbeef"
echo '{}' > "$D/fixture.json"
expect_fail "phantom in orphan gate .ts (no manifest entry)" "$D" "$D/fixture.json"

# ---------------------------------------------------------------------------
# Fixture E: theorem-runtime-manifest with a missing leanFile must NOT fail the
# build (report-only; lean status scoped separately there).
# ---------------------------------------------------------------------------
E="$TMP/E"; make_root "$E"
echo '[]' > "$E/gates_manifest.json"
cat > "$E/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-X","leanFile":"Lutar/Gate/GoneAway.lean","leanStatus":"theorem"}
] }
EOF
echo '{}' > "$E/fixture.json"
expect_pass "theorem-runtime-manifest missing leanFile is report-only" "$E" "$E/fixture.json"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
