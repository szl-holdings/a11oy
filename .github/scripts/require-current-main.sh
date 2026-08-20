#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_REF:?GITHUB_REF is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GH_TOKEN:?GH_TOKEN is required}"

if [[ "$GITHUB_REF" != "refs/heads/main" ]]; then
  echo "::error::Provider authority is restricted to refs/heads/main, not ${GITHUB_REF}."
  exit 1
fi

if [[ ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "::error::Dispatched source is not an immutable 40-character Git revision."
  exit 1
fi

checked_out="$(git rev-parse HEAD)"
if [[ "$checked_out" != "$GITHUB_SHA" ]]; then
  echo "::error::Checked-out source ${checked_out} does not match dispatched source ${GITHUB_SHA}."
  exit 1
fi

current_main="$(gh api "repos/${GITHUB_REPOSITORY}/git/ref/heads/main" --jq '.object.sha')"
if [[ "$current_main" != "$GITHUB_SHA" ]]; then
  echo "::error::Dispatched source ${GITHUB_SHA} is not current protected main ${current_main}."
  exit 1
fi

echo "Exact protected main confirmed: ${GITHUB_SHA}."
