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
#   3. otherwise installs only the missing packages: first offline from package
#      archives restored from the Actions cache (SZL_PW_DEB_CACHE, checked by
#      apt against the runner's signed package lists), else from the network
#      with apt request retries, per-request timeouts and bounded attempts,
#      keeping what it downloaded for the next cache save;
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
archives="${SZL_PW_APT_ARCHIVES:-/var/cache/apt/archives}"
# Optional: a directory restored from the Actions cache that holds the package
# archives an earlier job fetched. apt still checks every one against the
# runner's signed package lists before it installs it.
deb_cache="${SZL_PW_DEB_CACHE:-}"
case "$deb_cache" in "~/"*) deb_cache="$HOME/${deb_cache#\~/}" ;; esac
sudo_cmd=()
if [ "$(id -u)" -ne 0 ]; then
  sudo_cmd=(sudo)
fi

# Bounded runners. sudo (1.9.15) starts its command in a new session, so a
# timeout outside sudo kills only sudo and orphans a stalled apt-get, which
# keeps the apt lock. The root runner therefore puts the timeout under sudo.
bounded() { local limit="$1"; shift; timeout --kill-after=15 "$limit" "$@"; }
bounded_root() { local limit="$1"; shift; "${sudo_cmd[@]}" timeout --kill-after=15 "$limit" "$@"; }

# retry <label> <runner> <seconds per attempt> <command...>
retry() {
  local label="$1" runner="$2" limit="$3" n
  shift 3
  for n in $(seq 1 "$attempts"); do
    if "$runner" "$limit" "$@"; then
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

retry "Chromium download" bounded 300 "${pw[@]}" install chromium

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

list_archives() {
  find "$archives" -maxdepth 1 -type f -name '*.deb' -printf '%f\n' 2>/dev/null | sort || true
}

# Install the missing packages from cached archives only (apt-get --no-download).
# Succeeds only if every missing package ends up installed; otherwise the copied
# archives are removed again and the network path runs as before.
install_from_cache() {
  local f name n=0 copied=()
  [ -n "$deb_cache" ] || return 1
  for f in "$deb_cache"/*.deb; do
    [ -f "$f" ] || continue
    n=$((n + 1))
    name="$(basename "$f")"
    if [ ! -e "$archives/$name" ] && "${sudo_cmd[@]}" cp -- "$f" "$archives/$name"; then
      copied+=("$archives/$name")
    fi
  done
  [ "$n" -gt 0 ] || return 1
  echo "Trying $n cached package archives before the network"
  # shellcheck disable=SC2086 # one argument per package name
  if bounded_root 300 env DEBIAN_FRONTEND=noninteractive \
      apt-get install -y --no-install-recommends --no-download $missing \
      && [ -z "$(missing_packages)" ]; then
    echo "Installed from $n cached package archives; the Ubuntu archive was not used."
    return 0
  fi
  if [ "${#copied[@]}" -gt 0 ]; then
    "${sudo_cmd[@]}" rm -f -- "${copied[@]}" || true
  fi
  echo "The cached archives did not cover this install; using the network."
  return 1
}

# Keep exactly the archives this run downloaded, for the Actions cache to save.
# Never fails the job: a cache that is not refreshed only costs time next run.
keep_for_cache() {
  local before="$1" fetched f ok=1
  [ -n "$deb_cache" ] || return 0
  fetched="$(comm -13 <(printf '%s\n' "$before") <(list_archives) | sed '/^$/d')"
  [ -n "$fetched" ] || return 0
  mkdir -p "$deb_cache" && find "$deb_cache" -maxdepth 1 -type f -name '*.deb' -delete || ok=0
  if [ "$ok" -eq 1 ]; then
    while read -r f; do
      cp -- "$archives/$f" "$deb_cache/" || { ok=0; break; }
    done <<< "$fetched"
  fi
  if [ "$ok" -eq 1 ]; then
    echo "Kept $(printf '%s\n' "$fetched" | wc -l) downloaded package archives for the Actions cache."
  else
    echo "::warning::could not keep the downloaded package archives for the Actions cache" >&2
  fi
}

if [ "$plan_rc" -eq 0 ] && [ -z "$packages" ] \
  && [[ "$plan" == *"All system dependencies are installed"* ]]; then
  # Newer Playwright checks the libraries itself and prints no package list.
  echo "Playwright reports every OS dependency installed; apt was not used."
elif [ -n "$packages" ]; then
  # A package list is usable even if the dry-run exited non-zero
  # (Playwright 1.62 does so when dependencies are missing).
  if [ "$plan_rc" -ne 0 ]; then
    echo "Playwright's dry-run exited $plan_rc but listed its packages; using that list."
  fi
  total="$(printf '%s\n' $packages | wc -l)"
  missing="$(missing_packages)"
  if [ -z "$missing" ]; then
    echo "All $total OS packages Chromium needs are already installed; apt was not used."
  else
    echo "Installing $(printf '%s\n' $missing | wc -l) of $total OS packages: $(echo $missing)"
    install_from_cache || true
    # Recompute either way: never re-install (and so upgrade) a present package.
    missing="$(missing_packages)"
    if [ -n "$missing" ]; then
      before="$(list_archives)"
      harden_apt
      retry "apt-get update" bounded_root 240 apt-get update
      # shellcheck disable=SC2086 # one argument per package name
      retry "apt-get install" bounded_root 300 env DEBIAN_FRONTEND=noninteractive \
        apt-get install -y --no-install-recommends $missing
      keep_for_cache "$before"
    fi
    missing="$(missing_packages)"
    if [ -n "$missing" ]; then
      echo "::error::OS packages still missing after install: $(echo $missing)" >&2
      exit 1
    fi
  fi
else
  # Unreadable plan: fall back to Playwright's own installer, never worse than
  # --with-deps, still with hardened apt and bounded attempts. Playwright runs
  # its own sudo here, so a stalled apt inside it is bounded by the job's
  # timeout-minutes rather than by this timeout.
  echo "::warning::could not read Chromium's OS package plan (exit $plan_rc): $plan" >&2
  harden_apt
  retry "playwright install-deps" bounded 600 "${pw[@]}" install-deps chromium
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
