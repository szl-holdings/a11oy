/**
 * Amaru intelligence helpers — pure, deterministic.
 *
 * Every helper here is a function of its inputs. No I/O, no Math.random,
 * no Date.now — callers pass `nowIso` when they need it. This is what lets
 * the cockpit, the run page, the policy page, and the agent coalition all
 * agree on the same Σ for the same batch.
 */

import type {
  AmaruKpis,
  ApprovalRequest,
  RelayDestination,
  RelayMapping,
  RelayModel,
  RelayOutcome,
  RelayPolicy,
  RelayRunEvent,
  RelaySource,
  SeverityLevel,
} from '@/data/fabric/types';

// ─── Activation readiness (model + destination + policy hits) ───────────────
export interface ActivationReadiness {
  readonly score: number; // 0..100
  readonly bandLabel: string;
  readonly band: 'ready' | 'gated' | 'blocked';
  readonly blockers: readonly string[];
  readonly suggestions: readonly string[];
}

export function calculateActivationReadiness(
  model: RelayModel,
  destination: RelayDestination,
  mapping: RelayMapping | null,
): ActivationReadiness {
  const blockers: string[] = [];
  const suggestions: string[] = [];

  if (model.governanceState === 'red') blockers.push(`Source model ${model.name} is red.`);
  if (destination.governanceState === 'red') blockers.push(`Destination ${destination.name} is red.`);
  if (destination.authState === 'expired') blockers.push(`Destination auth expired (rotate by ${destination.authRotatesAt ?? 'asap'}).`);
  if (destination.authState === 'rotation_required') blockers.push('Destination credentials marked for rotation.');
  if (mapping?.approvalRequired) suggestions.push(`Approval pending: ${mapping.approvalReason ?? 'review required'}.`);
  if (model.piiScore > 0.6 && !destination.piiAllowed) blockers.push('Model PII fields exceed destination contract.');

  const qualityFactor = model.qualityScore / 100;
  const piiFactor = destination.piiAllowed ? 1 : Math.max(0.4, 1 - model.piiScore);
  const contractFactor = destination.fieldContractStrength;
  const obsFactor = destination.observabilityCoverage;
  const mappingFactor = mapping ? mapping.confidence : 0.6;
  const score = Math.round(qualityFactor * piiFactor * contractFactor * obsFactor * mappingFactor * 100);

  const band: ActivationReadiness['band'] = blockers.length > 0 ? 'blocked' : score >= 80 ? 'ready' : 'gated';
  const bandLabel = band === 'ready' ? 'Ready to activate' : band === 'blocked' ? 'Blocked' : 'Gated';

  if (mappingFactor < 0.85 && band !== 'blocked') suggestions.push('Mapper confidence < 0.85; review proposed transforms.');
  if (qualityFactor < 0.85) suggestions.push('Source quality < 85; profile or filter records before activation.');
  if (obsFactor < 0.8) suggestions.push('Destination observability < 80%; add per-field metrics.');

  return { score, bandLabel, band, blockers, suggestions };
}

// ─── PII risk classification ────────────────────────────────────────────────
export interface PiiRiskTier {
  readonly tier: 'low' | 'moderate' | 'high' | 'critical';
  readonly score: number;
  readonly reasons: readonly string[];
}

export function classifyPiiRisk(model: RelayModel, destination: RelayDestination): PiiRiskTier {
  const reasons: string[] = [];
  let score = model.piiScore;
  if (!destination.piiAllowed && model.piiFieldCount > 0) {
    score += 0.4;
    reasons.push('Destination contract forbids PII');
  }
  if (model.fields.some((f) => f.piiClass === 'gov_id' || f.piiClass === 'health' || f.piiClass === 'financial')) {
    score += 0.15;
    reasons.push('Sensitive class detected (gov_id / health / financial)');
  }
  if (destination.authState !== 'connected') {
    score += 0.1;
    reasons.push(`Destination auth state: ${destination.authState}`);
  }
  const tier: PiiRiskTier['tier'] = score >= 1.0 ? 'critical' : score >= 0.75 ? 'high' : score >= 0.45 ? 'moderate' : 'low';
  return { tier, score: Math.round(Math.min(score, 1.5) * 100) / 100, reasons };
}

// ─── Mapping compatibility scoring ──────────────────────────────────────────
export function scoreMappingCompatibility(mapping: RelayMapping): number {
  return Math.round(
    mapping.compatibilityScore * 0.55 +
      mapping.confidence * 100 * 0.3 +
      (mapping.approvalRequired ? 0 : 15),
  );
}

// ─── Blast radius estimation ────────────────────────────────────────────────
export interface BlastRadius {
  readonly recordsAtRisk: number;
  readonly destinationsAffected: number;
  readonly verticalLabel: string;
  readonly severity: SeverityLevel;
}

export function estimateBlastRadius(mapping: RelayMapping, source: RelaySource | null): BlastRadius {
  const records = source ? Math.round(source.rowCount * 0.0008) : 50_000;
  const destinationsAffected = 1;
  const severity: SeverityLevel = mapping.governanceState === 'red'
    ? 'critical'
    : mapping.approvalRequired
      ? 'high'
      : mapping.governanceState === 'amber'
        ? 'medium'
        : 'low';
  return {
    recordsAtRisk: records,
    destinationsAffected,
    verticalLabel: mapping.verticalId,
    severity,
  };
}

// ─── Sync health (status + recency) ─────────────────────────────────────────
export type SyncHealthState = 'healthy' | 'degraded' | 'failing' | 'paused';

export function deriveSyncHealth(events: readonly RelayRunEvent[]): SyncHealthState {
  if (events.length === 0) return 'paused';
  const recent = events.slice(0, 8);
  const failures = recent.filter((e) => e.type === 'failed' || e.type === 'rolled_back').length;
  const blocks = recent.filter((e) => e.type === 'quarantined').length;
  if (failures >= 3) return 'failing';
  if (failures >= 1 || blocks >= 2) return 'degraded';
  return 'healthy';
}

// ─── Destination health rollup ──────────────────────────────────────────────
export function calculateDestinationHealth(
  destination: RelayDestination,
  events: readonly RelayRunEvent[],
): number {
  const dEvents = events.filter((e) => e.destinationId === destination.id).slice(0, 50);
  if (dEvents.length === 0) return destination.healthScore;
  const failed = dEvents.filter((e) => e.type === 'failed').length;
  const failPct = failed / dEvents.length;
  const base = destination.healthScore;
  const penalty = Math.round(failPct * 30);
  return Math.max(0, Math.min(100, base - penalty));
}

// ─── Sync risk ranking ──────────────────────────────────────────────────────
export interface SyncRiskRow {
  readonly syncId: string;
  readonly syncName: string;
  readonly verticalId: string;
  readonly destinationId: string;
  readonly score: number;
  readonly drivers: readonly string[];
  readonly health: SyncHealthState;
}

export function rankSyncRisk(events: readonly RelayRunEvent[]): readonly SyncRiskRow[] {
  const grouped = new Map<string, RelayRunEvent[]>();
  for (const e of events) {
    const arr = grouped.get(e.syncId) ?? [];
    arr.push(e);
    grouped.set(e.syncId, arr);
  }
  const rows: SyncRiskRow[] = [];
  for (const [syncId, evts] of grouped) {
    const health = deriveSyncHealth(evts);
    const recent = evts.slice(0, 12);
    const failures = recent.filter((e) => e.type === 'failed' || e.type === 'rolled_back').length;
    const drivers: string[] = [];
    if (failures > 0) drivers.push(`${failures} recent failure${failures === 1 ? '' : 's'}`);
    const errorClasses = new Set(recent.map((e) => e.errorClass).filter((c): c is string => Boolean(c)));
    for (const c of errorClasses) drivers.push(`error: ${c}`);
    if (health === 'degraded') drivers.push('degraded health');
    if (health === 'failing') drivers.push('failing health');
    const score = Math.round(failures * 18 + (health === 'failing' ? 30 : health === 'degraded' ? 12 : 0) + errorClasses.size * 6);
    rows.push({
      syncId,
      syncName: evts[0]!.syncName,
      verticalId: evts[0]!.verticalId,
      destinationId: evts[0]!.destinationId,
      score,
      drivers,
      health,
    });
  }
  return rows.sort((a, b) => b.score - a.score);
}

// ─── Outcome lift / prediction error ────────────────────────────────────────
export function calculateOutcomeLift(outcomes: readonly RelayOutcome[]): number {
  if (outcomes.length === 0) return 0;
  const total = outcomes.reduce((s, o) => s + o.liftPct, 0);
  return Math.round((total / outcomes.length) * 1000) / 1000;
}

export function calculatePredictionError(outcomes: readonly RelayOutcome[]): number {
  if (outcomes.length === 0) return 0;
  const total = outcomes.reduce((s, o) => s + Math.abs(o.predictionError), 0);
  return Math.round((total / outcomes.length) * 1000) / 1000;
}

// ─── Recommended action generator ───────────────────────────────────────────
export function generateRecommendedAction(row: SyncRiskRow): string {
  if (row.health === 'failing') return 'Page on-call, pause sync, open incident.';
  if (row.drivers.some((d) => d.includes('auth_expired'))) return 'Rotate destination credentials.';
  if (row.drivers.some((d) => d.includes('rate_limit'))) return 'Lower batch ceiling or back off cadence.';
  if (row.drivers.some((d) => d.includes('schema_drift'))) return 'Re-profile source; refresh model.';
  if (row.drivers.some((d) => d.includes('pii_block'))) return 'Add redaction transform or change destination.';
  if (row.drivers.some((d) => d.includes('destination_5xx'))) return 'Check destination status; raise vendor ticket.';
  if (row.health === 'degraded') return 'Watch next 3 cycles; investigate if not self-clearing.';
  return 'No action required.';
}

// ─── Group helpers ──────────────────────────────────────────────────────────
export function groupSyncsByStatus(rows: readonly SyncRiskRow[]) {
  return rows.reduce(
    (acc, r) => {
      acc[r.health].push(r);
      return acc;
    },
    { healthy: [] as SyncRiskRow[], degraded: [] as SyncRiskRow[], failing: [] as SyncRiskRow[], paused: [] as SyncRiskRow[] },
  );
}

export function groupPoliciesBySeverity(policies: readonly RelayPolicy[]) {
  return policies.reduce(
    (acc, p) => {
      acc[p.severity].push(p);
      return acc;
    },
    { critical: [] as RelayPolicy[], high: [] as RelayPolicy[], medium: [] as RelayPolicy[], low: [] as RelayPolicy[], info: [] as RelayPolicy[] },
  );
}

// ─── Approval & dry-run ─────────────────────────────────────────────────────
export function deriveApprovalRequirement(mapping: RelayMapping, destination: RelayDestination): {
  required: boolean;
  reason: string | null;
  level: 'auto' | 'lead' | 'partner';
} {
  if (mapping.governanceState === 'red' || destination.governanceState === 'red')
    return { required: true, reason: 'Red governance state', level: 'partner' };
  if (mapping.approvalRequired)
    return {
      required: true,
      reason: mapping.approvalReason ?? 'Mapping flagged for approval',
      level: mapping.verticalId === 'counsel' ? 'partner' : 'lead',
    };
  return { required: false, reason: null, level: 'auto' };
}

export interface DryRunSummary {
  readonly recordsExtracted: number;
  readonly recordsFiltered: number;
  readonly recordsRedacted: number;
  readonly recordsToDeliver: number;
  readonly policyHits: readonly { policyId: string; outcome: string }[];
  readonly estimatedLatencyMs: number;
}

export function buildDryRunSummary(
  mapping: RelayMapping,
  source: RelaySource | null,
  policies: readonly RelayPolicy[],
): DryRunSummary {
  const baseRecords = source ? Math.round(source.rowCount * 0.0006) : 25_000;
  const filtered = Math.round(baseRecords * 0.04);
  const redacted = mapping.transformations.filter((t) => t.piiHandling !== 'pass').length * Math.round(baseRecords * 0.012);
  const policyHits: { policyId: string; outcome: string }[] = [];
  for (const p of policies) {
    if (p.scope.includes(mapping.verticalId)) {
      const hits = p.recentHits.filter((h) => h.syncId.includes(mapping.verticalId));
      if (hits.length > 0) policyHits.push({ policyId: p.id, outcome: p.enforcement });
    }
  }
  return {
    recordsExtracted: baseRecords,
    recordsFiltered: filtered,
    recordsRedacted: redacted,
    recordsToDeliver: Math.max(0, baseRecords - filtered),
    policyHits: policyHits.slice(0, 6),
    estimatedLatencyMs: 220 + mapping.transformations.length * 18,
  };
}

// ─── Lutar Σ composition (rational unit-fraction weights) ───────────────────
/**
 * Σ = ∏ axisᵢ^wᵢ  where wᵢ = pᵢ/qᵢ are unit fractions. The composition is
 * monotone, bit-exact reproducible, and pinned to 0 if any axis collapses.
 *
 * Default weights are the Egyptian unit-fraction split (1/2, 1/4, 1/8, 1/8).
 * Returns Σ in [0,1].
 */
export interface LutarAxes {
  readonly P: number; // provenance
  readonly K: number; // containment
  readonly phi: number; // coherence
  readonly C: number; // convergence
}

export interface LutarSigma {
  readonly sigma: number;
  readonly axes: LutarAxes;
  readonly weights: { P: [number, number]; K: [number, number]; phi: [number, number]; C: [number, number] };
  readonly floor: number;
  readonly ceil: number;
  readonly formula: string;
}

export function computeLutarSigma(axes: LutarAxes): LutarSigma {
  // Egyptian unit-fraction weights: 1/2 + 1/4 + 1/8 + 1/8 = 1.
  const w: LutarSigma['weights'] = {
    P: [1, 2],
    K: [1, 4],
    phi: [1, 8],
    C: [1, 8],
  };
  const wP = w.P[0] / w.P[1];
  const wK = w.K[0] / w.K[1];
  const wPhi = w.phi[0] / w.phi[1];
  const wC = w.C[0] / w.C[1];
  const safe = (v: number) => Math.max(1e-9, Math.min(1, v));
  const sigma =
    Math.pow(safe(axes.P), wP) *
    Math.pow(safe(axes.K), wK) *
    Math.pow(safe(axes.phi), wPhi) *
    Math.pow(safe(axes.C), wC);
  const vals = [axes.P, axes.K, axes.phi, axes.C];
  return {
    sigma: Math.round(sigma * 10000) / 10000,
    axes,
    weights: w,
    floor: Math.min(...vals),
    ceil: Math.max(...vals),
    formula: 'Σ = P^(1/2) · K^(1/4) · Φ^(1/8) · C^(1/8)',
  };
}

// ─── Lutar Σ envelope (axis-variance bounds) ────────────────────────────────
/**
 * Σ envelope — confidence interval around Σ derived from axis dispersion. The
 * monotone form Σ = ∏ axisᵢ^wᵢ is exact, but axes themselves carry sampling
 * noise. The envelope expresses the implicit Σ range when each axis is
 * perturbed by its mean-deviation, weighted by the same Egyptian unit
 * fractions used in the canonical Σ. Pure, deterministic, no randomness.
 *
 * Returns Σ_low / Σ_high bracketing the canonical Σ. Width tightens as axes
 * cluster, widens when one axis falls far from the mean.
 */
export interface LutarEnvelope {
  readonly sigma: number;
  readonly sigmaLow: number;
  readonly sigmaHigh: number;
  readonly width: number;
  readonly dispersion: number;
  readonly tightestAxis: 'P' | 'K' | 'phi' | 'C';
  readonly weakestAxis: 'P' | 'K' | 'phi' | 'C';
  readonly formula: string;
}

export function computeLutarEnvelope(axes: LutarAxes): LutarEnvelope {
  const safe = (v: number) => Math.max(1e-9, Math.min(1, v));
  const wP = 1 / 2, wK = 1 / 4, wPhi = 1 / 8, wC = 1 / 8;
  const sigma =
    Math.pow(safe(axes.P), wP) *
    Math.pow(safe(axes.K), wK) *
    Math.pow(safe(axes.phi), wPhi) *
    Math.pow(safe(axes.C), wC);
  const mean = (axes.P + axes.K + axes.phi + axes.C) / 4;
  const devs = {
    P: Math.abs(axes.P - mean),
    K: Math.abs(axes.K - mean),
    phi: Math.abs(axes.phi - mean),
    C: Math.abs(axes.C - mean),
  };
  const dispersion = (devs.P + devs.K + devs.phi + devs.C) / 4;
  const low = (a: number, dev: number) => safe(a - dev);
  const high = (a: number, dev: number) => safe(a + dev);
  const sigmaLow =
    Math.pow(low(axes.P, devs.P), wP) *
    Math.pow(low(axes.K, devs.K), wK) *
    Math.pow(low(axes.phi, devs.phi), wPhi) *
    Math.pow(low(axes.C, devs.C), wC);
  const sigmaHigh =
    Math.pow(high(axes.P, devs.P), wP) *
    Math.pow(high(axes.K, devs.K), wK) *
    Math.pow(high(axes.phi, devs.phi), wPhi) *
    Math.pow(high(axes.C, devs.C), wC);
  const axisKeys = ['P', 'K', 'phi', 'C'] as const;
  let tightest: typeof axisKeys[number] = 'P';
  let weakest: typeof axisKeys[number] = 'P';
  for (const k of axisKeys) {
    if (devs[k] < devs[tightest]) tightest = k;
    if (devs[k] > devs[weakest]) weakest = k;
  }
  return {
    sigma: Math.round(sigma * 10000) / 10000,
    sigmaLow: Math.round(sigmaLow * 10000) / 10000,
    sigmaHigh: Math.round(sigmaHigh * 10000) / 10000,
    width: Math.round((sigmaHigh - sigmaLow) * 10000) / 10000,
    dispersion: Math.round(dispersion * 10000) / 10000,
    tightestAxis: tightest,
    weakestAxis: weakest,
    formula: 'Σ_lo, Σ_hi = ∏ (axisᵢ ± |axisᵢ − mean|)^wᵢ',
  };
}

// ─── Lutar Σ flow (velocity vs prior) ───────────────────────────────────────
/**
 * Σ-flow — first-difference dynamics over a sequence of prior Σ samples.
 * Returns Σ velocity (Δ vs immediate prior), Σ acceleration (Δ²), and a
 * monotonicity score (0..1) that approaches 1 when Σ rises monotonically.
 * Pure function of an ordered sample window.
 */
export interface LutarFlow {
  readonly current: number;
  readonly prior: number | null;
  readonly velocity: number;
  readonly acceleration: number;
  readonly monotonicity: number;
  readonly trend: 'rising' | 'falling' | 'flat' | 'oscillating';
  readonly samples: number;
}

export function computeLutarFlow(samples: readonly number[]): LutarFlow {
  if (samples.length === 0) {
    return { current: 0, prior: null, velocity: 0, acceleration: 0, monotonicity: 0, trend: 'flat', samples: 0 };
  }
  const current = samples[samples.length - 1]!;
  const prior = samples.length > 1 ? samples[samples.length - 2]! : null;
  const priorPrior = samples.length > 2 ? samples[samples.length - 3]! : null;
  const velocity = prior === null ? 0 : current - prior;
  const acceleration = priorPrior === null || prior === null ? 0 : (current - prior) - (prior - priorPrior);
  let rising = 0;
  let falling = 0;
  for (let i = 1; i < samples.length; i++) {
    const d = samples[i]! - samples[i - 1]!;
    if (d > 1e-6) rising++;
    else if (d < -1e-6) falling++;
  }
  const transitions = rising + falling;
  const monotonicity = transitions === 0 ? 1 : Math.max(rising, falling) / transitions;
  const trend: LutarFlow['trend'] =
    Math.abs(velocity) < 1e-4 ? 'flat'
    : monotonicity < 0.6 ? 'oscillating'
    : velocity > 0 ? 'rising'
    : 'falling';
  return {
    current: Math.round(current * 10000) / 10000,
    prior: prior === null ? null : Math.round(prior * 10000) / 10000,
    velocity: Math.round(velocity * 10000) / 10000,
    acceleration: Math.round(acceleration * 10000) / 10000,
    monotonicity: Math.round(monotonicity * 10000) / 10000,
    trend,
    samples: samples.length,
  };
}

// ─── Aggregate cockpit KPIs ─────────────────────────────────────────────────
export function buildCockpitKpis(args: {
  events: readonly RelayRunEvent[];
  destinations: readonly RelayDestination[];
  mappings: readonly RelayMapping[];
  outcomes: readonly RelayOutcome[];
  policies: readonly RelayPolicy[];
}): AmaruKpis {
  const { events, destinations, mappings, outcomes, policies } = args;
  const last24Boundary = Date.parse('2026-05-04T03:55:00Z');
  const recent = events.filter((e) => Date.parse(e.atIso) >= last24Boundary);
  const records = recent
    .filter((e) => e.type === 'completed')
    .reduce((s, e) => s + e.recordsAffected, 0);
  const failed = recent
    .filter((e) => e.type === 'failed' || e.type === 'rolled_back')
    .reduce((s, e) => s + e.recordsAffected, 0);
  const policyBlocks = policies
    .flatMap((p) => p.recentHits)
    .filter((h) => Date.parse(h.atIso) >= last24Boundary && (h.outcome === 'block' || h.outcome === 'rollback' || h.outcome === 'quarantine'))
    .length;
  const approvalQueue = mappings.filter((m) => m.approvalRequired).length;
  const destHealth = Math.round(
    destinations.reduce((s, d) => s + d.healthScore, 0) / destinations.length,
  );
  const settledLatencies = recent.filter((e) => e.type === 'completed').map((e) => e.latencyMs);
  const avgLatencyMs = settledLatencies.length
    ? Math.round(settledLatencies.reduce((s, l) => s + l, 0) / settledLatencies.length)
    : 0;
  const uniqueSyncs = new Set(events.slice(0, 200).map((e) => e.syncId)).size;
  return {
    activeSyncs: uniqueSyncs,
    recordsActivated24h: records,
    failedRecords24h: failed,
    policyBlocks24h: policyBlocks,
    approvalQueue,
    destinationHealth: destHealth,
    avgLatencyMs,
    outcomeLiftPct: calculateOutcomeLift(outcomes),
  };
}

// ─── Approval queue rollup ──────────────────────────────────────────────────
export function buildApprovalQueue(
  mappings: readonly RelayMapping[],
  source: (id: string) => RelaySource | null,
): readonly ApprovalRequest[] {
  return mappings
    .filter((m) => m.approvalRequired)
    .map((m) => {
      const blast = estimateBlastRadius(m, source(m.modelId));
      return {
        id: `appr-${m.id}`,
        syncName: m.name,
        mappingId: m.id,
        verticalId: m.verticalId,
        destinationId: m.destinationId,
        reason: m.approvalReason ?? 'Approval required',
        proposedAtIso: '2026-05-04T20:00:00Z',
        severity: blast.severity,
        recordsImpacted: blast.recordsAtRisk,
      };
    });
}
