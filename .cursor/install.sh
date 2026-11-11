#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# a11oy Cloud Agent install — idempotent dependency refresh after checkout.
#
# Two toolchains, one repo:
#   * Python FastAPI runtime (serve.py, booted via gdw_runtime.py on :7860).
#     Primary runtime pins come from the same manifest as the HF Space image.
#     Image-only model artifacts and system dependencies are not installed here.
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
# 2. Python virtualenv with the canonical runtime pins, plus
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
python -m pip install -r "$REPO_ROOT/requirements-runtime.txt" pytest

# Cortex uses the same non-generative witness as the image. A missing or
# incompatible witness must stop setup before the environment is ready.
python -m pip install \
  "https://github.com/szl-holdings/szl-nemo/archive/810231a531188bb569e3faa17396386eb0a5e260.tar.gz"
python - <<'PY'
import szl_nemo

if (szl_nemo.__version__ != '0.4.0'
        or tuple(szl_nemo.LOCKED_PROVEN_FORMULA_IDS) != ('F1','F4','F7','F11','F12','F18','F19','F22')
        or szl_nemo.ENVELOPE_RULE_VERSION != 'doctrine-v11/E1-E10'):
    raise SystemExit('Nemo witness identity does not match the runtime contract')
PY

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
