#!/usr/bin/env bash
# doctrine_precommit.sh — fast LOCAL mirror of the org doctrine guard's
# highest-value honesty invariants. Advisory: the authoritative gate is the
# reusable workflow .github/workflows/doctrine-check.yml on CI. This catches the
# common overclaims BEFORE push so they never reach a PR.
#
# Usage:
#   .github/scripts/doctrine_precommit.sh            # scan whole repo
#   .github/scripts/doctrine_precommit.sh --staged   # scan only staged files
#   make doctrine                                    # via the Makefile target
#
# Honesty doctrine v11: locked-proven = 8 {F1,F4,F7,F11,F12,F18,F19,F22};
# Λ = Conjecture 1 (never a theorem); SLSA L1 honest (L2 only on verified
# product images; L3/FedRAMP/Iron Bank/CMMC = roadmap); kernel @ c7c0ba17.
set -uo pipefail

# Prefer the real GitHub repo name (origin URL) over the local dir name.
_origin="$(git config --get remote.origin.url 2>/dev/null || echo '')"
REPO_NAME="$(basename "${_origin%.git}" 2>/dev/null)"
[ -z "$REPO_NAME" ] && REPO_NAME="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo .)")"
VERIFIED_L2_REPOS="a11oy killinchu"
IS_VERIFIED_L2=0
for r in $VERIFIED_L2_REPOS; do [ "$r" = "$REPO_NAME" ] && IS_VERIFIED_L2=1; done

FAIL=0
INC=(--include="*.md" --include="*.json" --include="*.yaml" --include="*.html" --include="*.tsx" --include="*.ts")
EXC=(--exclude-dir=".git" --exclude-dir="node_modules" --exclude-dir=".lake" --exclude-dir="corpus" --exclude-dir="coordination" --exclude-dir="cursor-directives" --exclude-dir="thesis" --exclude-dir="papers" --exclude-dir="v18" --exclude-dir="v20" --exclude-dir="v22" --exclude-dir="v23" --exclude-dir="cookbook")
# shared negation/citation exemption: lines that DISCLAIM, correct, cite axioms, or are instructions
NEG='gap|not approved|not Iron Bank|sponsor ask|posture|Loading|invitation-only|fails claimCalibration|overclaim|do not upgrade|without the infrastructure|enforced|gate\.ts|\.lean. \| |Conjecture 1|= 5/5 organs verified|do(n.?t| not) call|do(n.?t| not) claim|must remain|must be|mis-?claim|previously|corrected|no(t)? formal|honest sorry|is now a|carries #print|#print axioms|verification|kernel-checked|do not depend on any axiom|theorem about the gap|GIVEN factorization|search of|returned (no|zero)|NO Iron Bank|no Iron Bank|No Iron Bank|capability honesty|not in the Iron Bank|Section 889'

echo "== doctrine pre-check ($REPO_NAME · verified_L2=$IS_VERIFIED_L2) =="

# Inv 2: Λ described as a theorem (must be Conjecture 1)
M2=$(grep -rnE "Λ.*\btheorem\b|Lambda.*\btheorem\b|lambda uniqueness.*proven" "${INC[@]}" "${EXC[@]}" . 2>/dev/null \
  | grep -viE "conjecture|not a (proven )?theorem|never|theorem U|conditional|uniqueness theorem and|derived theorems" | grep -viE "$NEG" || true)
if [ -n "$M2" ]; then echo "✗ Inv2 (Λ=Conjecture 1): Λ referred to as a theorem without qualifier:"; echo "$M2" | head -5; FAIL=1; fi

# Inv 3a: SLSA L3 claims are banned everywhere
M3L3=$(grep -rnE "SLSA.*L3|SLSA Level 3" "${INC[@]}" "${EXC[@]}" . 2>/dev/null \
  | grep -viE "roadmap|future|planned|STAGED|awaiting|not (achieved|claiming|claim|yet)|no(t)? .{0,12}L3|L3.{0,12}not|banned|prohibited|historical|target|open-pr|PRs (exist|opened)|workflows" | grep -viE "$NEG" || true)
if [ -n "$M3L3" ]; then echo "✗ Inv3 (SLSA L3 banned):"; echo "$M3L3" | head -5; FAIL=1; fi

# Inv 3b: bare SLSA L2 claims on non-verified repos
if [ "$IS_VERIFIED_L2" = "0" ]; then
  M3L2=$(grep -rnE "SLSA.*L2|SLSA Level 2" "${INC[@]}" "${EXC[@]}" . 2>/dev/null \
    | grep -viE "verified|attested|attestation|roadmap|future|planned|STAGED|awaiting|not yet|no.*L2|L2.*not|bundle-level.*(not|NOT).*earned|(a11oy|killinchu)|szl-(a11oy|killinchu)|on organ images|banned|prohibited|open-pr|PRs (exist|opened)" | grep -viE "$NEG" || true)
  if [ -n "$M3L2" ]; then echo "✗ Inv3 (SLSA L2 needs evidence/roadmap scope on non-verified repo $REPO_NAME):"; echo "$M3L2" | head -5; FAIL=1; fi
fi

# Inv 5: banned positive compliance claims
M5=$(grep -rnE "Iron Bank|FedRAMP (High|Moderate)|CMMC L[2-5]|SWFT certified|Mission Owner" "${INC[@]}" "${EXC[@]}" . 2>/dev/null \
  | grep -viE "roadmap|future|planned|parity|tracked-not-baked|not (yet )?(achieved|certified|earned|baked|claiming|claim)|does NOT|does not|do(n.?t| not)|no(t)? .{0,20}(claim|ship|hardened|in the)|banned|prohibited|out of scope|not pursuing|target" | grep -viE "$NEG" || true)
if [ -n "$M5" ]; then echo "✗ Inv5 (no positive compliance claims w/o roadmap scope):"; echo "$M5" | head -5; FAIL=1; fi

# Inv 7: kernel commit drift (must stay c7c0ba17 where a locked-kernel claim is made)
M7=$(grep -rnE "locked.*kernel.*@ ?[0-9a-f]{6,40}|kernel @ ?[0-9a-f]{6,40}.*locked" "${INC[@]}" "${EXC[@]}" . 2>/dev/null \
  | grep -iE "@ ?[0-9a-f]{6,40}" | grep -viE "c7c0ba17|experimental|main @|roadmap" || true)
if [ -n "$M7" ]; then echo "✗ Inv7 (locked kernel must stay c7c0ba17):"; echo "$M7" | head -5; FAIL=1; fi

if [ "$FAIL" = "0" ]; then
  echo "✓ doctrine pre-check passed (advisory; CI doctrine-check.yml is authoritative)"
else
  echo ""
  echo "✗ doctrine pre-check found likely overclaims. Fix or scope as roadmap before pushing."
  echo "  (If a hit is a false positive, the authoritative CI guard has the full exemption set.)"
fi
exit $FAIL
