#!/usr/bin/env bash
# =============================================================================
# weight_guard_alert.sh — the shared "page the team on a scheduled-run failure"
# relay for the weight guards (gguf-weight-guard.yml, llama-wheel-guard.yml, and
# any future pinned-weight guard).
#
# Each weight guard's weekly `schedule:` re-verifies its contract against the
# live upstream even when nobody touches the repo. A scheduled-run failure has
# no red PR/push check to surface it, so it must PAGE the team through the shared
# a11oy-uptime relay (SLACK_WEBHOOK_URL — the same relay the other a11oy CI alert
# workflows use). PR/push failures are NOT paged (the red check is already
# visible); the caller gates this script behind
# `if: failure() && github.event_name == 'schedule'`.
#
# This block USED to be copy-pasted verbatim into every weight guard, differing
# only in the message text — so it could silently drift between guards. It now
# lives here once. The caller builds the human message and exports it as MSG;
# this script does the relay.
#
# Inputs (environment):
#   MSG                the alert text to relay (built by the caller). Required.
#   SLACK_WEBHOOK_URL  the a11oy-uptime relay endpoint. If unset, the script
#                      warns and exits 0 (the failing run remains the source of
#                      truth — there is nothing to page).
#
# This script NEVER masks the failure: the guard job is already RED from the
# failing step above it, so the relay is purely a notification and always exits
# 0 (a non-200 relay or a missing webhook is a `::warning::`, not a second red).
# =============================================================================
set -uo pipefail

if [ -z "${MSG:-}" ]; then
  echo "::warning::weight_guard_alert.sh called with no MSG to relay; nothing to page. The failing run remains the source of truth."
  exit 0
fi

if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
  echo "::warning::SLACK_WEBHOOK_URL is not set — cannot page; the failing run remains the source of truth."
  exit 0
fi

payload="$(MSG="${MSG}" python3 -c 'import json,os; print(json.dumps({"text": os.environ["MSG"]}))')"
code="$(curl -sS -o /tmp/relay.out -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d "${payload}" "${SLACK_WEBHOOK_URL}" || echo 000)"
echo "alert relay responded HTTP ${code}"
if [ "${code}" != "200" ]; then
  echo "::warning::Alert relay did not return 200 (got ${code}); the failing run itself remains the source of truth."
fi
exit 0
