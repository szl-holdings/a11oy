#!/usr/bin/env bash
# Self-heal the amaru venv. Runs at every workflow start; no-ops if the venv
# is already present and importable. Idempotent.
#
# Important: we deliberately verify by file presence inside the venv's own
# site-packages, NOT by `python -c "import …"`. A bare import can succeed
# against PEP 370 user-site or system packages even when the venv is empty,
# which produced silent under-installs in the past.
set -euo pipefail

cd "$(dirname "$0")/.."

VENV=".venv"
PYBIN="$VENV/bin/python"
SITE="$VENV/lib/python3.11/site-packages"

required_paths=(
  "$PYBIN"
  "$SITE/fastapi"
  "$SITE/uvicorn"
  "$SITE/typing_extensions.py"
  "$SITE/anyio"
  "$SITE/pydantic"
)

needs_bootstrap=0
for p in "${required_paths[@]}"; do
  if [[ ! -e "$p" ]]; then
    needs_bootstrap=1
    break
  fi
done

# Modern pip (PEP 660) editable installs do NOT create amaru.egg-link.
# They create _editable_impl_amaru.pth + an amaru-*.dist-info directory.
# Accept either layout; rebuild only if neither marker is present.
if [[ "$needs_bootstrap" -eq 0 ]]; then
  if [[ ! -e "$SITE/_editable_impl_amaru.pth" ]] \
     && [[ -z "$(compgen -G "$SITE/amaru-*.dist-info" || true)" ]] \
     && [[ ! -e "$SITE/amaru.egg-link" ]]; then
    needs_bootstrap=1
  fi
fi

if [[ "$needs_bootstrap" -eq 1 ]]; then
  echo "[amaru bootstrap] (re)creating .venv"
  rm -rf "$VENV"
  python3 -m venv "$VENV"
  # --break-system-packages is required because the Nix-provided python is
  # marked PEP 668 externally-managed; the flag is harmless inside our own
  # venv (we are not modifying /nix/store).
  # --ignore-installed forces pip to write into the venv even when a
  # package is already present in the (read-only) Nix store. Without it,
  # pip will try to upgrade-in-place inside /nix/store and fail with EACCES.
  env PIP_USER=0 "$VENV/bin/pip" install --no-user --quiet --break-system-packages --ignore-installed \
    -e ".[dev]" \
    "typing_extensions>=4.0" >/dev/null
  echo "[amaru bootstrap] ready"
else
  echo "[amaru bootstrap] .venv healthy, skipping"
fi
