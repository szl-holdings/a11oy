#!/usr/bin/env bash
set -euo pipefail

ORG="${ORG:-szl-holdings}"
DEST="${DEST:-.repos/${ORG}}"
REMOTE_PROTOCOL="${REMOTE_PROTOCOL:-https}"

repos=(
  ".github"
  "a11oy"
  "agi-forecast"
  "amaru"
  "carlota-jo"
  "counsel"
  "lutar-lean"
  "ouroboros"
  "ouroboros-thesis"
  "platform"
  "rosie"
  "sentra"
  "szl-brand"
  "szl-cookbook"
  "szl-trust"
  "terra"
  "uds-mesh"
  "vessels"
  "vsp-otel"
)

repo_url() {
  local repo="$1"

  case "$REMOTE_PROTOCOL" in
    https)
      printf 'https://github.com/%s/%s.git\n' "$ORG" "$repo"
      ;;
    ssh)
      printf 'git@github.com:%s/%s.git\n' "$ORG" "$repo"
      ;;
    *)
      printf 'Unsupported REMOTE_PROTOCOL: %s\n' "$REMOTE_PROTOCOL" >&2
      return 2
      ;;
  esac
}

mkdir -p "$DEST"

for repo in "${repos[@]}"; do
  target="${DEST}/${repo}"

  if [[ -d "${target}/.git" ]]; then
    printf 'Refreshing %s\n' "${ORG}/${repo}"
    git -C "$target" fetch --prune origin
    continue
  fi

  if [[ -e "$target" ]]; then
    printf 'Skipping %s because %s exists but is not a git checkout\n' "${ORG}/${repo}" "$target" >&2
    continue
  fi

  printf 'Cloning %s\n' "${ORG}/${repo}"
  git clone "$(repo_url "$repo")" "$target"
done
