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
# Fixture E: theorem-runtime-manifest with an UNDISCLOSED phantom theorem
# citation (leanStatus=theorem, not stagedAdvisory, file exists nowhere) MUST
# fail the build. This is the Task #695 class the guard now catches.
# ---------------------------------------------------------------------------
E="$TMP/E"; make_root "$E"
echo '[]' > "$E/gates_manifest.json"
cat > "$E/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-X","leanFile":"Lutar/Gate/GoneAway.lean","leanStatus":"theorem","stagedAdvisory":false}
] }
EOF
echo '{}' > "$E/fixture.json"
expect_fail "theorem-runtime-manifest undisclosed phantom theorem citation" "$E" "$E/fixture.json"

# ---------------------------------------------------------------------------
# Fixture F: same missing theorem leanFile but honestly disclosed
# (leanStatus=phantom) must PASS. Honest disclosure is the whole point.
# ---------------------------------------------------------------------------
F="$TMP/F"; make_root "$F"
echo '[]' > "$F/gates_manifest.json"
cat > "$F/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-X","leanFile":"Lutar/Gate/GoneAway.lean","leanStatus":"phantom"}
] }
EOF
echo '{}' > "$F/fixture.json"
expect_pass "theorem-runtime-manifest missing leanFile honestly marked phantom" "$F" "$F/fixture.json"

# ---------------------------------------------------------------------------
# Fixture G: theorem entry, missing file, but marked stagedAdvisory=true must
# PASS (explicitly disclosed as staged, not a real claim yet).
# ---------------------------------------------------------------------------
G="$TMP/G"; make_root "$G"
echo '[]' > "$G/gates_manifest.json"
cat > "$G/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"STAGED-Y","leanFile":"Lutar/Gate/NotYet.lean","leanStatus":"theorem","stagedAdvisory":true}
] }
EOF
echo '{}' > "$G/fixture.json"
expect_pass "theorem-runtime-manifest missing leanFile marked stagedAdvisory" "$G" "$G/fixture.json"

# ---------------------------------------------------------------------------
# Fixture H: theorem entry whose leanFile DOES exist on main must PASS.
# ---------------------------------------------------------------------------
H="$TMP/H"; make_root "$H"
echo '[]' > "$H/gates_manifest.json"
cat > "$H/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-Z","leanFile":"Lutar/Bound.lean","leanStatus":"theorem","stagedAdvisory":false}
] }
EOF
cat > "$H/fixture.json" <<'EOF'
{ "main:Lutar/Bound.lean": true }
EOF
expect_pass "theorem-runtime-manifest theorem citation that resolves on main" "$H" "$H/fixture.json"

# ---------------------------------------------------------------------------
# Fixture I: corpus/formulas mirror DRIFTED from its source manifest must FAIL.
# (gates_manifest.json stays a valid list so the ONLY failure is the drift.)
# ---------------------------------------------------------------------------
I="$TMP/I"; make_root "$I"; mkdir -p "$I/corpus/formulas"
printf '[]' > "$I/gates_manifest.json"
printf '[{"name":"x"}]' > "$I/corpus/formulas/a11oy__gates_manifest.json"
echo '{}' > "$I/fixture.json"
expect_fail "corpus mirror drifted from source manifest" "$I" "$I/fixture.json"

# ---------------------------------------------------------------------------
# Fixture J: corpus/formulas mirror MISSING while its source exists must FAIL.
# ---------------------------------------------------------------------------
J="$TMP/J"; make_root "$J"; mkdir -p "$J/corpus/formulas"
printf '[]' > "$J/gates_manifest.json"
echo '{}' > "$J/fixture.json"
expect_fail "corpus mirror missing while source exists" "$J" "$J/fixture.json"

# ---------------------------------------------------------------------------
# Fixture K: corpus/formulas mirrors byte-identical to sources must PASS.
# ---------------------------------------------------------------------------
K="$TMP/K"; make_root "$K"; mkdir -p "$K/corpus/formulas"
printf '[]' > "$K/gates_manifest.json"
printf '[]' > "$K/corpus/formulas/a11oy__gates_manifest.json"
printf '{ "entries": [] }' > "$K/docs/theorem-runtime-manifest.json"
cp "$K/docs/theorem-runtime-manifest.json" "$K/corpus/formulas/a11oy__docs__theorem-runtime-manifest.json"
echo '{}' > "$K/fixture.json"
expect_pass "corpus mirrors byte-identical to sources" "$K" "$K/fixture.json"

# ---------------------------------------------------------------------------
# Fixture L: theorem-runtime-manifest entry carrying a leanCommit pin whose file
# exists NOWHERE (not at the pin, not on main) must FAIL — commit-pinned entries
# are hard-fail-eligible with gates_manifest.json rigor.
# ---------------------------------------------------------------------------
L="$TMP/L"; make_root "$L"
echo '[]' > "$L/gates_manifest.json"
cat > "$L/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-P","leanFile":"Lutar/Gate/PinnedGone.lean","leanStatus":"theorem","leanCommit":"pinsha"}
] }
EOF
echo '{}' > "$L/fixture.json"
expect_fail "theorem-runtime-manifest pinned citation absent everywhere" "$L" "$L/fixture.json"

# ---------------------------------------------------------------------------
# Fixture M: pinned entry absent at the pin but present on main = stale pin =>
# PASS (warning only), mirroring gates_manifest.json stale-pin behavior.
# ---------------------------------------------------------------------------
M="$TMP/M"; make_root "$M"
echo '[]' > "$M/gates_manifest.json"
cat > "$M/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-Q","leanFile":"Lutar/Bound.lean","leanStatus":"theorem","leanCommit":"oldsha"}
] }
EOF
cat > "$M/fixture.json" <<'EOF'
{ "main:Lutar/Bound.lean": true }
EOF
expect_pass "theorem-runtime-manifest pinned but stale (present on main)" "$M" "$M/fixture.json"

# ---------------------------------------------------------------------------
# Fixture N: pinned entry present at its pinned commit => PASS.
# ---------------------------------------------------------------------------
N="$TMP/N"; make_root "$N"
echo '[]' > "$N/gates_manifest.json"
cat > "$N/docs/theorem-runtime-manifest.json" <<'EOF'
{ "entries": [
  {"id":"RUNTIME-R","leanFile":"Lutar/Bound.lean","leanStatus":"theorem","leanCommit":"goodsha"}
] }
EOF
cat > "$N/fixture.json" <<'EOF'
{ "goodsha:Lutar/Bound.lean": true }
EOF
expect_pass "theorem-runtime-manifest pinned citation present at pin" "$N" "$N/fixture.json"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
