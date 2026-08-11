# Codex P0 Estate Closure — Start Here

This branch is a **context-only seed** for four isolated Codex cloud tasks. **Do not merge this seed branch.** Its commits were created through the GitHub contents API and are not the production implementation lineage.

## Exact seed identity

- Repository: `szl-holdings/a11oy`
- Protected branch: `main`
- Main at seed creation: `90ed8c7289efbda085d82f0dc60cf821b22f5caf`
- Seed branch: `codex/p0-live-parity-hf-estate-closure-20260811`

Every execution lane must refresh protected `main` at task start. If `main` has moved, use the newer exact head. Do not replay a stale patch against a changed architecture.

## Mandatory operating rules

1. Read the root `AGENTS.md` before editing and every more-specific `AGENTS.md` that applies to a touched path.
2. Work from a clean branch created from the exact current protected `main`.
3. Use a separate branch and pull request for each lane. Never let multiple agents write the same branch.
4. Create cryptographically signed commits with physical DCO trailers.
5. Never force-push, write directly to protected `main`, use an administrator bypass, self-approve, weaken a gate, or change rulesets/branch protection.
6. Never read, print, export, rotate, or copy secret values. Existing protected workflows may consume managed secrets.
7. Never publish unmerged source to Hugging Face. The canonical `hf-sync.yml` path is the only automatic writer for `SZLHOLDINGS/a11oy`.
8. Preserve honest labels. A merge is not deployment; reachability is not exact-source parity; a signature proves integrity/origin only within its declared scope.
9. Treat current source and direct current readback as authoritative. Cached readiness values, old payload SHAs, old PR bodies, and prior chat claims are evidence to reconcile—not truth to copy.
10. Do not trigger Nemo, GPU training, one-shot attempts, weight promotion, fuzzing, or other high-cost/irreversible work in these lanes.

## Four independent lanes

- [Lane 1 — Source-to-production parity and readiness](tasks/2026-08-11-lane-1-live-parity.md)
- [Lane 2 — Hugging Face estate and investor front door](tasks/2026-08-11-lane-2-huggingface-estate.md)
- [Lane 3 — PR, CI, payload, and dependency closure](tasks/2026-08-11-lane-3-github-closure.md)
- [Lane 4 — Release identity, evidence, and control-plane wiring](tasks/2026-08-11-lane-4-release-evidence.md)

## Required completion record

Each lane must finish with:

- exact starting and final commit SHAs;
- pull request URL;
- commands/tests executed and terminal results;
- workflow run IDs and artifact IDs where applicable;
- live immutable revision/readback evidence where applicable;
- every discovered payload classified as `APPLIED_AND_VERIFIED`, `SUPERSEDED_BY_NEWER_SOURCE`, `ALREADY_SATISFIED`, `RETIRED_WITH_READBACK`, `BLOCKED_EXTERNAL_AUTHORITY`, or `FAILED_WITH_RECEIPT`;
- explicit residual blockers, with no false-green claim.
