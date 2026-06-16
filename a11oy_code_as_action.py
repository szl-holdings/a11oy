# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
a11oy_code_as_action.py — the GOVERNED CODE-AS-ACTION KERNEL (GCAK) orchestration.

The headline agentic-frontier slice: a persistent sandboxed Python kernel
(a11oy_governed_kernel.GovernedKernel) where variables LIVE ACROSS cells, and where
EVERY cell is doctrine-gated BEFORE execution and — when allowed — mints a signed
Khipu provenance receipt with MEASURED-or-SAMPLE joules into the SHARED energy ledger.
A DENIED cell mints an honest signed deny-receipt and NEVER executes.

This module is the ONLY new orchestration; it REUSES (does not rebuild):
  - a11oy_code_engine.hard_security_screen  — the HARD deny-by-default gate
        (key/env/ledger/signer/network/fs bans), runs FIRST, model-independent.
  - szl_restraint.descend_ladder / lambda_score — advisory restraint ceiling + Λ
        (Conjecture 1, OPEN — advisory only; can only tighten, never override a DENY).
  - szl_lambda_tripwire.run_gate_check — hard Λ tripwire HALT (Λ < 0.30).
  - a11oy_governed_kernel.GovernedKernel — the persistent sandboxed worker.
  - szl_provenance_receipt.build_composite — signs ONE composite Khipu receipt into
        the shared provenance chain (signature = DSSE_PLACEHOLDER at the chain layer).
  - szl_energy_operator.get_operator().submit_external_job — routes joules into the
        ONE shared energy ledger via the live operator->ledger wire (PR #465).
  - the host's in-image DSSE signer (sign_fn=_a11oy_sign_receipt, ECDSA-P256,
        verifiable vs /cosign.pub) — passed in at register().

GATE ORDER (per cell, BEFORE exec):
    1. HARD security gate  -> hard_block ? verdict=DENY (no exec, signed deny-receipt)
    2. restraint ladder    -> advisory ceiling comment (HEURISTIC)
    3. Λ advisory score    -> tripwire HALT if Λ<0.30 (verdict=DENY, no exec)
       (a cell EXECUTES only when hard_gate_allow AND trust_pass.)

Routes (Starlette Route, registered BEFORE the SPA catch-all via routes.insert(0)):
    POST /api/a11oy/v1/agent/code/compose         {goal?, code} -> gate+exec a cell
    POST /api/a11oy/v1/agent/code/inspect         {run_id}      -> var-summary digests
    POST /api/a11oy/v1/agent/code/revise          {run_id, code}-> gate+exec next cell
    GET  /api/a11oy/v1/agent/code/status          -> module/kernel-count honest status
    GET  /api/a11oy/v1/agent/code/run/{run_id}    -> a run's cell timeline + receipts
    GET  /api/a11oy/v1/agent/code/receipts/{run_id} -> ordered signed cell receipts

NO write-on-GET: receipts mint only on POST compose/revise, never on a status/run GET.
Doctrine v11: deny-by-default; honest labels; never fabricate a joule/receipt; never
commit/read a key; honest BLOCKED beats fake green.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8", "replace")).hexdigest()


# ---------------------------------------------------------------------------
# In-process run store: each run is a kernel + an ordered list of cell records.
# ---------------------------------------------------------------------------
class _RunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}

    def create(self, goal: str) -> str:
        import a11oy_governed_kernel as gk
        run_id = gk.new_run_id()
        with self._lock:
            self._runs[run_id] = {
                "run_id": run_id, "goal": goal or "",
                "created": _now_iso(), "cells": [], "prev_hash": "GENESIS",
            }
        return run_id

    def get(self, run_id: str) -> dict | None:
        with self._lock:
            return self._runs.get(run_id)

    def append_cell(self, run_id: str, cell: dict) -> dict:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return {}
            cell["seq"] = len(run["cells"])
            cell["prev_hash"] = run["prev_hash"]
            cell["chain_hash"] = _sha256(
                json.dumps({"seq": cell["seq"], "code_sha256": cell.get("code_sha256"),
                            "verdict": cell.get("verdict"), "prev": run["prev_hash"]},
                           sort_keys=True))
            run["prev_hash"] = cell["chain_hash"]
            run["cells"].append(cell)
            return cell

    def count(self) -> int:
        with self._lock:
            return len(self._runs)


_STORE = _RunStore()


# ---------------------------------------------------------------------------
# The doctrine gate over ONE cell (BEFORE exec). HARD gate first, Λ advisory after.
# ---------------------------------------------------------------------------
def evaluate_gate(code: str, intensity: str = "full") -> dict:
    """Decide ALLOW | DENY for one cell BEFORE execution. Returns a structured
    verdict dict. DENY iff hard_block OR Λ tripwire HALT. Λ is advisory and can
    only tighten (add a DENY); it never overrides a hard DENY."""
    import a11oy_code_engine as ce
    import szl_restraint as restraint

    # 1) HARD security gate (deterministic, deny-by-default, model-independent).
    hard = ce.hard_security_screen(code)
    hard_allow = not hard["hard_block"]

    # 2) Restraint ladder (advisory HEURISTIC ceiling on the cell's intent).
    try:
        ladder = restraint.descend_ladder(code or "", intensity)
        restraint_view = {
            "rung": ladder.get("stopped_at_rung"),
            "ceiling": ladder.get("ceiling"),
            "comment": ladder.get("restraint_comment"),
            "label": ladder.get("label", "HEURISTIC"),
        }
    except Exception:
        restraint_view = {"label": "HEURISTIC", "ceiling": None}

    # 3) Λ advisory trust score (Conjecture 1, OPEN — never "proven trust").
    try:
        lam = restraint.lambda_score(restraint_view.get("rung") or 3, intensity, code or "")
        lam_value = float(lam.get("lambda", 0.0))
        lam_view = {"value": lam_value, "below_floor": lam.get("below_floor"),
                    "conjecture": lam.get("conjecture")}
    except Exception:
        lam_value = 0.9
        lam_view = {"value": lam_value, "below_floor": True,
                    "conjecture": "Conjecture 1 (Λ uniqueness) is OPEN — advisory only."}

    # Hard Λ tripwire — HALT if Λ collapses below the halt threshold (advisory escalation).
    tripwire_halt = False
    tripwire_detail = None
    try:
        import szl_lambda_tripwire as tw
        try:
            tw.run_gate_check(gate="code-as-action", payload={"code_sha256": _sha256(code)},
                              lambda_score=lam_value)
        except tw.LambdaTripwireTriggered as e:
            tripwire_halt = True
            tripwire_detail = e.to_dict()
    except Exception:
        pass

    trust_pass = (not tripwire_halt)
    allowed = hard_allow and trust_pass
    if hard["hard_block"]:
        verdict = "DENY"
        reason = hard["reason"]
    elif tripwire_halt:
        verdict = "DENY"
        reason = "Λ-tripwire HALT (advisory trust collapsed below halt threshold)"
    else:
        verdict = "ALLOW"
        reason = "hard gate clean AND advisory trust pass"

    return {
        "verdict": verdict,
        "allowed": allowed,
        "reason": reason,
        "security": {"findings": hard["findings"], "hard_block": hard["hard_block"],
                     "network_or_fs_attempt": hard["network_or_fs_attempt"]},
        "restraint": restraint_view,
        "lambda": lam_view,
        "tripwire": tripwire_detail,
        "note": ("HARD security gate is the deny authority (deterministic, "
                 "model-independent). Λ is advisory (Conjecture 1, OPEN) — it can "
                 "only tighten, never override a hard DENY. Cell runs only when "
                 "hard_gate_allow AND trust_pass."),
    }


# ---------------------------------------------------------------------------
# Receipt emission: signed Khipu composite + DSSE envelope + energy ledger entry.
# ---------------------------------------------------------------------------
def _emit_cell_receipt(run_id: str, seq: int, code: str, verdict: dict,
                       exec_result: dict | None, sign_fn) -> dict:
    """Mint ONE signed receipt for a cell. ALLOWed cells also route joules into the
    shared energy ledger via submit_external_job. DENIED cells mint an honest signed
    deny-receipt (no exec, no joule). Never fabricates a joule or a signature."""
    code_sha = _sha256(code)
    executed = bool(exec_result and exec_result.get("ok") and verdict.get("allowed"))

    energy = {"joules_measured": None, "joules_label": "SAMPLE", "ledger_seq": None,
              "note": "no exec — denied at the gate" if not verdict.get("allowed")
                      else "kernel runs on a CPU node (no NVML lung) — honest SAMPLE"}

    # ENERGY: only for an ALLOWed cell that actually executed. The cell runs in the
    # persistent worker (a CPU node, not an inference lung) so joules are honest
    # SAMPLE unless a real fresh NVML exporter delta is present — never fabricated.
    if verdict.get("allowed") and exec_result is not None:
        try:
            import szl_energy_operator as eo
            op = eo.get_operator()
            stdout = exec_result.get("stdout", "") or ""
            tokens = max(1, (len(code) + len(stdout)) // 4)
            wall_s = float(exec_result.get("wall_s", 0.0) or 0.0)
            rec = op.submit_external_job(
                node="local-governed-kernel", model="a11oy.code_as_action",
                kind="code_cell", tokens=tokens, wall_s=wall_s,
                exporter_sample=None, joules_measured=None)
            energy = {"joules_measured": rec.joules_measured,
                      "joules_label": rec.joules_label,
                      "ledger_seq": rec.seq,
                      "evidence": rec.joules_evidence,
                      "note": ("routed into the shared energy ledger via the operator "
                               "submit_external_job wire; MEASURED only with a fresh "
                               "NVML delta, else SAMPLE (never fabricated).")}
        except Exception as e:  # noqa: BLE001 — energy is additive; never break a receipt
            energy["note"] = "energy ledger unavailable: %s" % type(e).__name__

    # KHIPU composite receipt (signs into the shared provenance chain).
    khipu = {"available": False}
    try:
        import szl_provenance_receipt as pr
        composite = pr.build_composite({
            "action": "a11oy.code_as_action.cell seq=%d verdict=%s" % (seq, verdict["verdict"]),
            "request_id": "%s#%d" % (run_id, seq),
        })
        khipu = {"available": True, "digest": composite.get("digest"),
                 "prev": composite.get("prev"),
                 "chain_verified": composite.get("chain_verified"),
                 "signature": (composite.get("khipu") or {}).get("signature"),
                 "kind": "Conjecture 2"}
    except Exception as e:  # noqa: BLE001
        khipu = {"available": False, "note": "khipu unavailable: %s" % type(e).__name__}

    payload = {
        "receipt_type": "a11oy.code_as_action.cell",
        "run_id": run_id, "seq": seq,
        "code_sha256": code_sha, "code_preview": (code or "")[:200],
        "verdict": verdict["verdict"], "allowed": verdict["allowed"],
        "executed": executed,
        "security": verdict["security"],
        "restraint": verdict["restraint"],
        "lambda": verdict["lambda"],
        "exec": ({"ok": exec_result.get("ok"), "exit": exec_result.get("exit"),
                  "wall_s": exec_result.get("wall_s"),
                  "stdout_sha256": _sha256(exec_result.get("stdout", "")),
                  "degraded": exec_result.get("degraded", False),
                  "isolation": exec_result.get("isolation")}
                 if exec_result is not None else
                 {"ok": False, "isolation": "not executed — blocked at the gate"}),
        "energy": energy,
        "khipu": khipu,
        "honest_label": ("DENIED before exec — signed deny-receipt only, nothing ran. "
                         "This is the governance working." if not verdict["allowed"]
                         else "ALLOWED — ran in the governed persistent kernel; "
                              "signed receipt + shared-ledger energy entry."),
        "doctrine": "v11",
        "ts": _now_iso(),
    }

    # DSSE sign the cell receipt with the host's in-image ECDSA-P256 key.
    dsse = {"signed": False}
    if sign_fn is not None:
        try:
            env = sign_fn(payload)
            dsse = {"signed": bool(env.get("signed")),
                    "payloadType": env.get("payloadType"),
                    "keyid": (env.get("signatures") or [{}])[0].get("keyid")
                             if env.get("signatures") else None,
                    "honesty": env.get("honesty"), "verify": "/cosign.pub"}
        except Exception as e:  # noqa: BLE001
            dsse = {"signed": False, "honesty": "UNSIGNED — signer raised: %s"
                    % type(e).__name__}
    payload["dsse"] = dsse
    return payload


# ---------------------------------------------------------------------------
# The single governed cell: gate -> (exec if allowed) -> signed receipt.
# ---------------------------------------------------------------------------
def run_cell(run_id: str, code: str, sign_fn=None, intensity: str = "full") -> dict:
    """Gate one cell, execute it in the persistent kernel ONLY if allowed, mint a
    signed receipt either way, and append it to the run timeline."""
    import a11oy_governed_kernel as gk

    verdict = evaluate_gate(code, intensity=intensity)
    exec_result = None
    if verdict["allowed"]:
        kernel = gk.get_kernel(run_id, create=True)
        exec_result = kernel.exec_cell(code)

    seq = len(_STORE.get(run_id)["cells"]) if _STORE.get(run_id) else 0
    receipt = _emit_cell_receipt(run_id, seq, code, verdict, exec_result, sign_fn)

    cell = {
        "code": code, "code_sha256": receipt["code_sha256"],
        "verdict": verdict["verdict"], "allowed": verdict["allowed"],
        "security": verdict["security"], "restraint": verdict["restraint"],
        "lambda": verdict["lambda"],
        "stdout": (exec_result or {}).get("stdout", ""),
        "exec_ok": (exec_result or {}).get("ok", False),
        "executed": receipt["executed"],
        "var_summary": (exec_result or {}).get("vars", {}),
        "new_or_changed": (exec_result or {}).get("new_or_changed", []),
        "energy": receipt["energy"], "khipu": receipt["khipu"],
        "dsse": receipt["dsse"], "receipt": receipt,
        "ts": _now_iso(),
    }
    _STORE.append_cell(run_id, cell)
    return cell


# ---------------------------------------------------------------------------
# FastAPI/Starlette route registration (mirrors szl_agentic_loop.register).
# ---------------------------------------------------------------------------
def register(app, ns: str, sign_fn, verify_fn=None, pub_pem_fn=None,
             signer_label: str = "in-image key") -> dict:
    """Register the governed code-as-action routes BEFORE the SPA catch-all. Plain
    Starlette Routes inserted at position 0 (avoids FastAPI body-injection 422)."""
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    base = "/api/%s/v1/agent/code" % ns

    async def _compose(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        goal = body.get("goal") or ""
        code = body.get("code")
        if not code:
            return JSONResponse({"error": "compose requires a 'code' cell"}, status_code=400)
        run_id = body.get("run_id") or _STORE.create(goal)
        if _STORE.get(run_id) is None:
            run_id = _STORE.create(goal)
        cell = run_cell(run_id, code, sign_fn=sign_fn,
                        intensity=body.get("intensity", "full"))
        return JSONResponse({"run_id": run_id, "phase": "compose", "cell": cell})

    async def _revise(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        run_id = body.get("run_id")
        code = body.get("code")
        if not run_id or _STORE.get(run_id) is None:
            return JSONResponse({"error": "revise requires a known 'run_id'"}, status_code=400)
        if not code:
            return JSONResponse({"error": "revise requires a 'code' cell"}, status_code=400)
        cell = run_cell(run_id, code, sign_fn=sign_fn,
                        intensity=body.get("intensity", "full"))
        return JSONResponse({"run_id": run_id, "phase": "revise", "cell": cell})

    async def _inspect(request):
        # INSPECT is read-only over the persistent kernel — NO receipt minted (no
        # write-on-GET/POST-read). Returns the hashed var-summary digests.
        try:
            body = await request.json()
        except Exception:
            body = {}
        run_id = body.get("run_id")
        run = _STORE.get(run_id)
        if not run_id or run is None:
            return JSONResponse({"error": "inspect requires a known 'run_id'"}, status_code=400)
        import a11oy_governed_kernel as gk
        kernel = gk.get_kernel(run_id)
        var_summary = kernel.var_summary() if kernel else {}
        return JSONResponse({"run_id": run_id, "phase": "inspect",
                             "var_summary": var_summary,
                             "cells": len(run["cells"]),
                             "note": "read-only inspect — no receipt minted (no write-on-read)."})

    async def _status(request):
        import a11oy_governed_kernel as gk
        return JSONResponse({
            "service": "a11oy.code_as_action",
            "novelty": ("persistent sandboxed kernel — variables live across "
                        "compose->inspect->revise cells; every cell gated before exec; "
                        "each executed cell mints a signed Khipu receipt with "
                        "MEASURED-or-SAMPLE joules into the shared energy ledger."),
            "isolation": gk.ISOLATION_LABEL,
            "active_runs": _STORE.count(),
            "gate_order": ["hard_security_gate (deny authority)",
                           "restraint_ladder (advisory HEURISTIC)",
                           "lambda_advisory (Conjecture 1, OPEN) + tripwire HALT"],
            "doctrine": "v11",
            "honesty": ("subprocess-tier isolation (container/microVM = ROADMAP); "
                        "joules MEASURED only with a real NVML lung, else SAMPLE; "
                        "Khipu signature = DSSE_PLACEHOLDER at the chain layer; "
                        "Λ = Conjecture 1 (advisory, never proven trust)."),
            "ts": _now_iso(),
        })

    async def _get_run(request):
        run_id = request.path_params.get("run_id")
        run = _STORE.get(run_id)
        if run is None:
            return JSONResponse({"error": "unknown run_id"}, status_code=404)
        return JSONResponse({"run_id": run_id, "goal": run["goal"],
                             "created": run["created"],
                             "cell_count": len(run["cells"]),
                             "final_chain_hash": run["prev_hash"],
                             "cells": run["cells"]})

    async def _get_receipts(request):
        run_id = request.path_params.get("run_id")
        run = _STORE.get(run_id)
        if run is None:
            return JSONResponse({"error": "unknown run_id"}, status_code=404)
        receipts = [c["receipt"] for c in run["cells"]]
        return JSONResponse({"run_id": run_id, "count": len(receipts),
                             "final_chain_hash": run["prev_hash"],
                             "receipts": receipts})

    routes = [
        Route("%s/compose" % base, _compose, methods=["POST"], name="a11oy_code_compose"),
        Route("%s/revise" % base, _revise, methods=["POST"], name="a11oy_code_revise"),
        Route("%s/inspect" % base, _inspect, methods=["POST"], name="a11oy_code_inspect"),
        Route("%s/status" % base, _status, methods=["GET"], name="a11oy_code_status"),
        Route("%s/run/{run_id}" % base, _get_run, methods=["GET"], name="a11oy_code_run"),
        Route("%s/receipts/{run_id}" % base, _get_receipts, methods=["GET"],
              name="a11oy_code_receipts"),
    ]
    # Insert at the FRONT so these beat the SPA /{full_path:path} catch-all.
    for r in reversed(routes):
        app.router.routes.insert(0, r)

    return {"registered": [r.path for r in routes], "signer": signer_label,
            "count": len(routes)}


if __name__ == "__main__":
    # Self-test (no signer): benign persist + malicious DENY.
    rid = _STORE.create("demo")
    c1 = run_cell(rid, "a = np.arange(10)\nprint(int(a.sum()))")
    print("benign cell1:", c1["verdict"], c1["stdout"].strip(), c1["new_or_changed"])
    c2 = run_cell(rid, "b = a[a > 5]\nprint(b.tolist())")
    print("benign cell2 (reuses a):", c2["verdict"], c2["stdout"].strip())
    c3 = run_cell(rid, "import socket\ns = socket.create_connection(('8.8.8.8', 53))")
    print("malicious:", c3["verdict"], "executed=", c3["executed"],
          "findings=", c3["security"]["findings"])
    c4 = run_cell(rid, "import os\nopen('/etc/passwd').read()\nos.environ['HF_TOKEN']")
    print("key/env theft:", c4["verdict"], "executed=", c4["executed"],
          "findings=", c4["security"]["findings"])
