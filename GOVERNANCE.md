# Governance

A11oy is sponsored and maintained by **SZL Holdings, LLC**. This document describes who decides what, the response SLA you can expect, and how the maintainer roster changes.

## Roles

| Role | Who | What they can do |
|---|---|---|
| **Project Lead** | Stephen Z. Lopez (`@szl`) | Final say on doctrine, license, releases, signing keys, roadmap |
| **Maintainer** | Listed in [`.github/CODEOWNERS`](./.github/CODEOWNERS) | Triage, review, merge in Lane A; approve `core:accept-pr` labels |
| **Contributor** | Anyone with a merged commit | Open issues, open PRs in Lane A, request reviews |
| **Downstream operator** | E.g. Defense Unicorns republishing A11oy under their own signing key | Owns their fork end-to-end; upstream issues welcome; see [`docs/FORKING.md`](./docs/FORKING.md) |

## Decision SLAs (best effort, calendar days)

| Action | Response SLA |
|---|---|
| Acknowledge a new issue (triage label + comment) | 3 days |
| Decide whether a core PR is wanted (`core:accept-pr`) | 7 days |
| First review on a Lane A PR | 5 days |
| Security advisory acknowledgement | 2 days |
| Doctrine question response (first substantive reply) | 7 days |

We do not run a "stale bot." If an issue has stalled past these SLAs, please comment on the issue or email `stephen@szlholdings.com`.

## How decisions are made

- **Lazy consensus.** Any maintainer may approve and merge a Lane A PR that passes CI and is uncontested for 48 hours after review.
- **Doctrine changes** (anything touching `packages/a11oy-core/`) require Project Lead sign-off in addition to a maintainer review. The doctrine pre-flight checklist in [`CONTRIBUTING.md`](./CONTRIBUTING.md) must be green.
- **Release cuts** (new `uds-vX.Y.Z` tag) are signed by the Project Lead's cosign key. Downstream operators re-sign with their own key — see [`docs/FORKING.md`](./docs/FORKING.md).
- **License changes** are exclusively a Project Lead decision and require notice on the issue tracker 30 days in advance.

## Becoming a maintainer

You become a maintainer by doing the work, not by asking. The path:

1. Land 3+ non-trivial Lane A PRs reviewed by an existing maintainer.
2. Triage at least 10 issues (label, ask the right clarifying questions, close obvious dupes).
3. Show up on at least one doctrine question with a substantive, cited response.
4. An existing maintainer nominates you on a tracking issue. Project Lead confirms.

Maintainer status can be relinquished at any time and is reviewed annually for activity.

## Forks and downstream catalogs

If your organization (e.g. a UDS catalog operator) forks A11oy and republishes it under your own signing key:

- You own your fork's release cadence, signing key, and support model.
- You may open upstream issues; we will engage on doctrine and on bugs reproducible against the upstream release.
- You are not obligated to upstream changes. If you choose to, the standard contribution lanes apply.
- Trademark "A11oy" remains with SZL Holdings, LLC. Your fork should use a distinct name for distribution (e.g. "Org-A11oy" or "A11oy-Org").

See [`docs/FORKING.md`](./docs/FORKING.md) for the operational playbook.
