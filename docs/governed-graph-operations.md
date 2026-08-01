# Governed Graph Operations

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Lutar, Stephen P. - SZL Holdings

## What ships

Governed Graph Operations is a real, deterministic topology analyzer served at
`/graph-operations`. It accepts a strict `szl.governed-graph/v1` contract and
returns a normalized plan, stable digest, schedule, critical path, and explicit
gate findings.

The implementation is **REAL**. The proposed plan is **MODELED** and
`PLAN_ONLY`. This surface has zero effectors, zero provider calls, and zero
writes. It does not run agents, authorize a release, sign a read, or upgrade
evidence. Any future executor must bind itself to the exact contract digest,
re-evaluate policy, honor the declared human gates, and emit a receipt for every
write.

## Routes

| Route | Method | Contract |
|---|---:|---|
| `/graph-operations` | GET | Operator page; no runtime CDN |
| `/api/a11oy/v1/graph-operations/status` | GET | Machine-readable service and truth boundary |
| `/api/a11oy/v1/graph-operations/sample/{sample_id}` | GET | Audited sample plus its analysis |
| `/api/a11oy/v1/graph-operations/analyse` | POST | Pure computation over caller-supplied JSON; 96 KiB body cap |

GET routes are read-only and mint no receipt. The analysis POST is also
non-persistent: it computes a response and performs no effect.

## Contract model

A top-level plan must be acyclic. A retry cycle is represented as one `loop`
node with `max_iterations` and at least one explicit exit condition. This keeps
the global schedule auditable while allowing bounded local repair.

Every node declares:

- a bounded role and authority;
- data dependencies (`depends_on`) and control/resource ordering
  (`control_after`) separately;
- consumed and produced artifact keys;
- read, write, and exclusive-resource sets;
- verifier targets and whether verifier context is fresh;
- whether it is side-effecting; and
- local loop limits, when applicable.

Every graph declares external inputs, required truth anchors, and hard budgets
for nodes, parallel work, depth, and aggregate loop iterations.

## Fail-closed gates

The analyzer rejects malformed input, unknown fields, missing dependencies,
top-level cycles, unknown anchor targets, and an unsupported schema. It blocks
or flags plans with:

- missing input artifacts;
- incomplete reducer or synthesizer fan-in;
- parallel jobs that share mutable state or an exclusive resource;
- an unbounded loop;
- a verifier without fresh context or an artifact-bound target;
- an unanchored terminal outcome;
- a side-effecting node without governed/human authority and a mandatory
  receipt anchor; or
- a declared budget breach.

A data edge over which no declared artifact passes is reported as a fake-edge
optimization advisory. Legitimate control ordering belongs in `control_after`.

## Operator workflow

1. Select an audited sample or edit the JSON contract.
2. Choose **Analyze contract**.
3. Inspect the deterministic layers, scheduled batches, and critical path.
4. Resolve every blocker and review every fake-edge advisory.
5. Confirm reducer `expected` and `contractually_received` counts match.
6. Confirm terminal nodes are covered by an outside truth anchor.
7. Hand the exact `plan_id` and `contract_digest` to a separately governed
   orchestrator. Do not infer authorization from `READY_TO_ORCHESTRATE`.

## Architecture boundary

This module belongs to `governance/services`. It complements, rather than
replaces, the existing bounded `a11oy_agent_loop.py` control flow and Ouroboros
loop runtime. It intentionally does not call the broad code-orchestrator tool
surface or create another ledger. A production effecting graph runner should be
derived from the Governed Delta Workspace transaction and receipt history so
GDW remains the sole durable write boundary.

The safe production sequence is:

`freeze scope -> analyze graph -> authorize exact node -> persist authorization
-> execute one allowlisted effect -> observe -> verify -> persist receipt ->
derive run graph`

External repository, deployment, CRM, or data writes require a later
outbox/saga design, explicit approval, idempotency, and source-bound receipts.
They are outside this plan-only release.

## Verification

Focused tests live in `tests/test_governed_graph_operations.py`. They cover all
three samples, stable digests, graph cycles, bounded loops, fake edges, fan-in,
resource conflicts, verifier independence, write authority, receipt anchors,
body limits, read purity, and route precedence ahead of the SPA catch-all.
