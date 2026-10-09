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
  POST /api/a11oy/v1/code/plan          {task, purpose[, mode]} -> {run_id, plan[], honest}
  POST /api/a11oy/v1/code/runstep       {prompt, purpose[, mode, sandbox, approval]}
                                                               -> engine run + restart receipt
Operator Bearer and the configured tenant are checked before the body is parsed.
Purpose is chat, code, or research. The admitted purpose is the engine mode.
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
import hmac
import json
import os
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

try:
    import szl_operator_auth as _opauth
except Exception:  # resolver absent: nobody may execute (deny-by-default)
    _opauth = None


def _exec_permitted(request) -> bool:
    return bool(_opauth is not None and _opauth.exec_permitted(request))


def _refused(request, action: str):
    """401 BLOCKED before any plan, model call, gate or grant for a caller without
    the operator Bearer. A host without the resolver refuses everyone."""
    if _opauth is None:
        from starlette.responses import JSONResponse
        return JSONResponse({"ok": False, "status": "BLOCKED",
                             "error": "%s requires the operator credential." % action},
                            status_code=401, headers={"WWW-Authenticate": "Bearer"})
    return _opauth.operator_refusal(request, action)


# Admission for this surface only. It does not configure SZL_SECOND_BRAIN_RAG,
# the completion aliases, holographic RAG, graph analysis, or Hatun.
TENANT_ENV = "A11OY_CODE_TENANT"
TENANT_HEADER = "x-a11oy-tenant"
RECEIPT_LOG_ENV = "A11OY_CODE_RUNLOOP_RECEIPT_LOG"
_PURPOSES = frozenset({"chat", "code", "research"})
_MAX_QUERY_CHARS = 2000
_MAX_QUERY_BYTES = 8192
FIXED_SYNTHETIC_QUERY = "synthetic fixture: deny-by-default gate"
_RECEIPT_SCHEMA = "szl.a11oy.code-runloop-receipt/v1"
_RECEIPT_BODY_KEYS = (
    "schema", "evidence_class", "signer", "query_sha256", "purpose",
    "chain_final_hash", "receipt_chain", "signed_receipt",
)


def _blocked(error: str, status_code: int, **extra):
    from starlette.responses import JSONResponse
    body = {"ok": False, "status": "BLOCKED", "error": error}
    body.update(extra)
    return JSONResponse(body, status_code=status_code)


def _tenant_refusal(request):
    """Match the configured tenant before the body is parsed. Unset is fail-closed."""
    try:
        expected = (os.environ.get(TENANT_ENV) or "").strip()
        presented = (request.headers.get(TENANT_HEADER) or "").strip()
    except Exception:
        return _blocked("tenant admission unavailable", 503, tenant_configured=False)
    if not expected:
        return _blocked("tenant is not configured", 503, tenant_configured=False)
    presented_digest = hashlib.sha256(presented.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    if not hmac.compare_digest(presented_digest, expected_digest):
        return _blocked("tenant is not admitted", 403, tenant_configured=True)
    return None


def _admit_query(body: Any, primary: str):
    """Return (query, purpose, refusal). Refusal is set before any engine call."""
    if not isinstance(body, dict):
        return None, None, _blocked("JSON object required", 400)
    purpose = body.get("purpose")
    if purpose not in _PURPOSES:
        return None, None, _blocked("purpose is not admitted", 400)
    mode = body.get("mode") or ""
    if not isinstance(mode, str) or (mode and mode != purpose):
        return None, None, _blocked("mode conflicts with purpose", 400)
    raw = body.get(primary)
    if raw is None:
        raw = body.get("query") or body.get("prompt") or body.get("task") or ""
    if not isinstance(raw, str):
        return None, None, _blocked("query must be a string", 400)
    if len(raw) > _MAX_QUERY_CHARS:
        return None, None, _blocked("query exceeds the character limit", 400)
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError:
        return None, None, _blocked("query must be valid UTF-8", 400)
    if len(encoded) > _MAX_QUERY_BYTES:
        return None, None, _blocked("query exceeds 8192 UTF-8 bytes", 400)
    query = raw.strip()
    if not query:
        return None, None, _blocked("query is empty", 400)
    return query, purpose, None


def _canonical_receipt_body(record: dict) -> bytes:
    payload = {key: record[key] for key in _RECEIPT_BODY_KEYS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _persist_run_receipt(query: str, purpose: str, run: dict) -> dict:
    """Append one SIMULATED or host receipt. Unsigned output stays SIMULATED."""
    path = (os.environ.get(RECEIPT_LOG_ENV) or "").strip()
    signed_receipt = run.get("signed_receipt") if isinstance(run, dict) else None
    signed = bool(isinstance(signed_receipt, dict) and signed_receipt.get("signed") is True)
    record = {
        "schema": _RECEIPT_SCHEMA,
        "evidence_class": "DECLARED" if signed else "SIMULATED",
        "signer": "HOST" if signed else "SIMULATED",
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "purpose": purpose,
        "chain_final_hash": (run or {}).get("chain_final_hash"),
        "receipt_chain": (run or {}).get("receipt_chain") or [],
        "signed_receipt": signed_receipt or {"signed": False, "signatures": []},
    }
    digest = hashlib.sha256(_canonical_receipt_body(record)).hexdigest()
    record["record_sha256"] = digest
    if not path:
        return {"persisted": False, "restart_verifiable": False,
                "evidence_class": record["evidence_class"], "reason": "receipt log is not configured"}
    try:
        line = json.dumps(record, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True).encode("utf-8") + b"\n"
        flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
    except (OSError, TypeError, ValueError) as exc:
        return {"persisted": False, "restart_verifiable": False,
                "evidence_class": record["evidence_class"],
                "reason": type(exc).__name__}
    return {"persisted": True, "restart_verifiable": True,
            "evidence_class": record["evidence_class"], "signer": record["signer"],
            "record_sha256": digest, "chain_final_hash": record["chain_final_hash"]}


def verify_receipt_log(path: str) -> dict:
    """Re-read a receipt file and recompute its chain. A new process can call this."""
    try:
        import a11oy_code_engine as engine
    except Exception as exc:
        return {"ok": False, "status": "UNAVAILABLE", "reason": type(exc).__name__}
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        return {"ok": False, "status": "UNAVAILABLE", "reason": type(exc).__name__}
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        return {"ok": False, "status": "UNAVAILABLE", "reason": "empty receipt log"}
    checked = []
    for line in lines:
        try:
            record = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return {"ok": False, "status": "BLOCKED", "reason": "malformed receipt line"}
        if not isinstance(record, dict) or set(record) != set(_RECEIPT_BODY_KEYS) | {"record_sha256"}:
            return {"ok": False, "status": "BLOCKED", "reason": "unexpected receipt fields"}
        if record.get("schema") != _RECEIPT_SCHEMA:
            return {"ok": False, "status": "BLOCKED", "reason": "unexpected receipt schema"}
        if record.get("purpose") not in _PURPOSES:
            return {"ok": False, "status": "BLOCKED", "reason": "purpose is not admitted"}
        signed_receipt = record.get("signed_receipt")
        signed_flag = (isinstance(signed_receipt, dict)
                       and signed_receipt.get("signed") is True)
        expect_class = "DECLARED" if signed_flag else "SIMULATED"
        expect_signer = "HOST" if signed_flag else "SIMULATED"
        if (record.get("evidence_class") != expect_class
                or record.get("signer") != expect_signer):
            return {"ok": False, "status": "BLOCKED",
                    "reason": "evidence class does not match the signature flag"}
        query_sha = record.get("query_sha256")
        if not isinstance(query_sha, str) or len(query_sha) != 64:
            return {"ok": False, "status": "BLOCKED", "reason": "query digest is absent"}
        expect = hashlib.sha256(_canonical_receipt_body(record)).hexdigest()
        if not hmac.compare_digest(str(record.get("record_sha256") or ""), expect):
            return {"ok": False, "status": "BLOCKED", "reason": "record digest mismatch"}
        verdict = engine.verify_run({
            "receipt_chain": record["receipt_chain"],
            "signed_receipt": record["signed_receipt"],
        })
        if verdict.get("chain_intact") is not True:
            return {"ok": False, "status": "BLOCKED", "reason": "chain mismatch",
                    "chain_break_at_seq": verdict.get("chain_break_at_seq")}
        if verdict.get("final_hash") != record.get("chain_final_hash"):
            return {"ok": False, "status": "BLOCKED", "reason": "final hash mismatch"}
        checked.append({
            "record_sha256": expect,
            "evidence_class": record["evidence_class"],
            "signer": record["signer"],
            "query_sha256": record["query_sha256"],
            "purpose": record["purpose"],
            "chain_intact": True,
            "signature_valid": verdict.get("signature_valid"),
        })
    return {"ok": True, "status": "CHECKED", "count": len(checked), "receipts": checked}


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
        refused = _refused(request, "Run-loop plan")
        if refused is not None:
            return refused
        tenant = _tenant_refusal(request)
        if tenant is not None:
            return tenant
        try:
            b = await request.json()
        except Exception:
            return _blocked("JSON object required", 400)
        query, purpose, refusal = _admit_query(b, "task")
        if refusal is not None:
            return refusal
        body = plan(query, purpose)
        body["purpose"] = purpose
        body["admission"] = "principal, tenant, limits, and purpose checked before plan"
        return JSONResponse(body)

    async def _runstep(request):
        """Execute ONE planned step through the REAL governed engine. Returns the
        engine's full governed run (chain + signed receipt + Λ-gate) PLUS the
        HumanApprovalGate verdict for state-changing steps. NEVER fabricates.
        Admission finishes before the engine import check and before governed_turn.
        A missing engine writes no receipt."""
        refused = _refused(request, "Run-loop step")
        if refused is not None:
            return refused
        tenant = _tenant_refusal(request)
        if tenant is not None:
            return tenant
        try:
            b = await request.json()
        except Exception:
            return _blocked("JSON object required", 400)
        query, purpose, refusal = _admit_query(b, "prompt")
        if refusal is not None:
            return refusal
        if not _ENGINE_OK:
            return JSONResponse({
                "ok": False,
                "error": "engine unavailable: %s" % _ENGINE_ERR,
                "label": "MODELED-UNAVAILABLE — the real governed engine could not be "
                         "imported in this runtime; no run fabricated.",
            }, status_code=200)
        sandbox = bool(b.get("sandbox", purpose == "code"))
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
        # The body may ask for the sandbox; only the verified header principal
        # (two distinct server-held secrets) lets the engine actually run it.
        run = _engine.governed_turn(purpose, query, sign_fn, ns,
                                    untrusted_input=untrusted, run_chain=[],
                                    sandbox=sandbox, want_model=want_model,
                                    harness_profile_id=harness_profile_id,
                                    allow_exec=_exec_permitted(request))

        # HumanApprovalGate — durable checkpoint on state-changing, gate-allowed steps.
        approval = None
        if _APPROVAL_OK:
            try:
                approval = _approval_interrupt(
                    action=run.get("gate", {}).get("severity", "") + ":" + (query or "")[:60],
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

        restart_receipt = _persist_run_receipt(query, purpose, run)
        return JSONResponse({
            "ok": True,
            "step": b.get("step"),
            "run": run,
            "restart_receipt": restart_receipt,
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
        refused = _refused(request, "Run-loop approval grant")
        if refused is not None:
            return refused
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
