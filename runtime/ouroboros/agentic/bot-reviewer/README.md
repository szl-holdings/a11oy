<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings -->

# @szl/bot-reviewer

Doctrine V6 bot reviewer for the SZL Holdings repository. Scans changed files
in a pull request for compliance with the eight Doctrine V6 invariants and
posts a structured review comment via the `gh` CLI.

---

## What it does

On each pull request the reviewer runs every changed file through six checks:

| Check | Rule ID | Details |
|---|---|---|
| Forbidden patterns | `forbidden-pattern` | 8 patterns (see Doctrine V6); "Claude Mythos Preview" excepted |
| License allowlist | `license-allowlist` | Apache-2.0, MIT, BSD-3-Clause, CC-BY-4.0 only |
| SPDX header | `spdx-header` | `SPDX-License-Identifier: Apache-2.0` in first 5 lines of `.ts`/`.js` files |
| Lean bare sorry | `lean-bare-sorry` | Bare `sorry` on its own line in `.lean` files |
| File size cap | `file-size` | Maximum 1 MiB per file |
| Lambda gate (9-axis) | evaluated separately | All axes ≥ 0.90; `moralGrounding` and `measurabilityHonesty` ≥ 0.95 |

If all checks pass the reviewer approves the PR. Any failure blocks merge with
a detailed violation table.

---

## Install

```bash
npm install
```

---

## Run tests

```bash
npm test
```

Runs the full Vitest suite (covers all 6 check functions, edge cases, and
lambda hard-floor logic).

---

## Review a set of files manually

```bash
npx tsx src/reviewer.ts <file1> [file2 ...]
```

Exits `0` if all files are clean, `1` otherwise. Prints violations to stderr.

Example against the changed files in a local branch:

```bash
npx tsx src/reviewer.ts $(git diff --name-only origin/main...HEAD)
```

---

## Post a review to GitHub

```bash
# Pipe review result JSON to the poster
npx tsx src/reviewer.ts file1.ts file2.ts | \
  npx tsx src/github-poster.ts owner repo 42
```

Add `--dry-run` to print what would be posted without calling gh:

```bash
npx tsx src/github-poster.ts owner repo 42 --dry-run < result.json
```

`GITHUB_TOKEN` must be set in the environment. The bot account
(`szl-doctrine-bot`) token is stored as the `BOT_GITHUB_TOKEN` repository
secret and injected automatically by the GitHub Actions workflow.

---

## Wire into GitHub Actions

Copy `.github-workflows/bot-reviewer.yml` to `.github/workflows/bot-reviewer.yml`
in the target repository. The workflow file is pre-pinned to full SHAs for
supply-chain integrity.

Minimal pattern:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  doctrine-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - uses: actions/setup-node@1d0ff469b7ec7b3cb9d8673fde0c81c44821de2a
        with:
          node-version: "20"
      - run: cd 12_agentic/bot-reviewer && npm install
      - run: |
          npx tsx 12_agentic/bot-reviewer/src/reviewer.ts \
            $(git diff --name-only origin/${{ github.base_ref }}...HEAD)
        env:
          GITHUB_TOKEN: ${{ secrets.BOT_GITHUB_TOKEN }}
```

---

## Doctrine V6 axes used

The lambda gate evaluates all 9 axes defined in Doctrine V6:

| # | Axis | Floor |
|---|---|---|
| 1 | `semanticCoherence` | ≥ 0.90 |
| 2 | `empiricalGrounding` | ≥ 0.90 |
| 3 | `logicalConsistency` | ≥ 0.90 |
| 4 | `moralGrounding` | **≥ 0.95 (hard floor)** |
| 5 | `epistemicHumility` | ≥ 0.90 |
| 6 | `measurabilityHonesty` | **≥ 0.95 (hard floor)** |
| 7 | `reversibility` | ≥ 0.90 |
| 8 | `provenance` | ≥ 0.90 |
| 9 | `replayability` | ≥ 0.90 |

The conjunctive minimum of all nine axes is the overall lambda score. A run is
doctrine-clean if and only if every axis meets its threshold.

---

## Operator setup (required before first use)

1. **Create bot account** — create a GitHub user named `szl-doctrine-bot`.
2. **Add as collaborator** — grant `szl-doctrine-bot` write access to the
   target repository (`Settings → Collaborators → Add people`).
3. **Set as CODEOWNER** — add an entry to `.github/CODEOWNERS`:
   ```
   * @szl-doctrine-bot
   ```
4. **Generate a Personal Access Token** — from the `szl-doctrine-bot` account,
   create a fine-grained PAT with `pull_requests: write` scope on the target
   repo.
5. **Add `BOT_GITHUB_TOKEN` secret** — in the target repo go to
   `Settings → Secrets and variables → Actions → New repository secret`,
   name it `BOT_GITHUB_TOKEN`, paste the PAT.
6. **Copy the workflow file**:
   ```bash
   cp 12_agentic/bot-reviewer/.github-workflows/bot-reviewer.yml \
      .github/workflows/bot-reviewer.yml
   git add .github/workflows/bot-reviewer.yml
   git commit -m "ci: add Doctrine V6 bot-reviewer workflow"
   ```

---

## License

Apache-2.0 — © 2026 Lutar, Stephen P. — SZL Holdings
