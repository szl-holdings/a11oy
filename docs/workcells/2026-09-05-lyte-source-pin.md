# Lyte canonical source-pin repair

Base: `a4898e861e81bd19ccdb28131b48acc895f91be4` (protected A11oy main after Sentra #2003).

## Root cause

The canonical `hf-sync.yml` six-vertical publication stage is fail-closed because A11oy still pins Lyte to `a0479279505aded5c084d1644012829a1d93ad77`, while `szl-holdings/lyte-services` protected main is `a6a653b0d93a0d150b868a044642ce4f5c71d766` after merged Lyte #13. The deploy controller correctly refuses this stale production mutation.

## Required bounded repair

1. Replace the stale Lyte SHA with `a6a653b0d93a0d150b868a044642ce4f5c71d766` in the canonical source-owned Lyte publisher and estate entrypoint.
2. Update exact-SHA regression contracts/tests that intentionally pin that source revision.
3. Preserve Terra forge generator `szl-vertical-forge/0.2.2`, Sentra #2003 overlay, every non-Lyte vertical, the single-writer `hf-sync.yml` boundary, and the default-branch stale-deploy guard.
4. Do not weaken `--require-default-branch-tip`, do not add a second HF writer, do not mutate secrets, and do not directly write to the Hub outside the canonical workflow.
5. Keep the patch limited to the two publisher files, their exact source-pin tests, and this workcell unless a directly necessary regression file is required.

## Acceptance

The PR must prove the old SHA no longer exists in active source-pin contracts, the new SHA is consistently bound, all exact-head CI is terminal green, and after merge the canonical `Sync and Relock Canonical Hugging Face Space` run must pass the six-domain flagship publication stage including Lyte live verification.
