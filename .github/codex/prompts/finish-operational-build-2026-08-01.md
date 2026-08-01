# Codex execution contract — finish the A11oy operational build

**Target repository:** `szl-holdings/a11oy`  
**Base branch:** `main`  
**Task branch:** `codex/finish-operational-build-2026-07-28`  
**Task class:** implementation, integration, verification, protected delivery  
**Owner authorization:** source changes and branch updates are authorized; direct default-branch writes, force-pushes, self-merge, secret disclosure, and fabricated production claims are not.

## Mission

Finish the A11oy build in the repository's real architecture. Do not merely copy a demo, publish a plan, or restate an audit. Implement, test, repair, and leave this branch in a reviewable state.

The repository's existing root `AGENTS.md` is authoritative. Read it first and obey its doctrine, test commands, route constraints, shared-module hash lock, Docker `COPY` requirements, and honest evidence labels. This task adds execution priorities; it does not weaken existing rules.

The original Action Assurance generator supplied by the owner is preserved at:

`.github/codex/payloads/action-assurance/PAYLOAD_MASTER_ACTION_ASSURANCE_2026-07-27.py.txt`

Treat that file as provenance and requirements input, not proof that remote execution already occurred. It explicitly labels itself `RESEARCH-COMPLETE, EXECUTION-PENDING`.

## Start here

```bash
git status --short
git log -1 --oneline
```

Inspect, at minimum:

```text
AGENTS.md
README.md
docs/architecture.md
KNOWN_GOTCHAS.md
Dockerfile
serve.py
.github/workflows/
.shared_module_hashes.json
package.json
pnpm-workspace.yaml
.github/codex/payloads/action-assurance/PAYLOAD_MASTER_ACTION_ASSURANCE_2026-07-27.py.txt
```

Create or update a concise `PLANS.md` execution plan, but do not stop after planning. Continue through implementation and verification in the same task.

## Source-of-truth rules

1. Integrate into current code; do not overwrite newer repository work blindly.
2. Preserve current functionality and all demo-critical routes.
3. Never convert `MODELED`, `ROADMAP`, `SAMPLE`, `DEGRADED`, `DIVERGENT`, `UNAVAILABLE`, or stale evidence into green operational claims.
4. A successful HTTP response is not deployment provenance. Source SHA, image/build identity, runtime revision, signer state, and readback must agree before claiming `VERIFIED`.
5. Never commit credentials, private signing material, tokens, generated secrets, or captured environment values.
6. Keep custom-license or remote-code models reference-only until immutable revision, license, code, data-rights, capacity, evaluation, approval, and rollback gates close.
7. Prefer one canonical truth system over parallel dashboards, registries, or status APIs.

## P0 implementation sequence

### 1. Reconcile the repository

Map the actual build graph, route registration, frontend entry points, CI gates, container assembly, deployment path, signing modes, evidence stores, and current failures. Record reproducible findings in `artifacts/codex/BASELINE.json`.

### 2. Operationalize Action Assurance

Implement or consolidate the following invariants in the existing architecture:

- explicit evidence labels with no automatic promotion;
- non-increasing delegated authority;
- fail-closed action gating;
- verifiable success and refusal receipts;
- counterfactual expected-if-acted and expected-if-withheld records;
- trustworthy distinction between stable production signing, ephemeral development signing, compatibility signing, unsigned state, and verification failure;
- append-only evidence and rollback references;
- public status generated from versioned evidence rather than hard-coded counts.

Where equivalent machinery exists, consolidate it. Do not create a disconnected second implementation.

### 3. Make public estate claims evidence-driven

Remove hard-coded GitHub and Hugging Face counts from production paths. Render a signed or versioned status snapshot with source, freshness, revision, and evidence label. Missing, stale, conflicting, or unverifiable input must render `UNAVAILABLE` or `DIVERGENT`.

### 4. Repair signing semantics end to end

Public copy, API responses, console views, and receipts must distinguish:

- signer configured and independently verifiable;
- stable production key;
- ephemeral development key;
- compatibility or placeholder mode;
- unsigned;
- verification unavailable or failed.

Do not say every action is signed when the active signer cannot support that claim. Read paths must remain side-effect free. Write paths that claim receipt issuance must produce a verifiable receipt or fail closed.

### 5. Integrate the command surface

Upgrade the canonical frontend rather than shipping an isolated mock. Expose estate readiness, models, kernels, Spaces, proof, receipts, alignment, failures, and promotion blockers through real API contracts. Preserve keyboard access, reduced motion, responsive behavior, CSP safety, explicit evidence states, and approved dependency policy.

### 6. Close backend/frontend/container drift

For every route or module:

- register API routes before SPA catch-alls;
- update container `COPY` instructions;
- assert JSON content type and schema so HTML fallthrough cannot pass;
- preserve shared-module hash contracts;
- expose source, build, and runtime revision through health/status contracts.

### 7. Repair CI at root cause

Run the repository's documented gates and focused tests. Do not weaken doctrine, security, route, provenance, hash-lock, or honest-status checks. Fix code, fixtures, packaging, and workflows.

Minimum candidate gates, superseded by stricter `AGENTS.md` commands:

```bash
pnpm install --frozen-lockfile
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
npx jest __tests__/
python -m compileall -q .
```

Also run targeted Python/frontend tests, route tests, claim scanners, shared-module hash checks, secret scanning, and container/build smoke tests available in the repository.

Pre-existing failures may remain only when reproduced, unrelated to the diff, explicitly documented, and not silently excluded. New failures are unacceptable.

### 8. Produce durable evidence

Create:

```text
artifacts/codex/BASELINE.json
artifacts/codex/IMPLEMENTATION_REPORT.json
artifacts/codex/TEST_REPORT.json
artifacts/codex/REMOTE_READBACK.json
artifacts/codex/ROLLBACK.md
```

Each JSON report must include command, exit code, timestamp, commit SHA, and evidence label. `REMOTE_READBACK.json` must remain blocked or unavailable unless authenticated source, build, deployment, and live-revision readback actually occurred.

### 9. Cross-repository continuation

When related repositories are required and authorized, create separate protected branches and pull requests in dependency order. Never combine unrelated repositories into one history. When another repository is unavailable, emit `artifacts/codex/CROSS_REPO_HANDOFF.json` with repository, branch, files, prerequisites, blocker, and acceptance gate. Do not mark it complete.

### 10. Delivery

Commit completed work to this task branch and push it to the current pull request. Do not push directly to `main`, force-push, approve your own work, or merge. Request `@codex review` after the implementation diff exists, then address all P0/P1 findings.

## Definition of done

- Implementation is integrated into current A11oy architecture, not installed as an isolated mock.
- Production paths contain no newly introduced mock, placeholder, sample-only, or hard-coded estate data.
- Public status and signing language match runtime evidence.
- Demo-critical routes return correct content types and schemas.
- Relevant install, build, type, test, doctrine, security, provenance, and route gates pass from a clean checkout.
- Container assembly includes every required runtime file.
- No secret or private key is committed.
- Diff includes rollback instructions and machine-readable evidence.
- Remote deployment is claimed only after authenticated readback proves source SHA, built artifact, deployed revision, live response, signer state, and rollback readiness agree.
- Pull request contains a factual implementation summary, test evidence, residual blockers, and no cosmetic green state.

Do not stop at an audit, plan, or generated payload. Continue until repository changes are implemented and tested, or until a genuinely unavailable external credential or authority boundary is reached. At that boundary, complete every local change and record the exact remote command, target, expected readback, and blocker.