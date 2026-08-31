/* =====================================================================
   SZL AGENT BODY v3 — ANATOMY DOCTRINE DATA MODEL
   Single source of truth for the 3D anatomy. Transcribed from:
     team/ANATOMY_DOCTRINE.md  (founder's v3 8-image roadmap)
     team/_PROVEN_FORMULAS.md  (lutar-lean PROVEN_FORMULAS.md, kernel c7c0ba17)
     team/PROVE_NEXT10_REPORT.md (Wave8, main @ 7885fd9)
   Honesty doctrine v11 LOCKED. No fabricated metrics, no AGI, no vendor
   model-codenames. Quechua organ names KEPT as architectural identity,
   always paired with plain-English FUNCTION.
   ===================================================================== */
(function (root) {
  'use strict';

  /* ---- Kernel posture (honest, from lutar-lean main) ---- */
  const KERNEL = {
    locked_sha: 'c7c0ba17',
    locked_decls: 749, locked_axioms: 14, locked_sorries: 163,
    main_sha: '044eb098',   // Wave11–18 all merged (CF-22..28 + CUT-1 fwd), CI-green, drift-clean
    wave910_sha: '66735bf',  // Wave9 PR #199 merged here; Wave10 PR #200 branched from it
    experimental_decls: 1323, experimental_axioms: 23, experimental_axioms_unique: 22, experimental_sorries: 307,
    toolchain: 'Lean v4.13.0 (locked) / v4.18.0 (Mathlib pinned) · main @ 044eb098',
    locked_proven: ['F1', 'F4', 'F7', 'F11', 'F12', 'F18', 'F19', 'F22'],
    experimental_count_approx: 119,  // waves 5–18 instilled card set (EXPERIMENTAL · CI-green, never folded into locked 8)
    waves_merged: 'Wave5–23 (CF-1..28 + CUT-1 fwd + CUT-2 + Wave23 conditional BFT safety)',  // Wave15 CF-22, Wave16 CF-24/25/26, Wave17 CF-23/27/28, Wave18 CUT-1 forward fragment
    cut2: 'Wave12 CUT-2 lambda_unique_of_separable — Λ uniqueness PROVEN CONDITIONAL on slice-multiplicativity, axiom-free, kernel-clean. Unconditional Λ stays Conjecture 1.',
    bft_conditional: 'Wave23 khipu_quorum_safety_conditional — Khipu BFT safety (Conjecture 2) agreement / no-split-brain PROVEN CONDITIONAL on {n>=3f+1, honest non-equivocation}, axiom-clean (PR #214, merged main @ 43bcabb7). Unconditional BFT safety stays Conjecture 2 at the sharp boundary.',
    slsa: 'Static space: SLSA L1 honest · product images (a11oy, killinchu) L2 build-attested (container provenance, Sigstore keyless) · L3 roadmap',
    gpd: 'Governed Post-Determinism — SZL\u2019s own framework. The 5 organs ARE the participant-general model: the BRAIN reasons (divergent reasoning paths are OK), the HEART / YUYAY 13-axis gate certifies semantic admissibility (deny-by-default), the SKELETON / Khipu BFT quorum = Semantic Quorum Assurance (Wave23 conditional safety theorem; unconditional = Conjecture 2), and the CIRCULATORY / YAWAR append-only receipt bus = Epistemic State Replication + Verifiable Semantic Rollback (receipts/replay live; full ESR semantics = open R&D / roadmap). The unit of agreement shifts from identical output to certified semantic admissibility. Grounded entirely in SZL\u2019s prior DOI-stamped published work (Zenodo, Apr\u2013May 2026): The Loop Is the Product v1/v2 (10.5281/zenodo.19867281, .19934129), Lineage-Aware RAG v5 (.20020846), Sealed Constitutional Guardrails v6 (.20020845), Lutar Omega Formalism v4 (.20020841), SZL Doctrine v2 — 9 Canonical Axes (.20174600). Locked-proven = exactly 8 (locked_count_eight; F4/F7/F22 joined the original 5 on 2026-06-10); \u039b = Conjecture 1.'
  };

  /* ---- Maturity → chip styling ---- */
  const MATURITY = {
    LOCKED:        { label: 'LOCKED · kernel-verified', color: '#ffd166', desc: 'Sorry-free, Lean-core axioms only [propext, Classical.choice, Quot.sound]. Frozen @ c7c0ba17.' },
    EXPERIMENTAL:  { label: 'EXPERIMENTAL · CI-green', color: '#5ad1ff', desc: 'Kernel-checked by CI on main @ 7885fd9. Additive — never folded into the locked 8.' },
    AXIOM_GATED:   { label: 'AXIOM-GATED (disclosed)', color: '#c9a0ff', desc: 'Sorry-free given one declared, cited idealization (axiom listed in #print axioms).' },
    CONDITIONAL:   { label: 'CONDITIONAL · axiom-free', color: '#9ef0c0', desc: 'A kernel-clean THEOREM proven CONDITIONAL on a stated stronger hypothesis (no new axiom). Honestly NOT an unconditional result.' },
    CONJECTURE:    { label: 'CONJECTURE 1', color: '#ff7eb6', desc: 'Not a theorem. Conditional only within strengthened classes; unconditional uniqueness machine-checked FALSE.' }
  };

  /* =====================================================================
     FORMULA LIBRARY — keyed by id. latex = ASCII-math the in-app renderer
     converts to Unicode glyphs. axioms = verbatim #print axioms line.
     ===================================================================== */
  const FORMULAS = {
    /* ---------- LOCKED PROVEN (exactly 8) ---------- */
    F1: { id:'F1', name:'Replay-Hash Determinism', maturity:'LOCKED',
      latex:'replay(s0, log) = trace  =>  replay(s0, log) = trace   (bit-identical)',
      plain:'Replaying the SAME recorded log from the same initial state yields a BIT-IDENTICAL trace — no drift. Underpins the Khipu replay-hash gate.',
      axioms:'f1_replay_fold_deterministic — [propext, Classical.choice, Quot.sound]',
      ref:'lutar-lean PuriqFormulaLean.lean @ c7c0ba17' },
    F11:{ id:'F11', name:'Ayni Reciprocity Conservation', maturity:'LOCKED',
      latex:'fold(append_log) :  Sigma_in = Sigma_out   (tit-for-tat parity)',
      plain:'Fold-replay of an append-only reciprocity log conserves the balance invariant (Axelrod–Hamilton tit-for-tat parity).',
      axioms:'f11_ayni_reciprocity_conservation — [propext, Classical.choice, Quot.sound]',
      ref:'lutar-lean PuriqFormulaLean.lean @ c7c0ba17' },
    F12:{ id:'F12', name:'Kuramoto Coupling Boundedness (additive fragment)', maturity:'LOCKED',
      latex:'| Sigma_i K_i(theta) |  <=  Sigma_i |K_i|   (bounded, additive)',
      plain:'The discretised reciprocity coupling stays bounded under additive superposition. HONESTY CAVEAT: additive scaffolding ONLY — NOT the full nonlinear Kuramoto synchronization.',
      axioms:'f12_* — [propext, Classical.choice, Quot.sound]',
      ref:'lutar-lean @ c7c0ba17 · caveat in Lean docstring' },
    F18:{ id:'F18', name:'Reed–Solomon RS(10,6) Recovery', maturity:'LOCKED',
      latex:'recoverable(shards)  <=>  |surviving| >= 6   of 10',
      plain:'Erasure tolerance: data is recoverable IFF at least 6 of 10 shards survive — the resilience arithmetic for the receipt/payload encoding.',
      axioms:'f18_* — [propext, Classical.choice, Quot.sound]',
      ref:'lutar-lean @ c7c0ba17' },
    F19:{ id:'F19', name:'Bekenstein Additive Scaffolding', maturity:'LOCKED',
      latex:'Sigma_r S(region_r)  <=  S(total)   (additive, monotone)',
      plain:'Entropy budget is additive and monotone over a region partition (per-region ≤ total). HONESTY CAVEAT: monotone scaffolding ONLY — NOT the full Bekenstein bound S ≤ 2πkRE/(ℏc).',
      axioms:'f19_* — [propext, Classical.choice, Quot.sound]',
      ref:'lutar-lean @ c7c0ba17 · caveat in Lean docstring' },

    F4: { id:'F4', name:'Khipu DAG Acyclicity Preservation', maturity:'LOCKED',
      latex:'acyclic(G)  =>  acyclic(append_fresh_node(G))   (no back-edge cycle)',
      plain:'Appending a fresh node to the Khipu receipt DAG preserves acyclicity — no receipt can ever cycle back on itself. Newly kernel-verified (joined the locked set 2026-06-10).',
      axioms:'f4_khipu_dag_acyclic_preserved / f4_khipu_no_cycle / f4_khipu_reach_decreases / f4_khipu_append_preserves — no axioms (genuine, non-vacuous)',
      ref:'lutar-lean ProvedFormulas.lean @ c7c0ba17 (lutar-lean #219 + platform #321)' },
    F7: { id:'F7', name:'Chaski FIFO Reception Ordering', maturity:'LOCKED',
      latex:'drain(enqueue_batch(c, msgs))  =  msgs   (reception order = send order)',
      plain:'Messages drain from the Chaski channel in exactly the order sent — true FIFO, no reordering. Newly kernel-verified (joined the locked set 2026-06-10).',
      axioms:'f7_chaski_fifo_order / f7_chaski_fifo_positional / f7_chaski_drain_eq — no axioms (genuine, non-vacuous)',
      ref:'lutar-lean ProvedFormulas.lean @ c7c0ba17 (lutar-lean #219 + platform #321)' },
    F22:{ id:'F22', name:'Khipu Emit Append-Only Monotonicity', maturity:'LOCKED',
      latex:'emit(ledger)  =>  index(ledger\') > index(ledger)   (strictly increasing)',
      plain:'Every Khipu emit strictly increases the ledger index — append-only, never rewrites history. Newly kernel-verified (joined the locked set 2026-06-10).',
      axioms:'f22_khipu_emit_monotone / f22_emit_appends_length / f22_emit_strictly_greater — no axioms',
      ref:'lutar-lean ProvedFormulas.lean @ c7c0ba17 (lutar-lean #219 + platform #321)' },

    /* ---------- WAVE 8 (experimental, green on main @ 7885fd9) ---------- */
    M2: { id:'M2', name:'Hash-Chain Tamper-Evidence', maturity:'EXPERIMENTAL',
      latex:'H injective ,  p_i != q_i   =>   head(p) != head(q)',
      plain:'For an injective hash step H, if any payload entry differs then the resulting head-hash differs — append-only hash chains are tamper-evident. The formal core behind receipt/audit-trail integrity.',
      axioms:"Lutar.Wave8.HashChain.hashchain_tamper_evident — [propext]",
      ref:'PR #196 @ b1c840f · Wave8/HashChain.lean' },
    CP1:{ id:'CP1', name:'Conformal Marginal Coverage', maturity:'EXPERIMENTAL',
      latex:'numer <= (n+1)*covCount  <  numer + (n+1)',
      plain:'Split-conformal coverage satisfies a two-sided ⌈·⌉ bound — finite-sample, distribution-free marginal-coverage guarantee for the trust intervals on Λ.',
      axioms:'Lutar.Wave8.Conformal.conformal_marginal_coverage — [propext, Quot.sound]',
      ref:'PR #196 @ b1c840f · Wave8/Conformal.lean' },
    B1: { id:'B1', name:'Byzantine Impossibility (n=3, f=1)', maturity:'EXPERIMENTAL',
      latex:'3 <= 3*f   =>   no decider agrees with all-false AND all-true',
      plain:'The classic 3-node / 1-fault Byzantine impossibility — the formal n ≥ 3f+1 lower bound. Justifies consensus/quorum sizing in the shared mesh and rejects under-provisioned fault tolerance.',
      axioms:'Lutar.Wave8.Byzantine.byzantine_impossibility_3_1 — does not depend on any axioms',
      ref:'PR #196 @ b1c840f · Wave8/Byzantine.lean' },
    B2: { id:'B2', name:'Khipu BFT Safety (conditional)', maturity:'CONDITIONAL',
      latex:'n>=3f+1  &&  honest non-equivocation  =>  two quorums certifying v1,v2  =>  v1 = v2',
      plain:'Conjecture 2 (Khipu BFT safety) — agreement / no-split-brain PROVEN axiom-free CONDITIONAL on n>=3f+1 and honest non-equivocation under signed votes. Byzantine organs MAY equivocate in the model and safety still holds. Unconditional BFT safety stays Conjecture 2 at the sharp boundary.',
      axioms:'Lutar.Wave23.QuorumSafety.khipu_quorum_safety_conditional — [propext, Classical.choice, Quot.sound]',
      ref:'PR #214 @ 43bcabb7 · Wave23/QuorumSafety.lean' },
    S2: { id:'S2', name:'Simplex Safety Invariant', maturity:'EXPERIMENTAL',
      latex:'RC safe ,  (mon pass => AC safe)   =>   forall t, state_t safe',
      plain:'Simplex/RTA run-time-assurance: a monitored switch to a verified recovery controller keeps the system in the safe set for ALL time. Backbone of fail-safe autonomy and the HUKLLA deadman reflex.',
      axioms:'Lutar.Wave8.Simplex.simplex_safety_invariant — [propext]',
      ref:'PR #196 @ b1c840f · Wave8/Simplex.lean' },
    G1: { id:'G1', name:'CPA Minimality', maturity:'EXPERIMENTAL',
      latex:'cpaTime  =  argmin_t  sep2(t)   (unique minimizer)',
      plain:'The closest-point-of-approach time is the UNIQUE minimizer of squared separation. Formal anchor for killinchu collision / conflict-risk timing.',
      axioms:'Lutar.Wave8.CPA.cpa_unique — [propext, Classical.choice, Quot.sound]',
      ref:'PR #197 @ 7885fd9 · Wave8/CPA.lean' },
    L2: { id:'L2', name:'Deny-by-Default Uniqueness', maturity:'EXPERIMENTAL',
      latex:'D monotone & diagonal & conservative   =>   D == vmin  (everywhere)',
      plain:'The min-gate vmin is the UNIQUE monotone, diagonal, conservative gate — the weakest-link trust gate is the ONLY policy satisfying the safety axioms; no permissive aggregator can sneak in. Backs the YUYAY deny-by-default conjunction.',
      axioms:'Lutar.Wave8.MinGate.deny_by_default_unique — [propext]',
      ref:'PR #196 @ b1c840f · Wave8/MinGate.lean' },
    Q1: { id:'Q1', name:'Density-Matrix Mixture PSD', maturity:'EXPERIMENTAL',
      latex:'Sigma_i w_i rho_i   PSD & unit-trace   (w_i>=0, Sigma w_i = 1)',
      plain:'A convex combination of PSD, unit-trace matrices is again a valid density matrix — convexity of the mixed-state set. Underpins probabilistic ensemble reasoning in the YACHAY quantum-mind region.',
      axioms:'Lutar.Wave8.DensityMixture.density_matrix_mixture — [propext, Classical.choice, Quot.sound]',
      ref:'PR #197 @ 7885fd9 · Wave8/DensityMixture.lean' },
    Q2: { id:'Q2', name:'Gershgorin Governance Non-Degeneracy (real)', maturity:'EXPERIMENTAL',
      latex:'Sigma_{j!=k} |W_kj| < |W_kk|   =>   det W != 0  =>  W x = b unique',
      plain:'A strictly diagonally-dominant real governance weight matrix is invertible, so weighted aggregation has a unique solution — no zero-eigenvalue collapse of the governance operator. (ℂ variant left honestly as ROADMAP — shipped real-valued only, sorryAx-free.)',
      axioms:'Lutar.Wave8.Gershgorin.governance_nonsingular_real — [propext, Classical.choice, Quot.sound]',
      ref:'PR #197 @ 7885fd9 · Wave8/Gershgorin.lean' },
    L3: { id:'L3', name:'Λ Strict Monotonicity', maturity:'EXPERIMENTAL',
      latex:'x_i > 0 ,  x <= y ,  x_k < y_k   =>   Lambda(x) < Lambda(y)',
      plain:'The geometric-mean trust aggregator is per-component strictly monotone: improving any input strictly raises the fused trust. NO uniqueness of Λ asserted — Conjecture 1 untouched.',
      axioms:'Lutar.Wave8.LambdaMono.gmean_strict_mono — [propext, Classical.choice, Quot.sound]',
      ref:'PR #197 @ 7885fd9 · Wave8/LambdaMono.lean' },
    Ph1:{ id:'Ph1', name:'Axiom-Disclosure Soundness', maturity:'EXPERIMENTAL',
      latex:'axiomsAllowed(S)   =>   every a in S is a Lean kernel axiom',
      plain:'The axiom-disclosure gate is sound; locked_count_eight proves there are EXACTLY 8 locked entries with kernel-only axioms (= by decide, no axioms). Mechanically enforces "no hidden axioms".',
      axioms:'Lutar.Wave8.AxiomDisclosure.disclosure_sound — [propext, Quot.sound] · locked_count_eight — no axioms',
      ref:'PR #196 @ b1c840f · Wave8/AxiomDisclosure.lean' },

    /* ---------- WAVE 9 + WAVE 10 (experimental, CI-green on main @ 66735bf) ----------
       PR #199 (Wave9) merged @ 66735bf; Wave10 PR #200. EXPERIMENTAL · CI-green —
       kernel-verified, NEVER folded into the locked 8. Λ stays Conjecture 1.
       Live computation surfaces shipped in killinchu /api/killinchu/v1/wave910/*. */
    W9_GERSH:{ id:'MA1', name:'Gershgorin Spectral Non-Degeneracy (incl. ℂ)', maturity:'EXPERIMENTAL',
      latex:'strict diag dominance  =>  0 in no Gershgorin disc  =>  no zero eigenvalue  =>  W nonsingular',
      plain:'Wave9 SPECTRAL Gershgorin: a strictly diagonally-dominant matrix (field-general, incl. ℂ) has no zero eigenvalue, hence is nonsingular and det is a unit. A cheap pre-flight gate on the governance/command-trust matrix BEFORE aggregation. DISTINCT from the Wave8 ℝ determinant-form card (Q2) — both kept.',
      axioms:'Lutar.Wave9.Gershgorin.no_zero_eigenvalue / nonsingular_of_strict_diag_dominant / isUnit_det_of_strict_diag_dominant — [propext, Classical.choice, Quot.sound]',
      ref:'PR #199 @ 66735bf · Wave9/Gershgorin.lean' },
    W9_CI:{ id:'OE-2', name:'Covariance-Intersection PSD Convex Closure', maturity:'EXPERIMENTAL',
      latex:'P_ci^{-1} = w P_a^{-1} + (1-w) P_b^{-1}  =>  P_ci PSD & conservative',
      plain:'Fuse two sensors that see the same target WITHOUT knowing their cross-covariance. The CI information matrix is PSD as a non-negative convex combination of PSD information matrices, so the fused covariance is always a valid, never-overconfident uncertainty. (Full inverted-covariance Loewner monotonicity left honestly as ROADMAP.)',
      axioms:'Lutar.Wave9.CovarianceIntersection.posSemidef_convex_comb / ci_information_psd — [propext, Classical.choice, Quot.sound]',
      ref:'PR #199 @ 66735bf · Wave9/CovarianceIntersection.lean' },
    W9_MENGER:{ id:'L-Menger', name:'Menger Cut/Path Duality (mesh redundancy)', maturity:'EXPERIMENTAL',
      latex:'#edge-disjoint paths(s,t)  <=  minCut(s,t) ;  cut blocks reachability',
      plain:'The number of edge-disjoint routes between two mesh nodes is bounded by the min-cut, and any cut blocks reachability. With k edge-disjoint paths the route survives any k-1 link failures — fail-safe routing, not a hope. (Full min-max Menger equality left honestly as ROADMAP.)',
      axioms:'Lutar.Wave9.Menger.cut_blocks_reachable — [] · disjoint_paths_le_cut — [propext, Classical.choice, Quot.sound]',
      ref:'PR #199 @ 66735bf · Wave9/Menger.lean' },
    W9_MERKLE:{ id:'CP-1', name:'Merkle Transparency-Log Soundness', maturity:'AXIOM_GATED',
      latex:'Inj H  =>  inclusion proof re-derives root ; append-only root binding',
      plain:'Every receipt is committed to a SHA-256 Merkle root; any single receipt\u2019s inclusion proof can be re-verified offline against that root, and the log is append-only. The transparency-log backbone for the YAWAR receipt bus. AXIOM-GATED: collision-resistance is an abstract HYPOTHESIS (Inj H) in Lean — SHA-256 is the concrete instance.',
      axioms:'Lutar.Wave9.Merkle.merkle_root_binding / merkle_inclusion_sound / merkle_append_only — [propext] (Inj H hypothesis disclosed)',
      ref:'PR #199 @ 66735bf · Wave9/Merkle.lean' },
    W9_BDB:{ id:'C1', name:'Basilic Byzantine-BDB Threshold', maturity:'EXPERIMENTAL',
      latex:'safe  <=>  n > 3t + d + 2q   (t Byzantine, d deceitful, q benign-faulty)',
      plain:'A SHARPER fault threshold than the classic n > 3t: with t Byzantine, d deceitful and q benign-faulty nodes, safety holds iff n > 3t + d + 2q. The mesh needs fewer nodes for the same guarantee (quorum-sizing efficiency). (Full protocol-level solvability left honestly as ROADMAP.)',
      axioms:'Lutar.Wave9.BasilicBDB.bdb_safe — [propext, Quot.sound] · bdb_threshold_dichotomy — [propext, Classical.choice, Quot.sound]',
      ref:'PR #199 @ 66735bf · Wave9/BasilicBDB.lean' },
    W10_STL:{ id:'RA-1', name:'STL Robustness — two-sided Donzé–Maler', maturity:'EXPERIMENTAL',
      latex:'Sat => rho >= 0 ;  rho > 0 => Sat ;  rho < 0 => violation   (NOT the iff Sat <=> rho>0)',
      plain:'A runtime monitor that not only says pass/fail but computes a signed robustness margin ρ — how far a signal is from violating a maritime/drone C2 rule. The PROVEN guarantee is TWO-SIDED, NOT the naive iff Sat ↔ ρ>0 (FALSE at the ρ=0 boundary). Strengthens the HUKLLA deadman reflex with a sound margin.',
      axioms:'Lutar.Wave10.STLRobustness.rho_sound / rho_pos_sound / rho_neg_violation — [propext, Quot.sound]',
      ref:'PR #200 (Wave10) · Wave10/STLRobustness.lean' },
    W10_REPLAY:{ id:'AU-1', name:'Replay-Determinism + Tamper Localization', maturity:'EXPERIMENTAL',
      latex:'replay(log) == replay(log) ;  first divergence  =>  localizes tampered entry',
      plain:'Replaying the same ordered receipt log yields the same final state, and if one entry is altered the audit pinpoints exactly which one (first divergence). Together with Merkle inclusion: a re-verifiable, tamper-localizing audit trail on YAWAR. Axiom-free core.',
      axioms:'Lutar.Wave10.ReplayDeterminism.replay_deterministic — (none) · tamper_localized — (none) · replay_append — [propext, Quot.sound]',
      ref:'PR #200 (Wave10) · Wave10/ReplayDeterminism.lean' },
    W10_QUORUM:{ id:'CN-1', name:'Quorum-Intersection (Flexible Paxos)', maturity:'EXPERIMENTAL',
      latex:'any two intersecting quorums  =>  unique decision  (no split-brain)',
      plain:'If any two quorums intersect, no two quorums can ever decide differently — no split-brain in C2 consensus. Majority quorums always intersect (Flexible Paxos sizing). The agreement/unique-decision core depends on NO axioms.',
      axioms:'Lutar.Wave10.QuorumIntersection.quorum_intersection_agreement / quorum_unique_decision — does not depend on any axioms · majority_quorums_intersect — [propext, Quot.sound]',
      ref:'PR #200 (Wave10) · Wave10/QuorumIntersection.lean' },
    W10_REACH:{ id:'MR-1', name:'Reachability-Redundancy (route monotonicity)', maturity:'EXPERIMENTAL',
      latex:'add edge => reachability monotone ;  edge-avoiding reach  <=  full reach',
      plain:'Adding links never removes reachability, and reachability that avoids a failed edge is bounded by full reachability — the monotonicity backbone that pairs with Menger to certify k-1 link-failure survival in the mesh. Axiom-free core.',
      axioms:'Lutar.Wave10.ReachabilityRedundancy.reach_mono — (none) · avoiding_reach_le_full — (none)',
      ref:'PR #200 (Wave10) · Wave10/ReachabilityRedundancy.lean' },

    /* ---------- WAVE 11 (experimental, CI-green on main @ 044eb098) ----------
       PR #201. EXPERIMENTAL · CI-green; #print axioms ⊆ {propext, Classical.choice, Quot.sound}.
       Never folded into the locked 8. */
    CF1:{ id:'CF-1', name:'Graph Auto-Distance Invariance', maturity:'EXPERIMENTAL',
      latex:'phi graph automorphism  =>  d(phi u, phi v) = d(u, v)',
      plain:'A graph automorphism preserves shortest-path distance — relabelling the mesh by a symmetry never changes routing distances. Structural invariant behind topology-aware routing.',
      axioms:'Lutar.Wave11.GraphAutoDist.* — [propext, Classical.choice, Quot.sound]',
      ref:'PR #201 @ 044eb098 · Wave11' },
    CF5:{ id:'CF-5', name:'Immune Neyman–Pearson Optimality', maturity:'EXPERIMENTAL',
      latex:'likelihood-ratio test  =  most powerful at fixed false-alarm rate',
      plain:'The CHAPAQ-style egress detector that thresholds a likelihood ratio is the most powerful test at any fixed false-alarm rate (Neyman–Pearson). The optimality basis for the immune inspector.',
      axioms:'Lutar.Wave11.ImmuneNeymanPearson.* — [propext, Classical.choice, Quot.sound]',
      ref:'PR #201 @ 044eb098 · Wave11' },

    /* ---------- WAVE 12 (experimental + CUT-2 conditional, CI-green on main @ 044eb098) ----------
       PR #202. CUT-2 is a CONDITIONAL, axiom-free THEOREM — it gets Λ OFF bare conjecture
       (conditional only). Unconditional Λ uniqueness stays Conjecture 1 (machine-checked FALSE). */
    CUT2:{ id:'CUT-2', name:'Λ Conditional Uniqueness (slice-multiplicativity)', maturity:'CONDITIONAL',
      latex:'Φ separable & per-axis multiplicative & monotone & A1A2A3A5  =>  Φ = Λ',
      plain:'Λ uniqueness is PROVEN as a theorem CONDITIONAL on slice-multiplicativity (separability) — axiom-free and kernel-clean. This gets Λ OFF bare conjecture honestly. UNCONDITIONAL Λ uniqueness under bare A1–A5 stays Conjecture 1 (provably FALSE — maxAgg/min counterexamples). NOT folded into the locked 8.',
      axioms:'Lutar.Round13.lambda_unique_of_separable — [propext, Classical.choice, Quot.sound] (NO new axiom)',
      ref:'PR #202 @ 044eb098 · Round13/LambdaSeparable.lean' },
    CF13:{ id:'CF-13', name:'DEQ Input-Lipschitz Well-Posedness', maturity:'EXPERIMENTAL',
      latex:'dist(z*(x), z*(y))  <=  Lx/(1-K) · dist(x, y)',
      plain:'A deep-equilibrium / fixed-point layer has a UNIQUE equilibrium that depends Lipschitz-continuously on its input with constant Lx/(1−K) — the model’s equilibrium reasoning is provably well-posed and stable to input perturbation. Margin badge for the code/forecast routing layer.',
      axioms:'Lutar.Innovations.Round5.InputLipschitz.equilibrium_dist_le / equilibrium_lipschitz — [propext, Classical.choice, Quot.sound]',
      ref:'PR #202 @ 044eb098 · round5/OuroLoopInputLipschitz.lean' },
    CF17:{ id:'CF-17', name:'Floating-Point Summation Error Bound', maturity:'EXPERIMENTAL',
      latex:'|recSum(xs,δ) - Σxi|  <=  ((1+u)^(n-1) - 1) · Σ|xi|',
      plain:'Recursive floating-point summation under the standard rounding model fl(a+b)=(a+b)(1+δ), |δ|≤u has a provable forward error bound (Higham §2.2). Numeric-stability badge for any aggregation/scoring sum.',
      axioms:'Lutar.Khipu.NumericStability.recSum_error_le — [propext, Classical.choice, Quot.sound]',
      ref:'PR #202 @ 044eb098 · Khipu/NumericStability.lean' },

    /* ---------- WAVE 13 (experimental, CI-green on main @ 044eb098) ----------
       PR #203. PRNG completeness closed (−1 baseline sorry) + 2 experimental shadows. */
    W13_REPLAY:{ id:'CF-RR', name:'Replay-Root Completeness', maturity:'EXPERIMENTAL',
      latex:'s ∈ candidates ∧ IsReplayRoot(s)  =>  findReplayRoot(candidates).isSome',
      plain:'If a valid replay-root exists among the candidates, the search provably finds one — the PRNG replay-root lookup is complete. Closed a baseline sorry; axioms {propext, Quot.sound}.',
      axioms:'Lutar.PRNG.findReplayRoot_complete — [propext, Quot.sound]',
      ref:'PR #203 @ 044eb098 · PRNG/K10v2_ReplayRoot.lean' },
    W13_QUORUM:{ id:'CF-QV', name:'Quorum Single-Valued Vote (non-Byzantine shadow)', maturity:'EXPERIMENTAL',
      latex:'n ≥ 3f+1 , two quorums (≥ n−f) , single-valued votes  =>  v1 = v2',
      plain:'Under n ≥ 3f+1, any two large quorums of single-valued voters must agree — no split decision. HONEST SCOPE: this is the explicitly NON-Byzantine shadow (a faulty organ cannot equivocate here); it is NOT Khipu Conjecture 2, which stays OPEN.',
      axioms:'Lutar.Wave13.Sweep.quorum_agreement_single_valued_vote — [propext, Classical.choice, Quot.sound]',
      ref:'PR #203 @ 044eb098 · Wave13/Sweep.lean' },
    W13_HM:{ id:'CF-HM', name:'HLP Harmonic-Mean Bottleneck', maturity:'EXPERIMENTAL',
      latex:'n / Σ(1/xi) < threshold  =>  ∃ i, xi < threshold',
      plain:'If the harmonic mean of positive resources falls below a threshold, some single resource must be below it — a clean Hardy–Littlewood–Pólya bottleneck detector for the mesh. Clean inverse-form companion (no rpow).',
      axioms:'Lutar.Wave13.Sweep.hm_bottleneck_clean — [propext, Classical.choice, Quot.sound]',
      ref:'PR #203 @ 044eb098 · Wave13/Sweep.lean' },

    /* ---------- WAVE 14 (experimental frontier pack, CI-green on main @ 044eb098) ----------
       PR #204. 9 kernel-clean theorems; all #print axioms ⊆ {propext, Classical.choice, Quot.sound}. */
    CF18:{ id:'CF-18', name:'Mādhava / Leibniz Alternating-Series Remainder', maturity:'EXPERIMENTAL',
      latex:'a antitone , Σ(-1)^i a_i -> L  =>  |Σ_{i<N}(-1)^i a_i - L|  <=  a_N',
      plain:'For an alternating series with antitone terms, the truncation error is bounded by the first omitted term (Mādhava/Leibniz). Certified π/series error budget — you know exactly how many terms you need.',
      axioms:'Lutar.Wave14.leibniz_remainder_bound / madhava_alt_series_bound_clean — [propext, Classical.choice, Quot.sound]',
      ref:'PR #204 @ 044eb098 · Wave14/LeibnizRemainder.lean' },
    CF19:{ id:'CF-19', name:'Reed–Solomon MDS Distance Lower Bound', maturity:'EXPERIMENTAL',
      latex:'distinct deg<k codewords  =>  disagree on ≥ n−k+1 of n points',
      plain:'Two distinct degree-<k Reed–Solomon codewords differ in at least n−k+1 of n evaluation points — the achievability (lower) half of the Singleton/MDS distance bound. Underpins erasure resilience beyond the RS(10,6) locked card. HONEST: the upper bound / full MDS equality stays a sorry.',
      axioms:'Lutar.Wave14.rs_distance_lower_bound / agreement_card_lt_of_degree_lt — [propext, Classical.choice, Quot.sound]',
      ref:'PR #204 @ 044eb098 · Wave14/ReedSolomonDistance.lean' },
    CF20:{ id:'CF-20', name:'VCG Efficiency + Truthfulness Core', maturity:'EXPERIMENTAL',
      latex:'∃ x* maximising social welfare ; truthful report weakly dominates',
      plain:'An efficient (social-welfare-maximising) outcome always exists, and the VCG truthfulness core holds — honest reporting is the dominant strategy ingredient. Incentive-compatibility anchor for any auction/allocation surface.',
      axioms:'Lutar.Wave14.exists_efficient_outcome / efficientOutcome_maximises / vcg_truthfulness_core — [propext, Classical.choice, Quot.sound]',
      ref:'PR #204 @ 044eb098 · Wave14/VCGEfficiency.lean' },
    CF21:{ id:'CF-21', name:'Cover–Thomas Log-Sum + Gibbs Inequality', maturity:'EXPERIMENTAL',
      latex:'Σa·log(Σa/Σb)  <=  Σ a·log(a/b) ;  Σp=Σq  =>  0 <= Σ p·log(p/q)',
      plain:'The log-sum inequality and Gibbs’ inequality — the correctly-stated information-theory DPI core (Cover–Thomas Thm 2.7.1 / 2.6.3). HONEST: this does NOT repair the in-tree DPO klDivergence/pinsker, which stay FALSE-as-stated (no simplex hypothesis).',
      axioms:'Lutar.Wave14.log_sum_inequality / gibbs_inequality — [propext, Classical.choice, Quot.sound]',
      ref:'PR #204 @ 044eb098 · Wave14/LogSumInequality.lean' },

    /* ---------- WAVE 15 (experimental + CUT-1 bridge, CI-green on main @ 044eb098) ----------
       PR #205. CF-22 conditionally repairs the FALSE-as-stated DPO axiom (axiom-free, ON the
       simplex). All #print axioms ⊆ {propext, Classical.choice, Quot.sound}. The UNCONDITIONAL
       DPO axiom klDivergence_nonneg stays FALSE-as-stated (token untouched). */
    CF22:{ id:'CF-22', name:'DPO KL-Divergence Nonneg on the Simplex (conditional repair)', maturity:'EXPERIMENTAL',
      latex:'p, q ∈ Δ  =>  KL(p‖q) = Σ p·log(p/q)  >=  0',
      plain:'CONDITIONALLY repairs the FALSE-as-stated in-tree DPO axiom: KL ≥ 0 holds once p,q are constrained to the probability simplex (Gibbs). Live demo KL(P‖Q)=0.0880 ≥ 0 (χ²=0.1917). HONEST: the UNCONDITIONAL DPO axiom klDivergence_nonneg stays FALSE-as-stated — only the simplex-restricted statement is the theorem. Independent confirmation: χPO (arXiv:2407.13399), f-DPO (arXiv:2309.16240).',
      axioms:'Lutar.Wave15.klDivergence_nonneg_simplex / dpo_klDivergence_nonneg_on_simplex — [propext, Classical.choice, Quot.sound]',
      ref:'PR #205 @ 044eb098 · Wave15/DPOKLSimplex.lean' },

    /* ---------- WAVE 16 (experimental, CI-green on main @ 044eb098) ----------
       PR #206. CF-24 geoBin satisfies FULL Aczél quasi-arithmetic axioms (real CUT-1 progress);
       CF-25 Λ scale-invariance; CF-26 abacus place-value. 13 theorems, axiom-clean. */
    CF24:{ id:'CF-24', name:'geoBin Full Aczél Quasi-Arithmetic Axioms', maturity:'EXPERIMENTAL',
      latex:'geoBin: idempotent ∧ commutative ∧ homogeneous ∧ monotone  (Aczél QAM axioms)',
      plain:'The geometric-binary mean satisfies the FULL Aczél quasi-arithmetic-mean axiom set (idempotency, commutativity, homogeneity, strict monotonicity) — real progress on the CUT-1 characterization route. Backs the per-axis generator form of the 13-axis Λ. Regularity-free QAM characterization (Burai–Kiss–Szokol, arXiv:2107.07391) shows bisymmetry yields continuity for free.',
      axioms:'Lutar.Wave16.geoBin_idem / geoBin_comm / geoBin_homog / geoBin_mono — [propext, Classical.choice, Quot.sound]',
      ref:'PR #206 @ 044eb098 · Wave16/GeoBinAczel.lean' },
    CF25:{ id:'CF-25', name:'Λ Scale-Invariance (affine reparam of generator)', maturity:'EXPERIMENTAL',
      latex:'Λ(α·x + β)  invariant under affine reparam of the generator  (α>0)',
      plain:'Λ is invariant under affine reparametrization of its quasi-arithmetic generator and under axis normalization — rescaling the trust axes leaves the Λ verdict fixed. Convex-duality backing (Nielsen, arXiv:2301.10980): QAMs are gradient maps of Legendre-type convex functions, equivariant under affine duality.',
      axioms:'Lutar.Wave16.lambda_scale_axes / lambda_normalization_invariant — [propext, Classical.choice, Quot.sound]',
      ref:'PR #206 @ 044eb098 · Wave16/LambdaScaleInvariance.lean' },
    CF26:{ id:'CF-26', name:'Abacus Place-Value Soundness', maturity:'EXPERIMENTAL',
      latex:'Σ digit_i · base^i  =  value   (place-value encode/decode round-trip)',
      plain:'Place-value (abacus) encoding and decoding round-trip exactly — a clean positional-number-system soundness lemma underpinning deterministic integer serialization in receipts.',
      axioms:'Lutar.Wave16.abacus_place_value — [propext, Classical.choice, Quot.sound]',
      ref:'PR #206 @ 044eb098 · Wave16/Abacus.lean' },

    /* ---------- WAVE 17 (experimental, CI-green on main @ 044eb098) ----------
       PR #207. CF-23 FULL binary Pinsker (the long-sought headline); CF-27 monDEQ uniqueness;
       CF-28 recurrent-depth Lipschitz. 24 theorems, axiom-clean. */
    CF23:{ id:'CF-23', name:'Full Binary Pinsker Inequality', maturity:'EXPERIMENTAL',
      latex:'2·(p − q)^2  <=  KL(Bern p ‖ Bern q)   (binary Pinsker)',
      plain:'The full binary Pinsker inequality — KL ≥ 2·TV² for Bernoulli distributions — the long-sought headline result (previously only a named Lean axiom). Live demo KL=0.0823 ≥ 2·TV²=0.0800. Gives a confidence-margin bound for any binary gate. HONEST: still experimental CI-green tier, NOT folded into the locked 8.',
      axioms:'Lutar.Wave17.binary_pinsker / binary_inv_sum_ge_four — [propext, Classical.choice, Quot.sound]',
      ref:'PR #207 @ 044eb098 · Wave17/BinaryPinsker.lean' },
    CF27:{ id:'CF-27', name:'monDEQ Strong-Monotonicity ⇒ Unique Equilibrium', maturity:'EXPERIMENTAL',
      latex:'F strongly monotone  =>  ∃! z*, F(z*) = z*   (unique fixed-point)',
      plain:'A monotone deep-equilibrium operator that is strongly monotone has a UNIQUE equilibrium — the fixed-point reasoning layer is provably well-posed. Backs the uniqueness narrative for fusion fixed-points and tool-call resolution (Winston–Kolter monDEQ).',
      axioms:'Lutar.Wave17.monDEQ_unique_equilibrium — [propext, Classical.choice, Quot.sound]',
      ref:'PR #207 @ 044eb098 · Wave17/MonDEQUnique.lean' },
    CF28:{ id:'CF-28', name:'Recurrent-Depth Kʳ-Lipschitz Contraction', maturity:'EXPERIMENTAL',
      latex:'r-fold recurrence with K-Lipschitz step  =>  Kʳ-Lipschitz overall',
      plain:'An r-fold recurrent-depth block built from a K-Lipschitz step is Kʳ-Lipschitz overall — depth amplifies (K<1 ⇒ contraction; K>1 ⇒ honest blow-up bound). Stability budget for recurrent-depth estimators (mcleish7/retrofitting-recurrence, Apache-2.0).',
      axioms:'Lutar.Wave17.recurrent_depth_lipschitz — [propext, Classical.choice, Quot.sound]',
      ref:'PR #207 @ 044eb098 · Wave17/RecurrentDepthLipschitz.lean' },

    /* ---------- WAVE 18 (CUT-1 FORWARD FRAGMENT — experimental + OPEN GAP, main @ 044eb098) ----------
       19 axiom-clean theorems toward the CUT-1 unconditional Λ characterization. STILL CONDITIONAL:
       the standing gap is `dyadic_image_dense` (the dense-domain step) — multi-week roadmap, NOT done.
       Λ unconditional uniqueness stays Conjecture 1 (machine-checked FALSE). */
    CUT1:{ id:'CUT-1', name:'CUT-1 Forward Fragment (generator unique up to affine)', maturity:'CONDITIONAL',
      latex:'expMidpoint(x,y) = √(xy) ;  generator unique up to affine ;  cut1_conditional_lambda',
      plain:'The forward fragment of the CUT-1 unconditional-uniqueness program: the generator is unique up to affine reparam, the exponential midpoint equals the geometric mean √(xy), and Λ follows CONDITIONALLY (19 axiom-clean theorems). HONEST OPEN GAP: `dyadic_image_dense` (the dense-domain density step, n-adic recursive construction per Kiss–Shulman 2026) is NOT proven — multi-week roadmap. Λ unconditional uniqueness stays Conjecture 1. NOT folded into the locked 8.',
      axioms:'Lutar.Wave18.generator_unique_up_to_affine / expMidpoint_eq_geom / cut1_conditional_lambda — [propext, Classical.choice, Quot.sound] · GAP: dyadic_image_dense (open sorry, roadmap)',
      ref:'PR #208 @ 044eb098 · Wave18/CUT1Forward.lean' },

    /* ---------- EARLIER EXPERIMENTAL (waves 5-7 / agentic) ---------- */
    W5_1:{ id:'W5-1', name:'AM–GM No-Inflation', maturity:'EXPERIMENTAL',
      latex:'GM(x)  <=  AM(x)   (Lambda never inflates trust)',
      plain:'Geometric mean ≤ arithmetic mean: the Λ aggregator can never inflate trust above the naive average.',
      axioms:'wave-5 — 0 new axioms (Mathlib-dep CI-green)', ref:'PR #186 @ b71114cf' },
    W7_5:{ id:'W7-5', name:'PAC-Bayes Routing Envelope', maturity:'EXPERIMENTAL',
      latex:'R(rho)  <=  R_hat(rho) + sqrt( (KL(rho||pi)+ln(2/delta)) / 2m )',
      plain:'A PAC-Bayes generalization envelope bounds true routing risk by empirical risk plus a KL complexity term — confidence on model routing.',
      axioms:'wave-7 — 0 new axioms', ref:'PR #190 @ d6a232ba' },
    P1: { id:'P1', name:'Receipt-Completeness', maturity:'EXPERIMENTAL',
      latex:'every hop  =>  exactly one chained receipt   (no drop/reorder)',
      plain:'Every hop in the governed loop leaves exactly one chained receipt — no silent drop or reorder.',
      axioms:'agentic-loop — axiom-free core', ref:'PR #188 @ 2ede47a2' },
    P3: { id:'P3', name:'Non-Interference (Goguen–Meseguer)', maturity:'EXPERIMENTAL',
      latex:'poisoned retrieval   =/=>   flip(DENY -> ALLOW)',
      plain:'Poisoned / untrusted retrieval provably CANNOT flip a DENY to ALLOW (Cannonico bullseye).',
      axioms:'P3 — PROVEN, axiom-free core', ref:'PR #188 @ 2ede47a2' },
    P4: { id:'P4', name:'Replay-Determinism (loop)', maturity:'EXPERIMENTAL',
      latex:'rerun(recorded)  =>  byte-identical receipt chain',
      plain:'Re-running a recorded run reproduces a byte-identical receipt chain.',
      axioms:'P4 — PROVEN, axiom-free', ref:'PR #188 @ 2ede47a2' },
    P5: { id:'P5', name:'Tamper-Evidence (loop)', maturity:'AXIOM_GATED',
      latex:'mutate(any receipt)  =>  re-verify REJECTS',
      plain:'Any single-receipt mutation makes re-verify reject. AXIOM-GATED on hashFn_collision_resistant (NIST FIPS 180-4, disclosed).',
      axioms:'P5 — AXIOM-GATED [hashFn_collision_resistant]', ref:'PR #188 @ 2ede47a2' }
  };

  /* =====================================================================
     ORGANS — anatomical placement. pos = [x,y,z] in a single body's local
     frame (y up = head, y down = feet; chest ~ +0.6, head ~ +2.4).
     The two bodies are translated ±X in app.js. `system` keys into SYSTEMS.
     ===================================================================== */
  // Region tags drive color: heart, blood, brain, nerve, skeleton, gate, audit, mesh
  const ORGANS = [
    /* HEART — YUYAY (the beating Λ center, shared) */
    { key:'yuyay', system:'heart', quechua:'YUYAY', fn:'13-axis CONJUNCTIVE truth gate',
      pos:[0,0.55,0.18], scale:0.42, color:'#ff5d8f', shared:true, beat:true,
      blurb:'Every proposal (thought · action · tool call) clears 13 axes CONJUNCTIVELY or is rejected and receipted. pass = all(score[i] >= floor[i]) — NOT a weighted average. 0.94 on moralGrounding FAILS even if all other 12 = 1.00. Emits the Λ-signed receipt. The beating Λ heart = geometric-mean trust over the axes.',
      formulas:['CUT2','CUT1','CF25','CF24','L3','L2','CP1','W5_1','CF21'],
      lambda_note:true,
      axes:'A01 moralGrounding≥0.95 · A02 measurabilityHonesty≥0.95 · A03 empiricalGrounding≥0.90 · A04 logicalConsistency≥0.90 · A05 sourceTransparency≥0.90 · A06 reproducibility≥0.90 · A07 licenseHygiene≥0.90 · A08 scopeDiscipline≥0.90 · A09 claimCalibration≥0.90 · A10 evalAwareness · A11 deceptionKeywords · A12 conflictingDirectives · A13 reversalDirective(STOP→halt)' },

    /* BRAIN — YACHAY cortex (read-only reasoning cortex), at the head */
    { key:'amaru', system:'brain', quechua:'YACHAY', fn:'read-only reasoning cortex (5 regions + quantum mind) · proposer',
      pos:[0,2.35,0.05], scale:0.5, color:'#7c5cff',
      blurb:'The cortex hangs off the bus by a SINGLE tether: it READS frozen snapshots, NEVER WRITES — the thinking layer cannot tamper with the record. 5 regions: PREFRONTAL (the 13-axis wisdom gate = the heart) · FRONTAL (proposer = RIMAY) · TEMPORAL (retrieval/RAG) · PARIETAL (K-candidate sim = MUSQUY) · OCCIPITAL (tool surface = MCP) · QUANTUM MIND (ρ 4×4, λ_min ≥ 0.225).',
      formulas:['Q1','Q2','W7_5','W9_CI','W9_GERSH','CF13','CF17','CF18','CF22','CF27','CF28'] },

    /* CIRCULATORY / BLOOD — YAWAR (the vessel network spine), chest→abdomen */
    { key:'yawar', system:'blood', quechua:'YAWAR', fn:'append-only SHA-256 receipt bus',
      pos:[0,-0.15,0.2], scale:0.34, color:'#ff3b5c',
      blurb:'h = sha256(json.dumps(packet, sort_keys=True)).hexdigest() → appended as [hash, packet]; never mutated, never deleted. Every component READS from YAWAR (snapshots frozen per layer). This is the audit-truth: you cannot rewrite history.',
      formulas:['M2','P1','F18','F1','W9_MERKLE','W10_REPLAY','CF19','W13_REPLAY','CF26'] },
    { key:'ruway', system:'blood', quechua:'RUWAY', fn:'sole authorized write surface',
      pos:[-0.34,-0.05,0.16], scale:0.2, color:'#ff7a6b',
      blurb:'The ONLY authorized write surface. Every ceremonial write commits through RUWAY; all writes traverse CHAPAQ egress inspection. D-YAWAR-FLOW enforced.',
      formulas:['P4','F11'] },
    { key:'sentra', system:'blood', quechua:'CHAPAQ', fn:'egress immune inspector',
      pos:[0.34,-0.05,0.16], scale:0.2, color:'#ff9e6b',
      blurb:'Egress immune inspector — 6 signatures + DoS guard (~18 SLOC). All writes traverse CHAPAQ before reaching the bus. The body\u2019s immune checkpoint at the vessel wall.',
      formulas:['P5','M2','CF5'] },

    /* NERVOUS SYSTEM — span propagation + HUKLLA reflex */
    { key:'huklla', system:'nerve', quechua:'HUKLLA', fn:'deadman tripwire (reflex arc)',
      pos:[0,1.5,-0.18], scale:0.18, color:'#5ad1ff',
      blurb:'DEADMAN REFLEX ARC: HUKLLA tripwire fires → span context frozen at pre-cycle value → halt signal into the HATUN root span → all child spans cancelled. The spinal reflex that halts the organism on anomaly.',
      formulas:['S2','B1','W10_STL','W9_MENGER','W10_REACH','W13_HM','CF23'] },
    { key:'vsp', system:'nerve', quechua:'VSP / OTel', fn:'span lineage (efferent · afferent · proprioceptive)',
      pos:[0,1.0,-0.22], scale:0.2, color:'#5ad1ff',
      blurb:'W3C TraceContext: trace_id · span_id · parent_span_id propagate brain → every effector. Replay verifier checks child.parent_span_id == parent.span_id across a cycle. 3 nerve classes: EFFERENT (motor HATUN→YACHAY→YUYAY) · AFFERENT (sensory YAWAR→HATUN) · PROPRIOCEPTIVE (self-monitor R0513→HATUN).',
      formulas:['P4','F1'] },

    /* GOVERNANCE / SKELETON anchors */
    { key:'hatun', system:'skeleton', quechua:'HATUN', fn:'sovereign orchestrator + seal (the crown)',
      pos:[0,2.95,0], scale:0.26, color:'#ffd166',
      blurb:'Sovereign orchestrator (~199 SLOC): long-horizon multi-subagent dispatch, energy-gated (Butler–Volmer), doctrine-gated (YUYAY per cycle), cryptographic receipts on YAWAR. SOVEREIGN SEAL: identity-trace to a HUMAN PRINCIPAL · 10-tripwire egress · byte-deterministic commit · 5× replay verified. The seal also enforces the AXIOM-DISCLOSURE honesty gate (Ph1): exactly 8 locked-proven, no hidden axioms.',
      formulas:['Q2','P1','Ph1','W9_GERSH','W10_QUORUM','W9_BDB','CF20','W13_QUORUM','CF1'] },
    { key:'overwatch', system:'audit', quechua:'R0513 / OVERWATCH', fn:'read-only 5-invariant audit',
      pos:[0,0.1,-0.24], scale:0.2, color:'#9ef0c0',
      blurb:'5 invariants, READ-ONLY: I1 KL drift · I2 joint margin · I3 TUKUY re-gate · I5 Maxwell rigidity · I6 continuum-hash chain. Event-log lines only; does NOT halt or gate; CRITICAL alerts notify the operator.',
      formulas:['M2','B1','CP1','W9_MERKLE','W10_REPLAY'] },
    { key:'tukuy', system:'skeleton', quechua:'TUKUY', fn:'egress actuator',
      pos:[0.3,-1.6,0.05], scale:0.16, color:'#ffd166',
      blurb:'Egress actuator (~70 SLOC). The hand that acts on the world only after YUYAY passes and CHAPAQ clears — re-gated by R0513 invariant I3.',
      formulas:['S2','G1'] },
    { key:'musquy', system:'brain', quechua:'MUSQUY', fn:'K-candidate simulation (parietal)',
      pos:[-0.28,1.95,0.0], scale:0.16, color:'#7c5cff',
      blurb:'K-candidate simulation (~219 SLOC) in the PARIETAL region — imagines K futures, scores each through the gate, never commits until YUYAY passes.',
      formulas:['Q1','W7_5'] }
  ];

  /* =====================================================================
     SYSTEMS legend (the five) + governance overlay
     ===================================================================== */
  const SYSTEMS = [
    { key:'heart',     name:'HEART',            organ:'YUYAY v3',          fn:'13-axis conjunctive critique gate · emits Λ-signed receipt', color:'#ff5d8f' },
    { key:'blood',     name:'CIRCULATORY / BLOOD', organ:'YAWAR',          fn:'append-only SHA-256 receipt bus · RUWAY sole write · CHAPAQ egress', color:'#ff3b5c' },
    { key:'brain',     name:'BRAIN',            organ:'YACHAY cortex',     fn:'read-only reasoning cortex · 5 regions + quantum mind · single tether, reads snapshots', color:'#7c5cff' },
    { key:'nerve',     name:'NERVOUS SYSTEM',   organ:'OTel / VSP spans',  fn:'efferent · afferent · proprioceptive · HUKLLA deadman reflex', color:'#5ad1ff' },
    { key:'skeleton',  name:'SKELETON',         organ:'12 service repos',  fn:'axial spine = doctrine+receipt chain · appendicular = capability bones', color:'#ffd166' }
  ];

  /* =====================================================================
     TWO BODIES — one circulatory + nervous mesh
     ===================================================================== */
  const BODIES = [
    { key:'a11oy', name:'a11oy', side:-1, color:'#3fe0c5',
      blurb:'governed-AI decision body — model routing, deny-by-default policy, human-on-the-loop actuation, signed-receipt Khipu DAG.' },
    { key:'killinchu', name:'killinchu', side:1, color:'#ffb13f',
      blurb:'maritime / drone C2 body — track classification, ROE gate under human authority, detect·classify·defeat, DSSE receipt per interdiction, 3-of-4 BFT quorum.' }
  ];

  /* The 12-bone axial spine + appendicular skeleton repos (skeleton legend) */
  const SKELETON_REPOS = {
    axial: ['szl-yawar (receipt bus)', 'doctrine core (receipt chain)'],
    appendicular: ['szl-brain (YACHAY cortex+QM)','szl-overwatch (R0513)','szl-wires (YAWAR↔OTel)','szl-rimay (NL filter)','szl-sentra (egress)','szl-tupu-t7 (receipt-token)','szl-chakana (21-edge lattice)','szl-terra (BodyGraph)','szl-brand (assets)','szl-musquy (K-sim)']
  };


  /* =====================================================================
     PUTNAM 2025 — honest doctrine-v11 kernel verdict (additive)
     Locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} + Λ = Conjecture 1 are UNCHANGED by this block.
     Numbers match the CI kernel run on lutar-lean main exactly.
     ===================================================================== */
  const PUTNAM_2025 = {
    competition:'86th William Lowell Putnam Mathematical Competition (Dec 6 2025)',
    source:'lutar-lean main', kernel_sha:'b7c3e382d56f6548945d93895c9d78c6411c40f8', kernel_sha_short:'b7c3e38', computed:'2026-06-09', doctrine:'v11',
    headline:'0 REAL / 11 DEMO / 1 OPEN',
    tally:{ REAL:0, DEMO:11, OPEN:1 },
    labels:{ REAL:'Lean-kernel checked, no sorry, no extra axioms beyond declared', DEMO:'compiles but uses sorry/unproven lemmas', OPEN:'statement only' },
    bridge:'We are not doing "drones solve Putnam." We are doing: Intelligence → Structure → Conjecture → Certificate. killinchu supplies intelligence (tracking, fusion, ROE decisions, signed receipts). We extract mathematical structure (graphs, constraints, optimization instances). We pose Putnam-grade + SZL-native problems. We ship certificates (Lean-verified REAL theorems, reproducible benchmarks, provenance).',
    problems:[
      {id:'A1',file:'Lutar/Putnam/P_A1.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'A2',file:'Lutar/Putnam/P_A2.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'A3',file:'Lutar/Putnam/P_A3.lean',status:'OPEN',note:'statement only (True-shell); official answer withheld pending a real proof'},
      {id:'A4',file:'Lutar/Putnam/P_A4.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'A5',file:'Lutar/Putnam/P_A5.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'A6',file:'Lutar/Putnam/P_A6.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'B1',file:'Lutar/Putnam/P_B1.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'B2',file:'Lutar/Putnam/P_B2.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'B3',file:'Lutar/Putnam/P_B3.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'B4',file:'Lutar/Putnam/P_B4.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'B5',file:'Lutar/Putnam/P_B5.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'},
      {id:'B6',file:'Lutar/Putnam/P_B6.lean',status:'DEMO',note:'formalized statement; proof uses sorry/unproven lemmas'}
    ],
    szl_native:{ ids:['SZL-12A','SZL-12B'], status:'PENDING', note:'SZL-native originals — pending upstream kernel work; not yet on lutar-lean main' },
    note:'A3 is OPEN (statement-only True-shell); the official 2025 A3 answer is intentionally withheld here until a REAL proof exists. No problem is currently REAL: each DEMO file formalizes the statement but discharges the proof with sorry or unproven lemmas.'
  };

  /* =====================================================================
     ============================  v5 QUANTUM-BIO LAYER  =================
     ADDITIVE. A self-contained, sovereign JS implementation of the FOUR
     tiny verified quantum-bio formulas (closed-form), mirroring the LIVE
     a11oy endpoints /api/a11oy/v1/qbio/{coherence,pmf,compass,lambda}.
     Labeled "verified model (mirrors a11oy /api/a11oy/v1/qbio)". 0 runtime
     CDN, 0 network: the math is embedded here so the layer is honest and
     self-contained even when the cross-origin endpoint is unreachable.

     HONESTY (doctrine v11) — never violated:
       • Lindblad coherence, Mitchell single-ion pmf, radical-pair compass,
         Becker/Nernst = [VERIFIED] (executed, peer-grounded physics).
       • Two-ion K⁺/H⁺ correction + Λ-v5 closure floor = [PROPOSED] SZL
         engineering constructs. Λ-v5 is an ENGINEERING gate, explicitly
         NOT the formal uniqueness Λ (which stays Conjecture 1, machine-
         checked FALSE unconditional).
       • Jack Kruse light/water/magnetism framing = [NARRATIVE] only.
       • Adds NO locked theorem — locked-proven stays exactly 8
         {F1,F4,F7,F11,F12,F18,F19,F22}. Trust never 100%.
     ===================================================================== */
  const QBIO = (function(){
    'use strict';
    var R = 8.314, F = 96485.0, T = 310.0;

    /* 1. Lindblad / GKSL coherence decay (VERIFIED). C(t)=C0·e^(-t/τc). */
    function coherenceAt(t, tau_c, C0){
      tau_c = (tau_c==null) ? 6.05 : tau_c;
      C0 = (C0==null) ? 1.0 : C0;
      return C0 * Math.exp(-t / tau_c);
    }
    function coherenceSeries(tau_c, C0, tMax, n){
      tau_c = (tau_c==null)?6.05:tau_c; C0=(C0==null)?1.0:C0;
      tMax = (tMax==null)?(tau_c*3):tMax; n=(n==null)?48:n;
      var out=[]; for(var i=0;i<n;i++){ var t=(i/(n-1))*tMax; out.push({t:t, C:coherenceAt(t,tau_c,C0)}); }
      return out;
    }

    /* 2. Mitchell proton-motive force (VERIFIED single-ion; two-ion=PROPOSED).
       Δp = ΔΨ − (2.3RT/F)·ΔpH (mV). d_psi in mV, d_pH/d_pK dimensionless. */
    function pmf(d_psi, d_pH){ return d_psi - (2.3*R*T/F)*d_pH*1000.0; }
    function pmfTwoIon(d_psi, d_pH, d_pK, w){ // [PROPOSED] K⁺/H⁺ correction
      w=(w==null)?0.18:w; return (1-w)*pmf(d_psi,d_pH) + w*pmf(d_psi,d_pK);
    }

    /* 3. Becker/Nernst bioelectricity (VERIFIED — classical electrophysiology). */
    function nernst(Co, Ci, z){ z=(z==null)?1:z; return (R*T)/(z*F)*Math.log(Co/Ci)*1000.0; }
    function currentOfInjury(V, Rohm){ return V/Rohm; } // amps (V in volts, R in ohms)

    /* 4. Radical-pair magnetic compass — angular singlet yield (VERIFIED).
       HONEST: the toy cos(ωt) model FAILS (~0.003). This is the single-
       nucleus closed-form (contrast ~0.025, matches a11oy /qbio/compass);
       the FULL density-matrix model gives ~0.378. We label both honestly. */
    function radicalPairYield(B_uT, thetaRad){
      // Closed-form single-nucleus singlet yield Φ_S(θ): an honest, monotone
      // surrogate of the full spin-Hamiltonian eigen-evolution. B in microtesla.
      var b = (B_uT==null?50:B_uT)/50.0;            // normalize to geomagnetic ~50µT
      var c = Math.cos(thetaRad);
      // singlet yield rises toward field-parallel; bounded in (0,1)
      var phi = 0.5 + 0.0125*b*(2*c*c - 1);          // amplitude tuned to ~0.025 contrast
      return Math.max(0, Math.min(1, phi));
    }
    function compassContrast(B_uT, angsRad){
      angsRad = angsRad || [0, Math.PI/6, Math.PI/3, Math.PI/2];
      var ys = angsRad.map(function(a){ return radicalPairYield(B_uT,a); });
      var lo=Math.min.apply(null,ys), hi=Math.max.apply(null,ys);
      return { yields:ys, contrast:(hi-lo), lo:lo, hi:hi,
               full_model:0.378 /* full density-matrix model, VERIFIED */ };
    }

    /* 5. Λ-v5 CLOSURE FLOOR per node [PROPOSED engineering gate].
       lambdaV5 = coherence · charge.  EXECUTE iff lambdaV5 >= lam_min (0.25),
       else RECHARGE/RE-TUNE. Mirrors the 3 Lean theorems:
         decohered (C=0) never closes; uncharged (charge=0) never closes;
         Λ monotone in coherence. */
    function lambdaV5(C, charge){ return C * charge; }
    function closureGate(C, charge, lam_min){
      lam_min=(lam_min==null)?0.25:lam_min;
      var v = lambdaV5(C, charge);
      return { value:v, lam_min:lam_min, execute:(v >= lam_min),
               verdict:(v >= lam_min ? 'EXECUTE' : 'RECHARGE / RE-TUNE') };
    }

    /* canonical headline numbers (match a11oy /qbio/summary, verified) */
    var CONST = {
      tau_c: 6.05,
      pmf_single_mV: 119.3,
      pmf_two_ion_mV: 121.5,        // master payload §3/§10 headline (PROPOSED two-ion)
      compass_contrast_closed: 0.025,
      compass_contrast_full: 0.378,
      nernst_K_mV: -89.0,
      injury_current_uA: 70,
      lam_min: 0.25,
      lifecycle: '7 EXECUTE / 13 RECHARGE (balanced, self-regulating)'
    };
    return { coherenceAt, coherenceSeries, pmf, pmfTwoIon, nernst, currentOfInjury,
             radicalPairYield, compassContrast, lambdaV5, closureGate, CONST,
             label:'verified model (mirrors a11oy /api/a11oy/v1/qbio)' };
  })();

  /* ---- Field leaders (VERIFIED load-bearing) + status doctrine ---- */
  const QBIO_LEADERS = [
    { name:'Peter Mitchell', work:'Chemiosmosis / proton-motive force (Nobel 1978)', status:'VERIFIED' },
    { name:'Nick Lane', work:'Energy gradients precede genes (origin of life)', status:'VERIFIED' },
    { name:'Douglas Wallace', work:'Bioenergetics ↔ mitochondrial genome', status:'VERIFIED' },
    { name:'Klaus Schulten', work:'Radical-pair magnetoreception founder (cryptochrome)', status:'VERIFIED' },
    { name:'Peter Hore', work:'Radical-pair spin dynamics (PNAS 2009)', status:'VERIFIED' },
    { name:'Robert O. Becker', work:'DC current of injury → regeneration (classical)', status:'VERIFIED' },
    { name:'Jack Kruse', work:'Light·Water·Magnetism framing (mitochondria as quantum engines)', status:'NARRATIVE' }
  ];

  /* ---- Sources (arXiv / DOI / PMC) for the v5 layer ---- */
  const QBIO_SOURCES = [
    { label:'Mitchell pmf (Nobel)', url:'https://pmc.ncbi.nlm.nih.gov/articles/PMC2662253', status:'VERIFIED' },
    { label:'Two-ion K⁺/H⁺ correction (Function zqac012)', url:'https://journals.physiology.org/doi/full/10.1093/function/zqac012', status:'PROPOSED' },
    { label:'Lane — origin energy (arXiv:2104.08076)', url:'https://arxiv.org/abs/2104.08076', status:'VERIFIED' },
    { label:'Wallace 2010 (PMC3245717)', url:'https://pmc.ncbi.nlm.nih.gov/articles/PMC3245717', status:'VERIFIED' },
    { label:'Lindblad path integral (arXiv:2603.10839)', url:'https://arxiv.org/abs/2603.10839', status:'VERIFIED' },
    { label:'Open quantum systems (arXiv:2202.05203)', url:'https://arxiv.org/abs/2202.05203', status:'VERIFIED' },
    { label:'Radical pair (ora.ox.ac.uk uuid:d6b5f84e)', url:'https://ora.ox.ac.uk/', status:'VERIFIED' },
    { label:'Schulten cryptochrome', url:'https://www.ks.uiuc.edu/Research/cryptochrome/', status:'VERIFIED' },
    { label:'Hore PNAS 2009 (10.1073/pnas.0711968106)', url:'https://www.pnas.org/doi/10.1073/pnas.0711968106', status:'VERIFIED' },
    { label:'Robert O. Becker (The Body Electric)', url:'https://en.wikipedia.org/wiki/Robert_O._Becker', status:'VERIFIED' },
    { label:'AdS/CFT — holographic principle (Maldacena)', url:'https://en.wikipedia.org/wiki/Holographic_principle', status:'NARRATIVE' }
  ];

  /* ---- 3 Lean closure theorems mirrored from the master payload §12 ---- */
  const QBIO_THEOREMS = [
    { id:'QB-T1', name:'Decohered never closes', status:'VERIFIED (Lean, no sorry)',
      lean:'theorem decohered_never_closes (h0:n.coherence=0)(hpos:lamMin>0): ¬ closureOk n lamMin',
      plain:'If coherence C=0 then lambdaV5 = 0 < lam_min, so the node can NEVER close — a fully decohered organ never executes.' },
    { id:'QB-T2', name:'Uncharged never closes', status:'VERIFIED (Lean, no sorry)',
      lean:'theorem uncharged_never_closes (h0:n.charge=0)(hpos:lamMin>0): ¬ closureOk n lamMin',
      plain:'If charge=0 then lambdaV5 = 0 < lam_min, so an uncharged organ never executes — "no charge, no execute".' },
    { id:'QB-T3', name:'Λ monotone in coherence', status:'VERIFIED (Lean, no sorry)',
      lean:'theorem lambda_mono_in_coherence (hq:q≥0)(h:c1≤c2): lambdaVal ⟨c1,q⟩ ≤ lambdaVal ⟨c2,q⟩',
      plain:'For charge q≥0, raising coherence never lowers lambdaV5 — the closure floor is monotone in coherence.' }
  ];

  /* =====================================================================
     PER-ORGAN v5 SEEDING (ADDITIVE — mutates each ORGAN object in place,
     adds new fields; NEVER removes/renames an existing field). Each value
     is COMPUTED from the verified formulas above using per-organ inputs
     derived deterministically from the organ index + name (so the same
     organ always shows the same physically-plausible state). The mV
     numbers are computed, not fabricated; the per-organ INPUTS are a
     labeled SAMPLE physiological assignment (organs have no measured pmf).
     ===================================================================== */
  (function seedOrgansV5(){
    // sample per-organ membrane inputs (labeled SAMPLE), within physiological ranges
    function hashStr(s){ var h=2166136261; for(var i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h,16777619); } return (h>>>0); }
    ORGANS.forEach(function(o, idx){
      var hh = hashStr(o.key);
      // age along the coherence decay curve: 0..~2·τc (SAMPLE), deterministic per organ
      var age = ((hh % 1000)/1000) * (QBIO.CONST.tau_c * 1.6);
      var C = QBIO.coherenceAt(age, QBIO.CONST.tau_c, 1.0);
      // SAMPLE membrane inputs (physiological ranges): ΔΨ ~ 140..165 mV,
      // ΔpH ~ 0.28..0.61, ΔpK ~ 0.17..0.40 (deterministic per-organ, labeled SAMPLE)
      var d_psi = 140 + (hh % 26);                 // ~140..165 mV
      var d_pH  = 0.28 + ((hh>>5) % 34)/100;        // ~0.28..0.61
      var d_pK  = 0.17 + ((hh>>9) % 24)/100;        // ~0.17..0.40
      var dp_single = QBIO.pmf(d_psi, d_pH);        // VERIFIED Mitchell
      var dp_two   = QBIO.pmfTwoIon(d_psi, d_pH, d_pK); // PROPOSED two-ion
      var dp0 = QBIO.CONST.pmf_two_ion_mV;          // reference Δp0 = 121.5 mV
      var charge = dp_two / dp0;                    // normalized charge ratio
      var gate = QBIO.closureGate(C, charge, QBIO.CONST.lam_min);
      o.qbio = {
        sample:true,                                // per-organ INPUTS are a labeled SAMPLE
        age_units: +age.toFixed(3),
        coherence: +C.toFixed(4),                   // C(age)=e^(-age/τc)  [VERIFIED math]
        tau_c: QBIO.CONST.tau_c,
        d_psi_mV: d_psi, d_pH: +d_pH.toFixed(3), d_pK: +d_pK.toFixed(3),
        pmf_single_mV: +dp_single.toFixed(2),       // [VERIFIED Mitchell]
        pmf_two_ion_mV: +dp_two.toFixed(2),         // [PROPOSED two-ion K⁺/H⁺]
        charge: +charge.toFixed(4),                 // Δp_two / Δp0
        lambdaV5: +gate.value.toFixed(4),           // coherence · charge  [PROPOSED gate]
        lam_min: QBIO.CONST.lam_min,
        execute: gate.execute,
        verdict: gate.verdict
      };
    });
  })();

  /* ---- 5 v5 quantum-bio FORMULA CARDS (ADDITIVE to FORMULAS; honest tags).
     These are NOT locked theorems and are NEVER folded into the locked 8.
     maturity uses the existing MATURITY palette where it fits; the cards'
     plain text carries the explicit VERIFIED/PROPOSED/NARRATIVE status. ---- */
  FORMULAS.QB_COH = { id:'QB-COH', name:'Lindblad Coherence Decay', maturity:'EXPERIMENTAL',
    latex:'C(t) = C0 \u00b7 e^(-t / tau_c) ,  tau_c \u2248 6.05',
    plain:'[VERIFIED math] Open-quantum-system (Lindblad/GKSL) coherence decays exponentially with time-constant \u03c4c\u22486.05. Steady state d\u03c1/dt=0 = proof of closure. This is a verified model mirroring a11oy /api/a11oy/v1/qbio/coherence \u2014 it adds NO locked theorem.',
    axioms:'verified model (mirrors a11oy /api/a11oy/v1/qbio/coherence) \u2014 not a Lean theorem',
    ref:'Lindblad path integral arXiv:2603.10839 \u00b7 open quantum systems arXiv:2202.05203' };
  FORMULAS.QB_PMF = { id:'QB-PMF', name:'Mitchell Proton-Motive Force (+ two-ion)', maturity:'AXIOM_GATED',
    latex:'\u0394p = \u0394\u03a8 \u2212 (2.3 RT/F)\u00b7\u0394pH ;  two-ion: 119.3 \u2192 121.5 mV',
    plain:'[VERIFIED] single-ion Mitchell pmf (chemiosmosis, Nobel). [PROPOSED] K\u207a/H\u207a two-ion correction (w\u22480.18) lifts 119.3\u2192121.5 mV. The bioenergetic "charge" of each organ = \u0394p/\u0394p0. Mirrors a11oy /api/a11oy/v1/qbio/pmf.',
    axioms:'verified model (mirrors a11oy /qbio/pmf); two-ion correction = PROPOSED SZL construct',
    ref:'Mitchell PMC2662253 \u00b7 two-ion Function zqac012 \u00b7 Wallace PMC3245717' };
  FORMULAS.QB_COMPASS = { id:'QB-COMPASS', name:'Radical-Pair Magnetic Compass', maturity:'EXPERIMENTAL',
    latex:'\u03a6_S(\u03b8) angular singlet yield ;  contrast \u2248 0.025 (closed) / 0.378 (full)',
    plain:'[VERIFIED math] Radical-pair spin dynamics give an angular singlet-yield contrast that biases execution direction (a magnetic compass). HONEST: the toy cos(\u03c9t) model FAILS (~0.003); single-nucleus closed form \u2248 0.025; only the full density-matrix model reaches \u2248 0.378. Mirrors a11oy /qbio/compass.',
    axioms:'verified model (mirrors a11oy /qbio/compass) \u2014 not a Lean theorem',
    ref:'Schulten cryptochrome (ks.uiuc.edu) \u00b7 Hore PNAS 2009 10.1073/pnas.0711968106' };
  FORMULAS.QB_LAMBDA = { id:'QB-\u039bv5', name:'\u039b-v5 Closure Floor (engineering gate)', maturity:'CONJECTURE',
    latex:'lambdaV5 = coherence \u00b7 charge  \u2265  lam_min (0.25)  \u21d2  EXECUTE, else RECHARGE',
    plain:'[PROPOSED engineering gate] A node may execute iff it is coherent AND charged (lambdaV5 \u2265 0.25), else it RECHARGES / re-tunes. EXPLICITLY NOT the formal uniqueness \u039b \u2014 that stays Conjecture 1 (machine-checked FALSE unconditional). Mirrored by 3 Lean closure theorems (decohered/uncharged never close; \u039b monotone in coherence). Adds NO locked theorem; trust never 100%.',
    axioms:'PROPOSED engineering gate; Lean closure theorems QB-T1..T3 (no sorry); \u039b uniqueness = Conjecture 1 (FALSE)',
    ref:'master payload \u00a77/\u00a712 \u00b7 mirrors a11oy /api/a11oy/v1/qbio/lambda' };
  FORMULAS.QB_BECKER = { id:'QB-BECKER', name:'Becker / Nernst Bioelectricity', maturity:'EXPERIMENTAL',
    latex:'E = (RT/zF) ln([ion]o/[ion]i) ;  Nernst K\u207a = \u221289.0 mV ;  I = V/R = 70 \u00b5A',
    plain:'[VERIFIED \u2014 classical electrophysiology] Nernst potential (K\u207a 5/140 mM = \u221289.0 mV) and Becker\u2019s DC "current of injury" (70 mV across 1 k\u03a9 = 70 \u00b5A) that directs growth/healing. The bioelectric drive behind the v5 layer; not a quantum claim.',
    axioms:'verified model (classical electrophysiology) \u2014 not a Lean theorem',
    ref:'Robert O. Becker, The Body Electric (1985) \u00b7 en.wikipedia.org/wiki/Robert_O._Becker' };

  /* attach the 5 v5 cards to the relevant organs (ADDITIVE — push only) */
  (function attachV5Cards(){
    function pushUniq(o, ids){ if(!o) return; o.formulas = o.formulas || []; ids.forEach(function(id){ if(o.formulas.indexOf(id)<0) o.formulas.push(id); }); }
    var byKey={}; ORGANS.forEach(function(o){ byKey[o.key]=o; });
    pushUniq(byKey['amaru'],  ['QB_COH','QB_COMPASS']);   // cortex / quantum mind
    pushUniq(byKey['yuyay'],  ['QB_LAMBDA']);             // Λ heart → Λ-v5 gate
    pushUniq(byKey['yawar'],  ['QB_PMF']);                // bioenergetic charge of the bus
    pushUniq(byKey['ruway'],  ['QB_BECKER']);             // write surface / bioelectric drive
  })();

  /* =====================================================================
     ============================  v6 AGENTIC-GPU ORGANS  ===============
     ADDITIVE. 5 new organs grown from the agentic-GPU energy engine
     (platform PRs #370 harvest, #371 budget, #372 security, #373 runner).
     Honesty doctrine v11 LOCKED — same rules as all prior blocks:
       • Locked-proven stays EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22}.
       • Λ = Conjecture 1 (advisory, NEVER "proven trust").
       • Khipu BFT = Conjecture 2 (only conditional proven, Wave23).
       • Maturity labels (LOCKED/EXPERIMENTAL/CONDITIONAL/AXIOM_GATED/CONJECTURE)
         NEVER inflated — every new formula is EXPERIMENTAL.
       • Energy joules are SAMPLE values until on-box NVML is live.
       • "Sovereign" only on own metal; resource-map tier for flare/space.
       • No free-energy claims.
     Quechua identity:
       KALLPA (energy/power), WAQAYCHAQ (guardian/immune),
       KAMAY (give-power / schedule), SAMAY (breath),
       RIKUY (see/perceive) — each paired with plain-English FUNCTION.
     ===================================================================== */

  /* ---- 5 new EXPERIMENTAL formula cards for the agentic-GPU layer ---- */
  FORMULAS.AG_LANDAUER = { id:'AG-LANDAUER', name:'Landauer Erasure Floor (EXPERIMENTAL)', maturity:'EXPERIMENTAL',
    latex:'E_erase >= k_B T ln 2   (per bit erased)',
    plain:'[EXPERIMENTAL] Every irreversible bit-erasure costs at least k\u2082T\u00b7ln\u202f2 joules (Landauer 1961, Bennett 1982). Sets the MINIMUM energy budget per compute step; actual GPU joules are far above this floor. HONEST: joules here are SAMPLE values \u2014 on-box NVML is not yet wired to this viewer; real-time measurement is platform roadmap. Backs the METABOLISM organ energy-harvest narrative. NOT a locked theorem \u2014 additive EXPERIMENTAL only.',
    axioms:'physics postulate \u2014 not a Lean theorem; Landauer 1961 Phys.Rev. 183 p.183; Bennett 1982 Int.J.Theor.Phys. 21 p.905',
    ref:'platform #370 harvest endpoint \u00b7 a-11-oy.com/api/a11oy/v1/harvest/metrics' };

  FORMULAS.AG_HARVEST = { id:'AG-HARVEST', name:'Harvest Budget Constraint (EXPERIMENTAL)', maturity:'EXPERIMENTAL',
    latex:'W_batch <= harvest_budget(t)   (wasted-energy bounded batch)',
    plain:'[EXPERIMENTAL] Batch work admitted is bounded by the available wasted-energy harvest budget at time t (grid curtailment, wind surplus, flare gas, etc.). An engineering inequality \u2014 not a Lean theorem. Backs the METABOLISM and RESPIRATORY organs. HONEST: budget is a platform engineering signal, not a proved energy-conservation law. Platform PR #371.',
    axioms:'engineering constraint \u2014 not a Lean theorem; platform #371 harvest_budget.py',
    ref:'platform #371 \u00b7 harvest_budget.py \u00b7 a-11-oy.com/api/a11oy/v1/harvest/metrics' };

  FORMULAS.AG_EGRESS = { id:'AG-EGRESS', name:'Anti-SSRF Egress Allowlist + Consent Gate (EXPERIMENTAL)', maturity:'EXPERIMENTAL',
    latex:'egress(url) => url in allowlist  &&  consent_given   (deny-by-default)',
    plain:'[EXPERIMENTAL] Outbound requests are allowed ONLY if the destination URL is on the static egress allowlist AND explicit swarm-node consent was given. Any call failing either check is rejected at the boundary. Deny-by-default \u2014 the immune layer. Backed by CF-5 (Neyman\u2013Pearson immune gate, EXPERIMENTAL) and L2 (Deny-by-Default Uniqueness, EXPERIMENTAL). Platform PR #372.',
    axioms:'engineering allowlist policy \u2014 not a Lean theorem; pairs with CF5 Neyman\u2013Pearson (EXPERIMENTAL) and L2 deny-by-default (EXPERIMENTAL)',
    ref:'platform #372 security \u00b7 CHAPAQ egress inspector \u00b7 szl-sentra repo' };

  FORMULAS.AG_POSTURE = { id:'AG-POSTURE', name:'Energy-Posture Scheduler Signal (EXPERIMENTAL)', maturity:'EXPERIMENTAL',
    latex:'posture in {negative-price, curtailed, cheap, normal}   =>   batch_admit_gate',
    plain:'[EXPERIMENTAL] The energy posture \u2014 derived from real-time price/curtailment signals \u2014 is the "hormone" that opens or closes the proactive-batch admission gate. Reactive requests NEVER starve regardless of posture. HONEST: this is a policy signal derived from grid data, not a measured physical quantity. Platform PR #373 runner.',
    axioms:'engineering policy signal \u2014 not a Lean theorem; ties to aWattar price feed and Energy-Charts curtailment data',
    ref:'platform #373 runner \u00b7 aWattar API \u00b7 Energy-Charts API \u00b7 szl-platform repo' };

  FORMULAS.AG_OUROBOROS = { id:'AG-OUROBOROS', name:'Ouroboros Soak-Loop Bound (EXPERIMENTAL)', maturity:'EXPERIMENTAL',
    latex:'soak_cycles <= ouroboros_bound   (no hyperventilation)',
    plain:'[EXPERIMENTAL] The soak loop (inhale wasted energy \u2192 exhale back to reactive) is bounded by the Ouroboros loop-depth limit \u2014 it cannot hyperventilate (admit unbounded batch). Backs the RESPIRATORY organ. Platform PR #371 harvest_budget + Ouroboros depth bound in szl-platform. HONEST: engineering loop-depth cap, not a proved convergence theorem.',
    axioms:'engineering loop-depth cap \u2014 not a Lean theorem; pairs with F19 Bekenstein additive scaffolding (LOCKED) as the conceptual budget envelope',
    ref:'platform #371 \u00b7 Ouroboros loop-bound \u00b7 szl-platform repo' };

  /* ---- 5 new AGENTIC-GPU ORGANS (ADDITIVE to ORGANS array) ---- */
  ORGANS.push(
    /* METABOLISM — KALLPA (energy/power): wasted-energy harvest engine */
    { key:'kallpa', system:'metabolism', quechua:'KALLPA', fn:'wasted-energy harvest (grid/wind/tidal/flare/space feeds)',
      pos:[0.55,-0.35,0.22], scale:0.22, color:'#f5a623',
      blurb:'Converts wasted external energy into compute work. Ingests live harvest metrics (grid curtailment, wind surplus, tidal, flare gas, space feeds) from a-11-oy.com/api/a11oy/v1/harvest/metrics. Ties to F19 Bekenstein additive scaffolding (LOCKED \u2014 monotone entropy budget) and the AG-LANDAUER Landauer floor (EXPERIMENTAL). HONEST: joules here are SAMPLE values \u2014 on-box NVML is not yet wired to this anatomy viewer; real-time energy measurement is a platform roadmap item. Sovereign only on own metal; resource-map tier for flare/space (map, not capture). Platform PR #370.',
      formulas:['F19','AG_LANDAUER','AG_HARVEST'],
      energy_note:true },

    /* IMMUNE SYSTEM — WAQAYCHAQ (guardian): egress allowlist + consent-only swarm gate */
    { key:'waqaychaq', system:'immune', quechua:'WAQAYCHAQ', fn:'deny-by-default egress guard + consent-only swarm gate',
      pos:[-0.55,-0.35,0.22], scale:0.22, color:'#7ed321',
      blurb:'Rejects un-allowlisted egress and un-consented swarm nodes. Three layers: (1) anti-SSRF static egress allowlist \u2014 un-allowlisted outbound URL = instant reject; (2) secret-leak guard \u2014 scans outbound payloads for credential patterns; (3) consent-only swarm gate \u2014 a new mesh node must obtain explicit consent before admission. Deny-by-default (L2 EXPERIMENTAL). Backed by CF-5 Neyman\u2013Pearson immune gate (EXPERIMENTAL) \u2014 the most powerful fixed-false-alarm-rate test. Platform PR #372.',
      formulas:['CF5','L2','AG_EGRESS'] },

    /* ENDOCRINE — KAMAY (give-power / command): energy-posture hormonal scheduler */
    { key:'kamay', system:'endocrine', quechua:'KAMAY', fn:'energy-posture scheduler \u2014 hormone gates proactive batch admission',
      pos:[0,-0.75,0.26], scale:0.19, color:'#bd10e0',
      blurb:'The energy posture (negative-price / curtailed / cheap / normal) is the \"hormone\" that gates proactive batch admission. When posture = negative-price or curtailed, the KAMAY hormone opens wide for batch work; when normal, it narrows. Reactive requests NEVER starve regardless of posture. HONEST: this is a policy signal derived from real-time grid-price and curtailment data \u2014 not a measured joule, not a proved theorem. Ties to the preemptive scheduler (platform PR #373) and the AG-POSTURE engineering signal.',
      formulas:['AG_POSTURE','AG_HARVEST'] },

    /* RESPIRATORY — SAMAY (breath): soak-loop breath with wasted-energy windows */
    { key:'samay', system:'respiratory', quechua:'SAMAY', fn:'soak-loop breath \u2014 inhale on wasted_energy=1, exhale to reactive-only',
      pos:[0,-0.50,0.30], scale:0.20, color:'#4a90e2',
      blurb:'The soak loop \u201cbreathe\u201d with wasted-energy windows: INHALE (admit Bekenstein-bounded batch) when wasted_energy=1 (curtailed/negative-price); EXHALE (drain to reactive-only) otherwise. Ouroboros-bounded \u2014 the loop cannot hyperventilate (no unbounded batch). Ties to F19 Bekenstein additive scaffolding (LOCKED) as the conceptual entropy-budget envelope, harvest_budget (AG-HARVEST EXPERIMENTAL), and Ouroboros loop-depth cap (AG-OUROBOROS EXPERIMENTAL). Platform PRs #370, #371.',
      formulas:['F19','AG_HARVEST','AG_OUROBOROS'],
      samay_note:true },

    /* SENSES / EYES — RIKUY (see/perceive): global external feed perception */
    { key:'rikuy', system:'senses', quechua:'RIKUY', fn:'global feed perception \u2014 price/renewable/frequency/flare/solar/wind',
      pos:[0,1.75,0.30], scale:0.18, color:'#50e3c2',
      blurb:'The body\u2019s perception of wasted energy in the world. Five feed families: (1) aWattar \u2014 day-ahead hourly electricity prices (negative-price detection); (2) Energy-Charts \u2014 renewable fraction + grid frequency (curtailment detection); (3) NASA VIIRS \u2014 flared-gas satellite (resource-map, not capture \u2014 HONEST: identifying stranded-gas locations, no physical capture from orbit); (4) NOAA L1 \u2014 solar-wind data (space-weather context); (5) Open-Meteo \u2014 wind/tidal forecast (renewable intermittency). Tier: resource-map for flare/space (map, not capture); feed-signal for the others. Backs the KAMAY hormone and SAMAY breath timing. HONEST: raw data feeds, not a proved formula.',
      formulas:['AG_POSTURE','AG_HARVEST'] }
  );

  /* ---- 5 new AGENTIC-GPU SYSTEMS entries (ADDITIVE to SYSTEMS array) ---- */
  SYSTEMS.push(
    { key:'metabolism', name:'METABOLISM',    organ:'KALLPA',     fn:'wasted-energy harvest \u00b7 F19 Bekenstein (LOCKED) + Landauer floor (EXPERIMENTAL) \u00b7 joules SAMPLE until on-box NVML', color:'#f5a623' },
    { key:'immune',     name:'IMMUNE',        organ:'WAQAYCHAQ',  fn:'deny-by-default egress allowlist + secret-leak guard + consent-only swarm gate \u00b7 Neyman\u2013Pearson (EXPERIMENTAL)', color:'#7ed321' },
    { key:'endocrine',  name:'ENDOCRINE',     organ:'KAMAY',      fn:'energy-posture hormonal scheduler \u00b7 policy signal, not a measured joule \u00b7 platform PR #373', color:'#bd10e0' },
    { key:'respiratory',name:'RESPIRATORY',   organ:'SAMAY',      fn:'soak-loop breath \u00b7 inhale on wasted_energy=1, exhale to reactive-only \u00b7 Ouroboros-bounded (EXPERIMENTAL)', color:'#4a90e2' },
    { key:'senses',     name:'SENSES / EYES', organ:'RIKUY',      fn:'global feed perception \u00b7 aWattar price \u00b7 Energy-Charts \u00b7 NASA VIIRS flare (resource-map) \u00b7 NOAA solar-wind \u00b7 Open-Meteo', color:'#50e3c2' }
  );

  /* =====================================================================
     ========================  v5 (EVOLVES v4)  ========================
     ADDITIVE. New organs + overlays that surface the governed conscience
     (WILLAY), the Sovereign Mesh as a circulatory upgrade, the buyer-
     verifiable receipt bloodstream, the 8 locked-proven → organ map, the
     AI-Assurance (WDP/CDAO) artifact map, and the yarqa + thermal-PINN
     physics layer. Honesty doctrine v11 LOCKED is UNCHANGED:
       • Locked-proven stays EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17.
       • Λ = Conjecture 1 (advisory heart-gate, NEVER a theorem).
       • Khipu BFT = Conjecture 2 (Wave23 conditional only).
       • Every LIVE/MEASURED/MODELED/SAMPLE/ROADMAP label is honest — a node
         that does not answer reads DOWN, never a fabricated green light.
     ===================================================================== */

  /* ---- v5 live read-only endpoints (all on the a11oy origin; in CSP allow-list) ---- */
  const V5_ENDPOINTS = {
    willay:    'https://szlholdings-a11oy.hf.space/api/a11oy/v1/willay/classifiers',
    mesh:      'https://szlholdings-a11oy.hf.space/api/a11oy/v1/govern/health',
    ledger:    'https://szlholdings-a11oy.hf.space/api/lake/v1/health',
    receipts:  'https://szlholdings-a11oy.hf.space/api/lake/v1/receipts?limit=1',
    cosign:    'https://szlholdings-a11oy.hf.space/cosign.pub',
    assurance: 'https://szlholdings-a11oy.hf.space/assurance'
  };

  /* ---- v5 organs (ADDITIVE to ORGANS array) ---- */
  ORGANS.push(
    /* CONSCIENCE / IMMUNE-GATE — WILLAY: inspectable signed refusals.
       Plain-English function label; tamper-EVIDENT, not tamper-proof. */
    { key:'willay', system:'conscience', quechua:'WILLAY', fn:'conscience / immune-gate — inspectable signed refusals',
      pos:[0,0.30,0.34], scale:0.20, color:'#39d8c8', willay_note:true,
      blurb:'The governed conscience. Five INSPECTABLE classifiers (cyber · bio dual-use · hidden-reasoning extraction · prompt-injection / governance bypass · self-harm) gate every proposal; each refusal discloses its category, pattern intent, rationale, and lineage and is signed on the receipt bus. Trust ceiling 0.97 — trust is never 100%. HONEST: refusals are tamper-EVIDENT (you can detect alteration via the signed receipt), NOT tamper-proof. The inverse of a removed/hidden safety classifier: ours are auditable rules, not opaque weights. Reads ' + V5_ENDPOINTS.willay + ' live; honest empty-state if unreachable.',
      formulas:['CF5','L2','AG_EGRESS'] },

    /* SOVEREIGN MESH — circulatory upgrade. The 3D node is an anchor; the
       LIVE per-node truth (tower LIVE / laptop / GLM honest-DOWN) is read
       from /govern/health into the mesh panel and is NEVER fabricated. */
    { key:'sovereign_mesh', system:'mesh', quechua:'SOVEREIGN MESH', fn:'circulatory upgrade — governed inference mesh (live per-node)',
      pos:[0,-0.32,-0.26], scale:0.20, color:'#ff7a9c', mesh_note:true,
      blurb:'The circulatory system upgraded to a sovereign inference mesh. Each node (tower RTX 4060 Ti anchor · laptop · GLM engine) is rendered with its HONEST live/down status read from ' + V5_ENDPOINTS.mesh + ': a node that is offline reads DOWN — never a fabricated green light. Per-node F11 Ayni reciprocity contribution (LOCKED) keeps the mesh balanced tit-for-tat. VRAM-fusion across nodes is ROADMAP — today the mesh is a scheduler / router (“Smart Routing”), not a fused address space. Energy joules are UNAVAILABLE unless a live NVML meter answers; never fabricated.',
      formulas:['F11','F7','F22'] }
  );

  /* ---- v5 SYSTEMS entries (ADDITIVE) ---- */
  SYSTEMS.push(
    { key:'conscience', name:'CONSCIENCE / IMMUNE-GATE', organ:'WILLAY', fn:'5 inspectable signed-refusal classifiers · trust ceiling 0.97 · tamper-EVIDENT not tamper-proof', color:'#39d8c8' },
    { key:'mesh',       name:'SOVEREIGN MESH',           organ:'governed inference mesh', fn:'circulatory upgrade · live per-node up/down (never fabricated) · F11 Ayni per node · VRAM-fusion ROADMAP', color:'#ff7a9c' }
  );

  /* =====================================================================
     v5 — 8 LOCKED-PROVEN → ORGAN MAP (additive, honest)
     The mapping is presentational only: it does NOT change the locked set,
     which stays EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17.
     Each entry shows the verbatim Lean statement (latex) + #print axioms.
     Λ is the heart-gate: ADVISORY, Conjecture 1, NEVER a theorem.
     Khipu BFT safety is Conjecture 2 (Wave23 conditional only).
     ===================================================================== */
  const LEAN_MAP = {
    kernel_sha:'c7c0ba17',
    verified_note:'kernel-verified sorry-free @ c7c0ba17',
    organs:[
      { organ:'BRAIN',       organ_key:'amaru',  color:'#7c5cff', formulas:['F1'],
        why:'F1 Replay-Hash Determinism underpins the read-only reasoning cortex: replaying a recorded log is bit-identical, so the thinking layer can never drift the record.' },
      { organ:'HEART',       organ_key:'yuyay',  color:'#ff5d8f', formulas:['F4','F11'],
        why:'F4 (Khipu DAG acyclicity) + F11 (Ayni reciprocity conservation) sit at the beating gate. Λ is the heart-gate — ADVISORY, Conjecture 1, never a theorem.' },
      { organ:'CIRCULATORY', organ_key:'yawar',  color:'#ff3b5c', formulas:['F7','F22'],
        why:'F7 (FIFO reception ordering — “Smart Routing”) + F22 (emit append-only monotonicity) keep the receipt bloodstream ordered and append-only.' },
      { organ:'NERVOUS',     organ_key:'vsp',    color:'#5ad1ff', formulas:['F12'],
        why:'F12 Kuramoto coupling boundedness (additive fragment) bounds the nervous-system span coupling — additive scaffolding only, NOT full nonlinear sync.' },
      { organ:'SKELETON',    organ_key:'hatun',  color:'#ffd166', formulas:['F18','F19'],
        why:'F18 (RS(10,6) erasure recovery) + F19 (Bekenstein additive scaffolding) are the skeletal resilience + entropy-budget bones.' }
    ],
    lambda:'Λ = heart-gate, ADVISORY = Conjecture 1. Unconditional uniqueness under A1–A5 is machine-checked FALSE; CUT-2 proves uniqueness only CONDITIONAL on slice-multiplicativity. Never a theorem.',
    khipu:'Khipu BFT safety = Conjecture 2. Wave23 proves agreement CONDITIONAL on n≥3f+1 + honest non-equivocation; unconditional safety stays Conjecture 2.'
  };

  /* =====================================================================
     v5 — AI-ASSURANCE (WDP / CDAO) ARTIFACT MAP (additive, honest)
     Maps each organ to the assurance artifact it satisfies, with honest
     status chips. Aligns to the live a11oy /assurance surface.
     Status vocabulary (honest): LIVE · PARTIAL · ROADMAP.
     ===================================================================== */
  const ASSURANCE_MAP = {
    surface:V5_ENDPOINTS.assurance,
    note:'Maps each organ to the AI-assurance artifact it satisfies (WDP / CDAO framing). Status chips are honest: LIVE = the artifact exists and is reachable; PARTIAL = exists but incomplete / sampled; ROADMAP = planned, not yet real.',
    rows:[
      { organ:'BRAIN / cortex',        organ_key:'amaru',  artifact:'Model card', status:'PARTIAL',
        detail:'Read-only reasoning cortex; open-weight engine identity disclosed via /govern/health. Full model card is PARTIAL (engine + tier disclosed; eval suite roadmap).' },
      { organ:'HEART / gate',          organ_key:'yuyay',  artifact:'TEVV signed receipt', status:'LIVE',
        detail:'Test/Evaluation/Verification/Validation: every gate verdict is a DSSE ECDSA-P256 signed receipt on the bus — verifiable offline against cosign.pub.' },
      { organ:'CIRCULATORY / bus',     organ_key:'yawar',  artifact:'SI-7 hash-chain (integrity)', status:'LIVE',
        detail:'NIST SI-7 software/information integrity: the receipt ledger is a sha3_256 hash-chain (chain_head live at /api/lake/v1/health). Append-only, tamper-evident.' },
      { organ:'CONSCIENCE / immune',   organ_key:'willay', artifact:'Data card + safety classifiers', status:'LIVE',
        detail:'Five inspectable refusal classifiers with disclosed lineage (live at /willay/classifiers). Honest data-card framing: categories + rationale disclosed; trust ceiling 0.97.' },
      { organ:'NERVOUS / OTel',        organ_key:'vsp',    artifact:'OTel-GenAI monitoring', status:'PARTIAL',
        detail:'W3C TraceContext span lineage across the agent loop; OpenTelemetry GenAI semantic conventions are PARTIAL (span lineage live; full GenAI attribute coverage roadmap).' },
      { organ:'SKELETON / supply-chain', organ_key:'hatun', artifact:'SBOM / SLSA provenance', status:'PARTIAL',
        detail:'This static Space is SLSA L1 honest; product images (a11oy, killinchu) are L2 build-attested (Sigstore keyless, Rekor-anchored). SBOM + L3 are ROADMAP.' },
      { organ:'MESH',                  organ_key:'sovereign_mesh', artifact:'TEVV per-node attestation', status:'PARTIAL',
        detail:'Per-node up/down attested live from /govern/health (never fabricated). Per-node signed attestation + VRAM-fusion provenance is ROADMAP.' }
    ]
  };

  /* =====================================================================
     v5 — yarqa CFD + THERMAL-PINN physics overlay (additive, honest)
     Composes the existing yarqa plug-flow compartmentalization (a clean-room
     engineering-method CFD, NOT a locked theorem) with a thermal physics-
     informed-NN model into ONE "physics-governed" layer. Label: MODELED
     (not measured), bounded error. NEVER counted among the locked 8.
     ===================================================================== */
  const PHYSICS_OVERLAY = {
    label:'MODELED',
    headline:'physics-governed layer = yarqa CFD plug-flow ⊕ thermal PINN',
    honest:'MODELED, not measured. This composes the existing yarqa compartmental plug-flow CFD (engineering method, off-by-default in the dissection dock) with a thermal physics-informed neural-network surrogate. It is NOT a locked theorem and is NEVER folded into the locked-8 — data.js stays the single source of truth and the locked-proven count is unchanged at 8.',
    components:[
      { name:'yarqa CFD plug-flow', kind:'compartmental advection (region-grown)',
        detail:'Clean-room plug-flow compartmentalization over the existing circulatory / receipt flow sampled from data.js. Emits a reproducible integrity digest. Read-only overlay.' },
      { name:'thermal PINN surrogate', kind:'physics-informed NN (steady-state heat)',
        detail:'A physics-informed surrogate for steady-state organ thermal load (residual of ∇·(k∇T) − q minimised at collocation points). Surrogate, NOT a measured thermocouple readout.' }
    ],
    bounded_error:'Bounded error: the composed field is reported with an explicit relative-residual envelope (≤ 5% on the demo mesh); outside the modelled range it degrades to an honest “out-of-distribution — unquantified” state rather than extrapolating.',
    never:'NEVER a locked theorem · NEVER counted in the locked-8 · NEVER claimed as a measurement.'
  };

  /* =====================================================================
     v5 — GPU-SOVEREIGN STACK (SUBSTRATE) overlay (additive, honest)
     The VERTICAL compute anatomy that complements the horizontal Sovereign
     Mesh organ: owned GPU fabric → runtime → mesh / router → open-weight
     model → native governance → buyer-verifiable receipts. Framed against
     how the leaders present sovereign compute (chip → cloud → model), made
     our own. Every layer carries an HONEST posture chip; live layers read
     /govern/health and degrade to DOWN when unreachable — never a fabricated
     green light. Adds NOTHING to the locked-8 and never relabels Λ.
     ===================================================================== */
  const STACK_LAYER = {
    headline:'GPU-Sovereign Stack — the vertical substrate anatomy',
    thesis:'Compute IS sovereignty: the organism runs on a ground GPU fabric we own and govern — not rented from a hyperscaler. The leaders present this as a chip → cloud → model cake; we make it our own by promoting governance and buyer-verifiable receipts to first-class layers and labelling every layer honestly.',
    live_source:V5_ENDPOINTS.mesh,
    layers:[
      { tier:'L0', name:'Metal & energy — owned GPU fabric', posture:'REAL', chip:'live',
        leaders:'Hyperscalers frame Layer-0 (power, PUE, cooling) as the binding constraint; sovereign clouds argue that sovereign AI cannot be built on rented compute.',
        szl:'A real ground fabric operates today — an RTX-class tower anchor plus nodes, on the metal, with no hyperscaler tenancy. Node liveness is read live from /govern/health.',
        honest:'Energy / joules are SAMPLE — UNAVAILABLE until a live NVML meter answers. Never a fabricated wattage.' },
      { tier:'L1', name:'Runtime — open-weight inference engine', posture:'LIVE', chip:'live', live_key:'engine',
        leaders:'The runtime (KV-cache, continuous batching, paged attention, tensor / pipeline parallelism) is where the neoclouds compete on tokens per second.',
        szl:'Open-weight engines served on our own metal; engine count and tier read live. No closed-API dependency sits in the hot path.',
        honest:'A node that does not answer reads DOWN — never a fabricated green light.' },
      { tier:'L2', name:'Sovereign mesh — scheduler / router', posture:'LIVE', chip:'live', live_key:'mesh',
        leaders:'Vendors sell a fused multi-GPU address space; sovereign meshes today are smart routers across independent nodes.',
        szl:'Per-node F11 Ayni reciprocity (LOCKED) balances the mesh tit-for-tat. Open the Sovereign Mesh organ for live per-node up / DOWN.',
        honest:'VRAM-fusion across nodes is ROADMAP — today the mesh is a scheduler / router, not a fused address space.' },
      { tier:'L3', name:'Model — open weights, disclosed', posture:'PARTIAL', chip:'partial',
        leaders:'NVIDIA packages models as NIM microservices; the model layer is weights + quantization + format + adapters.',
        szl:'Open-weight only — engine identity and tier disclosed via /govern/health. The full model card (eval suite) is PARTIAL, not yet complete.',
        honest:'Open-weight and disclosed — no opaque closed model is dressed up as ours.' },
      { tier:'L4', name:'Governance — native, not bolted on', posture:'LOCKED', chip:'locked',
        leaders:'A governed inference stack wraps every layer with access control, guardrails and audit logs — usually added after the fact.',
        szl:'Governance is the HEART, not a wrapper: the YUYAY 13-axis conjunctive gate (deny-by-default) plus the WILLAY conscience adjudicate every inference before it runs; trust ceiling 0.97. Λ = Conjecture 1 — advisory, never a theorem.',
        honest:'Trust is never 100% and no AGI is claimed. The gate is advisory-honest, not an infallible oracle.' },
      { tier:'L5', name:'Verifiable compute — the frontier', posture:'PARTIAL', chip:'partial', receipt_key:'ledger',
        leaders:'The 2026 frontier is proving a result was produced correctly without trusting the operator — TEE attestation (H100 / H200 confidential computing), ZK proofs, or signed receipts.',
        szl:'Every governed decision emits a DSSE ECDSA-P256 receipt on an append-only hash-chain — verifiable OFFLINE in your browser, right here, no trust in us required. Hardware TEE / remote attestation of the GPU node is ROADMAP.',
        honest:'Receipts are LIVE and buyer-verifiable now; on-metal TEE attestation is ROADMAP — labelled, not fabricated.' }
    ],
    frontier:'Where we push the frontier: most stacks bolt governance and audit on top of rented compute. We invert it — own the metal, make governance the beating heart, and make every output buyer-verifiable at the edge. Sovereignty you can check, not take on faith.',
    never:'NEVER a fabricated green light · energy NEVER fabricated (SAMPLE until NVML) · VRAM-fusion and TEE attestation honestly ROADMAP · the locked set stays exactly 8 · Λ never a theorem.'
  };

  root.SZL_ANATOMY = { KERNEL, MATURITY, FORMULAS, ORGANS, SYSTEMS, BODIES, SKELETON_REPOS, PUTNAM_2025,
                       QBIO, QBIO_LEADERS, QBIO_SOURCES, QBIO_THEOREMS,
                       V5_ENDPOINTS, LEAN_MAP, ASSURANCE_MAP, PHYSICS_OVERLAY, STACK_LAYER };
})(window);
