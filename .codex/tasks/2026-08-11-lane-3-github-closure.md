# Lane 3 — Pull Requests, CI, Payloads, and Dependency Closure

## Mission

Drive the current `szl-holdings/a11oy` source-control queue to a truthful terminal state. Handle every open PR, current exact-default-branch workflow failure, repository-native payload, review thread, and dependency update. Do not merge by age, title, or automation source. Use exact-head evidence and normal protections.

## Current seed context

At seed creation, protected `main` is `90ed8c7289efbda085d82f0dc60cf821b22f5caf`, with open Dependabot PRs including action pins and a major Vite upgrade. Refresh the queue at task start; the seed list is not authoritative after `main` moves.

## Required PR disposition

Every open or recently superseded PR must receive exactly one terminal disposition:

```text
MERGED_WITH_EXACT_HEAD_EVIDENCE
CLOSED_SUPERSEDED
CLOSED_INVALID_OR_UNSAFE
BLOCKED_PROTECTED_GATE
BLOCKED_EXTERNAL_AUTHORITY
```

Do not leave stale duplicate branches or ambiguous successor lineage.

## Required payload disposition

Discover `AGENTS.md`, `CODEX_TASK.md`, `.codex/tasks/**`, `.github/codex/tasks/**`, payload ZIP/manifests, rescue tasks, frontier docs, and issue-linked execution briefs. Classify each as:

```text
APPLIED_AND_VERIFIED
SUPERSEDED_BY_NEWER_SOURCE
ALREADY_SATISFIED
RETIRED_WITH_READBACK
BLOCKED_EXTERNAL_AUTHORITY
FAILED_WITH_RECEIPT
```

Do not blindly apply an old payload to a newer protected tree.

## PR and CI rules

1. Refresh exact base/head SHA, draft state, mergeability, requested changes, independent reviews, and all status checks before any mutation.
2. Rerun failed workflow jobs at most once per immutable head and only when the failure could be transient.
3. Root-cause deterministic failures. Never weaken checks or relabel them neutral.
4. Require cryptographically verified commits and physical DCO trailers where repository rules require them.
5. Use exact-head auto-merge or the merge queue. Never use `--admin`, direct merge, force push, self-approval, or rule changes.
6. Close replaced PRs only after the successor contains the intended source and the closure comment records the lineage.
7. Preserve intentional-red or experimental workflows as honest non-green evidence.

## Dependency policy

- Grouped non-major action/dependency updates may merge only after all exact-head install/build/security and contract checks pass.
- Major upgrades, including Vite 6 to 8, require focused compatibility work, browser/build tests, Node/pnpm/npm matrix checks, plugin/config migration review, and explicit rollback evidence. Do not merge a major bump simply because Dependabot opened it.
- Resolve duplicate action-pin PRs so only one current qualified lineage remains.
- Preserve immutable action SHA pins and current provenance/security requirements.

## Acceptance criteria

```text
stale_open_pr_count == 0
unresolved_review_thread_count == 0
actionable_current_main_red_count == 0
ambiguous_payload_count == 0
unsigned_merge_candidate_count == 0
unqualified_major_dependency_merge_count == 0
protected_gate_bypass_count == 0
```

Founder-gated, external-infrastructure, or intentionally experimental failures may remain only with a named owner, exact dependency, current immutable evidence, and no operational-green claim.

## Deliverable

Create signed+DCO successor PRs as needed, run all relevant tests, request exact-head Codex review where available, obtain independent App attestation, and merge through protected mechanisms. Finish with the final open-PR count, current-main workflow inventory, every PR/payload disposition, merge SHAs, workflow run IDs, and residual external blockers.
