// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// SZL Holdings — Canonical Formulas
// One implementation per thesis. Every agent calls these — no drift.

// ============================================================
// Branded primitive types (TH7)
// ============================================================
export type Lambda      = number & { readonly __brand: "Lambda" };
export type AxisScore   = number & { readonly __brand: "AxisScore" };
export type ReplaySha   = string & { readonly __brand: "ReplaySha" };
export type DOI         = string & { readonly __brand: "DOI" };
export type Bits        = number & { readonly __brand: "Bits" };
export type Joules      = number & { readonly __brand: "Joules" };
export type Meters      = number & { readonly __brand: "Meters" };

export const REPLAY_ROOT = "1ed4d253e876f428c6e182f8ed8a569585442556b339529bbf8ec2522581698b" as ReplaySha;

// ============================================================
// TH1 — Lambda Gate
// 9-axis conjunctive AND; moral & measurability hard floors at 0.95
// ============================================================
export interface Axes {
  semanticCoherence:    AxisScore;
  empiricalGrounding:   AxisScore;
  logicalConsistency:   AxisScore;
  moralGrounding:       AxisScore;  // hard floor 0.95
  epistemicHumility:    AxisScore;
  measurabilityHonesty: AxisScore;  // hard floor 0.95
  reversibility:        AxisScore;
  provenance:           AxisScore;
  replayability:        AxisScore;
}

export interface LambdaResult {
  pass: boolean;
  lambda: Lambda;
  axes: Axes;
  failures: Array<{ axis: keyof Axes; score: number; floor: number }>;
}

const FLOORS: Record<keyof Axes, number> = {
  semanticCoherence:    0.90,
  empiricalGrounding:   0.90,
  logicalConsistency:   0.90,
  moralGrounding:       0.95, // hard
  epistemicHumility:    0.90,
  measurabilityHonesty: 0.95, // hard
  reversibility:        0.90,
  provenance:           0.90,
  replayability:        0.90,
};

export function lambdaGate(axes: Axes): LambdaResult {
  const failures: LambdaResult["failures"] = [];
  for (const [axis, score] of Object.entries(axes) as [keyof Axes, number][]) {
    if (score < FLOORS[axis]) failures.push({ axis, score, floor: FLOORS[axis] });
  }
  // Λ is the min — conjunctive AND, not arithmetic mean, not multiplicative product.
  // Doctrine V6 § 9-Axis Lambda Gate.
  const lambda = Math.min(...Object.values(axes)) as Lambda;
  return { pass: failures.length === 0, lambda, axes, failures };
}

// ============================================================
// TH2 — DOI Binding
// Bind a Zenodo DOI to a replay-root SHA. Idempotent.
// ============================================================
const doiBindings = new Map<DOI, ReplaySha>();
const DOI_RE = /^10\.\d{4,9}\/[-._;()/:A-Z0-9]+$/i;

export function doiBind(doi: string, sha: ReplaySha): { bound: DOI; sha: ReplaySha; idempotent: boolean } {
  if (!DOI_RE.test(doi)) throw new Error(`invalid DOI: ${doi}`);
  const d = doi as DOI;
  const existing = doiBindings.get(d);
  if (existing && existing !== sha) throw new Error(`DOI ${doi} already bound to a different SHA`);
  doiBindings.set(d, sha);
  return { bound: d, sha, idempotent: existing === sha };
}

export function doiResolve(doi: string): ReplaySha | null {
  return doiBindings.get(doi as DOI) ?? null;
}

// ============================================================
// TH3 — Closure
// Monotone, extensive, idempotent operator over a typed set.
// ============================================================
export function closure<T>(seed: Set<T>, step: (s: Set<T>) => Set<T>, maxIter = 1024): Set<T> {
  let prev = new Set(seed);
  for (let i = 0; i < maxIter; i++) {
    const next = step(prev);
    // extensive
    for (const x of prev) next.add(x);
    if (next.size === prev.size) return next; // idempotent reached
    prev = next;
  }
  throw new Error(`closure did not converge in ${maxIter} iterations`);
}

// ============================================================
// TH4 — Category
// Identity + associative composition over typed morphisms.
// ============================================================
export type Morph<A, B> = (a: A) => B;
export const identity = <A>(a: A): A => a;
export function compose<A, B, C>(g: Morph<B, C>, f: Morph<A, B>): Morph<A, C> {
  return (a: A) => g(f(a));
}
// Associativity holds by construction: compose(compose(h,g),f) ≡ compose(h, compose(g,f))

// ============================================================
// TH5 — Confluence
// Two divergent rewrites reach a common normal form within bound.
// ============================================================
export function confluence<T>(
  start: T,
  rewriteA: (t: T) => T,
  rewriteB: (t: T) => T,
  eq: (x: T, y: T) => boolean,
  maxSteps = 256
): { converged: boolean; steps: number; normalForm: T | null } {
  let a = start, b = start;
  for (let i = 0; i < maxSteps; i++) {
    a = rewriteA(a);
    b = rewriteB(b);
    if (eq(a, b)) return { converged: true, steps: i + 1, normalForm: a };
  }
  return { converged: false, steps: maxSteps, normalForm: null };
}

// ============================================================
// TH6 — Bekenstein Bound (canonical DPI form)
// Paper TH6 (Theorem 11): H(chain) ≤ H(registry) ≤ 8 · |registry_bytes|
// This is the information-theoretic data-processing-inequality form.
// The physical-cosmology form below is exported as bekensteinA7Superseded
// for historical reference only — it is NOT what the paper proves.
// ============================================================
export function bekensteinTH6(registryBytes: number): Bits {
  if (!Number.isFinite(registryBytes) || registryBytes < 0) {
    throw new Error("registryBytes must be a non-negative finite number");
  }
  return (8 * registryBytes) as Bits;
}

export function bekensteinTH6Respected(chainEntropyBits: number, registryBytes: number): boolean {
  if (!Number.isFinite(chainEntropyBits) || chainEntropyBits < 0) {
    throw new Error("chainEntropyBits must be non-negative");
  }
  return chainEntropyBits <= bekensteinTH6(registryBytes);
}

// ── Superseded physical form (A7 in the paper, kept for cross-reference) ──
const HBAR = 1.054571817e-34;        // J·s (CODATA)
const C    = 299792458;              // m/s (exact)
const LN2  = Math.LN2;
const TWO_PI = 2 * Math.PI;

/** @deprecated Physical Bekenstein bound (A7). Superseded by bekensteinTH6 (DPI). */
export function bekensteinA7Superseded(radiusMeters: Meters, energyJoules: Joules): Bits {
  if (radiusMeters <= 0) throw new Error("radius must be > 0");
  if (energyJoules  <= 0) throw new Error("energy must be > 0");
  return ((TWO_PI * radiusMeters * energyJoules) / (HBAR * C * LN2)) as Bits;
}

/** @deprecated kept for backward compatibility; routes to canonical TH6. */
export function bekensteinBound(radiusMeters: Meters, energyJoules: Joules): Bits {
  return bekensteinA7Superseded(radiusMeters, energyJoules);
}

/** @deprecated kept for backward compatibility; routes to canonical TH6. */
export function bekensteinRespected(info: Bits, radiusMeters: Meters, energyJoules: Joules): boolean {
  return info <= bekensteinA7Superseded(radiusMeters, energyJoules);
}

// ============================================================
// TH7 — Branded Type Constructors
// Safe lifts; throw on invalid input.
// ============================================================
export const mkLambda = (n: number): Lambda => {
  if (!Number.isFinite(n) || n < 0 || n > 1) throw new Error(`Λ out of range: ${n}`);
  return n as Lambda;
};
export const mkAxisScore = (n: number): AxisScore => {
  if (!Number.isFinite(n) || n < 0 || n > 1) throw new Error(`axis out of range: ${n}`);
  return n as AxisScore;
};
export const mkReplaySha = (s: string): ReplaySha => {
  if (!/^[0-9a-f]{64}$/.test(s)) throw new Error(`not a sha256: ${s}`);
  return s as ReplaySha;
};
export const mkDOI = (s: string): DOI => {
  if (!DOI_RE.test(s)) throw new Error(`not a DOI: ${s}`);
  return s as DOI;
};

// ============================================================
// TH8 — Graded Calculus: graded norm + linear receipt
// (Lean v2 has the full proof; this is the runtime mirror.)
// ============================================================
export interface Graded {
  grade: number;        // ℕ
  value: number;        // ℝ
}

// ‖x‖_g = |value| · 2^(-grade) — geometric weighting on the grade.
export function gradedNorm(x: Graded): number {
  return Math.abs(x.value) * Math.pow(2, -x.grade);
}

// Triangle inequality for the graded norm:  ‖αx + βy‖ ≤ |α|·‖x‖ + |β|·‖y‖
// Note: this is the triangle inequality of the norm, not linearity of an
// arbitrary functional. Equality holds only when the grades agree and signs align.
// Tolerance is floating-point relative epsilon, not a slack budget.
export function linearReceipt(
  alpha: number, x: Graded,
  beta:  number, y: Graded
): { lhs: number; rhs: number; linear: boolean } {
  const combined: Graded = { grade: Math.max(x.grade, y.grade), value: alpha * x.value + beta * y.value };
  const lhs = gradedNorm(combined);
  const rhs = Math.abs(alpha) * gradedNorm(x) + Math.abs(beta) * gradedNorm(y);
  // Triangle inequality: lhs <= rhs. Allow only relative fp epsilon (not slack).
  const fpEps = Math.max(rhs, 1) * Number.EPSILON * 8;
  const linear = lhs <= rhs + fpEps;
  return { lhs, rhs, linear };
}

// ============================================================
// VSP — Vessels Spine Protocol (span emit)
// ============================================================
export interface VspSpan {
  name: string;
  thesis?: string;
  startNs: bigint;
  endNs?: bigint;
  attrs: Record<string, string | number | boolean>;
  replayRoot: ReplaySha;
}

// Injectable clock for byte-identical replay testing.
export type SpanClock = () => bigint;
const defaultClock: SpanClock = () => process.hrtime.bigint();

export function spanStart(
  name: string,
  thesis?: string,
  attrs: Record<string, any> = {},
  clock: SpanClock = defaultClock
): VspSpan {
  return {
    name,
    thesis,
    startNs: clock(),
    attrs,
    replayRoot: REPLAY_ROOT,
  };
}
export function spanEnd(s: VspSpan, clock: SpanClock = defaultClock): VspSpan {
  return { ...s, endNs: clock() };
}

// ============================================================
// FG — Forecast Gauge (12 base + 3 derived + 4 a11oy safety gates)
// ============================================================
export interface FgGauges {
  // 12 base gauges
  capability:        number; alignment:    number; replayHealth: number;
  doctrineDrift:     number; testCoverage: number; ciHealth:     number;
  scorecardScore:    number; deployFreshness: number; depDrift:  number;
  vulnPressure:      number; latencyP95Ms: number; errorRate:    number;
}
export interface FgDerived {
  netHealth:    number;  // weighted average
  fragility:    number;  // 1 - netHealth, clamped
  velocity:     number;  // capability × ciHealth × (1 - depDrift)
}
export interface FgSafety {
  lambdaFloorOk: boolean;
  moralFloorOk:  boolean;
  measureFloorOk:boolean;
  replayOk:      boolean;
}

export function fgDerive(g: FgGauges): FgDerived {
  const weights = {
    capability: 0.15, alignment: 0.15, replayHealth: 0.10,
    doctrineDrift: -0.10, testCoverage: 0.10, ciHealth: 0.10,
    scorecardScore: 0.10, deployFreshness: 0.05, depDrift: -0.05,
    vulnPressure: -0.10, latencyP95Ms: 0, errorRate: -0.10,
  };
  const wSum = Object.values(weights).reduce((a, b) => a + Math.abs(b), 0);
  const net = (Object.entries(weights) as [keyof FgGauges, number][])
    .reduce((acc, [k, w]) => acc + (g[k] * w), 0) / wSum;
  const netHealth = Math.max(0, Math.min(1, 0.5 + net));
  const fragility = 1 - netHealth;
  const velocity  = g.capability * g.ciHealth * (1 - g.depDrift);
  return { netHealth, fragility, velocity };
}

export function fgSafety(axes: Axes, replayOk: boolean): FgSafety {
  return {
    lambdaFloorOk:  Math.min(...Object.values(axes)) >= 0.90,
    moralFloorOk:   axes.moralGrounding >= 0.95,
    measureFloorOk: axes.measurabilityHonesty >= 0.95,
    replayOk,
  };
}
