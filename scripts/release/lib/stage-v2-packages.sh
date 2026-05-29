#!/usr/bin/env bash
# stage-v2-packages.sh — shared helper sourced by every *-uds/scripts/build.sh
# that ships the v0.2 cross-cutting shared-package payload:
#
#   - @szl-holdings/perception-loop         (operator-loop perception envelope)
#   - @szl-holdings/sequence-pipeline       (multi-stage hashed pipeline)
#   - @szl-holdings/sparse-attention-kit    (sparse envelope + receipts)
#
# These packages ship as ESM source (their package.json declares main = src/),
# so we copy src/ + package.json into BUILD_DIR/shared/<name>/. The bundle's
# MANIFEST.json walker is extended to include build/shared/ so each shared
# file gets its own sha256, and the bundle's zarf.yaml exposes a single
# `<bundle>-shared` component that drops the dir at /opt/<product>/shared.
#
# Usage from a build.sh:
#   source "${REPO_ROOT}/scripts/release/lib/stage-v2-packages.sh"
#   stage_v2_shared_packages "${BUILD_DIR}" "${REPO_ROOT}" "${LOG_PREFIX:-uds}"
#
# The function is idempotent: it removes build/shared/ first.

set -euo pipefail

stage_v2_shared_packages() {
  local build_dir="$1"
  local repo_root="$2"
  local log_prefix="${3:-uds}"

  if [[ -z "${build_dir}" || -z "${repo_root}" ]]; then
    printf '[%s][stage-v2] ERROR: usage: stage_v2_shared_packages BUILD_DIR REPO_ROOT [LOG_PREFIX]\n' "${log_prefix}" >&2
    return 1
  fi

  local shared_root="${build_dir}/shared"
  rm -rf "${shared_root}"
  mkdir -p "${shared_root}"

  local pkg
  for pkg in perception-loop sequence-pipeline sparse-attention-kit; do
    local src_dir="${repo_root}/packages/${pkg}"
    if [[ ! -d "${src_dir}/src" ]]; then
      printf '[%s][stage-v2] ERROR: missing source for %s at %s\n' "${log_prefix}" "${pkg}" "${src_dir}/src" >&2
      return 1
    fi
    local out_dir="${shared_root}/${pkg}"
    mkdir -p "${out_dir}"
    # Copy src/ verbatim — these packages ship .ts as their main entry.
    cp -R "${src_dir}/src/." "${out_dir}/"
    # package.json carries the export map consumers rely on.
    if [[ -f "${src_dir}/package.json" ]]; then
      cp "${src_dir}/package.json" "${out_dir}/package.json"
    fi
    # README is informational but non-blocking; copy when present.
    if [[ -f "${src_dir}/README.md" ]]; then
      cp "${src_dir}/README.md" "${out_dir}/README.md"
    fi
    printf '[%s][stage-v2] staged %s -> %s\n' "${log_prefix}" "${pkg}" "${out_dir}"
  done
}
