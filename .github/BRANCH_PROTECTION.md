<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
-->
# `main` branch protection — required checks and required-workflow handoff

Repository files cannot prove or change live GitHub protection settings. This
document separates ordinary status checks from the action-contract workflow
that must be enforced by an organization ruleset.

## Security boundary

A workflow triggered by `pull_request` is normally loaded from the pull
request's candidate revision. The candidate can therefore replace its steps
with a successful no-op while retaining the same job name. Checking out a
validator from the protected base does not make the workflow definition itself
immutable.

For that reason:

- `.github/workflows/action-contract-promotion-guard.yml` reports
  `Action-contract promotion qualification`, but its repository-owned run is
  advisory until GitHub binds the workflow identity through **Require workflows
  to pass before merging**.
- `.github/workflows/frontier-source-pin-authority.yml` reports
  `Protected Frontier source-pin authority` under the same control-plane
  boundary. In the externally bound required-workflow run, it executes only a
  stdlib validator loaded from `job.workflow_sha` on protected `main` and treats
  the event base and candidate payload checkout as data. GitHub's required-
  workflow engine ignores the workflow's `branches-ignore: ["**"]` filter,
  while the filter suppresses ordinary candidate-associated duplicate runs.
  Any unexpected non-`main` source still fails closed as
  `ADVISORY_UNTRUSTED`.
- Do not configure that job name as an ordinary required status context.
- Do not cite any ordinary/bootstrap result as protected enforcement.
- No merge queue is configured. Add `merge_group` only through a separately
  qualified control-plane rotation if merge queue is enabled later.
- The workflow treats the candidate checkout only as untrusted data and runs
  the action-contract validator from the protected base checkout. The Frontier
  validator runs from the immutable ruleset workflow-source checkout instead.

This is a GitHub control-plane boundary, not something a test inside the same
candidate-controlled workflow can establish.

## Frontier source-pin authority rotation

`.github/workflows/frontier-source-pin-authority-v2.yml` is the versioned
successor used to admit the exact four-file transition that repairs both
Frontier workflow pins and the v1 regression fixture. Its protected validator
accepts exactly the three pinned workflow/contract files plus
`tests/test_validate_frontier_source_pin_candidate.py`; it executes no candidate
code and holds the v1 workflow, v1 validator, repair oracle, and terminal-truth
template byte-identical to protected `main`.

Keep v1 Active while the v2 bootstrap lands on new paths. Create v2 as a
separate Evaluate ruleset with an empty bypass list, prove an exact protected
v2 PASS, then activate v2 before disabling v1. Never leave both authorities
non-enforcing. Keep the disabled v1 definition for audit history and keep v2
Active after the transition so later guarded-file changes require a v3-first
rotation.

## Ordinary required status contexts

GitHub matches ordinary required-status-check contexts by exact string. Keep
the currently enforced contexts and every non-check protection in place. When
adding more contexts, use their exact reported check-run names:

| Gate | Workflow file | Exact reported context |
| --- | --- | --- |
| Secret scanning | `gitleaks.yml` | `Gitleaks secret scan` |
| Lockfile registry hygiene | `lockfile-registry-check.yml` | `lockfiles / No lockfile references a Replit-internal registry host` |
| Anatomy-map drift | `anatomy-map-drift.yml` | `anatomy-map-drift / Anatomy map honest & in sync (locked-8 + Λ=Conjecture-1)` |
| Banned-token honesty scan | `doctrine-grep.yml` | `Banned-token scan (Doctrine v7 §1)` |
| Shared-source drift | `shared-file-drift.yml` | `Shared source files in sync with killinchu` |
| Shared-module hash lock | `shared-module-hash-lock.yml` | `Shared modules match committed SHA-256 lock` |
| Dockerfile COPY completeness | `copy-completeness-guard.yml` | `COPY completeness / import-vs-copy check` |
| Dockerfile source existence | `dockerfile-copy-guard.yml` | `COPY/ADD sources exist` |
| COPY/source/HF lockstep | `copy-sync-lockstep-guard.yml` | `COPY <-> serve.py imports <-> hf-sync mirror are in lockstep` |
| DCO | `dco.yml` | `DCO sign-off check` |
| PR-title convention | `commit-lint.yml` | `Lint PR title (Conventional Commits)` |

Verify a context before requiring it:

```bash
gh api repos/szl-holdings/a11oy/commits/<sha>/check-runs \
  --paginate --jq '.check_runs[].name' | sort -u
```

## Action-contract required-workflow handoff

After the workflow file has landed on the protected default branch, configure
the GitHub-native required workflow as follows:

1. Open **Organization settings → Repository → Rulesets**.
2. Target repository `szl-holdings/a11oy` and the default branch only.
3. Add **Require workflows to pass before merging**.
4. Select source repository `szl-holdings/a11oy`.
5. Use a separate additive ruleset for each workflow identity; do not rewrite an
   existing protection bundle. The Frontier identities are:
   - `.github/workflows/frontier-source-pin-authority.yml` (v1 audit record)
   - `.github/workflows/frontier-source-pin-authority-v2.yml` (active successor)
6. Start a new identity in **Evaluate**, verify its protected source and exact
   report, then change only enforcement to **Active**. Leave **Do not require
   workflows checks on creation** disabled and keep the bypass list empty.
7. Preserve every existing status check, signature, linear-history,
   non-fast-forward, deletion, and conversation-resolution rule.

The `series-a-default-branch` ruleset must retain
`strict_required_status_checks_policy=true`. That strict setting forces a pull
request head to be updated when `main` moves; the resulting `synchronize` event
re-runs the required workflow against the new protected base.

The workflow intentionally omits `merge_group` while no merge queue is
configured. Add and qualify that event through a control-plane rotation before
enabling a queue.

Do not substitute an ordinary required status context for the required-workflow
rule. The latter binds the source repository and workflow identity in GitHub's
control plane; a candidate-authored job name does not.

## Activation and verification

This pull request cannot certify its own newly introduced workflow as
control-plane-required. Treat its ordinary Actions run as advisory for the
one-time bootstrap. After each file exists on `main`:

1. Add the required-workflow rule in **Evaluate** mode and inspect its run.
2. Switch it to **Active** without changing the other protections.
3. For pull requests that were already open, push a new commit, update the
   branch, or close and reopen the pull request so GitHub starts the newly
   required workflow.
4. Confirm the required workflow is attached to the current PR head and that
   the protected-base validator ran.
5. Confirm the repository ruleset still reports
   `strict_required_status_checks_policy=true`.

Changing the Frontier authority workflow, its validator, or its validator
regression is a control-plane rotation. Bind and verify a versioned successor
before removing the prior required-workflow identity. Once this bootstrap is
active, the Frontier workflow repair must change exactly the two guarded
workflows and their execution contract; it cannot rotate the authority code or
either protected source input in the same pull request.

Read-only verification commands:

```bash
gh api repos/szl-holdings/a11oy/rules/branches/main
ruleset_id="$(gh api repos/szl-holdings/a11oy/rulesets \
  --jq '.[] | select(.name == "series-a-default-branch") | .id')"
gh api "repos/szl-holdings/a11oy/rulesets/${ruleset_id}"
gh api repos/szl-holdings/a11oy/commits/<sha>/check-runs
```

GitHub references:

- [Require workflows to pass before merging](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-workflows-to-pass-before-merging)
- [Strict and loose required status checks](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-status-checks-to-pass-before-merging)
