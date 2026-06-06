#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""pac_bayes_quorum.py — PAC-Bayes bound + Byzantine quorum, run BEFORE the mesh merges.

The UDS mesh fuses verdicts from up to five organs (a11oy, sentra, amaru, killinchu,
rosie). Before it COMMITS a merged cross-organ verdict it must answer two questions:

  1. Is there a Byzantine-safe quorum? (n ≥ 3f+1, agreement ≥ 2f+1 — PBFT.) If a minority
     of organs disagree we must not merge their decision; if no quorum exists we REFUSE.
  2. How confident is the merged verdict given a finite observation window? The Catoni
     PAC-Bayes bound gives a high-probability upper bound on the merged-verdict risk so
     the mesh attaches an honest confidence interval instead of over-trusting agreement.

Combining them: the mesh only MERGES when (quorum holds) AND (PAC-Bayes confidence ≥ floor).

PAC-Bayes — McAllester (COLT 1999; ML 51(1):5–21, 2003); Catoni (IMS LN 56, 2007).
Byzantine quorum — Lamport/Shostak/Pease (1982); Castro/Liskov PBFT (OSDI 1999).

Lean: ``Lutar/PACBayes.lean :: pacBayesBound_eq_add_slack`` (L165, sorry-free) and
``Lutar/KhipuConsensus.lean :: faultyCount`` (L116) with BFT safety as **Conjecture 2**
(``khipu_consensus_safety`` L174 — NEVER a theorem). Permalinks pinned at commit abd58d1.

CITATION: thesis_v22.pdf §2  ·  LEAN: PACBayes.lean::pacBayesBound_eq_add_slack + KhipuConsensus.lean::faultyCount
"""
from __future__ import annotations

import math

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = ("Lutar/PACBayes.lean::pacBayesBound_eq_add_slack + "
                "Lutar/KhipuConsensus.lean::faultyCount (Conjecture 2 safety)")
LEAN_PERMALINK_PACBAYES = (
    "https://github.com/szl-holdings/lutar-lean/blob/"
    "abd58d159f1bdb79a017d71a6b94ab160ead8d9d/Lutar/PACBayes.lean#L165")
LEAN_PERMALINK_QUORUM = (
    "https://github.com/szl-holdings/lutar-lean/blob/"
    "abd58d159f1bdb79a017d71a6b94ab160ead8d9d/Lutar/KhipuConsensus.lean#L116")


def pac_bayes_bound(emp_risk: float, n: int, kl: float = 0.0, delta: float = 0.05) -> dict:
    """McAllester/Bégin additive PAC-Bayes upper bound on merged-verdict risk."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not (0.0 < delta < 1.0):
        raise ValueError("delta in (0,1)")
    slack = math.sqrt((kl + math.log(2.0 * math.sqrt(n) / delta)) / (2.0 * n))
    risk = min(1.0, emp_risk + slack)
    return {"risk_upper_bound": round(risk, 6),
            "confidence_lower_bound": round(max(0.0, 1.0 - risk), 6),
            "empirical_risk": round(emp_risk, 6), "slack": round(slack, 6),
            "n": n, "kl": kl, "delta": delta}


def byzantine_quorum(verdicts: dict, f: int = 1) -> dict:
    """Quorum over organ verdicts. verdicts: {organ: decision}. n≥3f+1, agree≥2f+1.

    Returns the majority decision iff a 2f+1 quorum exists and the cluster is BFT-feasible;
    otherwise REFUSE. The disagreeing minority is flagged as suspected-byzantine.
    """
    n = len(verdicts)
    feasible = n >= 3 * f + 1
    quorum = 2 * f + 1
    counts: dict = {}
    for organ, dec in verdicts.items():
        key = json_key(dec)
        counts.setdefault(key, []).append(organ)
    ranked = sorted(counts.items(), key=lambda kv: len(kv[1]), reverse=True)
    top_key, top_members = ranked[0]
    agreement = len(top_members)
    has_quorum = feasible and agreement >= quorum
    minority = [o for k, members in ranked[1:] for o in members]
    return {
        "n": n, "f": f, "required_quorum": quorum, "bft_feasible": feasible,
        "agreement_count": agreement, "quorum_met": has_quorum,
        "merged_decision": (unjson_key(top_key) if has_quorum else None),
        "agreeing_organs": top_members, "suspected_byzantine": minority,
        "verdict": ("MERGE" if has_quorum else "REFUSE"),
    }


def json_key(v):
    import json as _j
    return _j.dumps(v, sort_keys=True)


def unjson_key(k):
    import json as _j
    return _j.loads(k)


def gate_merge(verdicts: dict, f: int = 1, n_obs: int = 64, emp_risk: float | None = None,
               kl: float = 0.0, delta: float = 0.05, confidence_floor: float = 0.5) -> dict:
    """Combined gate the mesh runs BEFORE merging. Returns allow/deny + both sub-results.

    emp_risk defaults to the disagreement fraction among organs (honest, data-driven).
    """
    q = byzantine_quorum(verdicts, f=f)
    if emp_risk is None:
        n_organs = max(q["n"], 1)
        emp_risk = len(q["suspected_byzantine"]) / n_organs
    pb = pac_bayes_bound(emp_risk=emp_risk, n=n_obs, kl=kl, delta=delta)
    allow = bool(q["quorum_met"] and pb["confidence_lower_bound"] >= confidence_floor)
    return {
        "value": allow,
        "allow_merge": allow,
        "merged_decision": (q["merged_decision"] if allow else None),
        "quorum": q,
        "pac_bayes": pb,
        "confidence_floor": confidence_floor,
        "reason": ("quorum+confidence OK" if allow else
                   ("no BFT quorum" if not q["quorum_met"] else "confidence below floor")),
        "citation": CITATION,
        "lean_theorem": LEAN_THEOREM,
    }


__all__ = ["pac_bayes_bound", "byzantine_quorum", "gate_merge", "CITATION", "LEAN_THEOREM",
           "LEAN_PERMALINK_PACBAYES", "LEAN_PERMALINK_QUORUM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
