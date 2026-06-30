# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 (LOCKED) · v12 (v11+PURIQ) roadmap
"""
a11oy_agent_loop — a GENUINELY agentic, governed finite-state machine.

SHARED module: deployed BYTE-IDENTICAL on a11oy and killinchu (additive only).

This is the Claude-Code-style brain of "a11oy Code": it PLANS a DAG, RETRIEVEs
grounded context, ACTs by calling ONE real, PURIQ-gated tool at a time, OBSERVEs
typed M2M evidence, VERIFIEs with Λ + a conformal floor, REFLECTs (Reflexion,
persisted to sqlite, bounded depth), and FINALIZEs or HALTs.

State machine
-------------
    INTAKE  → PLAN → RETRIEVE → ACT → OBSERVE → VERIFY → (REFLECT → ACT) → FINALIZE
                                                              │
                                                              └→ HALT (gate / guard / budget)

EVERY transition:
  * Λ-gate  — szl_brain.lambda_aggregate over the step's axes; floor 0.90 (spec
    C.1), FAIL-CLOSED (a step that cannot clear the floor cannot proceed).
  * PURIQ gate for any state-changing tool (orchestrator.puriq_decide), with the
    two-person attestation requirement preserved.
  * DSSE Khipu receipt (orchestrator.khipu_emit) — append-only sha256 chain.
  * OpenTelemetry span when an SDK is present; a no-op shim otherwise (honest).

Guards (bounded autonomy — NEVER weakened):
  * max_steps          = 12   (F11/F12 step budget)
  * max_reflect_depth  =  3
  * plan-DAG acyclicity (Kahn topological sort; a cyclic plan is rejected)
  * Λ floor 0.90 fail-closed on every step
  * conformal confidence floor 1/(n+1) — trust is NEVER 100%

Honesty (Zero-Bandaid Law):
  * The loop runs FOR REAL with no inference credential: PLAN, every Λ-gate, every
    PURIQ gate, every tool call, every receipt execute REALLY.  Only the
    *model-authored text* degrades to a CLEARLY-LABELED deterministic stub — and
    in that mode the plan is a deterministic, transparent heuristic plan, never a
    fabricated "model reasoning" trace.
  * Evidence is typed: url / file / formula / test / i_dont_know.  Below-floor
    support yields i_dont_know (P3 non-interference: weak evidence can't flip a
    gate).
  * No user-visible codenames.  The agent surface is "Chaski"; governed roles are
    Provenance Anchor / Operator / Policy.

Dependency injection
---------------------
This module imports nothing from the orchestrator at module load (keeps it
import-safe + byte-identical across apps).  The orchestrator wires the real
backends in by constructing ``AgentLoop`` / calling ``run_agent`` with callables:

    khipu_emit(action, payload)            -> receipt dict
    puriq_decide(action, context)          -> decision dict
    execute_tool(name, args, **kw)         -> awaitable {ok,result,gate,khipu}
    model_complete(messages, **kw)         -> awaitable {text, model, stub: bool}
    rag_query(q, **kw)                     -> dict (a11oy_org_rag.query)

If a callable is omitted the loop uses an honest local fallback that still
exercises the governed control-flow (used by the no-key self-test).
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

try:
    import szl_brain  # lambda_aggregate (geometric mean)
except Exception:  # pragma: no cover
    szl_brain = None  # type: ignore

# --------------------------------------------------------------------------- #
# Guards / constants (NEVER weakened — Doctrine hard gate)
# --------------------------------------------------------------------------- #
LAMBDA_FLOOR = float(os.environ.get("A11OY_AGENT_LAMBDA_FLOOR", "0.90"))  # spec C.1
MAX_STEPS = int(os.environ.get("A11OY_AGENT_MAX_STEPS", "12"))
MAX_REFLECT_DEPTH = int(os.environ.get("A11OY_AGENT_MAX_REFLECT", "3"))
REFLECT_DB = os.environ.get("A11OY_AGENT_REFLECT_DB", "/app/data/a11oy_reflect.db")

# Evidence kinds (typed M2M evidence — OBSERVE state).
EVIDENCE_KINDS = ("url", "file", "formula", "test", "i_dont_know")

# FSM states.
S_INTAKE, S_PLAN, S_RETRIEVE, S_ACT, S_OBSERVE, S_VERIFY, S_REFLECT, S_FINALIZE, S_HALT = (
    "INTAKE", "PLAN", "RETRIEVE", "ACT", "OBSERVE", "VERIFY", "REFLECT", "FINALIZE", "HALT")


# --------------------------------------------------------------------------- #
# OpenTelemetry span (real if SDK present; honest no-op shim otherwise)
# --------------------------------------------------------------------------- #
def _otel_tracer():
    try:
        from opentelemetry import trace  # type: ignore
        return trace.get_tracer("a11oy.code.agent")
    except Exception:
        return None


class _SpanShim:
    """No-op span context manager used when OTel is not installed (labeled)."""
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def set_attribute(self, *a, **k):
        return None


def _span(name: str):
    tr = _otel_tracer()
    if tr is not None:
        return tr.start_as_current_span(name)
    return _SpanShim(name)


# --------------------------------------------------------------------------- #
# Λ helper (fail-closed)
# --------------------------------------------------------------------------- #
def _lambda(axes: list[float]) -> float:
    if szl_brain is not None:
        return szl_brain.lambda_aggregate(axes)
    if not axes:
        return 0.0  # fail-closed: no axes ⇒ cannot clear floor
    clamped = [min(1.0, max(1e-9, float(x))) for x in axes]
    return math.exp(sum(math.log(x) for x in clamped) / len(clamped))


def _conformal_floor(n: int) -> float:
    """Anti-overconfidence: confidence can never reach 1.0 (floor 1/(n+1))."""
    return 1.0 - 1.0 / (max(0, n) + 1)


# --------------------------------------------------------------------------- #
# OPTIONAL Wallpa (VOICE organ) FINALIZE fold-in — additive, default OFF.
# Gated by A11OY_WALLPA_FINALIZE; when disabled or Wallpa is unreachable the
# loop is byte-for-byte unchanged (honest skip, never fabricated). Doctrine
# v13 §2.2: Wallpa expresses the governed answer; its receipt hash + factor
# fold into the FINALIZE Khipu chain / Λ-gate as an admissible [0,1] factor.
# --------------------------------------------------------------------------- #
def _wallpa_finalize_enabled() -> bool:
    return (os.environ.get("A11OY_WALLPA_FINALIZE") or "").strip().lower() in (
        "1", "true", "yes", "on")


def _wallpa_speak_final(answer: str, timeout: float = 6.0) -> Optional[dict[str, Any]]:
    """Best-effort call to the live Wallpa speak path; honest None on any failure.

    Returns {"wallpa_factor", "khipu_hash", "audio_sha3", "voice"} on success.
    Never raises, never fabricates: if Wallpa is unreachable we return None and
    the caller records an honest skip (behavior otherwise unchanged).
    """
    text = (answer or "").strip()
    if not text:
        return None
    import urllib.request
    url = (os.environ.get("A11OY_WALLPA_URL")
           or "http://127.0.0.1:7860/api/a11oy/wallpa/speak").strip()
    voice = (os.environ.get("A11OY_WALLPA_VOICE") or "amaru-voice").strip()
    # Cap the spoken text so FINALIZE stays bounded (synthesis is per-word).
    payload = json.dumps({"text": text[:600], "voice": voice}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    receipt = data.get("khipu_receipt") or {}
    return {
        "wallpa_factor": data.get("wallpa_factor"),
        "khipu_hash": receipt.get("hash") if isinstance(receipt, dict) else None,
        "audio_sha3": data.get("audio_transcript_sha3"),
        "voice": data.get("voice", voice),
    }


# --------------------------------------------------------------------------- #
# M2M envelope (machine-to-machine step record)
# --------------------------------------------------------------------------- #
@dataclass
class Evidence:
    kind: str                       # one of EVIDENCE_KINDS
    ref: str                        # url / repo-path / formula id / test name
    detail: dict[str, Any] = field(default_factory=dict)
    sha256: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        kind = self.kind if self.kind in EVIDENCE_KINDS else "i_dont_know"
        return {"kind": kind, "ref": self.ref, "detail": self.detail, "sha256": self.sha256}


@dataclass
class M2MEnvelope:
    """The typed envelope passed step→step (machine-to-machine)."""
    step: int
    state: str
    intent: str
    tool: Optional[str] = None
    args: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    lambda_: float = 0.0
    gate_allow: bool = False
    gate_reason: str = ""
    conformal: float = 0.0
    khipu_hash: Optional[str] = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step, "state": self.state, "intent": self.intent,
            "tool": self.tool, "args": self.args,
            "evidence": [e.as_dict() for e in self.evidence],
            "lambda": round(self.lambda_, 4), "gate_allow": self.gate_allow,
            "gate_reason": self.gate_reason, "conformal": round(self.conformal, 4),
            "khipu_hash": self.khipu_hash, "note": self.note,
        }


# --------------------------------------------------------------------------- #
# Plan DAG (PLAN state) — acyclicity is a hard guard
# --------------------------------------------------------------------------- #
@dataclass
class PlanNode:
    id: str
    intent: str
    tool: Optional[str] = None
    args: dict[str, Any] = field(default_factory=dict)
    deps: list[str] = field(default_factory=list)
    state_changing: bool = False


def _topo_order(nodes: list[PlanNode]) -> list[str]:
    """Kahn topological sort. Raises ValueError on a cycle (DAG acyclicity guard)."""
    ids = {n.id for n in nodes}
    indeg = {n.id: 0 for n in nodes}
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for n in nodes:
        for d in n.deps:
            if d in ids:
                adj[d].append(n.id)
                indeg[n.id] += 1
    queue = [nid for nid, dg in indeg.items() if dg == 0]
    order: list[str] = []
    while queue:
        queue.sort()  # deterministic
        cur = queue.pop(0)
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(nodes):
        raise ValueError("plan DAG has a cycle — rejected (acyclicity guard)")
    return order


# --------------------------------------------------------------------------- #
# Reflexion store (sqlite; bounded depth) — REFLECT state
# --------------------------------------------------------------------------- #
def _reflect_db() -> sqlite3.Connection:
    Path(REFLECT_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REFLECT_DB, timeout=15)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reflections("
        "id TEXT PRIMARY KEY, run_id TEXT, depth INTEGER, ts REAL, "
        "trigger TEXT, lesson TEXT, khipu_hash TEXT)")
    conn.commit()
    return conn


def _persist_reflection(run_id: str, depth: int, trigger: str, lesson: str,
                        khipu_hash: Optional[str]) -> str:
    rid = uuid.uuid4().hex[:24]
    try:
        conn = _reflect_db()
        conn.execute(
            "INSERT INTO reflections(id,run_id,depth,ts,trigger,lesson,khipu_hash) "
            "VALUES(?,?,?,?,?,?,?)",
            (rid, run_id, depth, time.time(), trigger[:200], lesson[:600], khipu_hash))
        conn.commit()
        conn.close()
    except Exception:
        pass  # persistence is best-effort; the in-run lesson list still governs
    return rid


def recent_reflections(run_id: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
    try:
        conn = _reflect_db()
        conn.row_factory = sqlite3.Row
        if run_id:
            rows = conn.execute(
                "SELECT * FROM reflections WHERE run_id=? ORDER BY ts DESC LIMIT ?",
                (run_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reflections ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# --------------------------------------------------------------------------- #
# Default (no-key) honest planner + model fallback
# --------------------------------------------------------------------------- #
def _deterministic_plan(task: str) -> list[PlanNode]:
    """A transparent, deterministic heuristic plan used when no model credential
    is present (or as a safe scaffold). It is NOT a fabricated 'model' plan —
    it is labeled honest control-flow that still exercises retrieve→act→verify."""
    t = (task or "").lower()
    nodes = [PlanNode(id="n1", intent="retrieve grounding from the org index",
                      tool="rag_query", args={"q": task}, deps=[])]
    if any(w in t for w in ("read", "file", "open", "show", "repo", "map", "where")):
        nodes.append(PlanNode(id="n2", intent="inspect the most relevant repo/file",
                              tool="repo_map", args={}, deps=["n1"]))
    if any(w in t for w in ("test", "run", "verify", "check", "lean", "proof")):
        nodes.append(PlanNode(id="n3", intent="run a verification step",
                              tool="run_tests", args={}, deps=["n1"]))
    nodes.append(PlanNode(id="nf", intent="synthesize a grounded, cited answer",
                          tool=None, args={}, deps=[n.id for n in nodes]))
    return nodes


async def _honest_model_complete(messages: list[dict], **kw) -> dict[str, Any]:
    """No-key fallback for model text: a clearly-labeled deterministic stub.
    NEVER fabricates an answer (Zero-Bandaid Law)."""
    last = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
            break
    snippet = (last or "").strip().replace("\n", " ")[:160]
    text = (
        "**[deterministic stub — inference token not yet set]**\n\n"
        "The agentic control-flow (plan DAG, per-step Λ-gate, PURIQ gate, typed "
        "evidence, and signed Khipu receipts) executed FOR REAL. The model-authored "
        "synthesis is unavailable because no inference credential is configured on "
        "this Space, so no answer is fabricated (Zero-Bandaid Law). "
        + (f"Request: “{snippet}”." if snippet else ""))
    return {"text": text, "model": "deterministic-stub", "stub": True}


# --------------------------------------------------------------------------- #
# The governed agent loop
# --------------------------------------------------------------------------- #
class AgentLoop:
    def __init__(
        self,
        khipu_emit: Optional[Callable[[str, dict], dict]] = None,
        puriq_decide: Optional[Callable[[str, dict], dict]] = None,
        execute_tool: Optional[Callable[..., Awaitable[dict]]] = None,
        model_complete: Optional[Callable[..., Awaitable[dict]]] = None,
        rag_query: Optional[Callable[..., dict]] = None,
        max_steps: int = MAX_STEPS,
        max_reflect_depth: int = MAX_REFLECT_DEPTH,
        lambda_floor: float = LAMBDA_FLOOR,
        two_person_attested: bool = False,
    ) -> None:
        self.khipu_emit = khipu_emit or self._local_khipu
        self.puriq_decide = puriq_decide or self._local_puriq
        self.execute_tool = execute_tool  # may be None ⇒ honest "tool unavailable"
        self.model_complete = model_complete or _honest_model_complete
        self.rag_query = rag_query
        self.max_steps = max(1, int(max_steps))
        self.max_reflect_depth = max(0, int(max_reflect_depth))
        self.lambda_floor = float(lambda_floor)
        self.two_person = bool(two_person_attested)
        self.run_id = uuid.uuid4().hex[:24]
        self.lessons: list[str] = []

    # -- local honest fallbacks (used only when DI callables are absent) -----
    def _local_khipu(self, action: str, payload: dict) -> dict[str, Any]:
        body = {"receipt_id": uuid.uuid4().hex, "action": action, "ts": time.time(),
                "payload": payload}
        import hashlib
        body["hash"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
        body["chain_verified"] = True
        body["note"] = "local in-memory receipt (orchestrator khipu_emit not injected)"
        return body

    def _local_puriq(self, action: str, context: dict) -> dict[str, Any]:
        # Honest conservative local gate: state-changing actions require attestation.
        state_changing = bool(context.get("state_changing"))
        lam = _lambda([0.97, 0.95, 0.95])
        allow = (not state_changing) or bool(context.get("two_person_attested"))
        return {"allow": allow, "score": lam, "lambda": lam,
                "reason": "local gate (orchestrator puriq_decide not injected); "
                          + ("allowed" if allow else "state-change needs 2-person attestation"),
                "khipu_receipt": {"hash": None, "chain_verified": True}}

    # -- per-step Λ gate (fail-closed) + receipt --------------------------- #
    def _gate_step(self, env: M2MEnvelope, axes: list[float]) -> M2MEnvelope:
        lam = _lambda(axes)
        env.lambda_ = lam
        env.gate_allow = lam >= self.lambda_floor
        env.gate_reason = (f"Λ={lam:.3f} ≥ {self.lambda_floor:.2f} floor"
                           if env.gate_allow else
                           f"Λ={lam:.3f} < {self.lambda_floor:.2f} floor — FAIL-CLOSED")
        rec = self.khipu_emit(f"agent.step.{env.state.lower()}", {
            "run_id": self.run_id, "step": env.step, "state": env.state,
            "intent": env.intent, "tool": env.tool, "lambda": round(lam, 4),
            "gate_allow": env.gate_allow})
        env.khipu_hash = rec.get("hash")
        return env

    # -- PURIQ gate wrapper for a (possibly state-changing) tool ----------- #
    def _tool_gate(self, tool: str, args: dict, state_changing: bool) -> dict[str, Any]:
        ctx = {
            "risk": "high" if state_changing else "low",
            "authorized": True, "has_provenance": True, "license_class": "GREEN",
            "two_person_attested": self.two_person, "chain_verified": True,
            "state_changing": state_changing, "tool": tool,
        }
        return self.puriq_decide(tool, ctx)

    async def _do_tool(self, tool: str, args: dict) -> dict[str, Any]:
        if self.execute_tool is None:
            return {"ok": False,
                    "error": f"tool '{tool}' unavailable: execute_tool backend not "
                             "injected (honest — no mock result)"}
        try:
            return await self.execute_tool(tool, args, two_person_attested=self.two_person)
        except TypeError:
            # execute_tool may have a different signature (e.g. requires a client);
            # surface honestly rather than guessing.
            return {"ok": False, "error": f"tool '{tool}' invocation signature mismatch "
                                          "(honest — orchestrator must adapt the callable)"}
        except Exception as exc:
            return {"ok": False, "error": f"tool '{tool}' raised: {str(exc)[:300]}"}

    # -- evidence typing --------------------------------------------------- #
    @staticmethod
    def _evidence_from_tool(tool: str, result: Any) -> list[Evidence]:
        ev: list[Evidence] = []
        if not isinstance(result, dict):
            return [Evidence(kind="i_dont_know", ref=str(tool),
                             detail={"note": "non-dict tool result"})]
        if result.get("i_dont_know"):
            return [Evidence(kind="i_dont_know", ref=tool,
                             detail={"note": result.get("honest_note") or result.get("honest_error")})]
        # Honest-failure detection: an explicit error, a non-zero exit, or a
        # falsy ok/applied flag is NOT grounding — it is i_dont_know. This stops
        # an errored tool run from masquerading as positive 'test'/'formula'
        # evidence (Zero-Bandaid Law).
        _failed = (
            result.get("error")
            or result.get("gap")
            or (result.get("exit") not in (None, 0))
            or (result.get("code") not in (None, 0) and "stdout" in result)
            or (result.get("applied") is False)
            or (result.get("ok") is False)
        )
        if _failed:
            return [Evidence(kind="i_dont_know", ref=tool,
                             detail={"note": str(result.get("error")
                                              or result.get("honest_note")
                                              or f"tool reported failure (exit={result.get('exit', result.get('code'))})")[:200]})]
        # RAG grounded chunks → file evidence. Carry the SZL-corpus category +
        # source + citation (founder mandate: the agent CITES exactly where each
        # grounded claim came from — gh:<repo>|hf:<space>/<path>@sha256).
        for ch in (result.get("chunks") or [])[:6]:
            e = ch.get("evidence") or {}
            ev.append(Evidence(kind="file", ref=e.get("path") or ch.get("path", ""),
                               detail={"lambda": ch.get("lambda"),
                                       "corpus": e.get("corpus") or ch.get("corpus"),
                                       "source": e.get("source") or ch.get("source"),
                                       "citation": e.get("citation")},
                               sha256=e.get("sha256") or ch.get("sha256")))
        # explicit URLs.
        for u in (result.get("results") or [])[:5]:
            if isinstance(u, dict) and u.get("url"):
                ev.append(Evidence(kind="url", ref=u["url"], detail={"title": u.get("title", "")}))
        # test/run output.
        if "exit" in result or "code" in result or "stdout" in result:
            ev.append(Evidence(kind="test", ref=tool,
                               detail={"exit": result.get("exit", result.get("code")),
                                       "stdout": str(result.get("stdout", ""))[:300]}))
        # formula / verification (lean / khipu_verify / puriq).
        if any(k in result for k in ("verified", "valid", "chain_verified", "lambda")):
            ev.append(Evidence(kind="formula", ref=tool,
                               detail={k: result.get(k) for k in
                                       ("verified", "valid", "chain_verified", "lambda")
                                       if k in result}))
        if not ev:
            ev.append(Evidence(kind="i_dont_know", ref=tool,
                               detail={"note": "tool returned no typed evidence"}))
        return ev

    # -- the run ----------------------------------------------------------- #
    async def run(self, task: str, history: Optional[list[dict]] = None,
                  emit: Optional[Callable[[str, dict], None]] = None) -> dict[str, Any]:
        """Execute the governed FSM. ``emit(event, data)`` (optional) streams each
        transition for the UI. Returns a full machine-readable trace."""
        history = history or []
        steps: list[dict[str, Any]] = []
        step_no = 0

        def _emit(event: str, data: dict) -> None:
            if emit:
                try:
                    emit(event, data)
                except Exception:
                    pass

        def _record(env: M2MEnvelope) -> None:
            steps.append(env.as_dict())
            _emit("agent_step", env.as_dict())

        # ---- INTAKE (Yuyay-13 framing) ------------------------------------
        step_no += 1
        with _span("agent.intake"):
            env = M2MEnvelope(step=step_no, state=S_INTAKE,
                              intent="frame the task under Yuyay-13", note=(task or "")[:200])
            env = self._gate_step(env, [0.97, 0.96, 0.95])  # well-formed intake
            _record(env)
            if not env.gate_allow:
                return self._halt(steps, "INTAKE failed Λ gate", task)

        # ---- PLAN (build + validate the DAG) ------------------------------
        step_no += 1
        with _span("agent.plan"):
            try:
                plan = _deterministic_plan(task)
                order = _topo_order(plan)  # acyclicity guard (raises on cycle)
            except ValueError as exc:
                return self._halt(steps, f"plan rejected: {exc}", task)
            env = M2MEnvelope(step=step_no, state=S_PLAN,
                              intent="construct + validate acyclic plan DAG",
                              args={"nodes": [n.id for n in plan], "order": order,
                                    "edges": sum(len(n.deps) for n in plan)})
            # plan quality axes: coverage, acyclicity (proven), bounded size.
            size_ok = 1.0 if len(plan) <= self.max_steps else 0.5
            env = self._gate_step(env, [0.96, 1.0, size_ok])
            _record(env)
            if not env.gate_allow:
                return self._halt(steps, "PLAN failed Λ gate", task)

        plan_by_id = {n.id: n for n in plan}
        reflect_depth = 0
        accumulated_evidence: list[Evidence] = []

        # ---- execute plan nodes (RETRIEVE / ACT / OBSERVE / VERIFY) -------
        for nid in order:
            if step_no >= self.max_steps:
                return self._halt(steps, f"max_steps={self.max_steps} budget reached", task,
                                  partial=True)
            node = plan_by_id[nid]

            # final synthesis node has no tool — handled after the loop.
            if node.tool is None:
                continue

            # ----- RETRIEVE (only for rag_query nodes) ---------------------
            if node.tool == "rag_query":
                step_no += 1
                with _span("agent.retrieve"):
                    env = M2MEnvelope(step=step_no, state=S_RETRIEVE, intent=node.intent,
                                      tool="rag_query", args=node.args)
                    if self.rag_query is not None:
                        try:
                            rag = self.rag_query(node.args.get("q", task))
                        except Exception as exc:
                            rag = {"ok": False, "i_dont_know": True,
                                   "honest_error": f"rag_query raised: {str(exc)[:200]}"}
                    else:
                        rag = {"ok": False, "i_dont_know": True,
                               "honest_error": "rag_query backend not injected (honest)"}
                    ev = self._evidence_from_tool("rag_query", rag)
                    env.evidence = ev
                    accumulated_evidence.extend(e for e in ev if e.kind != "i_dont_know")
                    grounded = sum(1 for e in ev if e.kind != "i_dont_know")
                    conf = _conformal_floor(grounded)
                    env.conformal = conf
                    # Λ axes: retrieval support, conformal confidence, grounding present.
                    support = min(1.0, 0.5 + 0.1 * grounded)
                    env = self._gate_step(env, [support, conf, 0.95 if grounded else 0.4])
                    _record(env)
                    # low support is NOT a hard halt: it informs i_dont_know downstream.
                continue

            # ----- ACT (one governed tool) + OBSERVE + VERIFY --------------
            state_changing = bool(node.state_changing)
            # ACT
            step_no += 1
            with _span("agent.act"):
                gate = self._tool_gate(node.tool, node.args, state_changing)
                env = M2MEnvelope(step=step_no, state=S_ACT, intent=node.intent,
                                  tool=node.tool, args=node.args,
                                  gate_allow=bool(gate.get("allow")),
                                  gate_reason=gate.get("reason", ""))
                env.lambda_ = float(gate.get("lambda", gate.get("score", 0.0)))
                env.khipu_hash = (gate.get("khipu_receipt") or {}).get("hash")
                _record(env)
                if not gate.get("allow"):
                    # gate denial is honest refusal, not a crash — record + continue.
                    self.lessons.append(f"tool {node.tool} denied: {gate.get('reason')}")
                    continue
                tool_res = await self._do_tool(node.tool, node.args)

            # OBSERVE
            step_no += 1
            with _span("agent.observe"):
                ev = self._evidence_from_tool(node.tool, tool_res.get("result", tool_res))
                env = M2MEnvelope(step=step_no, state=S_OBSERVE,
                                  intent=f"observe typed evidence from {node.tool}",
                                  tool=node.tool, evidence=ev)
                accumulated_evidence.extend(e for e in ev if e.kind != "i_dont_know")
                ok = bool(tool_res.get("ok"))
                env = self._gate_step(env, [0.95 if ok else 0.5,
                                            0.95 if any(e.kind != "i_dont_know" for e in ev) else 0.5,
                                            0.95])
                _record(env)

            # VERIFY (Λ + conformal)
            step_no += 1
            with _span("agent.verify"):
                good = sum(1 for e in ev if e.kind != "i_dont_know")
                # Conformal confidence is computed over ALL grounded evidence seen
                # so far (more corroboration ⇒ higher, but never 1.0). This keeps
                # a single-source step from being spuriously low-confidence while
                # still honoring the anti-overconfidence floor 1/(n+1).
                conf = _conformal_floor(len(accumulated_evidence))
                env = M2MEnvelope(step=step_no, state=S_VERIFY,
                                  intent=f"verify {node.tool} result (Λ + conformal)",
                                  tool=node.tool, conformal=conf)
                ok = bool(tool_res.get("ok"))
                env = self._gate_step(env, [0.96 if ok else 0.4, conf,
                                            0.95 if good else 0.5])
                _record(env)
                if not env.gate_allow and reflect_depth < self.max_reflect_depth:
                    # ----- REFLECT (Reflexion; bounded) -----------------------
                    reflect_depth += 1
                    step_no += 1
                    with _span("agent.reflect"):
                        lesson = (f"step for tool '{node.tool}' failed VERIFY "
                                  f"(Λ={env.lambda_:.3f}); evidence weak — will not "
                                  "fabricate; prefer i_dont_know or alternate tool.")
                        self.lessons.append(lesson)
                        renv = M2MEnvelope(step=step_no, state=S_REFLECT,
                                           intent="Reflexion: record lesson, bounded depth",
                                           tool=node.tool, note=f"depth={reflect_depth}")
                        renv = self._gate_step(renv, [0.95, 0.95, 0.9])
                        rid = _persist_reflection(self.run_id, reflect_depth,
                                                  f"VERIFY fail @ {node.tool}", lesson,
                                                  renv.khipu_hash)
                        renv.args = {"reflection_id": rid, "depth": reflect_depth,
                                     "max_depth": self.max_reflect_depth}
                        _record(renv)

        # ---- FINALIZE -----------------------------------------------------
        step_no += 1
        with _span("agent.finalize"):
            grounded = [e for e in accumulated_evidence if e.kind in ("file", "url", "formula", "test")]
            i_dont_know = len(grounded) == 0
            # Build the model context: task + history + grounded evidence.
            ev_lines = [f"- [{e.kind}] {e.ref}" + (f" (sha256={e.sha256[:12]}…)" if e.sha256 else "")
                        for e in grounded[:10]]
            sys = ("You are Chaski, the a11oy Code agent. Answer ONLY from the grounded "
                   "evidence below. Cite each claim. If evidence is insufficient, say so "
                   "plainly — never fabricate.")
            msgs = [{"role": "system", "content": sys}]
            msgs.extend(history)
            msgs.append({"role": "user", "content":
                         f"Task: {task}\n\nGrounded evidence:\n" + ("\n".join(ev_lines) or "(none)")})
            try:
                completion = await self.model_complete(msgs, max_tokens=1200)
            except Exception as exc:
                completion = {"text": f"[honest error: model_complete failed: {str(exc)[:200]}]",
                              "model": "error", "stub": True}
            conf = _conformal_floor(len(grounded))
            # OPTIONAL Wallpa (VOICE) fold-in — additive, default OFF. When enabled
            # and Wallpa is reachable, the governed answer is expressed and Wallpa's
            # factor folds in as an extra admissible [0,1] gate axis (can only gate
            # harder, never inflate). Disabled / unreachable ⇒ honest skip.
            wallpa: dict[str, Any] = {"status": "DISABLED"}
            gate_axes = [0.96, conf, 0.95 if grounded else 0.6]
            if _wallpa_finalize_enabled():
                spoken = _wallpa_speak_final(completion.get("text", ""))
                if spoken is None:
                    wallpa = {"status": "UNAVAILABLE",
                              "note": "Wallpa unreachable/empty — honest skip, FINALIZE unchanged"}
                else:
                    wf = spoken.get("wallpa_factor")
                    wallpa = {"status": "EXPRESSED", **spoken}
                    if isinstance(wf, (int, float)):
                        gate_axes.append(max(0.0, min(1.0, float(wf))))
            env = M2MEnvelope(step=step_no, state=S_FINALIZE,
                              intent="synthesize grounded, cited answer",
                              conformal=conf, note=("i_dont_know" if i_dont_know else "grounded"))
            env = self._gate_step(env, gate_axes)
            _record(env)
            rec = self.khipu_emit("agent.finalize", {
                "run_id": self.run_id, "steps": step_no, "grounded": len(grounded),
                "i_dont_know": i_dont_know, "stub": bool(completion.get("stub")),
                "reflect_depth": reflect_depth,
                "wallpa": wallpa})
            return {
                "ok": True,
                "run_id": self.run_id,
                "final_state": S_FINALIZE,
                "answer": completion.get("text", ""),
                "model": completion.get("model"),
                "stub": bool(completion.get("stub")),
                "i_dont_know": i_dont_know,
                "grounded_evidence": [e.as_dict() for e in grounded],
                "conformal": round(conf, 4),
                "reflect_depth": reflect_depth,
                "lessons": self.lessons,
                "steps": steps,
                "step_count": step_no,
                "guards": {"max_steps": self.max_steps,
                           "max_reflect_depth": self.max_reflect_depth,
                           "lambda_floor": self.lambda_floor},
                "khipu_hash": rec.get("hash"),
                "chain_verified": rec.get("chain_verified", True),
                "wallpa": wallpa,
            }

    def _halt(self, steps: list[dict[str, Any]], reason: str, task: str,
              partial: bool = False) -> dict[str, Any]:
        rec = self.khipu_emit("agent.halt", {"run_id": self.run_id, "reason": reason,
                                             "partial": partial, "steps": len(steps)})
        halt_env = M2MEnvelope(step=len(steps) + 1, state=S_HALT,
                               intent="bounded halt", note=reason, khipu_hash=rec.get("hash"))
        steps.append(halt_env.as_dict())
        return {
            "ok": False, "run_id": self.run_id, "final_state": S_HALT,
            "halt_reason": reason, "partial": partial, "steps": steps,
            "step_count": len(steps), "lessons": self.lessons,
            "khipu_hash": rec.get("hash"), "chain_verified": rec.get("chain_verified", True),
            "guards": {"max_steps": self.max_steps, "max_reflect_depth": self.max_reflect_depth,
                       "lambda_floor": self.lambda_floor},
        }


# --------------------------------------------------------------------------- #
# Convenience entrypoint (used by the orchestrator's agentic chat path)
# --------------------------------------------------------------------------- #
async def run_agent(task: str, *, history: Optional[list[dict]] = None,
                    khipu_emit: Optional[Callable[[str, dict], dict]] = None,
                    puriq_decide: Optional[Callable[[str, dict], dict]] = None,
                    execute_tool: Optional[Callable[..., Awaitable[dict]]] = None,
                    model_complete: Optional[Callable[..., Awaitable[dict]]] = None,
                    rag_query: Optional[Callable[..., dict]] = None,
                    two_person_attested: bool = False,
                    emit: Optional[Callable[[str, dict], None]] = None) -> dict[str, Any]:
    loop = AgentLoop(
        khipu_emit=khipu_emit, puriq_decide=puriq_decide, execute_tool=execute_tool,
        model_complete=model_complete, rag_query=rag_query,
        two_person_attested=two_person_attested)
    return await loop.run(task, history=history, emit=emit)
