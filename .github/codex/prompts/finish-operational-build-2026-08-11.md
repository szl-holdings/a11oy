# Codex work thread — A11oy operational completion

Date: 2026-08-11  
Execution branch: `codex/finish-operational-build-2026-08-11`  
Base: current `main`  
State on entry: `EXECUTION_REQUIRED`

## Mission

Finish the repository build in the existing A11oy architecture. Continue beyond analysis and planning into source changes, tests, evidence, rollback instructions, and commits on this branch.

The closed PR `#1228` and branch `codex/finish-operational-build-2026-07-28` are historical inputs only. Do not accept their status artifacts as evidence unless the results are reproduced from this branch against the current `main` baseline.

## Authority boundary

You may modify and push this non-protected branch. Do not merge, force-push, weaken branch protection, alter organization or repository permissions, search for credentials, print secret values, or claim a provider/deployment action that did not occur. Keep remote activation and `REMOTE_READBACK` blocked unless authenticated execution and exact live-revision readback actually succeed.

## Required operating rules

1. Read root `AGENTS.md` first, then `CLAUDE.md`, `.claude/rules/`, `KNOWN_GOTCHAS.md`, `docs/architecture.md`, package manifests, Dockerfiles, and GitHub workflows relevant to changed code.
2. Preserve doctrine v11: honest labels, deny-by-default execution, receipt-on-write, the exact eight locked formulas `{F1, F4, F7, F11, F12, F18, F19, F22}`, conjecture labels, measured-only joules, secret exclusion, and existing CI/security gates.
3. Work inside the current flat-rooted taxonomy. Do not create a disconnected package or parallel mock implementation. Any new top-level module must identify its taxonomy home and, when required at runtime, receive the corresponding Dockerfile `COPY` entry.
4. Register API routes before the SPA catch-all. Preserve all demo-critical routes and return the documented content type rather than an HTML fall-through.
5. Fix defects at root cause. Do not skip, xfail, delete, relax, or rewrite tests merely to obtain a passing result.

## Execution sequence

### Phase 1 — clean baseline

- Start from a clean checkout of this PR branch.
- Record the exact base SHA, head SHA, runtime versions, package-manager versions, and available tools.
- Inspect current CI and reproduce every failing or unavailable locally executable gate.
- Treat the prior `artifacts/codex/*` material as untrusted until reproduced.

### Phase 2 — install and build

Run the repository-supported clean-clone path. At minimum, when the corresponding files are present:

```bash
corepack enable
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

Discover and run additional workflow-defined security, schema, container, route, receipt, and honesty gates. Report commands that are genuinely unavailable without marking them passed.

### Phase 3 — implementation

Resolve all reproducible P0/P1 defects across:

- Python API and governed-agent execution paths;
- TypeScript doctrine packages and standalone tests;
- frontend/backend route alignment;
- Docker build context and per-file runtime inclusion;
- signed receipt creation on writes and no signing side effect on reads;
- fail-closed authority, policy, and refusal paths;
- durable rollback instructions and exact pre/post-state evidence;
- CI workflow correctness without permission or policy weakening;
- canonical Hugging Face sync and build-info truth labeling;
- provider adapters for Fireworks, Hugging Face, and Laguna-compatible inference only behind explicit configuration and authorization gates.

After the baseline is green, integrate the repository-native performance controls where they are absent and can be verified:

- tokenizer throughput and cache warmth as routing signals for prefix-heavy, corpus-heavy, and prefill-heavy requests;
- a Prefix Foundry for canonical system prompts, tools, personas, enterprise headers, and recurring code-analysis scaffolds;
- file-native repository ingestion rather than per-file interpreter loops;
- retrieval-index refresh triggered by measured ingestion headroom;
- reinvestment of measured token/prefix/KV savings into branch scoring, static analysis, policy checks, replay, and code verification.

Do not promote a tokenizer or token-ID ingress path unless exact tokenization, special-token behavior, and chat-template compatibility are verified against the repository's declared oracle.

### Phase 4 — self-review and closure

- Review the complete diff for security, authority escalation, silent fallback, stale evidence, route fall-through, container omissions, and unsupported production claims.
- Address every P0/P1 finding before declaring the branch ready.
- Re-run the full clean-checkout test matrix.
- Commit implementation and evidence to this branch with focused commit messages.
- Post a PR update containing exact commit SHAs, changed files, commands, exit codes, test counts, failures, and external blockers.

## Required evidence files

Create or update these on the branch using only reproduced results:

```text
artifacts/codex/BASELINE-2026-08-11.json
artifacts/codex/IMPLEMENTATION-2026-08-11.json
artifacts/codex/TESTS-2026-08-11.json
artifacts/codex/REMOTE-READBACK-2026-08-11.json
artifacts/codex/ROLLBACK-2026-08-11.md
```

Every evidence object must distinguish `PASS`, `FAIL`, `BLOCKED`, `UNAVAILABLE`, `SAMPLE`, `MODELED`, `ROADMAP`, and `MEASURED` accurately. Never infer remote success from local success.

## Completion criteria

The task is complete only when:

- all locally executable required gates pass from a clean checkout;
- no unresolved P0/P1 self-review finding remains;
- implementation is integrated into the existing architecture;
- security and doctrine gates are unchanged or strengthened;
- the branch contains reproducible evidence and rollback instructions;
- CI on the exact head SHA is green, or any external blocker is documented with precise evidence;
- production and provider status remain blocked unless authenticated deployment and exact live readback prove otherwise.

Do not stop at a plan. Implement, verify, commit, and update the pull request.