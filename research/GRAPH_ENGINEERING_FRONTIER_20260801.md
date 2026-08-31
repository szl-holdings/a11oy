# Graph Engineering Frontier Review - 2026-08-01

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Lutar, Stephen P. - SZL Holdings

## Decision

A11oy should adopt graph engineering as a governed scheduling pattern, not as
an unbounded agent swarm. The useful advance is explicit structure: bounded
jobs, real artifact dependencies, isolated parallel work, deterministic reduce,
fresh-context verification, external truth anchors, hard budgets, and human or
policy gates before effects.

This review informed an original A11oy implementation. No third-party source
code, prose, diagram, or UI asset was copied into the product.

## Trigger material

Anatoli Kopadze's July 24, 2026 X Article, [Graph Engineering
explained](https://x.com/AnatoliKopadze/status/2080668775796314331), frames the
idea as a network of local generate/evaluate/repair loops. Its most useful
operational tests are:

- remove an edge when the downstream job consumes no predecessor artifact;
- fan out genuinely independent work, then deterministically reduce it;
- make fan-in count expected and received outputs;
- isolate a skeptical verifier from the maker's rationale;
- expose shared files, locks, APIs, and rate limits as hidden dependencies;
- cap retries, cost, time, and parallelism; and
- anchor agreement to executed tests, resolved sources, real business events,
  or a human decision.

The article contains no stated code or content license. A11oy links and
summarizes it, but does not copy its pseudocode or illustrations. Its speed and
compression examples are treated as illustrative author claims, not measured
A11oy outcomes.

## Primary-source triangulation

| Source | Pattern studied | License or reuse boundary | A11oy adaptation |
|---|---|---|---|
| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Parallelization, orchestrator-worker, evaluator-optimizer | Engineering article; ideas summarized, prose and figures not copied | Separate worker, reducer, verifier, and governance roles |
| [Anthropic: Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Lead agent plus parallel subagents and citation processing | Engineering article; reported product results remain attributed | Breadth-first research sample with source-resolution anchor |
| [Bun in Rust](https://bun.com/blog/bun-in-rust) | Dynamic workflows, worktrees, adversarial review, compiler feedback | Case study; operational claims remain Bun's | Isolated workspaces and exact-head verification in release sample |
| [LangGraph](https://github.com/langchain-ai/langgraph) and [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) | Typed state, nodes, reducers, conditional edges, cycles, recursion caps | MIT repository; no code imported | Strict state/artifact contract and bounded local loop node |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | Connectivity/type checks, supersteps, checkpoints, human-in-loop | MIT repository; no code imported | Static contract validation and explicit human gate |
| [Google ADK](https://github.com/google/adk-python) | Sequential, parallel, and loop agents | Apache-2.0 repository; no dependency added | Roles stay composable while authority remains separate |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | Handoffs, guardrails, tracing, structured orchestration | MIT repository; no dependency added | Artifact-bound handoffs and machine-readable findings |
| [Hugging Face smolagents](https://github.com/huggingface/smolagents) | Small inspectable loop and Hub integration | Apache-2.0 repository; no dependency added | Inspectable contracts and explicit provider-call truth boundary |
| [Temporal Python SDK](https://github.com/temporalio/sdk-python) | Durable replay, retries, cancellation, activities | MIT repository; no dependency added | Production runner roadmap requires idempotency and durable history |
| [Dagster](https://github.com/dagster-io/dagster) | Asset graph, lineage, observability, testing | Apache-2.0 repository; no dependency added | Artifact keys and lineage-bearing edges |
| [Prefect](https://github.com/PrefectHQ/prefect) | Bounded concurrency and task runners | Apache-2.0 repository; no dependency added | Explicit max-parallel budget and deterministic batches |
| [Reflexion](https://github.com/noahshinn/reflexion) | Feedback-driven bounded retry | MIT code; paper text/figures separate | Repair loop with an external-test exit and escalation cap |

The closest formal position paper located was Hu Wei's [From Agent Loops to
Structured Graphs](https://arxiv.org/abs/2604.11378). It proposes a static DAG
control plane but does not present a production implementation or empirical
evaluation. Its arXiv distribution terms are not an open-source code license;
only the architectural idea was considered.

No GitLab project offered a stronger primary implementation than the listed
official repositories and papers during this review.

## What A11oy adds

The A11oy contract makes governance first-class:

- Data and control edges are distinct. A data edge must carry a declared
  artifact; otherwise it is a fake-edge candidate.
- A top-level DAG may contain local loop nodes, but every loop has an iteration
  cap and named exit conditions.
- Nodes scheduled in the same layer are checked for shared writes, read/write
  collisions, and exclusive-resource conflicts.
- Reducers and synthesizers expose expected versus contractually received
  workers so silent failure cannot become a complete-looking answer.
- Verifiers declare both a target artifact and fresh context. This is a
  structural independence check, not a claim that same-model errors are
  statistically independent.
- Terminal outcomes require outside anchors. Consensus alone never upgrades a
  claim.
- Side-effecting nodes require governed or human authority plus a mandatory
  receipt anchor.
- The plan is content-addressed. `plan_id` derives from the normalized contract
  digest so a later executor can fail closed on drift.
- The analyzer never confuses structural readiness with execution authority.

## What was rejected

- no uncontrolled autonomous swarm;
- no majority vote presented as truth;
- no claim that context transfer is free;
- no universal speedup promise;
- no implicit writes from a read/analyze surface;
- no exposure of broad shell, filesystem, GitHub mutation, or CRM tools through
  the first graph API;
- no second persistence or receipt ledger beside GDW/Khipu; and
- no dependency added merely to reproduce patterns that fit in a small,
  testable standard-library implementation.

## Next production frontier

The safe effecting successor is a receipt-derived Governed Run Graph over GDW.
Each advance authorizes and executes at most one allowlisted node. The state
flow is `PROPOSED -> AUTHORIZED or DENIED -> OBSERVED -> VERIFIED or HALTED`.
Every POST requires scoped bearer authorization and a unique request ID; GET
projections remain pure. An external write is not admitted until durable
outbox/saga behavior, owner isolation, replay safety, human approval, and
receipt recovery pass exact-head protected checks and runtime readback.
