# Governed Graph Operations

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Lutar, Stephen P. - SZL Holdings

## What ships

Governed Graph Operations is a real, deterministic topology analyzer served at
`/graph-operations`. It accepts a strict `szl.governed-graph/v1` contract and
returns a normalized plan, stable digest, schedule, critical path, and explicit
gate findings.

The analyzer implementation is **REAL**. Its proposed plan is **MODELED** and
`PLAN_ONLY`. The HTTP surface has zero effectors, zero provider calls, and zero
writes. It does not run agents, authorize a release, sign a read, or upgrade
evidence. Production execution must bind itself to the exact contract digest,
re-evaluate policy, honor declared human gates, and emit a receipt for every
write.

`szl_sgh_scheduler.execute_governed_plan` now supplies a separate, explicitly
called **local read-only** executor for the same contract. It is not registered
as an HTTP route or enabled by a flag. It runs injected in-memory Python
callables only; those callables are trusted capabilities, not sandboxed code.

## Local plan execution

The local interface is:

```python
execute_governed_plan(
    contract, expected_digest,
    input_values={"input.key": value},
    admissions={"node-id": admission_callable},
    implementations={"node-id": implementation_callable},
    verifiers={"node-id": verifier_callable},
    max_attempts_per_node=2,
    max_total_attempts=256,
    cancelled=None, clock=None, deadline=None,
)
```

Each callable receives a separate JSON snapshot context containing the exact
`contract_digest`, normalized `node`, declared `inputs`, `attempt`, and direct
`predecessor_receipts`. The verifier context also contains candidate `outputs`.
Admission and verification return exactly `True` or `False`. An implementation
returns `{"status": "SUCCEEDED", "outputs": {<declared keys>: <JSON values>}}`
or an explicit local retry result,
`{"status": "RETRYABLE_FAILURE", "failure_kind": "LOCAL"}` (also
`SYNTHETIC`). Other outcomes fail closed. No capability is supplied by default.

The executor snapshots strict JSON inputs, recomputes `analyse_graph`, compares
the exact digest, and refuses blockers before calling any capability. It flattens
the analyzer's deterministic schedule serially. A node sees only its declared
external inputs and verified direct data predecessor outputs. `control_after`
orders dispatch without supplying artifacts. Ambiguous providers, missing
outputs, fake data edges, unsupported roles or loop semantics, side effects,
writes, `WRITE_GOVERNED` authority, and `HUMAN` authority are refused. Admission
is checked before each implementation attempt, including retries. A denial,
failed verification, cancellation, deadline, or ambiguous outcome stops further
dispatch and marks unrun nodes `BLOCKED`.

The graph's `max_total_iterations` bounds aggregate attempts, with hard ceilings
of 9 attempts per node and 256 total. A deadline checks an injected clock before
dispatch; it cannot interrupt a synchronous callable already running. The
result includes node dispositions and deterministic SHA-256 in-memory
transition records binding input and output hashes, attempt, predecessor
receipt identities, and prior record identity. These records are inspectable
local evidence. They are not signed, durable, independently verified, or an
exactly-once effect log.

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
They remain outside this local read-only implementation. Production effect
execution and durable replay require a separate integration through the
existing Governed Delta Workspace transaction and receipt history.

## Verification

Focused tests live in `tests/test_governed_graph_operations.py`. They cover all
three samples, stable digests, graph cycles, bounded loops, fake edges, fan-in,
resource conflicts, verifier independence, write authority, receipt anchors,
body limits, read purity, and route precedence ahead of the SPA catch-all.
`tests/test_sgh_plan_execution.py` covers serial chain and diamond dispatch,
fail-closed admission and verification, bounded local retry, cancellation,
snapshot isolation, deterministic transition records, and legacy wrapper
compatibility.
