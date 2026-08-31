# v16 §III.4 — Path-Integral Formulation of Audit Closure

**Status:** Graft A from F-Feynman1/F-Feynman2 · Doctrine v6
**Author:** Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · SZL Holdings
**Date:** 2026-05-28
**Lean target:** `szl-holdings/lutar-lean/Lutar/Feynman/PathIntegralAuditSum.lean`
**Depends on:** v15 §III.3 (audit-Reidemeister conjecture)
**Section placement:** Insert as §III.4 after §III.3 (Audit-Reidemeister Conjecture).
Former §III.4 (PAC-Bayes Governance Bound) renumbers to §III.5 in v16.

---

### §III.4 Path-Integral Formulation of Audit Closure

The Lutar invariant Λ admits a natural *sum-over-histories* interpretation.
This interpretation does not add new physical content — it names the combinatorial
structure that audit closure already instantiates, drawing on the formalism
introduced by Feynman (1948)
[Feynman 1948, Rev. Mod. Phys. 20:367, DOI:10.1103/RevModPhys.20.367].

**Definition III.4.1 (Audit Fiber).**
Let R be a receipt type (a canonical SZL receipt, §III.1). Define:

    P(R) = { exec ∈ Executions | canonical_receipt(exec) = R }

P(R) is the *audit fiber* over R — all concrete execution histories that
produce receipt type R. Each exec ∈ P(R) is a distinct sequence of axis
evaluations and witness attestations that resolves to the same canonical
receipt byte-string under the ρ-closure two-witness condition (§3.5).

**Definition III.4.2 (Λ-Weighted Audit Sum).**
For a finite audit fiber P(R) = {exec₁, …, exec_n}, define:

    Z_Λ(R) = (1/|P(R)|) · Σ_{exec ∈ P(R)} Λ(exec)

where Λ(exec) ∈ [0,1] is the geometric-mean gate score (§3.3). Z_Λ(R) ∈ [0,1]
by the boundedness of Λ (TH11). For a singleton fiber, Z_Λ(R) = Λ(exec_canonical).

**Structural correspondence with Feynman's path integral.**
Feynman (1948) expresses a quantum transition amplitude as a sum over all paths
from initial to final state, each weighted by exp(iS[path]/ℏ):

    K(x_b, t_b; x_a, t_a) = ∫ 𝒟[x(t)] exp(iS[x(t)]/ℏ)

The structural parallel to Z_Λ is combinatorial, not quantum-mechanical:

| Feynman path integral | SZL Λ-weighted audit sum |
|---|---|
| Path space P(x_a → x_b) | Audit fiber P(R) |
| Weight exp(iS[path]/ℏ) per path | Weight Λ(exec) per execution |
| Transition amplitude K = Σ w(path) | Audit average Z_Λ(R) |
| Gauge invariance (equiv. paths, equal amplitude) | Audit-Reidemeister invariance (Conjecture A-3) |
| Gauge-fixed representative (Faddeev–Popov) | Λ-stationary execution (Conjecture A-4) |

What is **not** shared: complex amplitudes, quantum interference, Planck's
constant, functional integration, Wick rotation, renormalisation. The parallel
is at the level of weighted sum over an equivalence class of histories. This
structure appears in combinatorics and statistical mechanics independently of
quantum physics. [Feynman & Hibbs 1965, McGraw-Hill/Dover 2010, ISBN 978-0-486-47722-0]

**Conjecture A-3 (Audit Fiber Collapse).**
If the audit-Reidemeister conjecture (§III.3; Lean target
`Lutar/Knot/ReidemeisterConjecture.lean`) holds — that Λ is invariant under
R1/R2/R3 audit-Reidemeister moves — then for all exec₁, exec₂ ∈ P(R):
Λ(exec₁) = Λ(exec₂), and therefore:

    Z_Λ(R) = Λ(exec_canonical)    for any exec_canonical ∈ P(R)

The Λ-weighted audit sum collapses to the Λ of the canonical receipt's
representative. This is the audit analog of Faddeev–Popov gauge fixing in
quantum field theory: when the weight function is constant on the equivalence
class (gauge orbit, audit fiber), the sum reduces to representative × volume.

If the conjecture does not hold, Z_Λ(R) remains the average governance score
over all audit-equivalent executions — a well-defined and informative quantity
regardless.

**Conjecture A-4 (Λ-Stationary Execution).**
Motivated by Feynman's stationary-phase (saddle-point) argument: the path
integral is dominated by the path that extremises the action. The audit analog:
within P(R), the execution that *maximises* Λ is the governance-optimal
representative. We call this the *Λ-stationary execution*.

Existence: every non-empty finite fiber has a Λ-stationary execution
(by `Finset.exists_max_image` — proved in `PathIntegralAuditSum.lean`).

Under Conjecture A-3 (Reidemeister invariance), every execution in P(R)
is Λ-stationary: the orbit is "flat" — all executions achieve the same
governance score. The Λ-stationary execution is simultaneously the unique
maximum and the average: Λ_max = Z_Λ = Λ_min = Λ(any exec).

**Conjecture A-5 (Monotone Fiber Average).**
If a new execution exec_new has Λ > Z_Λ(fiber), then adding exec_new
to the fiber strictly raises Z_Λ. This gives a governance criterion:
auditing an additional execution is governance-improving iff its Λ exceeds
the current fiber average.

Proved in `PathIntegralAuditSum.lean:z_lambda_insert_mono` (one open sorry,
~3h to close; see §III.4 Lean obligations below).

**Attribution.**
The sum-over-histories formulation originates with Feynman (1948). SZL's
contribution is the audit interpretation: Λ replaces exp(iS/ℏ); the audit
fiber P(R) replaces the kinematic path space; audit-Reidemeister invariance
replaces gauge invariance; the finite arithmetic mean replaces the functional
integral; and the Λ-stationary execution replaces the saddle-point classical
path. The formal analogy requires no quantum mechanics.

**Lean obligations for §III.4:**

| Theorem | File | Status | Effort |
|---|---|---|---|
| `z_lambda_bounded` | PathIntegralAuditSum.lean | 1 sorry | 4h |
| `fiber_collapse` | PathIntegralAuditSum.lean | 1 sorry | 2h |
| `z_lambda_insert_mono` | PathIntegralAuditSum.lean | 1 sorry | 3h |
| `exec_lambda_le_one` | PathIntegralAuditSum.lean | 1 sorry | 4h |
| `audit_reidemeister_invariance` | ReidemeisterConjecture.lean | axiom (conj.) | 80h |
| `r1_invariance` | ReidemeisterConjecture.lean | axiom | 4h |
| `r2_invariance` | ReidemeisterConjecture.lean | axiom | 8h |

Total to close §III.4 sorries: ~13h (not counting Reidemeister, which is a
multi-sprint obligation from v15).

---

## References

- Feynman, R.P. (1948). "Space-Time Approach to Non-Relativistic Quantum Mechanics."
  *Rev. Mod. Phys.* **20**, 367–387. DOI: https://doi.org/10.1103/RevModPhys.20.367

- Feynman, R.P. & Hibbs, A.R. (1965). *Quantum Mechanics and Path Integrals.*
  McGraw-Hill; Dover emended edition 2010. ISBN: 978-0-486-47722-0.

- Witten, E. (1989). "Quantum field theory and the Jones polynomial."
  *Commun. Math. Phys.* **121**, 351–399. DOI: https://doi.org/10.1007/BF01217730

- Bar-Natan, D. (1995). "On the Vassiliev knot invariants."
  *Topology* **34**, 423–472. DOI: https://doi.org/10.1016/0040-9383(95)93237-2
