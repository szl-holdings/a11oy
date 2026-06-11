"""szl_allodial.py — SZL Holdings "Allodial AI" sovereignty formula set.

EXPERIMENTAL-tier. PROPOSED engineering gate — adds NOTHING to the locked-8.
Λ stays Conjecture 1. Trust never 100%. No fabricated data. 0 runtime CDN.

Allodial title = ownership held ABSOLUTELY with no superior overlord (opposite of
feudal tenure). The digital analogue: an operator holds the governed-AI substrate
(model + weights + data) outright, on-prem / air-gap-capable, with a verifiable
provenance "chain of title" — no commercial overlord. Honest limit: like allodial
land, never literally absolute (lawful authority still applies).

Every formula below is DERIVED FROM PUBLISHED PRIOR ART and cites its real author;
SZL claims NONE as its own discovery. SZL's only contribution is the specific
AI-relevant dimension choice + the composition.

Citations (real, verified):
  * Allodial title (concept): en.wikipedia.org/wiki/Allodial_title; Nevada NRS 361.900-361.920.
  * Goguen & Meseguer (1982), "Security Policies and Security Models", IEEE S&P —
    non-interference Definition 4 (the formal "no external overlord influence" property).
  * Denning (1976), "A Lattice Model of Secure Information Flow", CACM 19(5),
    DOI:10.1145/360051.360056 — control forms a complete lattice; ⊤ = the allodial element.
  * EU Cloud Sovereignty Framework (2025) — SovScore = Σ (Score(SOVn)/Max(SOVn))·wn,
    SEAL 0-4 assurance scale.
  * Herfindahl-Hirschman Index (HHI) = Σ sᵢ²  — dependency-concentration measure.
  * SLSA v1.1 (Approved Apr 2025) — adds Verification Summary Attestation (VSA):
    https://slsa.dev/spec/v1.1/verification_summary ; announce: https://slsa.dev/blog
  * Sello / "Notarized Agents: Receiver-Attested Confidential Receipts for AI Agent
    Actions", Juan Figuera, arXiv:2606.04193 (2026): https://arxiv.org/abs/2606.04193

Routes:  GET /api/<ns>/v1/allodial/{summary,score,dci,seal,noninterference,lattice,standards}
"""
from __future__ import annotations

from typing import Sequence

# ── SEAL scale (EU CSF): Sovereignty Effectiveness Assurance Level 0..4 ──────
SEAL_SCALE = {
    0: "feudal extreme — entirely governed by external parties",
    1: "contractual residency only",
    2: "operational controls, external dependency remains",
    3: "strong operator control, minor external dependency",
    4: "allodial analogue — full operator control, no critical external dependency",
}

# The AI-relevant sovereignty dimensions SZL scores (SZL's specific dimension
# choice; the scoring math itself is EU-CSF + HHI prior art).
ALLODIAL_DIMENSIONS = (
    ("model_weights", "Operator holds the model weights (self-hostable / open)"),
    ("inference_compute", "Inference runs on operator hardware (on-prem / air-gap)"),
    ("data_residency", "Data never leaves the operator's jurisdictional boundary"),
    ("chain_of_title", "Verifiable provenance receipts (in-toto/SLSA/cosign/Rekor)"),
    ("governance_keys", "Operator holds signing/policy keys; governance enforced locally"),
)

DOCTRINE = {
    "tier": "EXPERIMENTAL / PROPOSED engineering gate",
    "locked_count_unchanged": True,
    "lambda": "Conjecture 1 (NEVER a theorem)",
    "allodial_is_formal_lambda": False,
    "trust_never_100": True,
    "honest_limit": ("Like allodial land, Allodial AI is not literally absolute — "
                     "lawful authority (regulatory compliance, lawful process, "
                     "forfeiture, eminent-domain-style state power) still applies. "
                     "Allodial = no commercial overlord, NOT above the law."),
    "rejects": "sovereign-citizen / 'allodial land patent' pseudolegal fringe — "
               "claim is architectural + governance, anchored to real statutes & standards.",
}


def dependency_concentration_index(shares: Sequence[float]) -> float:
    """DCI = HHI = Σ sᵢ²  over external AI-supply-chain dependency shares.

    shares: fractional dependency shares (model weights, inference compute, API
    calls, training-data sources, ...). DCI=1 -> single overlord controls all
    (max feudal); DCI->0 -> distributed/local (max sovereignty). Source: HHI.
    """
    if not shares:
        return 0.0
    total = float(sum(shares))
    if total <= 0:
        return 0.0
    norm = [max(0.0, float(s)) / total for s in shares]
    return float(sum(s * s for s in norm))


def allodial_score(seals: Sequence[int], weights: Sequence[float] | None,
                   dep_shares: Sequence[float]) -> dict:
    """Allodial Sovereignty Score 𝒜 ∈ [0,100].

        𝒜 = [ Σ_k w_k · (SEAL_k / 4) ] × (1 − DCI) × 100

    Derived entirely from EU CSF (weighted SEAL sum) + HHI (the (1−DCI) lock-in
    penalty). 𝒜=100 -> fully allodial (SEAL-4 everywhere, DCI=0); 𝒜=0 -> fully
    feudal. ENGINEERING GATE: dimension weights require empirical calibration.
    """
    n = len(seals)
    if n == 0:
        return {"status": "out_of_domain", "reason": "no dimensions"}
    if weights is None:
        weights = [1.0 / n] * n
    if len(weights) != n:
        return {"status": "out_of_domain", "reason": "weights/seals length mismatch"}
    wsum = float(sum(weights))
    if wsum <= 0:
        return {"status": "out_of_domain", "reason": "non-positive weights"}
    w = [float(x) / wsum for x in weights]
    seal_term = sum(w[k] * (min(4, max(0, int(seals[k]))) / 4.0) for k in range(n))
    dci = dependency_concentration_index(dep_shares)
    score = seal_term * (1.0 - dci) * 100.0
    posture = "allodial" if score >= 80 else ("mixed" if score >= 40 else "feudal")
    return {
        "score": round(score, 2),
        "seal_term": round(seal_term, 4),
        "dci": round(dci, 4),
        "posture": posture,
        "tier": "PROPOSED (EU CSF + HHI prior art; weights need calibration)",
        "formula": "A = [Σ w_k·SEAL_k/4] × (1−DCI) × 100",
        "cites": ["EU Cloud Sovereignty Framework 2025", "Herfindahl-Hirschman Index"],
    }


def noninterference_holds(operator_outputs: Sequence, operator_outputs_purged: Sequence) -> dict:
    """Goguen-Meseguer (1982) Definition 4 — operationalized check.

    An allodial system satisfies non-interference iff purging ALL external
    actors' commands leaves operator-visible outputs UNCHANGED:
        ∀ traces:  [[w]]_op  ==  [[ purge_external(w) ]]_op
    Here we compare the operator-visible output sequence with and without the
    external overlord's inputs. Equality => the overlord cannot influence the
    operator's protected outputs => formally allodial on this trace.
    """
    holds = list(operator_outputs) == list(operator_outputs_purged)
    return {
        "noninterference_holds": bool(holds),
        "interpretation": ("external overlord CANNOT influence operator outputs "
                           "(allodial on this trace)") if holds else
                          ("external inputs DID change operator outputs "
                           "(feudal leakage on this trace)"),
        "definition": "Goguen-Meseguer 1982, Def. 4: [[w]]_op == [[purge_ext(w)]]_op",
        "cite": "Goguen & Meseguer (1982), IEEE S&P",
        "note": "Per-trace operational witness; full proof is the Lean AllodialNI gate.",
    }


def lattice_position(seal: int) -> dict:
    """Denning (1976) lattice: control classes form a complete lattice; ⊤ is the
    allodial element (information flows in from everywhere, out to nowhere). A
    SEAL-4 configuration sits at ⊤; any feudal dependency is a strict step below.
    """
    s = min(4, max(0, int(seal)))
    return {
        "seal": s,
        "is_top": s == 4,
        "position": "⊤ (allodial / maximal)" if s == 4 else f"below ⊤ (feudal chain at level {s})",
        "lattice": "Denning 1976 complete lattice (SC, →, ⊕); ⊤ = ⊕SC",
        "cite": "Denning (1976) CACM, DOI:10.1145/360051.360056",
        "lean": "machine-checked: allodial_dominance (le_top), allodial_unique "
                "(isMax_iff_eq_top), feudal_has_overlord (lt_top_iff_ne_top) — "
                "lutar-lean, no sorry, Mathlib axioms only [PROPOSED tier].",
    }


# ---------------------------------------------------------------------------
# CHAIN-OF-TITLE STANDARDS ROADMAP (ADDITIVE, honest, PROPOSED/roadmap tier).
# These are the external provenance standards SZL's chain-of-title REFERENCES as
# its L6 direction. They are CITED prior art; SZL claims none of them as its own,
# and does NOT claim any of them is live here. PROPOSED/roadmap tier only.
# ---------------------------------------------------------------------------
STANDARDS_ROADMAP = {
    "tier": "PROPOSED / roadmap (NOT live; not in the locked-8; Λ stays Conjecture 1)",
    "slsa_v1_1_vsa": {
        "what": "SLSA v1.1 (Approved Apr 2025) adds the Verification Summary Attestation "
                "(VSA): a verifier attests that an artifact met a named policy AT "
                "VERIFICATION TIME (verifierName/version, policyUri, verificationResult), "
                "not just at build time. Backwards-compatible with v1.0.",
        "szl_direction": "Emit VSAs alongside the build-time chain-of-title receipts so a "
                         "downstream consumer can see WHAT POLICY the build passed — promoting "
                         "the chain-of-title toward an L2+VSA tier. ROADMAP, not yet live.",
        "honest_limit": "SLSA is necessary but NOT sufficient: build-identity attestations "
                        "(even bare L3) can be forged via OIDC-token theft (e.g. Shai-Hulud, "
                        "2026) — trust no single provenance signal; require behavioral "
                        "corroboration. SLSA L3 is roadmap, never claimed live or bare.",
        "cite": "SLSA v1.1, Apr 2025 (Verification Summary Attestation)",
        "cite_url": "https://slsa.dev/spec/v1.1/verification_summary",
    },
    "sello_receipts": {
        "what": "Sello (\"Notarized Agents: Receiver-Attested Confidential Receipts for AI "
                "Agent Actions\", Juan Figuera, arXiv:2606.04193, 2026) closes a gap SLSA/"
                "Sigstore do not cover — they attest BUILDS, not AGENT ACTIONS at runtime. "
                "Four properties: P1 receiver-side signing, P2 HPKE encryption to the agent-"
                "owner key, P3 publication to a witness-cosigned Merkle transparency log, "
                "P4 owner-side discovery by SHA-256(authorization-token).",
        "szl_direction": "Adopt the Sello P1–P4 receiver-attested-receipt pattern as the L6 "
                         "direction for the agent-action chain-of-title (receiver-signed, "
                         "owner-encrypted, Merkle-anchored receipts). PROPOSED, not implemented.",
        "cite": "Juan Figuera, Sello / Notarized Agents, arXiv:2606.04193 (2026)",
        "cite_url": "https://arxiv.org/abs/2606.04193",
    },
    "doctrine": ("PROPOSED/roadmap only — these standards are CITED prior art (not SZL's). "
                 "Nothing here is claimed live; SLSA is never claimed bare-L3 without "
                 "'roadmap'; Λ stays Conjecture 1; trust never 100%."),
}


def standards() -> dict:
    """Honest, PROPOSED/roadmap note on the external provenance standards the
    chain-of-title REFERENCES as its L6 direction: SLSA v1.1 VSA (Apr 2025) and the
    Sello receiver-attested-receipt protocol (arXiv:2606.04193). Cited prior art;
    SZL claims none as its own and claims none is live. [PROPOSED / roadmap]"""
    return {
        "title": "SZL chain-of-title — provenance standards roadmap (PROPOSED; prior art cited)",
        "l6_direction": ("L6 = machine-checked cryptographic chain-of-title receipt. The "
                         "external standards below are the CITED direction toward it; none "
                         "is live in this image yet."),
        "standards": STANDARDS_ROADMAP,
        "cites": [
            "SLSA v1.1 (Apr 2025) Verification Summary Attestation — https://slsa.dev/spec/v1.1/verification_summary",
            "Sello / Notarized Agents (Juan Figuera) arXiv:2606.04193 — https://arxiv.org/abs/2606.04193",
        ],
    }


def summary() -> dict:
    return {
        "title": "SZL Allodial AI — sovereignty formulas (PROPOSED; prior art cited)",
        "thesis": "Most AI is feudal (rented from an overlord who holds real title). "
                  "SZL is allodial: operator holds the substrate outright, "
                  "on-prem/air-gap-capable, verifiable chain-of-title, no overlord.",
        "layers": {
            "land": "infrastructure held free of any landlord (on-prem + UDS mesh + signed images)",
            "deed": "chain-of-title provenance receipts (in-toto/SLSA/cosign/Rekor)",
            "allodium": "the data + model itself, sovereign not rented",
        },
        "dimensions": [d[0] for d in ALLODIAL_DIMENSIONS],
        "seal_scale": SEAL_SCALE,
        "doctrine": DOCTRINE,
        "differentiator": "L6 — machine-checked cryptographic chain-of-title receipt "
                          "(industry players operate at L1-L5; none operationalize L6).",
        "standards_roadmap": {
            "tier": "PROPOSED / roadmap (cited prior art; none live; none claimed as SZL's)",
            "slsa_v1_1_vsa": "SLSA v1.1 (Apr 2025) Verification Summary Attestation — "
                             "verifier-attested 'what policy did this pass'; roadmap, not live. "
                             "SLSA never claimed bare-L3 without 'roadmap'. See /standards.",
            "sello_receipts": "Sello receiver-attested confidential receipts for AI agent "
                              "actions (arXiv:2606.04193) — the L6 direction for agent-action "
                              "provenance; PROPOSED, not implemented. See /standards.",
            "cites": [
                "SLSA v1.1 Apr 2025 (VSA) — https://slsa.dev/spec/v1.1/verification_summary",
                "Sello / Notarized Agents arXiv:2606.04193 — https://arxiv.org/abs/2606.04193",
            ],
        },
        "status_legend": {
            "VERIFIED": "deterministic computation reproduces a documented formula",
            "PROPOSED": "engineering gate; SZL composition of cited prior art",
        },
        "cites": [
            "en.wikipedia.org/wiki/Allodial_title; Nevada NRS 361.900-361.920",
            "Goguen-Meseguer 1982 (non-interference)",
            "Denning 1976 CACM DOI:10.1145/360051.360056 (lattice)",
            "EU Cloud Sovereignty Framework 2025 (SEAL/SovScore)",
            "Herfindahl-Hirschman Index (DCI)",
        ],
    }


def register(app, ns: str) -> None:
    """Attach /api/<ns>/v1/allodial/* via FastAPI add_api_route."""
    base = f"/api/{ns}/v1/allodial"
    app.add_api_route(f"{base}/summary", lambda: summary(), methods=["GET"])
    app.add_api_route(
        f"{base}/score",
        lambda seals="4,4,4,4,4", weights="", dep="0":
            allodial_score(
                [int(x) for x in seals.split(",") if x.strip() != ""],
                ([float(x) for x in weights.split(",") if x.strip() != ""] or None),
                [float(x) for x in dep.split(",") if x.strip() != ""],
            ),
        methods=["GET"])
    app.add_api_route(
        f"{base}/dci",
        lambda shares="1": {"shares": shares,
                            "dci": round(dependency_concentration_index(
                                [float(x) for x in shares.split(",") if x.strip() != ""]), 4),
                            "cite": "Herfindahl-Hirschman Index"},
        methods=["GET"])
    app.add_api_route(f"{base}/seal", lambda: {"seal_scale": SEAL_SCALE,
                                               "cite": "EU Cloud Sovereignty Framework 2025"},
                      methods=["GET"])
    app.add_api_route(
        f"{base}/noninterference",
        lambda op="1,2,3", purged="1,2,3":
            noninterference_holds(op.split(","), purged.split(",")),
        methods=["GET"])
    app.add_api_route(f"{base}/lattice",
                      lambda seal="4": lattice_position(int(seal)), methods=["GET"])
    # ADDITIVE: honest PROPOSED/roadmap standards note (SLSA v1.1 VSA + Sello receipts).
    app.add_api_route(f"{base}/standards", lambda: standards(), methods=["GET"])


def _selftest() -> None:
    # DCI bounds
    assert dependency_concentration_index([]) == 0.0
    assert abs(dependency_concentration_index([1.0]) - 1.0) < 1e-12       # single overlord
    assert abs(dependency_concentration_index([1, 1, 1, 1]) - 0.25) < 1e-12  # 4 equal -> 1/N
    assert dependency_concentration_index([1, 1]) > dependency_concentration_index([1, 1, 1, 1])
    # Allodial score: full allodial = SEAL-4 all + DCI 0 -> 100
    full = allodial_score([4, 4, 4, 4, 4], None, [0])
    assert abs(full["score"] - 100.0) < 1e-9, full
    assert full["posture"] == "allodial"
    # Fully feudal: SEAL-0 -> 0
    feud = allodial_score([0, 0, 0, 0, 0], None, [1.0])
    assert feud["score"] == 0.0 and feud["posture"] == "feudal", feud
    # Single-vendor lock-in penalizes even high SEAL
    locked = allodial_score([4, 4, 4, 4, 4], None, [1.0])  # DCI=1 -> score 0
    assert locked["score"] == 0.0, locked
    # Distributed deps score higher than concentrated at same SEAL
    a = allodial_score([3, 3, 3, 3, 3], None, [1, 1, 1, 1])
    b = allodial_score([3, 3, 3, 3, 3], None, [10, 1])
    assert a["score"] > b["score"], (a, b)
    # Non-interference: identical purged outputs -> holds; differing -> fails
    assert noninterference_holds([1, 2, 3], [1, 2, 3])["noninterference_holds"] is True
    assert noninterference_holds([1, 2, 3], [1, 9, 3])["noninterference_holds"] is False
    # Lattice: SEAL-4 is top
    assert lattice_position(4)["is_top"] is True
    assert lattice_position(2)["is_top"] is False
    # Out-of-domain guards
    assert allodial_score([], None, [0])["status"] == "out_of_domain"
    assert summary()["doctrine"]["allodial_is_formal_lambda"] is False
    # Standards roadmap note: present, PROPOSED/roadmap, cited, none claimed live
    st = standards()
    assert "slsa_v1_1_vsa" in st["standards"] and "sello_receipts" in st["standards"], st
    assert "roadmap" in st["standards"]["tier"].lower(), st
    assert st["standards"]["sello_receipts"]["cite_url"] == "https://arxiv.org/abs/2606.04193"
    assert "roadmap" in summary()["standards_roadmap"]["tier"].lower()
    print("szl_allodial: ALL OK (18 checks)")


if __name__ == "__main__":
    _selftest()
