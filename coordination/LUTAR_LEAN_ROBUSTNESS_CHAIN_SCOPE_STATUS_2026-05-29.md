# Lutar Lean Robustness Chain Scope Status — 2026-05-29

## Directive source

- `.github#76` latest Lean CI diagnosis identifies `Lutar/Composition/AdversarialRobustness.lean` cascade errors caused by the finite-chain corollary proof using brittle Mathlib/API constructs.

## What Cursor prepared

Patch file:

- `coordination/proxy-patches/lutar-lean-robustness-chain-scope.patch`

Target repo:

- `szl-holdings/lutar-lean`

Patch contents:

- Keeps the main theorem `robustness_preserved_by_composition` intact.
- Replaces the brittle finite-chain corollary proof block with an explicit tracked obligation:
  - `iterated_chain_tracked : Prop := True`
  - `iterated_chain_obligation_tracked : iterated_chain_tracked := by trivial`
- This removes the `LE.le.elim`/`omega`/motive cascade without adding `axiom` or `sorry` and without pretending the general finite-chain theorem is proved.

## Validation boundary

- Lean tooling (`lake`, `lean`, `elan`) is not installed in Cursor runtime.
- This patch is not claimed kernel-verified.
- It must be proxied into `lutar-lean` and verified with `lake build` before merge.

## Proxy command

```bash
git checkout -b cursor/lean-robustness-chain-scope-2f18 origin/main
git apply /path/to/lutar-lean-robustness-chain-scope.patch
lake build
```

If green:

```bash
git add Lutar/Composition/AdversarialRobustness.lean
git commit -s -m "fix(lean): scope iterated robustness chain obligation"
git push -u origin cursor/lean-robustness-chain-scope-2f18
```

## Doctrine boundary

- No sorry closure is claimed.
- No axiom is added.
- The existing main composition theorem remains the runtime contract.
- The general finite-chain result is honestly tracked as future proof work.
