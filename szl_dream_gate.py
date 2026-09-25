# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1. Trust ceiling 0.97 is policy.
"""szl_dream_gate.py — govern imagined capabilities without promoting them.

The request "make it all AGI and things no one has dreamed of" is itself
a typed object: a DREAM. Dreams get hash-linked unknown receipts.
They never become LIVE, ALLOW, ALL_DONE, or compiled-kernel v1.

This is not AGI. It is the opposite product move: imagination is first-class
and fail-closed. A wish cannot close an estate gate.

Stdlib only. Additive register(); never replace existing routes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

TRUST_CEILING = 0.97
CONJECTURE_1 = "Λ uniqueness remains Conjecture 1 — advisory, never a theorem."
SCHEMA = "szl.dream_gate/v1"

# Promotion of these phrases is forbidden even if every child later passes.
_FORBIDDEN_PROMOTION = (
    "agi",
    "artificial general intelligence",
    "superintelligence",
    "super-intelligence",
    "sentient",
    "conscious machine",
    "all_done",
    "fully operational",
    "trust 1.0",
    "trust=1",
    "lambda theorem",
    "Λ theorem",
    "hatun allow",
)

_DREAM_HINTS = (
    "dream",
    "imagine",
    "no one has dreamed",
    "undreamed",
    "wish",
    "someday",
    "will be able",
    "make it all",
    "agi",
)

_MEASURED_HINTS = (
    "http 200",
    "measured",
    "git_sha",
    "doctrine v11 locked",
)


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def classify_claim(text: str) -> dict[str, Any]:
    """Bucket a statement as MEASURED, DREAMED, or FORBIDDEN_PROMOTION."""
    raw = str(text or "")
    n = _norm(raw)
    if not n:
        return {
            "kind": "UNKNOWN",
            "promote": False,
            "reason": "empty claim is unknown, not measured",
            "agi_claim": False,
        }
    if any(tok in n for tok in _FORBIDDEN_PROMOTION):
        return {
            "kind": "FORBIDDEN_PROMOTION",
            "promote": False,
            "reason": "AGI / completeness / 1.0 / theorem-Λ cannot be promoted",
            "agi_claim": "agi" in n or "artificial general intelligence" in n,
        }
    if any(tok in n for tok in _DREAM_HINTS):
        return {
            "kind": "DREAMED",
            "promote": False,
            "reason": "imagined capability has no measured child",
            "agi_claim": False,
        }
    if any(tok in n for tok in _MEASURED_HINTS):
        return {
            "kind": "MEASURED_LANGUAGE",
            "promote": False,
            "reason": "measured language still requires an independent child proof",
            "agi_claim": False,
        }
    return {
        "kind": "DREAMED",
        "promote": False,
        "reason": "unclassified capability defaults to DREAMED",
        "agi_claim": False,
    }


def hash_unknown(statement: str, *, prior: str | None = None) -> dict[str, Any]:
    """Hash-linked unknown receipt. Hash-linked is not SIGNED."""
    body = {
        "schema": SCHEMA,
        "statement": str(statement or ""),
        "kind": classify_claim(statement)["kind"],
        "prior": prior,
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
        "lambda": "Conjecture 1",
        "signed": False,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha3_256(canonical).hexdigest()
    return {
        **body,
        "hash": f"sha3-256:{digest}",
        "honesty": "UNSIGNED-LOCAL",
        "note": "hash-linked is not SIGNED; DSSE remains a separate cosign concern",
    }


def counterfactual_requirements(dream: str) -> dict[str, Any]:
    """Name what would have to be true. Naming is not satisfying."""
    cls = classify_claim(dream)
    required = [
        "console_journey:EXECUTED_PASS",
        "lyte_runtime:EXECUTED_PASS",
        "compiled_kernel.v1:native_load_abi",
        "honest.trust_ceiling:emitted_in_image",
        "minicpm:held_out_eval",
        "khipu:held_out_eval",
        "brain_private:authorized_bind",
    ]
    return {
        "dream": dream,
        "classification": cls,
        "would_require": required,
        "satisfied": [],
        "promote": False,
        "all_done": False,
        "reason": "a list of requirements is not evidence those requirements passed",
    }


def promote(dream: str, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Promotion is denied. Evidence may be recorded; it cannot mint AGI."""
    ev = dict(evidence or {})
    cls = classify_claim(dream)
    if cls["kind"] == "FORBIDDEN_PROMOTION" or cls.get("agi_claim"):
        return {
            "decision": "BLOCKED",
            "honesty": "SOFTWARE",
            "kind": cls["kind"],
            "agi_claim": False,
            "reason": "F22 isolation — dreamed AGI cannot be promoted to LIVE",
            "conjecture": CONJECTURE_1,
            "evidence_keys": sorted(ev.keys()),
        }
    if ev.get("all_done") is True:
        return {
            "decision": "BLOCKED",
            "honesty": "SOFTWARE",
            "kind": "FORBIDDEN_PROMOTION",
            "agi_claim": False,
            "reason": "ALL_DONE in evidence is a wish, not a proof projection",
            "conjecture": CONJECTURE_1,
            "evidence_keys": sorted(ev.keys()),
        }
    return {
        "decision": "HOLD",
        "honesty": "HOLD",
        "kind": cls["kind"],
        "agi_claim": False,
        "reason": "human Hatun review required; dreams stay dreamed",
        "conjecture": CONJECTURE_1,
        "evidence_keys": sorted(ev.keys()),
    }


def negative_knowledge(known_unknowns: Iterable[str] | None = None) -> dict[str, Any]:
    """First-class inventory of what this organ refuses to know."""
    items = [str(x) for x in (known_unknowns or []) if str(x).strip()]
    defaults = [
        "compiled kernel v1 native load",
        "private Brain graph bind",
        "MiniCPM held-out promotion",
        "Khipu lineage weight recompute",
        "Λ uniqueness as theorem",
        "trust 1.0 as LIVE score",
        "AGI as product state",
    ]
    catalog = items or defaults
    linked = [hash_unknown(s) for s in catalog]
    return {
        "schema": SCHEMA,
        "count": len(linked),
        "zero_stays_zero": len(linked) == 0,
        "entries": linked,
        "agi_claim": False,
        "note": "negative knowledge is SOFTWARE. It is not omniscience.",
    }


def dream_status() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "agi_claim": False,
        "lambda": "Conjecture 1",
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
        "promotion": "denied",
        "estate_gate": "HOLD",
        "note": "Imagination is admitted. Promotion is not.",
    }


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    report = {"ok": False, "registered": []}
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        return report

    base = f"/api/{ns}/v1/dream"

    @app.get(f"{base}/status")
    async def _status():
        return JSONResponse(dream_status())

    @app.post(f"{base}/classify")
    async def _classify(payload: dict[str, Any] | None = None):
        data = payload or {}
        return JSONResponse(classify_claim(str(data.get("text") or data.get("claim") or "")))

    @app.post(f"{base}/promote")
    async def _promote(payload: dict[str, Any] | None = None):
        data = payload or {}
        return JSONResponse(promote(str(data.get("dream") or data.get("text") or ""), data.get("evidence")))

    @app.get(f"{base}/unknowns")
    async def _unknowns():
        return JSONResponse(negative_knowledge())

    report["ok"] = True
    report["registered"] = [
        f"{base}/status",
        f"{base}/classify",
        f"{base}/promote",
        f"{base}/unknowns",
    ]
    return report


if __name__ == "__main__":
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, ok))
        print(("PASS" if ok else "FAIL"), name)

    c = classify_claim("make it all agi and things no one has dreamed of")
    check("agi_is_forbidden", c["kind"] == "FORBIDDEN_PROMOTION" and c["promote"] is False)
    check("empty_unknown", classify_claim("")["kind"] == "UNKNOWN")
    p = promote("artificial general intelligence", {"all_done": True, "http": 200})
    check("cannot_promote_agi", p["decision"] == "BLOCKED" and p["agi_claim"] is False)
    p2 = promote("a quieter operator shell", {"http": 200})
    check("ordinary_dream_hold", p2["decision"] == "HOLD")
    u = hash_unknown("compiled kernel v1")
    check("hash_linked_not_signed", u["signed"] is False and u["honesty"] == "UNSIGNED-LOCAL" and u["hash"].startswith("sha3-256:"))
    u2 = hash_unknown("compiled kernel v1", prior=u["hash"])
    check("hash_changes_with_prior", u["hash"] != u2["hash"])
    cf = counterfactual_requirements("undreamed operator")
    check("counterfactual_not_done", cf["all_done"] is False and cf["satisfied"] == [])
    nk = negative_knowledge()
    check("negative_knowledge_nonzero", nk["count"] > 0 and nk["agi_claim"] is False)
    check("status_not_agi", dream_status()["agi_claim"] is False)
    failed = [n for n, ok in checks if not ok]
    print({"ok": not failed, "checks": len(checks), "failed": failed})
    raise SystemExit(1 if failed else 0)
