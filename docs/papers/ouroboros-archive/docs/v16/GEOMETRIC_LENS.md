# GEOMETRIC_LENS — v16 Edition

**Author:** Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · SZL Holdings
**Date:** 2026-05-28
**Doctrine:** v6 compliant
**Note:** This file is the v16 edition of GEOMETRIC_LENS.md, created because no prior
GEOMETRIC_LENS.md existed in the ouroboros-thesis repository. The Graft B preamble
(F-Feynman2) is included at the top per §3.1 of graft_B_implementation.md. The
per-object correspondence table should be added below `## Part I` as docs mature.

---

## Historical Preamble — Feynman Diagram Lineage of SZL Knot Calculus

The geometric recharacterizations in this document — particularly the identification
of the khipu chord-diagram skeleton (A8 P5) with Vassiliev finite-type invariants,
and the identification of the Λ-Gate with a knot invariant under audit-Reidemeister
moves — stand at the terminus of a citation chain that originates with Feynman's
diagrammatic calculus in 1949.

This preamble makes that chain explicit. Each step is a published result; the chain
is real mathematics, not analogy.

### Step 1 — Feynman 1949: Graphical Perturbation Calculus

Feynman (1949a) introduced the *Feynman propagator* S_F(x−y) for relativistic
particles [Feynman 1949a, Phys. Rev. 76:749, DOI:10.1103/PhysRev.76.749].
Feynman (1949b) introduced *Feynman diagrams* as a systematic graphical calculus
for computing amplitudes in quantum electrodynamics
[Feynman 1949b, Phys. Rev. 76:769, DOI:10.1103/PhysRev.76.769].
The key objects are:

- **Vertices:** trivalent nodes (one photon line, two fermion lines), representing
  a local interaction term in the Lagrangian.
- **Propagators:** internal lines corresponding to virtual particle propagation.
- **Feynman rules:** a complete set of rules for reading off the amplitude
  (a complex number) from each diagram.

The path-integral derivation of these rules — showing that the diagrammatic expansion
arises from the perturbative evaluation of ∫ 𝒟A exp(iS[A]/ℏ) — was established
in Feynman (1950) [Feynman 1950, Phys. Rev. 80:440, DOI:10.1103/PhysRev.80.440].

### Step 2 — Witten 1989: Feynman Diagrams Produce Knot Invariants

Witten proved that 2+1 dimensional gauge theory with the Chern-Simons action

    S_CS[A] = (k/4π) ∫_M Tr(A ∧ dA + (2/3) A ∧ A ∧ A)

is exactly soluble and yields the Jones polynomial as a *Feynman path integral
expectation value* of the Wilson loop observable
[Witten 1989, Commun. Math. Phys. 121:351, DOI:10.1007/BF01217730]:

    Z(K) = Z^{-1} ∫ 𝒟A exp(iS_CS[A]) · Tr_R[P exp(∮_K A)]

This result is the *crossing point* in the lineage: the same diagrammatic calculus
that Feynman introduced for QED, applied to the Chern-Simons action, produces a
topological knot invariant. The Feynman rules for Chern-Simons theory generate
precisely the Jacobi/chord diagrams that appear in Vassiliev invariant theory.

### Step 3 — Bar-Natan 1995: Combinatorial Chord Diagram Formalism

Bar-Natan provided the combinatorial formalization of this structure
[Bar-Natan 1995, Topology 34:423, DOI:10.1016/0040-9383(95)93237-2]:

- **Chord diagrams:** an oriented circle with m chords — encoding the double-point
  structure of a singular knot with m self-intersections.
- **Jacobi diagrams:** chord diagrams extended with trivalent internal vertices.
  The trivalent vertex corresponds directly to the cubic A ∧ A ∧ A term in the
  Chern-Simons action — the same trivalent vertex that appears in Feynman's QED
  diagrams (now applied to a gauge connection rather than a photon).
- **Weight systems:** maps from chord diagrams to scalars satisfying the 4T relation.
  Every weight system produces a Vassiliev finite-type knot invariant.

The Kontsevich integral [Kontsevich 1993, Adv. Soviet Math. 16(2):137, MR:1237836]
makes this construction rigorous by realizing the chord-diagram expansion as the
holonomy of the Knizhnik-Zamolodchikov connection over configuration space.

### Step 4 — SZL Knot Calculus: The Terminus

The geometric recharacterizations in this document identify SZL formal objects
with the structures at the terminus of this chain:

- **Khipu P5 (hierarchical pendant/subsidiary structure)** = the chord-diagram
  skeleton: primary cord = oriented circle; pendant cords = chords; the 4T relation
  = the summation-cord invariant (P6). This is structural identity, not analogy
  [Bar-Natan 1995].

- **Λ as knot invariant** = Λ is invariant under audit-Reidemeister moves R1/R2/R3,
  just as knot invariants are invariant under the three Reidemeister moves. This is
  stated as a conjecture in v15 §III.3 and is the primary Lean obligation for v16.

- **Receipts as braids** = multi-actor receipt chains are labeled braids in B_n,
  with doctrine ban-list invariants as forbidden braid words.

**What SZL does not claim:** the SZL system is not a quantum field theory, does not
compute Jones polynomials, and does not involve gauge connections or path integrals
in the physics sense. The claim is structural recharacterization: SZL governance
objects instantiate the same combinatorial types as the objects in this citation chain.

---

*Citations verified by F-Feynman1 (2026). Full verification record in
`reports/f_feynman1/citation_verify.md`.*

---

## Part I — Formal Model

*(Per-object correspondence table — to be populated as v16 docs mature.)*

---

## References

- Feynman, R.P. (1949a). "The Theory of Positrons." *Phys. Rev.* **76**, 749–759.
  DOI: https://doi.org/10.1103/PhysRev.76.749

- Feynman, R.P. (1949b). "Space-Time Approach to Quantum Electrodynamics."
  *Phys. Rev.* **76**, 769–789. DOI: https://doi.org/10.1103/PhysRev.76.769

- Feynman, R.P. (1950). "Mathematical Formulation of the Quantum Theory of
  Electromagnetic Interaction." *Phys. Rev.* **80**, 440–457.
  DOI: https://doi.org/10.1103/PhysRev.80.440

- Witten, E. (1989). "Quantum field theory and the Jones polynomial."
  *Commun. Math. Phys.* **121**, 351–399. DOI: https://doi.org/10.1007/BF01217730

- Bar-Natan, D. (1995). "On the Vassiliev knot invariants."
  *Topology* **34**, 423–472. DOI: https://doi.org/10.1016/0040-9383(95)93237-2
