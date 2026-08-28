#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# a11oy Cloud Agent install — idempotent dependency refresh after checkout.
#
# Two toolchains, one repo:
#   * Python FastAPI runtime (serve.py, booted via gdw_runtime.py on :7860).
#     Runtime deps are pinned byte-for-byte to the HF Space Dockerfile so the
#     dev server resolves the same fastapi/uvicorn/cryptography closure.
#   * Node/pnpm doctrine workspace (@a11oy/core, @a11oy/connection, the jest
#     compliance suite, qec-integrity, a11oy-knowledge) — the clean-clone gate
#     described in AGENTS.md.
#
# Idempotent by construction: apt/pip/pnpm all converge; the venv is reused.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[a11oy-install] repo root: $REPO_ROOT"

# ---------------------------------------------------------------------------
# 1. System package: python3-venv/pip. The default base image ships CPython
#    3.12 but not the venv/ensurepip stdlib module. Install it once (this runs
#    at build/snapshot time, not per-boot). Guard so the script still succeeds
#    if the module is already present or apt is unavailable.
# ---------------------------------------------------------------------------
if ! python3 -c 'import ensurepip, venv' >/dev/null 2>&1; then
  echo "[a11oy-install] installing python3-venv / python3-pip via apt"
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv python3-pip
fi

# ---------------------------------------------------------------------------
# 2. Python virtualenv with the exact runtime pins from the Dockerfile, plus
#    pytest for the in-repo route/policy guard suites.
# ---------------------------------------------------------------------------
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
  echo "[a11oy-install] creating virtualenv at .venv"
  python3 -m venv "$REPO_ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$REPO_ROOT/.venv/bin/activate"

python -m pip install --upgrade pip

echo "[a11oy-install] installing pinned Python runtime dependencies"
pip install \
  "fastapi==0.137.1" \
  "uvicorn[standard]==0.49.0" \
  "httpx==0.28.1" \
  "starlette==1.3.1" \
  "huggingface_hub==1.19.0" \
  "openai==2.43.0" \
  "python-multipart==0.0.32" \
  "cryptography==50.0.0" \
  "lmdb==2.2.1" \
  "slowapi==0.1.10" \
  "defusedxml==0.7.1" \
  "numpy==2.1.3" \
  "pytest"

# ---------------------------------------------------------------------------
# 3. Node/pnpm doctrine workspace (frozen lockfile — the AGENTS.md gate).
# ---------------------------------------------------------------------------
if command -v pnpm >/dev/null 2>&1; then
  echo "[a11oy-install] pnpm install --frozen-lockfile"
  pnpm install --frozen-lockfile
else
  echo "[a11oy-install] WARNING: pnpm not found on PATH; skipping JS workspace install" >&2
fi

echo "[a11oy-install] done. Activate Python with:  source .venv/bin/activate"
