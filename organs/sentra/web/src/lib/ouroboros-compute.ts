/**
 * Ouroboros formula computations for Sentra mobile views.
 *
 * Λ = C^(1/4)·H^(1/4)·R^(1/4)·F^(1/4), r = |1/N Σ e^(iθ_k)|,
 * Z = √(b²/max(1,s)), Q = W_useful/W_lost, V = h/3·(a²+ab+b²)
 */

export interface LutarAxes {
  readonly cleanliness: number;
  readonly horizon: number;
  readonly resonance: number;
  readonly frustum: number;
}

export interface LutarResult {
  readonly lambda: number;
  readonly axes: LutarAxes;
  readonly formula: string;
  readonly boundVerified: boolean;
  readonly minAxis: number;
  readonly maxAxis: number;
}

export interface KuramotoResult {
  readonly r: number;
  readonly status: 'COHERENT' | 'MIXING' | 'INCOHERENT';
  readonly phaseCount: number;
}

export interface ImpedanceResult {
  readonly Z: number;
  readonly gamma: number;
  readonly eta: number;
  readonly matched: boolean;
}

export interface QFactorResult {
  readonly Q: number;
  readonly status: 'HEALTHY' | 'DEGRADED' | 'OVER_BUDGET';
}

export type ModelTier = 'frontier' | 'mid' | 'workhorse';

export interface ADRDecision {
  readonly tier: ModelTier;
  readonly passes: 1 | 2 | 3;
  readonly costMultiplier: number;
  readonly rationale: string;
}

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(1, v));
}

/** Λ = C^(1/4)·H^(1/4)·R^(1/4)·F^(1/4). Zero-pinning: any axis 0 ⇒ Λ = 0. */
export function computeLutarInvariant(raw: LutarAxes): LutarResult {
  const axes: LutarAxes = {
    cleanliness: clamp01(raw.cleanliness),
    horizon: clamp01(raw.horizon),
    resonance: clamp01(raw.resonance),
    frustum: clamp01(raw.frustum),
  };

  const values = [axes.cleanliness, axes.horizon, axes.resonance, axes.frustum];
  const minAxis = Math.min(...values);
  const maxAxis = Math.max(...values);

  if (values.some(v => v === 0)) {
    return {
      lambda: 0,
      axes,
      formula: 'Λ = C^(1/4) · H^(1/4) · R^(1/4) · F^(1/4)',
      boundVerified: true,
      minAxis,
      maxAxis,
    };
  }

  const logL =
    0.25 * Math.log(axes.cleanliness) +
    0.25 * Math.log(axes.horizon) +
    0.25 * Math.log(axes.resonance) +
    0.25 * Math.log(axes.frustum);
  const lambda = Math.exp(logL);

  const eps = 1e-12;
  const boundVerified =
    lambda >= 0 &&
    lambda <= maxAxis + eps &&
    lambda >= minAxis - eps;

  return {
    lambda,
    axes,
    formula: 'Λ = C^(1/4) · H^(1/4) · R^(1/4) · F^(1/4)',
    boundVerified,
    minAxis,
    maxAxis,
  };
}

/** ADR: Λ ≥ 0.85 → workhorse, 0.65–0.85 → mid, <0.65 → frontier. */
export function classifyLambda(lambda: number): ADRDecision {
  if (lambda >= 0.85) {
    return {
      tier: 'workhorse',
      passes: 1,
      costMultiplier: 0.1,
      rationale: `High trust (Λ=${lambda.toFixed(4)}). Single-pass verification.`,
    };
  }
  if (lambda >= 0.65) {
    return {
      tier: 'mid',
      passes: 2,
      costMultiplier: 0.4,
      rationale: `Medium trust (Λ=${lambda.toFixed(4)}). Two-pass verification.`,
    };
  }
  return {
    tier: 'frontier',
    passes: 3,
    costMultiplier: 1.0,
    rationale: `Low trust (Λ=${lambda.toFixed(4)}). Full three-pass verification.`,
  };
}

/** r = |1/N Σ e^(iθ_k)|. ≥0.85 COHERENT, ≥0.4 MIXING, <0.4 INCOHERENT. */
export function computeKuramoto(phases: number[]): KuramotoResult {
  const N = phases.length;
  if (N === 0) return { r: 0, status: 'INCOHERENT', phaseCount: 0 };

  let sumCos = 0;
  let sumSin = 0;
  for (const theta of phases) {
    sumCos += Math.cos(theta);
    sumSin += Math.sin(theta);
  }
  const r = Math.sqrt(sumCos * sumCos + sumSin * sumSin) / N;

  let status: KuramotoResult['status'];
  if (r >= 0.85) status = 'COHERENT';
  else if (r >= 0.4) status = 'MIXING';
  else status = 'INCOHERENT';

  return { r, status, phaseCount: N };
}

/** Map agent statuses to Kuramoto phase angles. */
export function agentStatesToPhases(statuses: string[]): number[] {
  return statuses.map(s => {
    switch (s) {
      case 'healthy': return 0;
      case 'stale': return Math.PI / 2;
      case 'isolated': return Math.PI;
      default: return Math.PI / 3;
    }
  });
}

/** Z = √(b²/max(1,s)), Γ = (Z-1)/(Z+1), η = 1-|Γ|². Matched when |Γ|<0.2. */
export function computeImpedance(boundaryEvents: number, successfulHandoffs: number): ImpedanceResult {
  const Z = Math.sqrt((boundaryEvents * boundaryEvents) / Math.max(1, successfulHandoffs));
  const Z0 = 1;
  const gamma = Math.abs((Z - Z0) / (Z + Z0));
  const eta = 1 - gamma * gamma;
  const matched = gamma < 0.2;

  return { Z, gamma, eta, matched };
}

/** Q = W_useful/W_lost. <1.5 DEGRADED, 1.5–10 HEALTHY, >10 OVER_BUDGET. */
export function computeQFactor(usefulWork: number, lostWork: number): QFactorResult {
  if (lostWork <= 0) return { Q: usefulWork > 0 ? 10 : 0, status: usefulWork > 0 ? 'HEALTHY' : 'DEGRADED' };
  const Q = usefulWork / lostWork;

  let status: QFactorResult['status'];
  if (Q < 1.5) status = 'DEGRADED';
  else if (Q > 10) status = 'OVER_BUDGET';
  else status = 'HEALTHY';

  return { Q, status };
}

/** V = h/3·(a² + ab + b²). */
export function computeFrustumVolume(h: number, a: number, b: number): number {
  return (h / 3) * (a * a + a * b + b * b);
}

/** Derive axes from SOC operational data. */
export function deriveSocAxes(params: {
  verifiedAnchors: number;
  totalAnchors: number;
  recoveryPosture: number;
  healthyAgents: number;
  totalAgents: number;
  reconciledViews: number;
  totalViews: number;
}): LutarAxes {
  const C = params.totalAnchors > 0 ? params.verifiedAnchors / params.totalAnchors : 0;
  const H = clamp01(params.recoveryPosture / 100);
  const R_raw = params.totalAgents > 0 ? params.healthyAgents / params.totalAgents : 0;
  const R = clamp01(R_raw);
  const F = params.totalViews > 0 ? params.reconciledViews / params.totalViews : 0;

  return { cleanliness: clamp01(C), horizon: clamp01(H), resonance: clamp01(R), frustum: clamp01(F) };
}

/** Derive axes from mesh resilience data. */
export function deriveMeshAxes(params: {
  secretHygiene: number;
  permissionSurface: number;
  egressContainment: number;
  supplyChain: number;
}): LutarAxes {
  return {
    cleanliness: clamp01(params.secretHygiene / 100),
    horizon: clamp01(params.supplyChain / 100),
    resonance: clamp01(params.egressContainment / 100),
    frustum: clamp01(params.permissionSurface / 100),
  };
}

/** Derive axes from hunt data. */
export function deriveHuntAxes(params: {
  confidenceScore: number;
  falsePositiveRate: number;
  signalCount: number;
  severity: string;
}): LutarAxes {
  const sevMap: Record<string, number> = { critical: 0.4, high: 0.6, medium: 0.8, low: 0.95 };
  return {
    cleanliness: clamp01(1 - params.falsePositiveRate),
    horizon: clamp01(params.confidenceScore),
    resonance: clamp01(Math.min(1, params.signalCount / 10)),
    frustum: clamp01(sevMap[params.severity] ?? 0.5),
  };
}

/** Derive axes from PQC readiness data. */
export function derivePqcAxes(params: {
  verifiedAnchors: number;
  totalAnchors: number;
  deployedStandards: number;
  totalStandards: number;
  attestedComponents: number;
  totalComponents: number;
  completedPhases: number;
  totalPhases: number;
}): LutarAxes {
  return {
    cleanliness: params.totalAnchors > 0 ? clamp01(params.verifiedAnchors / params.totalAnchors) : 0,
    horizon: params.totalStandards > 0 ? clamp01(params.deployedStandards / params.totalStandards) : 0,
    resonance: params.totalComponents > 0 ? clamp01(params.attestedComponents / params.totalComponents) : 0,
    frustum: params.totalPhases > 0 ? clamp01(params.completedPhases / params.totalPhases) : 0,
  };
}

export const TIER_COLORS: Record<ModelTier, string> = {
  workhorse: 'text-emerald-400',
  mid: 'text-amber-400',
  frontier: 'text-red-400',
};

export const TIER_BG: Record<ModelTier, string> = {
  workhorse: 'bg-emerald-400/10 border-emerald-400/20',
  mid: 'bg-amber-400/10 border-amber-400/20',
  frontier: 'bg-red-400/10 border-red-400/20',
};

export const COHERENCE_COLORS: Record<KuramotoResult['status'], string> = {
  COHERENT: 'text-emerald-400',
  MIXING: 'text-amber-400',
  INCOHERENT: 'text-red-400',
};

export const Q_COLORS: Record<QFactorResult['status'], string> = {
  HEALTHY: 'text-emerald-400',
  DEGRADED: 'text-red-400',
  OVER_BUDGET: 'text-amber-400',
};
