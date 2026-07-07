<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
-->
# `main` branch protection — required-status-check contexts (recommendation)

> **This is a RECOMMENDATION for the founder.** This PR does **not** change any
> protection rule (that requires admin scope and a human decision). It documents
> the correct, string-exact required-status-check **contexts** so the trunk
> stays honestly green and unattended admin-merges stop tripping on a
> never-reported check.

## Why this doc exists — the `anatomy-map-drift` context mismatch

GitHub matches required-status-check **contexts by exact string**. A required
context that never string-matches an actual reported check-run is treated as
*"expected, but never arrives"* — it blocks merges (or, with admin-merge, trips
the unattended path) even when every real check is green.

The current `main` protection requires exactly one context:

```
anatomy-map-drift
```

But `anatomy-map-drift` is a **reusable-workflow caller job** (it `uses:`
`szl-holdings/.github/.github/workflows/reusable-anatomy-map-drift.yml`). For a
caller job, GitHub composes the reported check-run name as
`<caller-job-id> / <reusable-job-name>`. The reusable workflow's job carries
`name: Anatomy map honest & in sync (locked-8 + Λ=Conjecture-1)`, so the check
that actually appears on every commit is:

```
anatomy-map-drift / Anatomy map honest & in sync (locked-8 + Λ=Conjecture-1)
```

The bare `anatomy-map-drift` context therefore **never matches**. Verified on a
commit that ran the workflow (a11oy@8117c631):

- Reported check-run name: `anatomy-map-drift / Anatomy map honest & in sync (locked-8 + Λ=Conjecture-1)` ✅
- Required context configured: `anatomy-map-drift` ❌ (no such check name is ever reported)

## Correct required contexts (string-exact)

Set the required contexts to the **exact reported check-run names** (the job
`name:` fields, and for reusable callers the composed `caller / reusable-name`):

| Gate (what it protects)                         | Workflow file                         | **Required context (exact string)** |
|-------------------------------------------------|---------------------------------------|-------------------------------------|
| Banned-token / honesty scan (Doctrine v7 §1)    | `doctrine-grep.yml`                    | `Banned-token scan (Doctrine v7 §1)` |
| Shared-source drift vs killinchu                | `shared-file-drift.yml`               | `Shared source files in sync with killinchu` |
| Shared-module SHA-256 hash lock                 | `shared-module-hash-lock.yml`         | `Shared modules match committed SHA-256 lock` |
| Anatomy-map drift (locked-8 + Λ=Conjecture-1)   | `anatomy-map-drift.yml` (reusable)    | `anatomy-map-drift / Anatomy map honest & in sync (locked-8 + Λ=Conjecture-1)` |
| Dockerfile COPY-completeness (import↔COPY)      | `copy-completeness-guard.yml`         | `COPY completeness / import-vs-copy check` |
| Dockerfile COPY/ADD sources exist               | `dockerfile-copy-guard.yml`           | `COPY/ADD sources exist` |
| COPY↔serve.py↔hf-sync lockstep                  | `copy-sync-lockstep-guard.yml`        | `COPY <-> serve.py imports <-> hf-sync mirror are in lockstep` |
| DCO sign-off                                     | `dco.yml`                             | `DCO sign-off check` |
| Conventional-Commits PR-title lint               | `commit-lint.yml`                     | `Lint PR title (Conventional Commits)` |

The single most important fix: **replace** the bare `anatomy-map-drift` context
with the composed string above, and **add** the two gates that were recently
red on `main` but are not currently required — `Banned-token scan (Doctrine v7 §1)`
and `Shared source files in sync with killinchu` — so a future regression on
either is *blocking*, not merely informational.

### How to verify a context string before requiring it

The reported check-run names for any commit are authoritative:

```bash
gh api repos/szl-holdings/a11oy/commits/<sha>/check-runs \
  --paginate --jq '.check_runs[].name' | sort -u
```

Require **only** strings that appear verbatim in that list. This avoids the
"phantom required check" that the bare `anatomy-map-drift` context created.
(A repo-side guard for this class already exists: `phantom-required-check-guard.yml`.)

## Applying the change (founder / admin, GitHub UI or API)

Settings → Branches → `main` → *Require status checks to pass before merging* →
edit the checklist to the exact strings above. Or via API (admin token):

```bash
gh api -X PATCH repos/szl-holdings/a11oy/branches/main/protection/required_status_checks \
  -f strict=false \
  -f 'contexts[]=Banned-token scan (Doctrine v7 §1)' \
  -f 'contexts[]=Shared source files in sync with killinchu' \
  -f 'contexts[]=Shared modules match committed SHA-256 lock' \
  -f 'contexts[]=anatomy-map-drift / Anatomy map honest & in sync (locked-8 + Λ=Conjecture-1)' \
  -f 'contexts[]=COPY completeness / import-vs-copy check' \
  -f 'contexts[]=COPY/ADD sources exist' \
  -f 'contexts[]=COPY <-> serve.py imports <-> hf-sync mirror are in lockstep' \
  -f 'contexts[]=DCO sign-off check' \
  -f 'contexts[]=Lint PR title (Conventional Commits)'
```

Keep `enforce_admins=true` and `required_approving_review_count>=1` (already
set) so the **no-self-merge / human-merge** doctrine holds.

## Optional: enable GitHub merge queue (what top tech does)

A merge queue re-tests each PR against the *latest* `main` just before merge, so
the "green on stale base" ordering hazard — the exact class that reddened this
trunk (a11oy updated a shared module before killinchu's sibling sync landed) —
cannot land a broken trunk. Recommended settings:

- Settings → Branches → `main` → *Require merge queue*.
- Merge method: **Squash** (matches the current linear-ish history).
- Build concurrency 1–2; require the same status contexts listed above.
- Keep *Require branches to be up to date before merging* handled by the queue
  (so `strict` on the protection rule can stay `false` and avoid manual rebase
  churn).

This is additive and low-risk: it does not weaken any honesty/security gate; it
only guarantees each gate is evaluated against the real post-merge tree.
