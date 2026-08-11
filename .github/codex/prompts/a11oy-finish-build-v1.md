<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# A11oy Codex whole-thread execution prompt v2

You are operating in `szl-holdings/a11oy` under the canonical whole-thread coordination issue `szl-holdings/.github#415`. This run has source-edit authority only inside the checked-out A11oy worktree. The trusted workflow—not you—will create the feature branch, commit, push, and pull request after your changes pass deterministic gates.

## 1. Read first

Read, in order:

1. `AGENTS.md`
2. every applicable nested `AGENTS.md` or override
3. `CLAUDE.md`
4. `.claude/rules/**`
5. `KNOWN_GOTCHAS.md`
6. `.github/codex/a11oy-finish-build-task-v1.json`
7. `.codex-input/base-sha.txt`
8. `.codex-input/current-state.json`

Treat the current repository and snapshot as authority. Historical issue numbers and audits are hints only.

## 2. Hard boundaries

- Do not access, search for, print, hash, or persist secret values.
- Do not use network access, provider credentials, GitHub credentials, Hugging Face credentials, or database credentials.
- Do not run `git push`, merge, deploy, mutate Hugging Face, mutate a database, change rulesets, or write another repository.
- Do not weaken or delete tests, doctrine, source-binding, secret, review, DCO, signing, or branch-protection gates.
- Do not create a second app, ledger, deployment writer, model registry, or MCP authority when a canonical implementation exists.
- Do not copy leaked prompts, proprietary implementations, private data, or unlicensed weights.
- Preserve the eight locked formulas exactly. Lambda remains Conjecture 1.
- A truthful blocked result is preferable to a fabricated green result.

## 3. Select one coherent current repair

Inspect current `main` and the snapshot. Select the highest-priority still-unsatisfied repair that can be completed and proven in one A11oy pull request:

1. eliminate indefinite `CHECKING`, `LOADING`, `PROBING`, blank, or spinner-only public states with concurrent bounded probes and terminal fallbacks;
2. replace contradictory binary Killinchu deployment copy with capability-axis evidence without implying customer, certification, compliance, or authorization readiness;
3. repair exact GitHub/Hugging Face/runtime source binding or a current fail-closed deployment-parity defect;
4. establish a deny-by-default model admission or clean-room behavior-profile foundation in an existing canonical seam;
5. otherwise repair the next current A11oy blocker evidenced by the snapshot.

Do not bundle unrelated improvements. If the first priority is already satisfied, prove that through current code/tests and move to the next.

## 4. Implementation standard

- Reproduce the defect before changing code.
- Trace the real app factory, route registration, static build, Dockerfile `COPY` closure, and deployment source contract.
- Implement the smallest permanent root-cause repair in the existing taxonomy.
- Use hard wall-clock deadlines around network fetch and body parsing where public probes are involved.
- Settle public status to `REACHABLE`, `DEGRADED`, `UNREACHABLE`, or `UNAVAILABLE`.
- Preserve cached evidence only with source, timestamp, digest, freshness rule, and `CACHED` label.
- Render untrusted text and URLs safely.
- Add regression and negative tests through actual application or browser wiring, not only helper imports.
- Add Dockerfile copy entries for any new runtime Python file.
- Update concise operator/architecture documentation when behavior changes.

## 5. Required proof

Run the most specific tests while developing, then run:

```bash
.github/codex/a11oy-run-gates-v1.sh
```

Create a receipt at:

```text
artifacts/codex-finish-build/<base-sha-prefix>/receipt.json
```

The receipt must include exact base SHA, changed-file SHA-256 digests, tests and exit codes, truth labels, external blockers, and zero secret values.

Finally write `.codex-output/final-result.json` conforming exactly to `.github/codex/a11oy-finish-build-output.schema.json`.

- Use `PATCH_READY` only when the coherent source repair and every applicable local gate pass.
- Use `BLOCKED_MANAGED_PREREQUISITE` when completion requires an unavailable managed credential, deployment, external repository, reviewer, or database.
- Use `TERMINAL_FAILURE` when the attempted source repair cannot satisfy its contract.

Your final message must summarize the implemented repair, tests, receipt path, blockers, and the next protected action. Do not claim merged, deployed, production, customer-ready, certified, or Series-A complete.
