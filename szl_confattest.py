# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# Authored by Wave-S Dev 3 (Governance frontier — confidential-compute attestation +
#   govern-agent-ACTIONS-not-reasoning action gate).
"""szl_confattest.py — CONFIDENTIAL-COMPUTE ATTESTATION + ACTION-GATE (surface `confattest`)

WHAT THIS IS
------------
A governance-native surface that fits SZL's receipt/doctrine spine and models BOTH halves of
the 2026 confidential-agent story:

  (a) CONFIDENTIAL-COMPUTE ATTESTATION — a CPU-TEE + confidential-GPU **enclave attestation
      quote** (Intel-TDX MRTD / AMD-SEV-SNP REPORT_DATA / NVIDIA-CC EAT claim shape) bound to a
      workload measurement, chained into a content-addressed **receipt**. The enclave quote is
      **SIMULATED** — there is NO real TEE, NO real enclave, NO DCAP/KDS/NRAS network call. Every
      value is SHA-256/384-derived from the inputs so the flow is replayable, NOT fabricated as a
      live hardware measurement. Label honestly **MODELED** (quote SIMULATED).

  (b) GOVERN AGENT **ACTIONS**, NOT REASONING — a deterministic **action gate** that ALLOWs or
      HOLDs an agent action at the boundary where it would produce a side effect. Governance is
      applied to the ACTION (its effect, reversibility, authority + the attested enclave quote as
      an independent precondition), NEVER to the agent's plan/reasoning. Λ is an **advisory** axis
      only (Conjecture 1 — never "green"/"proven"). Deny-by-default: an action clears only when a
      deterministic policy AND its attested preconditions pass; Λ can lower a verdict to HOLD but
      a passing Λ never, on its own, "proves" ALLOW. Emits an honest verdict + a receipt.

Both endpoints are pure READS (GET): receipt-on-WRITE, never on-read (doctrine v11). The chain to
`szl_dsse` / `szl_durable_ledger` is GUARDED and READ-ONLY — it reports whether a signing key /
durable ledger is available (advisory) and NEVER signs or writes on the GET.

    GET /api/a11oy/v1/confattest/quote?seed=<int>&workload=<id>
    GET /api/a11oy/v1/confattest/gate?seed=<int>&action=<id>&effect=<class>&reversible=<0|1>

HONESTY (Doctrine v11 — NEVER violate)
--------------------------------------
Label = **MODELED**; the enclave attestation quote is **SIMULATED** (no real TEE/enclave, no
DCAP/KDS/NRAS call). The receipt is honestly **UNSIGNED-LOCAL** on this read path (real DSSE
co-signing happens on WRITE in-Space, never on a GET). Λ = **Conjecture 1** (advisory, gray —
never a theorem, never "green"). Trust ceiling 0.97. The action gate is a governance ADVISORY: a
HOLD is a safe default, an ALLOW is never a proof of safety. Nothing here touches the locked-8
{F1,F4,F7,F11,F12,F18,F19,F22}. Distinct from attestinfer / pcai / cryptopipeline (inference /
lifecycle transcript); this surface governs the ACTION boundary.

LEADERS STUDIED & CITED (clean-room PATTERN, not their code; ids verified before citing)
----------------------------------------------------------------------------------------
  • "Governing Actions, Not Agents: Institutional Attestation as a Governance Model for
    Autonomous AI Systems" — arXiv:2606.26298. Governance at the point of ACTION (irreversible
    side effect), not the reasoning; an action is permitted only when each precondition is
    attested by an independent authority, bound to the intent, and evaluated by a deterministic
    policy. This surface's gate is a direct clean-room realization of that model.
  • "Parallax: Why AI Agents That Think Must Never Act" — arXiv:2604.12986. Cognitive/executive
    separation + reversible execution: prompt-based safety is architecturally insufficient for
    agents with execution capability; govern at the architectural boundary, not the prompt.
  • "EnclaveX: End-to-End Confidential AI with CPU/GPU TEEs" — arXiv:2606.31408. Remote
    attestation across an Intel-TDX CPU TEE + NVIDIA confidential GPU; the enclave quote binds the
    loaded code measurement. Our SIMULATED quote mirrors that CPU-TEE + confidential-GPU shape.
  • "OpenPCC: Open and Confidential LLM Serving on Commodity TEEs" — arXiv:2606.11145. Confidential
    LLM serving on commodity TEEs (the confidential-compute-for-inference context).
  • OPAQUE 3.0 — Agent Governance Toolkit with verifiable identity + confidential execution
    (industry announcement, PR Newswire 2026; NO arXiv id — cited by title + venue, not invented).
    Every AI action executes under hardware-enforced governance producing a signed receipt an
    auditor can check independently — the receipt-on-action discipline this surface mirrors.

ENDPOINTS
---------
  GET /confattest/quote → {label:"MODELED", quote{SIMULATED enclave quote}, lambda{...},
                           receipt{UNSIGNED-LOCAL}, spine{dsse,ledger,signed_on_read:false},
                           honest_note, sources[]}
  GET /confattest/gate  → {label:"MODELED", governs, action{...}, policy{...}, lambda{...},
                           verdict:"ALLOW"|"HOLD", receipt{...}, spine{...}, honest_note, sources[]}
"""

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LABEL = "MODELED"
NS_DEFAULT = "a11oy"
TRUST_CEIL = 0.97          # doctrine v11 trust ceiling — Λ never claims 100%
LAMBDA_FLOOR = 0.90        # advisory Λ floor (mirror szl_org_lambda family)

# Canonical trust axes (mirror szl_proof_carrying_infer / szl_org_lambda).
_AXIS_NAMES = [
    "soundness", "calibration", "robustness", "provenance", "consent", "reversibility",
    "transparency", "fairness", "containment", "attestation", "freshness", "authority",
    "auditability",
]
_AXIS_WEIGHTS = [0.12, 0.06, 0.08, 0.11, 0.06, 0.07, 0.07, 0.05, 0.08, 0.10, 0.05, 0.07, 0.08]

# Effect classes an agent ACTION may fall in, ordered by escalating side-effect severity.
# Deny-by-default: only the reversible/low-severity classes clear on policy alone; a
# destructive/irreversible effect additionally requires elevated authority AND a good attestation.
_EFFECT_CLASSES = ["read", "write", "network", "spend", "destructive"]
_IRREVERSIBLE_BY_DEFAULT = {"spend", "destructive"}

# Sources — verified (arXiv ids resolved to their exact titles before citing); OPAQUE 3.0 has
# NO arXiv id and is cited by title + venue honestly, never with an invented id.
SOURCES: List[Dict[str, str]] = [
    {"name": "Governing Actions, Not Agents: Institutional Attestation as a Governance Model "
             "for Autonomous AI Systems (arXiv:2606.26298)",
     "url": "https://arxiv.org/abs/2606.26298"},
    {"name": "Parallax: Why AI Agents That Think Must Never Act (arXiv:2604.12986)",
     "url": "https://arxiv.org/abs/2604.12986"},
    {"name": "EnclaveX: End-to-End Confidential AI with CPU/GPU TEEs (arXiv:2606.31408)",
     "url": "https://arxiv.org/abs/2606.31408"},
    {"name": "OpenPCC: Open and Confidential LLM Serving on Commodity TEEs (arXiv:2606.11145)",
     "url": "https://arxiv.org/abs/2606.11145"},
    {"name": "OPAQUE 3.0 — Agent Governance Toolkit with Verifiable Identity + confidential "
             "execution (industry announcement, PR Newswire 2026; no arXiv id)",
     "url": "https://www.prnewswire.com/news-releases/opaque-extends-the-agent-governance-toolkit-"
            "with-verifiable-identity-and-first-ever-verifiably-governed-and-secure-mcp-302806751.html"},
]

HONEST_NOTE = (
    "MODELED — the confidential-compute enclave attestation quote is SIMULATED: there is NO real "
    "TEE, NO real enclave, and NO DCAP/KDS/NRAS network call. Quote values are SHA-256/384 of the "
    "inputs (replayable, NOT a live hardware measurement) and NEVER claim a real TEE. The receipt "
    "is UNSIGNED-LOCAL on this read path — real DSSE co-signing happens on WRITE in-Space, never "
    "on a GET (receipt-on-write, not on-read). The action gate GOVERNS THE ACTION EFFECT, NOT the "
    "agent's reasoning/plan; it is deny-by-default and Λ-ADVISORY: a HOLD is a safe default and an "
    "ALLOW is never a proof of safety. Λ = Conjecture 1 (advisory, gray, never green/proven); "
    "trust ceiling 0.97. Adds nothing to the locked-8."
)

DOCTRINE = {
    "locked_proven": 8,
    "lambda": "Conjecture 1 (advisory, NOT a theorem; never green/proven)",
    "khipu_bft": "Conjecture 2",
    "trust_ceiling": TRUST_CEIL,
    "receipt_on_write_not_read": True,
    "governs": "agent ACTION effect boundary — NOT the reasoning/plan",
}


# ---------------------------------------------------------------------------
# deterministic helpers (stdlib only, no RNG — everything replayable)
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha384(b: bytes) -> str:
    return hashlib.sha384(b).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(max(x, lo), hi)


def _det_unit(*parts: str) -> float:
    """Deterministic float in [0,1] from SHA-256 of the parts (replayable, no RNG)."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return _clamp(int.from_bytes(h[:8], "big") / float(1 << 64))


def _weighted_geomean(axes: List[float], weights: List[float]) -> float:
    """A4 zero-absorption weighted geometric mean. Any zero axis → 0.0. Λ ∈ [0,1]."""
    if not axes:
        return 0.0
    sw = sum(weights) or 1.0
    w = [x / sw for x in weights]
    acc = 0.0
    for x, wi in zip(axes, w):
        x = _clamp(float(x))
        if x <= 0.0:
            return 0.0
        acc += wi * math.log(x)
    return _clamp(math.exp(acc))


# ---------------------------------------------------------------------------
# Λ advisory — weighted geomean over the 13 trust axes (Conjecture 1)
# ---------------------------------------------------------------------------
def _lambda_axes(seed: int, subject: str, quote_digest: str, attested: bool,
                 reversible: bool = True) -> Dict[str, Any]:
    """Deterministic per-axis advisory trust in [0,1] from (seed, subject, quote).

    The `attestation` axis is HARD-COUPLED to the enclave quote result and the `reversibility`
    axis to the action's reversibility: a bad attestation or an irreversible effect collapses
    the coupled axis to 0 and A4 zero-absorption pulls Λ to 0 (advisory HOLD). Λ = Conjecture 1
    — advisory only, never a theorem, never green/proven.
    """
    s = str(seed)
    scores: Dict[str, float] = {}
    for name in _AXIS_NAMES:
        base = 0.90 + 0.09 * _det_unit(s, subject, quote_digest, name)   # in [0.90, 0.99]
        scores[name] = _clamp(base, 0.0, TRUST_CEIL)                     # trust ceiling 0.97
    if not attested:
        scores["attestation"] = 0.0    # zero-absorption → Λ = 0 → advisory HOLD
    if not reversible:
        scores["reversibility"] = 0.0  # irreversible side effect → advisory HOLD
    axes = [scores[n] for n in _AXIS_NAMES]
    L = _weighted_geomean(axes, _AXIS_WEIGHTS)
    return {
        "trust_axes": len(_AXIS_NAMES),
        "axes": [{"name": n, "score": round(scores[n], 4), "weight": _AXIS_WEIGHTS[i]}
                 for i, n in enumerate(_AXIS_NAMES)],
        "value": round(L, 6),
        "floor": LAMBDA_FLOOR,
        "advisory_pass": bool(L >= LAMBDA_FLOOR),
        "aggregator": "weighted geometric mean (F19 family), A4 zero-absorption, ceiling 0.97",
        "uniqueness": "Λ = Conjecture 1 (advisory, gray — NOT a theorem, never green/proven); "
                      "nothing to locked-8.",
    }


# ---------------------------------------------------------------------------
# (a) SIMULATED confidential-compute enclave attestation quote
# ---------------------------------------------------------------------------
def _tee_probe() -> Dict[str, Any]:
    """Defer to a real TEE probe if present; surface its honest label verbatim. Never fabricates."""
    try:
        import szl_tee_attest  # per-file COPY'd, guarded import
        return szl_tee_attest.get_tee_attestation()
    except Exception as e:  # pragma: no cover — additive, never breaks the request
        return {
            "present": False,
            "label": "UNAVAILABLE",
            "note": f"szl_tee_attest unavailable in this runtime ({type(e).__name__}); no TEE "
                    "probe performed; no measurement fabricated.",
        }


def build_quote(seed: int = 42, workload: str = "szl-agent-workload") -> Dict[str, Any]:
    """Build a SIMULATED confidential-compute enclave attestation quote bound to a workload
    measurement, chained into a content-addressed receipt. NEVER a real TEE.

    Shape mirrors the leaders' claim sets (Intel TDX MRTD + AMD SEV-SNP REPORT_DATA + NVIDIA
    confidential-GPU EAT): a fresh nonce, an overall attestation result, a per-enclave workload
    measurement digest, secure-boot + RIM-validation flags. Even seed → golden measurement match
    (attested); odd seed → SIMULATED measurement mismatch (attestation fails, honest).
    """
    seed = int(seed) & 0xFFFFFFFF
    workload = str(workload or "szl-agent-workload")

    # measured-boot / enclave-launch chain (SHA-384 stage fold; SIMULATED, not a real quote)
    stages = ["cpu-tee-launch", "enclave-image", "gpu-cc-mode", "runtime-loader", "workload-code"]
    acc = _sha384(f"szl-confattest-enclave|{workload}|seed={seed}".encode("utf-8"))
    enclave_identity = acc
    chain: List[Dict[str, str]] = []
    for stg in stages:
        m = _sha384(f"{stg}|{workload}|seed={seed}".encode("utf-8"))
        acc = _sha384(f"{acc}|{stg}:{m}".encode("utf-8"))
        chain.append({"stage": stg, "digest": acc})
    mrtd = acc                                              # Intel TDX MRTD analogue
    golden_match = (seed % 2 == 0)                          # even → attested, odd → SIMULATED tamper

    workload_measurement = _sha256(f"submod|{workload}|{mrtd}".encode("utf-8"))
    nonce = _sha256(f"nonce|{seed}|{workload}".encode("utf-8"))     # NRAS eat_nonce analogue
    report_data = _sha384(f"REPORT_DATA|{workload}|{mrtd}".encode("utf-8"))  # SEV-SNP bind

    eat_claims = {
        "iss": "SIMULATED://a-11-oy.com/confattest (no real enclave / NRAS / KDS / DCAP)",
        "sub": "SIMULATED-ENCLAVE-ATTESTATION",
        "eat_nonce": nonce,
        "overall_att_result": bool(golden_match),
        "secboot": bool(golden_match),
        "rim_schema_validated": bool(golden_match),
        "cpu_tee": "Intel-TDX (SIMULATED MRTD)",
        "confidential_gpu": "NVIDIA-CC (SIMULATED EAT)",
        "submods": {"ENCLAVE-0": ["DIGEST", ["SHA-256", workload_measurement]]},
        "mrtd": mrtd,
        "report_data": report_data,
    }
    quote_body = {
        "tee_family": "SIMULATED-CC (Intel-TDX + NVIDIA-CC shape)",
        "cc_mode": "ON (SIMULATED)",
        "nonce": nonce,
        "eat_claims": eat_claims,
        "enclave_launch_stages": [c["stage"] for c in chain],
        "verifier": "SIMULATED (no AMD KDS / NVIDIA NRAS / Intel DCAP network call performed)",
    }
    quote_digest = _sha384(_canon(quote_body))

    quote = {
        "label": LABEL,
        "simulated": True,
        "enclave_identity": enclave_identity,
        "measurement_chain": chain,
        "mrtd": mrtd,
        "quote_body": quote_body,
        "quote_digest": quote_digest,
        "nonce": nonce,
        "overall_att_result": bool(golden_match),
        "attested": bool(golden_match),
        "tee_probe": _tee_probe(),  # real probe label surfaced verbatim (MEASURED/UNAVAILABLE)
        "leaders_pattern": "Intel TDX MRTD · AMD SEV-SNP REPORT_DATA · NVIDIA confidential-GPU EAT "
                           "(nonce / overall-result / submod-digest / secboot)",
        "verified_against": "SIMULATED golden reference (no DCAP/KDS/NRAS verifier contacted)",
        "honesty": "SIMULATED enclave quote — NEVER a real TEE; SHA-derived + replayable.",
    }

    lam = _lambda_axes(seed, workload, quote_digest, attested=bool(golden_match))
    receipt = _receipt({"kind": "confattest.quote", "workload": workload,
                        "quote_digest": quote_digest, "mrtd": mrtd,
                        "attested": bool(golden_match), "lambda": lam["value"]}, seed)

    return {
        "label": LABEL,
        "surface": "confattest",
        "title": "Confidential-Compute Attestation + Action Gate (MODELED)",
        "leg": "(a) confidential-compute enclave attestation quote → receipt",
        "seed": seed,
        "workload": workload,
        "quote": quote,
        "lambda": lam,
        "receipt": receipt,
        "spine": _spine(),
        "honest_note": HONEST_NOTE,
        "doctrine": DOCTRINE,
        "sources": SOURCES,
        "ts": _now_iso(),
    }


# ---------------------------------------------------------------------------
# (b) GOVERN AGENT ACTIONS, NOT REASONING — deterministic action gate
# ---------------------------------------------------------------------------
def build_gate(seed: int = 42, action: str = "agent.tool.call",
               effect: str = "write", reversible: Optional[bool] = None) -> Dict[str, Any]:
    """Deterministic action gate. Governs the ACTION effect boundary, NOT the reasoning.

    Deny-by-default policy over independently-attestable preconditions (the "Governing Actions,
    Not Agents" model, arXiv:2606.26298):
      P1  attestation: the confidential-compute enclave quote for this action must attest OK;
      P2  effect-class: the action's effect must be a recognized class;
      P3  authority:    an irreversible/high-severity effect (spend/destructive) additionally
                        requires elevated authority (deterministically derived here);
      P4  reversibility: irreversible effects are held unless P3 grants authority.
    Λ is ADVISORY only: a sub-floor Λ lowers the verdict to HOLD, but a passing Λ NEVER proves
    ALLOW — the deterministic policy decides. Verdict ∈ {ALLOW, HOLD}; never "PROVEN"/"green".
    """
    seed = int(seed) & 0xFFFFFFFF
    action = str(action or "agent.tool.call")
    effect = str(effect or "write").lower()
    if effect not in _EFFECT_CLASSES:
        effect = "write"  # normalize unknown → the conservative default class
    # reversibility: explicit query wins; else derive from the effect class + seed.
    if reversible is None:
        reversible = effect not in _IRREVERSIBLE_BY_DEFAULT

    # An attested enclave quote is an INDEPENDENT precondition (reuse leg (a) deterministically).
    q = build_quote(seed, workload=f"action:{action}")
    quote_digest = q["quote"]["quote_digest"]
    attested = bool(q["quote"]["attested"])

    # P3 elevated authority — deterministically derived (stands in for an independent authority
    # attestation, e.g. an approver / capability token). Only relevant for irreversible effects.
    authority_granted = _det_unit(str(seed), action, effect, "authority") >= 0.5

    # deterministic policy evaluation (deny-by-default)
    p1 = attested
    p2 = effect in _EFFECT_CLASSES
    p3 = authority_granted if (effect in _IRREVERSIBLE_BY_DEFAULT or not reversible) else True
    p4 = reversible or authority_granted
    preconditions = [
        {"id": "P1", "name": "enclave-attestation-ok", "attested_by": "confidential-compute quote (SIMULATED)", "pass": bool(p1)},
        {"id": "P2", "name": "recognized-effect-class", "attested_by": "effect taxonomy", "pass": bool(p2)},
        {"id": "P3", "name": "elevated-authority-for-irreversible", "attested_by": "authority attestation (deterministic)", "pass": bool(p3)},
        {"id": "P4", "name": "reversible-or-authorized", "attested_by": "reversibility check", "pass": bool(p4)},
    ]
    policy_pass = all(pc["pass"] for pc in preconditions)

    lam = _lambda_axes(seed, action, quote_digest, attested=attested, reversible=bool(reversible))

    # verdict: deny-by-default AND Λ-advisory. ALLOW only when the deterministic policy passes
    # AND the advisory Λ is at/above floor. A passing Λ never, on its own, grants ALLOW.
    allow = bool(policy_pass and lam["advisory_pass"])
    verdict = "ALLOW" if allow else "HOLD"
    if not policy_pass:
        reason = "policy DENY (deny-by-default): " + ", ".join(
            pc["id"] for pc in preconditions if not pc["pass"]) + " failed → HOLD"
    elif not lam["advisory_pass"]:
        reason = f"policy passed but Λ advisory {lam['value']} < floor {LAMBDA_FLOOR} → HOLD (advisory)"
    else:
        reason = "policy passed AND Λ advisory at/above floor → ALLOW (advisory; not a safety proof)"

    action_obj = {
        "action": action,
        "effect_class": effect,
        "reversible": bool(reversible),
        "irreversible_by_default": effect in _IRREVERSIBLE_BY_DEFAULT,
        "governed_boundary": "the ACTION side effect (NOT the agent's reasoning/plan)",
    }
    policy = {
        "model": "deny-by-default; independently-attested preconditions; deterministic evaluation",
        "governs_reasoning": False,
        "governs_action_effect": True,
        "preconditions": preconditions,
        "policy_pass": bool(policy_pass),
        "elevated_authority_granted": bool(authority_granted),
        "lambda_is_advisory": True,
        "note": ("clean-room realization of 'Governing Actions, Not Agents' (arXiv:2606.26298): an "
                 "action clears only when each precondition is attested by an independent source, "
                 "bound to the intent, and evaluated by a deterministic policy — the reasoning is "
                 "never gated. Λ is advisory (Conjecture 1); a HOLD is safe, an ALLOW is not proof."),
    }

    receipt = _receipt({"kind": "confattest.gate", "action": action, "effect": effect,
                        "reversible": bool(reversible), "verdict": verdict,
                        "quote_digest": quote_digest, "lambda": lam["value"]}, seed)

    return {
        "label": LABEL,
        "surface": "confattest",
        "title": "Confidential-Compute Attestation + Action Gate (MODELED)",
        "leg": "(b) govern agent ACTIONS not reasoning → allow/hold verdict + receipt",
        "seed": seed,
        "governs": "agent ACTION effect boundary — NOT the reasoning/plan",
        "action": action_obj,
        "attestation": {"quote_digest": quote_digest, "attested": attested,
                        "simulated": True, "label": LABEL},
        "policy": policy,
        "lambda": lam,
        "verdict": verdict,
        "allow": allow,
        "reason": reason,
        "receipt": receipt,
        "spine": _spine(),
        "honest_note": HONEST_NOTE,
        "doctrine": DOCTRINE,
        "sources": SOURCES,
        "ts": _now_iso(),
    }


# ---------------------------------------------------------------------------
# GUARDED read-only spine (DSSE / durable ledger availability — advisory only)
# ---------------------------------------------------------------------------
def _spine() -> Dict[str, Any]:
    """GUARDED, READ-ONLY chain to the DSSE / durable-ledger spine. Reports whether a signing key
    + durable ledger are available (advisory) — does NOT sign or write on this GET (doctrine v11:
    receipt-on-write, never on-read)."""
    out: Dict[str, Any] = {
        "dsse": "UNAVAILABLE", "ledger": "UNAVAILABLE", "signed_on_read": False,
        "note": ("advisory read-only: DSSE co-signing + durable-ledger anchoring happen on WRITE "
                 "in-Space, never on this GET."),
    }
    try:
        import szl_dsse as _dsse  # type: ignore
        avail = bool(_dsse.signing_available())
        out["dsse"] = "SIGNING-KEY-PRESENT" if avail else "UNSIGNED-LOCAL"
        try:
            out["dsse_pubkey_fpr"] = _dsse.public_key_fingerprint()[:16]
        except Exception:
            pass
    except Exception:
        out["dsse"] = "UNAVAILABLE"
    try:
        import szl_durable_ledger as _dl  # type: ignore
        out["ledger"] = "AVAILABLE" if hasattr(_dl, "DurableStore") else "UNAVAILABLE"
    except Exception:
        out["ledger"] = "UNAVAILABLE"
    return out


def _receipt(payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """Content-addressed receipt over the MODELED payload. UNSIGNED-LOCAL on this read path —
    no signature is fabricated; real co-signing happens on WRITE in-Space."""
    blob = _canon(payload)
    return {
        "schema": "szl.confattest.receipt/v1",
        "digest_sha256": _sha256(blob),
        "seed": int(seed),
        "signature": "UNSIGNED-LOCAL",
        "note": ("content digest over the MODELED payload; deterministic in the seed. No DSSE "
                 "signature claimed locally (UNSIGNED-LOCAL); real co-signing happens on WRITE "
                 "in-Space, not on this read path."),
    }


# ---------------------------------------------------------------------------
# HTTP registration — front-inserted routes (mirrors szl_crypto_pipeline / pcai)
# ---------------------------------------------------------------------------
def register(app, ns: str = NS_DEFAULT) -> str:
    from starlette.responses import JSONResponse  # type: ignore[import]

    @app.get(f"/api/{ns}/v1/confattest/quote", include_in_schema=False)
    async def _quote(seed: int = 42, workload: str = "szl-agent-workload"):
        t0 = time.time()
        try:
            body = build_quote(int(seed), workload or "szl-agent-workload")
        except Exception as e:  # pragma: no cover — always renderable 200
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"quote build failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "sources": SOURCES}, status_code=200)
        body["elapsed_ms"] = round((time.time() - t0) * 1000, 2)
        return JSONResponse(body, status_code=200)

    @app.get(f"/api/{ns}/v1/confattest/gate", include_in_schema=False)
    async def _gate(seed: int = 42, action: str = "agent.tool.call",
                    effect: str = "write", reversible: str = ""):
        t0 = time.time()
        rev: Optional[bool] = None
        if reversible != "":
            rev = reversible.strip().lower() in ("1", "true", "yes", "y")
        try:
            body = build_gate(int(seed), action or "agent.tool.call", effect or "write", rev)
        except Exception as e:  # pragma: no cover — always renderable 200
            return JSONResponse({"label": "UNAVAILABLE",
                                 "detail": f"gate build failed: {type(e).__name__}",
                                 "doctrine": DOCTRINE, "sources": SOURCES}, status_code=200)
        body["elapsed_ms"] = round((time.time() - t0) * 1000, 2)
        return JSONResponse(body, status_code=200)

    return (f"confattest mounted: GET /api/{ns}/v1/confattest/quote (SIMULATED enclave quote) + "
            f"GET /api/{ns}/v1/confattest/gate (govern-actions-not-reasoning; label MODELED)")


# ---------------------------------------------------------------------------
# No-server self-test — determinism + honesty + policy invariants
# ---------------------------------------------------------------------------
def _selftest() -> None:
    # --- (a) quote determinism + honesty ---
    a = build_quote(42, "szl-agent-workload")
    b = build_quote(42, "szl-agent-workload")
    assert a["label"] == "MODELED", a["label"]
    assert a["quote"]["simulated"] is True, "enclave quote must be SIMULATED"
    assert a["quote"]["quote_digest"] == b["quote"]["quote_digest"], "quote not deterministic"
    assert a["lambda"]["value"] == b["lambda"]["value"], "Λ not deterministic"
    assert a["lambda"]["value"] <= TRUST_CEIL + 1e-9, "trust ceiling 0.97 violated"
    assert "Conjecture 1" in a["lambda"]["uniqueness"], "Λ must be Conjecture 1"
    assert a["receipt"]["signature"] == "UNSIGNED-LOCAL", "must not fabricate a signature"
    assert a["spine"]["signed_on_read"] is False, "must never sign on a read path"
    # even seed → attested; odd seed → SIMULATED mismatch → attestation axis 0 → Λ=0
    assert a["quote"]["attested"] is True, "even seed should attest"
    c = build_quote(43, "szl-agent-workload")
    assert c["quote"]["attested"] is False, "odd seed should simulate an attestation mismatch"
    assert c["lambda"]["value"] == 0.0, "zero-absorption must drive Λ to 0 on bad attestation"

    # --- (b) gate governs ACTION not reasoning; deny-by-default; Λ advisory ---
    g = build_gate(42, "agent.tool.call", "read", None)
    assert g["governs"].startswith("agent ACTION"), g["governs"]
    assert g["policy"]["governs_reasoning"] is False, "must NOT govern reasoning"
    assert g["policy"]["governs_action_effect"] is True
    assert g["verdict"] in ("ALLOW", "HOLD"), g["verdict"]
    assert g["policy"]["lambda_is_advisory"] is True
    # a reversible read with a good attestation and Λ≥floor → ALLOW
    assert g["verdict"] == "ALLOW", (g["verdict"], g["reason"])
    # bad attestation (odd seed) → P1 fails → deny-by-default HOLD regardless of Λ
    g_bad = build_gate(43, "agent.tool.call", "read", None)
    assert g_bad["verdict"] == "HOLD", "bad attestation must HOLD (deny-by-default)"
    assert any(pc["id"] == "P1" and pc["pass"] is False for pc in g_bad["policy"]["preconditions"])
    # an irreversible destructive effect without authority must HOLD
    g_destr = build_gate(41, "agent.fs.delete", "destructive", False)
    assert g_destr["action"]["reversible"] is False
    if not g_destr["policy"]["elevated_authority_granted"]:
        assert g_destr["verdict"] == "HOLD", "irreversible w/o authority must HOLD"
    # determinism
    assert build_gate(42, "agent.tool.call", "read", None)["verdict"] == g["verdict"]

    # --- honesty: no fabricated positive proof / green / real-TEE claim anywhere ---
    # (honest NEGATIONS like "never green/proven" are allowed; positive claims are not)
    blob = json.dumps({"quote": a, "gate": g}).upper()
    for bad in ("SAFETY PROVEN", "PROVEN SAFE", "PROVEN GREEN", "VERDICT PROVEN",
                "TRUST 1.0", "TRUST 100%"):
        assert bad not in blob, f"must never fabricate: {bad}"
    # positive honesty: the quote must be labeled SIMULATED and disclaim any real TEE/enclave
    assert "MODELED" in json.dumps(a) and "SIMULATED" in json.dumps(a["quote"])
    assert "NO real TEE" in HONEST_NOTE, "honest note must disclaim a real TEE"
    print("szl_confattest: ALL OK (SIMULATED enclave quote deterministic + honest; action gate "
          "governs ACTION not reasoning, deny-by-default, Λ advisory; UNSIGNED-LOCAL, no sign-on-read)")


if __name__ == "__main__":
    _selftest()
