<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Operational evidence integration

- Decision date: 2026-11-16.
- Scope: operator recommendations, command presentation, and the integration roadmap.
- Status: three bounded source changes below; wider integration is **PROPOSED / ROADMAP**.
- Source baseline: a11oy `2204f596d17a854fba12cd204ab86019bc2e0712`.
- A source change or passing local test does not establish a deployed runtime outcome.

## Decision

Use existing SZL evidence, admission, dependency, and storage contracts as the integration
boundary. Backend responses and operator views should describe the same observed state.
Do not introduce a competing evidence graph, receipt format, or persistence authority.
An observation, a recommendation, an authorized action, and a verified receipt remain distinct.

## IMPLEMENTED IN THIS CHANGE

| Change | Bounded behavior |
|---|---|
| Health-backed recommendation GETs | Operator and companion recommendations derive from the in-process health observation; absent or failed observations remain unavailable or degraded. |
| Command Recommend stage | The command flow exposes the recommendation response and its blockers before an action is considered. |
| Consistent fail-closed console | Recommendation views preserve unavailable/degraded results and do not turn a failed fetch or missing result into an all-clear message. |

Implementation evidence is the accompanying diff in `serve.py` and the command/console assets,
with focused checks in `tests/test_operator_recommendation_health.py`,
`tests/test_console_recommendations.mjs`, and the existing route/UI suites.
These changes do not establish durable workflow execution, independent signature verification,
fleet-wide coverage, or deployment readiness. Those integrations remain **PROPOSED / ROADMAP**.

## Existing contracts to preserve in the roadmap

The following immutable source references establish design constraints, not deployment claims.
Repository pins are traceability references; ADR-0001 forbids turning source pins into storage gates.

| Contract | Pinned source | Integration consequence |
|---|---|---|
| Read/write separation and storage ownership | [a11oy AGENTS.md][szl-agents], [ADR-0001][szl-storage] | GETs observe; mutations own receipts. Storage work targets `a11oy_state_store.py`. |
| Existing evidence graph | [Canonical Evidence Graph v1][szl-graph] | Reuse edge identities and bounded snapshots; content addressing alone authenticates neither observer nor freshness. |
| Invariant reports | [szl-invariants][szl-invariants] | Report `OK` means generated; inspect every invariant, summary, and coverage, including `NO_DATA` and `UNAVAILABLE`. |
| Estate admission | [estate_manifest.py][szl-admit] | Bind source/HF/readback declarations and current-time TTL; declarations still need independent verification of actual signatures. |
| Advisory Lambda gate | [lambda_gate.py][szl-lambda] | Preserve zero veto and invalid-axis rejection; `GO` is policy admission, with `CONJECTURE_1_OPEN_ADVISORY`. |
| Formal boundary | [AxiomCheck.lean][szl-axioms], [Pipeline.lean][szl-pipeline] | Eight locked formulas; Lambda uniqueness remains Conjecture 1. Abstract non-interference is not deployed wiring verification. |
| Dependency graph | [dependencies.py][szl-dependencies] | Reuse dependency records; add admission checks for missing references and invalid persisted parents before trusting descendants. |

## PROPOSED / ROADMAP: evidence and execution integration

1. **One observation contract.** Extend the existing graph adapter with the source revision,
   runtime identity, observation time, freshness limit, measurement class, coverage, and blockers.
   Reference the underlying observation, probe, or receipt separately; keep the original bytes.
   The UI renders the admitted response and exposes the relevant source and failed dependency.
   A reachable endpoint, hash match, or report-level `OK` cannot promote a downstream verdict.
2. **Deterministic deny gate.** Keep policy evaluation outside model-generated recommendations.
   Bind the principal, action, artifact, environment, policy version, and relevant evidence before
   execution. Missing, stale, invalid, or insufficient evidence must not become permission.
   Conjecture 1 can inform an advisory score; it cannot supply a theorem, authority, or safety proof.
3. **No receipts on GET.** Read paths may return an existing receipt reference or last-known digest.
   They must not sign, append a ledger entry, or execute a repair. Authorized writes use the
   established receipt path; verify signatures and chain binding before displaying “signed”.
4. **Reuse ADR-0001.** Register any new live store through `a11oy_state_store.STORES` and resolve
   its local path through that module. Preserve local live databases, immutable snapshots,
   CAS lease ownership, fencing, and restoration checks; never write a live database under `/data`.
   Activation and durability require observed `/api/a11oy/v1/storage/status`, not this document.
5. **Resumable actions.** Persist operation identity, approval context, checkpoints, and terminal
   observations through the existing storage authority. External writes need idempotency keys
   and reconciliation after an uncertain reply. A resumed step may rerun; an approval checkpoint
   alone cannot prevent duplicate side effects. LangGraph supplies the reference pattern, not
   an installed dependency or an alternate SZL store ([interrupts][langgraph-interrupts],
   [persistence][langgraph-persistence]).
6. **Outcome evidence.** Keep attempted actions, success/failure telemetry, edit history, and
   receipts distinguishable. Palantir action logs record successful action submissions; failed
   attempts and aggregate behavior belong in operational metrics and traces ([action log][palantir-actions]).
   Correlate an operation to its dependency lineage, errors, latency, and drill-down trace using
   the [observability pattern described by Palantir][palantir-observability].

## PROPOSED / ROADMAP: two research concepts

### Readiness repair planner

Use the existing dependency graph to enumerate the observed blockers of one requested outcome.
Propose candidate repair sets and explain which blockers each would address, which observations
must be refreshed, and which dependencies remain unknown. Begin with bounded deterministic
rules and operator review; do not claim a minimal set without an explicit objective and solver.
Execution still passes through the existing deny gate and mutation receipt path.
Test against independently checked terminal states, including interruption and duplicate delivery.
This adapts dependency analysis and the [outcome-based evaluation in tau-bench][tau-paper].

### Evidence freshness view

Display each observation's age, admitted TTL, source/runtime binding, and affected descendants.
Use the verifier's current clock. Recompute eligibility when evidence expires or a dependency
becomes missing or invalid; historical success remains historical, not current permission.
The existing dependency evaluator needs separate missing-parent and persisted-invalid-parent
checks before it can support this view's admission semantics ([dependency implementation][szl-dependencies]).
Provide an accessible table and source drill-down; visual graph layout is optional presentation.
This combines existing SZL freshness/dependency contracts with operational lineage practice;
it is a proposed experiment, with no novelty, superiority, or performance claim.

## PROPOSED / ROADMAP: dependency selection and acceptance

As checked on 2026-11-16, NVIDIA documents NeMo Agent Toolkit as deprecated since October 2026,
with end of life by the end of 2026. Its migration guide assigns observability/middleware to
NeMo Relay, execution adapters to NeMo Fabric, and evaluation/optimization to NeMo Helix
([official migration guide][nvidia]).
Do not introduce `nvidia-nat` from older examples. Qualify any successor behind a thin adapter
against required capabilities, data boundaries, failure behavior, and the existing SZL contracts.
No NVIDIA or LangGraph runtime integration is implemented by this change.

Acceptance for future integration requires independent final-state readback, complete required
invariant coverage, fresh evidence, restart/retry checks, and fail-closed dependency handling.
Record task fixtures and versions; [tau-bench][tau-paper] evaluates terminal database state and
repeated-run reliability, while its [repository][tau-repo] warns that the original tasks are outdated.
Benchmark methods guide the checks; historical benchmark scores do not establish SZL performance.
Deployment claims additionally require the deployed source/runtime binding and live route checks.

## Sources

[szl-agents]: https://github.com/szl-holdings/a11oy/blob/2204f596d17a854fba12cd204ab86019bc2e0712/AGENTS.md
[szl-storage]: https://github.com/szl-holdings/a11oy/blob/2204f596d17a854fba12cd204ab86019bc2e0712/docs/adr/ADR-0001-a11oy-state-store.md
[szl-graph]: https://github.com/szl-holdings/a11oy/blob/2204f596d17a854fba12cd204ab86019bc2e0712/docs/evidence-graph-v1.md
[szl-invariants]: https://github.com/szl-holdings/szl-invariants/blob/233833d00163b255836ec72b5a0b4f53b8f11e17/torch-ext/szl_invariants/__init__.py
[szl-admit]: https://github.com/szl-holdings/szl-evidence-core/blob/4f120b4bb51a6c15f73fa277c89e3184a92c69f0/src/szl_evidence_core/estate_manifest.py
[szl-lambda]: https://github.com/szl-holdings/szl-evidence-core/blob/4f120b4bb51a6c15f73fa277c89e3184a92c69f0/src/szl_evidence_core/lambda_gate.py
[szl-axioms]: https://github.com/szl-holdings/lutar-lean/blob/5e8a92917d2d4bfeb371a2372f87a4c7660d996d/Lutar/Uniqueness/AxiomCheck.lean
[szl-pipeline]: https://github.com/szl-holdings/lutar-lean/blob/5e8a92917d2d4bfeb371a2372f87a4c7660d996d/Lutar/Agentic/Pipeline.lean
[szl-dependencies]: https://github.com/szl-holdings/szl-evidence-mandate/blob/ef6efdb5c736363819785b8b4d8a852d7db6e8e2/src/szl_evidence/dependencies.py
[palantir-actions]: https://www.palantir.com/docs/foundry/action-types/action-log
[palantir-observability]: https://www.palantir.com/docs/foundry/aip-observability
[langgraph-interrupts]: https://docs.langchain.com/oss/python/langgraph/interrupts
[langgraph-persistence]: https://docs.langchain.com/oss/python/langgraph/persistence
[nvidia]: https://docs.nvidia.com/nemo/agent-toolkit/latest/resources/migration-guide.html
[tau-paper]: https://arxiv.org/abs/2406.12045
[tau-repo]: https://github.com/sierra-research/tau-bench
