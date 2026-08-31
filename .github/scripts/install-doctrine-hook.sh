#!/usr/bin/env bash
# install-doctrine-hook.sh — install the doctrine pre-check as an ADVISORY
# git pre-commit hook (warns, never blocks). The authoritative gate is the CI
# workflow doctrine-check.yml. Set DOCTRINE_BLOCK=1 if you WANT it to block.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
HOOK="$ROOT/.git/hooks/pre-commit"
[ -f "$ROOT/.github/scripts/doctrine_precommit.sh" ] || { echo "doctrine_precommit.sh missing" >&2; exit 1; }
cat > "$HOOK" <<'HOOK_EOF'
#!/usr/bin/env bash
# SZL doctrine pre-commit hook (ADVISORY by default; warns only).
# Set DOCTRINE_BLOCK=1 to make it block, DOCTRINE_SKIP=1 to silence.
[ "${DOCTRINE_SKIP:-0}" = "1" ] && exit 0
ROOT="$(git rev-parse --show-toplevel)"
if [ -x "$ROOT/.github/scripts/doctrine_precommit.sh" ]; then
  if ! bash "$ROOT/.github/scripts/doctrine_precommit.sh" --staged; then
    echo ""
    if [ "${DOCTRINE_BLOCK:-0}" = "1" ]; then
      echo "Commit blocked (DOCTRINE_BLOCK=1). Fix or scope as roadmap. CI doctrine-check.yml is authoritative."
      exit 1
    fi
    echo "⚠ Advisory: doctrine pre-check flagged possible overclaims above (heads-up only — not blocking)."
    echo "  CI doctrine-check.yml is authoritative. Set DOCTRINE_BLOCK=1 to enforce locally."
  fi
fi
exit 0
HOOK_EOF
chmod +x "$HOOK"
echo "✓ installed ADVISORY doctrine pre-commit hook (warn-only; DOCTRINE_BLOCK=1 to enforce)"
