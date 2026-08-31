# GitHub Enterprise access runbook

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

This runbook explains how the additional GitHub Enterprise seats can help the
remaining cross-repo phases. It does **not** assume that buying seats alone
grants write access. The observed runtime pattern is:

- `szl-holdings/a11oy` is writable from this environment.
- sibling repos such as `.github`, `agi-forecast`, `lutar-lean`, `uds-mesh`,
  `sentra`, `amaru`, `rosie`, and `vessels` have previously returned `403`
  for direct pushes from the current bot/token context.

## What the new licenses can fix

Additional Enterprise seats can help if the blocker was seat capacity:

1. assign seats to the human or service accounts that should operate the
   ecosystem;
2. invite those accounts to `szl-holdings`;
3. ensure the invitations are accepted;
4. add the accounts or GitHub App installation to teams with repo-level write
   access.

## What the new licenses cannot fix by themselves

Seats do not automatically grant:

- write permission to sibling repos;
- SSO authorization for an existing PAT;
- GitHub App installation scope on sibling repos;
- workflow-edit permission;
- branch-protection bypass;
- accepted org membership for pending invites.

## Required access target

The current Cursor/bot or designated service account needs:

| Repo | Minimum permission | Why |
| --- | --- | --- |
| `szl-holdings/.github` | Write | Org profile, coordination, reusable workflows, issue/PR templates. |
| `szl-holdings/lutar-lean` | Write | Apply Lean kernel/proof proxy patches directly instead of via A11oy handoff. |
| `szl-holdings/agi-forecast` | Write | Apply competition-math/FG pipeline patches directly. |
| `szl-holdings/uds-mesh` | Write | Update mesh pointers, release topology, and UDS bundle indexes. |
| `szl-holdings/amaru` | Write | Receipt minting/anchor UDS component upgrades. |
| `szl-holdings/sentra` | Write | Drift/telemetry UDS component upgrades. |
| `szl-holdings/rosie` | Write | Receipt DAG / CSS ingress component upgrades. |
| `szl-holdings/vessels` | Write | Active vertical demo wedge. |
| `szl-holdings/platform` | Write | Product integration monorepo changes, if in-scope and authorized. |

## Token / app requirements

For a fine-grained PAT:

- include every target repo above;
- grant `Contents: Read and write`;
- grant `Pull requests: Read and write` if PR creation should be direct;
- grant `Workflows: Read and write` only if workflow files will be edited;
- SSO-authorize the token for `szl-holdings`.

For a GitHub App:

- install the app on every target repo;
- grant the app contents and pull-request write scopes;
- include workflow write scope only if workflow edits are required.

## Read-only checks

These checks do not modify resources:

```bash
gh auth status
gh api user -q .login
gh repo view szl-holdings/a11oy --json viewerPermission
gh repo view szl-holdings/.github --json viewerPermission
gh repo view szl-holdings/agi-forecast --json viewerPermission
gh repo view szl-holdings/lutar-lean --json viewerPermission
gh repo view szl-holdings/uds-mesh --json viewerPermission
```

If `viewerPermission` is empty, `READ`, or not present, direct write phases
remain blocked and the proxy-patch pattern stays correct.

## Live read-only audit

After seats, invitations, teams, SSO, or GitHub App installation scopes are
updated, run:

```bash
npm run github:access:live:validate
```

This writes `dist/github-access-audit.json` with the current `gh` integration's
viewer permission for each target repo. It uses only read-only `gh auth`,
`gh api user`, and `gh repo view` commands. It does not push, create PRs, edit
repos, mutate teams, or call write-method GitHub APIs.

Interpretation:

| Status | Meaning |
| --- | --- |
| `write-ready` | Current auth context reports `WRITE`, `MAINTAIN`, or `ADMIN`. Direct feature-branch work may be tried. |
| `read-only` | Repo is visible but write phases remain blocked. |
| `unavailable` | Repo cannot be inspected from this token/app context. |

## Write-readiness check

Only after permissions are updated, test by pushing a new `cursor/*-2f18`
feature branch to a sibling repo, not to `main`. Do not merge to protected
branches without explicit approval.

## Doctrine boundary

Access changes are operational plumbing. They do not change public claim status.
A sibling repo becomes “directly operational” only after:

1. patches are applied in that repo;
2. repo-native tests pass;
3. CI is green;
4. release/HF/UDS surfaces are regenerated from GitHub truth;
5. public docs avoid unsupported all-green, endorsement, or catalog claims.
