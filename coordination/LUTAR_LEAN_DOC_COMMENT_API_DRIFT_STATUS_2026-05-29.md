# Lutar Lean Doc-Comment / CSS API Drift Status — 2026-05-29

## Directive source

- `.github#76` latest Lean CI diagnosis after Tier-A batch work.
- Goal: keep shrinking Lean red surface with surgical, honest patches.

## What Cursor prepared

Patch file:

- `coordination/proxy-patches/lutar-lean-doc-comment-api-drift.patch`

Target repo:

- `szl-holdings/lutar-lean`

Patch contents:

- `Lutar/Gates/Adinkra.lean`
  - Converts two section doc-comments that can parse as proof-continuation tokens into line comments.
- `Lutar/DPI/SCITTMaskEntropy.lean`
  - Converts a free-standing explanatory doc-comment before `maskedDist` into line comments, preserving the real declaration doc-comment.
- `Lutar/QEC/CSSBridge.lean`
  - Removes `decide` from the abstract `css_bridge_consistent` theorem after `simp [consistent, classicalToCSS]`.

## Validation boundary

- Lean tooling (`lake`, `lean`, `elan`) is not installed in the Cursor runtime.
- This patch is not claimed kernel-verified.
- It is a proxy candidate for a Lean-enabled runner to test with `lake build`.

## Proxy command

```bash
git checkout -b cursor/lean-doc-comment-api-drift-2f18 origin/main
git apply /path/to/lutar-lean-doc-comment-api-drift.patch
lake build
```

If green:

```bash
git add Lutar/Gates/Adinkra.lean Lutar/DPI/SCITTMaskEntropy.lean Lutar/QEC/CSSBridge.lean
git commit -s -m "fix(lean): repair doc-comment and CSSBridge API drift"
git push -u origin cursor/lean-doc-comment-api-drift-2f18
```

## Doctrine boundary

- No sorry closure is claimed here.
- No theorem count change is claimed.
- No marketing claims; this is a CI-unblock candidate only.
