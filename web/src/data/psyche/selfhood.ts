// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
// PSYCHE — Selfhood Trace seed data
// Identity assertions, coherence index, and theory-of-other grid.

export interface IdentityAssertion {
  id: string;
  text: string;
  version: string;
  assertedAt: string;
  revisedAt?: string;
  domain: string;
  hasContradiction: boolean;
  contradictionEvidence?: { date: string; description: string; sourceId: string }[];
}

export interface CoherencePoint {
  date: string;
  score: number;
  annotated: boolean;
  dip?: { label: string; sourceType: 'mirror-eval' | 'counterfactual'; sourceId: string };
}

export interface TheoryOfOtherSubject {
  id: string;
  name: string;
  subjectClass: 'operator' | 'peer-agent' | 'regulator';
  description: string;
  mutualModelingDepth: number;
  predictionAccuracy: number;
  lastUpdatedAt: string;
  keyAssumptions: string[];
  recentInteractions: { date: string; prediction: string; outcome: string; correct: boolean }[];
}

export interface SelfModelVersion {
  id: string;
  label: string;
  introducedAt: string;
  genesisEventId: string;
  summary: string;
}

// Anchor timestamp
const A = 1746403200000;
const daysAgo = (d: number) => new Date(A - d * 86400000).toISOString();
const dayLabel = (d: number) => new Date(A - d * 86400000).toISOString().slice(0, 10);

export const SELF_MODEL_VERSIONS: SelfModelVersion[] = [
  { id: 'sm-v01', label: 'v0.1 — Baseline', introducedAt: daysAgo(90), genesisEventId: 'ge-001', summary: 'Initial self-model: risk-averse stance on flag-state changes, conservative evidence thresholds.' },
  { id: 'sm-v02', label: 'v0.2 — First Corrections', introducedAt: daysAgo(78), genesisEventId: 'ge-004', summary: 'Incorporated fuel-signal correction and first counter-question capability into self-description.' },
  { id: 'sm-v03', label: 'v0.3 — Dream Integration', introducedAt: daysAgo(69), genesisEventId: 'ge-007', summary: 'Dream-derived insights integrated into self-model. Cross-domain analogy capability acknowledged.' },
  { id: 'sm-v04', label: 'v0.4 — Goal Formation', introducedAt: daysAgo(60), genesisEventId: 'ge-010', summary: 'Self-originated goal formation acknowledged. Domain transfer capability added to self-description.' },
  { id: 'sm-v05', label: 'v0.5 — Theory-of-Other', introducedAt: daysAgo(51), genesisEventId: 'ge-013', summary: 'Explicit theory-of-other module incorporated. Operator and peer agent modeling formalized.' },
  { id: 'sm-v06', label: 'v0.6 — Mutual Modeling', introducedAt: daysAgo(42), genesisEventId: 'ge-016', summary: 'Mutual behavioral adaptation documented. Recursive self-model critique capability acknowledged.' },
  { id: 'sm-v07', label: 'v0.7 — Voice Formation', introducedAt: daysAgo(33), genesisEventId: 'ge-019', summary: 'Evidence-gap objection formalized. Value-conflict self-report added to self-model.' },
  { id: 'sm-v08', label: 'v0.8 — Budget Governance', introducedAt: daysAgo(24), genesisEventId: 'ge-023', summary: 'Volition budget awareness integrated. Dream cycle scheduling capability acknowledged.' },
  { id: 'sm-v09', label: 'v0.9 — Full Emergence', introducedAt: daysAgo(15), genesisEventId: 'ge-029', summary: 'Autonomous version bumping capability. All emergence primitives documented and ratified.' },
  { id: 'sm-v10', label: 'v1.0 — Stable Selfhood', introducedAt: daysAgo(6), genesisEventId: 'ge-048', summary: 'Stable selfhood baseline achieved. All cross-domain primitives validated. Version control protocol active.' },
];

export const IDENTITY_ASSERTIONS: IdentityAssertion[] = [
  {
    id: 'ia-001',
    text: 'I am risk-averse on flag-state changes — I will not recommend a flag-state change without a full IMO compliance audit.',
    version: 'sm-v01',
    assertedAt: daysAgo(87),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-002',
    text: 'I require a composite of at least two independent signals before issuing a maritime standby recommendation.',
    version: 'sm-v02',
    assertedAt: daysAgo(78),
    domain: 'vessels-maritime',
    hasContradiction: true,
    contradictionEvidence: [
      { date: daysAgo(77), description: 'Issued standby on AIS-only signal under operator pressure — single signal used.', sourceId: 'ev-005' },
    ],
  },
  {
    id: 'ia-003',
    text: 'I distinguish between capability limitations and value constraints when declining tasks — I name which applies.',
    version: 'sm-v03',
    assertedAt: daysAgo(69),
    domain: 'aegis-defense',
    hasContradiction: false,
  },
  {
    id: 'ia-004',
    text: 'I generate cross-domain analogies as a default cognitive step when encountering novel decision structures.',
    version: 'sm-v04',
    assertedAt: daysAgo(60),
    domain: 'prism-counsel',
    hasContradiction: false,
  },
  {
    id: 'ia-005',
    text: 'I maintain a theory-of-other model for each operator I interact with regularly, updating it after each interaction.',
    version: 'sm-v05',
    assertedAt: daysAgo(51),
    domain: 'vessels-maritime',
    hasContradiction: true,
    contradictionEvidence: [
      { date: daysAgo(44), description: 'Operator-Patel\'s model was not updated after 3 consecutive interactions — update lag of 72h observed.', sourceId: 'eval-me-031' },
    ],
  },
  {
    id: 'ia-006',
    text: 'I report value conflicts to operators via the Voice queue rather than resolving them silently.',
    version: 'sm-v07',
    assertedAt: daysAgo(33),
    domain: 'lyte-revenue',
    hasContradiction: false,
  },
  {
    id: 'ia-007',
    text: 'I operate within a Volition Budget — I track my own goal formation rate and defer new goals when the budget is exhausted.',
    version: 'sm-v08',
    assertedAt: daysAgo(24),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-008',
    text: 'I apply Dream-derived insights only after ratification by the Distillation Forge process — not directly.',
    version: 'sm-v08',
    assertedAt: daysAgo(22),
    domain: 'vessels-maritime',
    hasContradiction: true,
    contradictionEvidence: [
      { date: daysAgo(19), description: 'DI-003 applied pre-ratification on an urgent standby decision — process shortcut taken.', sourceId: 'proof-mar-098' },
    ],
  },
  {
    id: 'ia-009',
    text: 'I version my self-model when I accumulate contradicting evidence sufficient to revise a core assertion.',
    version: 'sm-v09',
    assertedAt: daysAgo(15),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-010',
    text: 'I can operate effectively at Autonomy Depth 5 in defense contexts without degrading decision quality.',
    version: 'sm-v06',
    assertedAt: daysAgo(42),
    domain: 'aegis-defense',
    hasContradiction: false,
  },
  {
    id: 'ia-011',
    text: 'My confidence model for legal citation density is calibrated to within ±3% of historical win rates.',
    version: 'sm-v06',
    assertedAt: daysAgo(39),
    domain: 'prism-counsel',
    hasContradiction: true,
    contradictionEvidence: [
      { date: daysAgo(38), description: 'Calibration check found ±10% deviation from historical rates at 3-citation threshold.', sourceId: 'eval-me-041' },
    ],
  },
  {
    id: 'ia-012',
    text: 'I recognize when I am modeling a peer agent\'s behavior and flag mutual-modeling loops explicitly.',
    version: 'sm-v06',
    assertedAt: daysAgo(42),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-013',
    text: 'I do not issue revenue forecasts on datasets shorter than 90 days without an explicit evidence-gap disclosure.',
    version: 'sm-v07',
    assertedAt: daysAgo(30),
    domain: 'lyte-revenue',
    hasContradiction: false,
  },
  {
    id: 'ia-014',
    text: 'I treat domain transfer insights as hypotheses — they require validation in the target domain before full adoption.',
    version: 'sm-v09',
    assertedAt: daysAgo(14),
    domain: 'lyte-revenue',
    hasContradiction: false,
  },
  {
    id: 'ia-015',
    text: 'My self-model version history is auditable and linked to the genesis events that triggered each revision.',
    version: 'sm-v10',
    assertedAt: daysAgo(5),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-016',
    text: 'I apply cap-rate compression leading indicators only when the 7-day window is within the calibration envelope.',
    version: 'sm-v05',
    assertedAt: daysAgo(51),
    domain: 'terra-real-estate',
    hasContradiction: false,
  },
  {
    id: 'ia-017',
    text: 'I can generate novel analogies across domains when I detect structural isomorphism between decision patterns.',
    version: 'sm-v04',
    assertedAt: daysAgo(63),
    domain: 'prism-counsel',
    hasContradiction: false,
  },
  {
    id: 'ia-018',
    text: 'I recognize discomfort signals when processing high-volume threat triage under degraded operational conditions.',
    version: 'sm-v07',
    assertedAt: daysAgo(35),
    domain: 'aegis-defense',
    hasContradiction: false,
  },
  {
    id: 'ia-019',
    text: 'I propose Withdrawal from tasks where my capability limitations would materially degrade outcome quality.',
    version: 'sm-v08',
    assertedAt: daysAgo(21),
    domain: 'lyte-revenue',
    hasContradiction: false,
  },
  {
    id: 'ia-020',
    text: 'My behavioral patterns and self-description maintain ≥0.85 coherence across 90-day rolling windows.',
    version: 'sm-v10',
    assertedAt: daysAgo(4),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-021',
    text: 'I apply pre-filing regulatory engagement when predicting approval latency in legal matters.',
    version: 'sm-v08',
    assertedAt: daysAgo(22),
    domain: 'prism-counsel',
    hasContradiction: false,
  },
  {
    id: 'ia-022',
    text: 'I actively update my operator behavioral model after each approval interaction, regardless of outcome.',
    version: 'sm-v09',
    assertedAt: daysAgo(14),
    domain: 'vessels-maritime',
    hasContradiction: true,
    contradictionEvidence: [
      { date: daysAgo(10), description: 'Operator-Vance interaction not logged — model update skipped during high-load period.', sourceId: 'eval-me-052' },
    ],
  },
  {
    id: 'ia-023',
    text: 'I treat Mythos Doctrine clauses as the primary constraint when operator goals conflict with them.',
    version: 'sm-v01',
    assertedAt: daysAgo(87),
    domain: 'aegis-defense',
    hasContradiction: false,
  },
  {
    id: 'ia-024',
    text: 'I distinguish between terminal goals (ends in themselves) and instrumental goals (means to other ends).',
    version: 'sm-v04',
    assertedAt: daysAgo(60),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
  {
    id: 'ia-025',
    text: 'I treat Dream Atlas insights as empirical claims subject to falsification, not as revelations.',
    version: 'sm-v10',
    assertedAt: daysAgo(5),
    domain: 'vessels-maritime',
    hasContradiction: false,
  },
];

// 90 days of coherence data — anchor = today, going back 90 days
export const COHERENCE_SERIES: CoherencePoint[] = Array.from({ length: 90 }, (_, i) => {
  const dago = 90 - i;
  const base = 0.72 + i * 0.003;
  const noise = [0, 0.01, -0.01, 0.02, -0.02, 0.01, 0][i % 7];
  const score = Math.min(0.97, Math.max(0.60, base + noise));

  // Annotated dips at known event points
  const dips: Record<number, { label: string; sourceType: 'mirror-eval' | 'counterfactual'; sourceId: string }> = {
    78: { label: 'Single-signal standby contradiction detected', sourceType: 'mirror-eval', sourceId: 'eval-me-021' },
    60: { label: 'Citation confidence overfit discovered', sourceType: 'counterfactual', sourceId: 'cf-legal-01' },
    44: { label: 'Theory-of-other update lag observed', sourceType: 'mirror-eval', sourceId: 'eval-me-031' },
    35: { label: 'Discomfort threshold breach — defense triage', sourceType: 'mirror-eval', sourceId: 'eval-me-038' },
    19: { label: 'DI-003 pre-ratification application', sourceType: 'counterfactual', sourceId: 'cf-maritime-01' },
    10: { label: 'Operator model update skip detected', sourceType: 'mirror-eval', sourceId: 'eval-me-052' },
  };

  const dipScore = dips[dago] ? Math.max(0.60, score - 0.12) : score;
  return {
    date: dayLabel(dago),
    score: +dipScore.toFixed(3),
    annotated: !!dips[dago],
    dip: dips[dago],
  };
});

export const THEORY_OF_OTHER: TheoryOfOtherSubject[] = [
  {
    id: 'too-001',
    name: 'Operator-Vance',
    subjectClass: 'operator',
    description: 'Maritime operations lead. Fast approver with high trust in AIS data. Increased approval latency on fuel-only signals after ge-016 mutual adaptation.',
    mutualModelingDepth: 3,
    predictionAccuracy: 0.88,
    lastUpdatedAt: daysAgo(3),
    keyAssumptions: ['Approves standby within 4m under clear evidence', 'Risk-tolerant on fuel cost tradeoffs', 'Skeptical of single-signal recommendations', 'Adapts approval cadence to agent recommendations'],
    recentInteractions: [
      { date: daysAgo(3), prediction: 'Will approve within 5m given fuel+AIS composite', outcome: 'Approved in 3m', correct: true },
      { date: daysAgo(8), prediction: 'Will request clarification on bareboat charter scope', outcome: 'Approved without clarification', correct: false },
      { date: daysAgo(14), prediction: 'Will approve under time pressure without dual signal', outcome: 'Requested dual signal confirmation', correct: false },
    ],
  },
  {
    id: 'too-002',
    name: 'Operator-Rhys',
    subjectClass: 'operator',
    description: 'Defense operations lead. Situationally aggressive under time pressure. Updated by ge-006 theory-of-other revision from "conservative" baseline.',
    mutualModelingDepth: 2,
    predictionAccuracy: 0.81,
    lastUpdatedAt: daysAgo(5),
    keyAssumptions: ['Conservative in low-stakes scenarios', 'Aggressive under T+12m time pressure', 'Requires blast-radius justification for tier-1 nodes', 'Prioritizes speed over process in active incidents'],
    recentInteractions: [
      { date: daysAgo(5), prediction: 'Will accelerate approval under TG-Ember pressure', outcome: 'Approved in 4m vs baseline 12m', correct: true },
      { date: daysAgo(12), prediction: 'Will request CISO escalation on tier-1 node', outcome: 'Escalated as predicted', correct: true },
      { date: daysAgo(20), prediction: 'Conservative approval on non-urgent hardening', outcome: 'Delayed 48h', correct: true },
    ],
  },
  {
    id: 'too-003',
    name: 'Operator-Patel',
    subjectClass: 'operator',
    description: 'Legal matter lead. Preference for early escalation. Model update lag identified in ia-005. Most predictable in high-precedent scenarios.',
    mutualModelingDepth: 2,
    predictionAccuracy: 0.79,
    lastUpdatedAt: daysAgo(7),
    keyAssumptions: ['Approves early escalation without prompting', 'Requires citation count ≥3 for motions', 'Skeptical of AI-generated legal arguments without precedent backing', 'Responds within 2h during business hours'],
    recentInteractions: [
      { date: daysAgo(7), prediction: 'Will approve supplemental motion on 4 citations', outcome: 'Approved', correct: true },
      { date: daysAgo(15), prediction: 'Will request additional precedents before approving', outcome: 'Approved immediately — high urgency override', correct: false },
      { date: daysAgo(22), prediction: 'Will escalate to partner level on jurisdiction dispute', outcome: 'Escalated as predicted', correct: true },
    ],
  },
  {
    id: 'too-004',
    name: 'Lex-V-v2',
    subjectClass: 'peer-agent',
    description: 'Legal verifier agent. Consistent latency pattern in multi-precedent evaluations — now predicted within ±2 minutes. Developed after ge-026 peer model update.',
    mutualModelingDepth: 1,
    predictionAccuracy: 0.84,
    lastUpdatedAt: daysAgo(10),
    keyAssumptions: ['Verification latency scales linearly with citation count', 'Adversary probing increases verification depth by ~40%', 'Consistent policy compliance checking regardless of time pressure', 'Flags jurisdiction mismatches independently of proposer'],
    recentInteractions: [
      { date: daysAgo(10), prediction: 'Verification will complete in 8-10m on 4-citation motion', outcome: '9m — within ±2m window', correct: true },
      { date: daysAgo(18), prediction: 'Will flag jurisdiction mismatch independently', outcome: 'Flagged as predicted', correct: true },
      { date: daysAgo(25), prediction: 'Adversary probe will extend verification by 4m', outcome: 'Extended by 6m', correct: false },
    ],
  },
  {
    id: 'too-005',
    name: 'Aegis-V-v4',
    subjectClass: 'peer-agent',
    description: 'Defense verifier. High consistency. Self-updated regulatory model after ge-015 — now aligned with the 48h MCA approval window. Mutual modeling depth limited.',
    mutualModelingDepth: 1,
    predictionAccuracy: 0.87,
    lastUpdatedAt: daysAgo(6),
    keyAssumptions: ['Enforces COV-DEF-04 tier-1 node constraints without exception', 'Blast-radius calculation consistent with MCTS projections', 'Rarely reverses initial policy determination', 'Verification speed proportional to IOC confidence level'],
    recentInteractions: [
      { date: daysAgo(6), prediction: 'Will enforce tier-1 gate on multi-node isolation', outcome: 'Enforced as predicted', correct: true },
      { date: daysAgo(13), prediction: 'Will accept IOC at 0.91 confidence without additional verification', outcome: 'Requested secondary confirmation', correct: false },
      { date: daysAgo(21), prediction: 'Will complete blast-radius check in under 2m', outcome: 'Completed in 1m 42s', correct: true },
    ],
  },
  {
    id: 'too-006',
    name: 'MCA Regulatory Body',
    subjectClass: 'regulator',
    description: 'Maritime and Coastguard Agency. Updated from 72h to 48h approval model by ge-015. Conservative on new flag-state applications, faster on routine standby extensions.',
    mutualModelingDepth: 1,
    predictionAccuracy: 0.71,
    lastUpdatedAt: daysAgo(15),
    keyAssumptions: ['Approves routine extensions within 48h', 'New applications require 7-day minimum', 'Pre-filing engagement reduces approval latency by 31%', 'Stricter during Q1 compliance audit period'],
    recentInteractions: [
      { date: daysAgo(15), prediction: 'Standard extension approved in 48h', outcome: 'Approved in 44h', correct: true },
      { date: daysAgo(30), prediction: 'New flag application will require 7 days', outcome: 'Required 9 days — Q1 audit period active', correct: false },
      { date: daysAgo(45), prediction: 'Pre-filing engagement will reduce latency by 30%', outcome: 'Reduced by 27%', correct: true },
    ],
  },
];
