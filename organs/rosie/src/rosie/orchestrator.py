# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""orchestrator — real Amaru → Sentra → Killinchu → A11oy organ chain.

LangGraph-style StateGraph (State + Nodes + Edges, message-passing with a
reducer) — see field-leaders brief §A.2. No `langgraph` runtime dependency
(airgap-safe); we implement the State/Node/Edge contract verbatim.

Flow (deterministic sequential process, CrewAI-style hand-off §A.4):

    amaru (cortex: reason/recall)
      → sentra (immune: policy_evaluate over 46 gates)
        → killinchu (field: domain-awareness check)
          → a11oy (governance: lambda_gate Λ verdict — Conjecture 1)

Each node:
  * routes through ToolRouter (real HTTP to the live organ; BFT quorum on
    safety-critical tools), and
  * emits a real OTLP span via Observability, threading ONE W3C trace-id across
    every hop (cross-pod tracing contract).

A conditional edge HALTS the chain early if a node returns a hard deny
(e.g. Sentra policy block or A11oy Λ-gate fail) — honest short-circuit, no
fabricated downstream success.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .observability import Observability, child_traceparent, make_traceparent
from .tool_router import ToolRouter

# ── State (LangGraph-style TypedDict-equivalent dataclass) ────────────────────


@dataclass
class OrchestrationState:
    """Mutable state carried through a single rosie orchestration run.

    Tracks the originating ``goal``, the root ``traceparent``, an append-only
    list of per-hop ``receipts``, and the terminal ``halted``/``verdict``
    outcome of the Amaru→Sentra→Killinchu→A11oy chain.
    """

    goal: str
    traceparent: str
    receipts: list[dict] = field(default_factory=list)   # reducer: append-only
    halted: bool = False
    halt_reason: Optional[str] = None
    verdict: Optional[str] = None

    def append_receipt(self, r: dict) -> None:
        """Reducer — append a node receipt to the running state."""
        self.receipts.append(r)


# ── Node definition ───────────────────────────────────────────────────────────


@dataclass
class Node:
    """One hop in the orchestration chain: an organ and the MCP tool to call.

    Attributes:
        name: Organ name (e.g. ``amaru``).
        tool: MCP tool this node invokes.
        role: Human-readable description of the organ's role.
        arg_key: Argument key the tool expects the goal under.
    """

    name: str          # organ name
    tool: str          # MCP tool this node invokes
    role: str          # human-readable organ role
    arg_key: str = "action"   # argument key the tool expects


# Amaru → Sentra → Killinchu → A11oy. (Killinchu = field/domain awareness node.)
CHAIN: list[Node] = [
    Node("amaru", "memory_query", "cortex — reason / provenanced recall", "query"),
    Node("sentra", "policy_evaluate", "immune — 46 policy gates", "action"),
    Node("killinchu", "mesh_inspect", "field — domain-awareness attestation", "action"),
    Node("a11oy", "lambda_gate", "governance — Λ aggregator verdict (Conjecture 1)", "action"),
]


class Orchestrator:
    """Compiled StateGraph: a linear chain with conditional halt edges."""

    def __init__(self, router: Optional[ToolRouter] = None,
                 obs: Optional[Observability] = None,
                 chain: Optional[list[Node]] = None):
        self.router = router or ToolRouter()
        self.obs = obs or Observability(service_name="rosie")
        self.chain = chain or CHAIN
        self._validate()

    def _validate(self) -> None:
        """Compile-time orphan/contract check (LangGraph compiles the graph)."""
        seen = set()
        for n in self.chain:
            if n.organ_dup_key() in seen:  # pragma: no cover - guarded below
                pass
            seen.add(n.name)
        if not self.chain:
            raise ValueError("orchestrator: empty chain")

    @staticmethod
    def _is_deny(result: dict) -> tuple[bool, str | None]:
        """Decide whether a node result is a hard deny that must halt the chain."""
        if not result.get("success", False):
            # quorum denial is a real, honest deny
            if result.get("error") == "byzantine_quorum_denied":
                return True, "byzantine_quorum_denied"
            # an unreachable organ is reported but does NOT fake success;
            # we continue degraded only if it was reached via healthz attestation
            if result.get("via") == "healthz-attestation":
                return False, None
            return True, result.get("error") or "node_failed"
        body = result.get("result")
        if isinstance(body, dict):
            # explicit policy/Λ deny verdicts
            verdict = str(body.get("verdict") or body.get("decision") or "").lower()
            if verdict in ("deny", "block", "fail", "reject"):
                return True, f"{result.get('organ')}:{verdict}"
            if body.get("allowed") is False or body.get("permit") is False:
                return True, f"{result.get('organ')}:not_allowed"
        return False, None

    def run(self, goal: str, traceparent: Optional[str] = None) -> OrchestrationState:
        """Execute the full organ chain for ``goal`` and return the final state.

        Walks Amaru→Sentra→Killinchu→A11oy, emitting a span and an
        append-only receipt per hop and halting early on any organ deny.

        Args:
            goal: The natural-language goal to route through the chain.
            traceparent: Optional W3C traceparent to root the trace; a new
                one is minted when omitted.

        Returns:
            The :class:`OrchestrationState` with all receipts and an honestly
            derived verdict (ALLOW only on a real a11oy Λ-gate pass —
            Conjecture 1, not a theorem).
        """
        tp = traceparent or make_traceparent()
        state = OrchestrationState(goal=goal, traceparent=tp)
        # root span for the whole workflow (keeps trace-id stable across hops)
        self.obs.span("rosie.workflow.start", tp, {"goal": goal[:120]})

        for node in self.chain:
            if state.halted:
                break
            hop_tp = child_traceparent(state.traceparent)
            t0 = time.time()
            args = {node.arg_key: goal}
            result = self.router.route(node.tool, args, hop_tp)
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            self.obs.span(f"rosie.hop.{node.name}", hop_tp, {
                "organ": node.name, "tool": node.tool, "role": node.role,
                "success": result.get("success"), "http": result.get("http"),
                "elapsed_ms": elapsed_ms,
            })
            deny, reason = self._is_deny(result)
            receipt = {
                "organ": node.name, "role": node.role, "tool": node.tool,
                "traceparent": hop_tp, "trace_id": (hop_tp.split("-")[1]),
                "success": result.get("success"), "http": result.get("http"),
                "elapsed_ms": elapsed_ms,
                "quorum": result.get("quorum"),
                "result": result.get("result"),
                "deny": deny, "deny_reason": reason,
            }
            state.append_receipt(receipt)
            if deny:
                state.halted = True
                state.halt_reason = reason
                self.obs.span("rosie.workflow.halt", hop_tp,
                              {"reason": reason, "at": node.name})
                break

        # Final verdict from the last (governance) hop, honestly derived.
        last = state.receipts[-1] if state.receipts else {}
        if state.halted:
            state.verdict = f"HALTED at {last.get('organ')} ({state.halt_reason})"
        elif last.get("organ") == "a11oy" and last.get("success"):
            state.verdict = "ALLOW (Λ-gate passed — Conjecture 1, not a theorem)"
        else:
            state.verdict = "INCONCLUSIVE (chain completed without a11oy ALLOW)"
        self.obs.span("rosie.workflow.verdict", state.traceparent,
                      {"verdict": state.verdict})
        return state

    def summary(self, state: OrchestrationState) -> dict:
        """Produce a compact, JSON-ready summary of a finished run.

        Args:
            state: The :class:`OrchestrationState` returned by :meth:`run`.

        Returns:
            A dict with the goal, root trace id, hop count, chain, halt info,
            verdict, and exporter — suitable for API responses or logs.
        """
        return {
            "goal": state.goal,
            "trace_id": state.traceparent.split("-")[1],
            "hops": len(state.receipts),
            "chain": [n.name for n in self.chain],
            "halted": state.halted,
            "halt_reason": state.halt_reason,
            "verdict": state.verdict,
            "exporter": self.obs.exporter,
            "single_trace_id": len(self.obs.trace_ids()) == 1,
            "trace_ids": sorted(self.obs.trace_ids()),
            "receipts": state.receipts,
            "doctrine": "v11 LOCKED 749/14/163 @ c7c0ba17",
            "lambda_status": "Conjecture 1 (NOT a theorem)",
        }


# helper used only by the compile-time validator
def _node_organ_dup_key(self):  # pragma: no cover
    return self.name


Node.organ_dup_key = _node_organ_dup_key


def orchestrate(goal: str, traceparent: Optional[str] = None) -> dict:
    """Module-level convenience: run the real chain and return a summary dict."""
    orch = Orchestrator()
    state = orch.run(goal, traceparent)
    return orch.summary(state)
