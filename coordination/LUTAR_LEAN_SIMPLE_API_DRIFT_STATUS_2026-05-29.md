# Lutar Lean Simple API Drift Status — 2026-05-29

## Directive source

- `.github#82` Tier 1: fix Lean CI red before sorry closures.
- `.github#76` latest comment: Lean CI diagnosis lists simple API drifts in Wheeler/Shannon/Kitaev plus deeper modules.

## What Cursor prepared

Patch file:

- `coordination/proxy-patches/lutar-lean-simple-api-drift.patch`

Target repo:

- `szl-holdings/lutar-lean`

Patch contents:

- `Lutar/QEC/KitaevSurface.lean`
  - replaces Lean-invalid chained `!=` with explicit `Bool.xor` fold.
- `Lutar/Wheeler/DelayedChoiceClosure.lean`
  - replaces brittle `And.decidable` with `infer_instance` for decidable admission.
- `Lutar/Shannon/DoctrineEntropy.lean`
  - root-qualifies `_root_.Fintype.card DoctrineLabel` in the theorem/example called out by the CI diagnosis.

## Validation boundary

- Lean tooling (`lake`, `lean`, `elan`) is not installed in the Cursor runtime, so this patch is **not claimed kernel-verified**.
- The patch addresses mechanically identified API/syntax drift from the CI diagnosis and must be verified by `lake build` in a Lean-enabled environment before merge.

## Proxy command

From a writable `lutar-lean` checkout:

```bash
git checkout -b cursor/lean-simple-api-drift-2f18 origin/main
git apply /path/to/lutar-lean-simple-api-drift.patch
lake build
git add Lutar/QEC/KitaevSurface.lean Lutar/Wheeler/DelayedChoiceClosure.lean Lutar/Shannon/DoctrineEntropy.lean
git commit -s -m "fix(lean): repair simple API drift in QEC Wheeler Shannon"
git push -u origin cursor/lean-simple-api-drift-2f18
```

## Doctrine boundary

- No sorry closure is claimed here.
- No theorem count change is claimed.
- This is a CI-unblock candidate for three simple drift items only.
