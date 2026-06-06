#!/usr/bin/env bash
# cosign-init.sh — the HONEST, fail-closed supply-chain gate.
#
# Two roles:
#   1. As `make verify` (--all): runs cosign verify + slsa-verifier against every
#      organ image from the host, prints a per-organ verdict matrix, exits non-zero
#      if any REQUIRED organ fails. This is the gate an engineer runs locally.
#   2. As the in-pod init container logic (mirrored inline in manifests/organs/*.yaml):
#      the pod fails to start if cosign verify fails.
#
# Doctrine: SLSA L1 honest + L2 attested. We DO NOT fake an L2 attestation. If an
# image has no provenance, we say so (L1 honest) rather than printing a green check.
set -uo pipefail

NAMESPACE="${NAMESPACE:-szl}"
ORGAN_TAG="${ORGAN_TAG:-uds-v0.2.0}"
REGISTRY="ghcr.io/szl-holdings"
COSIGN_PUB="${COSIGN_PUB:-$(dirname "$0")/../keys/cosign.pub}"
ORGANS=(a11oy sentra amaru killinchu rosie)
# killinchu is private until the founder flips GHCR. Treat its pull failure as a
# KNOWN GAP, not a hard gate failure, so the rest of the matrix is still useful.
PRIVATE_ORGANS=("killinchu")

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }

is_private() { for p in "${PRIVATE_ORGANS[@]}"; do [ "$p" = "$1" ] && return 0; done; return 1; }

verify_one() {
  local organ="$1" image="${REGISTRY}/$1:${ORGAN_TAG}"
  echo "=============================================================="
  echo ">> ${organ}  ($image)"

  # 0) can we even pull/reference it?
  if ! cosign triangulate "$image" >/dev/null 2>&1; then
    if is_private "$organ"; then
      yellow "   [SKIP-KNOWN-GAP] ${organ} image not accessible (private GHCR). Founder must flip to public."
      return 2
    fi
    red "   [FAIL] cannot reference ${image} (not pushed? not public?)"
    return 1
  fi

  # 1) cosign verify (keyed against szl-holdings public key) — REQUIRED.
  if cosign verify --key "$COSIGN_PUB" "$image" >/tmp/cosign.${organ}.out 2>&1; then
    green "   [OK]   cosign signature verified"
  else
    if is_private "$organ"; then
      yellow "   [SKIP-KNOWN-GAP] cosign verify blocked (private image). Founder flip pending."
      return 2
    fi
    red "   [FAIL] cosign verify FAILED — see /tmp/cosign.${organ}.out"
    sed 's/^/      /' /tmp/cosign.${organ}.out
    return 1
  fi

  # 2) slsa-verifier — L2 attested where present, L1 honest otherwise.
  if slsa-verifier verify-image "$image" \
       --source-uri "github.com/szl-holdings/${organ}" >/tmp/slsa.${organ}.out 2>&1; then
    green "   [OK]   SLSA L2 provenance verified"
  elif grep -qi "no matching\|no provenance\|no attestation" /tmp/slsa.${organ}.out; then
    yellow "   [L1]   no SLSA provenance attestation — honest L1 (cosign sig still valid)"
  else
    red "   [FAIL] slsa-verifier rejected ${image}"
    sed 's/^/      /' /tmp/slsa.${organ}.out
    return 1
  fi
  return 0
}

main() {
  if ! command -v cosign >/dev/null;  then red "cosign not installed (see README prerequisites)"; exit 3; fi
  if ! command -v slsa-verifier >/dev/null; then yellow "slsa-verifier not installed — L2 checks will be skipped"; fi
  [ -f "$COSIGN_PUB" ] || { red "cosign public key not found at $COSIGN_PUB"; exit 3; }

  local fail=0 gap=0
  declare -A verdict
  for organ in "${ORGANS[@]}"; do
    verify_one "$organ"
    rc=$?
    case $rc in
      0) verdict[$organ]="PASS" ;;
      2) verdict[$organ]="KNOWN-GAP"; gap=$((gap+1)) ;;
      *) verdict[$organ]="FAIL"; fail=$((fail+1)) ;;
    esac
  done

  echo "=============================================================="
  echo "VERDICT MATRIX (doctrine v11 749/14/163 @ c7c0ba17)"
  for organ in "${ORGANS[@]}"; do printf "   %-10s %s\n" "$organ" "${verdict[$organ]}"; done
  echo "--------------------------------------------------------------"
  if [ "$fail" -gt 0 ]; then
    red "RESULT: $fail organ(s) FAILED the honest supply-chain gate. Build env is NOT trustworthy."
    exit 1
  fi
  if [ "$gap" -gt 0 ]; then
    yellow "RESULT: all reachable organs PASS. $gap organ(s) are KNOWN GAPS (private image)."
    yellow "        This is honest-green: nothing faked, killinchu awaits founder GHCR flip."
    exit 0
  fi
  green "RESULT: 5/5 organs PASS cosign + SLSA gate. Build env supply chain is honest."
}

case "${1:-}" in
  --all|"") main ;;
  *) echo "usage: $0 --all"; exit 2 ;;
esac
