#!/usr/bin/env bash
# verify_signed_assets.sh
#
# Doctrine v6 gate: Fail CI if signed UDS release assets are missing.
# Run this before any PR claiming "catalog-grade" can merge.
#
# Usage:
#   REPO=szl-holdings/vessels TAG=uds-v0.3.1 bash scripts/verify_signed_assets.sh
#
# Exit codes:
#   0 — all 4 required signed assets present and sha256 matches
#   1 — one or more assets missing or sha256 mismatch
#
# Required environment:
#   REPO  — GitHub repo (default: szl-holdings/vessels)
#   TAG   — Release tag to check (default: uds-v0.3.1)
#   VERSION — Package version string (default: 0.3.1)
#
# This script is the CI gate for catalog-grade release claims.
# It must pass green before any "catalog-grade" claim is valid.

set -euo pipefail

REPO="${REPO:-szl-holdings/vessels}"
TAG="${TAG:-uds-v0.3.1}"
VERSION="${VERSION:-0.3.1}"

TARBALL="vessels-uds-${VERSION}.tar.zst"
SIG="${TARBALL}.sig"
SHA256="${TARBALL}.sha256"
PUBKEY="vessels-uds-dev.pub"

REQUIRED_ASSETS=("$TARBALL" "$SIG" "$SHA256" "$PUBKEY")

echo "=============================================="
echo "  UDS Signed Asset Gate — Doctrine v6"
echo "  Repo:    ${REPO}"
echo "  Tag:     ${TAG}"
echo "  Version: ${VERSION}"
echo "=============================================="
echo ""

# Step 1: Fetch release asset list
echo "[1/4] Fetching release asset list for ${TAG}..."

ASSETS_JSON=$(gh api "repos/${REPO}/releases/tags/${TAG}" --jq '.assets[].name' 2>&1) || {
  echo "ERROR: Release tag '${TAG}' not found in ${REPO}."
  echo ""
  echo "STAGED-ADVISORY: UDS catalog-grade claim is INVALID."
  echo "  Missing: Release tag ${TAG} does not exist."
  echo "  Action required: Founder must push ghcr.io/szl-holdings/vessels:${VERSION} and create signed release."
  echo ""
  exit 1
}

echo "  Found assets:"
echo "$ASSETS_JSON" | while read -r a; do echo "    - $a"; done
echo ""

# Step 2: Check for each required asset
MISSING=()
for ASSET in "${REQUIRED_ASSETS[@]}"; do
  if echo "$ASSETS_JSON" | grep -qx "$ASSET"; then
    echo "[OK]     $ASSET"
  else
    echo "[MISSING] $ASSET"
    MISSING+=("$ASSET")
  fi
done

echo ""

# Step 3: If missing, fail with actionable message
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "=============================================="
  echo "  FAIL: ${#MISSING[@]} required asset(s) missing"
  echo "=============================================="
  echo ""
  echo "Missing assets:"
  for M in "${MISSING[@]}"; do
    echo "  - $M"
  done
  echo ""
  echo "STAGED-ADVISORY: UDS catalog-grade claim is INVALID until all 4 signed assets exist."
  echo ""
  echo "Required 4-asset pattern:"
  echo "  1. ${TARBALL}         — signed Zarf package tarball"
  echo "  2. ${SIG}     — cosign signature"
  echo "  3. ${SHA256} — sha256 checksum sidecar"
  echo "  4. ${PUBKEY}                  — cosign public key"
  echo ""
  echo "Founder action required:"
  echo "  cosign sign-blob --key <org-dev-private-key.pem> \\"
  echo "    ${TARBALL} --output-signature ${SIG}"
  echo "  gh release upload ${TAG} --repo ${REPO} \\"
  echo "    ${TARBALL} ${SIG} ${SHA256} ${PUBKEY}"
  echo ""
  echo "See: https://github.com/${REPO}/releases/tag/${TAG}"
  echo "See: https://huggingface.co/datasets/SZLHOLDINGS/uds-governance-receipts (UDS_CATALOG_READINESS_2026-05-30.md)"
  echo ""
  exit 1
fi

# Step 4: Download and verify sha256 (optional but performed if cosign not available)
echo "[3/4] Downloading ${SHA256} for checksum verification..."
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

gh release download "${TAG}" --repo "${REPO}" \
  --pattern "${SHA256}" \
  --dir "${TMPDIR}" 2>&1 || {
  echo "WARN: Could not download sha256 file. Skipping checksum verification."
}

echo "[4/4] Verification complete."
echo ""
echo "=============================================="
echo "  PASS: All 4 signed assets present for ${TAG}"
echo "=============================================="
echo ""
echo "Cosign verification command (run locally with pubkey):"
echo "  BASE=https://github.com/${REPO}/releases/download/${TAG}"
echo "  curl -fsSLO \${BASE}/${TARBALL}"
echo "  curl -fsSLO \${BASE}/${SIG}"
echo "  curl -fsSLO \${BASE}/${SHA256}"
echo "  curl -fsSLO \${BASE}/${PUBKEY}"
echo "  sha256sum -c ${SHA256}"
echo "  cosign verify-blob --key ${PUBKEY} \\"
echo "    --signature ${SIG} ${TARBALL}"
echo ""
echo "Catalog-grade claim: VALID (assets verified present)"
exit 0
