# P0 — Current-main production completion

## Authority and source

- Repository: `szl-holdings/a11oy`
- Starting protected-main revision: `90ed8c7289efbda085d82f0dc60cf821b22f5caf`
- Current protected source and `AGENTS.md` are authoritative.
- This task supersedes old drift scripts, old task payloads, and old SHA assumptions when they conflict with current source.
- Work only on this task PR branch. Do not write directly to `main`.

## Mission

Finish the currently implementable source work required to make a11oy one coherent, state-native, investor-ready, operationally honest product. Do not return another roadmap. Inspect, edit, test, and leave the complete source repair on this branch.

## Required work

### 1. Establish current truth before editing

Read `AGENTS.md`, `KNOWN_GOTCHAS.md`, `docs/architecture.md`, current open issues, current workflow definitions, and every repository-native task/payload file. Establish from current evidence:

- protected-main source identity;
- canonical Hugging Face writer and source-binding contract;
- current `/api/build-info`, `/readyz`, `/healthz`, and readiness-harness contracts;
- current CEO/control-center routes and their API dependencies;
- current Dockerfile `COPY` coverage and route registration order;
- current state-native runtime, persistent-state, receipt, verifier, adapter, tokenizer, and deployment gates.

Classify every discovered payload as one of:

- `APPLIED_AND_VERIFIED`
- `SUPERSEDED_BY_NEWER_SOURCE`
- `ALREADY_SATISFIED`
- `BLOCKED_EXTERNAL_AUTHORITY`

Do not replay an older patch against a newer architecture.

### 2. Close real source gaps

Implement every current source-level gap you can reproduce in these areas:

- the full-viewport CEO/control-center console and every owned mobile/tablet/desktop state;
- demo-critical route and API registration before the SPA catch-all;
- Dockerfile inclusion for every runtime module and static asset used by changed routes;
- bounded loading, empty, unavailable, degraded, denied, and error states;
- state-native memory, kernel routing, verifier, policy, receipt, and durable-work visibility;
- exact source/build/runtime identity presentation without stale hard-coded counts;
- canonical `hf-sync.yml` and readiness contracts, with one automatic Space writer only;
- investor/developer language that preserves honest labels and does not overstate production, customers, proofs, energy, or model promotion.

When current source is already correct, add no cosmetic churn. Prove the contract with focused regressions instead.

### 2a. Qualify state and ingress efficiency after the baseline is stable

Implement these only where the current repository lacks them and each claim can be reproduced:

- use tokenizer throughput and cache warmth as bounded routing signals for prefix-heavy, corpus-heavy, and prefill-heavy work;
- build a Prefix Foundry for canonical system prompts, personas, tools, enterprise headers, and recurring code-analysis scaffolds;
- perform repository ingestion as a file-native batch path rather than a per-file interpreter loop;
- refresh retrieval indexes only from measured ingestion headroom;
- track prefix reuse and KV reuse together;
- reinvest measured token, prefix, and KV savings into branch scoring, static checks, policy checks, replay, counterexamples, and code verification rather than claiming speed alone.

Do not promote an alternate tokenizer, zero-copy token-ID path, or cache contract unless token IDs, normalization, special-token behavior, document separators, and chat-template behavior match the declared semantic oracle on representative repository data. Record mismatches and fail closed.

### 3. Qualification

Use the deterministic environment contract in `.codex/CODEX_CLOUD_ENVIRONMENT_20260811.md`, then run the exact applicable commands from `AGENTS.md` and the repository workflows. At minimum cover:

- Python compilation for changed Python files;
- focused Python tests for changed routes/services;
- demo-critical route tests;
- Dockerfile/source inclusion checks;
- doctrine and honest-status checks;
- relevant Jest/Vitest/pnpm tests for changed UI or packages;
- route QA when routes change;
- responsive browser checks at 320, 390, 768, 1366, and 1728 CSS pixels for changed public UI;
- `git diff --check`;
- secret scan of the final diff.

Do not weaken, skip, delete, or relabel a failing gate to create a green result.

### 4. Evidence and handoff

Update this file before finishing with:

- exact files changed;
- root causes fixed;
- commands and outcomes;
- payload dispositions;
- exact remaining external blockers;
- explicit non-claims.

Create or update a concise Proof Packet under the repository’s existing audit/evidence convention. Do not commit screenshots that were not captured from a real running surface.

## Hard boundaries

- No force push or history rewrite.
- No direct protected-main write.
- No administrator merge bypass or self-approval.
- No secret retrieval, display, copying, rotation, or mutation.
- No training, Nemo attempt, adapter/weight promotion, or GPU claim.
- No Hugging Face publication or production-deployment claim from this task.
- No `MEASURED` energy claim without a fresh real exporter delta.
- Lambda uniqueness remains Conjecture 1; Khipu BFT safety remains Conjecture 2.
- Preserve exact-head protected checks and independent review as merge authority.

## Definition of done for this Codex task

The branch contains tested source changes or a proof-backed `ALREADY_SATISFIED` result; this task file and Proof Packet are updated; no actionable reproducible source defect in scope is left as a roadmap item; and all unavailable production/provider facts are named as external blockers rather than painted green.

---

## Execution update — 2026-08-11

### Exact work now applied

- `migrations/20260811_memory_covenant_v2.sql` — initial PostgreSQL-authoritative Memory Covenant v2 schema.
- `migrations/20260811_memory_covenant_v2_security_hardening.sql` — explicit non-bypass runtime role, dedicated worker capability, bounded outbox leasing, and public-execute revocation.
- `audit/P0-2026-08-11-memory-covenant-proof.md` — real isolated Neon acceptance evidence with no credential material.

### Root cause fixed

The provider-managed Neon migration owner has `rolbypassrls=true`, so an owner-session cross-domain probe returned one row even with forced RLS. That result was not accepted as runtime isolation proof. A dedicated `a11oy_memory_app` role was added as `NOBYPASSRLS`, permissions were reduced to the runtime contract, and isolation was rerun under that role.

### Real acceptance outcomes

On isolated Neon project `young-snow-70923323`, branch `br-bitter-block-a6kuzqxt`, database `neondb`:

- seven governed memory tables created;
- RLS enabled on every memory table;
- intended forced-RLS posture observed;
- append-only triggers observed on receipts, query audit, and idempotency;
- dedicated app and worker roles observed as non-superuser and non-RLS-bypass;
- same-domain application-role visibility: `1` row;
- cross-domain application-role visibility: `0` rows;
- cross-domain write rejected;
- receipt mutation intercepted and original value preserved;
- acceptance rows rolled back; residue: `0`.

Database-side disposition: `APPLIED_AND_VERIFIED`.

### Payload dispositions established so far

- Memory Covenant PostgreSQL schema: `APPLIED_AND_VERIFIED` on the isolated acceptance database.
- Memory Covenant role/RLS hardening: `APPLIED_AND_VERIFIED` on the isolated acceptance database.
- Older owner-session RLS assumption: `SUPERSEDED_BY_NEWER_SOURCE` because provider-owner `BYPASSRLS` is not a valid runtime test identity.
- Codex Cloud handoff: `BLOCKED_EXTERNAL_AUTHORITY` until a repository Codex environment exists; this does not block direct repository work through the authenticated GitHub connector.

### Remaining exact blockers

The overall P0 task is not complete yet. Remaining work is source/runtime and protected-release authority, specifically:

- bind the application runtime to a non-bypass PostgreSQL login/member of `a11oy_memory_app` without committing credentials;
- wire the Memory Covenant runtime API before the SPA catch-all;
- include the runtime database dependency and all changed modules in the canonical container;
- implement/qualify the bounded index-worker path against a declared embedding/index generation rather than claiming derived-index completion;
- run final exact-head repository gates and responsive route checks for any changed public surface;
- promote through a separately signed+DCO successor lineage, independent review, protected merge, canonical Hugging Face writer, and immutable deployed-SHA readback.

### Explicit non-claims

No protected-main merge, production deployment, Hugging Face publication, signing-key operation, model training, GPU inference, measured-energy claim, or live production-parity claim is made by this execution update.
