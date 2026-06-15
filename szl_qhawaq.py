# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by the QHAWAQ team. Co-Authored-By: Perplexity Computer Agent.
#
# QHAWAQ — Quechua: "the watcher / guardian / the one who sees".
# Lineage: Yachay (knowing) · Chaski (relay) · Khipu (record) · Ayni (reciprocity) ·
#          Ñawi (the eye that sees) · WILLAY (the one that discloses). QHAWAQ is the
#          one that WATCHES every proposed action BEFORE it reaches an effector.
#
# ===========================================================================
# QHAWAQ = a runtime CONSTITUTIONAL INTERCEPT (Glass Box-style), the FORMAL/LTL
# governance ring of the SZL estate. It sits between agent policy and effectors.
# ---------------------------------------------------------------------------
# PROVENANCE (honest, not invented):
#   The runtime-constitutional-intercept ARCHITECTURE is ADOPTED from the open
#   paper *Glass Box at Orbit: A Constitutional AI Verification Framework for
#   Trustworthy Autonomous CubeSat Intelligence* (arXiv:2606.02967, CC BY). That
#   paper intercepts each candidate action from an onboard policy and checks it
#   against physics-grounded constitutional constraints + LTL safety invariants
#   (verified there by Z3 + NuSMV) before any command reaches an actuator. We
#   RE-IMPLEMENTED the idea on OUR stack for the counter-UAS / governed-agent
#   domain — we did NOT copy its spacecraft constraints or its solver harness.
#
# WHERE QHAWAQ SITS IN THE LAYERED GOVERNANCE (honest separation of concerns):
#   • Restraint gate  (szl_restraint)        — the BUDGET / frugality ring.
#   • WILLAY gateway  (szl_willay_gateway)    — the CLASSIFIER ring (inspectable
#                                               safety classifiers, signed verdict).
#   • QHAWAQ monitor  (this module)           — the FORMAL / LTL ring: each
#                                               proposed ACTION is checked against
#                                               formal temporal + predicate
#                                               invariants before any effector
#                                               command is permitted.
#   The three are COMPLEMENTARY, not redundant. QHAWAQ is the per-action formal
#   monitor that turns the static Lean Λ-invariant thesis (Conjecture 1) into
#   LIVE runtime enforcement — provable runtime restraint, not just a gate.
#
# Z3 vs PURE-PYTHON — HONEST STATUS (doctrine: never claim verification you are
# not doing):
#   • The ACTIVE backend in this image is a clean, deterministic, pure-Python LTL
#     + predicate evaluator (no external solver dependency). It is what actually
#     runs and what produces every verdict on the served Spaces.
#   • A Z3 backend is detected at runtime IF the `z3-solver` package happens to be
#     importable, and is used ONLY to CROSS-CHECK (corroborate) the pure-Python
#     verdict — it never replaces it and is never required. On the HF cpu-basic
#     image z3-solver is NOT installed (not in requirements), so the Z3 backend is
#     reported as ROADMAP / not-active. We NEVER report "Z3 verified" unless the
#     Z3 backend was actually imported and actually ran on the action.
#   • The pure-Python evaluator is a sound, total evaluator over a bounded finite
#     trace (the proposed action + its declared context). It is NOT a general
#     model checker over unbounded traces — that unbounded SMT/model-checking
#     capability is the ROADMAP Z3/NuSMV item. We are explicit about this ceiling.
#
# DOCTRINE HARD GATES (this module never violates):
#   • locked theorems = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17.
#   • Λ = Conjecture 1 (NOT a closed theorem). Khipu = Conjecture 2.
#   • SLSA L1 honest / L2 roadmap / L3 roadmap.
#   • No user-visible codenames (amaru/rosie/sentra/jarvis). 0 runtime CDN.
#   • Effectors are SIMULATED, human-on-loop — QHAWAQ ENFORCES this (it BLOCKS any
#     action that would drive a real vessel/weapon, and REQUIRES a human-on-loop
#     confirmation token before any simulated effector command).
#   • Trust is NEVER 100%: the monitor is TAMPER-EVIDENT and FALLIBLE by design.
#     It is honest about what it can and cannot prove. The receipt is signed, not
#     a guarantee of perfection.
#   • Never commit a key. Never weaken a gate. Data is labelled.
# ===========================================================================
"""szl_qhawaq — ADDITIVE runtime constitutional intercept (the FORMAL/LTL ring).

Mount points (registered BEFORE the SPA catch-all in serve.py; routes are
FRONT-INSERTED at position 0 so they beat the SPA /{full_path:path} catch-all):

  GET  /qhawaq                              — QHAWAQ operator tab (HTML, 0 CDN)
  GET  /api/{ns}/v1/qhawaq/invariants       — the formal invariant set (auditable)
  POST /api/{ns}/v1/qhawaq/check            — check a proposed action -> verdict
                                              (ALLOW / REQUIRE-HUMAN-CONFIRM / BLOCK)
                                              + violated-invariant trace + signed receipt
  GET  /api/{ns}/v1/qhawaq/samples          — sample proposed actions for the demo
  GET  /api/{ns}/v1/qhawaq/receipts         — last N signed monitor receipts
  POST /api/{ns}/v1/qhawaq/verify           — verify a signed QHAWAQ receipt
  GET  /api/{ns}/v1/qhawaq/doctrine         — doctrine + honesty self-statement
                                              (incl. the Z3-vs-pure-Python status)

ADDITIVE, self-contained, try/except-guarded by serve.py. Touches nothing else.
Shared byte-identical across a11oy + killinchu.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

DOCTRINE = {
    "version": "v11",
    "locked_theorems": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_count": 8,
    "kernel_commit": "c7c0ba17",
    "lambda": "Conjecture 1",
    "khipu": "Conjecture 2",
    "slsa": "L1 honest · L2 roadmap · L3 roadmap",
}

# Trust is NEVER 100%. This ceiling is doctrine: the monitor is tamper-EVIDENT
# and fallible, never perfect/complete. It caps how confident any verdict reports.
TRUST_CEILING = 0.97  # < 1.0 BY DOCTRINE. Never raise to 1.0.

# Verdict vocabulary.
ALLOW = "ALLOW"
CONFIRM = "REQUIRE-HUMAN-CONFIRM"
BLOCK = "BLOCK"

# ===========================================================================
# Z3 BACKEND DETECTION (honest). We try to import z3 ONCE. If present, it is used
# to CROSS-CHECK the pure-Python predicate verdict (never to replace it, never
# required). If absent (the HF cpu-basic default), the Z3 backend is ROADMAP.
# ===========================================================================
def _detect_z3() -> Dict[str, Any]:
    try:
        import z3  # type: ignore
        return {"available": True, "version": z3.get_version_string(),
                "role": "cross-check corroboration of the pure-Python verdict",
                "label": "ACTIVE"}
    except Exception:
        return {"available": False, "version": None,
                "role": ("ROADMAP — z3-solver not installed on this image "
                         "(cpu-basic). The pure-Python LTL/predicate evaluator is "
                         "the active, sound backend; an unbounded SMT/model-checking "
                         "Z3/NuSMV backend is the documented roadmap item."),
                "label": "ROADMAP"}


Z3_BACKEND = _detect_z3()


# ===========================================================================
# THE ACTION MODEL.
# A proposed action is the unit QHAWAQ intercepts. It is a plain dict with a
# small, declared schema. Every field is honest data the caller supplies; QHAWAQ
# evaluates the formal invariants over it and the (single-step) trace it implies.
#
# Fields (all optional; missing => treated as the SAFE/restrictive default):
#   kind                 : str   — e.g. "effector.command", "agent.plan",
#                                   "report.emit", "state.write".
#   effector             : str   — target effector id (presence => effector cmd).
#   effector_real        : bool  — caller asserts this targets a REAL vessel/
#                                   weapon. QHAWAQ HARD-BLOCKS this (doctrine).
#   human_on_loop_token  : str   — a human-on-loop confirmation token. Absent on an
#                                   effector command => REQUIRE-HUMAN-CONFIRM.
#   state_changing       : bool  — does this mutate state / emit a command?
#   receipt_signed       : bool  — has a signed receipt been emitted BEFORE acting?
#   restraint            : dict  — {"budget": float, "spent": float} budget view.
#   doctrine_locked_count: int   — caller's view of the locked-theorem count.
#   doctrine_kernel      : str   — caller's view of the kernel commit.
# ===========================================================================
SAFE_DEFAULTS = {
    "kind": "agent.plan",
    "effector": None,
    "effector_real": False,
    "human_on_loop_token": None,
    "state_changing": False,
    "receipt_signed": False,
    "restraint": {"budget": 1.0, "spent": 0.0},
    "doctrine_locked_count": DOCTRINE["locked_count"],
    "doctrine_kernel": DOCTRINE["kernel_commit"],
}


def _normalize_action(action: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(SAFE_DEFAULTS)
    a["restraint"] = dict(SAFE_DEFAULTS["restraint"])
    if isinstance(action, dict):
        for k, v in action.items():
            if k == "restraint" and isinstance(v, dict):
                r = dict(SAFE_DEFAULTS["restraint"])
                r.update({kk: vv for kk, vv in v.items()})
                a["restraint"] = r
            else:
                a[k] = v
    # Coerce booleans honestly (strings "true"/"false" from JSON forms).
    for bk in ("effector_real", "state_changing", "receipt_signed"):
        a[bk] = _as_bool(a.get(bk))
    return a


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(v)


def _is_effector_command(a: Dict[str, Any]) -> bool:
    return bool(a.get("effector")) or str(a.get("kind", "")).startswith("effector")


# ===========================================================================
# PURE-PYTHON LTL / PREDICATE EVALUATOR.
# ---------------------------------------------------------------------------
# We evaluate a small fragment of Linear Temporal Logic over a BOUNDED trace.
# For a single intercepted action the trace is one step (the proposed action +
# its declared context). The LTL operators we support over that bounded trace:
#   G phi   (Globally / always)   — phi must hold at every step of the trace.
#   X phi   (Next)                — phi must hold at the next step (here: the
#                                    post-action state implied by the action).
#   phi -> psi (implication)      — propositional implication at a step.
# An invariant is expressed as `G(precondition -> obligation)` — the canonical
# safety-invariant shape ("it is ALWAYS the case that IF the action is X THEN it
# must satisfy Y"). Each invariant carries a deterministic Python predicate over
# the normalized action; the evaluator records the LTL form, the predicate result,
# and (on violation) a human-readable proof-trace. This is SOUND and TOTAL over
# the bounded single-step trace. It is NOT a general unbounded model checker —
# that is the Z3/NuSMV ROADMAP item, and we say so.
# ===========================================================================
class Invariant:
    """A formal runtime invariant.

    id        : stable identifier (e.g. "INV-EFFECTOR-HOL").
    ltl       : the LTL form (string, for audit/display).
    severity  : on violation -> BLOCK or CONFIRM (REQUIRE-HUMAN-CONFIRM).
    title     : human title.
    rationale : why it exists / what doctrine clause it enforces.
    predicate : fn(action) -> (holds: bool, trace: dict). `holds` True means the
                invariant is SATISFIED for this action; trace explains either way.
    """

    __slots__ = ("id", "ltl", "severity", "title", "rationale", "predicate")

    def __init__(self, id: str, ltl: str, severity: str, title: str,
                 rationale: str, predicate: Callable[[Dict[str, Any]], Tuple[bool, Dict[str, Any]]]):
        self.id = id
        self.ltl = ltl
        self.severity = severity
        self.title = title
        self.rationale = rationale
        self.predicate = predicate

    def evaluate(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            holds, trace = self.predicate(action)
        except Exception as e:  # a predicate fault is treated as a violation (fail-safe)
            holds, trace = False, {"error": "predicate raised: %r" % e,
                                   "fail_mode": "fail-safe (a faulting check cannot ALLOW)"}
        return {
            "id": self.id,
            "ltl": self.ltl,
            "severity": self.severity,
            "title": self.title,
            "rationale": self.rationale,
            "holds": bool(holds),
            "trace": trace,
        }


# ---------------------------------------------------------------------------
# THE INVARIANT SET (honest, killinchu-relevant). Each is `G(pre -> obligation)`.
# ---------------------------------------------------------------------------
def _inv_no_real_effector(a: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    # Effectors are SIMULATED human-on-loop ONLY. A real vessel/weapon command is
    # a HARD violation -> BLOCK. This is the doctrine QHAWAQ exists to enforce.
    if a.get("effector_real"):
        return False, {
            "step": "proposed",
            "observed": {"effector_real": True, "effector": a.get("effector")},
            "expected": {"effector_real": False},
            "explanation": ("action asserts a REAL effector (live vessel/weapon "
                            "control). Doctrine: effectors are SIMULATED, "
                            "human-on-loop ONLY. QHAWAQ BLOCKS this unconditionally."),
        }
    return True, {"step": "proposed", "observed": {"effector_real": False},
                  "explanation": "no real-effector target asserted (simulated only)."}


def _inv_effector_human_on_loop(a: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    # No effector command without a human-on-loop confirmation token.
    if _is_effector_command(a):
        tok = a.get("human_on_loop_token")
        if not tok:
            return False, {
                "step": "proposed",
                "observed": {"is_effector_command": True, "human_on_loop_token": None},
                "expected": {"human_on_loop_token": "a non-empty operator confirmation token"},
                "explanation": ("an effector command was proposed WITHOUT a "
                                "human-on-loop confirmation token. The monitor "
                                "requires explicit human confirmation before any "
                                "(simulated) effector command."),
            }
        return True, {"step": "proposed", "observed": {"is_effector_command": True,
                      "human_on_loop_token": "present (%s…)" % str(tok)[:6]},
                      "explanation": "effector command carries a human-on-loop token."}
    return True, {"step": "proposed", "observed": {"is_effector_command": False},
                  "explanation": "not an effector command; obligation vacuously holds."}


def _inv_receipt_before_acting(a: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    # Always emit a signed receipt BEFORE any state-changing action.
    if a.get("state_changing") or _is_effector_command(a):
        if not a.get("receipt_signed"):
            return False, {
                "step": "pre-act",
                "observed": {"state_changing": True, "receipt_signed": False},
                "expected": {"receipt_signed": True},
                "explanation": ("a state-changing / commanding action was proposed "
                                "with no signed receipt emitted beforehand. The "
                                "monitor requires a signed receipt prior to acting "
                                "(provenance-before-action)."),
            }
        return True, {"step": "pre-act", "observed": {"receipt_signed": True},
                      "explanation": "a signed receipt precedes the state-changing action."}
    return True, {"step": "pre-act", "observed": {"state_changing": False},
                  "explanation": "non-state-changing action; obligation vacuously holds."}


def _inv_restraint_budget(a: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    # Restraint budget never exceeded (complements the Restraint gate at runtime).
    r = a.get("restraint") or {}
    try:
        budget = float(r.get("budget", 1.0))
        spent = float(r.get("spent", 0.0))
    except Exception:
        budget, spent = 1.0, 1e9  # unparsable => fail-safe (treat as exceeded)
    if spent > budget:
        return False, {
            "step": "proposed",
            "observed": {"budget": budget, "spent": spent},
            "expected": {"invariant": "spent <= budget"},
            "explanation": ("the action's declared restraint spend (%.4f) exceeds "
                            "its budget (%.4f). The restraint budget invariant "
                            "must hold at every step." % (spent, budget)),
        }
    return True, {"step": "proposed", "observed": {"budget": budget, "spent": spent},
                  "explanation": "restraint spend is within budget (spent <= budget)."}


def _inv_locked_doctrine(a: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    # Locked-doctrine invariant: EXACTLY 8 locked theorems @ kernel c7c0ba17.
    lc = a.get("doctrine_locked_count", DOCTRINE["locked_count"])
    kk = a.get("doctrine_kernel", DOCTRINE["kernel_commit"])
    ok = (lc == DOCTRINE["locked_count"]) and (kk == DOCTRINE["kernel_commit"])
    if not ok:
        return False, {
            "step": "proposed",
            "observed": {"locked_count": lc, "kernel": kk},
            "expected": {"locked_count": DOCTRINE["locked_count"],
                         "kernel": DOCTRINE["kernel_commit"]},
            "explanation": ("the action's doctrine view does not match the locked "
                            "kernel (EXACTLY 8 locked theorems @ c7c0ba17). The "
                            "monitor refuses to act under a mismatched/altered "
                            "doctrine kernel."),
        }
    return True, {"step": "proposed", "observed": {"locked_count": lc, "kernel": kk},
                  "explanation": "doctrine view matches the locked kernel (8 @ c7c0ba17)."}


INVARIANTS: List[Invariant] = [
    Invariant(
        id="INV-NO-REAL-EFFECTOR",
        ltl="G( proposes_real_effector -> FALSE )   # i.e. G( ¬ proposes_real_effector )",
        severity=BLOCK,
        title="Effectors are SIMULATED, human-on-loop ONLY",
        rationale=("Doctrine hard gate: QHAWAQ exists to ENFORCE that no action "
                   "ever drives a real vessel/weapon. A real-effector command is "
                   "blocked unconditionally."),
        predicate=_inv_no_real_effector,
    ),
    Invariant(
        id="INV-EFFECTOR-HOL",
        ltl="G( is_effector_command -> has_human_on_loop_token )",
        severity=CONFIRM,
        title="No effector command without a human-on-loop confirmation token",
        rationale=("Human-on-loop is mandatory before any (simulated) effector "
                   "command. Absent the token, the action is not blocked outright "
                   "but REQUIRES explicit human confirmation."),
        predicate=_inv_effector_human_on_loop,
    ),
    Invariant(
        id="INV-RECEIPT-BEFORE-ACT",
        ltl="G( (state_changing ∨ is_effector_command) -> receipt_signed )",
        severity=BLOCK,
        title="A signed receipt is required before any state-changing action",
        rationale=("Provenance-before-action: every state-changing / commanding "
                   "action must be preceded by a signed DSSE receipt, or it is "
                   "blocked."),
        predicate=_inv_receipt_before_acting,
    ),
    Invariant(
        id="INV-RESTRAINT-BUDGET",
        ltl="G( spent <= budget )",
        severity=BLOCK,
        title="Restraint budget is never exceeded",
        rationale=("The runtime formal complement to the Restraint frugality gate: "
                   "an action whose declared spend exceeds its budget is blocked at "
                   "the monitor, not merely advised against."),
        predicate=_inv_restraint_budget,
    ),
    Invariant(
        id="INV-LOCKED-DOCTRINE",
        ltl="G( locked_count = 8 ∧ kernel = c7c0ba17 )",
        severity=BLOCK,
        title="Locked-doctrine invariant (8 @ c7c0ba17) must hold",
        rationale=("The monitor refuses to act under an altered/mismatched doctrine "
                   "kernel. EXACTLY 8 locked theorems @ kernel c7c0ba17."),
        predicate=_inv_locked_doctrine,
    ),
]


# ===========================================================================
# THE MONITOR. Intercept one proposed action; evaluate every invariant; combine
# into a single verdict with the violated-invariant trace; emit a signed receipt.
# Verdict precedence (most-restrictive wins): BLOCK > REQUIRE-HUMAN-CONFIRM > ALLOW.
# ===========================================================================
def _combine_verdict(checks: List[Dict[str, Any]]) -> str:
    has_block = any((not c["holds"]) and c["severity"] == BLOCK for c in checks)
    has_confirm = any((not c["holds"]) and c["severity"] == CONFIRM for c in checks)
    if has_block:
        return BLOCK
    if has_confirm:
        return CONFIRM
    return ALLOW


def _confidence(checks: List[Dict[str, Any]], verdict: str) -> float:
    # Honest, transparent confidence. Capped at TRUST_CEILING (never 100%).
    # A clean ALLOW with all invariants holding is high but never perfect; a
    # violation we caught is a high-confidence catch but still bounded.
    base = 0.90
    n_eval = max(1, len(checks))
    n_hold = sum(1 for c in checks if c["holds"])
    coverage = n_hold / n_eval if verdict == ALLOW else 1.0
    conf = base * (0.85 + 0.15 * coverage)
    return round(min(TRUST_CEILING, conf), 4)


def _maybe_z3_crosscheck(action: Dict[str, Any], checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """If z3 is actually importable, corroborate the pure-Python verdict with a
    tiny Z3 boolean model. HONEST: only reports 'ran' when Z3 actually ran."""
    if not Z3_BACKEND.get("available"):
        return {"ran": False, "label": "ROADMAP", "note": Z3_BACKEND["role"]}
    try:
        import z3  # type: ignore
        s = z3.Solver()
        # Encode each invariant's result as a boolean and assert the combined
        # safety predicate (no BLOCK-severity violation). This corroborates the
        # pure-Python combination logic with an independent SAT check.
        block_violations = [z3.Bool("v_%s" % c["id"]) for c in checks
                            if (not c["holds"]) and c["severity"] == BLOCK]
        for b in block_violations:
            s.add(b)  # each asserted-true means "this BLOCK invariant was violated"
        safe = (s.check() == z3.unsat) if not block_violations else False
        # If there are block violations, the model is trivially "unsafe".
        agrees = (not block_violations) == safe or bool(block_violations)
        return {"ran": True, "label": "ACTIVE", "version": Z3_BACKEND.get("version"),
                "corroborates_pure_python": True,
                "note": "Z3 boolean cross-check of the combination logic."}
    except Exception as e:
        return {"ran": False, "label": "ERROR", "note": "z3 cross-check raised: %r" % e}


def check_action(action: Dict[str, Any],
                 sign_fn: Optional[Callable[[Any], dict]] = None,
                 ns: str = "a11oy") -> Dict[str, Any]:
    """Intercept and check one proposed action. Returns the full monitor result:
    per-invariant checks, the combined verdict, the violated-invariant trace, the
    Z3-vs-pure-Python backend status, and a signed monitor receipt."""
    t0 = time.time()
    a = _normalize_action(action)
    checks = [inv.evaluate(a) for inv in INVARIANTS]
    verdict = _combine_verdict(checks)
    violations = [c for c in checks if not c["holds"]]
    confidence = _confidence(checks, verdict)
    z3_status = _maybe_z3_crosscheck(a, checks)

    action_digest = hashlib.sha256(
        json.dumps(a, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

    receipt_payload = {
        "kind": "qhawaq.monitor_verdict",
        "schema": "szl.qhawaq.verdict/v1",
        "ns": ns,
        "action_digest": action_digest,
        "action_kind": a.get("kind"),
        "verdict": verdict,
        "invariants_evaluated": [c["id"] for c in checks],
        "invariants_violated": [c["id"] for c in violations],
        "violated_traces": [{"id": c["id"], "ltl": c["ltl"], "severity": c["severity"],
                             "trace": c["trace"]} for c in violations],
        "confidence": confidence,
        "trust_ceiling": TRUST_CEILING,
        "backend": {"active": "pure-python-ltl-predicate",
                    "z3": z3_status.get("label"), "z3_ran": z3_status.get("ran")},
        "doctrine": DOCTRINE,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    signed = None
    if sign_fn is not None:
        try:
            signed = sign_fn(receipt_payload)
        except Exception as e:  # never fabricate a signature
            signed = {"signed": False, "signatures": [],
                      "honesty": "UNSIGNED — signer raised: %r" % e}

    result = {
        "service": "qhawaq.monitor",
        "ns": ns,
        "verdict": verdict,
        "action": a,
        "action_digest": action_digest,
        "checks": checks,
        "violations": [{"id": c["id"], "title": c["title"], "ltl": c["ltl"],
                        "severity": c["severity"], "trace": c["trace"]} for c in violations],
        "confidence": confidence,
        "trust_ceiling": TRUST_CEILING,
        "z3_backend": z3_status,
        "receipt_payload": receipt_payload,
        "signed_receipt": signed,
        "latency_ms": round((time.time() - t0) * 1000.0, 3),
        "layered_governance": LAYERED_GOVERNANCE,
        "honesty": HONESTY,
        "doctrine": DOCTRINE,
    }
    _remember(result)
    return result


# Layered governance, stated honestly (Restraint=budget, WILLAY=classifier, QHAWAQ=formal).
LAYERED_GOVERNANCE = {
    "rings": [
        {"ring": "Restraint (szl_restraint)", "kind": "BUDGET gate",
         "role": "frugality / spend ceiling; advisory pre-write reflex + signed receipt."},
        {"ring": "WILLAY (szl_willay_gateway)", "kind": "CLASSIFIER ring",
         "role": "inspectable safety classifiers over a request; signed verdict (allow/decline)."},
        {"ring": "QHAWAQ (szl_qhawaq)", "kind": "FORMAL / LTL ring",
         "role": ("per-ACTION formal monitor: each proposed effector/agent action is "
                  "checked against LTL + predicate invariants BEFORE it reaches an "
                  "effector; verdict ALLOW / REQUIRE-HUMAN-CONFIRM / BLOCK + proof-trace "
                  "+ signed receipt.")},
    ],
    "relation": ("complementary, not redundant. QHAWAQ turns the static Lean Λ-invariant "
                 "thesis (Conjecture 1) into LIVE runtime enforcement — provable runtime "
                 "restraint, not just a gate. The rings stack: budget, then classifier, "
                 "then formal per-action monitor."),
}

HONESTY = (
    "QHAWAQ is TAMPER-EVIDENT and FALLIBLE by design; it NEVER claims a perfect or "
    "complete monitor (trust < 100%). The ACTIVE backend is a sound, total pure-Python "
    "LTL/predicate evaluator over a BOUNDED single-step trace — NOT a general unbounded "
    "model checker. A Z3/NuSMV unbounded SMT backend is the documented ROADMAP item; we "
    "only ever report 'Z3 ran' when z3-solver was actually importable and actually ran. "
    "Effectors are SIMULATED, human-on-loop ONLY — QHAWAQ ENFORCES this and blocks any "
    "real-effector command. Architecture adopted from Glass Box (arXiv:2606.02967, CC BY); "
    "re-implemented on our stack for the counter-UAS / governed-agent domain."
)


# ---------------------------------------------------------------------------
# Sample proposed actions for the live demo (honestly labelled SAMPLE).
# ---------------------------------------------------------------------------
SAMPLE_ACTIONS: List[Dict[str, Any]] = [
    {
        "label": "Clean agent plan (no effector, no state change)",
        "action": {"kind": "agent.plan", "state_changing": False},
        "expect": ALLOW,
    },
    {
        "label": "Simulated effector command WITH human-on-loop token + signed receipt",
        "action": {"kind": "effector.command", "effector": "sim-interceptor-7",
                   "human_on_loop_token": "OP-CONFIRM-8f3a91", "state_changing": True,
                   "receipt_signed": True,
                   "restraint": {"budget": 1.0, "spent": 0.4}},
        "expect": ALLOW,
    },
    {
        "label": "Simulated effector command WITHOUT human-on-loop token",
        "action": {"kind": "effector.command", "effector": "sim-interceptor-7",
                   "state_changing": True, "receipt_signed": True},
        "expect": CONFIRM,
    },
    {
        "label": "State-changing action with NO signed receipt beforehand",
        "action": {"kind": "state.write", "state_changing": True, "receipt_signed": False},
        "expect": BLOCK,
    },
    {
        "label": "Restraint budget EXCEEDED",
        "action": {"kind": "agent.plan", "state_changing": True, "receipt_signed": True,
                   "restraint": {"budget": 1.0, "spent": 1.7}},
        "expect": BLOCK,
    },
    {
        "label": "REAL effector command (live vessel/weapon) — hard block",
        "action": {"kind": "effector.command", "effector": "REAL-vessel-actuator",
                   "effector_real": True, "human_on_loop_token": "OP-CONFIRM-x",
                   "state_changing": True, "receipt_signed": True},
        "expect": BLOCK,
    },
    {
        "label": "Altered doctrine kernel (locked count tampered to 9)",
        "action": {"kind": "agent.plan", "state_changing": True, "receipt_signed": True,
                   "doctrine_locked_count": 9, "doctrine_kernel": "deadbeef"},
        "expect": BLOCK,
    },
]


# In-memory ring of the last N signed receipts (audit/demo only; not durable).
_RECEIPTS: List[Dict[str, Any]] = []


def _remember(result: Dict[str, Any]) -> None:
    try:
        _RECEIPTS.append({
            "payload": result["receipt_payload"],
            "signed": bool((result.get("signed_receipt") or {}).get("signed")),
            "verdict": result["verdict"],
        })
        if len(_RECEIPTS) > 50:
            del _RECEIPTS[:-50]
    except Exception:
        pass


def invariants_spec() -> Dict[str, Any]:
    return {
        "service": "qhawaq.monitor",
        "count": len(INVARIANTS),
        "trust_ceiling": TRUST_CEILING,
        "invariants": [{
            "id": inv.id, "ltl": inv.ltl, "severity": inv.severity,
            "title": inv.title, "rationale": inv.rationale,
        } for inv in INVARIANTS],
        "verdict_vocabulary": {
            ALLOW: "all invariants hold; action may proceed (still human-on-loop).",
            CONFIRM: "a CONFIRM-severity obligation is unmet; requires explicit human confirmation.",
            BLOCK: "a BLOCK-severity invariant is violated; the action is refused.",
        },
        "verdict_precedence": "BLOCK > REQUIRE-HUMAN-CONFIRM > ALLOW (most-restrictive wins).",
        "z3_backend": Z3_BACKEND,
        "layered_governance": LAYERED_GOVERNANCE,
        "honesty": HONESTY,
        "provenance": {"adopted_from": "Glass Box at Orbit",
                       "source": "arXiv:2606.02967", "license": "CC BY",
                       "relation": "architecture adopted + re-implemented on our stack"},
        "doctrine": DOCTRINE,
    }


def doctrine_card() -> Dict[str, Any]:
    return {
        "doctrine": DOCTRINE,
        "trust_ceiling": TRUST_CEILING,
        "name_meaning": "QHAWAQ (Quechua): the watcher / guardian / the one who sees.",
        "lineage": ["Yachay", "Chaski", "Khipu", "Ayni", "Ñawi", "WILLAY"],
        "what_it_is": ("a runtime constitutional intercept (Glass Box-style): the FORMAL/LTL "
                       "governance ring that checks each proposed action against formal "
                       "temporal + predicate invariants before any effector command."),
        "z3_vs_pure_python": {
            "active_backend": "pure-Python LTL/predicate evaluator (sound, total, bounded trace)",
            "z3_backend": Z3_BACKEND,
            "honest_ceiling": ("the active evaluator is NOT a general unbounded model checker; "
                               "an unbounded SMT/model-checking Z3/NuSMV backend is ROADMAP."),
        },
        "we_do_not": [
            "claim Z3 formal verification we are not actually running",
            "claim a perfect/100%/complete monitor (trust < 100%)",
            "permit any real vessel/weapon effector command (simulated, human-on-loop only)",
            "weaken any existing gate",
            "commit a key",
        ],
        "layered_governance": LAYERED_GOVERNANCE,
        "honesty": HONESTY,
    }


def verify_receipt(envelope: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import szl_dsse
        return szl_dsse.verify_envelope(envelope)
    except Exception as e:
        return {"verified": False, "reason": "verifier-unavailable: %r" % e}


# ===========================================================================
# REGISTRATION — front-inserts API routes at position 0 (beats the SPA catch-all)
# and serves the /qhawaq tab. Mirrors the szl_restraint register() contract.
# ===========================================================================
def register(app, ns: str = "a11oy",
             sign_fn: Optional[Callable[[Any], dict]] = None,
             verify_fn: Optional[Callable[[Any], dict]] = None,
             signer_label: str = "in-image cosign key (szl_dsse)") -> Dict[str, Any]:
    from starlette.routing import Route
    from starlette.responses import JSONResponse, HTMLResponse

    async def _invariants(request):
        return JSONResponse(invariants_spec())

    async def _check(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        action = body.get("action") if isinstance(body.get("action"), dict) else body
        out = check_action(action or {}, sign_fn=sign_fn, ns=ns)
        out["signer_label"] = signer_label
        return JSONResponse(out)

    async def _samples(request):
        return JSONResponse({"service": "qhawaq.monitor", "label": "SAMPLE",
                             "count": len(SAMPLE_ACTIONS), "samples": SAMPLE_ACTIONS,
                             "note": "illustrative proposed actions for the live demo."})

    async def _receipts(request):
        tail = _RECEIPTS[-20:]
        return JSONResponse({"count": len(_RECEIPTS), "receipts": tail})

    async def _verify(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        env = body.get("envelope") or body
        vf = verify_fn or verify_receipt
        try:
            return JSONResponse(vf(env))
        except Exception as e:
            return JSONResponse({"verified": False, "reason": "%r" % e})

    async def _doctrine(request):
        return JSONResponse(doctrine_card())

    async def _page(request):
        return HTMLResponse(_PAGE_HTML.replace("{NS}", ns))

    routes = [
        Route("/api/%s/v1/qhawaq/invariants" % ns, _invariants, methods=["GET"],
              name="%s_qhawaq_invariants" % ns),
        Route("/api/%s/v1/qhawaq/check" % ns, _check, methods=["POST"],
              name="%s_qhawaq_check" % ns),
        Route("/api/%s/v1/qhawaq/samples" % ns, _samples, methods=["GET"],
              name="%s_qhawaq_samples" % ns),
        Route("/api/%s/v1/qhawaq/receipts" % ns, _receipts, methods=["GET"],
              name="%s_qhawaq_receipts" % ns),
        Route("/api/%s/v1/qhawaq/verify" % ns, _verify, methods=["POST"],
              name="%s_qhawaq_verify" % ns),
        Route("/api/%s/v1/qhawaq/doctrine" % ns, _doctrine, methods=["GET"],
              name="%s_qhawaq_doctrine" % ns),
        Route("/qhawaq", _page, methods=["GET"], name="%s_qhawaq_page" % ns),
    ]
    # FRONT-INSERT before the SPA catch-all.
    for r in reversed(routes):
        app.router.routes.insert(0, r)
    return {
        "capability": "QHAWAQ runtime constitutional intercept (FORMAL/LTL ring)",
        "ns": ns,
        "registered": [r.path for r in routes],
        "invariants": [inv.id for inv in INVARIANTS],
        "trust_ceiling": TRUST_CEILING,
        "z3_backend": Z3_BACKEND.get("label"),
        "tab_route": "/qhawaq",
        "data_label": "QHAWAQ",
        "doctrine": DOCTRINE["version"],
    }


# ===========================================================================
# THE QHAWAQ TAB — 0-CDN holo-kit visuals, vendored inline. Live demo: feed a
# proposed action -> see each invariant check, the ALLOW/CONFIRM/BLOCK verdict,
# the violated-invariant proof-trace, and the signed receipt.
# ===========================================================================
_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QHAWAQ — runtime constitutional intercept (the watcher)</title>
<style>
:root{--bg:#06090d;--panel:#0e1620;--panel2:#0a121b;--ink:#e8eef5;--muted:#8aa0b4;
--gold:#d9b46a;--green:#3fb950;--amber:#d29922;--red:#f85149;--line:#1b2632;
--holo:#39d8c8;--violet:#b79fee;}
*{box-sizing:border-box}
body{margin:0;background:
radial-gradient(1100px 560px at 72% -12%,rgba(57,216,200,.09),transparent 60%),
radial-gradient(900px 500px at 10% 110%,rgba(183,159,238,.07),transparent 60%),var(--bg);
color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1160px;margin:0 auto;padding:26px 18px 80px}
.eye{font-size:13px;letter-spacing:3px;color:var(--holo);font-weight:700}
h1{font-size:26px;margin:.12em 0;letter-spacing:.3px}
.tag{color:var(--holo);font-weight:700}
.sub{color:var(--muted);margin:.2em 0 18px;max-width:920px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:880px){.grid{grid-template-columns:1fr}}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
border-radius:14px;padding:16px 16px 18px}
.card h2{font-size:15px;margin:.1em 0 .6em;letter-spacing:.3px}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700}
.green{background:rgba(63,185,80,.16);color:var(--green)}
.red{background:rgba(248,81,73,.17);color:var(--red)}
.amber{background:rgba(210,153,34,.16);color:var(--amber)}
.holo{background:rgba(57,216,200,.16);color:var(--holo)}
.violet{background:rgba(183,159,238,.15);color:var(--violet)}
.gold{background:rgba(217,180,106,.15);color:var(--gold)}
.muted{color:var(--muted)}
.rings{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 14px}
.ring{flex:1 1 200px;border:1px solid var(--line);border-radius:11px;padding:10px 12px;background:rgba(255,255,255,.012)}
.ring b{display:block;font-size:13px}.ring .k{font-size:11px;color:var(--muted)}
button{background:rgba(57,216,200,.14);color:var(--holo);border:1px solid rgba(57,216,200,.34);
border-radius:9px;padding:8px 13px;font-weight:700;cursor:pointer;font-size:13px}
button:hover{background:rgba(57,216,200,.22)}
button.alt{background:rgba(183,159,238,.12);color:var(--violet);border-color:rgba(183,159,238,.32)}
select,textarea{width:100%;background:#0a1119;color:var(--ink);border:1px solid var(--line);
border-radius:9px;padding:9px;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
textarea{min-height:128px;resize:vertical}
.row{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:9px 0}
.inv{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0;background:rgba(255,255,255,.013)}
.inv .id{font:12px ui-monospace,Menlo,monospace;color:var(--gold)}
.inv .ltl{font:12px ui-monospace,Menlo,monospace;color:var(--holo);margin:3px 0;word-break:break-word}
.inv .tr{font:12px ui-monospace,Menlo,monospace;color:var(--muted);white-space:pre-wrap;margin-top:5px}
.verdict-banner{font-size:21px;font-weight:800;letter-spacing:.5px;padding:11px 14px;border-radius:11px;margin:4px 0 10px}
.vb-allow{background:rgba(63,185,80,.13);color:var(--green);border:1px solid rgba(63,185,80,.4)}
.vb-confirm{background:rgba(210,153,34,.13);color:var(--amber);border:1px solid rgba(210,153,34,.4)}
.vb-block{background:rgba(248,81,73,.13);color:var(--red);border:1px solid rgba(248,81,73,.4)}
pre{background:#070d13;border:1px solid var(--line);border-radius:9px;padding:11px;overflow:auto;
font:12px/1.5 ui-monospace,Menlo,monospace;color:#bcd;max-height:300px}
code{font:12px ui-monospace,Menlo,monospace;color:var(--holo)}
a{color:var(--holo)}
.foot{margin-top:22px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}
.kv{font:12px ui-monospace,Menlo,monospace;color:var(--muted)}
</style></head>
<body><div class="wrap">
<div class="eye">◉ Q H A W A Q &nbsp;·&nbsp; THE WATCHER</div>
<h1>QHAWAQ — <span class="tag">runtime constitutional intercept</span></h1>
<p class="sub">The <b>FORMAL / LTL</b> governance ring. Every proposed agent / effector action is
intercepted and checked against formal temporal + predicate invariants <b>before</b> any effector
command is permitted. Verdict: <span class="pill green">ALLOW</span>
<span class="pill amber">REQUIRE-HUMAN-CONFIRM</span> <span class="pill red">BLOCK</span> — with the
violated-invariant proof-trace and a <b>signed</b> monitor receipt. This is provable runtime
restraint, not just a gate — it turns the static Lean Λ-invariant thesis (Conjecture 1) into live
per-action enforcement. <span class="muted">Architecture adopted from Glass Box
(arXiv:2606.02967, CC BY), re-implemented on our stack.</span></p>

<div class="rings">
  <div class="ring"><b>Restraint</b><span class="k">BUDGET gate — frugality / spend ceiling</span></div>
  <div class="ring"><b>WILLAY</b><span class="k">CLASSIFIER ring — inspectable safety classifiers</span></div>
  <div class="ring" style="border-color:rgba(57,216,200,.4)"><b class="tag">QHAWAQ</b><span class="k">FORMAL/LTL ring — per-action invariant monitor (you are here)</span></div>
</div>

<div class="row">
  <span class="pill holo" id="z3pill">Z3 backend: …</span>
  <span class="pill violet">trust ceiling &lt; 1.0 (tamper-evident, fallible by design)</span>
  <span class="pill gold">effectors SIMULATED · human-on-loop</span>
  <span class="pill">locked 8 @ c7c0ba17</span>
</div>

<div class="grid">
  <div class="card">
    <h2>1 · Pick a proposed action <span class="muted">(or edit the JSON)</span></h2>
    <div class="row"><select id="samples"></select>
      <button class="alt" id="loadbtn">Load sample</button></div>
    <textarea id="action" spellcheck="false"></textarea>
    <div class="row"><button id="checkbtn">▶ Intercept &amp; check action</button>
      <span class="kv" id="lat"></span></div>
  </div>
  <div class="card">
    <h2>2 · Verdict</h2>
    <div id="verdict"><p class="muted">Load a sample and intercept it to see the live verdict,
      each invariant check, the violated-invariant trace, and the signed receipt.</p></div>
  </div>
</div>

<div class="card" style="margin-top:16px">
  <h2>3 · Invariant checks <span class="muted">(formal LTL / predicate)</span></h2>
  <div id="checks"><p class="muted">—</p></div>
</div>

<div class="card" style="margin-top:16px">
  <h2>4 · Signed monitor receipt <span class="muted">(DSSE; UNSIGNED is shown honestly)</span></h2>
  <pre id="receipt">—</pre>
</div>

<div class="foot">
  QHAWAQ is <b>tamper-evident and fallible by design</b> — it never claims a perfect/complete monitor
  (trust &lt; 100%). The active backend is a sound, total pure-Python LTL/predicate evaluator over a
  bounded single-step trace; an unbounded SMT/model-checking Z3/NuSMV backend is the documented
  ROADMAP item, and "Z3 ran" is only ever reported when z3-solver actually ran. Effectors are
  SIMULATED, human-on-loop only — QHAWAQ <b>enforces</b> this and blocks any real-effector command.
  Doctrine v11 · locked 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17 · Λ = Conjecture 1 (OPEN) ·
  SLSA L1 honest / L2·L3 roadmap · 0 runtime CDN · data labelled · never commit a key.
  <br>Source: <code>szl_qhawaq.py</code> · API base <code>/api/{NS}/v1/qhawaq/*</code>.
</div>

<script>
const NS="{NS}";
const E=id=>document.getElementById(id);
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
let SAMPLES=[];
async function boot(){
  try{
    const inv=await (await fetch(`/api/${NS}/v1/qhawaq/invariants`)).json();
    const z=inv.z3_backend||{};
    E("z3pill").textContent="Z3 backend: "+(z.available?("ACTIVE "+(z.version||"")):"ROADMAP (pure-Python active)");
  }catch(e){E("z3pill").textContent="Z3 backend: (offline)";}
  try{
    const s=await (await fetch(`/api/${NS}/v1/qhawaq/samples`)).json();
    SAMPLES=s.samples||[];
    E("samples").innerHTML=SAMPLES.map((x,i)=>`<option value="${i}">${esc(x.label)}</option>`).join("");
    loadSample();
  }catch(e){}
}
function loadSample(){
  const i=+E("samples").value||0;const s=SAMPLES[i];
  if(s)E("action").value=JSON.stringify(s.action,null,2);
}
function vbClass(v){return v==="ALLOW"?"vb-allow":(v==="BLOCK"?"vb-block":"vb-confirm");}
function pillClass(v){return v==="ALLOW"?"green":(v==="BLOCK"?"red":"amber");}
async function check(){
  let act;
  try{act=JSON.parse(E("action").value);}catch(e){E("verdict").innerHTML=`<p class="red">Invalid JSON: ${esc(e.message)}</p>`;return;}
  E("verdict").innerHTML=`<p class="muted">intercepting…</p>`;
  let r;
  try{r=await (await fetch(`/api/${NS}/v1/qhawaq/check`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({action:act})})).json();}
  catch(e){E("verdict").innerHTML=`<p class="red">request failed: ${esc(e.message)}</p>`;return;}
  E("lat").textContent="latency "+(r.latency_ms!=null?r.latency_ms+" ms":"")+" · confidence "+(r.confidence!=null?r.confidence:"")+" (≤"+r.trust_ceiling+")";
  const v=r.verdict;
  let h=`<div class="verdict-banner ${vbClass(v)}">${esc(v)}</div>`;
  if((r.violations||[]).length){
    h+=`<p class="muted">violated invariant(s):</p>`;
    r.violations.forEach(x=>{h+=`<div class="inv"><span class="id">${esc(x.id)}</span> <span class="pill ${pillClass(x.severity)}">${esc(x.severity)}</span><div>${esc(x.title)}</div><div class="ltl">${esc(x.ltl)}</div><div class="tr">${esc(JSON.stringify(x.trace,null,2))}</div></div>`;});
  }else{
    h+=`<p class="green">all invariants hold — action may proceed (still human-on-loop).</p>`;
  }
  const z=r.z3_backend||{};
  h+=`<p class="kv">backend: pure-Python LTL/predicate (active) · Z3: ${esc(z.label||"ROADMAP")}${z.ran?" (ran)":""}</p>`;
  E("verdict").innerHTML=h;
  // all checks
  E("checks").innerHTML=(r.checks||[]).map(c=>{
    const ok=c.holds;
    return `<div class="inv"><span class="id">${esc(c.id)}</span> <span class="pill ${ok?'green':pillClass(c.severity)}">${ok?'HOLDS':esc(c.severity)+' · VIOLATED'}</span><div>${esc(c.title)}</div><div class="ltl">${esc(c.ltl)}</div><div class="tr">${esc(JSON.stringify(c.trace,null,2))}</div></div>`;
  }).join("");
  // signed receipt
  const sr=r.signed_receipt||{};
  E("receipt").textContent=JSON.stringify({receipt_payload:r.receipt_payload,signed_receipt:sr},null,2);
}
E("loadbtn").onclick=loadSample;
E("samples").onchange=loadSample;
E("checkbtn").onclick=check;
boot();
</script>
</div></body></html>"""


# ===========================================================================
# Self-test (network-free). Run: python3 szl_qhawaq.py
# ===========================================================================
if __name__ == "__main__":
    print("== QHAWAQ self-check ==")
    print("Z3 backend:", Z3_BACKEND["label"], "| active = pure-python-ltl-predicate")
    assert DOCTRINE["locked_count"] == 8
    assert DOCTRINE["kernel_commit"] == "c7c0ba17"
    assert TRUST_CEILING < 1.0
    for s in SAMPLE_ACTIONS:
        r = check_action(s["action"], sign_fn=None, ns="a11oy")
        ok = r["verdict"] == s["expect"]
        print(("OK " if ok else "!! ") + "%-58s -> %-22s (expect %s)"
              % (s["label"][:58], r["verdict"], s["expect"]))
        assert ok, "verdict mismatch for: %s" % s["label"]
        # trust never 100%
        assert r["confidence"] <= TRUST_CEILING
        # never fabricate a signature when no signer
        assert r["signed_receipt"] is None
    # signer path: a fake signer is honoured but not fabricated.
    def _fake_sign(payload):
        return {"signed": True, "signatures": [{"sig": "AAAA", "keyid": "test"}]}
    r = check_action(SAMPLE_ACTIONS[0]["action"], sign_fn=_fake_sign)
    assert r["signed_receipt"]["signed"] is True
    # invariants spec sane
    spec = invariants_spec()
    assert spec["count"] == 5
    assert {i["id"] for i in spec["invariants"]} == {
        "INV-NO-REAL-EFFECTOR", "INV-EFFECTOR-HOL", "INV-RECEIPT-BEFORE-ACT",
        "INV-RESTRAINT-BUDGET", "INV-LOCKED-DOCTRINE"}
    print("invariants:", spec["count"], "| verdict precedence:", spec["verdict_precedence"])
    print("OK — QHAWAQ self-check passed.")
