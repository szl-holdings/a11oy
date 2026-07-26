#!/usr/bin/env bash
# =============================================================================
# check_putnam_drift.test.sh — negative-fixture self-test for the Putnam 2025
# drift guard (scripts/check_putnam_drift.py).
#
# Builds throwaway a11oy-shaped trees (szl_putnam.py loader + pages/console.html
# fallback) alongside an offline canonical Lutar/Putnam fixture, and asserts the
# guard PASSES on an honest tree and FAILS on every drift it is meant to catch:
# per-problem label drift, console-vs-loader divergence, count-phrase drift, a
# missing canonical problem file, named "X and Y are OPEN" prose drift, SZL
# REAL-count drift, REAL-source sorry/axiom violations, duplicate generated
# markers, an out-of-policy kernel axiom report, multiline theorem headers,
# section-vs-namespace scope handling, balanced nested attributes, and private
# helper handling, plus named instance proof auditing. Runs fully offline via
# PUTNAM_DRIFT_FIXTURE (no network).
# This is what keeps the guard from silently being neutered.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_putnam_drift.py"

PASS=0
FAIL=0

run() {
  # $1 = a11oy root (its ./canon is the offline canonical fixture)
  PYTHONDONTWRITEBYTECODE=1 PUTNAM_DRIFT_FIXTURE="$1/canon" \
    python3 "$GUARD" --root "$1" >/dev/null 2>&1
}

expect_pass() {
  local name="$1" root="$2"
  if run "$root"; then
    echo "[PASS] $name (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $name (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
  fi
}

expect_fail() {
  local name="$1" root="$2"
  if run "$root"; then
    echo "[FAIL] $name (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $name (failed as expected)"; PASS=$((PASS + 1))
  fi
}

expect_fail_report() {
  local name="$1" root="$2" report="$3"
  if PUTNAM_DRIFT_FIXTURE="$root/canon" python3 "$GUARD" --root "$root" \
      --axiom-report "$report" >/dev/null 2>&1; then
    echo "[FAIL] $name (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $name (failed as expected)"; PASS=$((PASS + 1))
  fi
}

expect_pass_report() {
  local name="$1" root="$2" report="$3"
  if PUTNAM_DRIFT_FIXTURE="$root/canon" python3 "$GUARD" --root "$root" \
      --axiom-report "$report" >/dev/null 2>&1; then
    echo "[PASS] $name (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $name (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------------------
# make_honest <root> — an internally consistent, honest a11oy tree.
# Canonical mini-set: A1 DEMO, A2 OPEN, A3 OPEN (0 REAL / 1 DEMO / 2 OPEN),
# plus one SZL original (REAL). Loader + console fallback both match it.
# ---------------------------------------------------------------------------
make_honest() {
  local r="$1"
  mkdir -p "$r/pages" "$r/canon/SZL" "$r/docs"

  cat > "$r/szl_putnam.py" <<'PY'
"""szl_putnam test loader. Honest tally: 0 REAL / 1 DEMO / 2 OPEN.
A2 and A3 are OPEN. The SZL originals are 3 REAL ... well, 1 here."""
from typing import Any, Dict, List

_PUTNAM: List[Dict[str, str]] = [
    {"id": "A1", "file": "P_A1.lean", "title": "A1", "status": "DEMO", "note": "x"},
    {"id": "A2", "file": "P_A2.lean", "title": "A2", "status": "OPEN", "note": "x"},
    {"id": "A3", "file": "P_A3.lean", "title": "A3", "status": "OPEN", "note": "x"},
]
_SZL: List[Dict[str, Any]] = [
    {"id": "SZL-One", "file": "SZL/One.lean", "title": "One", "status": "REAL", "note": "x"},
]


def _putnam_block() -> Dict[str, Any]:
    real = sum(1 for p in _PUTNAM if p["status"] == "REAL")
    demo = sum(1 for p in _PUTNAM if p["status"] == "DEMO")
    open_ = sum(1 for p in _PUTNAM if p["status"] == "OPEN")
    return {"count": len(_PUTNAM), "real": real, "demo": demo, "open": open_}


def _szl_block() -> Dict[str, Any]:
    return {"count": len(_SZL), "real": sum(1 for s in _SZL if s["status"] == "REAL")}
PY

  cat > "$r/pages/console.html" <<'HTML'
<script>
// putnam-2025-tab-patch fallback
var FB_PROBS=[
 ['A1','P_A1.lean','DEMO','faithful statement; proof deferred'],
 ['A2','P_A2.lean','OPEN','corrected answer; main proof deferred'],
 ['A3','P_A3.lean','OPEN','corrected answer; main proof deferred']
];
var FB_SZL=[
 ['SZL-One','SZL/One.lean','REAL','kernel-clean original']
];
// headline: Putnam 2025 is 0 REAL / 1 DEMO / 2 OPEN. <b>A2</b> and <b>A3</b> are OPEN.
</script>
HTML

  printf '%s\n' '/-- Putnam A1. -/' '-- **Honest status: DEMO**' > "$r/canon/P_A1.lean"
  printf '%s\n' '/-- Putnam A2. -/' '-- **Honest status: OPEN**' > "$r/canon/P_A2.lean"
  printf '%s\n' '/-- Putnam A3. -/' '-- **Honest status: OPEN**' > "$r/canon/P_A3.lean"
  cat > "$r/canon/SZL/One.lean" <<'LEAN'
namespace Lutar.Putnam.SZL.One
/-! SZL original. All proofs are REAL (kernel-checked); no `sorry`. -/
theorem proof : True := by trivial
end Lutar.Putnam.SZL.One
LEAN
  cat > "$r/docs/SERIES_A_DILIGENCE.md" <<'MD'
# Fixture diligence packet

| Area | Investor-safe wording |
| --- | --- |
<!-- BEGIN GENERATED PUTNAM STATUS -->
placeholder
<!-- END GENERATED PUTNAM STATUS -->
MD
  PYTHONDONTWRITEBYTECODE=1 PUTNAM_DRIFT_FIXTURE="$r/canon" \
    python3 "$GUARD" --root "$r" \
    --write-diligence >/dev/null
}

# --- Fixture A: honest tree -> PASS ----------------------------------------
A="$TMP/A"; make_honest "$A"
expect_pass "honest tree (loader == console == canonical 0/1/2, 1 SZL REAL)" "$A"

# --- Fixture B: loader per-problem label drift -> FAIL ---------------------
B="$TMP/B"; make_honest "$B"
sed -i 's/"status": "OPEN"/"status": "DEMO"/g' "$B/szl_putnam.py"
expect_fail "loader per-problem label drift (OPEN->DEMO vs canonical)" "$B"

# --- Fixture C: console fallback diverges from loader -> FAIL ---------------
C="$TMP/C"; make_honest "$C"
sed -i "s/\['A3','P_A3.lean','OPEN'/['A3','P_A3.lean','DEMO'/" "$C/pages/console.html"
expect_fail "console FB_PROBS diverges from loader (A3 OPEN->DEMO)" "$C"

# --- Fixture D: literal count-phrase drift in console -> FAIL ---------------
D="$TMP/D"; make_honest "$D"
sed -i 's#0 REAL / 1 DEMO / 2 OPEN#0 REAL / 3 DEMO / 0 OPEN#' "$D/pages/console.html"
expect_fail "console count phrase drift (claims 0/3/0 vs canonical 0/1/2)" "$D"

# --- Fixture E: canonical gains a problem the a11oy page never transcribed --
E="$TMP/E"; make_honest "$E"
printf '%s\n' '/-- Putnam B1. -/' '-- **Honest status: DEMO**' > "$E/canon/P_B1.lean"
expect_fail "missing canonical Putnam file (B1 added upstream, loader stale)" "$E"

# --- Fixture F: named "X and Y are OPEN" prose drift -> FAIL ----------------
F="$TMP/F"; make_honest "$F"
sed -i 's/<b>A2<\/b> and <b>A3<\/b> are OPEN/<b>A1<\/b> and <b>A2<\/b> are OPEN/' "$F/pages/console.html"
expect_fail "named-OPEN prose drift (says A1 and A2; canonical OPEN = A2,A3)" "$F"

# --- Fixture G: SZL REAL-count / label drift -> FAIL -----------------------
G="$TMP/G"; make_honest "$G"
sed -i 's/All proofs are REAL/All proofs are DEMO/' "$G/canon/SZL/One.lean"
expect_fail "SZL label/count drift (loader REAL vs canonical DEMO)" "$G"

# --- Fixture H: diligence packet count drift -> FAIL ----------------------
H="$TMP/H"; make_honest "$H"
sed -i 's/0 of 3 Putnam/1 of 3 Putnam/' "$H/docs/SERIES_A_DILIGENCE.md"
expect_fail "generated diligence packet drift (claims 1/3 vs canonical 0/3)" "$H"

# --- Fixture I: duplicate generated marker block -> FAIL ------------------
I="$TMP/I"; make_honest "$I"
cat >> "$I/docs/SERIES_A_DILIGENCE.md" <<'MD'
<!-- BEGIN GENERATED PUTNAM STATUS -->
duplicate
<!-- END GENERATED PUTNAM STATUS -->
MD
expect_fail "duplicate generated diligence marker block" "$I"

# --- Fixture J: REAL source contains sorry -> FAIL ------------------------
J="$TMP/J"; make_honest "$J"
sed -i 's/by trivial/by sorry/' "$J/canon/SZL/One.lean"
expect_fail "REAL theorem contains sorry" "$J"

# --- Fixture K: REAL source declares a new axiom -> FAIL ------------------
K="$TMP/K"; make_honest "$K"
sed -i '/theorem proof/i axiom rogue : Prop' "$K/canon/SZL/One.lean"
expect_fail "REAL source declares an extra axiom" "$K"

# --- Fixture L: kernel report contains an out-of-policy axiom -> FAIL -----
L="$TMP/L"; make_honest "$L"
cat > "$L/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' depends on axioms: [Classical.choice, Rogue.audit]
TXT
expect_fail_report "REAL theorem kernel report has an extra axiom" "$L" \
  "$L/axioms.txt"

# --- Fixture M: attributed REAL theorem missing from report -> FAIL -------
M="$TMP/M"; make_honest "$M"
sed -i '/theorem proof/a @[simp] theorem attributed : True := by trivial' \
  "$M/canon/SZL/One.lean"
cat > "$M/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
TXT
expect_fail_report "attributed REAL theorem is required in kernel report" "$M" \
  "$M/axioms.txt"

# --- Fixture N: split theorem header missing from report -> FAIL ----------
N="$TMP/N"; make_honest "$N"
sed -i '/end Lutar.Putnam.SZL.One/i theorem\n  splitHeader : True := by trivial' \
  "$N/canon/SZL/One.lean"
cat > "$N/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
TXT
expect_fail_report "multiline REAL theorem is required in kernel report" "$N" \
  "$N/axioms.txt"

# --- Fixture O: section end preserves namespace for later theorem -> PASS -
O="$TMP/O"; make_honest "$O"
sed -i '/end Lutar.Putnam.SZL.One/i section Local\n\
theorem insideSection : True := by trivial\n\
end Local\n\
theorem afterSection : True := by trivial' "$O/canon/SZL/One.lean"
cat > "$O/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
'Lutar.Putnam.SZL.One.insideSection' does not depend on any axioms
'Lutar.Putnam.SZL.One.afterSection' does not depend on any axioms
TXT
expect_pass_report "section end preserves namespace qualification" "$O" \
  "$O/axioms.txt"

# --- Fixture P: nested attribute theorem is audited -> FAIL then PASS -----
P="$TMP/P"; make_honest "$P"
sed -i '/theorem proof/a @[aesop safe apply (rule_sets := [foo])] theorem nestedAttribute : True := by trivial' \
  "$P/canon/SZL/One.lean"
cat > "$P/missing-axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
TXT
expect_fail_report "nested-attribute REAL theorem is required in kernel report" \
  "$P" "$P/missing-axioms.txt"
cat > "$P/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
'Lutar.Putnam.SZL.One.nestedAttribute' does not depend on any axioms
TXT
expect_pass_report "nested-attribute REAL theorem has a complete kernel report" \
  "$P" "$P/axioms.txt"

# --- Fixture Q: private helper omitted, public dependent audited ----------
Q="$TMP/Q"; make_honest "$Q"
sed -i '/theorem proof/a private theorem secret : True := by trivial\n\
theorem publicUsesPrivate : True := secret' "$Q/canon/SZL/One.lean"
cat > "$Q/missing-public.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
TXT
expect_fail_report "public theorem depending on private helper is still audited" \
  "$Q" "$Q/missing-public.txt"
cat > "$Q/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
'Lutar.Putnam.SZL.One.publicUsesPrivate' does not depend on any axioms
TXT
expect_pass_report "private helper does not require an unusable external name" \
  "$Q" "$Q/axioms.txt"

# --- Fixture R: named instance proof is required and axiom-audited --------
R="$TMP/R"; make_honest "$R"
sed -i '/theorem proof/a class AuditWitness : Prop where\n\
  witness : True\n\
public instance (priority := 100) auditedInstance.{u} : AuditWitness := ⟨True.intro⟩' \
  "$R/canon/SZL/One.lean"
cat > "$R/missing-instance.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
TXT
expect_fail_report "named REAL instance is required in kernel report" \
  "$R" "$R/missing-instance.txt"
cat > "$R/out-of-policy.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
'Lutar.Putnam.SZL.One.auditedInstance' depends on axioms: [Classical.choice, Rogue.audit]
TXT
expect_fail_report "named REAL instance cannot hide an out-of-policy axiom" \
  "$R" "$R/out-of-policy.txt"
cat > "$R/axioms.txt" <<'TXT'
'Lutar.Putnam.SZL.One.proof' does not depend on any axioms
'Lutar.Putnam.SZL.One.auditedInstance' depends on axioms: [Classical.choice]
TXT
expect_pass_report "named REAL instance has a complete in-policy kernel report" \
  "$R" "$R/axioms.txt"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
