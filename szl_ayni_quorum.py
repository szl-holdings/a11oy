# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
#
# szl_ayni_quorum.py — ADDITIVE wiring of the Round-12 Lean theorem
#   `Lutar.Round12.AyniQuorum.quorum_intersection_honest`  (PROVED, sorry-free)
# into a11oy as a read-only formula endpoint.
#
#   GET|POST /api/a11oy/v1/formula/ayni-quorum
#
# The theorem (Ayni/Ubuntu quorum intersection): with `n` organs, fault budget `f`
# obeying the Ubuntu charter `n ≥ 3*f + 1`, any two quorums of size ≥ n − f intersect
# in strictly MORE than `f` organs — hence they share at least one *honest* organ.
# "umuntu ngumuntu ngabantu" — a person is a person through other persons.
#
# This endpoint EVALUATES the proved invariant for caller-supplied (n, f, q1, q2) and
# reports whether the quorum-intersection guarantee holds, citing the Lean theorem and
# the philosopher pod's conjecture file. It does NOT re-prove anything and it does NOT
# claim the open `ubuntu_quorum_safety` (Khipu Conjecture 2) — that stays a conjecture.
#
# ZERO BANDAID: pure arithmetic over the proved bound; no fabricated state, no network.

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Provenance — the proved Lean artifact this endpoint exposes.
LEAN_THEOREM = "Lutar.Round12.AyniQuorum.quorum_intersection_honest"
LEAN_FILE = "Lutar/Innovations/round12/Identity_Ayni_Quorum.lean"
LEAN_REPO = "szl-holdings/lutar-lean"
LEAN_BRANCH = "feat/round12-frontier-unification"  # Round-12 PR #181
CONJECTURE_FILE = "team/philosophy-meditation/CANDIDATE_THEOREMS_EASTERN.md (CT-E5 Ubuntu ∥ CT-3 Spinoza nesting)"
CITATIONS = [
    "Ramose, African Philosophy through Ubuntu (Mond Books, 1999)",
    "Metz, 'Toward an African Moral Theory', J. Political Philosophy 15(3) (2007)",
    "Webb (ed.), Yanantin and Masintin in the Andean World (UNM Press, 2012)",
    "Lamport, Shostak, Pease, 'The Byzantine Generals Problem', ACM TOPLAS 4(3) (1982)",
    "Castro & Liskov, 'Practical Byzantine Fault Tolerance', OSDI (1999)",
]


def _evaluate(n: int, f: int, q1: int, q2: int) -> dict:
    """Apply the PROVED bound. Returns the guarantee status without re-proving it.

    Proved fact (sorry-free in Lean): if `n ≥ 3f+1` and `q1,q2 ≥ n−f`, then
    `|Q1 ∩ Q2| ≥ q1 + q2 − n ≥ 2(n−f) − n = n − 2f ≥ f+1 > f`, so the two quorums
    share strictly more than `f` organs → at least one honest organ in common.
    """
    charter_ok = n >= 3 * f + 1
    quorum_ok = (q1 >= n - f) and (q2 >= n - f)
    # Inclusion–exclusion lower bound on the intersection size (|Q1∪Q2| ≤ n).
    inter_lower_bound = max(0, q1 + q2 - n)
    guarantee = charter_ok and quorum_ok and inter_lower_bound > f
    return {
        "n_organs": n,
        "fault_budget_f": f,
        "quorum_sizes": {"q1": q1, "q2": q2},
        "ubuntu_charter_n_ge_3f_plus_1": charter_ok,
        "quorums_committable_ge_n_minus_f": quorum_ok,
        "intersection_lower_bound": inter_lower_bound,
        "honest_organ_guaranteed": guarantee,
        "explanation": (
            "Two committable quorums share strictly more than f organs, hence at least "
            "one honest organ in common — no two conflicting verdicts can both commit."
            if guarantee else
            "Inputs do not satisfy the Ubuntu charter (n≥3f+1) and/or quorum sizes (≥n−f); "
            "the proved guarantee does not apply to these inputs."
        ),
    }


def register(app: FastAPI, ns: str = "a11oy") -> dict:
    """Attach the read-only Ayni/Ubuntu quorum formula endpoint to `app`.

    Must be registered BEFORE the /api/<ns>/{path:path} catch-all so it resolves locally.
    """
    path = f"/api/{ns}/v1/formula/ayni-quorum"

    async def _handler(request: Request) -> JSONResponse:
        # Defaults model the SZL 5-organ mesh tolerating 1 fault (n=4? — use n≥3f+1 honest default).
        n, f, q1, q2 = 4, 1, 3, 3
        try:
            if request.method == "POST":
                body = await request.json()
            else:
                body = dict(request.query_params)
            if body:
                n = int(body.get("n", n))
                f = int(body.get("f", f))
                q1 = int(body.get("q1", body.get("quorum1", q1)))
                q2 = int(body.get("q2", body.get("quorum2", q2)))
        except Exception:
            pass  # fall back to defaults; never 500 on bad input

        result = _evaluate(n, f, q1, q2)
        return JSONResponse({
            "formula": "ayni-quorum",
            "name": "Ayni / Ubuntu quorum-intersection convergence",
            "lean_theorem": LEAN_THEOREM,
            "lean_file": LEAN_FILE,
            "lean_repo": LEAN_REPO,
            "lean_branch": LEAN_BRANCH,
            "proof_status": "PROVED (sorry-free) — quorum_intersection_honest",
            "conjecture_source": CONJECTURE_FILE,
            "open_companion": (
                "ubuntu_quorum_safety remains Khipu Conjecture 2 (honest sorry: "
                "HONEST_ORGAN_SINGLE_VALUED). NOT claimed proven."
            ),
            "lambda_status": "Λ = Conjecture 1 (NEVER theorem) — unaffected",
            "doctrine": "v11 LOCKED 749/14/163 @ c7c0ba17 · axioms_unique=14 (no axiom added)",
            "citations": CITATIONS,
            "result": result,
        })

    app.add_api_route(path, _handler, methods=["GET", "POST"], name=f"{ns}_ayni_quorum")
    return {"path": path, "lean_theorem": LEAN_THEOREM, "proof_status": "PROVED"}


# ---------------------------------------------------------------------------
# Doctrine footer
#   Doctrine v11 LOCKED — 749 declarations / 14 unique axioms / 163 sorries @ c7c0ba17.
#   Λ = Conjecture 1 (NEVER a theorem). A5 is a STRUCTURE FIELD (axiom count stays 14).
#   This endpoint exposes the PROVED, sorry-free Lean theorem
#   Lutar.Round12.AyniQuorum.quorum_intersection_honest (Round-12 PR #181). It does NOT
#   elevate Λ and does NOT claim the open ubuntu_quorum_safety (Khipu Conjecture 2).
#   SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap (never L3). Motivating philosophers cited above (real works only).
# ---------------------------------------------------------------------------
