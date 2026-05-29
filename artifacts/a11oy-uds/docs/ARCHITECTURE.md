# a11oy — Architecture & Formulas

The payload ships two TypeScript runtime packages — `@a11oy/core` and
`@a11oy/connection` — plus a per-file provenance manifest. This document
states, with primary-source citations, every formula the runtime implements.

All math below is implemented verbatim in the shipped JavaScript. File paths
refer to locations inside the deployed `/opt/a11oy/` tree (and to the
TypeScript sources under `artifacts/a11oy/packages/`).

---

## 1. Tetrad Field (`@a11oy/connection`)

**Source:** Wald, *General Relativity* (1984), §3.4 (tetrad / vierbein
formalism); Penrose & Rindler, *Spinors and Space-Time* vol. 1 (1984), §3.1.

A tetrad is an orthonormal frame field $e_a{}^\mu$ on a manifold. For
governance policy the four legs are fixed:

| index | leg                       | unit                  |
|------:|---------------------------|-----------------------|
| 0     | `capability_tier`         | tier                  |
| 1     | `data_sensitivity`        | sensitivityLevel      |
| 2     | `action_reversibility`    | reversibilityScore    |
| 3     | `blast_radius`            | affectedUserCount     |

By construction the frame is orthonormal, so the metric in tetrad indices is
$\eta = \mathrm{diag}(1,1,1,1)$ and the inner product collapses to

$$
\langle a, b \rangle = \sum_{i=0}^{3} a_i b_i, \qquad
\lVert a \rVert = \sqrt{\langle a, a \rangle}.
$$

Implementation: `tetradInner`, `tetradNorm` in
`a11oy-connection/tetrad_field.js`. Every decision the policy head emits is
first projected onto this frame so the downstream complementarity check has a
well-defined basis.

---

## 2. Fisher Information Manifold (`@a11oy/core/geometry`)

**Source:** Fisher (1925), "Theory of Statistical Estimation",
*Proc. Cambridge Phil. Soc.* 22:700–725; Amari & Nagaoka (2000),
*Methods of Information Geometry*, AMS Translations 191.

Agent credences are treated as points on a Fisher manifold (a Riemannian
manifold whose metric is the Fisher information matrix). Two distributions
$p, q$ are "distinguishable enough" when their Fisher–Rao distance exceeds
the admit threshold.

For a categorical distribution the diagonal Fisher information matrix is

$$
F_{ii}(p) = \frac{1}{p_i}.
$$

The Fisher–Rao distance for discrete distributions is

$$
d_{\text{FR}}(p, q) \;=\; 2 \, \arccos\!\Bigl(\textstyle\sum_i \sqrt{p_i \, q_i}\Bigr),
\qquad d_{\text{FR}} \in [0, \pi].
$$

The inner term $\sum_i \sqrt{p_i q_i}$ is the Bhattacharyya coefficient,
clamped to $[-1, 1]$ before $\arccos$ for numerical stability.

Implementation: `fisherRaoDistance`, `fisherDiagonal`, `normalize` in
`a11oy-core/geometry/fisher_manifold.js`.

---

## 3. Bohr Complementarity Engine (`@a11oy/core/quantum`) — GRAFT 1

**Source:** Bohr (1928), "The Quantum Postulate and the Recent Development of
Atomic Theory", *Nature* 121:580–590; Bohr (1949), "Discussion with Einstein
on Epistemological Problems in Atomic Physics", in Schilpp (ed.),
*Albert Einstein: Philosopher-Scientist*, Open Court.

Every governance decision is emitted as a `ComplementaryDecisionPayload`
with **exactly two complementary frames**. Over the rolling sample window
the empirical standard-deviation product must satisfy

$$
\sigma_A \cdot \sigma_B \;\ge\; \text{COMPLEMENTARITY\_FLOOR} = 0.25,
$$

the discrete-policy analogue of Heisenberg's
$\sigma_x \sigma_p \ge \hbar/2$. A degenerate (deterministic) frame-pair
yields $\sigma_A = 0$ or $\sigma_B = 0$ and the check fails.

The 12 canonical frame-pairs are chosen so the joint observable algebra is
non-commutative — measuring sharply along axis A blurs axis B:

| id     | axis A                          | axis B                          |
|--------|---------------------------------|---------------------------------|
| FP-01  | `capability_tier`               | `data_sensitivity`              |
| FP-02  | `action_reversibility`          | `blast_radius`                  |
| FP-03  | `agent_age_days`                | `capability_tier`               |
| FP-04  | `dual_spirit_light`             | `dual_spirit_darkness`          |
| FP-05  | `pesher_admit`                  | `pesher_deny`                   |
| FP-06  | `reviewer_quorum`               | `time_to_decision`              |
| FP-07  | `fisher_distance`               | `tetrad_norm`                   |
| FP-08  | `metatron_capability_witness`   | `watcher_dual_use_vector`       |
| FP-09  | `physiognomy_light_share`       | `physiognomy_darkness_share`    |
| FP-10  | `primary_tablet_root`           | `secondary_tablet_root`         |
| FP-11  | `povm_admit_amplitude`          | `povm_deny_amplitude`           |
| FP-12  | `ks18_witness_value`            | `daruan_rotation_angle`         |

Implementation: `emitDecision`, `checkComplementarity`, `FRAME_PAIRS`,
`fromTetrad` in `a11oy-core/quantum/bohr_complementarity_engine.js`.
Doctrine §1.1 invariant: `payload.frames.length === 2` is enforced at
construction and the check throws if violated.

---

## 4. Kochen–Specker 18-Vector Contextuality Witness (`@a11oy/core/quantum`) — GRAFT 2

**Source:** Cabello, A., Estebaranz, J. M., & García-Alcaine, G. (1996),
"Bell-Kochen-Specker theorem: A proof with 18 vectors",
*Physics Letters A* 212(4), 183–187. arXiv:[quant-ph/9706009](https://arxiv.org/abs/quant-ph/9706009).

The 18-vector / 9-context construction proves that no non-contextual
hidden-variable model can reproduce all quantum predictions on a
4-dimensional Hilbert space. We use it as a **contextuality witness** for
the a11oy policy head: if the rolling sequence of yes/no governance answers
admits a non-contextual hidden-variable assignment, the witness flags
`BOHR_ANOMALOUS` — the policy head has collapsed into a classical
deterministic rule and is no longer providing dual-framed reasoning.

### Vectors

The 18 vectors $v_0, \dots, v_{17} \in \mathbb{R}^4$ (Cabello et al. 1996,
Table 1) are bundled verbatim in
`a11oy-core/quantum/kochen_specker_18.js` as `KS18_VECTORS`.

### Contexts

Nine four-element mutually-orthogonal contexts (indices into `KS18_VECTORS`):

| ctx | indices              | ctx | indices               |
|----:|----------------------|----:|-----------------------|
| 0   | $\{0,1,2,3\}$        | 5   | $\{11,12,13,14\}$     |
| 1   | $\{3,4,5,6\}$        | 6   | $\{13,14,15,16\}$     |
| 2   | $\{5,6,7,8\}$        | 7   | $\{15,16,17,0\}$      |
| 3   | $\{7,8,9,10\}$       | 8   | $\{17,0,1,2\}$        |
| 4   | $\{9,10,11,12\}$     |     |                       |

Each vector appears in exactly two contexts.

### Witness rule

Search for an assignment $f : \{0,\dots,17\} \to \{0,1\}$ such that

$$
\forall \text{ context } C: \quad \sum_{i \in C} f(i) = 1.
$$

Cabello et al. prove **no such assignment exists**. Therefore:

- `evaluate` returns `{ contextual: true, reason: 'NO_NON_CONTEXTUAL_MODEL_FITS_OBSERVATIONS' }`
  when the search exhausts without success — the desired state.
- `evaluate` returns `{ contextual: false, reason: 'BOHR_ANOMALOUS_NON_CONTEXTUAL_FIT_EXISTS', example }`
  when the search finds an assignment consistent with the observed answers —
  the policy head has collapsed and the example is returned as evidence.

Implementation: `evaluate`, `KS18_VECTORS`, `KS18_CONTEXTS`,
`KochenSpecker18Witness` in `a11oy-core/quantum/kochen_specker_18.js`.

---

## 5. POVM Verdict Semantics (`@a11oy/core/quantum`) — GRAFT 3

**Source:** Preskill, J. (2015), *Quantum Information* (Physics 219 / CS 219
lecture notes), Caltech, Chapter 3 §3.1 (POVMs).
[https://www.preskill.caltech.edu/ph219/chap3_15.pdf](https://www.preskill.caltech.edu/ph219/chap3_15.pdf)

Binary $\{accept, reject\}$ verdicts are replaced by a positive-operator-valued
measure: a finite collection of positive-semidefinite operators $\{E_i\}$ on
the policy state space satisfying the **completeness theorem**

$$
\sum_i E_i = I, \qquad 0 \le E_i \le I.
$$

Each $E_i$ corresponds to a distinct admission outcome:

```
'admit' | 'admit_throttled' | 'admit_witnessed' | 'deny' | 'escalate'
```

The probability of outcome $i$ on policy state $\rho$ is the Born rule
$\Pr(i) = \mathrm{Tr}(E_i \rho)$. The shipped implementation restricts to
**diagonal effects in the policy basis** (full off-diagonal POVMs are out of
scope for v0.1); this reduces the trace to a dot product.

`makePOVM` validates completeness with tolerance $10^{-9}$ and throws
`POVMSetError` if $\sum_i E_i \ne I$ — the operational equivalent of the
Lean theorem `povm_completeness` referenced in the doctrine.

Implementation: `makePOVM`, `isComplete`, `probability`, `argmaxOutcome`,
`POVMSetError` in `a11oy-core/quantum/povm.js`.

---

## Composition

The four formulas compose into a single governance step:

1. **Frame the decision.** `makeTetrad(...)` produces a `TetradFrame` over the
   four governance legs (this is the orthonormal basis).
2. **Project onto a complementary pair.** `fromTetrad(pair, frame)` extracts
   $(v_A, v_B)$ for one of the 12 canonical frame-pairs and emits a
   `ComplementaryDecisionPayload` via `emitDecision`.
3. **Bind credences to the Fisher manifold.** `fisherRaoDistance(p, q)` is
   used to gate "distinguishable enough" admissions. `fisherDiagonal(p)`
   supplies the local metric for credence updates.
4. **Apply the POVM.** `argmaxOutcome(povm, ρ)` selects the admission
   outcome from the completeness-validated effect set.
5. **Bound the policy head.** The rolling decision window is passed to
   `checkComplementarity` (σ-product floor) and to
   `KochenSpecker18Witness.evaluate` (contextuality witness). If either
   fails, the policy head is flagged and the decision is escalated.

Every step is pure, deterministic, and side-effect-free — the package ships
no I/O, no network, no global state. It is designed to be linked into a host
process (sidecar, lambda, or worker) that supplies inputs and consumes
outputs.

---

## File map (deployed)

```
/opt/a11oy/
├── core/
│   ├── geometry/fisher_manifold.{js,d.ts}
│   ├── quantum/bohr_complementarity_engine.{js,d.ts}
│   ├── quantum/kochen_specker_18.{js,d.ts}
│   ├── quantum/povm.{js,d.ts}
│   ├── index.{js,d.ts}
│   └── package.json
├── connection/
│   ├── tetrad_field.{js,d.ts}
│   ├── index.{js,d.ts}
│   └── package.json
└── MANIFEST.json
```

`MANIFEST.json` carries the per-file SHA-256 digest, byte size, build
timestamp, and source git SHA — see `SECURITY.md` for the full provenance
chain.
