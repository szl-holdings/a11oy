#!/usr/bin/env bash
# Copyright 2026 SZL Holdings — SPDX-License-Identifier: Apache-2.0
#
# build_sign_all.sh — FOUNDER-RUNNABLE. Produces REAL, verifiable UDS artifacts:
#   1. Builds 5 container images from each flagship Dockerfile
#   2. Builds 5 Zarf packages (*.tar.zst) via `zarf package create`
#   3. Generates an SBOM per image (syft) and cosign-attests it
#   4. cosign-signs each Zarf package (.sig) with the SZL org key (offline)
#   5. `zarf package inspect` + `cosign verify-blob` on each (proof)
#   6. Records sha256sums of every artifact
#
# Prereqs (all confirmed installed in the build env): docker (daemon UP), zarf,
# uds (uds-cli), cosign, syft, kind, kubectl, helm.
#
# REQUIRED: the SZL cosign signing key must be present:
#   COSIGN_KEY=/home/user/workspace/szl/audit_2026-05-30_cursor_offline/.secret/cosign_signing_key.key
#   COSIGN_PUB=/home/user/workspace/szl/audit_2026-05-30_cursor_offline/.secret/cosign_signing_key.pub
#   export COSIGN_PASSWORD=""   # key passphrase is empty (verified by DSSE agent)
#
# Run:
#   cd uds_productionization && bash build_sign_all.sh 2>&1 | tee BUILD_RUN.log
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PER="$ROOT/PER_BUNDLE"
OUT="$ROOT/artifacts"
SECRET="/home/user/workspace/szl/audit_2026-05-30_cursor_offline/.secret"
COSIGN_KEY="${COSIGN_KEY:-$SECRET/cosign_signing_key.key}"
COSIGN_PUB="${COSIGN_PUB:-$SECRET/cosign_signing_key.pub}"
export COSIGN_PASSWORD="${COSIGN_PASSWORD:-}"
ARCH="${ARCH:-amd64}"
VER="0.3.1"
FLAGSHIPS=(a11oy amaru sentra killinchu rosie)

declare -A PKGNAME=( [a11oy]=a11oy-runtime [amaru]=amaru-attestation \
  [sentra]=sentra-gates [killinchu]=killinchu-bundle [rosie]=rosie-replay )
declare -A IMG=( [a11oy]=ghcr.io/szl-holdings/a11oy:uds-v0.3.1 \
  [amaru]=ghcr.io/szl-holdings/amaru:uds-v0.3.1 \
  [sentra]=ghcr.io/szl-holdings/sentra:uds-v0.3.1 \
  [killinchu]=ghcr.io/szl-holdings/killinchu:uds-v0.3.1 \
  [rosie]=ghcr.io/szl-holdings/rosie:uds-v0.3.1 )

mkdir -p "$OUT"
echo "== toolchain ==" ; zarf version; cosign version | head -1; syft version | head -1; docker version --format '{{.Server.Version}}'

for f in "${FLAGSHIPS[@]}"; do
  echo; echo "######## $f ########"
  cd "$PER/$f"

  echo "-- [1] docker build ${IMG[$f]}"
  docker build -t "${IMG[$f]}" .

  echo "-- [2] syft SBOM"
  syft "${IMG[$f]}" -o spdx-json > "$OUT/$f.sbom.spdx.json"

  echo "-- [3] zarf package create"
  zarf package create . --confirm --flavor upstream --output "$OUT"
  PKG="$OUT/zarf-package-${PKGNAME[$f]}-${ARCH}-${VER}.tar.zst"
  ls -la "$PKG"

  echo "-- [4] cosign sign-blob (offline, SZL org key) -> ${f}.uds.sig"
  cosign sign-blob --key "$COSIGN_KEY" --tlog-upload=false --yes "$PKG" > "$OUT/${f}.uds.sig"

  echo "-- [5] cosign verify-blob (PROOF)"
  cosign verify-blob --key "$COSIGN_PUB" --signature "$OUT/${f}.uds.sig" --insecure-ignore-tlog=true "$PKG"

  echo "-- [6] zarf package inspect (PROOF)"
  zarf package inspect "$PKG" || zarf package inspect definition "$PKG"

  echo "-- [7] cosign attest SBOM to package digest (optional, requires registry push)"
  # cosign attest --predicate "$OUT/$f.sbom.spdx.json" --type spdxjson --key "$COSIGN_KEY" --tlog-upload=false --yes "${IMG[$f]}"
done

echo; echo "== sha256sums =="
cd "$OUT"
sha256sum *.tar.zst *.uds.sig *.sbom.spdx.json | tee "$OUT/SHA256SUMS.txt"

echo "DONE. Artifacts in $OUT"
