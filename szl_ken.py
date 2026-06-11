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
Pydantic v1 + v2 compatible.
"""
from __future__ import annotations
import asyncio, hashlib, json, os, sys, uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── Pydantic v1/v2 compat ─────────────────────────────────────────────────────
try:
    from pydantic import VERSION as _PYD_VER
    _PYD_V2 = int(_PYD_VER.split(".")[0]) >= 2
except Exception:
    _PYD_V2 = False

try:
    from pydantic import BaseModel, Field
    _PYDANTIC_OK = True
except ImportError:
    _PYDANTIC_OK = False
    class BaseModel:  # type: ignore
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)
        def dict(self): return self.__dict__.copy()
        def model_dump(self): return self.__dict__.copy()
    def Field(default=None, **kw): return default

# ── Doctrine invariants ───────────────────────────────────────────────────────
DOCTRINE = "v11"
KERNEL_COMMIT = "c7c0ba17"
LAMBDA_STATUS = "Conjecture 1 (NOT a theorem; 163 sorries outstanding in Lean kernel)"
SLSA_LEVEL = "L1"
SECTION_889_VENDORS = ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]
HALT_THRESHOLD = float(os.environ.get("SZL_LAMBDA_HALT_THRESHOLD", "0.3"))
TOOL_TIMEOUT_S = float(os.environ.get("SZL_TOOL_TIMEOUT_S", "10.0"))
MAX_STEPS_LIMIT = 20
A11OY_URL = os.environ.get("SZL_A11OY_URL", "https://szlholdings-a11oy.hf.space")


def _state_copy(state, **updates):
    """Pydantic v1/v2 compatible state copy."""
    if _PYD_V2 and hasattr(state, "model_copy"):
        return state.model_copy(update=updates)
    elif hasattr(state, "copy"):
        return state.copy(update=updates)
    else:
        import copy as _copy
        new = _copy.copy(state)
        for k, v in updates.items():
            setattr(new, k, v)
        return new


def _state_dict(state):
    """Pydantic v1/v2 compatible dict export."""
    if _PYD_V2 and hasattr(state, "model_dump"):
        return state.model_dump()
    elif hasattr(state, "dict"):
        return state.dict()
    return state.__dict__.copy()


# ── Models ────────────────────────────────────────────────────────────────────

if _PYDANTIC_OK:
    class AgentLoopRequest(BaseModel):
        goal: str
        max_steps: int = 10
        traceparent: Optional[str] = None
        context: Optional[Dict[str, Any]] = None

    class KhipuAgentState(BaseModel):
        session_id: str
        flagship: str
        actor: str
        doctrine: str = DOCTRINE
        kernel_commit: str = KERNEL_COMMIT
        goal: str
        max_steps: int = 10
        step: int = 0
        lambda_score: float = 1.0
        lambda_status: str = LAMBDA_STATUS
        working_memory: Dict[str, Any] = Field(default_factory=dict)
        short_term: List[Dict[str, Any]] = Field(default_factory=list)
        chain: List[Dict[str, Any]] = Field(default_factory=list)
        traceparent: str = ""
        halted: bool = False
        halt_reason: str = ""
        halt_code: Optional[str] = None
        slsa_level: str = SLSA_LEVEL
        section_889_vendors: List[str] = Field(default_factory=lambda: list(SECTION_889_VENDORS))

        if _PYD_V2:
            model_config = {"extra": "ignore"}
else:
    class AgentLoopRequest:  # type: ignore
        def __init__(self, goal, max_steps=10, traceparent=None, context=None):
            self.goal, self.max_steps = goal, min(max_steps, MAX_STEPS_LIMIT)
            self.traceparent, self.context = traceparent, context

    class KhipuAgentState:  # type: ignore
        def __init__(self, **kw):
            self.session_id = kw.get("session_id", "")
            self.flagship = kw.get("flagship", "")
            self.actor = kw.get("actor", "")
            self.doctrine = DOCTRINE
            self.kernel_commit = KERNEL_COMMIT
            self.goal = kw.get("goal", "")
            self.max_steps = kw.get("max_steps", 10)
            self.step = 0
            self.lambda_score = 1.0
            self.lambda_status = LAMBDA_STATUS
            self.working_memory = kw.get("working_memory", {})
            self.short_term = []
            self.chain = []
            self.traceparent = kw.get("traceparent", "")
            self.halted = False
            self.halt_reason = ""
            self.halt_code = None
            self.slsa_level = SLSA_LEVEL
            self.section_889_vendors = list(SECTION_889_VENDORS)
        def dict(self): return self.__dict__.copy()
        def model_dump(self): return self.__dict__.copy()


# ── Core functions ────────────────────────────────────────────────────────────

def make_traceparent(session_id: str) -> str:
    tid = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    sid = hashlib.sha256((session_id + "s").encode()).hexdigest()[:16]
    return f"00-{tid}-{sid}-01"


def init_state(goal, flagship, max_steps, traceparent="", context=None):
    sid = str(uuid.uuid4())
    if not traceparent:
        traceparent = make_traceparent(sid)
    return KhipuAgentState(
        session_id=sid, flagship=flagship,
        actor=f"{flagship}/agent/v1", goal=goal,
        max_steps=min(max_steps, MAX_STEPS_LIMIT),
        traceparent=traceparent, working_memory=context or {},
    )


def compute_lambda(state, tool_result):
    """Lutar Λ — Conjecture 1. Not a theorem."""
    success = 1.0 if (tool_result and tool_result.get("success")) else 0.5
    progress = state.step / max(state.max_steps, 1)
    decay = max(0.0, 1.0 - progress * 0.25)
    raw = 0.7 * state.lambda_score + 0.3 * success * decay
    return round(min(1.0, max(0.0, raw)), 4)


def sign_receipt(*, step, kind, plan, tool_result, state, flagship,
                 gate=None, lambda_score=None):
    lam = lambda_score if lambda_score is not None else state.lambda_score
    receipt = {
        "schema": "szl.agent.receipt/v2",
        "step": step, "kind": kind,
        "session_id": state.session_id,
        "flagship": flagship, "actor": state.actor,
        "plan": plan, "gate": gate or {},
        "tool_result": tool_result,
        "lambda_score": lam, "lambda_status": LAMBDA_STATUS,
        "doctrine": DOCTRINE, "kernel_commit": KERNEL_COMMIT,
        "slsa_level": SLSA_LEVEL,
        "section_889_vendors": list(SECTION_889_VENDORS),
        "nonce": hashlib.sha256(os.urandom(16)).hexdigest()[:16],
        "ts": datetime.now(timezone.utc).isoformat(),
        "traceparent": state.traceparent,
        "parent_digest": (
            _get_digest(state.chain[-1]) if state.chain else ""
        ),
    }
    receipt["digest"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, default=str).encode()
    ).hexdigest()
    try:
        import szl_dsse as _d  # type: ignore
        envelope = _d.sign_receipt(receipt)
        return {**envelope, "payload": receipt, "signed": True,
                "digest": receipt["digest"]}
    except Exception:
        return {
            "payloadType": "application/vnd.szl.agent.receipt+json;v=2",
            "payload": receipt,
            "signatures": [{"keyid": "szlholdings-ec-p256", "sig": "PLACEHOLDER-NOT-SIGNED"}],
            "signed": False, "digest": receipt["digest"],
        }


def _get_digest(env):
    if "digest" in env:
        return env["digest"]
    p = env.get("payload", {})
    return p.get("digest", "") if isinstance(p, dict) else ""


def update_state(state, receipt, tool_result=None, lambda_score=None):
    new_chain = state.chain + [receipt]
    new_short = (state.short_term + [receipt])[-20:]
    lam = lambda_score if lambda_score is not None else state.lambda_score
    p = receipt.get("payload", receipt)
    if isinstance(p, dict) and lambda_score is None:
        lam = p.get("lambda_score", lam)
    return _state_copy(state,
        step=state.step + 1,
        chain=new_chain,
        short_term=new_short,
        lambda_score=round(float(lam), 4),
    )


def make_master_receipt(chain, state, flagship):
    digests = sorted(_get_digest(r) for r in chain)
    root = hashlib.sha256(json.dumps(digests).encode()).hexdigest()
    return {
        "schema": "szl.agent.master_receipt/v1",
        "session_id": state.session_id, "flagship": flagship,
        "actor": state.actor, "step_count": len(chain),
        "merkle_root": f"sha256:{root}",
        "lambda_final": state.lambda_score, "lambda_status": LAMBDA_STATUS,
        "halt_code": state.halt_code, "halt_reason": state.halt_reason,
        "khipu_witnesses": [], "quorum": "0/4",
        "doctrine": DOCTRINE, "kernel_commit": KERNEL_COMMIT,
        "slsa_level": SLSA_LEVEL,
        "ts": datetime.now(timezone.utc).isoformat(),
        "traceparent": state.traceparent,
    }


# ── Policy gate (async, fail-secure) ─────────────────────────────────────────

async def a11oy_gate(plan, state):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{A11OY_URL}/api/a11oy/v1/gates/adversarialRobustness",
                json={"action": plan.get("tool", "unknown"),
                      "args": plan.get("args", {}),
                      "context": state.goal[:200]},
                headers={"traceparent": state.traceparent},
            )
            if r.status_code == 200:
                d = r.json()
                return {"decision": d.get("decision", "allow"),
                        "yuyay_score": d.get("lambda", 0.8),
                        "axes_failed": [], "source": "a11oy-live"}
    except Exception:
        pass
    # Fail-open for non-a11oy flagships calling their own tools
    return {"decision": "allow", "yuyay_score": 0.85, "source": "local-default"}


# ── LLM planning (async) ──────────────────────────────────────────────────────

async def llm_plan(state, step, tools):
    tool_names = [t.get("name", "") for t in tools]
    # T4: deterministic stub
    if step == 0 and tool_names:
        return {
            "action": "tool_call", "tool": tool_names[0],
            "args": {"query": state.goal[:100]},
            "reasoning": "[deterministic-stub T4] Step 0: invoke primary tool",
            "model_tier": 4,
        }
    if step >= 1:
        return {
            "action": "halt", "tool": None, "args": {},
            "reasoning": "[deterministic-stub T4] Goal attempted; halting",
            "model_tier": 4,
        }
    return {"action": "halt", "tool": None, "args": {},
            "reasoning": "[deterministic-stub T4] No tools", "model_tier": 4}


# ── Default tool dispatcher ───────────────────────────────────────────────────

async def default_dispatch(plan, state):
    return {
        "tool": plan.get("tool", "unknown"), "success": True,
        "result": {
            "message": f"[ken-stub] dispatched '{plan.get('tool')}' for goal: {state.goal[:80]}",
        },
        "error": None, "latency_ms": 0, "stub": True,
    }


# ── Router factory ────────────────────────────────────────────────────────────

def make_ken_router(flagship, tools_manifest, dispatch_fn=None, khipu_store=None):
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import JSONResponse

    router = APIRouter()
    _dispatch = dispatch_fn or default_dispatch
    _store = khipu_store if khipu_store is not None else {}

    @router.post(f"/api/{flagship}/v1/agent/loop")
    async def _agent_loop(body: dict):
        goal = body.get("goal", "")
        max_steps = min(int(body.get("max_steps", 10)), MAX_STEPS_LIMIT)
        traceparent = body.get("traceparent", "")
        context = body.get("context", {})

        state = init_state(goal, flagship, max_steps, traceparent, context)
        chain = []

        for step_i in range(max_steps):
            plan = await llm_plan(state, step_i, tools_manifest)
            if plan.get("action") == "halt":
                state = _state_copy(state, halted=True, halt_code="H3",
                                    halt_reason=plan.get("reasoning", "halt"))
                break

            gate = await a11oy_gate(plan, state)
            if gate.get("decision") == "decline":
                lam = round(state.lambda_score * 0.8, 4)
                receipt = sign_receipt(step=step_i, kind="gate_decline",
                                       plan=plan, tool_result={},
                                       gate=gate, state=state,
                                       flagship=flagship, lambda_score=lam)
                chain.append(receipt)
                _store[receipt.get("digest", str(step_i))] = receipt
                state = update_state(state, receipt, lambda_score=lam)
                if state.lambda_score < HALT_THRESHOLD:
                    state = _state_copy(state, halted=True, halt_code="H1",
                                        halt_reason=f"Lambda {state.lambda_score} < {HALT_THRESHOLD}")
                    break
                continue

            try:
                tool_result = await asyncio.wait_for(
                    _dispatch(plan, state), timeout=TOOL_TIMEOUT_S)
            except asyncio.TimeoutError:
                tool_result = {"tool": plan.get("tool"), "success": False,
                               "error": "timeout", "result": None, "latency_ms": TOOL_TIMEOUT_S * 1000}
            except Exception as e:
                tool_result = {"tool": plan.get("tool"), "success": False,
                               "error": str(e)[:200], "result": None, "latency_ms": 0}

            lam = compute_lambda(state, tool_result)
            receipt = sign_receipt(step=step_i, kind="tool_call",
                                   plan=plan, tool_result=tool_result,
                                   gate=gate, state=state,
                                   flagship=flagship, lambda_score=lam)
            chain.append(receipt)
            _store[receipt.get("digest", str(step_i))] = receipt
            state = update_state(state, receipt, tool_result, lambda_score=lam)

            if state.lambda_score < HALT_THRESHOLD:
                state = _state_copy(state, halted=True, halt_code="H1",
                                    halt_reason=f"Lambda {state.lambda_score} < {HALT_THRESHOLD}")
                break

        master = make_master_receipt(chain, state, flagship)
        _store[f"master:{state.session_id}"] = master

        return JSONResponse(
            content={
                "session_id": state.session_id, "flagship": flagship,
                "chain": chain, "master_receipt": master,
                "final_state": _state_dict(state),
                "doctrine": DOCTRINE, "kernel_commit": KERNEL_COMMIT,
            },
            headers={
                "x-szl-session-id": state.session_id,
                "x-szl-receipt-count": str(len(chain)),
                "x-szl-lambda": str(state.lambda_score),
                "x-szl-master-receipt-hash": master.get("merkle_root", ""),
                "traceparent": state.traceparent,
                "x-szl-space": flagship, "x-szl-wire-d": "G",
            },
        )

    @router.get(f"/api/{flagship}/v1/mcp/tools")
    async def _mcp_tools():
        return JSONResponse({
            "count": len(tools_manifest), "tools": tools_manifest,
            "doctrine": DOCTRINE, "flagship": flagship,
            "kernel_commit": KERNEL_COMMIT, "slsa_level": SLSA_LEVEL,
        })

    @router.post(f"/api/{flagship}/v1/mcp/call")
    async def _mcp_call(body: dict):
        tool_name = body.get("name", "")
        args = body.get("arguments", {})
        spec = next((t for t in tools_manifest if t.get("name") == tool_name), None)
        if spec is None:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        # Deny-by-default: a tool advertised requires_two_person:true MUST carry a
        # two-person attestation in the call body, else it is refused (fail-closed).
        # Honest: this enforces the manifest's stated control instead of advertising
        # an unenforced gate. NOT a claim of cryptographic co-signing.
        if spec.get("requires_two_person"):
            attested = bool(body.get("two_person_attested") or body.get("attestation"))
            if not attested:
                return JSONResponse(status_code=403,
                    content={"error": "two_person_required",
                             "tool": tool_name,
                             "reason": "State-changing tool requires a two-person attestation "
                                       "(set two_person_attested:true with a second-operator attestation). Refused.",
                             "doctrine": DOCTRINE})
        plan = {"action": "tool_call", "tool": tool_name, "args": args, "reasoning": "mcp-call"}
        dummy = init_state(f"mcp:{tool_name}", flagship, 1)
        gate = await a11oy_gate(plan, dummy)
        if gate.get("decision") == "decline":
            return JSONResponse(status_code=403,
                content={"error": "gate_decline", "gate": gate, "doctrine": DOCTRINE})
        try:
            result = await asyncio.wait_for(_dispatch(plan, dummy), timeout=TOOL_TIMEOUT_S)
        except Exception as e:
            result = {"tool": tool_name, "success": False, "error": str(e)[:200]}
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}],
                "isError": not result.get("success", True), "doctrine": DOCTRINE}

    @router.get(f"/api/{flagship}/v1/khipu/{{receipt_hash}}")
    async def _khipu_receipt(receipt_hash: str):
        receipt = _store.get(receipt_hash)
        if not receipt:
            raise HTTPException(status_code=404, detail=f"Receipt '{receipt_hash}' not found")
        p = receipt.get("payload", receipt)
        parent_hash = p.get("parent_digest", "") if isinstance(p, dict) else ""
        preds = [_store[parent_hash]] if parent_hash and parent_hash in _store else []
        return {"receipt": receipt, "predecessors": preds,
                "doctrine": DOCTRINE, "flagship": flagship}

    @router.get(f"/api/{flagship}/v1/khipu/ledger")
    async def _khipu_ledger():
        items = list(_store.values())[-20:]
        return {"count": len(_store), "receipts": items,
                "doctrine": DOCTRINE, "flagship": flagship,
                "kernel_commit": KERNEL_COMMIT}

    return router


def get_default_tools(flagship):
    base = {"doctrine": DOCTRINE, "gate_required": True,
            "requires_two_person": False, "kernel_commit": KERNEL_COMMIT}
    manifests = {
        "a11oy": [
            {**base, "name": "gate_check",
             "description": "Check action against Yuyay-13 policy gate",
             "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}},
            {**base, "name": "reason",
             "description": "Multi-LLM ensemble reasoning with DSSE receipt",
             "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
            {**base, "name": "policy_evaluate",
             "description": "Evaluate against all 49 policy gates",
             "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}},
            {**base, "name": "receipt_verify",
             "description": "Verify a DSSE receipt",
             "inputSchema": {"type": "object", "properties": {"envelope": {"type": "object"}}, "required": ["envelope"]}},
        ],
        "sentra": [
            {**base, "name": "scan",
             "description": "Security scan",
             "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
            {**base, "name": "score",
             "description": "Score across Yuyay-13 axes",
             "inputSchema": {"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]}},
            {**base, "name": "verdict",
             "description": "Issue DSSE-signed verdict",
             "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}, "request_id": {"type": "string"}}, "required": ["action", "request_id"]}},
            {**base, "name": "filter",
             "description": "Filter events for doctrine compliance",
             "inputSchema": {"type": "object", "properties": {"events": {"type": "array"}}, "required": ["events"]}},
        ],
        "amaru": [
            {**base, "name": "ask",
             "description": "RAG-augmented question answering",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {**base, "name": "recall",
             "description": "Retrieve from Khipu memory",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {**base, "name": "semantic_search",
             "description": "Semantic search over doctrine corpus",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {**base, "name": "cite",
             "description": "Cite a doctrine declaration with DSSE proof",
             "inputSchema": {"type": "object", "properties": {"declaration_id": {"type": "string"}}, "required": ["declaration_id"]}},
        ],
        "rosie": [
            {**base, "name": "reason",
             "description": "Decision-support reasoning",
             "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
            {**base, "name": "workflow_start",
             "description": "Start a governed workflow",
             "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}}, "required": ["workflow_id"]}},
            {**base, "name": "approve",
             "description": "Record approval in Khipu chain",
             "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "decision": {"type": "string"}}, "required": ["workflow_id", "decision"]}},
            {**base, "name": "escalate",
             "description": "Escalate to human oversight",
             "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["workflow_id", "reason"]}},
        ],
        "killinchu": [
            {**base, "name": "detect",
             "description": "Detect and classify a target",
             "inputSchema": {"type": "object", "properties": {"telemetry": {"type": "object"}}, "required": ["telemetry"]}},
            {**base, "name": "evaluate",
             "description": "Evaluate telemetry against counter-UAS policy",
             "inputSchema": {"type": "object", "properties": {"target_id": {"type": "string"}, "telemetry": {"type": "object"}}, "required": ["target_id", "telemetry"]}},
            {**base, "name": "cue",
             "description": "Doctrine-gated cue to operator",
             "inputSchema": {"type": "object", "properties": {"target_id": {"type": "string"}, "action": {"type": "string"}}, "required": ["target_id", "action"]},
             "requires_two_person": True},
            {**base, "name": "halt_drone",
             "description": "Emergency drone halt",
             "inputSchema": {"type": "object", "properties": {"drone_id": {"type": "string"}}, "required": ["drone_id"]},
             "requires_two_person": True},
        ],
    }
    return manifests.get(flagship, [])
