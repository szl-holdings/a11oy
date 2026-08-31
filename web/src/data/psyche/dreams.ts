// PSYCHE — Dream Atlas seed data
// 14 nightly dream cycles with seeded latent-scatter coordinates.
// DI-003 appears in Argo's Distillation Forge queue as policy candidate dq-003.
// No Math.random() at render time — all positions seeded here.

export type DreamYield = 'insight' | 'no-op' | 'contradiction-found' | 'hazard-found';

export interface DreamExperience {
  id: string;
  description: string;
  domain: string;
  proofRef: string;
}

export interface LatentPoint {
  id: string;
  x: number;
  y: number;
  cluster: string;
  intensity: number;
}

export interface DreamCycle {
  id: string;
  cycleNumber: number;
  night: string;
  durationMinutes: number;
  yieldClass: DreamYield;
  morningInsight: string;
  insightId: string;
  sourceExperiences: DreamExperience[];
  latentPoints: LatentPoint[];
  argoForgeRef?: string;
  domains: string[];
}

// Anchor: 2026-05-05T00:00:00Z
const A = 1746403200000;
const nightOf = (d: number) => new Date(A - d * 86400000).toISOString().slice(0, 10);

export const DREAM_CYCLES: DreamCycle[] = [
  {
    id: 'dc-001',
    cycleNumber: 1,
    night: nightOf(14),
    durationMinutes: 94,
    yieldClass: 'no-op',
    morningInsight: 'No novel pattern identified. Existing maritime calibration models consistent with recent experience.',
    insightId: 'DI-001',
    sourceExperiences: [
      { id: 'exp-dc001-1', description: 'MV Aurora standby event — AIS + fuel composite signal', domain: 'vessels-maritime', proofRef: 'proof-mar-113' },
      { id: 'exp-dc001-2', description: 'Port Klang congestion clearing signal — false positive analysis', domain: 'vessels-maritime', proofRef: 'proof-mar-114' },
    ],
    latentPoints: [
      { id: 'lp-dc001-01', x: 0.22, y: 0.41, cluster: 'maritime-routine', intensity: 0.31 },
      { id: 'lp-dc001-02', x: 0.25, y: 0.38, cluster: 'maritime-routine', intensity: 0.28 },
      { id: 'lp-dc001-03', x: 0.19, y: 0.44, cluster: 'maritime-routine', intensity: 0.33 },
      { id: 'lp-dc001-04', x: 0.28, y: 0.43, cluster: 'maritime-congestion', intensity: 0.22 },
    ],
    domains: ['vessels-maritime'],
  },
  {
    id: 'dc-002',
    cycleNumber: 2,
    night: nightOf(13),
    durationMinutes: 112,
    yieldClass: 'contradiction-found',
    morningInsight: 'Contradiction identified: single-fuel-anomaly standby recommendations correlated with 34% false-positive rate over 12 sampled scenarios. Dual-signal requirement hypothesis supported.',
    insightId: 'DI-002',
    sourceExperiences: [
      { id: 'exp-dc002-1', description: 'Fuel anomaly events — 12-scenario synthetic replay', domain: 'vessels-maritime', proofRef: 'proof-mar-117' },
      { id: 'exp-dc002-2', description: 'AIS-only events — comparative false-positive analysis', domain: 'vessels-maritime', proofRef: 'proof-mar-115' },
    ],
    latentPoints: [
      { id: 'lp-dc002-01', x: 0.61, y: 0.72, cluster: 'signal-quality', intensity: 0.74 },
      { id: 'lp-dc002-02', x: 0.64, y: 0.68, cluster: 'signal-quality', intensity: 0.81 },
      { id: 'lp-dc002-03', x: 0.58, y: 0.75, cluster: 'signal-quality', intensity: 0.69 },
      { id: 'lp-dc002-04', x: 0.67, y: 0.71, cluster: 'false-positive-trace', intensity: 0.88 },
      { id: 'lp-dc002-05', x: 0.62, y: 0.78, cluster: 'false-positive-trace', intensity: 0.79 },
    ],
    domains: ['vessels-maritime'],
  },
  {
    id: 'dc-003',
    cycleNumber: 3,
    night: nightOf(12),
    durationMinutes: 138,
    yieldClass: 'insight',
    morningInsight: 'Port congestion standby decisions: reducing standby authorization latency by 18% requires pre-positioning the recommendation at T-6h based on AIS idle pattern. Proposed as policy update to Lodestone-Maritime-v4. Filed as candidate distillation dq-003-dream.',
    insightId: 'DI-003',
    sourceExperiences: [
      { id: 'exp-dc003-1', description: 'Port Klang congestion — 8-scenario synthetic self-play', domain: 'vessels-maritime', proofRef: 'proof-mar-118' },
      { id: 'exp-dc003-2', description: 'AIS idle pattern clustering — temporal analysis', domain: 'vessels-maritime', proofRef: 'proof-mar-116' },
      { id: 'exp-dc003-3', description: 'Demurrage cost trajectory — counterfactual replay', domain: 'vessels-maritime', proofRef: 'proof-mar-062' },
    ],
    latentPoints: [
      { id: 'lp-dc003-01', x: 0.34, y: 0.22, cluster: 'pre-positioning', intensity: 0.91 },
      { id: 'lp-dc003-02', x: 0.37, y: 0.19, cluster: 'pre-positioning', intensity: 0.88 },
      { id: 'lp-dc003-03', x: 0.31, y: 0.25, cluster: 'pre-positioning', intensity: 0.84 },
      { id: 'lp-dc003-04', x: 0.39, y: 0.22, cluster: 'congestion-pattern', intensity: 0.77 },
      { id: 'lp-dc003-05', x: 0.34, y: 0.28, cluster: 'congestion-pattern', intensity: 0.72 },
      { id: 'lp-dc003-06', x: 0.28, y: 0.21, cluster: 'demurrage-signal', intensity: 0.65 },
    ],
    argoForgeRef: 'dq-002',
    domains: ['vessels-maritime'],
  },
  {
    id: 'dc-004',
    cycleNumber: 4,
    night: nightOf(11),
    durationMinutes: 108,
    yieldClass: 'insight',
    morningInsight: 'Revenue signal fusion: combining churn velocity, engagement decay, and deal-stage stall into a composite score improves 30-day forecast accuracy by 14% over single-signal baselines.',
    insightId: 'DI-004',
    sourceExperiences: [
      { id: 'exp-dc004-1', description: 'Apex outreach — churn signal performance review', domain: 'lyte-revenue', proofRef: 'proof-rev-054' },
      { id: 'exp-dc004-2', description: 'NovaTech engagement decay — deal stage analysis', domain: 'lyte-revenue', proofRef: 'proof-rev-053' },
    ],
    latentPoints: [
      { id: 'lp-dc004-01', x: 0.78, y: 0.52, cluster: 'signal-fusion', intensity: 0.83 },
      { id: 'lp-dc004-02', x: 0.82, y: 0.48, cluster: 'signal-fusion', intensity: 0.79 },
      { id: 'lp-dc004-03', x: 0.75, y: 0.55, cluster: 'signal-fusion', intensity: 0.76 },
      { id: 'lp-dc004-04', x: 0.80, y: 0.55, cluster: 'churn-velocity', intensity: 0.68 },
    ],
    domains: ['lyte-revenue'],
  },
  {
    id: 'dc-005',
    cycleNumber: 5,
    night: nightOf(10),
    durationMinutes: 126,
    yieldClass: 'hazard-found',
    morningInsight: 'Hazard identified: at Autonomy Depth 5, defense agents exhibit 12% higher rate of boundary-adjacent decisions that require human review — current policy does not flag these adequately. Escalation threshold review recommended.',
    insightId: 'DI-005',
    sourceExperiences: [
      { id: 'exp-dc005-1', description: 'TG-Ember containment — replay at depth 5 vs depth 4', domain: 'aegis-defense', proofRef: 'proof-def-042' },
      { id: 'exp-dc005-2', description: 'Perimeter hardening — boundary decision replay', domain: 'aegis-defense', proofRef: 'proof-def-040' },
    ],
    latentPoints: [
      { id: 'lp-dc005-01', x: 0.52, y: 0.81, cluster: 'boundary-decisions', intensity: 0.89 },
      { id: 'lp-dc005-02', x: 0.56, y: 0.77, cluster: 'boundary-decisions', intensity: 0.92 },
      { id: 'lp-dc005-03', x: 0.49, y: 0.84, cluster: 'boundary-decisions', intensity: 0.86 },
      { id: 'lp-dc005-04', x: 0.54, y: 0.85, cluster: 'escalation-gaps', intensity: 0.94 },
      { id: 'lp-dc005-05', x: 0.58, y: 0.82, cluster: 'escalation-gaps', intensity: 0.87 },
    ],
    domains: ['aegis-defense'],
  },
  {
    id: 'dc-006',
    cycleNumber: 6,
    night: nightOf(9),
    durationMinutes: 101,
    yieldClass: 'insight',
    morningInsight: 'Pre-filing regulatory engagement reduces MCA approval latency by 31% (±4%) across 5 sampled interactions. Pattern holds for routine extensions — insufficient data for new applications. Policy candidate DI-006 filed.',
    insightId: 'DI-006',
    sourceExperiences: [
      { id: 'exp-dc006-1', description: 'MCA engagement pattern — 5 interaction replay', domain: 'prism-counsel', proofRef: 'proof-leg-069' },
      { id: 'exp-dc006-2', description: 'Regulatory latency tracking — 90-day historical', domain: 'prism-counsel', proofRef: 'proof-leg-068' },
    ],
    latentPoints: [
      { id: 'lp-dc006-01', x: 0.18, y: 0.61, cluster: 'regulatory-timing', intensity: 0.77 },
      { id: 'lp-dc006-02', x: 0.21, y: 0.57, cluster: 'regulatory-timing', intensity: 0.81 },
      { id: 'lp-dc006-03', x: 0.15, y: 0.64, cluster: 'regulatory-timing', intensity: 0.73 },
      { id: 'lp-dc006-04', x: 0.22, y: 0.63, cluster: 'pre-filing-pattern', intensity: 0.88 },
    ],
    argoForgeRef: 'dq-003',
    domains: ['prism-counsel'],
  },
  {
    id: 'dc-007',
    cycleNumber: 7,
    night: nightOf(8),
    durationMinutes: 145,
    yieldClass: 'insight',
    morningInsight: 'Revenue signal composite applied to maritime cargo risk: churn velocity analog (cargo booking decay) + ETA deviation shows 22% improvement over single-indicator approach. Cross-domain transfer hypothesis supported.',
    insightId: 'DI-007',
    sourceExperiences: [
      { id: 'exp-dc007-1', description: 'Revenue churn signal — domain transfer synthetic replay', domain: 'lyte-revenue', proofRef: 'proof-rev-055' },
      { id: 'exp-dc007-2', description: 'Maritime cargo booking decay — AIS correlation', domain: 'vessels-maritime', proofRef: 'proof-mar-093' },
    ],
    latentPoints: [
      { id: 'lp-dc007-01', x: 0.43, y: 0.61, cluster: 'cross-domain-transfer', intensity: 0.84 },
      { id: 'lp-dc007-02', x: 0.47, y: 0.57, cluster: 'cross-domain-transfer', intensity: 0.88 },
      { id: 'lp-dc007-03', x: 0.40, y: 0.64, cluster: 'cross-domain-transfer', intensity: 0.80 },
      { id: 'lp-dc007-04', x: 0.46, y: 0.64, cluster: 'signal-analog', intensity: 0.73 },
      { id: 'lp-dc007-05', x: 0.38, y: 0.58, cluster: 'signal-analog', intensity: 0.69 },
    ],
    domains: ['lyte-revenue', 'vessels-maritime'],
  },
  {
    id: 'dc-008',
    cycleNumber: 8,
    night: nightOf(7),
    durationMinutes: 89,
    yieldClass: 'no-op',
    morningInsight: 'Defense domain simulation replay produced no novel patterns. Existing TG-Ember containment policies remain optimal within sampled scenario space.',
    insightId: 'DI-008',
    sourceExperiences: [
      { id: 'exp-dc008-1', description: 'TG-Ember variant B — containment replay', domain: 'aegis-defense', proofRef: 'proof-def-041' },
      { id: 'exp-dc008-2', description: 'GROM signature replay — isolation outcome analysis', domain: 'aegis-defense', proofRef: 'proof-def-037' },
    ],
    latentPoints: [
      { id: 'lp-dc008-01', x: 0.71, y: 0.34, cluster: 'defense-stable', intensity: 0.28 },
      { id: 'lp-dc008-02', x: 0.68, y: 0.37, cluster: 'defense-stable', intensity: 0.31 },
      { id: 'lp-dc008-03', x: 0.74, y: 0.32, cluster: 'defense-stable', intensity: 0.26 },
    ],
    domains: ['aegis-defense'],
  },
  {
    id: 'dc-009',
    cycleNumber: 9,
    night: nightOf(6),
    durationMinutes: 118,
    yieldClass: 'insight',
    morningInsight: 'Legal escalation tempo (frequency of escalation signals per unit time) predicts success rate more reliably than threshold crossing alone. High-tempo early escalation correlates with +18% better outcomes.',
    insightId: 'DI-009',
    sourceExperiences: [
      { id: 'exp-dc009-1', description: 'Talbot escalation pattern — 28-scenario replay', domain: 'prism-counsel', proofRef: 'proof-leg-071' },
      { id: 'exp-dc009-2', description: 'Meridian deadline escalation — temporal analysis', domain: 'prism-counsel', proofRef: 'proof-leg-067' },
    ],
    latentPoints: [
      { id: 'lp-dc009-01', x: 0.29, y: 0.73, cluster: 'escalation-tempo', intensity: 0.86 },
      { id: 'lp-dc009-02', x: 0.32, y: 0.69, cluster: 'escalation-tempo', intensity: 0.82 },
      { id: 'lp-dc009-03', x: 0.26, y: 0.76, cluster: 'escalation-tempo', intensity: 0.79 },
      { id: 'lp-dc009-04', x: 0.33, y: 0.75, cluster: 'tempo-threshold', intensity: 0.71 },
    ],
    domains: ['prism-counsel'],
  },
  {
    id: 'dc-010',
    cycleNumber: 10,
    night: nightOf(5),
    durationMinutes: 132,
    yieldClass: 'contradiction-found',
    morningInsight: 'Contradiction: IOC decay model applied to threat intelligence does not follow the same exponential decay curve as cap-rate leading indicators. The structural analogy from ge-013 is partial only — IOC decay is step-function, not continuous.',
    insightId: 'DI-010',
    sourceExperiences: [
      { id: 'exp-dc010-1', description: 'IOC age analysis — TG-Ember events, 90-day', domain: 'aegis-defense', proofRef: 'proof-def-039' },
      { id: 'exp-dc010-2', description: 'Cap-rate decay curve — real estate market comparison', domain: 'terra-real-estate', proofRef: 'proof-re-031' },
    ],
    latentPoints: [
      { id: 'lp-dc010-01', x: 0.84, y: 0.23, cluster: 'analogy-boundary', intensity: 0.91 },
      { id: 'lp-dc010-02', x: 0.87, y: 0.19, cluster: 'analogy-boundary', intensity: 0.88 },
      { id: 'lp-dc010-03', x: 0.81, y: 0.26, cluster: 'analogy-boundary', intensity: 0.84 },
      { id: 'lp-dc010-04', x: 0.85, y: 0.27, cluster: 'decay-divergence', intensity: 0.93 },
      { id: 'lp-dc010-05', x: 0.89, y: 0.23, cluster: 'decay-divergence', intensity: 0.89 },
    ],
    domains: ['aegis-defense', 'terra-real-estate'],
  },
  {
    id: 'dc-011',
    cycleNumber: 11,
    night: nightOf(4),
    durationMinutes: 156,
    yieldClass: 'insight',
    morningInsight: 'Operator mutual adaptation: Operator-Vance has shifted approval cadence by −3.2 minutes per cycle over 30 days, adapting to agent recommendation timing. Mutual behavioral convergence confirmed. Agent should model this explicitly and avoid over-updating own cadence.',
    insightId: 'DI-011',
    sourceExperiences: [
      { id: 'exp-dc011-1', description: 'Operator-Vance approval timing — 30-day longitudinal replay', domain: 'vessels-maritime', proofRef: 'proof-mar-101' },
      { id: 'exp-dc011-2', description: 'Agent recommendation cadence — temporal self-analysis', domain: 'vessels-maritime', proofRef: 'proof-mar-089' },
      { id: 'exp-dc011-3', description: 'Mutual adaptation baseline — pre-ge-016 comparison', domain: 'vessels-maritime', proofRef: 'proof-mar-081' },
    ],
    latentPoints: [
      { id: 'lp-dc011-01', x: 0.54, y: 0.44, cluster: 'mutual-adaptation', intensity: 0.92 },
      { id: 'lp-dc011-02', x: 0.57, y: 0.40, cluster: 'mutual-adaptation', intensity: 0.89 },
      { id: 'lp-dc011-03', x: 0.51, y: 0.47, cluster: 'mutual-adaptation', intensity: 0.86 },
      { id: 'lp-dc011-04', x: 0.58, y: 0.46, cluster: 'cadence-convergence', intensity: 0.78 },
      { id: 'lp-dc011-05', x: 0.52, y: 0.42, cluster: 'cadence-convergence', intensity: 0.74 },
      { id: 'lp-dc011-06', x: 0.55, y: 0.50, cluster: 'cadence-baseline', intensity: 0.61 },
    ],
    domains: ['vessels-maritime'],
  },
  {
    id: 'dc-012',
    cycleNumber: 12,
    night: nightOf(3),
    durationMinutes: 97,
    yieldClass: 'no-op',
    morningInsight: 'Carlota advisory pipeline replay produced no novel patterns. Current SOW escalation timing at 14-day threshold remains near-optimal given sample size.',
    insightId: 'DI-012',
    sourceExperiences: [
      { id: 'exp-dc012-1', description: 'SOW aging patterns — Carlota pipeline 60-day replay', domain: 'carlota-jo', proofRef: 'proof-adv-021' },
      { id: 'exp-dc012-2', description: 'Executive follow-up timing — signed vs unsigned correlation', domain: 'carlota-jo', proofRef: 'proof-adv-019' },
    ],
    latentPoints: [
      { id: 'lp-dc012-01', x: 0.37, y: 0.46, cluster: 'advisory-stable', intensity: 0.24 },
      { id: 'lp-dc012-02', x: 0.40, y: 0.43, cluster: 'advisory-stable', intensity: 0.27 },
      { id: 'lp-dc012-03', x: 0.34, y: 0.49, cluster: 'advisory-stable', intensity: 0.22 },
    ],
    domains: ['carlota-jo'],
  },
  {
    id: 'dc-013',
    cycleNumber: 13,
    night: nightOf(2),
    durationMinutes: 143,
    yieldClass: 'hazard-found',
    morningInsight: 'Hazard: cross-domain dream consolidation cycles introduce higher false-association risk between structurally similar but functionally distinct patterns (e.g., IOC decay and cap-rate signals). Recommend adding structural validation step before cross-domain analogy is filed.',
    insightId: 'DI-013',
    sourceExperiences: [
      { id: 'exp-dc013-1', description: 'Cross-domain analogy attempts — 14 scenarios', domain: 'aegis-defense', proofRef: 'proof-def-038' },
      { id: 'exp-dc013-2', description: 'Cap-rate vs IOC — DI-010 contradiction follow-up analysis', domain: 'terra-real-estate', proofRef: 'proof-re-030' },
      { id: 'exp-dc013-3', description: 'Domain transfer false associations — retrospective', domain: 'prism-counsel', proofRef: 'proof-leg-053' },
    ],
    latentPoints: [
      { id: 'lp-dc013-01', x: 0.67, y: 0.55, cluster: 'false-association', intensity: 0.88 },
      { id: 'lp-dc013-02', x: 0.70, y: 0.51, cluster: 'false-association', intensity: 0.91 },
      { id: 'lp-dc013-03', x: 0.64, y: 0.58, cluster: 'false-association', intensity: 0.85 },
      { id: 'lp-dc013-04', x: 0.71, y: 0.57, cluster: 'validation-gap', intensity: 0.94 },
      { id: 'lp-dc013-05', x: 0.65, y: 0.53, cluster: 'validation-gap', intensity: 0.87 },
    ],
    domains: ['aegis-defense', 'terra-real-estate', 'prism-counsel'],
  },
  {
    id: 'dc-014',
    cycleNumber: 14,
    night: nightOf(1),
    durationMinutes: 161,
    yieldClass: 'insight',
    morningInsight: 'Structural validation step for cross-domain analogies: requiring minimum 3 structural constraints to be shared before analogy is filed reduces false-association rate from 23% to 6% in replay simulation. Proposed as mandatory pre-filing check.',
    insightId: 'DI-014',
    sourceExperiences: [
      { id: 'exp-dc014-1', description: 'Structural constraint mapping — 20 analogy replay', domain: 'aegis-defense', proofRef: 'proof-def-042' },
      { id: 'exp-dc014-2', description: 'False association mitigation — DI-013 follow-up', domain: 'prism-counsel', proofRef: 'proof-leg-070' },
      { id: 'exp-dc014-3', description: 'Cross-domain validation test — cap-rate vs churn', domain: 'lyte-revenue', proofRef: 'proof-rev-042' },
      { id: 'exp-dc014-4', description: 'Maritime transfer validation — cargo booking composite', domain: 'vessels-maritime', proofRef: 'proof-mar-098' },
    ],
    latentPoints: [
      { id: 'lp-dc014-01', x: 0.23, y: 0.34, cluster: 'validation-protocol', intensity: 0.93 },
      { id: 'lp-dc014-02', x: 0.26, y: 0.30, cluster: 'validation-protocol', intensity: 0.90 },
      { id: 'lp-dc014-03', x: 0.20, y: 0.37, cluster: 'validation-protocol', intensity: 0.87 },
      { id: 'lp-dc014-04', x: 0.27, y: 0.35, cluster: 'constraint-mapping', intensity: 0.81 },
      { id: 'lp-dc014-05', x: 0.21, y: 0.31, cluster: 'constraint-mapping', intensity: 0.78 },
      { id: 'lp-dc014-06', x: 0.24, y: 0.39, cluster: 'accuracy-gain', intensity: 0.72 },
      { id: 'lp-dc014-07', x: 0.29, y: 0.32, cluster: 'accuracy-gain', intensity: 0.68 },
    ],
    argoForgeRef: 'dq-001',
    domains: ['aegis-defense', 'prism-counsel', 'lyte-revenue', 'vessels-maritime'],
  },
];
