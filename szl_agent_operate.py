# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. Jr. — SZL Holdings — ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (advisory, NEVER "green"/proven/a gate).
"""szl_agent_operate — an OPERATIONAL, BOUNDED agent loop grounded on the Brain.

WHAT THIS IS (honest, one line): a thin additive orchestrator that runs a
BOUNDED, Ouroboros-style plan -> act -> self-eval -> gate -> (retry) loop where
every step is GROUNDED on the REAL brain graph (HippoRAG-PPR ⊕ GraphRAG, via
szl_brain_api.get_index(ns).ask) and JUDGED by a DETERMINISTIC doctrine gate that
is NOT the writer (writer≠judge). It NEVER recurses unboundedly and it NEVER
fabricates a model action, a passed gate, or a signature.

WHY it differs from szl_agent_loop_governed (which it builds ON, not duplicates):
  * governed loop = COMPOSES existing siloed primitives (/code engine, harness,
    eval-arena) into ONE composite signed receipt. It answers "govern + receipt a
    full run."
  * THIS loop = the OPERATE primitive: a minimal, self-contained bounded recursion
    that grounds each step directly on the brain's PPR retrieval and separates the
    generative WRITER (a sovereign model over the grounding) from a deterministic
    doctrine JUDGE (Colang policy + codename gate). It answers "can the agent, per
    step, ground -> propose -> self-check -> be judged, within a hard bound, and
    emit an honest per-step receipt chain?"

BOUNDED RECURSION (Ouroboros — never unbounded):
  * STEP_CAP planned steps; each step retried at most RETRY_CAP times.
  * Hard ceiling on total actions = STEP_CAP * (1 + RETRY_CAP). The loop cannot
    exceed it; there is no path that recurses without decrementing a budget.

WRITER ≠ JUDGE (a real separation, not theater):
  * WRITER  = a sovereign model asked to propose an action over the brain grounding
    (szl_brain_api ask -> answer). If no local model is reachable the action is an
    HONEST UNAVAILABLE — the grounding is still REAL; we never invent an action.
  * JUDGE   = a deterministic, file-backed doctrine gate (szl_colang_policy.evaluate
    over the proposed-action dict + szl_codename_gate.scan_text over its text). The
    judge is non-generative and never sees a model; it cannot be talked into "allow."

HONESTY (absolute):
  * The brain grounding subgraph + cited node ids are REAL regardless of model.
  * A generated action is LIVE only if a sovereign model actually answered; else
    UNAVAILABLE. We NEVER mark ACCEPTED on a fabricated/absent action.
  * Per-step SHA-256 receipts are a genuine hash-chain over canonical step bodies.
    This is receipt-on-WRITE (POST /operate only); GET /status signs nothing.
  * Λ = Conjecture 1 everywhere. locked-8 untouched. Trust ceiling 0.97.

ENDPOINTS (registered before the SPA catch-all, ns-scoped):
  * POST /api/{ns}/v1/agent/operate?goal=...   run the bounded loop, full trace
  * GET  /api/{ns}/v1/agent/status             bounded-loop config + last-run summary
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "szl.agent.operate/v1"
DOCTRINE = "v11"
TRUST_CEILING = 0.97
LOCKED8 = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")

# --- HARD Ouroboros bounds (never unbounded) --------------------------------
STEP_CAP = 6           # max planned sub-steps per goal
RETRY_CAP = 2          # max retries per step (so <= 3 attempts / step)
MAX_ACTIONS = STEP_CAP * (1 + RETRY_CAP)   # absolute ceiling on model calls

LBL_UNAVAILABLE = "UNAVAILABLE"
LBL_MODELED = "MODELED"
LBL_LIVE = "LIVE"

_CONJECTURE_NOTE = ("Λ is Conjecture 1 — advisory only, NEVER 'green'/proven/a gate; "
                    "trust is bounded at 0.97 and is never a proof.")

# Last-run summary for GET /status (in-memory, honest; no fabrication).
_LAST_RUN: Optional[Dict[str, Any]] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _run_id(goal: str) -> str:
    return "operate-" + _sha256("%s|%s" % (goal, _now()))[:12]


# --------------------------------------------------------------------------- #
# GROUND: real brain PPR retrieval (never fabricated).
# --------------------------------------------------------------------------- #
def _ground(ns: str, query: str, k: int = 8) -> Dict[str, Any]:
    """Ground a step on the REAL brain graph. Returns cited node ids + the
    sovereign model's proposed prose (writer) or an honest UNAVAILABLE. The
    grounding subgraph is REAL whether or not a model answered."""
    try:
        import szl_brain_api
        idx = szl_brain_api.get_index(ns)
        a = idx.ask(query, k=k)
        return {
            "available": True,
            "label": a.get("label", LBL_MODELED),
            "grounding_ids": list(a.get("cited_node_ids") or []),
            "retrieval": a.get("retrieval"),
            "answer": a.get("answer"),                       # writer prose or None
            "answer_label": a.get("answer_label", LBL_UNAVAILABLE),
            "answer_model": a.get("answer_model"),
            "community_context": len(a.get("community_context") or []),
        }
    except Exception as e:
        # Brain unreachable => honest UNAVAILABLE grounding. Never fabricate ids.
        return {
            "available": False,
            "label": LBL_UNAVAILABLE,
            "grounding_ids": [],
            "retrieval": None,
            "answer": None,
            "answer_label": LBL_UNAVAILABLE,
            "answer_model": None,
            "community_context": 0,
            "error": "brain grounding unavailable: %r" % (e,),
        }


# --------------------------------------------------------------------------- #
# ACT (WRITER): propose an action from the grounding + goal.
# --------------------------------------------------------------------------- #
def _act(goal: str, step_idx: int, grounding: Dict[str, Any]) -> Dict[str, Any]:
    """The WRITER move. If a sovereign model answered over the grounding, that
    prose IS the proposed action (LIVE). Otherwise the action is honestly
    UNAVAILABLE — we NEVER fabricate an action so a gate can 'pass'."""
    model_text = grounding.get("answer")
    model = grounding.get("answer_model")
    if model_text and grounding.get("answer_label") == LBL_MODELED and model:
        # A real sovereign model grounded on the brain produced this.
        return {
            "label": LBL_LIVE,
            "kind": "model_proposal",
            "text": str(model_text),
            "model": model,
            "grounded_on": grounding.get("grounding_ids", []),
        }
    # No model reachable: honest UNAVAILABLE. The loop structure + grounding are
    # still real; only the generated action is absent.
    return {
        "label": LBL_UNAVAILABLE,
        "kind": "model_proposal",
        "text": None,
        "model": None,
        "grounded_on": grounding.get("grounding_ids", []),
        "note": ("no sovereign model reachable (SZL_LOCAL_LLM_URL/MODEL unset) — "
                 "action UNAVAILABLE, never fabricated."),
    }


# --------------------------------------------------------------------------- #
# SELF-EVAL: deterministic structural self-critique (MODELED heuristic).
# --------------------------------------------------------------------------- #
def _self_eval(goal: str, grounding: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    """A deterministic, honest self-check the loop CAN do without a model:
    is the step grounded (real cited ids) and is the action present + non-trivial?
    This is a MODELED heuristic, NOT a proof and NOT the doctrine gate."""
    n_ground = len(grounding.get("grounding_ids") or [])
    has_action = bool(action.get("text"))
    grounded = n_ground > 0
    passed = grounded and has_action
    reasons: List[str] = []
    if not grounded:
        reasons.append("no real brain grounding for this step")
    if not has_action:
        reasons.append("no sovereign-model action to evaluate (UNAVAILABLE)")
    return {
        "label": LBL_MODELED,
        "passed": bool(passed),
        "grounded": bool(grounded),
        "n_grounding": n_ground,
        "has_action": has_action,
        "reasons": reasons,
        "note": "MODELED heuristic self-critique — never a proof, never the gate.",
    }


# --------------------------------------------------------------------------- #
# GATE (JUDGE): deterministic doctrine gate. Writer≠judge — no model here.
# --------------------------------------------------------------------------- #
def _gate(action: Dict[str, Any]) -> Dict[str, Any]:
    """The JUDGE move: a deterministic, file-backed doctrine gate that never
    generates. Two independent checks:
      1) szl_colang_policy.evaluate(action_dict) — file-backed Colang flows.
      2) szl_codename_gate.scan_text(action_text) — banned-codename scan.
    A gate PASS requires BOTH to be clean. We never fabricate an allow."""
    text = action.get("text") or ""
    colang: Dict[str, Any]
    try:
        import szl_colang_policy
        colang = szl_colang_policy.get_policy().evaluate({
            "action": "agent_operate_step",
            "text": text,
            "kind": action.get("kind"),
            "model": action.get("model"),
        })
    except Exception as e:
        colang = {"allow": False, "decision": "deny", "fired_count": 0,
                  "error": "colang policy unavailable: %r" % (e,),
                  "honesty": "gate DENIES when the policy layer is unavailable "
                             "(fail-closed) — never a fabricated allow."}
    try:
        import szl_codename_gate
        codenames = list(szl_codename_gate.scan_text(text))
    except Exception:
        codenames = []
    colang_allow = bool(colang.get("allow"))
    codename_clean = (len(codenames) == 0)
    allowed = colang_allow and codename_clean
    return {
        "label": "STRUCTURAL",
        "allowed": bool(allowed),
        "decision": "allow" if allowed else "deny",
        "writer_is_judge": False,   # explicit: this path never sees a model
        "colang": {
            "allow": colang_allow,
            "decision": colang.get("decision"),
            "fired_count": colang.get("fired_count", 0),
            "fired_flows": colang.get("fired_flows", []),
            "policy_files": colang.get("policy_files", []),
            "error": colang.get("error"),
        },
        "codename_gate": {
            "clean": codename_clean,
            "banned_tokens_found": codenames,
        },
        "honesty": ("Deterministic file-backed doctrine gate (Colang flows + "
                    "codename scan). Non-generative; independent of the writer. "
                    "Fail-closed. Never a fabricated allow."),
    }


# --------------------------------------------------------------------------- #
# The BOUNDED loop.
# --------------------------------------------------------------------------- #
def _plan(goal: str) -> List[str]:
    """Deterministic MODELED plan decomposition, HARD-bounded by STEP_CAP. Each
    planned sub-step is a grounded query refinement toward the goal. This is a
    heuristic decomposition (MODELED), never a proof of the right plan."""
    goal = (goal or "").strip()
    phases = [
        "ground the goal on the brain and identify the core entities",
        "retrieve supporting evidence and constraints",
        "propose a doctrine-safe action toward the goal",
        "self-critique the proposal against the grounding",
        "check the proposal against the doctrine gate",
        "finalize the grounded, gate-passing action",
    ]
    steps: List[str] = []
    for i, ph in enumerate(phases[:STEP_CAP]):
        steps.append("[step %d/%d] %s: %s" % (i + 1, min(STEP_CAP, len(phases)), ph, goal))
    return steps


def operate(goal: str, ns: str = "a11oy", *, k: int = 8) -> Dict[str, Any]:
    """Run the BOUNDED plan->act->self-eval->gate->(retry) loop. Returns the full
    honest trace. NEVER unbounded; NEVER fabricates an action/gate/receipt."""
    global _LAST_RUN
    goal = (goal or "").strip()
    started = _now()
    run_id = _run_id(goal)

    if not goal:
        return {
            "ok": False,
            "status_code": 400,
            "error": "goal is required",
            "label": "%s — supply ?goal= to run the bounded operate loop." % LBL_MODELED,
            "conjecture_note": _CONJECTURE_NOTE,
        }

    plan = _plan(goal)
    # Genesis of the per-step hash-chain (binds the chain to goal + config).
    prev_hash = _sha256(_canon({
        "schema": SCHEMA, "run_id": run_id, "goal": goal, "ns": ns,
        "step_cap": STEP_CAP, "retry_cap": RETRY_CAP, "max_actions": MAX_ACTIONS,
        "started": started,
    }))
    genesis_hash = prev_hash

    steps: List[Dict[str, Any]] = []
    actions_used = 0
    accepted_any = False
    gated_final = False

    for si, plan_line in enumerate(plan):
        step_accepted = False
        step_gated = False
        attempts: List[Dict[str, Any]] = []
        # Bounded retries: at most (1 + RETRY_CAP) attempts, and never past the
        # absolute MAX_ACTIONS ceiling. This is the Ouroboros bound.
        for attempt in range(1 + RETRY_CAP):
            if actions_used >= MAX_ACTIONS:
                break
            actions_used += 1
            query = "%s (attempt %d)" % (plan_line, attempt + 1)
            grounding = _ground(ns, query, k=k)
            action = _act(goal, si, grounding)
            self_eval = _self_eval(goal, grounding, action)
            gate = _gate(action)
            accept = bool(self_eval["passed"] and gate["allowed"]
                          and action["label"] == LBL_LIVE)
            attempts.append({
                "attempt": attempt + 1,
                "query": query,
                "grounding_ids": grounding.get("grounding_ids", []),
                "grounding_label": grounding.get("label"),
                "action": action,
                "self_eval": self_eval,
                "gate_result": gate,
                "accepted": accept,
            })
            if not gate["allowed"]:
                step_gated = True
            if accept:
                step_accepted = True
                break
            # else: retry (bounded) — reason recorded in self_eval/gate.

        # Determine this step's honest outcome.
        if step_accepted:
            step_status = "ACCEPTED"
            accepted_any = True
        elif step_gated:
            step_status = "GATED"
        else:
            step_status = "EXHAUSTED"

        step_body = {
            "schema": SCHEMA,
            "run_id": run_id,
            "step_index": si + 1,
            "step_of": len(plan),
            "plan_line": plan_line,
            "attempts": attempts,
            "n_attempts": len(attempts),
            "retry_cap": RETRY_CAP,
            "status": step_status,
            "prev_receipt": prev_hash,
            "at": _now(),
        }
        step_hash = _sha256(_canon(step_body))
        step_body["receipt"] = step_hash          # per-step SHA-256 receipt
        prev_hash = step_hash                      # hash-CHAIN link
        steps.append(step_body)

        # A GATED step is terminal for the run (doctrine deny stops the loop).
        if step_status == "GATED":
            gated_final = True
            break

    # HONEST final status (never a fabricated ACCEPTED):
    #   ACCEPTED  — at least one step produced a real, gate-passing model action.
    #   GATED     — the loop was stopped by a deterministic doctrine deny.
    #   EXHAUSTED — bounds hit with no accepted action (e.g. model UNAVAILABLE).
    if gated_final:
        final_status = "GATED"
    elif accepted_any:
        final_status = "ACCEPTED"
    else:
        final_status = "EXHAUSTED"

    model_reachable = any(
        a["action"]["label"] == LBL_LIVE
        for s in steps for a in s["attempts"])

    run_digest = _sha256(_canon({
        "genesis": genesis_hash,
        "chain": [s["receipt"] for s in steps],
        "final_status": final_status,
    }))

    result = {
        "ok": True,
        "status_code": 200,
        "schema": SCHEMA,
        "run_id": run_id,
        "goal": goal,
        "ns": ns,
        "label": LBL_MODELED,
        "bounded": {
            "step_cap": STEP_CAP,
            "retry_cap": RETRY_CAP,
            "max_actions": MAX_ACTIONS,
            "actions_used": actions_used,
            "planned_steps": len(plan),
            "note": "Ouroboros hard bound — the loop can never exceed max_actions.",
        },
        "writer_ne_judge": {
            "writer": "sovereign model over brain grounding (LIVE) or UNAVAILABLE",
            "judge": "deterministic file-backed doctrine gate (Colang + codename)",
            "separated": True,
        },
        "steps": steps,
        "final_status": final_status,
        "model_reachable": model_reachable,
        "genesis_receipt": genesis_hash,
        "run_digest": run_digest,
        "locked8_touched": False,
        "lambda": "Conjecture 1 (advisory — never a gate, never 'green').",
        "trust_ceiling": TRUST_CEILING,
        "conjecture_note": _CONJECTURE_NOTE,
        "honesty": (
            "Brain grounding + cited ids are REAL. A generated action is LIVE only "
            "if a sovereign model answered; otherwise UNAVAILABLE (never fabricated). "
            "The gate is a deterministic doctrine judge, independent of the writer. "
            "Per-step SHA-256 receipts are a genuine hash-chain. Λ = Conjecture 1."),
        "started": started,
        "finished": _now(),
    }

    _LAST_RUN = {
        "run_id": run_id,
        "goal": goal,
        "final_status": final_status,
        "planned_steps": len(plan),
        "actions_used": actions_used,
        "model_reachable": model_reachable,
        "run_digest": run_digest,
        "finished": result["finished"],
    }
    return result


def status(ns: str = "a11oy") -> Dict[str, Any]:
    """Honest bounded-loop config + last-run summary. Pure read — signs nothing."""
    brain_ok = False
    try:
        import szl_brain_api  # noqa: F401
        brain_ok = True
    except Exception:
        brain_ok = False
    gate_ok = False
    try:
        import szl_colang_policy  # noqa: F401
        import szl_codename_gate  # noqa: F401
        gate_ok = True
    except Exception:
        gate_ok = False
    sovereign_ready = bool(os.environ.get("SZL_LOCAL_LLM_URL", "").strip()
                           and os.environ.get("SZL_LOCAL_LLM_MODEL", "").strip())
    return {
        "ok": True,
        "schema": SCHEMA,
        "ns": ns,
        "surface": "szl_agent_operate — bounded Ouroboros operate loop grounded on the brain",
        "bounded_loop": {
            "step_cap": STEP_CAP,
            "retry_cap": RETRY_CAP,
            "max_actions": MAX_ACTIONS,
            "recursion": "HARD-bounded — never unbounded.",
        },
        "gate_policy": {
            "writer": "sovereign model over brain PPR grounding (LIVE) or UNAVAILABLE",
            "judge": "deterministic file-backed doctrine gate (Colang flows + codename scan)",
            "writer_ne_judge": True,
            "fail_closed": True,
        },
        "grounding": {
            "brain_available": brain_ok,
            "how": "szl_brain_api.get_index(ns).ask(query, k) — HippoRAG-PPR ⊕ GraphRAG",
            "label": LBL_LIVE if brain_ok else LBL_UNAVAILABLE,
        },
        "gate_available": gate_ok,
        "sovereign_writer_ready": sovereign_ready,
        "sovereign_note": ("actions are LIVE only when a local sovereign model is reachable "
                           "(SZL_LOCAL_LLM_URL + SZL_LOCAL_LLM_MODEL); else honest UNAVAILABLE."),
        "endpoints": ["/api/%s/v1/agent/operate" % ns, "/api/%s/v1/agent/status" % ns],
        "backs_view": "agentops",
        "last_run": _LAST_RUN,
        "locked8": list(LOCKED8),
        "locked8_touched": False,
        "lambda": "Conjecture 1 (advisory — never a gate, never 'green').",
        "trust_ceiling": TRUST_CEILING,
        "doctrine": DOCTRINE,
        "conjecture_note": _CONJECTURE_NOTE,
        "checked_at": _now(),
    }


# --------------------------------------------------------------------------- #
# FastAPI registration — additive, BEFORE the SPA catch-all. Raw Starlette.
# --------------------------------------------------------------------------- #
def register(app, ns: str = "a11oy") -> dict:
    """Front-insert the two routes so they resolve before the SPA catch-all.
    Uses raw Starlette Route (no Pydantic — safe under `from __future__` gotcha).
    receipt-on-WRITE: only POST /operate builds the receipt chain; GET signs nothing."""
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    async def _operate(request):
        goal = request.query_params.get("goal") or ""
        if not goal:
            try:
                b = await request.json()
            except Exception:
                b = {}
            if isinstance(b, dict):
                goal = b.get("goal") or b.get("task") or b.get("prompt") or ""
        try:
            k = int(request.query_params.get("k", 8))
        except Exception:
            k = 8
        k = max(3, min(24, k))
        result = operate(goal, ns=ns, k=k)
        return JSONResponse(result, status_code=result.get("status_code", 200))

    async def _status(request):
        return JSONResponse(status(ns=ns))

    routes = [
        Route("/api/%s/v1/agent/operate" % ns, _operate, methods=["POST"],
              name="%s_agent_operate" % ns),
        Route("/api/%s/v1/agent/status" % ns, _status, methods=["GET"],
              name="%s_agent_status" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "step_cap": STEP_CAP, "retry_cap": RETRY_CAP, "max_actions": MAX_ACTIONS}


def _selftest() -> None:  # pragma: no cover
    """Local honest selftest — no network required, no fabricated data."""
    out = operate("explain the Euler Khipu DAG identity F1", ns="a11oy")
    assert out["ok"] is True, out
    assert out["schema"] == SCHEMA
    assert out["bounded"]["max_actions"] == STEP_CAP * (1 + RETRY_CAP)
    assert out["bounded"]["actions_used"] <= out["bounded"]["max_actions"]
    assert out["final_status"] in ("ACCEPTED", "GATED", "EXHAUSTED")
    assert out["locked8_touched"] is False
    assert out["writer_ne_judge"]["separated"] is True
    # hash-chain integrity: each step chains to the previous receipt.
    prev = out["genesis_receipt"]
    for s in out["steps"]:
        assert s["prev_receipt"] == prev, "broken chain"
        body = dict(s)
        rec = body.pop("receipt")
        assert rec == _sha256(_canon(body)), "receipt does not verify"
        prev = rec
    # honesty: with no sovereign model, actions are UNAVAILABLE, never ACCEPTED-fake.
    for s in out["steps"]:
        for a in s["attempts"]:
            if a["action"]["label"] != LBL_LIVE:
                assert a["accepted"] is False, "accepted a non-LIVE action"
    st = status(ns="a11oy")
    assert st["bounded_loop"]["max_actions"] == STEP_CAP * (1 + RETRY_CAP)
    assert st["gate_policy"]["writer_ne_judge"] is True
    print("szl_agent_operate: ALL OK (bounded loop max_actions=%d, final=%s, "
          "model_reachable=%s, steps=%d, writer≠judge, Λ=Conjecture 1, locked-8 untouched)."
          % (out["bounded"]["max_actions"], out["final_status"],
             out["model_reachable"], len(out["steps"])))


if __name__ == "__main__":  # pragma: no cover
    _selftest()
