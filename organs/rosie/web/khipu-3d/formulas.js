/* ===========================================================================
 * formulas.js — The math beat. Hover a node → see the formula that produced
 * its Λ, cited by NAME + REAL source location. HONESTY OVER CHECKLIST:
 *
 *   - thesis_v22.pdf is the 3-page "Convergence" paper (Lutar Jr., 2026-06-03,
 *     Concept DOI 10.5281/zenodo.19944926). Only what is actually printed
 *     there is cited to a v22 page. Verified page map:
 *       p1 = doctrine line (749/14/163 @ c7c0ba17, Λ = Conjecture 1, SLSA L1 honest)
 *            + Abstract + §1.1 A5 merge + §1.2 Cauchy_ND.
 *       p2 = §1.5 Innovation Rounds 10–11 (Round 10 Quantum #176 Holevo;
 *            CS #178 Byzantine quorum / FLP / CAP; Crypto #179 DSSE / BLS)
 *            + §1.6 Sim-to-Real + §2 lineage + §3 honest posture (start).
 *       p3 = §3 honest posture (cont.) + citation/DCO footer.
 *   - Formulas NOT named in the 3-page v22 (PAC-Bayes, Welford) are cited to
 *     their REAL implementation in the rosie repo (szl_formulas.py /
 *     szl_khipu_consensus.py) with an explicit "not in v22 p1–3" note.
 *     We never invent a page number.
 *
 * Signed-off-by: Yachay <yachay@szlholdings.ai>
 * Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
 * =========================================================================== */
(function (global) {
  "use strict";

  const FORMULAS = {
    pac_bayes: {
      name: "PAC-Bayes bound (Catoni / McAllester)",
      math: "R(Q) ≤ R̂(Q) + √[ (KL(Q‖P) + ln(2√n/δ)) / (2n) ]",
      cite: "szl_formulas.py · pac_bayes_mcallester() — REAL numeric impl; " +
            "tracked Lean sorry (PACBayes ×4). Catoni-style concentration is the " +
            "generalization-risk lens on Λ verdicts. NOT named on thesis_v22.pdf p1–3.",
      explain: "Bounds the worst-case verdict risk of the aggregator from the " +
               "empirical risk over n co-signed receipts."
    },
    welford: {
      name: "Welford online variance",
      math: "k←k+1 ; δ=x−μ ; μ←μ+δ/k ; M2←M2+δ·(x−μ) ; Var=M2/(k−1)",
      cite: "szl_khipu_consensus.py (online verdict aggregation). Standard " +
            "single-pass algorithm (Welford 1962). Drives NODE SIZE here. " +
            "NOT named on thesis_v22.pdf p1–3 (3-page Convergence paper).",
      explain: "Node radius ∝ running variance of the Λ stream up to this " +
               "receipt — high variance = the mesh is still disagreeing."
    },
    bls: {
      name: "BLS aggregate signature",
      math: "σ_agg = Σᵢ σᵢ ∈ 𝔾₁ ;  e(σ_agg, g₂) = Πᵢ e(H(mᵢ), pkᵢ)",
      cite: "thesis_v22.pdf p2 §1.5 — Round 10 Crypto (#179: DSSE EUF-CMA, " +
            "Rekor Merkle, Fulcio, BLS). Shown when N organs co-sign one trace.",
      explain: "When ≥2 organs sign the same trace_id, their signatures " +
               "aggregate into one constant-size proof of multi-organ agreement."
    },
    byzantine: {
      name: "Byzantine quorum  n ≥ 3f + 1",
      math: "threshold t = 3 of n = 4 witnesses  ⇒  tolerates f = n − t = 1",
      cite: "thesis_v22.pdf p2 §1.5 — Round 10 CS (#178: Byzantine quorum, " +
            "FLP, CAP). Impl: szl_khipu_consensus.py THRESHOLD=3 (3-of-4 BFT).",
      explain: "An action is ACCEPTED only with 3-of-4 organ co-signatures; " +
               "2-of-4 ⇒ REJECTED. One Byzantine/down organ is survivable."
    },
    holevo: {
      name: "Holevo capacity bound",
      math: "χ = S(Σᵢ pᵢ ρᵢ) − Σᵢ pᵢ S(ρᵢ)  ≥  I(X:Y)  (accessible info ≤ χ)",
      cite: "thesis_v22.pdf p2 §1.5 — Round 10 Quantum (#176: PQ signatures, " +
            "Holevo, Kitaev, ZK, no-cloning→A5). Channel-capacity cap.",
      explain: "Upper-bounds classical information extractable from the " +
               "quantum-resistant signing channel — the PQ-channel ceiling."
    }
  };

  // Decide which formula(s) are relevant for a given node, given its real data.
  function forNode(node) {
    const out = [];
    // Λ verdict is always produced through the PAC-Bayes risk lens.
    out.push({ ...FORMULAS.pac_bayes, value: lambdaLine(node) });
    // Welford variance is what drives this node's SIZE.
    out.push({ ...FORMULAS.welford, value: "Var(Λ)≈ " + fmt(node.var) + "  (n=" + (node.k || 1) + ")  → radius" });
    // BLS only when this trace was co-signed by ≥2 organs (real cosigners).
    if ((node.cosigners || 1) >= 2) {
      out.push({ ...FORMULAS.bls, value: node.cosigners + " organs co-signed trace …" + (node.trace8 || "") });
    }
    // Byzantine marker when the trace reaches the quorum threshold.
    if ((node.cosigners || 1) >= 3) {
      out.push({ ...FORMULAS.byzantine, value: "QUORUM MET: " + node.cosigners + "-of-4 ≥ 3" });
    } else if ((node.cosigners || 1) === 2) {
      out.push({ ...FORMULAS.byzantine, value: "2-of-4 — below 3-of-4 quorum" });
    }
    // Holevo whenever the receipt rode a real DSSE/PQ-signing channel.
    if (node.signed) out.push({ ...FORMULAS.holevo, value: "DSSE channel: ECDSA-P256 (PQ roadmap)" });
    return out;
  }

  function lambdaLine(node) {
    return "Λ = " + fmt(node.lambda) + "  → " + node.verdict.toUpperCase() +
           "  (signed=" + (!!node.signed) + ")";
  }
  function fmt(x) { return (typeof x === "number") ? x.toFixed(3) : String(x); }

  global.KhipuFormulas = { FORMULAS, forNode };
})(typeof window !== "undefined" ? window : globalThis);
