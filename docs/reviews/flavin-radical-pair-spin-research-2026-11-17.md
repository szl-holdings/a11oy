<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 SZL Holdings — Doctrine v11, research/model-only -->

# Flavin radical-pair spin relaxation: literature to executable invariants

**Date:** 2026-11-17 ET / 2026-11-18 UTC.
**Status:** MODELED / reproducible numerical research; no calibrated flavin
molecule, experimental measurement, spin qubit, device execution or
claim of quantum advantage.

## 1. Exact supplied primary review — scope of access

Valentyna Sirenko and Juan Bartolomé, Biomimetic engineering spin relaxation
in flavin radical pairs for singlet–triplet qubits (Review Article),
Low Temperature Physics 52(7), 760–783, 1 July 2026,
https://doi.org/10.1063/10.0044249.

The publisher provides the abstract, references and select figure captions,
but the complete 24-page review is **not publicly readable** through the
supplied AIP URLs. ResearchGate offers a publisher preview and a request
for the full article. No numerical tensors or mechanisms absent from these
accessible sections are attributed to its authors.

What the review's accessible abstract supports:
* Photo-induced flavin semiquinone radical pairs can have spin-correlated
  singlet/triplet character and field-dependent spin-selective recombination.
* Hyperfine, magnetic fields, environment and spin relaxation can change
  the S/T dynamics and candidate biomimetic sensor design.
* A spin-correlated radical-pair lifetime exceeding approximately 700 ns
  is given as a **conditional design consideration** for Earth's field;
  this is not a measured lifetime achieved by our software.
* The physics of radiationless intersystem crossing remains debated.
  The article is a literature REVIEW, not an SZL validation experiment.

Publisher: https://pubs.aip.org/aip/ltp/article/52/7/760/3398292/Biomimetic-engineering-spin-relaxation-in-flavin

## 2. Additional primary scientific and open-source comparators

**RadicalPy** — RadicalPy: A Tool for Spin Dynamics Simulations,
J. Chem. Theory Comput. 20, 9488–9499 (2024),
DOI https://doi.org/10.1021/acs.jctc.4c00887,
GitHub https://github.com/Spin-Chemistry-Labs/radicalpy.
Provides an independent validation target for classical, semiclassical
and quantum radical pair dynamics including FAD photochemistry. This
implementation is new code, not lifted from that library.

**FAD biradical modeling** — Quantum theory of a potential biological
magnetic field sensor: Radical pair mechanism in flavin adenine
dinucleotide biradicals,
https://pmc.ncbi.nlm.nih.gov/articles/PMC11652833/.
Gives independent spin-dependent recombination/Haberkorn treatment and
illustrates the much larger space of realistic flavin parameters.

**EYFP triplet qubit** — Feder et al., A fluorescent-protein spin qubit,
Nature 645, 73–79 (2025),
https://doi.org/10.1038/s41586-025-09417-w.
Reports 16 ± 2 microsecond CPMG coherence at liquid-nitrogen
temperatures and room-temperature ODMR contrast in bacterial cells.
That optical triplet qubit is distinct from a two-radical
singlet/triplet spin-correlated pair; its numbers are NOT our model data.

**MagLOV** — Abrahams et al., Quantum spin resonance in engineered
proteins for multimodal sensing, Nature 649, 1172–1179 (2026),
https://doi.org/10.1038/s41586-025-09971-3.
The genetically engineered LOV/flavin radical pair and cell experiments
motivate a proper held-out biosensing benchmark.

**In vivo** — Magnetic resonance control of spin-correlated radical pair
dynamics in vivo, Nature 651, 940–945 (2026),
https://doi.org/10.1038/s41586-026-10282-4.
The authors report a field-responsive RFP/flavin mechanism in
C. elegans and estimate >4 ns of coherence for THAT system. It does
not contradict a >700 ns design criterion for a distinct geomagnetic
mechanism or establish a universal coherence requirement.

**Mitochondrial bioenergetics** — Aghaei et al., A quantum interface with
mitochondrial bioenergetics, bioRxiv, July 2026,
https://doi.org/10.64898/2026.07.03.736226.
PREPRINT, not peer-reviewed at time checked. Useful source for future
redox-specific measurement questions, not clinical or therapeutic claims.

## 3. SZL gap and additive implementation

The existing shared szl_quantum_bio.py /qbio/compass code uses a
fixed effective mixing-frequency cosine formula. This is not a
many-body spin-density-matrix treatment of specific flavin chemistry,
and its pre-existing claimed multi-spin contrast is not independently
measured by this new work. We leave that shared A11oy/Killinchu module
untouched to avoid silently changing existing interfaces.

The new isolated szl_flavin_spin_research.py implements a
two-electron + one spin-1/2-nucleus 8 × 8 density matrix:

    omega_e(B) = 2*pi*(0.02802495164 MHz/uT)*B_uT
    H/hbar = omega_e*n(theta).(S1+S2)
           + 2*pi*(A_xy*S1x*Ix + A_xy*S1y*Iy + A_z*S1z*Iz)
           + 2*pi*J*(S1 dot S2)
    P_S = I/4 - S1 dot S2
    P_T = I - P_S
    rho(0) = P_S / 2   [unpolarized nucleus]

Spin-selective Haberkorn recombination plus phenomenological dephasing
and electron-local bit flips:

    d rho/dt = -i[H,rho] - 1/2 {k_s P_S+k_t P_T,rho}
                + D_ST(rho) + D_flip(rho)

The splitting method uses exact unitary half-steps, a nonunitary
singlet/triplet loss map, trace-preserving dephasing and bit-flip
channels. It enforces and exposes the invariant

    Y_s + Y_t + Tr[rho_surviving] = 1  (residual <= 1e-8)

**Important omissions:** actual flavin has many coupled nuclear spins;
there is no calibrated anisotropic hyperfine/exchange/dipolar tensor,
spin-orbit interaction, solvent/protein disorder, dynamical
reaction network, photochemistry or experimentally fit relaxation
spectrum. The model does NOT establish T1, T2, coherent control,
device operation, magnetoreception in organisms, or quantum advantage.

## 4. Falsifiable controls

* B=0 must eliminate angular response.
* Isotropic A_x=A_y=A_z must eliminate a direction-dependent compass.
* With hyperfine=0 and zero flips, an initial singlet has
  Y_s=1-exp(-k_s t), Y_t=0.
* For all bounded sweeps, density PSD, product probabilities nonnegative
  and total mass conserved.
* Halving integration step at identical observation time must converge.
* Nonfinite, pathological and resource-heavy inputs fail with 422;
  missing numpy is 503, not a fabricated analytic fallback.
* The read-only route never signs, writes a receipt, launches a
  model inference, or changes a biological device.
* The output contains a deterministic SHA-256 content digest over a
  strict sorted-JSON representation excluding the two digest metadata
  fields. The digest is UNSIGNED_CONTENT_HASH_ONLY: not a signature,
  attestation, model validation or authorization.

At B=50 uT the electron Larmor period from the known gyromagnetic
ratio is about 714 ns. That is not a measured radical pair lifetime.

**Illustrative model-only fixture:** B=50 uT; A_xy=0.25 MHz,
A_z=1.25 MHz; J=0; k_s=k_t=1 per us; gamma_ST=0.2 per us;
gamma_flip=0; dt=0.02 us; 500 steps.
At 0, 45 and 90 degrees the software calculated singlet yields
approximately 0.531686, 0.539337 and 0.746250, respectively.
Angular contrast ~0.214564. Probability conservation error ~7e-14.
These depend on deliberately uncalibrated inputs; no biological effect
size or published result is being reproduced. Refinement to
dt=0.01 us and 1000 steps changed the contrast by ~3e-6.

## 5. Next frontier experiment: evidence-conserving spin lab

**New SZL research hypothesis, not validated:** a falsification-first
experimental planner could rank fluorescence/magnetoresonance
measurements by their ability to distinguish hyperfine anisotropy,
exchange/dipolar effects, singlet-triplet dephasing and flip noise.

1. Obtain explicit data-use permission and experiment metadata for
   real FAD/MagLOV scans (field, angle, temperature, light schedule,
   protein variant, controls and calibration uncertainty).
2. Bind each dataset revision to a public citation, lawful license,
   source hash and preparation protocol. Mark incomplete data
   UNAVAILABLE; synthetic parameter sweeps remain MODELED.
3. Fit parameters ONLY on training scans. Compare predictions on
   blinded protein variants, fields, temperature and excitation
   sequences. Include isotropic and no-hyperfine negative controls.
4. Select feasible next measurements by expected information gain
   after nuisance marginalization, not by a model's confidence claim.
   All physical experiments require reviewed human authorization.
5. Validate against RadicalPy or an independent solver with the
   SAME kinetic/Hamiltonian definitions, and report disagreement.
6. Publish abstentions and failed predictions along with passing ones.

First useful application: reproducibility and hypothesis ranking for
open, consented spin-chemistry and biological sensing labs.

## 6. Product wiring, authority and rollout

The API is read-only:
GET /api/a11oy/v1/qbio/flavin-spin-research, with bounded parameters,
strict input validation, zero persistence, no signing, and
state=MODELED / verification_scope=NUMERICAL_INVARIANTS_ONLY.

Command v2 Models exposes an explicit linked "Flavin spin research —
MODELED, not measured" path; it does not auto-solve on page load.
The canonical Dockerfile COPY supplies the model and tests cover
FastAPI route vs SPA fallback, physical controls, source labels and
no read-side effect.

This is **not live** until CI checks, protected merge, canonical
HF sync and exact build/route readback succeed. Existing locked-8
formulas, Lambda Conjecture 1, Khipu BFT Conjecture 2 and all governed
action permissions are unchanged.
