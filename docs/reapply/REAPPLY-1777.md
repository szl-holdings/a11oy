# REAPPLY-1777 — Obsidian Signal rollout-contract repair

PR #1777 was closed unmerged (2026-09-04T03:04Z). Verified 2026-09-04: main does
NOT carry the repair (`STYLE_MARKER` absent from
`scripts/rollout_holographic_experience_v2.py`). This kit re-applies it.

## Apply (any lane with a git client)

```bash
git checkout main && git pull
 git checkout -b fix/obsidian-signal-rollout-contracts-v2
git apply --3way docs/reapply/1777.patch
git rm .github/workflows/emergency-live-convergence-v1.yml   # part of the original repair
python -m pytest -q tests/test_frontend_flow_shell.py
gh pr create --title "fix(ux): close the Obsidian Signal rollout contracts (re-apply of #1777)"
```

## What the repair does (from the original PR)

- `is_bound()` validates Holo v2 bindings semantically: exactly one marker per
  local asset, independent of attribute order or `>` vs `/>` serialization
- duplicate-marker / local-source / source-boundary failures preserved
- `pages/wires.html` declared a complete source-native Hatun shell; excluded from
  the generic Flow Shell injector
- `frontend-flow-shell-state.json` records the bespoke shell; wires.html removed
  from the injected ledger; examined 108 -> 107
- regression test: zero Flow bindings, one Holo stylesheet, one Holo runtime,
  Hatun identity, live mesh contract on pages/wires.html
- the emergency convergence workflow (which auto-merged while checks settled)
  is removed
