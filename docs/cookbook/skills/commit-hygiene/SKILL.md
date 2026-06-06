---
name: commit-hygiene
description: Guidelines for writing clear commit messages, keeping PRs focused, and maintaining a clean git history in this monorepo. Use when preparing commits, writing PR descriptions, or reviewing commit history for a feature. Adapted from Awesome Claude Code git hygiene patterns.
---

# Commit Hygiene

Well-scoped commits and clear messages make code review faster, rollbacks safer, and blame history useful. Apply these rules when preparing any commit in this monorepo.

## Commit Message Format

Use the Conventional Commits format:

```
<type>(<scope>): <short summary in imperative mood>

[optional body — what changed and why, not how]

[optional footer: BREAKING CHANGE, Closes #issue]
```

### Types

| Type | When to Use |
|------|------------|
| `feat` | New user-facing feature |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `perf` | Performance improvement |
| `style` | Formatting, whitespace, no logic change |
| `test` | Adding or updating tests |
| `chore` | Build config, dependency bumps, tooling |
| `docs` | Documentation only |

### Scopes (this project)

Use the artifact or package slug: `szl-holdings`, `command`, `pulse`, `shared`, `api-server`, `mobile`, `sentra`, `aegis`, `counsel`, `terra`, etc.

### Examples

```
feat(command): add tenant filter to support queue

fix(api-server): return 404 instead of 500 for missing tenant

refactor(shared): extract formatCurrency into shared utils

chore: bump vite from 5.1.0 to 5.2.0
```

## Commit Scope Rules

- **One logical change per commit.** If you catch yourself writing "and" in a commit message, split it.
- **Do not mix refactoring with feature work.** Separate cleanup commits make bisect reliable.
- **Do not commit commented-out code, debug logs, or `console.log` left from debugging.**
- **Keep `package.json` and lockfile changes in their own commit** if they are not directly required by the feature commit.

## PR Description Template

```markdown
## What
[1–3 sentences: what this PR does]

## Why
[1–3 sentences: the problem it solves or the request it fulfils]

## How
[Optional: non-obvious implementation decisions]

## Testing
[How you verified this works — manual steps or test names]

## Screenshots
[Required for UI changes]
```

## When to Squash vs. Preserve History

- **Squash** a series of "WIP", "fix typo", "oops" commits before merging — they add noise.
- **Preserve** individual commits when each commit is a meaningful, deployable unit (e.g., a migration followed by the API change that uses it).
