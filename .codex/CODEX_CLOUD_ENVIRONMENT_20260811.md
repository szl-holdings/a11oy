# Codex Cloud environment — A11oy P0 production completion

This file is the exact workspace configuration for the canonical implementation lane in PR #1261.

## Identity

```text
Environment name: a11oy-p0-current-main-20260811
Repository:       szl-holdings/a11oy
Default branch:   main
Task PR:          #1261
Work branch:      codex/p0-a11oy-work-20260811
Task contract:    .codex/tasks/P0_CURRENT_MAIN_PRODUCTION_COMPLETION_20260811.md
```

The environment must use the repository's current protected `main` as source truth. PR #1261 is the only active Codex implementation lane for this task. Do not reopen or reuse older task PRs.

## Setup script

```bash
set -euo pipefail

python3 --version
git --version
node --version

corepack enable
corepack prepare pnpm@10.26.1 --activate
pnpm --version

pnpm install --frozen-lockfile

if [ -f requirements.txt ]; then
  python3 -m pip install --disable-pip-version-check -r requirements.txt
fi

if [ -f requirements-dev.txt ]; then
  python3 -m pip install --disable-pip-version-check -r requirements-dev.txt
fi

python3 -m compileall -q .
```

Do not weaken lockfile or supply-chain policy to make setup pass. When a dependency install fails, record the exact failure and repair the repository contract rather than bypassing it.

## Agent internet policy

Keep agent-phase internet disabled unless a current task step requires read-only production or provider verification. When enabled, use the narrowest allowlist that supports the work:

```text
api.github.com
github.com
registry.npmjs.org
pypi.org
files.pythonhosted.org
a-11-oy.com
a11oy.net
huggingface.co
```

Prefer `GET`, `HEAD`, and `OPTIONS`. Source implementation on PR #1261 does not authorize provider mutation, deployment, or Hugging Face publication.

## Secrets and authority

No secret is required for the source implementation task. Do not add or expose production signing material, GitHub tokens, Hugging Face tokens, deployment credentials, or model-provider credentials to the agent phase. Protected workflows may consume managed repository/environment secrets after a separately reviewed successor PR reaches the normal release path.

## Mandatory startup prompt

After creating this environment, invoke Codex on PR #1261 with:

```text
@codex implement and test `.codex/tasks/P0_CURRENT_MAIN_PRODUCTION_COMPLETION_20260811.md` on this exact PR branch. Read root and scoped AGENTS.md files first. Rebase the task analysis on current protected main, reproduce current gaps, edit the real source, run every applicable repository gate, update the task disposition and Proof Packet, and push the complete tested implementation to `codex/p0-a11oy-work-20260811`. Do not return another roadmap. Do not merge, deploy, force-push, expose secrets, weaken gates, train models, publish to Hugging Face, or claim production parity.
```

## Completion boundary

Codex completion on PR #1261 means tested source changes and a proof-backed disposition are present on the work branch. It does not authorize merging this unsigned seed lineage. Promotion remains a separate signed+DCO successor PR with exact-head checks, independent review, protected merge, deployment, and immutable readback.
