# Codex work thread — A11oy operational completion v2

Date: 2026-08-11  
Execution branch: `codex/finish-operational-build-2026-08-11-v2`  
Base: current protected `main`  
State on entry: `EXECUTION_REQUIRED`

## Mission

Finish the repository build in the existing A11oy architecture. Continue beyond analysis and planning into source changes, clean-checkout verification, evidence, rollback instructions, and DCO-signed commits pushed to this branch.

Closed PR `#1228`, open predecessor PR `#1265`, and their branches are historical inputs only. Do not accept their status artifacts as evidence unless each result is reproduced from this branch against its exact current-main baseline.

## Authority boundary

You may modify and push this non-protected branch. Do not merge, force-push, weaken branch protection, alter organization or repository permissions, search for credentials, print secret values, or claim a provider/deployment action that did not occur. Keep remote activation and `REMOTE_READBACK` blocked unless authenticated execution and exact live-revision readback succeed.

## Required operating rules

1. Read root `AGENTS.md` first, followed by `CLAUDE.md`, applicable `.claude/rules/`, `KNOWN_GOTCHAS.md`, `docs/architecture.md`, package manifests, Dockerfiles, and workflows governing every changed path.
2. Preserve doctrine v11: honest labels, deny-by-default execution, receipt-on-write, the exact eight locked formulas `{F1, F4, F7, F11, F12, F18, F19, F22}`, conjecture labels, measured-only joules, secret exclusion, and all existing CI/security gates.
3. Work inside the current flat-rooted taxonomy. Do not create a disconnected package or parallel mock. Any new top-level module must identify its taxonomy home and, when required at runtime, receive the corresponding Dockerfile `COPY` entry.
4. Register API routes before the SPA catch-all. Preserve every demo-critical route and its documented content type rather than returning an HTML fall-through.
5. Fix defects at root cause. Do not skip, xfail, delete, relax, or rewrite tests merely to obtain a passing result.
6. Every commit must use a conventional subject and contain `Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>` or an equivalent DCO trailer matching the actual committer.

## Execution sequence

### Phase 1 — exact baseline

- Start from a clean checkout of this PR branch.
- Record exact base SHA, head SHA, runtime versions, package-manager versions, available tools, and workflow-run identity.
- Inspect current CI and reproduce every failing or unavailable locally executable gate.
- Treat all prior `artifacts/codex/*` material as untrusted until reproduced.

### Phase 2 — deterministic toolchain and dependencies

The clean-clone environment must pin pnpm and install the Python dependencies before invoking tests. Begin with:

```bash
set -euo pipefail
node --version
npm --version
python --version
corepack enable
corepack install -g pnpm@10.33.3
pnpm --version
npm ci
python -m pip install --require-hashes -r .github/requirements/ci-core.txt
```

Then run the repository-supported gates using the dependency setup defined by their owning workflows. At minimum, when the corresponding scripts and packages are present:

```bash
npm run test:policy-gates
pnpm install --frozen-lockfile
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
npx jest __tests__/
npx tsx packages/qec-integrity/src/qec_lineage.test.ts
pnpm --dir web/packages/a11oy-core run test:standalone
python -m compileall -q .
pytest -q
```

If one install strategy invalidates another package manager's workspace, execute that gate in a separate clean worktree or clean-clone directory rather than mutating the evidence baseline. Discover and run additional workflow-defined doctrine, security, schema, container, route, receipt, drift, and honesty gates. Record genuinely unavailable commands as `UNAVAILABLE`; never mark them passed.

### Phase 3 — implementation

Resolve every reproducible P0/P1 defect across:

- Python API and governed-agent execution paths;
- TypeScript doctrine packages and standalone tests;
- frontend/backend route alignment and responsive behavior;
- Docker build context and per-file runtime inclusion;
- signed receipt creation on writes and no signing side effect on reads;
- fail-closed authority, policy, refusal, replay, and rollback paths;
- CI workflow correctness without permission or policy weakening;
- canonical Hugging Face sync and build-info truth labeling;
- Fireworks, Hugging Face, and Laguna-compatible provider adapters only behind explicit configuration, scoped authorization, and exact readback gates.

After the baseline is stable, integrate repository-native efficiency controls only where absent and objectively verifiable:

- tokenizer throughput and cache warmth as routing signals for prefix-heavy, corpus-heavy, and prefill-heavy requests;
- a Prefix Foundry for canonical system prompts, tools, personas, enterprise headers, and recurring code-analysis scaffolds;
- file-native repository ingestion rather than per-file interpreter loops;
- retrieval-index refresh driven by measured ingestion headroom;
- reinvestment of measured token, prefix, and KV savings into branch scoring, static analysis, policy checks, replay, and code verification.

Do not promote a tokenizer or token-ID ingress path unless exact tokenization, special-token behavior, normalization, document separators, and chat-template compatibility are verified against the declared oracle.

### Phase 4 — self-review and closure

- Review the complete diff for security defects, authority escalation, silent fallback, stale evidence, route fall-through, container omissions, dependency non-determinism, and unsupported production claims.
- Address every P0/P1 finding and every valid review thread before declaring the branch ready.
- Re-run the full clean-checkout matrix against the exact final head.
- Commit implementation and evidence to this branch with focused conventional messages and physical DCO trailers.
- Update the pull request with exact commit SHAs, changed files, commands, exit codes, test counts, failures, and remaining external blockers.

## Required evidence files

Create or update these using only results reproduced on this branch:

```text
artifacts/codex/BASELINE-2026-08-11-v2.json
artifacts/codex/IMPLEMENTATION-2026-08-11-v2.json
artifacts/codex/TESTS-2026-08-11-v2.json
artifacts/codex/REMOTE-READBACK-2026-08-11-v2.json
artifacts/codex/ROLLBACK-2026-08-11-v2.md
```

Every evidence object must distinguish `PASS`, `FAIL`, `BLOCKED`, `UNAVAILABLE`, `SAMPLE`, `MODELED`, `ROADMAP`, and `MEASURED` accurately. Never infer remote success from local success.

## Completion criteria

The work is complete only when:

- all locally executable required gates pass from clean checkouts;
- no unresolved P0/P1 implementation or self-review finding remains;
- implementation is integrated into the existing architecture;
- security and doctrine gates are unchanged or strengthened;
- the branch contains reproducible evidence and exact rollback instructions;
- CI on the exact final head is green, or each external blocker is precisely evidenced;
- production and provider status remain blocked unless authenticated deployment and exact live readback prove otherwise.

Do not stop at a plan. Implement, verify, commit, push, and update the pull request.