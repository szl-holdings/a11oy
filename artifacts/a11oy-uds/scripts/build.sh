#!/usr/bin/env bash
# Build the A11oy UDS / Zarf payload.
#
# Pipeline:
#   1. Build @a11oy/connection then @a11oy/core via `tsc -p tsconfig.json`.
#      Hard failures on missing source, missing build script, or empty
#      dist/. (Strict by default — set A11OY_UDS_ALLOW_SOURCE_FALLBACK=1
#      ONLY for local development to permit packaging src/ when no dist/
#      can be produced. This is forbidden for release output.)
#   2. Stage each package's built dist/ under artifacts/a11oy-uds/build/.
#   3. Generate MANIFEST.json with per-file sha256 + size + build metadata.
#   4. Run the verifier to round-trip every checksum.
#   5. If `zarf` is available, run `zarf package create` into
#      dist/a11oy-uds/ — this is the only release-grade output.
#      Otherwise, emit a deterministic tarball into the SEPARATE path
#      dist/a11oy-uds-fallback/ so it cannot be confused with a real
#      Zarf package. The README documents this distinction.
#   6. If COSIGN_KEY is set and `cosign` is available, sign the tarball.
#      Otherwise, write an unsigned <tarball>.sha256 sidecar.

set -euo pipefail

ARTIFACT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ARTIFACT_DIR}/../.." && pwd)"
BUILD_DIR="${ARTIFACT_DIR}/build"
ATTEST_DIR="${ARTIFACT_DIR}/build-attestations"
VERSION="$(node -p "require('${ARTIFACT_DIR}/package.json').version")"
GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BUILD_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

TSC="${REPO_ROOT}/node_modules/.bin/tsc"

log() { printf '[a11oy-uds] %s\n' "$*"; }
die() { printf '[a11oy-uds] ERROR: %s\n' "$*" >&2; exit 1; }

ALLOW_SOURCE="${A11OY_UDS_ALLOW_SOURCE_FALLBACK:-0}"
SOURCE_PACKAGED=0

log "version=${VERSION} git=${GIT_SHA} ts=${BUILD_TS} allow_source_fallback=${ALLOW_SOURCE}"

# ---------------------------------------------------------------------------
# 1. Clean staging.
# ---------------------------------------------------------------------------
rm -rf "${BUILD_DIR}" "${ATTEST_DIR}"
mkdir -p "${BUILD_DIR}/a11oy-core" "${BUILD_DIR}/a11oy-connection"

if [[ -d "${REPO_ROOT}/artifacts/a11oy/packages/a11oy-core" ]]; then
  A11OY_CORE_SRC="${REPO_ROOT}/artifacts/a11oy/packages/a11oy-core"
  A11OY_CONN_SRC="${REPO_ROOT}/artifacts/a11oy/packages/a11oy-connection"
else
  A11OY_CORE_SRC="${REPO_ROOT}/web/packages/a11oy-core"
  A11OY_CONN_SRC="${REPO_ROOT}/web/packages/a11oy-connection"
fi

[[ -d "${A11OY_CORE_SRC}" ]] || die "@a11oy/core source missing: ${A11OY_CORE_SRC}"
[[ -d "${A11OY_CONN_SRC}" ]] || die "@a11oy/connection source missing: ${A11OY_CONN_SRC}"

# ---------------------------------------------------------------------------
# 2. Build + stage each package.
# ---------------------------------------------------------------------------

build_with_tsc() {
  local pkg_label="$1"
  local pkg_dir="$2"
  if [[ ! -f "${pkg_dir}/tsconfig.json" ]]; then
    die "${pkg_label}: missing tsconfig.json at ${pkg_dir}/tsconfig.json"
  fi
  if [[ ! -x "${TSC}" ]]; then
    if [[ "${ALLOW_SOURCE}" == "1" ]]; then
      log "WARNING: ${pkg_label}: tsc not found at ${TSC}; source fallback enabled"
      rm -rf "${pkg_dir}/dist"
      return 0
    fi
    die "tsc binary not found at ${TSC} — run 'pnpm install' at repo root"
  fi
  log "building ${pkg_label} (tsc -p ${pkg_dir}/tsconfig.json)"
  rm -rf "${pkg_dir}/dist"
  ( cd "${pkg_dir}" && "${TSC}" -p tsconfig.json )
}

stage_built_package() {
  local pkg_label="$1"
  local pkg_dir="$2"
  local out_root="$3"

  build_with_tsc "${pkg_label}" "${pkg_dir}"

  if [[ -d "${pkg_dir}/dist" ]] && [[ -n "$(ls -A "${pkg_dir}/dist" 2>/dev/null || true)" ]]; then
    log "staging ${pkg_label} dist/ -> ${out_root}"
    cp -R "${pkg_dir}/dist/." "${out_root}/"
  else
    if [[ "${ALLOW_SOURCE}" != "1" ]]; then
      die "${pkg_label}: tsc produced no dist/ output at ${pkg_dir}/dist (set A11OY_UDS_ALLOW_SOURCE_FALLBACK=1 only for dev)"
    fi
    log "WARNING: ${pkg_label} produced no dist/ — packaging src/ as dev fallback"
    cp -R "${pkg_dir}/src/." "${out_root}/"
    SOURCE_PACKAGED=1
  fi

  if [[ -f "${pkg_dir}/package.json" ]]; then
    cp "${pkg_dir}/package.json" "${out_root}/package.json"
  fi
}

# Connection builds first (core's tsconfig consumes its .d.ts).
stage_built_package "@a11oy/connection" "${A11OY_CONN_SRC}" "${BUILD_DIR}/a11oy-connection"
stage_built_package "@a11oy/core"       "${A11OY_CORE_SRC}" "${BUILD_DIR}/a11oy-core"

# v0.2: stage cross-cutting shared packages (perception-loop, sequence-pipeline,
# sparse-attention-kit) under build/shared/. write-manifest.mjs walks the whole
# build/ dir so these are picked up automatically; attestation subjects extended
# in write-attestations.mjs and zarf.yaml below.
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/release/lib/stage-v2-packages.sh"
stage_v2_shared_packages "${BUILD_DIR}" "${REPO_ROOT}" "a11oy-uds"

# ---------------------------------------------------------------------------
# 3. Generate MANIFEST.json (sorted, per-file sha256 + size).
# ---------------------------------------------------------------------------
log "writing MANIFEST.json (sourcePackaged=${SOURCE_PACKAGED})"
VERSION="${VERSION}" GIT_SHA="${GIT_SHA}" BUILD_TS="${BUILD_TS}" \
  SOURCE_PACKAGED="${SOURCE_PACKAGED}" \
  node "${ARTIFACT_DIR}/scripts/write-manifest.mjs" "${BUILD_DIR}"

# ---------------------------------------------------------------------------
# 4. Verify the freshly-written manifest round-trips.
# ---------------------------------------------------------------------------
log "verifying MANIFEST.json"
node "${ARTIFACT_DIR}/scripts/verify-manifest.mjs" "${BUILD_DIR}"

# ---------------------------------------------------------------------------
# 4b. Generate + verify the hash-chained attestation sidecar.
#     Lives in a SEPARATE directory (build-attestations/) so it does not
#     pollute build/ — verify-manifest.mjs treats unknown files there as
#     a hard error. The Zarf component a11oy-attestations ships this
#     file as /opt/a11oy/ATTESTATIONS.json.
# ---------------------------------------------------------------------------
log "writing ATTESTATIONS.json (hash chain over MANIFEST.json subjects)"
node "${ARTIFACT_DIR}/scripts/write-attestations.mjs" "${BUILD_DIR}" "${ATTEST_DIR}"
log "verifying ATTESTATIONS.json"
node "${ARTIFACT_DIR}/scripts/verify-attestations.mjs" "${BUILD_DIR}" "${ATTEST_DIR}"

# ---------------------------------------------------------------------------
# 5. Produce the deployable tarball.
#    Release output goes ONLY to dist/a11oy-uds/<...>.tar.zst and is produced
#    by `zarf package create`. The non-zarf fallback uses a separate
#    dist/a11oy-uds-fallback/ path so it can never masquerade as a real
#    Zarf package.
# ---------------------------------------------------------------------------

if command -v zarf >/dev/null 2>&1; then
  DIST_DIR="${REPO_ROOT}/dist/a11oy-uds"
  mkdir -p "${DIST_DIR}"
  TARBALL="${DIST_DIR}/a11oy-uds-${VERSION}.tar.zst"
  log "zarf detected: running 'zarf package create' -> ${DIST_DIR}"
  ( cd "${ARTIFACT_DIR}" && zarf package create . --confirm --output "${DIST_DIR}" )
  # zarf names its output zarf-package-<name>-<arch>-<version>.tar.zst.
  PRODUCED="$(ls -1t "${DIST_DIR}"/zarf-package-a11oy-uds-*.tar.zst 2>/dev/null | head -n1 || true)"
  if [[ -n "${PRODUCED}" ]]; then
    rm -f "${TARBALL}"
    mv -f "${PRODUCED}" "${TARBALL}"
  fi
else
  DIST_DIR="${REPO_ROOT}/dist/a11oy-uds-fallback"
  mkdir -p "${DIST_DIR}"
  log "zarf not available — producing NON-zarf fallback archive"
  log "  (this is NOT a Zarf package and cannot be deployed via 'zarf package deploy')"
  if command -v zstd >/dev/null 2>&1; then
    TARBALL="${DIST_DIR}/a11oy-uds-${VERSION}.fallback.tar.zst"
    rm -f "${TARBALL}" "${TARBALL}.sig" "${TARBALL}.sha256"
    tar --sort=name \
        --owner=0 --group=0 --numeric-owner \
        --mtime="${BUILD_TS}" \
        -C "${BUILD_DIR}" \
        -cf - . \
      | zstd -19 -q -f -o "${TARBALL}"
  else
    TARBALL="${DIST_DIR}/a11oy-uds-${VERSION}.fallback.tar"
    log "WARNING: zstd not available — writing uncompressed deterministic tar fallback"
    rm -f "${TARBALL}" "${TARBALL}.sig" "${TARBALL}.sha256"
    tar --sort=name \
        --owner=0 --group=0 --numeric-owner \
        --mtime="${BUILD_TS}" \
        -C "${BUILD_DIR}" \
        -cf "${TARBALL}" .
  fi
fi

if [[ ! -s "${TARBALL}" ]]; then
  die "tarball not produced at ${TARBALL}"
fi
log "wrote $(du -h "${TARBALL}" | cut -f1) -> ${TARBALL}"

# ---------------------------------------------------------------------------
# 6. ALWAYS emit a sha256 sidecar; cosign .sig is additive when keys exist.
#    Earlier revs treated cosign as a replacement for sha256, which broke the
#    release gate's sha256 invariant whenever a key was configured.
# ---------------------------------------------------------------------------
( cd "${DIST_DIR}" && sha256sum "$(basename "${TARBALL}")" > "$(basename "${TARBALL}").sha256" )
log "wrote ${TARBALL}.sha256"

# Cosign signature — auto-discover binary + default to .local/cosign/cosign.key.
COSIGN_BIN="${COSIGN_BIN:-}"
if [[ -z "${COSIGN_BIN}" ]]; then
  if command -v cosign >/dev/null 2>&1; then COSIGN_BIN="$(command -v cosign)"
  elif [[ -x "${REPO_ROOT}/.local/bin/cosign" ]]; then COSIGN_BIN="${REPO_ROOT}/.local/bin/cosign"
  fi
fi
COSIGN_KEY="${COSIGN_KEY:-${REPO_ROOT}/.local/cosign/cosign.key}"
COSIGN_PUB="${COSIGN_PUB:-${REPO_ROOT}/.local/cosign/cosign.pub}"
if [[ -n "${COSIGN_BIN}" && -f "${COSIGN_KEY}" ]]; then
  log "signing with cosign (${COSIGN_BIN})"
  rm -f "${TARBALL}.sig"
  COSIGN_PASSWORD="${COSIGN_PASSWORD-}" "${COSIGN_BIN}" sign-blob --yes \
    --key "${COSIGN_KEY}" --output-signature "${TARBALL}.sig" "${TARBALL}"
  log "wrote ${TARBALL}.sig"
  if [[ -f "${COSIGN_PUB}" ]]; then
    cp -f "${COSIGN_PUB}" "${DIST_DIR}/a11oy-uds-dev.pub"
    log "wrote ${DIST_DIR}/a11oy-uds-dev.pub"
    log "verifying signature locally"
    "${COSIGN_BIN}" verify-blob --key "${COSIGN_PUB}" --signature "${TARBALL}.sig" "${TARBALL}" >/dev/null
    log "signature OK"
  fi
else
  log "WARNING: cosign signing skipped (bin=${COSIGN_BIN:-none} key=${COSIGN_KEY})"
fi

log "done."
