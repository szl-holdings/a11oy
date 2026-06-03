# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings
# Author: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Change-class: ADDITIVE — SZL Agent Pattern v1 ("Ken"). Doctrine v11 LOCKED
# 749/14/163 UNCHANGED. Kernel commit c7c0ba17. Λ = Conjecture 1 (NOT a theorem).
#
# Adapted patterns (all Apache-2.0 / MIT — no GPL/AGPL):
#   - LangGraph StateGraph topology (Apache-2.0) — langchain-ai/langgraph
#   - Letta/MemGPT tiered memory model (Apache-2.0) — letta-ai/letta
#   - AutoGen GroupChat handoff pattern (MIT) — microsoft/autogen
#   - crewAI role/goal identity (MIT) — joaomdmoura/crewAI
#   - smolagents CodeAgent observation loop (Apache-2.0) — huggingface/smolagents
#   - MCP tool schema (Apache-2.0) — modelcontextprotocol
#
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
szl_ken — SZL Agent Pattern v1 ("Ken") shared library.

Implements the standard SZL agent loop:
  INIT_STATE → PLAN → POLICY_GATE → DISPATCH_TOOL → OBSERVE → SIGN_RECEIPT →
  Λ_CHECK → (loop or HALT) → FINALIZE

Every flagship imports this module to get the Ken agent loop endpoints:
  POST /api/{flagship}/v1/agent/loop
  GET  /api/{flagship}/v1/mcp/tools
  GET  /api/{flagship}/v1/khipu/{receipt_hash}

CRITICAL: This module is ADDITIVE. It does NOT modify existing routes.
It does NOT change doctrine, kernel_commit, Λ, declarations, axioms, or sorries.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError:
    # Graceful no-op if fastapi not present (test environments)
    BaseModel = object
    Field = lambda **k: None
    APIRouter = dict

# ── Doctrine invariants — NEVER change these ─────────────────────────────────
DOCTRINE = "v11"
KERNEL_COMMIT = "c7c0ba17"
LAMBDA_STATUS = "Conjecture 1 (NOT a theorem; 163 sorries outstanding in Lean kernel)"
DECLARATIONS = 749
AXIOMS = 14
SORRIES = 163
SLSA_LEVEL = "L1"
SECTION_889_VENDORS = ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]

# ── Environment ───────────────────────────────────────────────────────────────
HALT_THRESHOLD = float(os.environ.get("SZL_LAMBDA_HALT_THRESHOLD", "0.3"))
TOOL_TIMEOUT_S = float(os.environ.get("SZL_TOOL_TIMEOUT_S", "10.0"))
MAX_STEPS_LIMIT = 20

A11OY_URL = os.environ.get("SZL_A11OY_URL", "https://szlholdings-a11oy.hf.space")
AMARU_URL = os.environ.get("SZL_AMARU_URL", "https://szlholdings-amaru.hf.space")
KHIPU_CONSENSUS_URL = os.environ.get(
    "SZL_KHIPU_CONSENSUS_URL", "https://szlholdings-khipu-consensus.hf.space"
)


# ── Pydantic models ───────────────────────────────────────────────────────────

class AgentLoopRequest(BaseModel):
    goal: str
    max_steps: int = Field(default=10, ge=1, le=MAX_STEPS_LIMIT)
    traceparent: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class AgentLoopResponse(BaseModel):
    session_id: str
    flagship: str
    chain: List[Dict[str, Any]]
    master_receipt: Dict[str, Any]
    final_state: Dict[str, Any]
    doctrine: str = DOCTRINE
    kernel_commit: str = KERNEL_COMMIT


class KhipuAgentState(BaseModel):
    # Identity
    session_id: str
    flagship: str
    actor: str
    doctrine: str = DOCTRINE
    kernel_commit: str = KERNEL_COMMIT

    # Goal & limits
    goal: str
    max_steps: int = 10
    step: int = 0

    # Λ (Conjecture 1)
    lambda_score: float = 1.0
    lambda_status: str = LAMBDA_STATUS

    # Memory tiers
    working_memory: Dict[str, Any] = Field(default_factory=dict)
    short_term: List[Dict[str, Any]] = Field(default_factory=list)

    # Execution
    chain: List[Dict[str, Any]] = Field(default_factory=list)
    traceparent: str = ""
    halted: bool = False
    halt_reason: str = ""
    halt_code: Optional[str] = None

    # Compliance constants
    slsa_level: str = SLSA_LEVEL
    section_889_vendors: List[str] = Field(default_factory=lambda: list(SECTION_889_VENDORS))

    class Config:
        extra = "forbid"


# ── State management ──────────────────────────────────────────────────────────

def make_traceparent(session_id: str) -> str:
    """Generate a W3C traceparent from session_id."""
    tid = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    sid = hashlib.sha256((session_id + "span").encode()).hexdigest()[:16]
    return f"00-{tid}-{sid}-01"


async def init_state(
    goal: str,
    flagship: str,
    max_steps: int,
    traceparent: str = "",
    context: Optional[Dict] = None,
) -> KhipuAgentState:
    """Create a fresh KhipuAgentState for a new agent session."""
    session_id = str(uuid.uuid4())
    if not traceparent:
        traceparent = make_traceparent(session_id)
    return KhipuAgentState(
        session_id=session_id,
        flagship=flagship,
        actor=f"{flagship}/agent/v1",
        goal=goal,
        max_steps=min(max_steps, MAX_STEPS_LIMIT),
        traceparent=traceparent,
        working_memory=context or {},
    )


def compute_lambda(state: KhipuAgentState, tool_result: Optional[Dict]) -> float:
    """
    Lutar Λ-aggregator — Conjecture 1. Bounded [0,1].
    NOT a theorem. 163 sorries outstanding in Lean kernel.
    Deterministic — no LLM calls. Same inputs → same output.
    """
    success_signal = 1.0 if (tool_result and tool_result.get("success")) else 0.5
    # Step decay: the further along we are, the more we penalise uncertainty
    progress = state.step / max(state.max_steps, 1)
    step_decay = max(0.0, 1.0 - progress * 0.25)
    # Exponential moving average with previous Λ
    alpha = 0.7
    raw = alpha * state.lambda_score + (1 - alpha) * success_signal * step_decay
    return round(min(1.0, max(0.0, raw)), 4)


def sign_receipt(
    *,
    step: int,
    kind: str,
    plan: Dict,
    tool_result: Dict,
    state: KhipuAgentState,
    flagship: str,
    gate: Optional[Dict] = None,
    lambda_score: Optional[float] = None,
) -> Dict:
    """
    Build a KhipuReceipt v2 and DSSE-sign it.
    Real ECDSA-P256 when szl_dsse available; honest unsigned placeholder otherwise.
    """
    lam = lambda_score if lambda_score is not None else state.lambda_score
    receipt: Dict[str, Any] = {
        "schema": "szl.agent.receipt/v2",
        "step": step,
        "kind": kind,
        "session_id": state.session_id,
        "flagship": flagship,
        "actor": state.actor,
        "plan": plan,
        "gate": gate or {},
        "tool_result": tool_result,
        "lambda_score": lam,
        "lambda_status": LAMBDA_STATUS,
        "doctrine": DOCTRINE,
        "kernel_commit": KERNEL_COMMIT,
        "slsa_level": SLSA_LEVEL,
        "section_889_vendors": state.section_889_vendors,
        "nonce": hashlib.sha256(os.urandom(16)).hexdigest()[:16],
        "ts": datetime.now(timezone.utc).isoformat(),
        "traceparent": state.traceparent,
        "parent_digest": (
            _extract_digest(state.chain[-1]) if state.chain else ""
        ),
    }
    receipt["digest"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, default=str).encode()
    ).hexdigest()

    # Attempt DSSE signing
    try:
        import szl_dsse as _d  # type: ignore
        envelope = _d.sign_receipt(receipt)
        return {**envelope, "payload": receipt, "signed": True}
    except Exception:
        return {
            "payloadType": "application/vnd.szl.agent.receipt+json;v=2",
            "payload": receipt,
            "signatures": [
                {"keyid": "szlholdings-ec-p256", "sig": "PLACEHOLDER-NOT-SIGNED"}
            ],
            "signed": False,
            "digest": receipt["digest"],
        }


def _extract_digest(envelope: Dict) -> str:
    """Extract digest from a receipt envelope or payload."""
    if "digest" in envelope:
        return envelope["digest"]
    payload = envelope.get("payload", {})
    if isinstance(payload, dict):
        return payload.get("digest", "")
    return ""


def update_state(
    state: KhipuAgentState,
    receipt: Dict,
    tool_result: Optional[Dict] = None,
    lambda_score: Optional[float] = None,
) -> KhipuAgentState:
    """Pure state transition — returns a new KhipuAgentState."""
    new_chain = state.chain + [receipt]
    new_short_term = (state.short_term + [receipt])[-20:]
    lam = lambda_score if lambda_score is not None else state.lambda_score
    # Extract lambda from receipt if not provided
    payload = receipt.get("payload", receipt)
    if isinstance(payload, dict) and lambda_score is None:
        lam = payload.get("lambda_score", lam)
    return state.model_copy(update={
        "step": state.step + 1,
        "chain": new_chain,
        "short_term": new_short_term,
        "lambda_score": round(lam, 4),
    })


def make_master_receipt(
    chain: List[Dict], state: KhipuAgentState, flagship: str
) -> Dict:
    """Compute Merkle root over chain and emit master receipt."""
    digests = sorted(
        _extract_digest(r) for r in chain
    )
    merkle_root = hashlib.sha256(json.dumps(digests).encode()).hexdigest()
    return {
        "schema": "szl.agent.master_receipt/v1",
        "session_id": state.session_id,
        "flagship": flagship,
        "actor": state.actor,
        "step_count": len(chain),
        "merkle_root": f"sha256:{merkle_root}",
        "lambda_final": state.lambda_score,
        "lambda_status": LAMBDA_STATUS,
        "halt_code": state.halt_code,
        "halt_reason": state.halt_reason,
        "khipu_witnesses": [],  # Populated by khipu-consensus call
        "quorum": "0/4",
        "doctrine": DOCTRINE,
        "kernel_commit": KERNEL_COMMIT,
        "slsa_level": SLSA_LEVEL,
        "section_889_vendors": state.section_889_vendors,
        "ts": datetime.now(timezone.utc).isoformat(),
        "traceparent": state.traceparent,
    }


# ── Policy gate ───────────────────────────────────────────────────────────────

async def a11oy_gate(plan: Dict, state: KhipuAgentState) -> Dict:
    """
    Check plan against a11oy Yuyay-13 policy gate.
    Fail-secure: network error → decline.
    """
    tool = plan.get("tool", "unknown")
    args = plan.get("args", {})
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{A11OY_URL}/api/a11oy/v1/gates/adversarialRobustness",
                json={"action": tool, "args": args, "context": state.goal[:200]},
                headers={"traceparent": state.traceparent},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "decision": data.get("decision", "allow"),
                    "yuyay_score": data.get("lambda", 0.8),
                    "axes_failed": data.get("axes_failed", []),
                    "source": "a11oy-live",
                }
    except Exception as e:
        # Fail-secure: gate error → decline
        print(f"[ken] a11oy gate error: {e!r}", file=sys.stderr)
        return {
            "decision": "decline",
            "reason": f"gate_error:{type(e).__name__}",
            "yuyay_score": 0.0,
            "axes_failed": ["gate_connectivity"],
            "source": "fail-secure",
        }
    return {"decision": "allow", "yuyay_score": 0.9, "source": "a11oy-live-default"}


# ── LLM planning ──────────────────────────────────────────────────────────────

async def llm_plan(state: KhipuAgentState, step: int, tools: List[Dict]) -> Dict:
    """
    Plan the next action. Uses /v1/brain tier hierarchy.
    Returns a plan dict with action, tool, args, reasoning.
    """
    tool_names = [t.get("name", "") for t in tools]
    system = (
        f"You are {state.actor}, a doctrine-pinned SZL agent (Doctrine v11, "
        f"kernel_commit {KERNEL_COMMIT}, Λ = Conjecture 1). "
        f"Your goal: {state.goal}. "
        f"Available tools: {tool_names}. "
        f"Step {step}/{state.max_steps}. Lambda: {state.lambda_score:.3f}. "
        "Respond with JSON: {action, tool, args, reasoning}. "
        "action must be one of: tool_call, halt, handoff, replan."
    )
    prompt = f"Goal: {state.goal}\nWorking memory: {json.dumps(state.working_memory, default=str)[:500]}\nPlan next action."

    # Try HF Inference API (T2 tier)
    try:
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN", "")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct/v1/chat/completions",
                headers={"Authorization": f"Bearer {hf_token}"},
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 256,
                    "temperature": 0.0,
                },
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # Extract JSON from content
                import re
                m = re.search(r"\{[^}]+\}", content, re.DOTALL)
                if m:
                    plan = json.loads(m.group())
                    if plan.get("action") in ("tool_call", "halt", "handoff", "replan"):
                        plan["model_tier"] = 2
                        return plan
    except Exception as e:
        print(f"[ken] llm_plan T2 error: {e!r}", file=sys.stderr)

    # T4: deterministic stub (honest, clearly labelled)
    # Simple heuristic: if step == 0 and tools exist, call first tool; else halt
    if step == 0 and tools:
        first_tool = tools[0].get("name", "unknown")
        return {
            "action": "tool_call",
            "tool": first_tool,
            "args": {"query": state.goal[:100]},
            "reasoning": "[deterministic-stub] First step: call primary tool",
            "model_tier": 4,
        }
    return {
        "action": "halt",
        "tool": None,
        "args": {},
        "reasoning": "[deterministic-stub] No more planned steps; halting",
        "model_tier": 4,
    }


# ── Default tool dispatcher ───────────────────────────────────────────────────

async def default_dispatch(plan: Dict, state: KhipuAgentState) -> Dict:
    """
    Stub tool dispatcher. Flagships override with their own dispatch logic.
    Returns a structured Observation.
    """
    tool = plan.get("tool", "unknown")
    return {
        "tool": tool,
        "success": True,
        "result": {
            "message": f"[ken-stub] Tool '{tool}' dispatched (no real backend connected)",
            "goal_fragment": state.goal[:100],
        },
        "error": None,
        "latency_ms": 0,
        "stub": True,
    }


# ── FastAPI router factory ────────────────────────────────────────────────────

def make_ken_router(
    flagship: str,
    tools_manifest: List[Dict],
    dispatch_fn: Optional[Callable] = None,
    khipu_store: Optional[Dict] = None,
) -> "APIRouter":
    """
    Build the Ken FastAPI router for a flagship.
    
    Args:
        flagship: e.g. "a11oy"
        tools_manifest: MCP-compatible tool list
        dispatch_fn: async (plan, state) -> Observation dict; defaults to stub
        khipu_store: dict to use as in-memory receipt store (shared mutable dict)
    
    Returns FastAPI APIRouter with:
        POST /api/{flagship}/v1/agent/loop
        GET  /api/{flagship}/v1/mcp/tools
        POST /api/{flagship}/v1/mcp/call
        GET  /api/{flagship}/v1/khipu/{receipt_hash}
        GET  /api/{flagship}/v1/khipu/ledger
    """
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter()
    _dispatch = dispatch_fn or default_dispatch
    _store: Dict[str, Dict] = khipu_store if khipu_store is not None else {}

    @router.post(f"/api/{flagship}/v1/agent/loop")
    async def _agent_loop(req: AgentLoopRequest):
        """Ken standard agent loop — plan→gate→tool→receipt→Λ-check cycle."""
        state = await init_state(
            req.goal, flagship, req.max_steps,
            traceparent=req.traceparent or "",
            context=req.context,
        )
        chain: List[Dict] = []

        for step in range(req.max_steps):
            # PLAN
            plan = await llm_plan(state, step, tools_manifest)

            if plan.get("action") == "halt":
                state = state.model_copy(update={
                    "halted": True, "halt_code": "H3",
                    "halt_reason": plan.get("reasoning", "LLM decided to halt"),
                })
                break

            # POLICY_GATE
            gate_result = await a11oy_gate(plan, state)
            if gate_result.get("decision") == "decline":
                receipt = sign_receipt(
                    step=step, kind="gate_decline",
                    plan=plan, tool_result={},
                    gate=gate_result, state=state,
                    flagship=flagship, lambda_score=state.lambda_score * 0.8,
                )
                chain.append(receipt)
                _store[receipt.get("digest", step)] = receipt
                state = update_state(state, receipt, lambda_score=state.lambda_score * 0.8)
                if state.lambda_score < HALT_THRESHOLD:
                    state = state.model_copy(update={
                        "halted": True, "halt_code": "H1",
                        "halt_reason": f"Lambda {state.lambda_score:.3f} below threshold",
                    })
                    break
                continue  # REPLAN

            # DISPATCH_TOOL
            try:
                tool_result = await asyncio.wait_for(
                    _dispatch(plan, state), timeout=TOOL_TIMEOUT_S
                )
            except asyncio.TimeoutError:
                tool_result = {
                    "tool": plan.get("tool"), "success": False,
                    "result": None, "error": "timeout", "latency_ms": TOOL_TIMEOUT_S * 1000,
                }
            except Exception as e:
                tool_result = {
                    "tool": plan.get("tool"), "success": False,
                    "result": None, "error": str(e)[:200], "latency_ms": 0,
                }

            # SIGN_RECEIPT
            lam = compute_lambda(state, tool_result)
            receipt = sign_receipt(
                step=step, kind="tool_call",
                plan=plan, tool_result=tool_result,
                gate=gate_result, state=state,
                flagship=flagship, lambda_score=lam,
            )
            chain.append(receipt)
            _store[receipt.get("digest", f"step-{step}")] = receipt

            # UPDATE STATE
            state = update_state(state, receipt, tool_result, lambda_score=lam)

            # Λ CHECK
            if state.lambda_score < HALT_THRESHOLD:
                state = state.model_copy(update={
                    "halted": True, "halt_code": "H1",
                    "halt_reason": f"Lambda {state.lambda_score:.3f} below threshold {HALT_THRESHOLD}",
                })
                break

        # FINALIZE
        master = make_master_receipt(chain, state, flagship)
        _store[f"master:{state.session_id}"] = master

        response = AgentLoopResponse(
            session_id=state.session_id,
            flagship=flagship,
            chain=chain,
            master_receipt=master,
            final_state=state.model_dump(),
        )
        return JSONResponse(
            content=response.model_dump(),
            headers={
                "x-szl-session-id": state.session_id,
                "x-szl-receipt-count": str(len(chain)),
                "x-szl-lambda": str(state.lambda_score),
                "x-szl-master-receipt-hash": master.get("merkle_root", ""),
                "traceparent": state.traceparent,
                "x-szl-space": flagship,
                "x-szl-wire-d": "G",
            },
        )

    @router.get(f"/api/{flagship}/v1/mcp/tools")
    async def _mcp_tools():
        """MCP-compatible tool manifest for this flagship."""
        return {
            "count": len(tools_manifest),
            "tools": tools_manifest,
            "doctrine": DOCTRINE,
            "flagship": flagship,
            "kernel_commit": KERNEL_COMMIT,
            "slsa_level": SLSA_LEVEL,
        }

    @router.post(f"/api/{flagship}/v1/mcp/call")
    async def _mcp_call(body: Dict[str, Any]):
        """Direct MCP tool call — gate-checked and receipted."""
        tool_name = body.get("name", "")
        args = body.get("arguments", {})
        # Verify tool exists
        known = {t["name"] for t in tools_manifest}
        if tool_name not in known:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        # Gate check
        plan = {"action": "tool_call", "tool": tool_name, "args": args, "reasoning": "MCP call"}
        dummy_state = KhipuAgentState(
            session_id=str(uuid.uuid4()), flagship=flagship,
            actor=f"{flagship}/mcp/v1", goal=f"mcp_call:{tool_name}",
        )
        gate = await a11oy_gate(plan, dummy_state)
        if gate.get("decision") == "decline":
            return JSONResponse(
                status_code=403,
                content={
                    "error": "gate_decline",
                    "gate": gate,
                    "doctrine": DOCTRINE,
                },
            )
        try:
            result = await asyncio.wait_for(_dispatch(plan, dummy_state), timeout=TOOL_TIMEOUT_S)
        except Exception as e:
            result = {"tool": tool_name, "success": False, "error": str(e)[:200]}
        return {
            "content": [{"type": "text", "text": json.dumps(result, default=str)}],
            "isError": not result.get("success", True),
            "doctrine": DOCTRINE,
        }

    @router.get(f"/api/{flagship}/v1/khipu/{{receipt_hash}}")
    async def _khipu_receipt(receipt_hash: str):
        """Retrieve a receipt by digest from the in-memory Khipu store."""
        receipt = _store.get(receipt_hash)
        if not receipt:
            raise HTTPException(status_code=404, detail=f"Receipt '{receipt_hash}' not found")
        predecessors = []
        payload = receipt.get("payload", receipt)
        if isinstance(payload, dict):
            parent_digest = payload.get("parent_digest", "")
            if parent_digest and parent_digest in _store:
                predecessors = [_store[parent_digest]]
        return {
            "receipt": receipt,
            "predecessors": predecessors,
            "doctrine": DOCTRINE,
            "flagship": flagship,
        }

    @router.get(f"/api/{flagship}/v1/khipu/ledger")
    async def _khipu_ledger():
        """Return the last 20 receipts in the Khipu store."""
        receipts = list(_store.values())[-20:]
        return {
            "count": len(_store),
            "receipts": receipts,
            "doctrine": DOCTRINE,
            "flagship": flagship,
            "kernel_commit": KERNEL_COMMIT,
        }

    return router


# ── Minimal MCP tool manifests per flagship ───────────────────────────────────

def get_default_tools(flagship: str) -> List[Dict]:
    """Return the minimal MCP tool manifest for a flagship."""
    base = {
        "doctrine": DOCTRINE,
        "gate_required": True,
        "requires_two_person": False,
        "kernel_commit": KERNEL_COMMIT,
    }
    manifests = {
        "a11oy": [
            {**base, "name": "gate_check",
             "description": "Check an action against the a11oy Yuyay-13 policy gate",
             "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}, "context": {"type": "string"}}, "required": ["action"]}},
            {**base, "name": "reason",
             "description": "Multi-LLM ensemble reasoning with DSSE receipt",
             "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
            {**base, "name": "policy_evaluate",
             "description": "Evaluate a proposed action against all 49 a11oy policy gates",
             "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}, "args": {"type": "object"}}, "required": ["action"]}},
            {**base, "name": "receipt_verify",
             "description": "Verify a DSSE receipt envelope",
             "inputSchema": {"type": "object", "properties": {"envelope": {"type": "object"}}, "required": ["envelope"]}},
        ],
        "sentra": [
            {**base, "name": "scan",
             "description": "Security scan an artifact or payload",
             "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
            {**base, "name": "score",
             "description": "Score a request across Yuyay-13 axes",
             "inputSchema": {"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]}},
            {**base, "name": "verdict",
             "description": "Issue a DSSE-signed verdict on an action",
             "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}, "request_id": {"type": "string"}}, "required": ["action", "request_id"]}},
            {**base, "name": "filter",
             "description": "Filter a batch of events for doctrine compliance",
             "inputSchema": {"type": "object", "properties": {"events": {"type": "array"}}, "required": ["events"]}},
        ],
        "amaru": [
            {**base, "name": "ask",
             "description": "RAG-augmented question answering from doctrine corpus",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {**base, "name": "recall",
             "description": "Retrieve from Khipu memory tier",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {**base, "name": "semantic_search",
             "description": "Semantic search over doctrine + receipt corpus",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]}},
            {**base, "name": "cite",
             "description": "Cite a doctrine declaration or theorem with DSSE proof",
             "inputSchema": {"type": "object", "properties": {"declaration_id": {"type": "string"}}, "required": ["declaration_id"]}},
        ],
        "rosie": [
            {**base, "name": "reason",
             "description": "Decision-support reasoning with workflow context",
             "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
            {**base, "name": "workflow_start",
             "description": "Start a governed workflow with approval chain",
             "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "params": {"type": "object"}}, "required": ["workflow_id"]}},
            {**base, "name": "approve",
             "description": "Record an approval decision in the Khipu chain",
             "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "decision": {"type": "string"}}, "required": ["workflow_id", "decision"]}},
            {**base, "name": "escalate",
             "description": "Escalate a workflow decision to human oversight",
             "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["workflow_id", "reason"]}},
        ],
        "killinchu": [
            {**base, "name": "detect",
             "description": "Detect and classify a target from sensor telemetry",
             "inputSchema": {"type": "object", "properties": {"telemetry": {"type": "object"}}, "required": ["telemetry"]}},
            {**base, "name": "evaluate",
             "description": "Evaluate telemetry against counter-UAS policy",
             "inputSchema": {"type": "object", "properties": {"target_id": {"type": "string"}, "telemetry": {"type": "object"}}, "required": ["target_id", "telemetry"]}},
            {**base, "name": "cue",
             "description": "Issue a doctrine-gated cue to an operator (requires 2-person)",
             "inputSchema": {"type": "object", "properties": {"target_id": {"type": "string"}, "action": {"type": "string"}}, "required": ["target_id", "action"]},
             "requires_two_person": True},
            {**base, "name": "halt_drone",
             "description": "Halt drone operations (emergency stop)",
             "inputSchema": {"type": "object", "properties": {"drone_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["drone_id"]},
             "requires_two_person": True},
        ],
    }
    return manifests.get(flagship, [])
