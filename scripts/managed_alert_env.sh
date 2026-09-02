#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Source this file inside an alert-delivery step.  It changes only the current
# shell environment, emits no endpoint value, and masks the migrated value
# before any transport command can observe it.

_szl_prepare_managed_alert_endpoint() {
  if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
    return 0
  fi

  local root="${GITHUB_WORKSPACE:-$(pwd)}"
  local endpoint_file
  endpoint_file="$(mktemp)" || return 1
  chmod 600 "${endpoint_file}"

  if ! python3 "${root}/scripts/managed_alert_endpoint.py" --output "${endpoint_file}"; then
    rm -f "${endpoint_file}"
    echo "::error::Managed alert endpoint is invalid; no delivery was attempted."
    return 1
  fi

  local normalized
  if ! IFS= read -r normalized < "${endpoint_file}"; then
    rm -f "${endpoint_file}"
    echo "::error::Managed alert endpoint normalization produced no usable value."
    return 1
  fi
  rm -f "${endpoint_file}"
  if [ -z "${normalized}" ]; then
    echo "::error::Managed alert endpoint normalization produced an empty value."
    return 1
  fi

  echo "::add-mask::${normalized}"
  export SLACK_WEBHOOK_URL="${normalized}"
  unset normalized
}

_szl_prepare_managed_alert_endpoint
_szl_alert_endpoint_rc=$?
unset -f _szl_prepare_managed_alert_endpoint
return "${_szl_alert_endpoint_rc}" 2>/dev/null || exit "${_szl_alert_endpoint_rc}"
