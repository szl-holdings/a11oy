#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# demo/jack-in.sh — top-level interactive jack-in selector for Warhacker.
# Founder directive 2026-05-30 16:46 EDT: "able to switch if they give us
# things to jack into." This asks the operator what Defense Unicorns handed
# over and dispatches to the right mode sub-script with the right env.
#
# Portability: bash 4+/5+ (Stephen's Lenovo Yoga, Win 11 + WSL2). No zsh-isms.
# Usage:
#   ./demo/jack-in.sh                 # interactive menu
#   ./demo/jack-in.sh A --dry-run     # jump straight to mode A in dry-run
#   ./demo/jack-in.sh --list          # list modes and exit

set -o errexit
set -o nounset
set -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "${HERE}/lib/common.sh"

# Mode registry: KEY|TITLE|RELATIVE_SCRIPT|READY
# READY ∈ {ready, config, prstage, doc, partial}
MODES=(
  "A|kubectl access to DU UDS Core cluster|modes/A-uds-core-kubectl/run.sh|ready"
  "B|vanilla k8s/k3d cluster (no UDS Core)|modes/B-vanilla-k8s/run.sh|partial"
  "C|bastion/SSH into air-gapped env (USB)|modes/C-airgap-usb/run.sh|ready"
  "D|custom OIDC issuer + client ID|modes/D-custom-oidc/run.sh|config"
  "E|private OCI registry behind firewall|modes/E-private-registry/run.sh|config"
  "F|cosign SAN allowlist / approved SANs|modes/F-cosign-allowlist/run.sh|ready"
  "G|OTel collector endpoint (Tempo/Jaeger)|modes/G-otel-endpoint/run.sh|prstage"
  "H|Kafka/NATS message bus they run|modes/H-message-bus/run.sh|doc"
  "I|IL5+/FedRAMP crypto (HSM/FIPS)|modes/I-il5-attestation/run.sh|doc"
  "J|nothing — show it on the laptop (k3d)|modes/J-laptop-k3d/run.sh|ready"
)

ready_tag() {
  case "$1" in
    ready)   echo "[READY today]";;
    config)  echo "[config tweak]";;
    prstage) echo "[PR-stage #19 — verify image first]";;
    partial) echo "[partial — needs UDS Core install]";;
    doc)     echo "[DOC ONLY — not a live switch]";;
    *)       echo "";;
  esac
}

list_modes() {
  echo "Warhacker jack-in modes (founder directive 2026-05-30 16:46 EDT):"
  echo
  for row in "${MODES[@]}"; do
    IFS='|' read -r key title script ready <<<"${row}"
    printf "  %s) %-42s %s\n" "${key}" "${title}" "$(ready_tag "${ready}")"
  done
  echo
  echo "Reference: demo/QUICKREF.md  |  ../../JACK_IN_PLAYBOOK.md (audit dir)"
}

dispatch() {
  local choice="$1"; shift || true
  for row in "${MODES[@]}"; do
    IFS='|' read -r key title script ready <<<"${row}"
    if [ "${key}" = "${choice}" ]; then
      local path="${HERE}/${script}"
      [ -x "${path}" ] || die "mode script missing or not executable: ${path}" "${EC_PRECOND}"
      log "Dispatching Mode ${key}: ${title} $(ready_tag "${ready}")"
      exec "${path}" "$@"
    fi
  done
  die "unknown mode: ${choice} (run with --list to see modes)" "${EC_USAGE}"
}

main() {
  if [ "${1:-}" = "--list" ] || [ "${1:-}" = "-l" ]; then
    list_modes; exit "${EC_OK}"
  fi

  if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: $0 [MODE_LETTER] [--dry-run] [mode-specific args]"
    echo "       $0 --list"
    list_modes; exit "${EC_OK}"
  fi

  # Non-interactive: a mode letter was passed.
  if [ "$#" -ge 1 ]; then
    local m; m="$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')"; shift
    dispatch "${m}" "$@"
    return
  fi

  # Interactive menu.
  echo "============================================================"
  echo " WARHACKER JACK-IN  —  What did Defense Unicorns give you?"
  echo "============================================================"
  list_modes
  printf "Enter a mode letter (A-J), or Q to quit: "
  read -r answer
  case "${answer}" in
    [Qq]) log "no mode selected; exiting"; exit "${EC_OK}";;
    *) ;;
  esac
  local up; up="$(printf '%s' "${answer}" | tr '[:lower:]' '[:upper:]')"
  printf "Run Mode %s in DRY-RUN first (recommended)? [Y/n]: " "${up}"
  read -r dr
  case "${dr}" in
    [Nn]*) dispatch "${up}" ;;
    *)     dispatch "${up}" --dry-run ;;
  esac
}

main "$@"
