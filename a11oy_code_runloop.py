# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED (749/14/163). Signed: Yachay.
# Built by: Perplexity Computer Agent (Opus-class). Co-Authored-By in the commit trailer.
"""
a11oy Code — GOVERNED RUN-LOOP orchestrator routes (the /code surface backend).

WHAT THIS IS (honest, one line): a thin, additive orchestrator layer that turns a
task into a *plan*, runs each planned step through the REAL proven governed engine
(`a11oy_code_engine.governed_turn` — the P1-P6 6-receipt loop with a signed DSSE
receipt), surfaces the Λ-gate (advisory, Conjecture 1) per step, and enforces a
durable HumanApprovalGate (`szl_agentic_loop.approval_interrupt`) on state-changing
steps. NO orchestration theater — every step's receipt is the engine's real one.

API SHAPE (modeled on the platform orchestrator for familiarity; served locally):
  POST /api/a11oy/v1/code/plan          {task[,mode]}          -> {run_id, plan[], honest}
  POST /api/a11oy/v1/code/runstep       {run_id, step, prompt, mode[, sandbox, approval]}
                                                               -> engine run + gate + approval
  POST /api/a11oy/v1/code/approve       {checkpoint_id, approver, approved}
                                                               -> approval-interrupt grant echo
  GET  /api/a11oy/v1/code/runloop/health                       -> honest liveness of the surface

HONESTY (absolute):
  - The per-step governed run, the Λ-gate, the receipt chain and the DSSE signature
    are REAL (the engine's own code). The *plan decomposition* is a deterministic,
    MODELED heuristic (labeled MODELED in every response) — it is not itself a proof.
  - Λ (trust score) is ALWAYS Conjecture 1 — advisory, NEVER "green"/proven/a gate.
  - The HumanApprovalGate is OFF unless A11OY_APPROVAL_INTERRUPT=1 (honest label);
    when off, the UI shows it as MODELED-OFF, not a fake approval.
  - Signatures are REAL ECDSA-P256 in-Space when the in-image key is present; an
    honest UNSIGNED marker locally. Never a fabricated signature.

Registered BEFORE the SPA catch-all (routes.insert(0, ...)), try/except guarded so
a missing dependency can NEVER take the Space down. Reuses the host app's REAL
signer/verifier passed in from serve.py (same ones a11oy_code_engine uses).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional


# ---- reuse the REAL engine (single source of truth for the governed run) -----
try:
    import a11oy_code_engine as _engine
    _ENGINE_OK = True
except Exception as _e:  # additive: never break the Space if the engine moves
    _ENGINE_OK = False
    _ENGINE_ERR = repr(_e)

# ---- reuse the REAL durable HumanApprovalGate primitive ----------------------
try:
    import szl_agentic_loop as _loop
    _approval_interrupt = getattr(_loop, "approval_interrupt", None)
    _APPROVAL_OK = callable(_approval_interrupt)
except Exception:
    _APPROVAL_OK = False
    _approval_interrupt = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mk_run_id(task: str) -> str:
    h = hashlib.sha256(("%s|%s" % (task, time.time())).encode()).hexdigest()[:12]
    return "run-%s" % h


# ===========================================================================
# PLAN DECOMPOSITION  (deterministic, MODELED — labeled as such everywhere).
# Turns a free-text task into an ordered list of governed steps. Each step will
# be EXECUTED by the real engine (governed_turn) — so the plan is modeled but the
# execution + receipts are live. We mirror the platform orchestrator's step shape.
# ===========================================================================
def _classify_mode(task: str) -> str:
    t = (task or "").lower()
    if any(k in t for k in ("cve", "kev", "mitre", "att&ck", "research", "cite",
                            "source", "what is", "explain", "vulnerab", "earthquake")):
        return "research"
    if any(k in t for k in ("def ", "function", "class ", "import ", "compute",
                            "algorithm", "fix ", "bug", "refactor", "code", "script",
                            "loop", "regex", "sort", "prime", "fib", "factorial",
                            "run ", "execute", "sandbox")):
        return "code"
    return "chat"


def plan(task: str, mode: str = "") -> dict:
    """Deterministic MODELED plan: decompose the task into governed steps. Each
    step declares the engine mode + whether it requests a sandbox exec (code) and
    a state-change hint (drives the HumanApprovalGate). NOT a proof — a modeled
    decomposition executed step-by-step by the real governed engine."""
    task = (task or "").strip()
    mode = (mode or "").lower() or _classify_mode(task)
    if mode not in ("chat", "code", "research"):
        mode = _classify_mode(task)
    run_id = _mk_run_id(task)

    steps: list[dict] = []

    # Step 1 — always: understand + retrieve (chat/research grounding of the task).
    steps.append({
        "n": 1, "title": "Understand & ground the task",
        "mode": "research" if mode == "research" else "chat",
        "prompt": task or "Describe the task.",
        "sandbox": False, "state_changing": False,
        "why": "Retrieve in-image governance context and frame the task (P1 retrieve).",
    })

    if mode == "code":
        # Step 2 — synthesize code. Step 3 — governed sandbox EXECUTION (state-changing).
        steps.append({
            "n": 2, "title": "Synthesize candidate code",
            "mode": "code", "prompt": task, "sandbox": False, "state_changing": False,
            "why": "Route to an open-weight coder (or the honest local scaffold) and "
                   "produce runnable code — still behind the Λ-gate + policy gate.",
        })
        steps.append({
            "n": 3, "title": "Execute code in the governed sandbox",
            "mode": "code", "prompt": task, "sandbox": True, "state_changing": True,
            "why": "Run the code in the REAL restricted-subprocess sandbox. This is a "
                   "state-changing action, so it also passes the HumanApprovalGate when enabled.",
        })
    elif mode == "research":
        steps.append({
            "n": 2, "title": "Answer with cited sources",
            "mode": "research", "prompt": task, "sandbox": False, "state_changing": False,
            "why": "Emit a grounded, cited answer over the in-image corpus / live feeds.",
        })
    else:  # chat
        steps.append({
            "n": 2, "title": "Compose the governed answer",
            "mode": "chat", "prompt": task, "sandbox": False, "state_changing": False,
            "why": "Emit the answer through the full P1-P6 loop with a signed receipt.",
        })

    return {
        "run_id": run_id,
        "task": task,
        "mode": mode,
        "created_at": _now(),
        "plan": steps,
        "engine_available": _ENGINE_OK,
        "approval_gate_available": _APPROVAL_OK,
        "label": "MODELED plan — deterministic decomposition. Each step is EXECUTED by "
                 "the REAL governed engine (P1-P6, signed receipt). The plan itself is a "
                 "modeled heuristic, not a proof.",
        "doctrine": "v11",
        "lambda": "Conjecture 1 (advisory — never a gate, never 'green'/proven).",
    }


# ===========================================================================
# ROUTE REGISTRATION — Starlette routes inserted BEFORE the SPA catch-all.
# sign_fn / verify_fn = the HOST app's REAL signer/verifier (same as the engine).
# ===========================================================================
def register(app, ns: str, sign_fn, verify_fn=None):
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    async def _plan(request):
        try:
            b = await request.json()
        except Exception:
            b = {}
        task = b.get("task") or b.get("prompt") or b.get("query") or ""
        mode = (b.get("mode") or "").lower()
        return JSONResponse(plan(task, mode))

    async def _runstep(request):
        """Execute ONE planned step through the REAL governed engine. Returns the
        engine's full governed run (chain + signed receipt + Λ-gate) PLUS the
        HumanApprovalGate verdict for state-changing steps. NEVER fabricates."""
        try:
            b = await request.json()
        except Exception:
            b = {}
        if not _ENGINE_OK:
            return JSONResponse({
                "ok": False,
                "error": "engine unavailable: %s" % _ENGINE_ERR,
                "label": "MODELED-UNAVAILABLE — the real governed engine could not be "
                         "imported in this runtime; no run fabricated.",
            }, status_code=200)
        mode = (b.get("mode") or "chat").lower()
        if mode not in ("chat", "code", "research"):
            mode = "chat"
        prompt = b.get("prompt") or b.get("task") or ""
        sandbox = bool(b.get("sandbox", mode == "code"))
        untrusted = b.get("untrusted_input") or b.get("untrusted") or ""
        want_model = b.get("model") or b.get("want_model") or ""
        state_changing = bool(b.get("state_changing", sandbox))
        grant = b.get("approval") if isinstance(b.get("approval"), dict) else None
        # Wave G: OPTIONAL behavior profile for THIS step. When set, the engine
        # runs the model through szl_model_harness.apply (profile system layer +
        # Λ-gate) and the step's SIGNED receipt records the profile provenance.
        # This is the governed version of how the leaders switch a persona on a
        # step mid-run (LangGraph runtime context / Swarm handoff / CrewAI role /
        # AutoGen system_message / Claude Code subagent / MCP prompts/get).
        harness_profile_id = str(b.get("harness_profile_id") or b.get("profile_id") or "").strip()

        # REAL governed run (P1-P6, signed DSSE receipt) via the engine.
        run = _engine.governed_turn(mode, prompt, sign_fn, ns,
                                    untrusted_input=untrusted, run_chain=[],
                                    sandbox=sandbox, want_model=want_model,
                                    harness_profile_id=harness_profile_id)

        # HumanApprovalGate — durable checkpoint on state-changing, gate-allowed steps.
        approval = None
        if _APPROVAL_OK:
            try:
                approval = _approval_interrupt(
                    action=run.get("gate", {}).get("severity", "") + ":" + (prompt or "")[:60],
                    severity=run.get("gate", {}).get("severity", "low"),
                    reversible=not state_changing,
                    decision=run.get("decision", "DENY"),
                    grant=grant,
                )
            except Exception as e:
                approval = {"required": None, "granted": None, "checkpoint_id": None,
                            "note": "approval-interrupt error: %s" % type(e).__name__}
        else:
            approval = {"required": None, "granted": None, "checkpoint_id": None,
                        "note": "HumanApprovalGate primitive unavailable in this runtime (MODELED-OFF)."}

        # Honest liveness of THIS step's signature.
        sig = run.get("signed_receipt") or {}
        signed_live = bool(sig.get("signed"))

        # Wave G: surface the OPTIONAL behavior profile applied to THIS step so the
        # receipt trail can name it (profile id+version+sha256, model_id, provenance).
        harness = run.get("harness") or None
        harness_summary = None
        if harness:
            _hp = (harness.get("profile") or {})
            _prov = (_hp.get("provenance") or {})
            harness_summary = {
                "requested": harness.get("requested"),
                "available": harness.get("available"),
                "profile_id": _hp.get("id"),
                "profile_name": _hp.get("name"),
                "version": _hp.get("version"),
                "sha256": _prov.get("sha256_resolved") or _prov.get("sha256_manifest"),
                "sha256_integrity": _prov.get("sha256_integrity"),
                "provenance": {"author": _prov.get("author"), "source": _prov.get("source"),
                               "license": _prov.get("license"),
                               "not_verbatim_of": _prov.get("not_verbatim_of")},
                "harness_state": harness.get("harness_state"),
                "honesty": harness.get("honesty"),
                "forum_ingested": bool((harness.get("forum") or {}).get("ingested")),
                "label": ("Governed behavior profile attached to this step — Λ-gated + "
                          "sha256-provenanced + signed. Behavior transfer is MODELED "
                          "(disposition only; capability ceiling unchanged). The profile "
                          "swap is recorded in /llm/forum."),
            }

        return JSONResponse({
            "ok": True,
            "step": b.get("step"),
            "run": run,
            "approval": approval,
            "harness_profile": harness_summary,
            "signature_live": signed_live,
            "signature_label": ("LIVE — real ECDSA-P256 DSSE over the receipt (verify vs /cosign.pub)."
                                if signed_live else
                                "UNSIGNED (honest) — no in-image key in this runtime; no signature fabricated."),
            "label": "LIVE governed step — the P1-P6 chain, Λ-gate and receipt are the "
                     "engine's REAL output. Λ is advisory (Conjecture 1)."
                     + (" Behavior profile '%s' was applied to this step." % harness_summary["profile_id"]
                        if harness_summary and harness_summary.get("profile_id") else ""),
        })

    async def _approve(request):
        """Echo a HumanApprovalGate grant back so the UI can re-run the step carrying
        it. This does NOT itself fire anything — it records the human's intent for the
        durable checkpoint; the engine re-run is what may then proceed."""
        try:
            b = await request.json()
        except Exception:
            b = {}
        checkpoint_id = str(b.get("checkpoint_id") or "")
        approver = str(b.get("approver") or "").strip()
        approved = bool(b.get("approved", True))
        if not (checkpoint_id and approver):
            return JSONResponse({
                "ok": False,
                "error": "checkpoint_id and approver are required",
                "label": "MODELED — a grant needs a real approver identity + the exact checkpoint_id.",
            }, status_code=200)
        return JSONResponse({
            "ok": True,
            "grant": {"checkpoint_id": checkpoint_id, "approver": approver[:120],
                      "approved": approved, "granted_at": _now()},
            "label": ("LIVE grant — re-run the step with this grant in `approval`; the durable "
                      "HumanApprovalGate will honour it ONLY for the exact matching checkpoint. "
                      "Approval composes with, never overrides, the deny-by-default gate."),
        })

    async def _health(request):
        # Honest liveness: is the engine importable? is the signer real? is approval on?
        signer_live = False
        try:
            probe = sign_fn({"probe": "runloop-health", "ts": _now()})
            signer_live = bool(probe.get("signed"))
        except Exception:
            signer_live = False
        import os
        # Wave G: honest liveness of the OPTIONAL behavior-profile harness.
        harness_available = False
        harness_profile_count = None
        try:
            import szl_model_harness as _h
            harness_available = callable(getattr(_h, "apply", None))
            try:
                harness_profile_count = len(_h._load_manifests())
            except Exception:
                harness_profile_count = None
        except Exception:
            harness_available = False
        return JSONResponse({
            "surface": "a11oy Code — governed run-loop",
            "engine_available": _ENGINE_OK,
            "engine_error": (None if _ENGINE_OK else _ENGINE_ERR),
            "approval_gate_available": _APPROVAL_OK,
            "harness_available": harness_available,
            "harness_profile_count": harness_profile_count,
            "harness_profiles_endpoint": "/api/%s/v1/harness/profiles" % ns,
            "harness_note": ("OPTIONAL per-step behavior profile: pass harness_profile_id to "
                             "/runstep; the step runs the model through the governed harness "
                             "(profile system layer + Λ-gate) and the signed receipt records "
                             "the profile provenance. Profile-swaps appear in /llm/forum."),
            "approval_gate_enabled": os.environ.get("A11OY_APPROVAL_INTERRUPT") == "1",
            "signer_live": signer_live,
            "signature_mode": ("LIVE (real ECDSA-P256 in-image key)" if signer_live
                               else "UNSIGNED (honest marker — no in-image key in this runtime)"),
            "endpoints": ["/api/%s/v1/code/plan" % ns,
                          "/api/%s/v1/code/runstep" % ns,
                          "/api/%s/v1/code/approve" % ns,
                          "/api/%s/v1/code/runloop/health" % ns],
            "backs_view": "/code",
            "lambda": "Conjecture 1 (advisory — never a gate).",
            "doctrine": "v11",
            "honesty": ("The run-loop EXECUTES each modeled plan step through the real "
                        "governed engine. Plan = MODELED; execution + Λ-gate + receipt = LIVE. "
                        "Signatures real in-Space, honest UNSIGNED locally."),
            "checked_at": _now(),
        })

    routes = [
        Route("/api/%s/v1/code/plan" % ns, _plan, methods=["POST"], name="%s_code_plan" % ns),
        Route("/api/%s/v1/code/runstep" % ns, _runstep, methods=["POST"], name="%s_code_runstep" % ns),
        Route("/api/%s/v1/code/approve" % ns, _approve, methods=["POST"], name="%s_code_approve" % ns),
        Route("/api/%s/v1/code/runloop/health" % ns, _health, methods=["GET"], name="%s_code_runloop_health" % ns),
    ]
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {"registered": [r.path for r in routes], "ns": ns,
            "engine_available": _ENGINE_OK, "approval_gate_available": _APPROVAL_OK}
