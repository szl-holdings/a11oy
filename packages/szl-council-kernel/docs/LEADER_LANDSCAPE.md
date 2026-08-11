# Leader landscape and fashion-thinking synthesis

Observed: 2026-08-03. This document is a design comparison, not a claim that any upstream code has been copied, vendored, reproduced, or approved for production. Exact revisions, licenses, security posture, and benchmarks remain Research Foundry gates. Source locations are recorded in `research/UPSTREAM_CATALOG.json`.

## Operating thesis

The strongest projects in the agent ecosystem are converging on several useful layers: durable workflows, graph orchestration, specialist-agent harnesses, sandboxed tools, workload identity, policy engines, inter-agent protocols, observability, and agent catalogs. None of those layers should be allowed to become the root authority for a consequential action merely because it can generate or route an agent response.

A11oy should therefore **compose the leaders beneath an SZL-owned deterministic kernel**:

```text
framework/model specialist
  -> untrusted structured assessment or action proposal
  -> Alloy Autonomy Envelope
  -> Fourfold commit/reveal + diversity compiler
  -> calibrated release gate
  -> capability-bound effector
  -> postcondition proof + signed receipt
  -> transparency + delayed outcome settlement
```

## Comparative matrix

| Upstream | Strong mechanism to borrow | What not to inherit as authority | Alloy integration posture |
|---|---|---|---|
| Temporal | Durable history, Activities, replay, timers, recovery | Workflow code deciding its own permissions or proof truth | Durable orchestration adapter; kernel transitions remain authoritative |
| LangGraph | Fine-grained state graphs, checkpointing, human interruption | Transcript/message state as legal or operational truth | Agentic-node runtime behind typed state and receipt contracts |
| Microsoft Agent Framework | Provider-flexible agents, graph workflows, restartability, middleware, human-in-loop | Framework-level collaboration treated as independent assurance | Optional specialist harness and workflow adapter |
| Google ADK | Code-first agents, workflow runtime, task delegation, evaluation surface | Model/task output bypassing capability or settlement gates | Optional domain-agent and evaluation harness |
| OpenAI Agents SDK | Small primitives, handoffs, guardrails, tracing, isolated sandbox-agent patterns | SDK guardrails being confused with enterprise authority or effect verification | Optional specialist client; all tool calls pass through Alloy governors |
| GitLab Duo Agent Platform | Repo-side asynchronous agents, SDLC context, flows, catalog and triggers | Catalog membership or agent trace being treated as release proof | GitLab source-control/SDLC connector plus evidence read-back |
| AgentScope / Runtime | Permission system, multi-tenancy, sandbox backends, event system, observability | Agent runtime permission declarations overriding kernel grants | Optional worker and sandbox provider beneath Alloy contracts |
| CrewAI | Role-oriented teams, event-driven flows, high-level automation | Role names or majority agreement masquerading as epistemic independence | Baseline and optional worker harness; Fourfold settlement stays external |
| OpenHands | Self-hosted coding control center, backend portability, automations | Unsandboxed host access or agent completion claims without read-back | Engineering effector behind repository-scoped capability envelopes |
| OPA/Rego | Externalized, testable policy decisions | A policy response without exact input/revision/signature binding | Constitution and release-policy adapter, fail-closed on unavailability |
| SPIFFE/SPIRE | Workload identity, short-lived SVIDs, trust domains | Static shared tokens and self-declared operator identity | Production identity plane and diversity evidence |
| MCP | Tool/resource interoperability | Trusting a protocol message as authorization | MCP Governor validates exact action, target, grant, epoch, and budget |
| A2A | Cross-framework agent interoperability | Remote peers claiming kernel authority or verified state | A2A Governor binds case, policy, evidence manifest, and identity |
| SCITT / RFC 9162 patterns | Signed statements, receipts, inclusion/consistency, monitors | A local log being represented as independent public transparency | Production transparency service and offline verification target |

## Research baselines

The model/ensemble literature suggests that “more agents” is not automatically better. The build therefore carries explicit baselines for:

- strongest single model;
- self-consistency;
- homogeneous self-mixture;
- heterogeneous mixture-of-agents;
- majority vote;
- debate/cross-critique;
- Fourfold with and without correlation constraints; and
- calibrated ACT/ESCALATE/BLOCK release logic.

Conformal-risk-control and contract-grounded tool-execution papers are treated as methods to reproduce and benchmark, not as inherited guarantees. The reference release gate is empirical and states that limitation in its output.

## SZL-owned frontier

The proprietary differentiation is not a renamed agent framework. It is the governance and proof layer that makes heterogeneous frameworks interchangeable:

1. **Proof-Carrying Deliberation Graph** — claims, evidence, challenge, stance, decision, action, and outcome are canonical objects; private chain-of-thought is excluded.
2. **Effective Epistemic Council Size** — a fail-closed independence measure across trust domain, key, implementation, model lineage, evidence source, operator, retrieval path, and provider account.
3. **Blinded Fourfold settlement** — Authority, Sentinel, Verifier, and Value commit before reveal; categorical veto and minority truth survive aggregation.
4. **Autonomy Envelope** — exact target, capability, budget, epoch, idempotency, rollback, postconditions, and proof obligations.
5. **Counterfactual Branch Market** — bounded alternatives compete on utility, risk, cost, latency, proof, diversity, and unsupported novelty.
6. **Negative Capability Ledger** — the router knows which task classes, tools, epochs, and conditions are unsafe or uncalibrated.
7. **Causal Outcome Closure** — immediate technical success is separated from delayed business value.
8. **Read-only A11oy projection** — the presentation layer cannot manufacture `verified`.

## Build decision

The correct product is **a kernel plus a later specialist-model family**, not a single Council model.

- The kernel is the minimal deterministic trusted computing base and should be open to multiple model/framework providers.
- Specialist models should be trained only on rights-cleared, structured traces with objective verifier and delayed-outcome labels.
- No weight update, policy update, or kernel update self-promotes; each remains a separate candidate requiring reproducible evaluation and a new promotion council.
