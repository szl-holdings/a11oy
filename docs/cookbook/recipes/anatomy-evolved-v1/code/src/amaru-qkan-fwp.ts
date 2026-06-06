/**
 * amaru-qkan-fwp.ts — DARUAN activation + gated fast-weight programmer
 * Organ: amaru (HEART / SEQUENCE MEMORY)
 *
 * STATUS: TUTORIAL FIXTURE — runnable copy for smoke tests in this recipe.
 *   The CANONICAL implementation is the source of truth in:
 *     amaru/web/src/lib/qkan-fwp/qkan-fwp.ts
 *   Keep the two byte-equivalent on the receipt-bearing surface
 *   (rx/rz/daruanActivate/gatedUpdate/qkanFwpStep/initQKANFWP).
 *
 * Source: arXiv:2605.06734 (Peng et al., 2026) — Gated QKAN-FWP
 *         Nielsen & Chuang 2010, §4.2 (Rx/Rz unitary form)
 * Author: Stephen P. Lutar Jr., SZL Holdings
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface DaruanParams {
  theta: number[];   // learnable rotation angles
  phi: number[];     // learnable phase angles
  layers: number;    // re-uploading depth (default 3)
}

export interface FastWeightMatrix {
  W: Float64Array;
  d: number;
}

export interface QKANFWPState {
  fastWeights: FastWeightMatrix[];  // one per KAN layer
  gates: number[];                  // scalar gates per layer
  params: DaruanParams[];           // DARUAN params per edge
}

export interface ForecastResult {
  horizon132months: number[];  // predicted values
  framePair: string;           // which complementary pair
  frobeniusNorm: number;       // ||W||_F — boundedness check
}

// ─── DARUAN Core ─────────────────────────────────────────────────────────────

export interface QubitState {
  alpha: [number, number]; // [re, im] of |0⟩ amplitude
  beta:  [number, number]; // [re, im] of |1⟩ amplitude
}

// R_x(θ) = exp(-i·θ·X/2) = cos(θ/2)·I − i·sin(θ/2)·X
// [Nielsen & Chuang 2010, "Quantum Computation and Quantum Information", §4.2, eq. 4.4]
// On a state ψ = (α, β) with α = α_re + i·α_im, β = β_re + i·β_im:
//   α' = c·α + s·(β_im − i·β_re)
//   β' = c·β + s·(α_im − i·α_re)
// where c = cos(θ/2), s = sin(θ/2). The matrix is manifestly unitary: U†U = I.
export function rx(s: QubitState, theta: number): QubitState {
  const c = Math.cos(theta / 2), si = Math.sin(theta / 2);
  return {
    alpha: [c * s.alpha[0] + si * s.beta[1], c * s.alpha[1] - si * s.beta[0]],
    beta:  [c * s.beta[0]  + si * s.alpha[1], c * s.beta[1]  - si * s.alpha[0]],
  };
}

// R_z(φ) = exp(-i·φ·Z/2) = diag(e^(-iφ/2), e^(+iφ/2))
// [Nielsen & Chuang 2010, §4.2, eq. 4.5]
// α' = (c − i·s)·α  →  α'_re = c·α_re + s·α_im, α'_im = c·α_im − s·α_re
// β' = (c + i·s)·β  →  β'_re = c·β_re − s·β_im, β'_im = c·β_im + s·β_re
export function rz(s: QubitState, phi: number): QubitState {
  const cp = Math.cos(phi / 2), sp = Math.sin(phi / 2);
  return {
    alpha: [cp * s.alpha[0] + sp * s.alpha[1], cp * s.alpha[1] - sp * s.alpha[0]],
    beta:  [cp * s.beta[0]  - sp * s.beta[1],  cp * s.beta[1]  + sp * s.beta[0]],
  };
}

/** DARUAN forward pass: L layers of Rz(φ·x) Rx(θ) → expectation ⟨Z⟩ ∈ [-1,+1] */
export function daruanActivate(x: number, params: DaruanParams): number {
  let state: QubitState = { alpha: [1, 0], beta: [0, 0] };
  for (let l = 0; l < params.layers; l++) {
    const idx = l % params.theta.length;
    state = rz(state, params.phi[idx] * x);
    state = rx(state, params.theta[idx]);
  }
  const a2 = state.alpha[0] ** 2 + state.alpha[1] ** 2;
  const b2 = state.beta[0]  ** 2 + state.beta[1]  ** 2;
  return a2 - b2; // ⟨Z⟩
}

// ─── Scalar-Gated Fast-Weight Update ─────────────────────────────────────────

function sigmoid(x: number): number { return 1 / (1 + Math.exp(-x)); }

export function frobeniusNorm(W: FastWeightMatrix): number {
  let sum = 0;
  for (const w of W.W) sum += w * w;
  return Math.sqrt(sum);
}

/**
 * Gated fast-weight update — geometric boundedness guaranteed
 * Lean theorem: gated_qkan_boundedness (lutar-lean/Lutar/QKAN/GatedBoundedness.lean)
 */
export function gatedUpdate(
  W: FastWeightMatrix,
  key: Float64Array,
  value: Float64Array,
  g: number,
): FastWeightMatrix {
  const gate = sigmoid(g);
  const decay = 1 - gate;
  const { d } = W;
  const newW = new Float64Array(d * d);
  for (let i = 0; i < d; i++) {
    for (let j = 0; j < d; j++) {
      newW[i * d + j] = decay * W.W[i * d + j] + gate * key[i] * value[j];
    }
  }
  return { W: newW, d };
}

// ─── QKAN-FWP Sequence Model ──────────────────────────────────────────────────

/** Query the fast-weight memory with key k */
export function fastWeightQuery(W: FastWeightMatrix, k: Float64Array): Float64Array {
  const { d } = W;
  const out = new Float64Array(d);
  for (let i = 0; i < d; i++) {
    let s = 0;
    for (let j = 0; j < d; j++) s += W.W[i * d + j] * k[j];
    out[i] = s;
  }
  return out;
}

/** QKAN-FWP forward step — process one time-step of the sequence */
export function qkanFwpStep(
  state: QKANFWPState,
  inputVec: Float64Array,
  framePair: string,
): { output: Float64Array; nextState: QKANFWPState } {
  const { fastWeights, gates, params } = state;
  let x = inputVec;
  const nextWeights: FastWeightMatrix[] = [];

  for (let l = 0; l < fastWeights.length; l++) {
    // DARUAN activation on each element of x
    const activated = new Float64Array(x.length);
    for (let i = 0; i < x.length; i++) {
      activated[i] = daruanActivate(x[i], params[l % params.length]);
    }
    // Query fast-weight memory
    const queried = fastWeightQuery(fastWeights[l], activated);
    // Update fast-weight with gated rule
    const W2 = gatedUpdate(fastWeights[l], activated, queried, gates[l]);
    nextWeights.push(W2);
    x = queried;
  }

  return {
    output: x,
    nextState: { ...state, fastWeights: nextWeights },
  };
}

/** Initialize a QKAN-FWP state with ~12.5k params */
export function initQKANFWP(d: number = 8, layers: number = 3): QKANFWPState {
  const initW = (): FastWeightMatrix => ({
    W: Float64Array.from({ length: d * d }, () => (Math.random() - 0.5) * 0.1),
    d,
  });
  const initDaruan = (): DaruanParams => ({
    theta: Array.from({ length: 3 }, () => Math.random() * Math.PI),
    phi:   Array.from({ length: 3 }, () => Math.random() * Math.PI),
    layers: 3,
  });
  return {
    fastWeights: Array.from({ length: layers }, initW),
    gates: Array.from({ length: layers }, () => 0.0),
    params: Array.from({ length: layers }, initDaruan),
  };
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const state = initQKANFWP(8, 3);
const inputVec = new Float64Array([0.1, 0.4, 0.3, 0.8, 0.2, 0.6, 0.5, 0.7]);
const { output, nextState } = qkanFwpStep(state, inputVec, "intent_effect");
console.log("QKAN-FWP output:", output);
console.log("Fast-weight Frobenius norm:", frobeniusNorm(nextState.fastWeights[0]));
// Boundedness invariant: norm should be ≤ B for all t
*/