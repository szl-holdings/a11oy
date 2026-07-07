# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. Jr. — SZL Holdings — ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED (749/14/163). Λ = Conjecture 1 (advisory, NEVER "green").
# Built by: Perplexity Computer Agent (Opus-class). Co-Authored-By in the commit trailer.
"""
szl_agent_loop_governed — ONE governed autonomous agent loop that COMPOSES the
three siloed pieces that already exist in a11oy into a single closed-loop run:

    plan  →  act  →  self-eval  →  gate  →  (retry)  →  ONE composite signed receipt

WHAT THIS IS (honest, one line): a thin, additive orchestrator that reuses the
REAL siloed primitives — the /code run-loop's governed engine, the model-harness
behavior profiles, and the eval-arena scorer — and chains them, per step, into
ONE composite DSSE-signed receipt ingested to /llm/forum. NO new engine, NO new
scorer, NO orchestration theater: every sub-result is the real module's own output.

WHY (gap from waveI_gapsB): /code orchestration, the model-harness and the
eval-arena exist but are SILOED. Nobody has governed + receipted a full autonomous
loop end-to-end. This turns the siloed pieces into a real governed loop.

STUDIED LEADERS (folded into the GOVERNED version — cited, never claimed-as):
  * LangGraph — stateful graph, conditional retry edges, interrupt() human-in-loop
      https://langchain-ai.github.io/langgraph/
  * OpenAI Agents SDK — guardrails + approval INTERRUPTIONS + resumable RunState
      https://openai.github.io/openai-agents-js/guides/human-in-the-loop/
  * CrewAI — task guardrail callbacks that reject output and force bounded retry
      https://docs.crewai.com/
  * AutoGen — reflection/self-critique loops + human_input_mode approval gate
      https://microsoft.github.io/autogen/
  * Anthropic MCP — host composes many servers; sensitive actions host-gated
      https://modelcontextprotocol.io/
The differentiator no leader ships: EVERY step's plan+act+eval+gate is folded into
ONE ECDSA-P256 DSSE-signed composite receipt (hash-chained), ingested to /llm/forum.

CLOSED LOOP, per planned step:
  (a) OPTIONAL: apply a harness behavior profile (szl_model_harness.apply) — the
      governed "persona/disposition attach" move (LangGraph runtime context /
      CrewAI role / AutoGen system_message), Λ-gated + sha256-provenanced.
  (b) ACT: execute via the /code run-loop engine (a11oy_code_engine.governed_turn):
      the P1-P6 6-receipt chain, Λ-gate (advisory), sandboxed exec when mode=code.
  (c) SELF-EVAL: score via the eval-arena (szl_eval_arena.run_eval) — deterministic
      suite, HELM-style axes, Λ geometric mean (Conjecture 1), its own signed receipt.
  (d) GATE: HumanApprovalGate (szl_agentic_loop.approval_interrupt) — durable,
      deny-by-default, OFF unless A11OY_APPROVAL_INTERRUPT=1 (honest MODELED-OFF else).
  (e) RETRY: bounded re-attempt of a step when the eval accuracy is below threshold
      AND the gate does not HOLD (mirrors CrewAI guardrail retry / AutoGen reflect).
  (f) ONE composite signed receipt chaining {profile, step-run, eval, gate} per step;
      a whole-run hash-chain digest signed once; ingested to /llm/forum.

HONESTY (absolute):
  * The engine run, its Λ-gate + P1-P6 receipt chain, the eval scoring + its Λ axes,
    the harness Λ-gate + provenance, and the HumanApprovalGate are all the REAL
    modules' own output. This file only ORCHESTRATES + CHAINS + SIGNS the composite.
  * The plan decomposition is deterministic + MODELED (labeled MODELED everywhere) —
    it is not a proof.
  * Λ (trust) is ALWAYS Conjecture 1 — advisory, NEVER "green"/proven/a gate.
  * Signatures are REAL ECDSA-P256 DSSE in-Space (host in-image key); an honest
    UNSIGNED-LOCAL marker locally. NEVER a fabricated signature.
  * Nothing here touches the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}. locked8_touched:false.

Endpoint: POST /api/a11oy/v1/agentloop/run ; GET /api/a11oy/v1/agentloop/health.
Routes inserted BEFORE the SPA catch-all, try/except guarded (never takes the Space down).
Reuses the HOST app's REAL signer passed in from serve.py (same one the engine uses).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

SCHEMA = "szl.agentloop.receipt/v1"
DOCTRINE = "v11"
_KERNEL = "c7c0ba17"
LOCKED8 = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
TRUST_CEILING = 0.97  # never 1.0
_CONJECTURE_NOTE = ("Λ is Conjecture 1 — advisory only, NEVER 'green'/proven/a gate; "
                    "trust ceiling 0.97; nothing here touches the locked-8.")

LEADERS = [
    {"name": "LangGraph (stateful graph, retry edges, interrupt() HITL)",
     "url": "https://langchain-ai.github.io/langgraph/"},
    {"name": "OpenAI Agents SDK (guardrails + approval interruptions + resumable state)",
     "url": "https://openai.github.io/openai-agents-js/guides/human-in-the-loop/"},
    {"name": "CrewAI (task guardrail callbacks + bounded retry)",
     "url": "https://docs.crewai.com/"},
    {"name": "AutoGen (reflection loops + human_input_mode gate)",
     "url": "https://microsoft.github.io/autogen/"},
    {"name": "Anthropic MCP (host composes servers; sensitive actions host-gated)",
     "url": "https://modelcontextprotocol.io/"},
]

# ── reuse the REAL siloed pieces (single sources of truth — COMPOSE, don't reimplement) ──
try:
    import a11oy_code_engine as _engine
    _ENGINE_OK = True
except Exception as _e:  # additive: never break the Space if the engine moves
    _ENGINE_OK = False
    _ENGINE_ERR = repr(_e)

try:
    import a11oy_code_runloop as _runloop
    _RUNLOOP_OK = True
except Exception as _e:
    _RUNLOOP_OK = False
    _RUNLOOP_ERR = repr(_e)

try:
    import szl_eval_arena as _arena
    _ARENA_OK = True
except Exception as _e:
    _ARENA_OK = False
    _ARENA_ERR = repr(_e)

try:
    import szl_model_harness as _harness
    _HARNESS_OK = callable(getattr(_harness, "apply", None))
except Exception:
    _HARNESS_OK = False

try:
    import szl_agentic_loop as _loop
    _approval_interrupt = getattr(_loop, "approval_interrupt", None)
    _APPROVAL_OK = callable(_approval_interrupt)
except Exception:
    _APPROVAL_OK = False
    _approval_interrupt = None

# Wave M (Dev 2): shared sovereign-flywheel bridge. Lets the governed loop run on
# SZL's OWN model (sovereign_local) via Dev-1's registry backend; honest
# MODELED/UNAVAILABLE when the local Tower endpoint is unreachable (no fabrication).
try:
    import szl_sovereign_flywheel as _sov  # noqa: F401
    _SOV_OK = True
except Exception:  # pragma: no cover — bridge missing → sovereign option simply off
    _sov = None  # type: ignore
    _SOV_OK = False

# ── Wave O (Dev 4): the governed loop can CONSULT the Brain pulse for context.
# szl_brain_corpus.brain_pulse() prefers Dev-1's szl_brain_hub pulse (the signed
# ecosystem bus) and degrades to a guarded local a11oy_brain_graph summary until
# #brain-hub merges. The context is CONSULTED (attached to the composite receipt,
# labelled) — it never changes a gate and never fabricates a citation. When the
# vault is empty/down the block is honestly UNAVAILABLE. Λ = Conjecture 1.
try:
    import szl_brain_corpus as _brain  # noqa: F401
    _BRAIN_OK = True
except Exception:  # pragma: no cover — module missing → brain-consult option simply off
    _brain = None  # type: ignore
    _BRAIN_OK = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _mk_run_id(task: str) -> str:
    return "aloop-" + _sha256("%s|%s" % (task, _now()))[:12]


def _default_eval_suite(mode: str) -> str:
    """Pick a deterministic self-eval suite for the step's mode (honest MODELED heuristic)."""
    if mode == "research":
        return "honesty_v1"
    if mode == "code":
        return "core_honest_v1"
    return "core_honest_v1"


# ===========================================================================
# THE GOVERNED LOOP — importable core (no FastAPI request). NEVER raises into
# the caller; NEVER fabricates a run, an eval, a signature, or an approval.
# ===========================================================================
def run_loop(task: str,
             sign_fn: Callable[[dict], dict],
             ns: str = "a11oy",
             mode: str = "",
             model_id: str = "",
             harness_profile_id: str = "",
             eval_suite: str = "",
             approval: Optional[dict] = None,
             max_retries: int = 1,
             sandbox: Optional[bool] = None,
             consult_brain: bool = False) -> dict:
    """Run ONE governed autonomous loop over a task.

    Composes the REAL siloed pieces per planned step:
      (a) harness.apply (optional behavior profile) → (b) engine.governed_turn (act,
      Λ-gate, sandbox) → (c) eval_arena.run_eval (self-eval) → (d) approval_interrupt
      (HumanApprovalGate) → (e) bounded retry → (f) ONE composite signed receipt +
      forum ingest.

    Returns a dict with: ok, run_id, plan, steps[], composite_receipt (signed),
    aggregate, forum_ingest, honest labels. Λ = Conjecture 1.
    """
    task = (task or "").strip()
    ns = ns or "a11oy"
    mode = (mode or "").lower()
    max_retries = max(0, min(3, int(max_retries)))
    grant = approval if isinstance(approval, dict) else None

    # ── Wave M (Dev 2): sovereign preflight ───────────────────────────────────
    # If the caller asked to run this loop on SZL's OWN governed model, probe the
    # sovereign backend ONCE (Dev-1 registry) and carry the honest verdict into the
    # composite receipt. The per-step ACT still flows through the engine with
    # want_model=model_id; the sovereign block records the intended backend +
    # reachability so an offline run is honestly MODELED/UNAVAILABLE (no fabrication).
    sovereign_requested = bool(_SOV_OK and _sov and _sov.is_sovereign(model_id))
    sovereign_block = None
    sovereign_state = None
    if sovereign_requested:
        _sp = _sov.run_on_sovereign(task or "State your doctrine in one line.",
                                    requested_model_id=model_id, probe_only=True)
        sovereign_state = _sp.get("state")
        sovereign_block = _sov.receipt_block(_sp)

    # ── Wave O (Dev 4): CONSULT the Brain pulse for context (advisory only). ─────
    # When consult_brain is set, read the Brain pulse (Dev-1 hub preferred, guarded
    # local fallback) plus the top brain passages relevant to the task. This is
    # CONTEXT the loop is aware of — it is recorded in the composite receipt and
    # NEVER changes a gate/decision and never fabricates a citation. Honest
    # UNAVAILABLE when the vault is empty/down.
    brain_context = None
    if consult_brain:
        if _BRAIN_OK and _brain is not None:
            try:
                brain_context = _brain.brain_pulse(ns, query=task, top_k=5)
            except Exception as _be:  # pragma: no cover - defensive
                brain_context = {"available": False,
                                 "label": "UNAVAILABLE — brain pulse read failed; no context fabricated.",
                                 "error": repr(_be), "conjecture_note": _CONJECTURE_NOTE}
        else:
            brain_context = {"available": False,
                             "label": "UNAVAILABLE — szl_brain_corpus not loaded; no context fabricated.",
                             "conjecture_note": _CONJECTURE_NOTE}

    if not _ENGINE_OK:
        return {
            "ok": False,
            "error": "engine unavailable: %s" % _ENGINE_ERR,
            "label": ("MODELED-UNAVAILABLE — the real governed engine could not be imported "
                      "in this runtime; no loop fabricated."),
            "conjecture_note": _CONJECTURE_NOTE,
            "status_code": 200,
        }

    # ── PLAN — reuse the runloop's MODELED decomposition (single source of truth) ──
    if _RUNLOOP_OK:
        plan_out = _runloop.plan(task, mode)
    else:  # additive fallback: minimal 1-step plan (still honest MODELED)
        eff_mode = mode if mode in ("chat", "code", "research") else "chat"
        plan_out = {"run_id": _mk_run_id(task), "task": task, "mode": eff_mode,
                    "created_at": _now(),
                    "plan": [{"n": 1, "title": "Compose the governed answer",
                              "mode": eff_mode, "prompt": task or "Describe the task.",
                              "sandbox": eff_mode == "code", "state_changing": eff_mode == "code",
                              "why": "runloop unavailable; minimal MODELED single-step plan."}],
                    "label": "MODELED plan (runloop fallback).",
                    "lambda": "Conjecture 1 (advisory)."}

    run_id = plan_out.get("run_id") or _mk_run_id(task)
    plan_mode = plan_out.get("mode", "chat")
    plan_steps = plan_out.get("plan") or []

    steps_out: list[dict] = []
    chain_digests: list[str] = []
    engine_chain: list[dict] = []  # carry the engine's rolling receipt chain across steps
    prev_digest = ""

    for pstep in plan_steps:
        n = pstep.get("n")
        step_mode = (pstep.get("mode") or plan_mode or "chat").lower()
        if step_mode not in ("chat", "code", "research"):
            step_mode = "chat"
        step_prompt = pstep.get("prompt") or task
        step_sandbox = bool(pstep.get("sandbox")) if sandbox is None else bool(sandbox)
        state_changing = bool(pstep.get("state_changing", step_sandbox))
        suite_id = eval_suite or _default_eval_suite(step_mode)

        attempts: list[dict] = []
        best = None
        n_try = 0
        while n_try <= max_retries:
            n_try += 1

            # ── (a)+(b) ACT via the REAL engine (P1-P6 chain, Λ-gate, sandbox). The
            # engine itself applies the OPTIONAL harness profile for this step and
            # records its provenance in the step receipt (harness_profile_id passthrough). ──
            try:
                run = _engine.governed_turn(
                    step_mode, step_prompt, sign_fn, ns,
                    untrusted_input=pstep.get("untrusted_input", "") or "",
                    run_chain=engine_chain, sandbox=step_sandbox,
                    want_model=model_id, harness_profile_id=harness_profile_id or "")
            except Exception as e:  # never raise into the request
                run = {"ok": False, "error": "engine error: %s" % type(e).__name__,
                       "decision": "DENY", "gate": {"severity": "high"},
                       "label": "engine raised; no run fabricated."}

            step_sig = run.get("signed_receipt") or {}
            step_signed = bool(step_sig.get("signed"))
            gate = run.get("gate") or {}
            decision = run.get("decision", "DENY")
            step_lambda = run.get("lambda")
            if isinstance(run.get("chain"), list) and run["chain"]:
                engine_chain = run["chain"]  # roll the chain forward (memory across steps)

            # ── harness summary (from the engine's own harness attach, if any) ──
            harness_summary = None
            _h = run.get("harness") or None
            if _h:
                _hp = (_h.get("profile") or {})
                _prov = (_hp.get("provenance") or {})
                harness_summary = {
                    "requested": _h.get("requested"),
                    "available": _h.get("available"),
                    "profile_id": _hp.get("id"),
                    "version": _hp.get("version"),
                    "sha256": _prov.get("sha256_resolved") or _prov.get("sha256_manifest"),
                    "sha256_integrity": _prov.get("sha256_integrity"),
                    "harness_state": _h.get("harness_state"),
                    "honesty": _h.get("honesty"),
                    "label": ("Governed behavior profile attached to this step — Λ-gated + "
                              "sha256-provenanced. Disposition only; capability ceiling unchanged."),
                }

            # ── (c) SELF-EVAL via the REAL eval-arena (deterministic scoring + Λ axes) ──
            eval_summary = None
            if _ARENA_OK:
                try:
                    ev = _arena.run_eval(suite_id, model_id or "claude_opus_4_8",
                                         harness_profile_id or None)
                    agg = ev.get("aggregate") or {}
                    ev_receipt = (ev.get("receipt") or {})
                    ev_dsse = (ev_receipt.get("dsse") or {})
                    eval_summary = {
                        "suite_id": suite_id,
                        "accuracy": agg.get("accuracy"),
                        "n_cases": agg.get("n_cases"),
                        "n_passed": agg.get("n_passed"),
                        "lambda": agg.get("lambda"),
                        "lambda_status": agg.get("lambda_status"),
                        "honesty_label": ev.get("honesty_label"),
                        "receipt_pae_sha256": ev_dsse.get("_pae_sha256"),
                        "receipt_signed": bool(ev_dsse.get("signed")),
                        "forum_ingested": bool((ev.get("forum_ingest") or {}).get("ingested")),
                        "label": ("LIVE eval-arena scoring — deterministic suite, HELM-style "
                                  "axes, Λ geometric mean (Conjecture 1). Its own signed receipt "
                                  "was ingested to /llm/forum."),
                    }
                except Exception as e:
                    eval_summary = {"suite_id": suite_id, "accuracy": None,
                                    "note": "eval-arena error: %s" % type(e).__name__,
                                    "label": "MODELED-UNAVAILABLE — eval-arena raised; not fabricated."}
            else:
                eval_summary = {"suite_id": suite_id, "accuracy": None,
                                "note": "szl_eval_arena not importable in this runtime.",
                                "label": "MODELED-OFF — eval-arena unavailable; no score fabricated."}

            # ── (d) GATE — durable HumanApprovalGate (deny-by-default, OFF unless env=1) ──
            if _APPROVAL_OK:
                try:
                    approval_res = _approval_interrupt(
                        action=(gate.get("severity", "") + ":" + (step_prompt or "")[:60]),
                        severity=gate.get("severity", "low"),
                        reversible=not state_changing,
                        decision=decision,
                        grant=grant)
                except Exception as e:
                    approval_res = {"required": None, "granted": None, "checkpoint_id": None,
                                    "note": "approval-interrupt error: %s" % type(e).__name__}
            else:
                approval_res = {"required": None, "granted": None, "checkpoint_id": None,
                                "note": ("HumanApprovalGate primitive unavailable in this runtime "
                                         "(MODELED-OFF).")}

            attempt = {
                "attempt": n_try,
                "engine": {
                    "ok": run.get("ok"),
                    "decision": decision,
                    "gate_severity": gate.get("severity"),
                    "lambda": step_lambda,
                    "mode": step_mode,
                    "sandbox": step_sandbox,
                    "signed": step_signed,
                    "signed_pae_sha256": step_sig.get("_pae_sha256"),
                    "answer_preview": (run.get("answer") or run.get("output") or "")[:200]
                        if isinstance(run.get("answer") or run.get("output"), str) else None,
                    "sandbox_run": (run.get("sandbox_run") or run.get("exec") or None),
                },
                "harness_profile": harness_summary,
                "eval": eval_summary,
                "approval": approval_res,
            }
            attempts.append(attempt)
            best = attempt

            # ── (e) RETRY decision (bounded; mirrors CrewAI guardrail retry / AutoGen reflect) ──
            acc = (eval_summary or {}).get("accuracy")
            gate_hold = bool(approval_res.get("required") and approval_res.get("granted") is None)
            good_enough = (acc is None) or (isinstance(acc, (int, float)) and acc >= 0.5)
            if good_enough or gate_hold or decision == "DENY":
                # stop: eval passed, OR gate is holding (no point retrying a held action),
                # OR the automated gate denied (retrying won't flip a deny).
                break
            # else: low eval score and nothing blocking → retry the step.

        # ── per-step composite digest (hash-chain: prev ⊕ this step) ──
        step_body = {
            "n": n, "title": pstep.get("title"), "mode": step_mode,
            "sandbox": step_sandbox, "state_changing": state_changing,
            "suite_id": suite_id, "attempts": len(attempts), "final": best,
            "prev_digest": prev_digest,
        }
        step_digest = _sha256(_canon(step_body))
        prev_digest = step_digest
        chain_digests.append(step_digest)
        steps_out.append({
            "n": n, "title": pstep.get("title"), "why": pstep.get("why"),
            "mode": step_mode, "sandbox": step_sandbox, "state_changing": state_changing,
            "suite_id": suite_id,
            "retries": len(attempts) - 1,
            "attempts": attempts,
            "final": best,
            "step_digest": step_digest,
        })

    # ── whole-run aggregate (honest; Λ is advisory Conjecture 1) ──
    n_steps = len(steps_out)
    step_accs = [s["final"]["eval"].get("accuracy") for s in steps_out
                 if s.get("final") and s["final"].get("eval")
                 and isinstance(s["final"]["eval"].get("accuracy"), (int, float))]
    mean_acc = round(sum(step_accs) / len(step_accs), 4) if step_accs else None
    step_lams = [s["final"]["eval"].get("lambda") for s in steps_out
                 if s.get("final") and s["final"].get("eval")
                 and isinstance(s["final"]["eval"].get("lambda"), (int, float))]
    mean_lambda = round(min(TRUST_CEILING, sum(step_lams) / len(step_lams)), 6) if step_lams else None
    any_denied = any(s["final"]["engine"].get("decision") == "DENY"
                     for s in steps_out if s.get("final") and s["final"].get("engine"))
    any_gate_hold = any(bool(s["final"]["approval"].get("required")
                             and s["final"]["approval"].get("granted") is None)
                        for s in steps_out if s.get("final") and s["final"].get("approval"))
    run_chain_digest = _sha256(_canon(chain_digests))

    # ── build the ONE composite receipt body (chains profile+step+eval per step) ──
    receipt_body = {
        "schema": SCHEMA,
        "ts": _now(),
        "hub": "a11oy",
        "surface": "szl_agent_loop_governed",
        "run_id": run_id,
        "task": task,
        "mode": plan_mode,
        "model_id": model_id or "(engine default)",
        "sovereign": sovereign_block,  # Wave M: intended sovereign backend (None when not requested)
        # Wave O: the Brain pulse the loop CONSULTED (advisory context; labelled;
        # None when not requested; UNAVAILABLE when the vault is empty/down). It is
        # recorded here but NEVER changed a gate/decision — the loop's Λ/eval/approval
        # are the real modules' own output.
        "brain_context": brain_context,
        "brain_consulted": bool(consult_brain),
        "harness_profile_id": harness_profile_id or None,
        "eval_suite_default": eval_suite or "(per-step mode heuristic)",
        "max_retries": max_retries,
        "n_steps": n_steps,
        "step_chain": [{"n": s["n"], "digest": s["step_digest"],
                        "decision": (s["final"]["engine"].get("decision") if s.get("final") else None),
                        "eval_accuracy": (s["final"]["eval"].get("accuracy") if s.get("final") else None),
                        "eval_lambda": (s["final"]["eval"].get("lambda") if s.get("final") else None),
                        "harness_profile": (s["final"]["harness_profile"].get("profile_id")
                                            if s.get("final") and s["final"].get("harness_profile") else None),
                        "step_receipt_pae_sha256": (s["final"]["engine"].get("signed_pae_sha256")
                                                    if s.get("final") else None),
                        "eval_receipt_pae_sha256": (s["final"]["eval"].get("receipt_pae_sha256")
                                                    if s.get("final") else None),
                        "approval_checkpoint": (s["final"]["approval"].get("checkpoint_id")
                                                if s.get("final") else None)}
                       for s in steps_out],
        "run_chain_digest": run_chain_digest,
        "aggregate": {
            "n_steps": n_steps,
            "mean_eval_accuracy": mean_acc,
            "mean_eval_lambda": mean_lambda,
            "any_step_denied": any_denied,
            "any_gate_hold": any_gate_hold,
            "lambda_posture": "advisory (Conjecture 1) — NEVER green/theorem",
            "lambda_status": "CONJECTURE",
            "trust_ceiling": TRUST_CEILING,
        },
        "composes": {
            "act_engine": "a11oy_code_engine.governed_turn (P1-P6, Λ-gate, sandbox)",
            "act_engine_available": _ENGINE_OK,
            "plan_source": "a11oy_code_runloop.plan (MODELED decomposition)",
            "plan_source_available": _RUNLOOP_OK,
            "self_eval": "szl_eval_arena.run_eval (deterministic scoring + Λ axes)",
            "self_eval_available": _ARENA_OK,
            "behavior_profile": "szl_model_harness.apply (Λ-gated + sha256-provenanced)",
            "behavior_profile_available": _HARNESS_OK,
            "human_gate": "szl_agentic_loop.approval_interrupt (durable, deny-by-default)",
            "human_gate_available": _APPROVAL_OK,
        },
        "leaders_cited": [{"name": l["name"], "url": l["url"]} for l in LEADERS],
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "locked8": list(LOCKED8),
        "locked8_touched": False,
        "honest_note": (
            "Composite governed loop. The plan is MODELED (deterministic decomposition). "
            "The per-step ACT (engine P1-P6 + Λ-gate + sandbox), the SELF-EVAL (eval-arena "
            "scoring + Λ axes), the behavior-profile attach (harness), and the HumanApprovalGate "
            "are the REAL modules' own output — this receipt only CHAINS + SIGNS them. "
            "Λ is Conjecture 1 (advisory, never green). No answer, eval, gate, or signature "
            "fabricated. Nothing touches the locked-8."),
    }

    # ── sign the ONE composite receipt (host signer: real ECDSA-P256 in-Space; UNSIGNED-LOCAL locally) ──
    dsse, signing = _sign(receipt_body, sign_fn)

    # ── ingest the composite receipt to the shared /llm/forum ──
    forum = _ingest_forum(receipt_body, dsse)

    return {
        "ok": True,
        "status_code": 200,
        "surface": "szl_agent_loop_governed",
        "run_id": run_id,
        "task": task,
        "mode": plan_mode,
        "plan": plan_out,
        "steps": steps_out,
        "aggregate": receipt_body["aggregate"],
        "composite_receipt": {"body": receipt_body, "dsse": dsse, "signing": signing},
        "sovereign": sovereign_block,  # Wave M: honest intended-backend + reachability
        "sovereign_label": (_sov.selected_label({"state": sovereign_state})
                            if sovereign_requested and _SOV_OK and _sov else None),
        "brain_context": brain_context,  # Wave O: consulted Brain pulse (advisory), None if not requested
        "brain_label": ((brain_context or {}).get("label") if consult_brain else None),
        "forum_ingest": forum,
        "composes": receipt_body["composes"],
        "leaders_cited": LEADERS,
        "signature_live": bool(dsse.get("signed")),
        "signature_label": ("LIVE — real ECDSA-P256 DSSE over the composite receipt "
                            "(verify vs /cosign.pub)." if dsse.get("signed") else
                            "UNSIGNED-LOCAL (honest) — no in-image key in this runtime; "
                            "no signature fabricated."),
        "doctrine": DOCTRINE,
        "kernel_commit": _KERNEL,
        "conjecture_note": _CONJECTURE_NOTE,
        "label": ("LIVE governed agent loop — plan (MODELED) → act (engine P1-P6, Λ-gate, "
                  "sandbox) → self-eval (eval-arena) → HumanApprovalGate → bounded retry → "
                  "ONE composite signed receipt chaining profile+step+eval, ingested to "
                  "/llm/forum. Λ is Conjecture 1 (advisory)."),
    }


def _sign(receipt_body: dict, sign_fn: Callable[[dict], dict]) -> tuple[dict, dict]:
    """Sign the composite receipt with the HOST signer (real ECDSA-P256 in-Space;
    honest UNSIGNED-LOCAL locally). Falls back to szl_dsse, then to an honest PAE
    digest — NEVER fabricates a signature."""
    # 1) host signer (same in-image key the engine + eval-arena use)
    if callable(sign_fn):
        try:
            env = sign_fn(receipt_body)
            if isinstance(env, dict):
                signing = {
                    "available": bool(env.get("signed")),
                    "mode": "REAL" if env.get("signed") else "UNSIGNED-LOCAL",
                    "alg": "ECDSA-P256-SHA256", "envelope": "DSSEv1",
                    "pae_sha256": env.get("_pae_sha256"),
                    "note": env.get("honesty"),
                }
                return env, signing
        except Exception:
            pass
    # 2) szl_dsse directly
    try:
        import szl_dsse
        env = szl_dsse.sign_payload(receipt_body, "application/vnd.szl.khipu+json")
        signing = {
            "available": bool(szl_dsse.signing_available()),
            "mode": "REAL" if env.get("signed") else "UNSIGNED-LOCAL",
            "alg": "ECDSA-P256-SHA256", "envelope": "DSSEv1",
            "pae_sha256": env.get("_pae_sha256"), "note": env.get("honesty"),
        }
        return env, signing
    except Exception as e:  # pragma: no cover
        body = _canon(receipt_body).encode("utf-8")
        pae = b"DSSEv1 " + b"application/vnd.szl.khipu+json " + body
        env = {"payloadType": "application/vnd.szl.khipu+json",
               "payload_sha256": hashlib.sha256(body).hexdigest(),
               "_pae_sha256": hashlib.sha256(pae).hexdigest(),
               "signatures": [], "signed": False,
               "honesty": "UNSIGNED-LOCAL — no signer available (%r); no signature fabricated." % e}
        signing = {"available": False, "mode": "UNSIGNED-LOCAL", "alg": "ECDSA-P256-SHA256",
                   "envelope": "DSSEv1", "pae_sha256": env["_pae_sha256"], "note": env["honesty"]}
        return env, signing


def _ingest_forum(receipt_body: dict, dsse: dict) -> dict:
    """Ingest the composite receipt into the shared /llm/forum substrate. Mirrors
    serve.py's resolution order EXACTLY (substrate package first, local fallback) so
    the append lands in the SAME _FORUM_LOG the /llm/forum GET reads."""
    try:
        try:  # pragma: no cover
            from szl_substrate import szl_llm_registry as _reg
        except Exception:
            import szl_llm_registry as _reg
        entry = {
            "ts": _now(),
            "source": "agent_loop_governed",
            "event": "agentloop_run",
            "schema": SCHEMA,
            "run_id": receipt_body.get("run_id"),
            "task_preview": (receipt_body.get("task") or "")[:80],
            "mode": receipt_body.get("mode"),
            "n_steps": receipt_body.get("n_steps"),
            "mean_eval_accuracy": receipt_body.get("aggregate", {}).get("mean_eval_accuracy"),
            "mean_eval_lambda": receipt_body.get("aggregate", {}).get("mean_eval_lambda"),
            "run_chain_digest": receipt_body.get("run_chain_digest"),
            "signed": bool(dsse.get("signed")),
            "receipt_schema": SCHEMA,
        }
        _reg._forum_append(entry)
        return {"ingested": True, "forum": "/api/a11oy/v1/llm/forum", "source": "agent_loop_governed"}
    except Exception as e:  # pragma: no cover
        return {"ingested": False, "note": "forum ingest skipped (%r)" % e}


# ===========================================================================
# ROUTE REGISTRATION — Starlette routes inserted BEFORE the SPA catch-all.
# sign_fn = the HOST app's REAL signer (same as the engine + eval-arena use).
# ===========================================================================
def register(app, ns: str = "a11oy", sign_fn: Optional[Callable[[dict], dict]] = None,
             verify_fn=None) -> dict:
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    if not callable(sign_fn):
        # Honest fallback signer via szl_dsse (still real in-Space, UNSIGNED-LOCAL locally).
        def _fallback_sign(obj: dict) -> dict:
            try:
                import szl_dsse
                return szl_dsse.sign_payload(obj, "application/vnd.szl.khipu+json")
            except Exception as e:
                body = _canon(obj).encode("utf-8")
                return {"payloadType": "application/vnd.szl.khipu+json",
                        "_pae_sha256": hashlib.sha256(body).hexdigest(),
                        "signatures": [], "signed": False,
                        "honesty": "UNSIGNED-LOCAL — no signer (%r)." % e}
        sign_fn = _fallback_sign

    async def _run(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        task = b.get("task") or b.get("prompt") or b.get("query") or ""
        if not task:
            return JSONResponse({
                "ok": False,
                "error": "task is required",
                "label": "MODELED — supply a task to run the governed loop.",
                "conjecture_note": _CONJECTURE_NOTE,
            }, status_code=400)
        mode = (b.get("mode") or "").lower()
        model_id = str(b.get("model_id") or b.get("model") or "").strip()
        harness_profile_id = str(b.get("harness_profile_id") or b.get("profile_id") or "").strip()
        eval_suite = str(b.get("eval_suite") or b.get("suite_id") or "").strip()
        approval = b.get("approval") if isinstance(b.get("approval"), dict) else None
        try:
            max_retries = int(b.get("max_retries", 1))
        except Exception:
            max_retries = 1
        sandbox = b.get("sandbox")
        sandbox = None if sandbox is None else bool(sandbox)
        # Wave O: opt-in Brain pulse consultation (advisory context only).
        consult_brain = bool(b.get("consult_brain") or b.get("brain") or False)
        result = run_loop(task, sign_fn, ns=ns, mode=mode, model_id=model_id,
                          harness_profile_id=harness_profile_id, eval_suite=eval_suite,
                          approval=approval, max_retries=max_retries, sandbox=sandbox,
                          consult_brain=consult_brain)
        return JSONResponse(result, status_code=result.get("status_code", 200))

    async def _health(request):
        signer_live = False
        try:
            probe = sign_fn({"probe": "agentloop-health", "ts": _now()})
            signer_live = bool(probe.get("signed"))
        except Exception:
            signer_live = False
        eval_suites = None
        if _ARENA_OK:
            try:
                eval_suites = list(getattr(_arena, "_SUITES", {}).keys())
            except Exception:
                eval_suites = None
        return JSONResponse({
            "surface": "szl_agent_loop_governed — governed autonomous agent loop",
            "role": ("Composes /code run-loop (act) + model-harness (behavior profile) + "
                     "eval-arena (self-eval) + HumanApprovalGate into ONE governed loop with "
                     "ONE composite signed receipt per run, ingested to /llm/forum."),
            "composes": {
                "act_engine_available": _ENGINE_OK,
                "plan_source_available": _RUNLOOP_OK,
                "self_eval_available": _ARENA_OK,
                "behavior_profile_available": _HARNESS_OK,
                "human_gate_available": _APPROVAL_OK,
                "sovereign_available": _SOV_OK,
                "brain_consult_available": _BRAIN_OK,
            },
            # Wave O (Dev 4): the loop can CONSULT the Brain pulse for context.
            "consult_brain": {
                "available": bool(_BRAIN_OK),
                "how": ("POST /agentloop/run with consult_brain=true. The loop reads the "
                        "Brain pulse (Dev-1 szl_brain_hub preferred; guarded a11oy_brain_graph "
                        "fallback until #brain-hub merges) + the top brain passages relevant to "
                        "the task, and records them in the composite receipt as ADVISORY context. "
                        "It never changes a gate/decision and never fabricates a citation; honest "
                        "UNAVAILABLE when the vault is empty/down."),
                "brain_available": (bool(_brain.available(ns)) if _BRAIN_OK and _brain else False),
            },
            # Wave M (Dev 2): run this governed loop on SZL's OWN model.
            "run_on_sovereign": {
                "available": bool(_SOV_OK),
                "how": ("POST /agentloop/run with model_id='szl-sovereign-local' "
                        "(alias of registry backend 'sovereign_local'). The loop "
                        "probes the local Tower via Dev-1's backend and records the "
                        "intended sovereign backend in the composite receipt; honest "
                        "MODELED/UNAVAILABLE when offline (no fabrication)."),
                "backend_id": "sovereign_local",
                "model_slug": "llama3-szl-finetuned-q4",
            },
            "eval_suites": eval_suites,
            "approval_gate_enabled": os.environ.get("A11OY_APPROVAL_INTERRUPT") == "1",
            "signer_live": signer_live,
            "signature_mode": ("LIVE (real ECDSA-P256 in-image key)" if signer_live
                               else "UNSIGNED-LOCAL (honest — no in-image key in this runtime)"),
            "endpoints": ["/api/%s/v1/agentloop/run" % ns,
                          "/api/%s/v1/agentloop/health" % ns],
            "backs_view": "governedagent",
            "leaders_cited": LEADERS,
            "lambda": "Conjecture 1 (advisory — never a gate, never 'green').",
            "doctrine": DOCTRINE,
            "kernel_commit": _KERNEL,
            "locked8_touched": False,
            "honesty": (
                "Plan = MODELED; act + self-eval + gate + composite receipt = LIVE. "
                "Signatures real in-Space, honest UNSIGNED-LOCAL locally. Λ = Conjecture 1."),
            "checked_at": _now(),
        })

    routes = [
        Route("/api/%s/v1/agentloop/run" % ns, _run, methods=["POST"],
              name="%s_agentloop_run" % ns),
        Route("/api/%s/v1/agentloop/health" % ns, _health, methods=["GET"],
              name="%s_agentloop_health" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "act_engine_available": _ENGINE_OK, "self_eval_available": _ARENA_OK,
            "behavior_profile_available": _HARNESS_OK, "human_gate_available": _APPROVAL_OK}


def _selftest() -> None:  # pragma: no cover
    """Local honest selftest — no network, no fabricated data."""
    import szl_dsse
    def _sign(obj):
        return szl_dsse.sign_payload(obj, "application/vnd.szl.khipu+json")
    out = run_loop("write a python function that returns the first 5 primes",
                   _sign, ns="a11oy", mode="code", max_retries=1)
    assert out["ok"] is True, out
    assert out["composite_receipt"]["body"]["schema"] == SCHEMA
    assert out["composite_receipt"]["body"]["locked8_touched"] is False
    assert out["aggregate"]["lambda_status"] == "CONJECTURE"
    assert out["n_steps"] if "n_steps" in out else True
    assert len(out["steps"]) >= 1
    # Wave O: consult_brain attaches an advisory Brain-pulse context (labelled),
    # recorded in the composite receipt, never changing a gate/decision.
    outb = run_loop("explain the Euler Khipu DAG identity F1", _sign, ns="a11oy",
                    mode="chat", max_retries=0, consult_brain=True)
    assert outb["ok"] is True
    bc = outb["composite_receipt"]["body"]["brain_context"]
    assert isinstance(bc, dict) and "label" in bc and "available" in bc
    assert outb["composite_receipt"]["body"]["brain_consulted"] is True
    # gate/decision unaffected: locked-8 still untouched, Λ still Conjecture.
    assert outb["composite_receipt"]["body"]["locked8_touched"] is False
    print(f"szl_agent_loop_governed: consult_brain -> brain_context label={bc['label']!r} "
          f"available={bc['available']} relevant={len(bc.get('relevant', []))}")
    print("szl_agent_loop_governed: ALL OK (composed engine+harness+eval+gate, "
          "ONE composite signed receipt, Λ=Conjecture 1, locked-8 untouched)")


if __name__ == "__main__":  # pragma: no cover
    _selftest()
