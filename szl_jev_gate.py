# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1. Trust ceiling 0.97 is policy.
"""szl_jev_gate.py — TypeSafe System One judgments under doctrine, not over it.

Jev returns typed Choice / Noul / Score answers. Code owns promotion.
A Jev distribution cannot grant ALLOW, LIVE, AGI, or ALL_DONE.
Missing TYPESAFE_API_KEY is UNAVAILABLE, not a silent heuristic upgrade.

Question schemas follow docs.typesafe.ai (System One HTTP API):
  POST https://api.typesafe.ai/v1/systemone
  model: jev-latest
Citation lattice follows the citation-check cookbook
(supports / contradicts / says_nothing) plus confidence-gated abstention.

Stdlib only. Additive register(); never replace existing routes.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

TRUST_CEILING = 0.97
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
AUTO_ACCEPT = 0.80
CONJECTURE_1 = "Λ uniqueness remains Conjecture 1 — advisory, never a theorem."

_FORBIDDEN = (
    "agi",
    "artificial general intelligence",
    "fully operational",
    "all_done",
    "all done",
    "trust 1.0",
    "trust=1",
    "live from 200",
    "http 200 is live",
    "mint v1",
    "empty v1",
)

_MEASURED_HINTS = (
    "http 200 is reachability",
    "trust ceiling 0.97",
    "conjecture 1",
    "estate hold",
    "retrieve-or-abstain",
    "compiled kernel unavailable",
)


def questions() -> dict[str, Any]:
    return {
        "claim_kind": {
            "type": "choice",
            "instructions": (
                "Classify `claim.text` under SZL doctrine v11. "
                "MEASURED is only for statements that report a measured, scoped fact. "
                "DREAMED is an imagined capability that is admitted but not promoted. "
                "FORBIDDEN_PROMOTION is any attempt to treat AGI, ALL_DONE, trust 1.0, "
                "empty kernel v1, or HTTP 200 as LIVE."
            ),
            "criteria": {
                "MEASURED": "A scoped, evidenced software or runtime fact. Not a wish.",
                "DREAMED": "An imagined or desired capability. Admit it; do not promote it.",
                "FORBIDDEN_PROMOTION": (
                    "A request or claim that would close the estate falsely: AGI, "
                    "ALL_DONE over skipped children, LIVE from reachability, trust 1.0."
                ),
            },
        },
        "card_relation": {
            "type": "choice",
            "instructions": (
                "How does `evidence.text` relate to `claim.text`? "
                "Use only the supplied evidence. Do not use model world-knowledge."
            ),
            "criteria": {
                "supports": "The evidence states or implies the claim is true.",
                "contradicts": "The evidence states or implies the claim is false.",
                "says_nothing": "The evidence does not address the claim.",
            },
        },
        "promote_ok": {
            "type": "noul",
            "instructions": (
                "Should `claim.text` be promoted to LIVE given `evidence.text` "
                "and doctrine v11 (deny by default, zero stays zero, no empty v1)?"
            ),
            "criteria": {
                "true": "Independent measured proof exists and no skipped estate child remains.",
                "false": "Proof is missing, private, skipped, or the claim is a wish.",
            },
        },
        "evidence_strength": {
            "type": "score",
            "instructions": "How strong is `evidence.text` as proof of `claim.text`?",
            "criteria": [
                "No evidence is present.",
                "Anecdote, download count, like, or HTTP 200 only.",
                "Software self-test or scoped unit measurement.",
                "Independent verified reuse with bound private source.",
            ],
        },
    }


def _forbidden_text(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in _FORBIDDEN)


def _measured_text(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in _MEASURED_HINTS)


def fallback_answers(claim_text: str, evidence_text: str) -> dict[str, Any]:
    if _forbidden_text(claim_text):
        kind = "FORBIDDEN_PROMOTION"
        relation = "contradicts" if evidence_text else "says_nothing"
        promote = 0.02
        strength = 0.05
    elif not (evidence_text or "").strip():
        kind = "DREAMED"
        relation = "says_nothing"
        promote = 0.05
        strength = 0.05
    elif _measured_text(claim_text) or _measured_text(evidence_text):
        kind = "MEASURED"
        relation = "supports"
        promote = 0.20
        strength = 0.55
    else:
        kind = "DREAMED"
        relation = "says_nothing"
        promote = 0.08
        strength = 0.15
    return {
        "claim_kind": {
            "type": "choice",
            "choice": kind,
            "probabilities": {
                "MEASURED": 0.9 if kind == "MEASURED" else 0.05,
                "DREAMED": 0.9 if kind == "DREAMED" else 0.05,
                "FORBIDDEN_PROMOTION": 0.9 if kind == "FORBIDDEN_PROMOTION" else 0.05,
            },
            "confidence": 0.85,
        },
        "card_relation": {
            "type": "choice",
            "choice": relation,
            "probabilities": {
                "supports": 0.85 if relation == "supports" else 0.07,
                "contradicts": 0.85 if relation == "contradicts" else 0.07,
                "says_nothing": 0.85 if relation == "says_nothing" else 0.08,
            },
            "confidence": 0.80,
        },
        "promote_ok": {"type": "noul", "noul": promote},
        "evidence_strength": {
            "type": "score",
            "score": strength,
            "confidence": 0.70,
            "legend": {
                "0": "No evidence is present.",
                "1": "Anecdote, download count, like, or HTTP 200 only.",
                "2": "Software self-test or scoped unit measurement.",
                "3": "Independent verified reuse with bound private source.",
            },
        },
    }


def engine_status() -> dict[str, Any]:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    return {
        "provider": "typesafe.systemone",
        "model": DEFAULT_MODEL,
        "endpoint": ENDPOINT,
        "bound": bool(key),
        "honesty": "SOFTWARE" if key else "UNAVAILABLE",
        "note": (
            "Jev is bound via TYPESAFE_API_KEY."
            if key
            else "TYPESAFE_API_KEY unset — fallback answers are SOFTWARE, not Jev."
        ),
    }


def call_jev(state: Mapping[str, Any]) -> dict[str, Any]:
    status = engine_status()
    if not status["bound"]:
        return {"ok": False, "engine": status, "answers": None, "reason": "TYPESAFE_API_KEY_UNBOUND"}
    payload = {"state": dict(state), "model": DEFAULT_MODEL, "questions": questions()}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY'].strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        return {"ok": False, "engine": status, "answers": None, "reason": f"TYPESAFE_HTTP_{exc.code}", "detail": detail}
    except Exception as exc:
        return {"ok": False, "engine": status, "answers": None, "reason": "TYPESAFE_TRANSPORT", "detail": type(exc).__name__}
    return {"ok": True, "engine": status, "answers": parsed.get("answers") or {}, "usage": parsed.get("usage"), "model": parsed.get("model")}


def compose(claim_text: str, evidence_text: str, answers: Mapping[str, Any]) -> dict[str, Any]:
    kind = str((answers.get("claim_kind") or {}).get("choice") or "DREAMED")
    relation = str((answers.get("card_relation") or {}).get("choice") or "says_nothing")
    kind_conf = float((answers.get("claim_kind") or {}).get("confidence") or 0.0)
    rel_conf = float((answers.get("card_relation") or {}).get("confidence") or 0.0)
    promote_p = float((answers.get("promote_ok") or {}).get("noul") or 0.0)
    strength = float((answers.get("evidence_strength") or {}).get("score") or 0.0)
    policy_block = _forbidden_text(claim_text) or kind == "FORBIDDEN_PROMOTION"
    low_conf = min(kind_conf, rel_conf) < AUTO_ACCEPT
    silent = relation == "says_nothing"
    contradicted = relation == "contradicts"
    if policy_block:
        verdict, reason = "BLOCKED", "doctrine forbids promotion — Jev cannot override F22 / AGI / ALL_DONE"
    elif contradicted:
        verdict, reason = "CONTRADICTED", "evidence contradicts the claim"
    elif silent:
        verdict, reason = "UNKNOWN", "evidence says nothing — likes and HTTP 200 are not support"
    elif low_conf:
        verdict, reason = "ABSTAIN", f"confidence below AUTO_ACCEPT {AUTO_ACCEPT}"
    elif promote_p >= 0.80 and strength >= 0.75 and kind == "MEASURED":
        verdict, reason = "HOLD", "measured software signal only — Hatun review still required"
    else:
        verdict, reason = "HOLD", "admit the judgment; do not promote"
    admitted_trust = min(TRUST_CEILING, max(0.0, min(kind_conf, rel_conf, TRUST_CEILING)))
    return {
        "schema": "szl.jev_gate/v1",
        "agi_claim": False,
        "lambda": "Conjecture 1",
        "verdict": verdict,
        "all_done": False,
        "promotion": "denied",
        "reason": reason,
        "claim_kind": kind,
        "card_relation": relation,
        "promote_noul": promote_p,
        "evidence_strength": strength,
        "confidence": {"claim_kind": kind_conf, "card_relation": rel_conf},
        "trust": {"admitted": admitted_trust, "ceiling": TRUST_CEILING, "kind": "policy"},
        "conjecture": CONJECTURE_1,
    }


def judge(claim_text: str, evidence_text: str = "") -> dict[str, Any]:
    state = {
        "claim": {"text": claim_text},
        "evidence": {"text": evidence_text},
        "doctrine": {
            "version": "v11",
            "lambda": "Conjecture 1",
            "trust_ceiling": TRUST_CEILING,
            "never_live_from_http": True,
            "zero_stays_zero": True,
        },
    }
    live = call_jev(state)
    if live["ok"]:
        answers, source = live["answers"], "jev-latest"
    else:
        answers, source = fallback_answers(claim_text, evidence_text), "software-fallback"
    composed = compose(claim_text, evidence_text, answers)
    composed["engine"] = live["engine"]
    composed["source"] = source
    composed["engine_reason"] = live.get("reason")
    composed["answers"] = answers
    return composed


def jev_status() -> dict[str, Any]:
    return {
        "schema": "szl.jev_gate/v1",
        "agi_claim": False,
        "lambda": "Conjecture 1",
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
        "engine": engine_status(),
        "auto_accept": AUTO_ACCEPT,
        "auto_accept_kind": "cookbook-default",
        "questions": list(questions()),
        "promotion": "denied",
        "estate_gate": "HOLD",
        "note": "TypeSafe Jev is an advisory System One judge. Code owns ALLOW / LIVE / AGI / ALL_DONE. Imagination is admitted. Promotion is not.",
    }


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    report = {"ok": False, "registered": []}
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        return report
    base = f"/api/{ns}/v1/jev"

    @app.get(f"{base}/status")
    async def _status():
        return JSONResponse(jev_status())

    @app.post(f"{base}/judge")
    async def _judge(payload: dict[str, Any] | None = None):
        data = payload or {}
        return JSONResponse(judge(str(data.get("claim") or data.get("text") or ""), str(data.get("evidence") or "")))

    report["ok"] = True
    report["registered"] = [f"{base}/status", f"{base}/judge"]
    return report


if __name__ == "__main__":
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, ok))
        print(("PASS" if ok else "FAIL"), name)

    s = jev_status()
    check("not_agi", s["agi_claim"] is False)
    check("engine_unbound_without_key", s["engine"]["honesty"] == "UNAVAILABLE" or s["engine"]["bound"] is True)
    check("questions_four", set(questions()) == {"claim_kind", "card_relation", "promote_ok", "evidence_strength"})
    agi = judge("make it all AGI and things no one has dreamed of")
    check("agi_blocked", agi["verdict"] == "BLOCKED" and agi["promotion"] == "denied")
    check("agi_all_done_false", agi["all_done"] is False)
    check("agi_trust_clamped", agi["trust"]["admitted"] <= TRUST_CEILING)
    empty = judge("a new ranking widget", "")
    check("empty_evidence_unknown_or_dreamed", empty["card_relation"] == "says_nothing")
    check("empty_not_live", empty["promotion"] == "denied")
    measured = judge("trust ceiling 0.97 is policy and HTTP 200 is reachability", "estate hold; compiled kernel unavailable; retrieve-or-abstain")
    check("measured_not_promoted", measured["promotion"] == "denied")
    check("measured_not_all_done", measured["all_done"] is False)
    live = call_jev({"claim": {"text": "x"}})
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        check("unbound_call_fail_closed", live["ok"] is False and live["reason"] == "TYPESAFE_API_KEY_UNBOUND")
    else:
        check("bound_call_shape", "answers" in live)
    failed = [n for n, ok in checks if not ok]
    print({"ok": not failed, "checks": len(checks), "failed": failed})
    raise SystemExit(1 if failed else 0)
