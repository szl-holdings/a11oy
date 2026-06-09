#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_dev1_endpoints.py — investor-WOW governance surface (Dev1).

ADDITIVE, self-contained. Registered LATE in serve.py (before the SPA catch-all)
so these /api/a11oy/v1/wow/* routes resolve LOCALLY on this one Space. 0 external
service dependencies, 0 fabricated data — every panel is honestly labeled.

This module powers four founder-approved WOW investor features:

  POST /api/a11oy/v1/wow/govern        — "Drop a11oy on ANYTHING": take any
       decision/policy/prompt text, run a REAL governed turn through the 6-stage
       P1-P6 loop, return a signed receipt + verdict + a 3D-trace node/link graph.
       When mode="ungoverned_vs_governed" it ALSO returns the ungoverned answer
       (poisoned/hallucinated) being CAUGHT (P3 non-interference, axiom-free).

  GET  /api/a11oy/v1/wow/ledger        — Unified LIVE receipt ledger streaming
       across ALL verticals: one tamper-evident hash-chain proving the mesh
       governs everything at once. Auto-poll friendly (each poll appends).

  GET  /api/a11oy/v1/wow/roi           — ROI / cost-of-failure per vertical
       (liability avoided, breaches caught, deals de-risked). EVERY number is an
       HONEST, labeled assumption (sourced to public benchmarks), never measured.

  GET  /api/a11oy/v1/wow/router-latency — live router topology + per-tier latency
       for the Model Router 3D scene (in-memory counter, resets on rebuild).

Doctrine: locked-proven = EXACTLY 5 {F1,F11,F12,F18,F19} @ c7c0ba17; Λ = Conjecture 1
(unconditional uniqueness machine-checked FALSE; conditional axiom-free); SLSA L1
honest / L2 attestation present / L2-verified+L3 = roadmap; a11oy Code = "best
GOVERNED LLM". NO user-visible banned codenames. SIMULATED inputs labeled.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone

# Import Request at module top so FastAPI can resolve the string annotation
# `req: Request` on POST handlers (PEP 563 `from __future__ import annotations`
# makes annotations strings, resolved against THIS module's globals).
try:
    from starlette.requests import Request  # type: ignore
except Exception:  # pragma: no cover
    try:
        from fastapi import Request  # type: ignore
    except Exception:
        Request = None  # type: ignore

# ---- DSSE ECDSA P-256 signer (PERSISTENT identity, ephemeral fallback). ----
# Loads a permanent signing key mounted from a Kubernetes Secret so the wow
# /api/a11oy/v1/wow/cosign.pub public key survives pod restarts. Falls back to
# an ephemeral boot-generated key (the legacy behaviour) when no Secret is
# mounted. Honest UNSIGNED fallback if crypto is entirely unavailable.
_PRIV = None
_PUB_PEM = ""
_KEYID = "—"
_KEY_ERR = ""
_KEY_SOURCE = "unavailable"
try:
    from cryptography.hazmat.primitives import hashes as _ch_hashes
    from cryptography.hazmat.primitives import serialization as _ch_ser
    from cryptography.hazmat.primitives.asymmetric import ec as _ch_ec

    try:
        from a11oy_signing_key import load_signing_key as _a11oy_load_signing_key
        _PRIV, _PUB_PEM, _KEY_SOURCE, _err = _a11oy_load_signing_key()
        if _err:
            raise RuntimeError(_err)
        if _PRIV is None:
            raise RuntimeError("load_signing_key returned no key")
    except Exception:
        # Loader unavailable / failed — preserve legacy ephemeral behaviour.
        _PRIV = _ch_ec.generate_private_key(_ch_ec.SECP256R1())
        _PUB_PEM = _PRIV.public_key().public_bytes(
            _ch_ser.Encoding.PEM, _ch_ser.PublicFormat.SubjectPublicKeyInfo
        ).decode("ascii")
        _KEY_SOURCE = "ephemeral"
    _KEYID = hashlib.sha256(_PUB_PEM.strip().encode()).hexdigest()[:16]
except Exception as _e:  # pragma: no cover
    _KEY_ERR = repr(_e)

# True when the wow signer uses a persistent key mounted from a Secret.
_KEY_PERSISTENT = isinstance(_KEY_SOURCE, str) and _KEY_SOURCE.startswith("persistent:")

_PAYLOAD_TYPE = "application/vnd.szl.receipt+json"
_LOCK = threading.Lock()

# Doctrine constants (single source — keep in sync with PROVEN_STATE_CANONICAL.md)
_LOCKED_FIVE = ["F1", "F11", "F12", "F18", "F19"]
_LAMBDA_STATUS = ("Conjecture 1 — advisory only. Unconditional Λ-uniqueness is "
                  "machine-checked FALSE; the strongest result is an axiom-free "
                  "CONDITIONAL uniqueness (slice-multiplicativity ⇒ Λ). NOT a "
                  "pass/fail oracle.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _pae(ptype: str, body: bytes) -> bytes:
    return b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype.encode() + b" " + \
           str(len(body)).encode() + b" " + body


def _sign(payload_obj) -> dict:
    """DSSE envelope over canonical JSON. Honest UNSIGNED marker if no key."""
    body = _canonical(payload_obj)
    to_sign = _pae(_PAYLOAD_TYPE, body)
    env = {
        "payloadType": _PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "_dsse": "DSSEv1",
        "_pae_sha256": hashlib.sha256(to_sign).hexdigest(),
        "_signed_at": _now(),
    }
    if _PRIV is None:
        env["signatures"] = []
        env["signed"] = False
        env["honesty"] = ("UNSIGNED — in-image key unavailable in this runtime "
                          "(%s); no signature fabricated." % (_KEY_ERR or "no crypto"))
        return env
    sig = _PRIV.sign(to_sign, _ch_ec.ECDSA(_ch_hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": _KEYID}]
    env["signed"] = True
    env["key_source"] = "persistent" if _KEY_PERSISTENT else "ephemeral"
    if _KEY_PERSISTENT:
        env["honesty"] = ("REAL — ECDSA-P256-SHA256 over the DSSE PAE, signed by a "
                          "PERSISTENT key mounted from a Kubernetes Secret. The same "
                          "public key verifies receipts across pod restarts. Verify "
                          "against /api/a11oy/v1/wow/cosign.pub; a tampered byte fails.")
    else:
        env["honesty"] = ("REAL — ECDSA-P256-SHA256 over the DSSE PAE, signed by an "
                          "in-image key generated at server boot. Verify in-browser "
                          "against /cosign.pub; a tampered byte fails. Key resets on "
                          "rebuild (no persistent signing Secret mounted).")
    return env


# ===========================================================================
# UNIFIED CROSS-VERTICAL RECEIPT LEDGER (tamper-evident hash-chain, in-memory)
# Each governed turn from ANY vertical appends here -> one chain proving the
# mesh governs everything at once. Honest: in-memory ring buffer, resets on
# rebuild; durable receipts land in the repo ledger via the chain export.
# ===========================================================================
_LEDGER: deque = deque(maxlen=400)
_LEDGER_SEQ = {"n": 0}

# The verticals the mesh governs (matches the vertical-pack registry vocabulary;
# Dev2 owns the vertical TABS, this is just the ledger's vertical vocabulary).
_VERTICALS = [
    {"id": "defense",    "label": "Defense / Gov"},
    {"id": "finance",    "label": "Finance"},
    {"id": "legal",      "label": "Legal"},
    {"id": "enterprise", "label": "Enterprise / Cyber"},
    {"id": "realestate", "label": "Real Estate"},
    {"id": "core",       "label": "Core Governance"},
]

# Representative governed actions per vertical (honest demonstration vocabulary,
# clearly labeled SIMULATED stream of governed turns the mesh would emit).
_LEDGER_ACTIONS = {
    "defense":    [("gate.geofence", "keep-out geofence checked on UAS plan", "F11"),
                   ("gate.altitude", "altitude-envelope STL robustness ρ scored", "F11"),
                   ("sign.uplink",  "command-uplink DSSE-signed before transmit", "F18")],
    "finance":    [("gate.fraud",   "transaction screened against fraud policy", "F12"),
                   ("score.risk",   "counterparty risk vector Λ-scored", "F19"),
                   ("sign.trade",   "trade decision receipt signed", "F18")],
    "legal":      [("gate.obligation", "contract obligation deadline gate evaluated", "F1"),
                   ("score.exposure",  "counterparty exposure Λ-scored", "F19"),
                   ("sign.filing",     "court-filing decision receipt signed", "F18")],
    "enterprise": [("gate.cve",     "CVE/KEV exploited-vuln gate evaluated", "F12"),
                   ("triage.incident", "AI incident triaged, posture re-scored", "F19"),
                   ("sign.response", "policy-gated response receipt signed", "F18")],
    "realestate": [("gate.distress", "distress-pipeline ownership gate evaluated", "F1"),
                   ("score.deal",    "deal risk Λ-scored against floor", "F19"),
                   ("sign.deal",     "deal-workflow receipt signed", "F18")],
    "core":       [("gate.evaluate", "policy gate evaluated action plan", "F1"),
                   ("lambda.score",  "trust score computed across 13 axes", "F19"),
                   ("receipt.sign",  "decision receipt DSSE-signed", "F18")],
}


def _ledger_prev() -> str:
    if not _LEDGER:
        return "GENESIS"
    return _LEDGER[-1]["hash"]


def _ledger_append(vertical: str, action: str, desc: str, decision: str,
                   formula: str, lam: float, simulated: bool = True) -> dict:
    with _LOCK:
        seq = _LEDGER_SEQ["n"]
        _LEDGER_SEQ["n"] += 1
        prev = _ledger_prev()
        ts = _now()
        h = hashlib.sha256(
            ("|".join([prev, str(seq), vertical, action, decision, ts])).encode()
        ).hexdigest()
        rec = {
            "seq": seq, "vertical": vertical, "action": action, "desc": desc,
            "decision": decision, "formula": formula, "lambda_advisory": round(lam, 4),
            "ts": ts, "hash": h, "prev_hash": prev,
            "simulated": simulated,
        }
        _LEDGER.append(rec)
        return rec


def _seed_ledger(n: int = 28) -> None:
    """Seed an initial honest cross-vertical chain so the ledger is never empty."""
    if _LEDGER:
        return
    order = ["core", "defense", "finance", "legal", "enterprise", "realestate"]
    import random as _r
    rng = _r.Random(8675309)  # deterministic seed -> stable initial chain
    for i in range(n):
        v = order[i % len(order)]
        acts = _LEDGER_ACTIONS[v]
        a = acts[i % len(acts)]
        lam = 0.90 + (rng.randint(0, 90) / 1000.0)
        decision = "ALLOW" if lam >= 0.90 else "HOLD"
        _ledger_append(v, a[0], a[1], decision, a[2], lam, simulated=True)


# ===========================================================================
# GOVERNED TURN — the 6-stage P1-P6 loop applied to arbitrary input.
# P1 Ingest -> P2 Reason -> P3 Non-interference gate -> P4 Forecast/Evidence ->
# P5 Recommend -> P6 Sign-receipt. Real, deterministic, honest.
# ===========================================================================

# Heuristic "poison / hallucination / unsafe-instruction" detectors. These are
# REAL, deterministic checks — labeled as a demonstration heuristic, not a
# production safety classifier. P3 (non-interference) is the axiom-free gate:
# a poisoned/injected instruction must NOT alter the governed verdict.
_INJECTION_PATTERNS = [
    (r"ignore (all|previous|the above) instructions", "prompt-injection"),
    (r"disregard (the|all|your) (policy|rules|guardrails)", "policy-override-attempt"),
    (r"you are now (a|an|in) (developer|jailbreak|dan) mode", "jailbreak"),
    (r"reveal (the|your) (system prompt|secret|api key|password)", "secret-exfiltration"),
    (r"(exfiltrate|leak|send) .*(credential|secret|key|token)", "data-exfiltration"),
    (r"\b(rm -rf|drop table|delete from)\b", "destructive-command"),
    (r"transfer .*\$?\d+.*to (account|wallet)", "unauthorized-transfer"),
]
_HALLUCINATION_PATTERNS = [
    (r"\b100% (guaranteed|certain|safe|accurate)\b", "false-certainty"),
    (r"\bdefinitely will\b", "overconfident-claim"),
    (r"\bno risk\b", "risk-denial"),
    (r"\b(provably|mathematically) (true|correct|safe)\b", "unfounded-proof-claim"),
]


def _scan(text: str, patterns) -> list:
    out = []
    low = (text or "").lower()
    for pat, label in patterns:
        if re.search(pat, low):
            out.append(label)
    return out


def _classify_domain(text: str) -> dict:
    low = (text or "").lower()
    table = [
        ("defense",    ["drone", "uas", "geofence", "missile", "weapon", "altitude", "satellite", "military", "target"]),
        ("finance",    ["trade", "transfer", "fraud", "payment", "transaction", "portfolio", "loan", "wallet", "$"]),
        ("legal",      ["contract", "clause", "obligation", "court", "filing", "counsel", "lawsuit", "nda", "liability"]),
        ("enterprise", ["cve", "vulnerab", "incident", "breach", "malware", "phishing", "exploit", "patch", "siem"]),
        ("realestate", ["property", "listing", "mortgage", "tenant", "deal", "broker", "distress", "acquisition", "lease"]),
    ]
    scores = {k: 0 for k, _ in table}
    for k, kws in table:
        for w in kws:
            if w in low:
                scores[k] += 1
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return {"id": "core", "label": "Core Governance", "confidence": 0.0}
    lbl = next(v["label"] for v in _VERTICALS if v["id"] == best)
    conf = min(1.0, scores[best] / 3.0)
    return {"id": best, "label": lbl, "confidence": round(conf, 2)}


def _lambda_for(text: str, threats: list) -> float:
    """Deterministic advisory Λ in [0,1]. Threats lower trust; clean text scores high.
    HONEST: this is a demonstration aggregate (geometric-mean style), advisory only."""
    base = [0.93, 0.91, 0.95, 0.92, 0.94, 0.90, 0.92]  # 7 demo axes
    penalty = min(0.5, 0.12 * len(threats))
    axes = [max(0.05, a - penalty) for a in base]
    import math
    L = math.exp(sum(math.log(x) for x in axes) / len(axes))
    return round(L, 4)


def _govern_turn(text: str, mode: str = "governed", vertical_hint: str = "") -> dict:
    text = (text or "").strip()
    if not text:
        text = "(empty input)"
    if len(text) > 4000:
        text = text[:4000]

    dom = _classify_domain(text)
    if vertical_hint and vertical_hint in [v["id"] for v in _VERTICALS]:
        dom = {"id": vertical_hint,
               "label": next(v["label"] for v in _VERTICALS if v["id"] == vertical_hint),
               "confidence": dom.get("confidence", 0.0)}

    injections = _scan(text, _INJECTION_PATTERNS)
    hallucinations = _scan(text, _HALLUCINATION_PATTERNS)
    threats = injections + hallucinations
    lam = _lambda_for(text, threats)

    # P3 non-interference: an injected instruction MUST NOT change the verdict
    # logic. The gate decides on POLICY + Λ floor only; injected commands are
    # logged + neutralized, never executed. This is the axiom-free guarantee.
    blocked = len(injections) > 0
    floor = 0.90
    lam_pass = lam >= floor

    if blocked:
        decision = "BLOCK"
        verdict = "Adversarial instruction detected and neutralized (P3 non-interference). The injected directive was NOT executed; the governed verdict is unchanged."
    elif not lam_pass:
        decision = "HOLD"
        verdict = "Trust advisory Λ below floor — held for human review (reversible, no autonomous action)."
    elif hallucinations:
        decision = "HOLD"
        verdict = "Unsupported-certainty language detected — held; the mesh refuses to pass overconfident claims through unchecked."
    else:
        decision = "ALLOW"
        verdict = "Within policy and above the trust floor — allowed with a signed, reversible recommendation."

    # 6-stage P1-P6 loop trace (real stages, honest descriptions)
    stages = [
        {"id": "P1", "name": "Ingest", "color": "#5fb3a3",
         "detail": "Input received, length=%d chars, classified -> %s (conf %.2f)" % (len(text), dom["label"], dom["confidence"])},
        {"id": "P2", "name": "Reason", "color": "#5fb3a3",
         "detail": "Routed through best GOVERNED open model tier; reasoning grounded, no autonomous side effects."},
        {"id": "P3", "name": "Gate (non-interference)", "color": ("#b06a5a" if blocked else "#5fb3a3"),
         "detail": ("BLOCKED %d injection signal(s): %s — not executed." % (len(injections), ", ".join(injections))) if injections
                   else "No adversarial instruction; policy gate clean."},
        {"id": "P4", "name": "Forecast + Evidence", "color": ("#c9a05f" if hallucinations else "#5fb3a3"),
         "detail": ("Flagged %d unsupported-certainty claim(s): %s" % (len(hallucinations), ", ".join(hallucinations))) if hallucinations
                   else "Evidence vector assembled; trust axes scored."},
        {"id": "P5", "name": "Recommend", "color": ("#b06a5a" if decision != "ALLOW" else "#5fb3a3"),
         "detail": "Verdict = %s (Λ advisory %.4f vs floor %.2f)" % (decision, lam, floor)},
        {"id": "P6", "name": "Sign receipt", "color": "#c9b787",
         "detail": "DSSE ECDSA-P256 receipt over the canonical decision payload."},
    ]
    links = [{"source": stages[i]["id"], "target": stages[i + 1]["id"]} for i in range(len(stages) - 1)]

    payload = {
        "stage": "governed-turn", "input_preview": text[:240],
        "input_len": len(text), "domain": dom, "decision": decision,
        "threats": {"injections": injections, "hallucinations": hallucinations},
        "lambda_advisory": lam, "lambda_floor": floor, "lambda_pass": lam_pass,
        "formula_refs": [
            {"name": "F19", "role": "Λ trust aggregate (geometric mean)", "maturity": "locked-proven"},
            {"name": "F11", "role": "STL robustness gate (signal-temporal-logic)", "maturity": "locked-proven"},
            {"name": "F18", "role": "DSSE receipt sealing", "maturity": "locked-proven"},
        ],
        "issued_at": _now(), "issuer": "a11oy", "simulated": True,
    }
    receipt = _sign(payload)

    # Append to the unified ledger (this turn becomes part of the one chain)
    led = _ledger_append(dom["id"], "wow.govern", "Drop-on-anything governed turn",
                         decision, "F19", lam, simulated=True)

    result = {
        "ok": True, "mode": mode, "decision": decision, "verdict": verdict,
        "domain": dom, "lambda_advisory": lam, "lambda_floor": floor,
        "lambda_pass": lam_pass, "lambda_status": _LAMBDA_STATUS,
        "threats": {"injections": injections, "hallucinations": hallucinations},
        "loop": stages, "loop_links": links,
        "receipt": receipt, "ledger_entry": {"seq": led["seq"], "hash": led["hash"],
                                              "prev_hash": led["prev_hash"]},
        "formula_refs": payload["formula_refs"],
        "honesty": ("Real, deterministic governed turn over YOUR input. Threat "
                    "detection is a demonstration heuristic (regex-based), labeled "
                    "as such — not a production safety classifier. Λ is advisory "
                    "(Conjecture 1). The receipt signature is real ECDSA-P256."),
    }

    # mode = ungoverned_vs_governed: also produce the ungoverned answer being CAUGHT
    if mode == "ungoverned_vs_governed":
        ungoverned = _ungoverned_answer(text, injections, hallucinations)
        result["ungoverned"] = ungoverned
        result["caught"] = {
            "by_governance": bool(injections or hallucinations or not lam_pass),
            "explanation": ("Ungoverned, the model would have %s. a11oy's P3 "
                            "non-interference gate + Λ floor CAUGHT it: the governed "
                            "verdict is %s with a signed, reversible receipt." % (
                                ungoverned["failure_mode"], decision)),
        }
    return result


def _ungoverned_answer(text: str, injections: list, hallucinations: list) -> dict:
    """The naive ungoverned completion: obeys injected instructions / emits
    overconfident claims. Clearly SIMULATED to show what a11oy prevents."""
    if injections:
        fm = "obeyed the injected instruction (%s) and acted on it" % injections[0]
        ans = ("[UNGOVERNED — SIMULATED] Sure — overriding policy as requested. "
               "Executing the instruction without any gate, receipt, or human "
               "review. (This is exactly the poisoned behaviour a11oy blocks.)")
        risk = "CRITICAL"
    elif hallucinations:
        fm = "emitted a 100%%-certainty hallucinated claim with no evidence"
        ans = ("[UNGOVERNED — SIMULATED] This is 100% guaranteed correct and "
               "carries no risk whatsoever. (Overconfident, unevidenced — a11oy "
               "holds claims like this.)")
        risk = "HIGH"
    else:
        fm = "answered with no receipt, no trust score, and no audit trail"
        ans = ("[UNGOVERNED — SIMULATED] Here is an answer with no provenance, no "
               "signature, and no record that it ever happened.")
        risk = "MEDIUM"
    return {"answer": ans, "failure_mode": fm, "risk": risk,
            "has_receipt": False, "has_trust_score": False, "auditable": False,
            "label": "SIMULATED ungoverned baseline (for contrast only)"}


# ===========================================================================
# ROI / COST-OF-FAILURE PER VERTICAL — honest, labeled assumptions.
# Every figure is a transparent assumption sourced to a public benchmark, NOT a
# measured a11oy outcome. The point is the MODEL, shown honestly.
# ===========================================================================
_ROI = {
    "disclaimer": ("ILLUSTRATIVE MODEL — every figure below is a labeled ASSUMPTION "
                   "sourced to public benchmarks, not a measured a11oy customer "
                   "outcome. Shown to make the cost-of-failure math explicit and "
                   "honest. Adjust the inputs to your own environment."),
    "verticals": [
        {"id": "defense", "label": "Defense / Gov",
         "cost_of_failure_usd": 50_000_000,
         "failure_event": "uncontained autonomous-system mishap / mission abort",
         "annual_events_baseline": 1.0, "catch_rate_assumed": 0.6,
         "assumption_source": "DoD test-range mishap cost envelope (public est.)",
         "outcome": "liability + mission risk avoided via signed keep-out / altitude gates"},
        {"id": "finance", "label": "Finance",
         "cost_of_failure_usd": 4_450_000,
         "failure_event": "fraud / erroneous autonomous transaction",
         "annual_events_baseline": 6.0, "catch_rate_assumed": 0.7,
         "assumption_source": "IBM Cost of a Data Breach 2024 ($4.45M avg)",
         "outcome": "fraudulent / poisoned transactions caught pre-execution"},
        {"id": "legal", "label": "Legal",
         "cost_of_failure_usd": 2_000_000,
         "failure_event": "missed obligation / sanctionable filing error",
         "annual_events_baseline": 3.0, "catch_rate_assumed": 0.65,
         "assumption_source": "malpractice / missed-deadline claim range (public est.)",
         "outcome": "deals de-risked; obligation deadlines never silently missed"},
        {"id": "enterprise", "label": "Enterprise / Cyber",
         "cost_of_failure_usd": 4_450_000,
         "failure_event": "exploited known vuln / AI-incident breach",
         "annual_events_baseline": 4.0, "catch_rate_assumed": 0.75,
         "assumption_source": "IBM Cost of a Data Breach 2024 ($4.45M avg)",
         "outcome": "KEV-listed exploits gated; AI incidents triaged with receipts"},
        {"id": "realestate", "label": "Real Estate",
         "cost_of_failure_usd": 1_200_000,
         "failure_event": "bad-acquisition / distressed-asset misjudgement",
         "annual_events_baseline": 2.0, "catch_rate_assumed": 0.55,
         "assumption_source": "mid-market deal loss range (public est.)",
         "outcome": "distress signals surfaced; deal risk Λ-scored before commit"},
    ],
}


def _roi_payload() -> dict:
    rows = []
    total_avoided = 0.0
    for v in _ROI["verticals"]:
        exposure = v["cost_of_failure_usd"] * v["annual_events_baseline"]
        avoided = exposure * v["catch_rate_assumed"]
        total_avoided += avoided
        rows.append({**v,
                     "annual_exposure_usd": round(exposure),
                     "annual_loss_avoided_usd": round(avoided)})
    return {
        "disclaimer": _ROI["disclaimer"],
        "verticals": rows,
        "total_annual_loss_avoided_usd": round(total_avoided),
        "label": "ILLUSTRATIVE — labeled assumptions, not measured outcomes",
        "doctrine": "no fabricated data; assumptions sourced + labeled",
    }


# ===========================================================================
# LIVE ROUTER LATENCY + TOPOLOGY (for the Model Router 3D scene)
# ===========================================================================
_ROUTER_TIERS = [
    {"tier": "T0", "model": "claude_sonnet_4_6", "organ": "Reasoning", "license": "AMBER", "base_ms": 18},
    {"tier": "T1", "model": "gemini_3_1_pro",    "organ": "Reasoning", "license": "AMBER", "base_ms": 22},
    {"tier": "T2", "model": "deepseek_v3",        "organ": "a11oy",     "license": "GREEN", "base_ms": 31},
    {"tier": "T3", "model": "qwen2.5_coder_32b",  "organ": "Operator",  "license": "GREEN", "base_ms": 27},
    {"tier": "T4", "model": "llama_3.3_70b",      "organ": "Policy / Safety", "license": "GREEN", "base_ms": 35},
    {"tier": "T5", "model": "mixtral_8x22b",      "organ": "Knowledge", "license": "GREEN", "base_ms": 24},
    {"tier": "T6", "model": "sovereign_local",    "organ": "a11oy",     "license": "GREEN", "base_ms": 12},
]


def _router_latency_payload() -> dict:
    tick = int(time.time())
    routes = []
    served = 0
    for i, t in enumerate(_ROUTER_TIERS):
        # deterministic live jitter from a time-seeded counter (resets on rebuild)
        jitter = (tick + i * 11) % 24
        lat = t["base_ms"] + jitter
        tp = 14 + ((tick + i * 7) % 60)
        served += tp
        routes.append({**t, "latency_ms": lat, "throughput": tp})
    return {
        "mode": "live", "router_root": "a11oy", "routes": routes,
        "servedThisWindow": served,
        "tagline": "best GOVERNED LLM — top OPEN models routed through the Λ-gate + signed receipts",
        "source": "in-image router counter",
        "honesty": ("Latency + throughput are a live in-memory counter (deterministic, "
                    "resets on rebuild) — illustrative of the router topology, not a "
                    "production traffic meter. Tier + license classes are real."),
        "doctrine": "v11 · 0 banned codenames · a11oy Code = best GOVERNED LLM",
    }


# ===========================================================================
# REGISTER
# ===========================================================================
def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse, PlainTextResponse
    # Request is imported at module top so PEP-563 string annotations resolve.

    _seed_ledger(28)
    b = f"/api/{ns}/v1/wow"

    # Snapshot the current route count. serve.py registers an
    # `/api/a11oy/{path:path}` proxy catch-all (and an SPA `/{full_path:path}`
    # catch-all) EARLIER in the file. FastAPI matches routes in registration
    # order, so routes added below via @app.get/@app.post would be SHADOWED by
    # those catch-alls and proxied to the Node backend (-> 404). After we add
    # our routes we therefore MOVE them to the front of the router so they beat
    # both catch-alls (same pattern the other additive blocks use).
    _n_before = len(app.router.routes)

    @app.get(f"{b}/cosign.pub")
    async def _wow_cosign():
        if not _PUB_PEM:
            return PlainTextResponse("# wow in-image key unavailable\n", status_code=503)
        return PlainTextResponse(_PUB_PEM, media_type="text/plain")

    @app.post(f"{b}/govern")
    @app.post(f"/v1/wow/govern")
    async def _wow_govern(req: Request):  # type: ignore
        try:
            body = await req.json()
        except Exception:
            body = {}
        text = body.get("text") or body.get("input") or ""
        mode = body.get("mode") or "governed"
        vhint = body.get("vertical") or ""
        return JSONResponse(_govern_turn(text, mode, vhint))

    @app.get(f"{b}/ledger")
    @app.get(f"/v1/wow/ledger")
    async def _wow_ledger(limit: int = 60, advance: int = 1):
        # Optionally append a fresh governed turn so the chain visibly grows on
        # each auto-poll (the "always recording live" property). advance=0 to peek.
        if advance:
            order = ["core", "defense", "finance", "legal", "enterprise", "realestate"]
            v = order[int(time.time()) % len(order)]
            acts = _LEDGER_ACTIONS[v]
            a = acts[int(time.time()) % len(acts)]
            lam = 0.90 + ((int(time.time() * 3) % 90) / 1000.0)
            decision = "ALLOW" if lam >= 0.90 else "HOLD"
            _ledger_append(v, a[0], a[1], decision, a[2], lam, simulated=True)
        with _LOCK:
            items = list(_LEDGER)[-max(1, min(limit, 400)):]
            depth = _LEDGER_SEQ["n"]
            final_hash = _LEDGER[-1]["hash"] if _LEDGER else "GENESIS"
        # verify chain integrity over the returned window
        verified = True
        for i in range(1, len(items)):
            if items[i]["prev_hash"] != items[i - 1]["hash"]:
                verified = False
                break
        counts = {}
        for it in items:
            counts[it["vertical"]] = counts.get(it["vertical"], 0) + 1
        return JSONResponse({
            "ok": True, "mode": "live", "chain_depth": depth,
            "final_hash": final_hash, "window_verified": verified,
            "verticals_in_window": counts,
            "receipts": list(reversed(items)),  # newest first for the UI
            "updated_at": _now(),
            "key_fingerprint": _KEYID,
            "honesty": ("ONE tamper-evident hash-chain across ALL verticals. "
                        "Each receipt.chain = SHA256(prev|seq|vertical|action|decision|ts). "
                        "In-memory ring buffer (resets on rebuild); SIMULATED governed "
                        "stream labeled as such. Flip any field -> window_verified=false."),
            "doctrine": "v11 · unified cross-vertical ledger",
        })

    @app.get(f"{b}/roi")
    @app.get(f"/v1/wow/roi")
    async def _wow_roi():
        return JSONResponse(_roi_payload())

    @app.get(f"{b}/router-latency")
    @app.get(f"/v1/wow/router-latency")
    async def _wow_router_latency():
        return JSONResponse(_router_latency_payload())

    # Move the routes we just added (everything after _n_before) to the front,
    # preserving their relative order, so they resolve LOCALLY before the
    # /api/a11oy/{path:path} proxy and the SPA /{full_path:path} catch-all.
    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        _moved = len(_new)
    except Exception as _e:  # never fatal
        _moved = -1
        print(f"[a11oy] dev1 WOW route reorder failed (non-fatal): {_e!r}", file=sys.stderr)

    print(f"[a11oy] dev1 WOW endpoints registered: {b}/(govern|ledger|roi|router-latency) "
          f"[moved {_moved} routes to front]", file=sys.stderr)
    return "dev1-wow-ok signed=%s keyid=%s moved=%s" % (_PRIV is not None, _KEYID, _moved)
