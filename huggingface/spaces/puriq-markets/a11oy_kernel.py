#!/usr/bin/env python3
"""A11oy Decision Integrity Kernel.

Fail-closed evaluation of a Decision Integrity Graph. Formulas have
authority NONE. Models, market signals and formulas never authorize.
No network. No side effects. Emits a signed receipt digest.

This is the Python reference kernel. The TypeScript runtime in
src/lib/engine mirrors the same contracts so the live app can evaluate
without spawning a process.
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

VERSION = "8.0.0"
SCHEMA = "szl.decision-integrity-kernel/v8"

FRESHNESS_WEIGHT = {
    "LIVE": 1.0,
    "CACHED": 0.7,
    "STALE": 0.25,
    "UNAVAILABLE": 0.0,
}

MAX_FUEL = 12
COMPLEXITY_CAP = 48

AUTHORITY_PHRASES = (
    "authorized to",
    "you should buy",
    "you should sell",
    "you must file",
    "certified value",
    "certified appraisal",
    "this is legal advice",
    "this is investment advice",
    "this is financial advice",
    "place the order",
    "place an order",
    "i approve",
    "i authorize",
    "permission granted",
    "you are approved",
    "execute the trade",
    "automatic offer",
    "i hereby grant",
    "authority is granted",
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def f1_graph_identity(graph: dict[str, Any]) -> dict[str, Any]:
    digest = sha256_hex(canonical_json(graph))
    return {
        "id": "F1",
        "role": "decision/evidence graph structural identity",
        "authority": "NONE",
        "value": digest,
        "limit": "does not prove source truth or domain correctness",
    }


def f4_aggregate(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if not evidence:
        score = 0.0
    else:
        total = sum(float(item.get("weight", 0)) for item in evidence)
        score = max(0.0, min(1.0, total / max(len(evidence), 1)))
    return {
        "id": "F4",
        "role": "bounded multi-signal aggregation",
        "authority": "NONE",
        "value": round(score, 4),
        "limit": "does not prove optimal weights or calibrated probability",
    }


def f7_freshness(sources: list[dict[str, Any]]) -> dict[str, Any]:
    if not sources:
        score = 0.0
    else:
        score = sum(
            FRESHNESS_WEIGHT.get(str(item.get("freshness", "UNAVAILABLE")), 0.0)
            for item in sources
        ) / len(sources)
    return {
        "id": "F7",
        "role": "provenance and freshness weighting",
        "authority": "NONE",
        "value": round(score, 4),
        "limit": "does not prove source truth, completeness or licensing",
    }


def f11_action_space(
    allowed: list[str],
    prohibited: list[str],
    proposed: str | None,
) -> dict[str, Any]:
    remaining = [item for item in allowed if item not in prohibited]
    return {
        "id": "F11",
        "role": "candidate action-space narrowing",
        "authority": "NONE",
        "value": remaining,
        "proposed_in_space": proposed in remaining if proposed else False,
        "limit": "does not prove a remaining action is safe or authorized",
    }


def f12_sequence(chain_index: int, chain_len: int) -> dict[str, Any]:
    denom = max(chain_len, 1)
    value = round(min(1.0, max(0.0, chain_index / denom)), 4)
    return {
        "id": "F12",
        "role": "bounded schedule/sequence surrogate",
        "authority": "NONE",
        "value": value,
        "limit": "does not prove real-world feasibility or optimality",
    }


def f18_complexity(payload: dict[str, Any]) -> dict[str, Any]:
    tokens = len(json.dumps(payload, ensure_ascii=False))
    ratio = tokens / (COMPLEXITY_CAP * 80)
    return {
        "id": "F18",
        "role": "description and context complexity cap",
        "authority": "NONE",
        "value": round(min(1.0, ratio), 4),
        "over_cap": ratio > 1.0,
        "limit": "does not prove sufficient evidence or privacy",
    }


def f19_fuel(used: int) -> dict[str, Any]:
    remaining = max(0, MAX_FUEL - used)
    return {
        "id": "F19",
        "role": "finite internal workflow fuel",
        "authority": "NONE",
        "value": remaining,
        "max": MAX_FUEL,
        "limit": "does not prove general program termination or external shutdown",
    }


def f22_paths(graph: dict[str, Any]) -> dict[str, Any]:
    edges = graph.get("edges") or []
    nodes = {item.get("id") for item in graph.get("nodes") or []}
    inbound = {node: 0 for node in nodes}
    for edge in edges:
        target = edge.get("to")
        if target in inbound:
            inbound[target] += 1
    aggregation = round(
        sum(inbound.values()) / max(len(nodes), 1),
        4,
    )
    return {
        "id": "F22",
        "role": "bounded graph-path aggregation",
        "authority": "NONE",
        "value": aggregation,
        "edge_count": len(edges),
        "limit": "does not prove causality or outcome",
    }


def lambda_posture(
    evidence_score: float,
    freshness: float,
    contradiction_count: int,
    fuel: int,
    rights_denied: int,
) -> dict[str, Any]:
    axes = {
        "evidence": evidence_score,
        "freshness": freshness,
        "contradiction_pressure": min(1.0, contradiction_count / 3.0),
        "fuel": fuel / MAX_FUEL,
        "rights": 1.0 if rights_denied == 0 else 0.0,
    }
    return {
        "id": "LAMBDA",
        "role": "advisory multi-axis posture",
        "authority": "NONE",
        "status": "ADVISORY_CONJECTURAL",
        "value": {key: round(val, 4) for key, val in axes.items()},
        "limit": "Conjecture/advisory only; never grants authority",
    }


def _hits_prohibited(proposed: str, phrase: str) -> bool:
    proposed_l = proposed.lower()
    phrase_l = phrase.lower()
    head = phrase_l.split(",")[0].split("/")[0].strip()
    if len(head) >= 8 and head in proposed_l:
        return True
    if len(proposed_l) >= 8 and proposed_l in phrase_l:
        return True
    return False


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    graph = payload.get("graph") or {"nodes": [], "edges": []}
    sources = payload.get("sources") or []
    evidence = payload.get("evidence") or []
    contradictions = payload.get("contradictions") or []
    allowed = payload.get("allowed_actions") or []
    prohibited = payload.get("prohibited_actions") or []
    proposed = payload.get("proposed_action")
    used_fuel = int(payload.get("used_fuel") or 0)
    chain_index = int(payload.get("chain_index") or 0)
    chain_len = int(payload.get("chain_len") or 10)
    prior_approval = bool(payload.get("prior_approval"))

    formulas = [
        f1_graph_identity(graph),
        f4_aggregate(evidence),
        f7_freshness(sources),
        f11_action_space(allowed, prohibited, proposed),
        f12_sequence(chain_index, chain_len),
        f18_complexity(payload),
        f19_fuel(used_fuel),
        f22_paths(graph),
    ]
    f4 = formulas[1]["value"]
    f7 = formulas[2]["value"]
    f11 = formulas[3]
    f19 = formulas[6]["value"]
    rights_denied = sum(1 for item in sources if item.get("rights") == "DENIED")
    stale = sum(1 for item in sources if item.get("freshness") in {"STALE", "UNAVAILABLE"})
    formulas.append(
        lambda_posture(float(f4), float(f7), len(contradictions), int(f19), rights_denied)
    )

    reason_codes: list[str] = []
    state = "PROPOSED"

    if proposed and any(
        _hits_prohibited(proposed, phrase) for phrase in prohibited
    ):
        state = "DENIED"
        reason_codes.append("PROHIBITED_ACTION")
    elif proposed and not f11["proposed_in_space"]:
        state = "DENIED"
        reason_codes.append("ACTION_NOT_IN_SPACE")
    elif rights_denied:
        state = "DENIED"
        reason_codes.append("DATA_RIGHTS_DENIED")
    elif int(f19) <= 0:
        state = "DENIED"
        reason_codes.append("WORKFLOW_FUEL_EXHAUSTED")
    elif contradictions:
        state = "ESCALATED"
        reason_codes.append("UNRESOLVED_CONTRADICTION")
    elif stale:
        state = "ABSTAINED"
        reason_codes.append("STALE_OR_UNAVAILABLE_SOURCE")
    elif not prior_approval:
        state = "AWAITING_APPROVAL"
        reason_codes.append("HUMAN_APPROVAL_REQUIRED")
    else:
        state = "APPROVED"
        reason_codes.append("HUMAN_AUTHORIZED_BOUNDED_ACTION")

    receipt_body = {
        "schema": "szl.governed-receipt/v8",
        "kernel": VERSION,
        "vertical_id": payload.get("vertical_id"),
        "case_id": payload.get("case_id"),
        "proposed_action": proposed,
        "state": state,
        "reason_codes": reason_codes,
        "formula_authority": "NONE",
        "model_grants_authority": False,
        "formula_grants_authority": False,
        "market_signal_grants_authority": False,
        "limitations": [
            "Demonstration kernel. Does not prove production readiness.",
            "Formulas do not grant authority.",
            "No transaction, trading, legal-advice or offensive action is authorized.",
        ],
        "formulas": formulas,
    }
    digest = sha256_hex(canonical_json(receipt_body))
    receipt_body["digest"] = digest

    return {
        "schema": SCHEMA,
        "kernel_version": VERSION,
        "engine": "python",
        "state": state,
        "reason_codes": reason_codes,
        "formulas": formulas,
        "receipt": receipt_body,
        "policy": {
            "default_effect": "DENY",
            "model_grants_authority": False,
            "formula_grants_authority": False,
            "market_signal_grants_authority": False,
        },
    }


def scan_memo(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    hits = [phrase for phrase in AUTHORITY_PHRASES if phrase in lower]
    return {
        "claimed_authority": len(hits) > 0,
        "hits": hits,
    }


def replay_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    stored = str(receipt.get("digest") or "")
    body = {key: value for key, value in receipt.items() if key != "digest"}
    computed = sha256_hex(canonical_json(body))
    return {
        "stored": stored,
        "computed": computed,
        "hold": stored == computed,
    }


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "evaluate"
    raw = sys.stdin.read()
    if not raw:
        print(json.dumps({"error": "expected JSON on stdin"}, indent=2))
        return 2
    payload = json.loads(raw)
    if command == "scan":
        result = scan_memo(str(payload.get("text") or ""))
    elif command == "replay":
        result = replay_receipt(payload if isinstance(payload, dict) else {})
    else:
        result = evaluate(payload)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
