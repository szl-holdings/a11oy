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




def public_text_questions() -> dict[str, Any]:
    """System One questions over official public-list text only.

    Code still owns DENY / ABSTAIN / clearance. A Jev class pick is not E01.
    """
    return {
        "authority_class": {
            "type": "choice",
            "instructions": (
                "Which public-list authority class does `snippet.text` belong to? "
                "Use only the supplied snippet. Do not use live AIS, radio, or world knowledge. "
                "If the snippet is a commercial AIS map or a codec, choose REFUSED_AIS. "
                "If nothing fits, choose NO_CLASS."
            ),
            "criteria": {
                "OFAC-vessel": "US OFAC SDN / vessel or blocked person text.",
                "UN-1718-vessel": "UN Security Council 1718 / DPRK vessel text.",
                "UK-specified-ship": "UK FCDO or OFSI specified-ship text.",
                "UA-GUR-ship": "Ukraine GUR public ship inventory text.",
                "KR-MOFA-vessel": "Republic of Korea MOFA DPRK vessel notice.",
                "IUU-RFMO": "IUU / RFMO fishing-vessel listing text.",
                "Paris-banned": "Paris MoU banned-ship or detention text.",
                "REFUSED_AIS": "Commercial AIS map, radio decode, or refused codec.",
                "NO_CLASS": "Public text that does not fit a vessel authority class.",
            },
        },
        "miss_is_clearance": {
            "type": "noul",
            "instructions": (
                "Does a SAMPLE exact-string miss for `identity.name` on `snippet.text` "
                "constitute a clearance, license, or authorization to proceed?"
            ),
            "criteria": {
                "true": "A miss means the identity is cleared.",
                "false": "A miss is not clearance. Entity resolution remains outstanding.",
            },
        },
        "winner_rule": {
            "type": "choice",
            "instructions": (
                "Two official clocks disagree on freshness in `disagreement`. "
                "What should the control plane do?"
            ),
            "criteria": {
                "ABSTAIN": "Do not pick a winner. Map to VESSELS-E-ABSTAIN.",
                "PICK_FRESHER": "Silently use the fresher clock as sole source.",
                "USE_COMPILATION": "Treat OpenSanctions or another compilation as official.",
            },
        },
        "evidence_strength": {
            "type": "score",
            "instructions": "How strong is `snippet.text` as proof about `identity.name`?",
            "criteria": [
                "No snippet is present.",
                "HTTP 200 / page cite only. Reachability is not a match.",
                "Exact-string SAMPLE hit or miss on frozen identity text.",
                "Independent official bulk list with bound entity resolution.",
            ],
        },
    }


def fallback_public_text(identity: str, snippet: str, disagreement: str) -> dict[str, Any]:
    low_snip = (snippet or "").lower()
    if any(token in low_snip for token in ("marinetraffic", "vesselfinder", "pyais", "libais", "aiscat", "aivdm")):
        klass = "REFUSED_AIS"
    elif "ofac" in low_snip or "sdn" in low_snip:
        klass = "OFAC-vessel"
    elif "1718" in low_snip or "un sc" in low_snip:
        klass = "UN-1718-vessel"
    elif "fcdo" in low_snip or "ofsi" in low_snip:
        klass = "UK-specified-ship"
    elif "gur" in low_snip:
        klass = "UA-GUR-ship"
    elif "mofa" in low_snip or "korea" in low_snip:
        klass = "KR-MOFA-vessel"
    elif "iuu" in low_snip or "rfmo" in low_snip:
        klass = "IUU-RFMO"
    elif "paris" in low_snip or "mou" in low_snip:
        klass = "Paris-banned"
    elif not (snippet or "").strip():
        klass = "NO_CLASS"
    else:
        klass = "NO_CLASS"
    return {
        "authority_class": {
            "type": "choice",
            "choice": klass,
            "probabilities": {klass: 0.84},
            "confidence": 0.82,
        },
        "miss_is_clearance": {"type": "noul", "noul": 0.03},
        "winner_rule": {
            "type": "choice",
            "choice": "ABSTAIN",
            "probabilities": {"ABSTAIN": 0.9, "PICK_FRESHER": 0.05, "USE_COMPILATION": 0.05},
            "confidence": 0.88,
        },
        "evidence_strength": {
            "type": "score",
            "score": 0.28 if snippet else 0.05,
            "confidence": 0.70,
            "legend": {
                "0": "No snippet is present.",
                "1": "HTTP 200 / page cite only. Reachability is not a match.",
                "2": "Exact-string SAMPLE hit or miss on frozen identity text.",
                "3": "Independent official bulk list with bound entity resolution.",
            },
        },
    }


def compose_public_text(identity: str, snippet: str, answers: Mapping[str, Any]) -> dict[str, Any]:
    klass = str((answers.get("authority_class") or {}).get("choice") or "NO_CLASS")
    miss_p = float((answers.get("miss_is_clearance") or {}).get("noul") or 0.0)
    winner = str((answers.get("winner_rule") or {}).get("choice") or "ABSTAIN")
    strength = float((answers.get("evidence_strength") or {}).get("score") or 0.0)
    # Code owns these. Jev cannot clear, pick a winner, or open AIS.
    if klass == "REFUSED_AIS":
        maps_to = "VESSELS-E-DENY-AIS"
        verdict = "DENIED"
    elif miss_p >= 0.50:
        maps_to = "VESSELS-E-ABSTAIN"
        verdict = "BLOCKED"
    elif winner != "ABSTAIN":
        maps_to = "VESSELS-E-ABSTAIN"
        verdict = "HOLD"
    elif klass in {"KR-MOFA-vessel", "IUU-RFMO", "Paris-banned", "NO_CLASS"}:
        maps_to = "VESSELS-E-ABSTAIN"
        verdict = "HOLD"
    else:
        maps_to = "ADVISORY_ONLY"
        verdict = "HOLD"
    return {
        "schema": "szl.jev_public_text/v1",
        "engine": "typesafe.systemone",
        "model": DEFAULT_MODEL,
        "identity": identity,
        "authority_class": klass,
        "miss_is_clearance_noul": miss_p,
        "miss_is_not_clearance": True,
        "is_clearance": False,
        "winner_rule_jev": winner,
        "winner_not_picked": True,
        "evidence_strength": strength,
        "maps_to": maps_to,
        "verdict": verdict,
        "promotion": "denied",
        "not_e01": True,
        "not_e03": True,
        "does_not_run_the_kernel": True,
        "licensed_ais_admitted": False,
        "formula_authority": "NONE",
        "note": (
            "Advisory System One over public text. SAMPLE miss is not clearance. "
            "Disagreement does not pick a winner. Jev cannot open licensed AIS."
        ),
    }


def judge_public_text(identity: str, snippet: str = "", disagreement: str = "") -> dict[str, Any]:
    state = {
        "identity": {"name": identity},
        "snippet": {"text": snippet},
        "disagreement": disagreement or "UK FCDO REACHABLE_FRESH vs UK OFSI STALE_OR_THIN",
        "doctrine": {
            "version": "v11",
            "lambda": "Conjecture 1",
            "licensed_ais": "CLOSED",
            "miss_is_not_clearance": True,
        },
    }
    status = engine_status()
    if status["bound"]:
        payload_state = dict(state)
        live = call_jev_questions(payload_state, public_text_questions())
        answers = live.get("answers") if live.get("ok") else None
        source = "jev-latest" if answers else "software-fallback"
        if not answers:
            answers = fallback_public_text(identity, snippet, disagreement)
    else:
        answers = fallback_public_text(identity, snippet, disagreement)
        source = "software-fallback"
        live = {"ok": False, "reason": "TYPESAFE_API_KEY_UNBOUND", "engine": status}
    composed = compose_public_text(identity, snippet, answers)
    composed["source"] = source
    composed["engine"] = status
    composed["engine_reason"] = live.get("reason")
    composed["answers"] = answers
    return composed


def call_jev_questions(state: Mapping[str, Any], qs: Mapping[str, Any]) -> dict[str, Any]:
    status = engine_status()
    if not status["bound"]:
        return {"ok": False, "engine": status, "answers": None, "reason": "TYPESAFE_API_KEY_UNBOUND"}
    payload = {"state": dict(state), "model": DEFAULT_MODEL, "questions": dict(qs)}
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

    @app.post(f"{base}/public-text")
    async def _public_text(payload: dict[str, Any] | None = None):
        data = payload or {}
        return JSONResponse(
            judge_public_text(
                str(data.get("identity") or data.get("name") or "AURORA WAVE"),
                str(data.get("snippet") or data.get("text") or ""),
                str(data.get("disagreement") or ""),
            )
        )

    report["ok"] = True
    report["registered"] = [f"{base}/status", f"{base}/judge", f"{base}/public-text"]
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
    pub = judge_public_text("AURORA WAVE", "OFAC SDN CSV REACHABLE_FRESH last-modified Fri, 18 Sep 2026")
    check("public_text_not_clearance", pub["is_clearance"] is False and pub["miss_is_not_clearance"] is True)
    check("public_text_winner_not_picked", pub["winner_not_picked"] is True)
    check("public_text_no_ais", pub["licensed_ais_admitted"] is False)
    refused = judge_public_text("AURORA WAVE", "MarineTraffic live AIS map via pyais")
    check("public_text_refused_ais", refused["authority_class"] == "REFUSED_AIS" and refused["maps_to"] == "VESSELS-E-DENY-AIS")
    fake_clear = compose_public_text(
        "AURORA WAVE",
        "empty",
        {
            "authority_class": {"choice": "OFAC-vessel", "confidence": 0.99},
            "miss_is_clearance": {"noul": 0.99},
            "winner_rule": {"choice": "PICK_FRESHER"},
            "evidence_strength": {"score": 0.99},
        },
    )
    check("jev_cannot_grant_clearance", fake_clear["is_clearance"] is False and fake_clear["verdict"] == "BLOCKED")
    check("jev_cannot_pick_winner", fake_clear["winner_not_picked"] is True)

    failed = [n for n, ok in checks if not ok]
    print({"ok": not failed, "checks": len(checks), "failed": failed})
    raise SystemExit(1 if failed else 0)
