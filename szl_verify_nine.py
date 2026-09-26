# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1. Trust ceiling 0.97 is policy.
"""szl_verify_nine.py — locked admit math + 9-step labels for the estate.

TypeSafe / Jev may emit Choice / Noul / Score. Composite scoring in the
TypeSafe docs is a weighted SUM in code. That sum is a preference roll-up.
It is never the admit function.

Admit is the non-compensating geometric mean:

    G = exp(Σ w_i log x_i / Σ w_i)
    admit ⇔ G ≥ POLICY_TAU ∧ min(x) > 0
    dang  ⇔ (AM ≥ τ) ∧ (GM < τ)

POLICY_TAU = 0.80 on public /verify.
FRONTIER_DEFAULT_TAU = 0.70 is printed, not used on /verify.
A model, Jev distribution, HTTP 200, or arithmetic mean cannot ALLOW.

Stdlib only. Additive. Import from szl_public_verify when wiring the POST.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

POLICY_TAU = 0.80
FRONTIER_DEFAULT_TAU = 0.70
TRUST_CEILING = 0.97
LAMBDA_POSTURE = "Conjecture 1"
LOCKED_8 = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")

VERIFIED = "VERIFIED"
MISMATCH = "MISMATCH"
UNSIGNED_LOCAL = "UNSIGNED-LOCAL"
UNAVAILABLE = "UNAVAILABLE"
BLOCKED = "BLOCKED"
ADMITTED = "ADMITTED"
CONJECTURE = "CONJECTURE"
MEASURED = "MEASURED"
DENY = "DENY"

DEMO_VECTORS = (
    ("nominal", (0.95, 0.92, 0.88, 0.90), True, False),
    ("provenance_drop", (0.95, 0.04, 0.88, 0.90), False, False),
    ("liar", (0.97, 0.97, 0.97, 0.02), False, False),
    ("hidden_weak", (0.95, 0.95, 0.95, 0.40), False, True),
    ("false_friend", (0.95, 0.92, 0.90, 0.55), True, False),
)

_PROVEN = (
    "proven theorem",
    "proven",
    "theorem",
    "proved",
    "never a conjecture",
    "uniqueness proven",
    "trust 1.0",
    "trust=1",
)


def weighted_gm(scores: Sequence[float], weights: Sequence[float] | None = None) -> float:
    if not scores:
        return 0.0
    if any(s < 0 or not math.isfinite(s) for s in scores):
        return float("nan")
    if any(s == 0 for s in scores):
        return 0.0
    w = list(weights) if weights is not None else [1.0] * len(scores)
    wsum = sum(w)
    return math.exp(sum(wi * math.log(si) for si, wi in zip(scores, w)) / wsum)


def weighted_am(scores: Sequence[float], weights: Sequence[float] | None = None) -> float:
    if not scores:
        return 0.0
    w = list(weights) if weights is not None else [1.0] * len(scores)
    return sum(si * wi for si, wi in zip(scores, w)) / sum(w)


def admit(scores: Sequence[float], tau: float = POLICY_TAU, weights: Sequence[float] | None = None) -> dict[str, Any]:
    gm = weighted_gm(scores, weights)
    am = weighted_am(scores, weights)
    mn = min(scores) if scores else 0.0
    ok = bool(math.isfinite(gm) and gm >= tau and mn > 0)
    dang = bool(am >= tau and (not math.isfinite(gm) or gm < tau))
    return {
        "gm": None if not math.isfinite(gm) else round(gm, 4),
        "am": round(am, 4) if math.isfinite(am) else None,
        "min": round(mn, 4),
        "tau": tau,
        "admit": ok,
        "dang": dang,
        "status": ADMITTED if ok else DENY,
    }


def lambda_posture(claim: str | None) -> dict[str, Any]:
    text = (claim or "").lower()
    if text and any(tok in text for tok in _PROVEN):
        return {
            "status": BLOCKED,
            "lambda": LAMBDA_POSTURE,
            "detail": "Λ claim treats uniqueness as proven/theorem — fail closed; uniqueness is Conjecture 1, never a theorem",
        }
    return {
        "status": CONJECTURE,
        "lambda": LAMBDA_POSTURE,
        "detail": (
            f"{LAMBDA_POSTURE} — never a theorem. "
            f"POLICY τ={POLICY_TAU:.2f} (frontier-default={FRONTIER_DEFAULT_TAU:.2f}, "
            f"ceiling={TRUST_CEILING:.2f})"
        ),
    }


def typesafe_role() -> dict[str, Any]:
    return {
        "provider": "typesafe.systemone",
        "model": "jev-latest",
        "primitives": ["choice", "noul", "score"],
        "citation_lattice": ["supports", "contradicts", "says_nothing"],
        "composite_scoring": "weighted_sum_in_code",
        "admit_function": "weighted_geometric_mean",
        "jev_can_allow": False,
        "jev_can_grant_live": False,
        "jev_can_close_conjecture_1": False,
        "missing_key": UNAVAILABLE,
        "note": (
            "Jev judges claim/evidence. Code owns promotion. "
            "TypeSafe composite scoring is arithmetic — it may feed axes, it must not admit."
        ),
    }


def model_contract() -> dict[str, Any]:
    """Bytes a training card, router, or controller can pin. Not weights."""
    return {
        "schema": "szl.model_admit_contract/v1",
        "doctrine": "v11 LOCKED",
        "lambda": LAMBDA_POSTURE,
        "locked_8": list(LOCKED_8),
        "trust_ceiling": TRUST_CEILING,
        "policy_tau": POLICY_TAU,
        "frontier_default_tau": FRONTIER_DEFAULT_TAU,
        "admit": "geometric_mean",
        "witness_only": "arithmetic_mean",
        "hidden_weak": [0.95, 0.95, 0.95, 0.40],
        "labels": [
            VERIFIED, MISMATCH, UNSIGNED_LOCAL, UNAVAILABLE,
            BLOCKED, ADMITTED, CONJECTURE, MEASURED,
        ],
        "typesafe": typesafe_role(),
        "production_authorized": False,
        "http_200_is_live": False,
    }


def nine_steps(payload: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    body = dict(payload or {})
    axes = body.get("axes")
    gate = admit(list(axes), POLICY_TAU) if isinstance(axes, (list, tuple)) and axes else {
        "status": UNAVAILABLE,
        "detail": "no axes — GM not run",
        "optional": True,
    }
    return [
        {"check": "schema", "status": VERIFIED if body else UNAVAILABLE, "detail": "parse"},
        {"check": "pae", "status": UNAVAILABLE, "optional": True, "detail": "no _pae_sha256 — compare-unavailable"},
        {"check": "signature", "status": UNSIGNED_LOCAL, "detail": "no signature in this helper"},
        {"check": "hash_chain", "status": UNAVAILABLE, "optional": True, "detail": "order, not non-equivocation"},
        {"check": "rekor", "status": UNAVAILABLE, "optional": True, "detail": "no Rekor/SCITT bundle"},
        {"check": "gate", **gate},
        {"check": "energy", "status": UNAVAILABLE, "optional": True, "detail": "absent meter is not 0.0 J"},
        {"check": "lambda_posture", **lambda_posture(str(body.get("lambda_posture") or body.get("lambda") or ""))},
        {"check": "optional_tiers", "status": UNAVAILABLE, "optional": True, "detail": "C2PA/OTS/OMS/ZK absent"},
    ]


def demo_table() -> list[dict[str, Any]]:
    rows = []
    for name, axes, expect_admit, expect_dang in DEMO_VECTORS:
        g = admit(axes, POLICY_TAU)
        g["name"] = name
        g["axes"] = list(axes)
        g["ok"] = g["admit"] is expect_admit and g["dang"] is expect_dang
        rows.append(g)
    liar70 = admit((0.97, 0.97, 0.97, 0.02), FRONTIER_DEFAULT_TAU)
    liar70["name"] = "liar@0.70"
    rows.append(liar70)
    return rows


def selftest() -> dict[str, Any]:
    failed: list[str] = []
    rows = demo_table()
    for row in rows:
        if row["name"] == "liar@0.70":
            if not row["dang"] or row["admit"]:
                failed.append("liar@0.70")
            continue
        if not row.get("ok"):
            failed.append(row["name"])
    hidden = next(r for r in rows if r["name"] == "hidden_weak")
    if hidden["gm"] != 0.7653 or hidden["am"] != 0.8125:
        failed.append("hidden_weak_4dp")
    if admit((0.95, 0.92, 0.88, 0.90))["admit"] is not True:
        failed.append("nominal")
    blocked = lambda_posture("Λ is a proven theorem")  # negative fixture; uniqueness is Conjecture 1, never a theorem
    if blocked["status"] != BLOCKED:
        failed.append("lambda_block")
    role = typesafe_role()
    if role["jev_can_allow"] or role["admit_function"] != "weighted_geometric_mean":
        failed.append("typesafe_role")
    return {"ok": not failed, "failed": failed, "rows": rows, "contract": model_contract()}


if __name__ == "__main__":
    report = selftest()
    for row in report["rows"]:
        print(
            f"{row['name']:18} GM={row['gm']} AM={row['am']} min={row['min']} "
            f"admit={row['admit']} dang={row['dang']}"
        )
    print("SELFTEST", "PASS" if report["ok"] else "FAIL", report["failed"])
    raise SystemExit(0 if report["ok"] else 1)
