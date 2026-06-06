#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# offline-quickstart.sh — run sentra's test suite with no registry auth.
#
# Three of the five module repos depend on private @szl-holdings/* packages
# published to GitHub Packages, which a fresh clone cannot fetch without a
# NODE_AUTH_TOKEN (ERR_PNPM_FETCH_401). sentra already ships local workspace
# stubs for every one of those packages under stubs/, so the suite can run
# fully offline — but two things get in the way of a guest:
#
#   1. .npmrc references ${NODE_AUTH_TOKEN}; when it is unset pnpm prints a
#      warning and, on a cold store, tries the authenticated registry.
#   2. pnpm re-verifies dependency status before `run` scripts and re-triggers
#      install, which then hits the same registry path.
#
# This script sidesteps both: it defaults NODE_AUTH_TOKEN to empty so the
# .npmrc reference resolves without warning (the workspace stubs satisfy the
# @szl-holdings/* names locally, so the authenticated registry is never
# contacted for them), and disables the pre-run deps check. It backs the root
# `test:offline` / `build:offline` / `dev:offline` scripts.
#
# Usage:  bash scripts/offline-quickstart.sh [test|build|dev]   (default: test)
#
# Authored for SZL Holdings. Signed-off per repository DCO.
set -euo pipefail

ACTION="${1:-test}"

# Provide an empty auth token so the .npmrc ${NODE_AUTH_TOKEN} reference
# resolves instead of warning. Every @szl-holdings/* dependency is a workspace
# stub, so the authenticated registry is never actually contacted for them and
# an empty token suffices for a workspace install/run.
export NODE_AUTH_TOKEN="${NODE_AUTH_TOKEN:-}"

# Do not re-verify / re-install deps before running a script: the pre-run deps
# check otherwise re-triggers install and the registry path.
export PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "── sentra offline quickstart (no registry auth) ────────────────────"
echo "Confirming the private deps are satisfied by shipped stubs…"
for pkg in a11oy-policy a11oy-receipt-substrate; do
  stub_dir="stubs/szl-holdings-${pkg}"
  if [ ! -f "${stub_dir}/package.json" ]; then
    echo "ERROR: expected stub ${stub_dir}/package.json is missing." >&2
    exit 1
  fi
  echo "  found ${stub_dir}"
done
echo ""

case "${ACTION}" in
  test)
    echo "Running the web safety-gate suite offline…"
    exec pnpm --dir web test
    ;;
  build)
    echo "Building the web app offline…"
    exec pnpm --dir web build
    ;;
  dev)
    echo "Starting the web dev server offline…"
    exec pnpm --dir web dev
    ;;
  *)
    echo "ERROR: unknown action '${ACTION}'. Use test, build, or dev." >&2
    exit 1
    ;;
esac
