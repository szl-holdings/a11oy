#!/usr/bin/env bash
set -euo pipefail

ORG="${ORG:-szl-holdings}"
DEST="${DEST:-.repos/${ORG}}"
REMOTE_PROTOCOL="${REMOTE_PROTOCOL:-https}"
REPO_LIMIT="${REPO_LIMIT:-300}"
INCLUDE_ARCHIVED="${INCLUDE_ARCHIVED:-0}"
INCLUDE_FORKS="${INCLUDE_FORKS:-0}"
UPDATE_WORKTREE="${UPDATE_WORKTREE:-1}"

fallback_repos=(
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

discover_repos() {
  local rows

  if command -v gh >/dev/null 2>&1; then
    if rows="$(gh repo list "$ORG" --limit "$REPO_LIMIT" --json name,isArchived,isFork --template '{{range .}}{{.name}}{{"\t"}}{{.isArchived}}{{"\t"}}{{.isFork}}{{"\n"}}{{end}}')" && [[ -n "$rows" ]]; then
      while IFS=$'\t' read -r name is_archived is_fork; do
        [[ -z "$name" ]] && continue
        [[ "$is_archived" == "true" && "$INCLUDE_ARCHIVED" != "1" ]] && continue
        [[ "$is_fork" == "true" && "$INCLUDE_FORKS" != "1" ]] && continue
        printf '%s\n' "$name"
      done <<< "$rows"
      return 0
    fi

    printf 'gh repo list did not return repos for %s; using fallback manifest\n' "$ORG" >&2
  else
    printf 'gh CLI not found; using fallback manifest\n' >&2
  fi

  printf '%s\n' "${fallback_repos[@]}"
}

refresh_checkout() {
  local target="$1"
  local repo="$2"
  local default_ref current_branch

  printf 'Refreshing %s\n' "${ORG}/${repo}"
  git -C "$target" fetch --prune origin

  [[ "$UPDATE_WORKTREE" == "1" ]] || return 0

  if ! git -C "$target" diff --quiet || ! git -C "$target" diff --cached --quiet; then
    printf 'Leaving %s worktree as-is because it has local changes\n' "${ORG}/${repo}" >&2
    return 0
  fi

  default_ref="$(git -C "$target" symbolic-ref -q --short refs/remotes/origin/HEAD || true)"
  default_ref="${default_ref#origin/}"
  [[ -n "$default_ref" ]] || default_ref="main"

  current_branch="$(git -C "$target" rev-parse --abbrev-ref HEAD)"
  if [[ "$current_branch" != "$default_ref" ]]; then
    printf 'Leaving %s on %s; default branch is %s\n' "${ORG}/${repo}" "$current_branch" "$default_ref" >&2
    return 0
  fi

  git -C "$target" pull --ff-only origin "$default_ref"
}

mapfile -t repos < <(discover_repos | LC_ALL=C sort -u)

if [[ "${#repos[@]}" -eq 0 ]]; then
  printf 'No repositories discovered for %s\n' "$ORG" >&2
  exit 1
fi

printf 'Syncing %s repositories for %s into %s\n' "${#repos[@]}" "$ORG" "$DEST"
mkdir -p "$DEST"

for repo in "${repos[@]}"; do
  target="${DEST}/${repo}"

  if [[ -d "${target}/.git" ]]; then
    refresh_checkout "$target" "$repo"
    continue
  fi

  if [[ -e "$target" ]]; then
    printf 'Skipping %s because %s exists but is not a git checkout\n' "${ORG}/${repo}" "$target" >&2
    continue
  fi

  printf 'Cloning %s\n' "${ORG}/${repo}"
  git clone "$(repo_url "$repo")" "$target"
done
