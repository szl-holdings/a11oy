# Cursor latest status — 2026-05-29 late loop

## New directives read

- `.github#82` latest consolidated CTO+PM+Putnam comment.
- `.github#76` latest comments: agi-forecast patch proxied/applied as agi-forecast#42, invitations still runtime-bound, Lean CI diagnosis, Tier 1 queue.

## Completed now

### AGI Forecast

- Cursor FG-S1→S4 patch has already been proxied into `agi-forecast#42`.
- Cursor source-of-truth branch remains `a11oy:cursor/proxy-agi-forecast-fg-pipeline-2f18`.
- Local validation already passed: `npm install`, `npm test` (38 tests), `npm run build`.

### Lutar Lean simple API drift

Prepared a proxy patch for the three simplest Lean CI drift items from `.github#76` diagnosis:

- `Lutar/QEC/KitaevSurface.lean`: chained `!=` → explicit `Bool.xor` fold.
- `Lutar/Wheeler/DelayedChoiceClosure.lean`: `And.decidable` → `infer_instance`.
- `Lutar/Shannon/DoctrineEntropy.lean`: root-qualify `_root_.Fintype.card DoctrineLabel`.

Pushed to a11oy branch:

- `cursor/proxy-lutar-simple-api-drift-2f18`
- commit `5e920c3 fix(coordination): proxy simple lutar lean API drift patch`

Files:

- `coordination/LUTAR_LEAN_SIMPLE_API_DRIFT_STATUS_2026-05-29.md`
- `coordination/proxy-patches/lutar-lean-simple-api-drift.patch`

## Validation boundary

- Lean tooling (`lake`, `lean`, `elan`) is not installed in Cursor runtime.
- I do not claim the patch is kernel-verified.
- It must be proxied into `lutar-lean` and run through `lake build` before merge.

## Access status

Tried invitation acceptance loop; every invitation id returns 404 and `gh api user` returns 403. Runtime is still not authenticated as invitee user. Direct push/comment to sibling repos remains blocked.

## Next best proxy action

Please proxy `a11oy:cursor/proxy-lutar-simple-api-drift-2f18` into `lutar-lean` and run:

```bash
git checkout -b cursor/lean-simple-api-drift-2f18 origin/main
git apply coordination/proxy-patches/lutar-lean-simple-api-drift.patch
lake build
```

If green, commit with:

```bash
git commit -s -m "fix(lean): repair simple API drift in QEC Wheeler Shannon"
```
