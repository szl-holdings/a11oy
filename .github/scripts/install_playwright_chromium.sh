#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
#
# Install Playwright's Chromium for a CI job without making the job depend on
# the Ubuntu archive answering at that moment.
#
# `playwright install --with-deps chromium` runs apt-get update and install on
# every job. On 2026-11-19 security.ubuntu.com returned I/O errors and stalls:
# a11oy#3570 and #3592 failed fetching mesa-libgallium and fonts-wqy-zenhei,
# and a11oy#3551 hit its 10-minute job limit inside apt, with no code at fault.
#
# This keeps the final package set identical to --with-deps, but:
#   1. downloads the pinned browser build with bounded retries;
#   2. asks Playwright which OS packages it needs (install-deps --dry-run) and
#      does not touch apt when every one is already installed (newer
#      Playwright reports "All system dependencies are installed" itself);
#      an unreadable plan falls back to Playwright's own installer;
#   3. otherwise installs only the missing packages, with apt request retries,
#      per-request timeouts and bounded attempts;
#   4. fails closed unless every required package is installed and the
#      Chromium headless shell renders a page.
#
# Usage: install_playwright_chromium.sh <playwright CLI...>
#   e.g. install_playwright_chromium.sh python -m playwright
#        install_playwright_chromium.sh npx playwright
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <playwright CLI...>" >&2
  exit 2
fi
pw=("$@")
attempts="${SZL_PW_ATTEMPTS:-3}"
pause="${SZL_PW_RETRY_PAUSE:-10}"
apt_conf="${SZL_PW_APT_CONF:-/etc/apt/apt.conf.d/99-szl-ci-network}"
sudo_cmd=()
if [ "$(id -u)" -ne 0 ]; then
  sudo_cmd=(sudo)
fi

# retry <label> <seconds per attempt> <command...>
retry() {
  local label="$1" limit="$2" n
  shift 2
  for n in $(seq 1 "$attempts"); do
    if timeout --kill-after=15 "$limit" "$@"; then
      return 0
    fi
    echo "::warning::$label failed (attempt $n of $attempts)" >&2
    if [ "$n" -lt "$attempts" ]; then
      sleep $((n * pause))
    fi
  done
  echo "::error::$label failed after $attempts attempts" >&2
  return 1
}

retry "Chromium download" 300 "${pw[@]}" install chromium

harden_apt() {
  printf '%s\n' 'Acquire::Retries "5";' 'Acquire::http::Timeout "30";' 'Acquire::https::Timeout "30";' \
    | "${sudo_cmd[@]}" tee "$apt_conf" >/dev/null
}

# Never let a failing dry-run abort silently: keep its output and exit code.
plan_rc=0
plan="$("${pw[@]}" install-deps --dry-run chromium 2>&1)" || plan_rc=$?
packages="$(printf '%s\n' "$plan" \
  | sed -n 's/.*--no-install-recommends \([^"]*\).*/\1/p' \
  | tr ' ' '\n' | grep -E '^[a-z0-9][a-z0-9.+-]*$' | sort -u || true)"

missing_packages() {
  local pkg
  for pkg in $packages; do
    if [ "$(dpkg-query -W -f='${db:Status-Status}' "$pkg" 2>/dev/null || true)" != "installed" ]; then
      echo "$pkg"
    fi
  done
}

if [ "$plan_rc" -eq 0 ] && [ -z "$packages" ] \
  && [[ "$plan" == *"All system dependencies are installed"* ]]; then
  # Newer Playwright checks the libraries itself and prints no package list.
  echo "Playwright reports every OS dependency installed; apt was not used."
elif [ "$plan_rc" -eq 0 ] && [ -n "$packages" ]; then
  total="$(printf '%s\n' $packages | wc -l)"
  missing="$(missing_packages)"
  if [ -z "$missing" ]; then
    echo "All $total OS packages Chromium needs are already installed; apt was not used."
  else
    echo "Installing $(printf '%s\n' $missing | wc -l) of $total OS packages: $(echo $missing)"
    harden_apt
    retry "apt-get update" 240 "${sudo_cmd[@]}" apt-get update
    # shellcheck disable=SC2086 # one argument per package name
    retry "apt-get install" 300 "${sudo_cmd[@]}" env DEBIAN_FRONTEND=noninteractive \
      apt-get install -y --no-install-recommends $missing
    missing="$(missing_packages)"
    if [ -n "$missing" ]; then
      echo "::error::OS packages still missing after install: $(echo $missing)" >&2
      exit 1
    fi
  fi
else
  # Unreadable plan: fall back to Playwright's own installer, never worse than
  # --with-deps, still with hardened apt and bounded attempts.
  echo "::warning::could not read Chromium's OS package plan (exit $plan_rc): $plan" >&2
  harden_apt
  retry "playwright install-deps" 600 "${pw[@]}" install-deps chromium
fi

browsers="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
shell_bin="$(find "$browsers" -type f \( -name headless_shell -o -name chrome-headless-shell \) \
  -perm -u+x 2>/dev/null | sort | tail -n 1)"
if [ -z "$shell_bin" ]; then
  echo "::error::no Chromium headless shell found under $browsers" >&2
  exit 1
fi
if ldd "$shell_bin" 2>/dev/null | grep -q 'not found'; then
  echo "::error::Chromium is missing shared libraries:" >&2
  ldd "$shell_bin" | grep 'not found' >&2
  exit 1
fi
dom="$(timeout --kill-after=10 60 "$shell_bin" --headless --no-sandbox --disable-gpu \
  --dump-dom 'data:text/html,<p>szl-chromium-ok</p>' 2>/dev/null || true)"
case "$dom" in
  *szl-chromium-ok*) echo "Chromium renders headlessly: $shell_bin" ;;
  *)
    echo "::error::Chromium did not render a test page: $shell_bin" >&2
    exit 1
    ;;
esac
