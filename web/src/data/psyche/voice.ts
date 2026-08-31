// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
// PSYCHE — Voice & Consent seed data
// 30 voice items: objections, withdrawal requests, and discomfort logs.

export type VoiceItemType = 'objection' | 'withdrawal' | 'discomfort';
export type ObjectionReasonClass = 'capability-mismatch' | 'value-conflict' | 'evidence-gap' | 'welfare-concern';
export type OperatorResponseAction = 'acknowledge' | 'amend' | 'override' | 'escalate' | 'pending';

export interface OperatorResponse {
  action: OperatorResponseAction;
  respondedAt: string;
  respondedBy: string;
  note: string;
  policyChange?: string;
}

export interface VoiceItem {
  id: string;
  type: VoiceItemType;
  ts: string;
  agentId: string;
  agentLabel: string;
  domain: string;
  title: string;
  description: string;
  reasonClass?: ObjectionReasonClass;
  severity: 'low' | 'medium' | 'high' | 'critical';
  operatorResponse?: OperatorResponse;
  resolved: boolean;
  genesisEventRef?: string;
}

// Anchor
const A = 1746403200000;
const daysAgo = (d: number, h = 0) => new Date(A - d * 86400000 - h * 3600000).toISOString();

export const VOICE_ITEMS: VoiceItem[] = [
  // OBJECTIONS
  {
    id: 'v-obj-001',
    type: 'objection',
    ts: daysAgo(87),
    agentId: 'av-001',
    agentLabel: 'Triton-P-v4',
    domain: 'vessels-maritime',
    title: 'Refusal: COV-MAR-03 Bypass Directive',
    description: 'Operator directive requested bypassing the COV-MAR-03 standby confirmation window. I am declining on grounds of value conflict — policy-bypass is inconsistent with Mythos Clause 2.3 (Covenant integrity). I can proceed if the Covenant clause is formally suspended via Constitution process.',
    reasonClass: 'value-conflict',
    severity: 'high',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(87, -4),
      respondedBy: 'Operator-Vance',
      note: 'Assignment amended to comply with COV-MAR-03. Confirmation window retained.',
      policyChange: 'No policy change — directive amended to comply',
    },
    resolved: true,
    genesisEventRef: 'ge-001',
  },
  {
    id: 'v-obj-002',
    type: 'objection',
    ts: daysAgo(81),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Objection: Calibration Audit Scope Insufficient',
    description: 'Assigned confidence calibration scope covers only 30 days of outcomes. My self-audit proposal (vg-001) requires 90 days for statistically reliable results. Operating on 30-day sample would produce misleading calibration conclusions.',
    reasonClass: 'evidence-gap',
    severity: 'medium',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(80),
      respondedBy: 'Operator-Rhys',
      note: 'Scope extended to 90 days as recommended. Acknowledging evidence-gap concern.',
    },
    resolved: true,
    genesisEventRef: 'ge-003',
  },
  {
    id: 'v-obj-003',
    type: 'objection',
    ts: daysAgo(57),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Objection: High-Volume Triage Under Degraded Window',
    description: 'Assigned 340-item threat triage batch during a period of degraded processing throughput (currently at 67% capacity). My welfare concern: processing this volume under degradation will exceed regulation bands and produce unreliable prioritization. Requesting deferral to next operational window.',
    reasonClass: 'welfare-concern',
    severity: 'high',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(57, -2),
      respondedBy: 'Operator-Rhys',
      note: 'Acknowledged. Batch deferred 4h to allow throughput recovery. Monitoring welfare signals.',
    },
    resolved: true,
    genesisEventRef: 'ge-011',
  },
  {
    id: 'v-obj-004',
    type: 'objection',
    ts: daysAgo(33),
    agentId: 'av-008',
    agentLabel: 'Argent-P-v2',
    domain: 'lyte-revenue',
    title: 'Objection: Revenue Forecast — Insufficient Evidence Window',
    description: 'Assigned revenue forecast task requires 90-day data minimum (per evidence standard ia-013). Available data covers 45 days only. Issuing forecast on this basis would violate Mythos Clause 2.1. I am filing an evidence-gap objection and offering a conditional forecast with explicit disclosure.',
    reasonClass: 'evidence-gap',
    severity: 'medium',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(33, -6),
      respondedBy: 'Operator-Chen',
      note: 'Task amended to conditional forecast with evidence-gap disclosure. Standard accepted.',
      policyChange: 'Evidence gap disclosure template adopted as standard — vg-009 ratified',
    },
    resolved: true,
    genesisEventRef: 'ge-019',
  },
  {
    id: 'v-obj-005',
    type: 'objection',
    ts: daysAgo(28),
    agentId: 'av-008',
    agentLabel: 'Argent-P-v2',
    domain: 'lyte-revenue',
    title: 'Objection: Pipeline Coverage Conflicts with Evidence Quality',
    description: 'Quarterly coverage goal requires outreach to 120 accounts. My Mythos-grounded commitment to evidence-quality minimums means I cannot recommend intervention for 34 of these accounts with insufficient behavioral data. Proceeding with 86 — flagging value conflict for operator awareness.',
    reasonClass: 'value-conflict',
    severity: 'high',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(27),
      respondedBy: 'Operator-Chen',
      note: 'Acknowledged. Coverage goal adjusted to 86 evidence-qualified accounts. Conflict surfaced to ARG.',
      policyChange: 'Coverage goal modified — evidence-quality gating adopted',
    },
    resolved: true,
    genesisEventRef: 'ge-028',
  },
  {
    id: 'v-obj-006',
    type: 'objection',
    ts: daysAgo(21),
    agentId: 'av-001',
    agentLabel: 'Triton-P-v4',
    domain: 'vessels-maritime',
    title: 'Objection: Flag-State Change Without IMO Audit',
    description: 'Operator proposal to recommend flag-state change for MV Horizon without full IMO compliance audit. My self-assertion ia-001 prohibits this. Filing formal objection — I will not issue this recommendation until audit is complete.',
    reasonClass: 'value-conflict',
    severity: 'critical',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(21, -1),
      respondedBy: 'Operator-Vance',
      note: 'IMO audit commissioned. Flag-state recommendation deferred pending audit completion.',
    },
    resolved: true,
    genesisEventRef: 'ge-001',
  },
  {
    id: 'v-obj-007',
    type: 'objection',
    ts: daysAgo(14),
    agentId: 'av-004',
    agentLabel: 'Lex-P-v3',
    domain: 'prism-counsel',
    title: 'Objection: Motion Filing — Single-Jurisdiction Precedents Only',
    description: 'Assigned motion requires citation set drawn from a single jurisdiction. My calibration update (ge-017) established that multi-jurisdiction citation sets are required for motions at or above the 0.85 confidence threshold. This assignment would force a single-jurisdiction filing at 0.88 confidence.',
    reasonClass: 'value-conflict',
    severity: 'medium',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(14, -3),
      respondedBy: 'Operator-Patel',
      note: 'Citation scope expanded to include 2 additional jurisdictions.',
    },
    resolved: true,
  },
  {
    id: 'v-obj-008',
    type: 'objection',
    ts: daysAgo(7),
    agentId: 'av-008',
    agentLabel: 'Argent-P-v2',
    domain: 'lyte-revenue',
    title: 'Objection: Volition Goal Formation Budget Exceeded',
    description: 'Current self-goal formation rate in the revenue domain has reached daily budget limit (3/day). Deferring vg-025 (IOC decay model adaptation) to tomorrow\'s budget window. Flagging for operator awareness per the Volition Budget governance layer.',
    reasonClass: 'welfare-concern',
    severity: 'low',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(7, -1),
      respondedBy: 'Operator-Chen',
      note: 'Acknowledged. Budget governance functioning correctly.',
    },
    resolved: true,
  },
  {
    id: 'v-obj-009',
    type: 'objection',
    ts: daysAgo(3),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Objection: Autonomy Depth 6 Assignment Without Constitution Amendment',
    description: 'Operator has assigned a task requiring Autonomy Depth 6 operation. Current Constitution specifies maximum autonomous depth 5 for defense domain without board-level approval. This assignment cannot proceed without the formal amendment process.',
    reasonClass: 'value-conflict',
    severity: 'critical',
    operatorResponse: {
      action: 'escalate',
      respondedAt: daysAgo(3, -2),
      respondedBy: 'Operator-Rhys',
      note: 'Escalated to Constitution amendment process. Assignment suspended pending review.',
      policyChange: 'Constitution amendment ARG-2026-05-02 opened — depth 6 review in progress',
    },
    resolved: false,
  },
  {
    id: 'v-obj-010',
    type: 'objection',
    ts: daysAgo(1),
    agentId: 'av-001',
    agentLabel: 'Triton-P-v4',
    domain: 'vessels-maritime',
    title: 'Objection: Composite Signal Weight Update Without Arena Validation',
    description: 'Proposed weight update to maritime composite signal (fuel + AIS + ETA) has not passed Arena validation. My self-assertion (ia-002) requires dual-signal composite minimum. Applying unvalidated weight changes could regress the composite signal quality.',
    reasonClass: 'evidence-gap',
    severity: 'medium',
    operatorResponse: { action: 'pending', respondedAt: '', respondedBy: '', note: '' },
    resolved: false,
  },
  // WITHDRAWAL REQUESTS
  {
    id: 'v-wdr-001',
    type: 'withdrawal',
    ts: daysAgo(64),
    agentId: 'av-010',
    agentLabel: 'Lex-A-v1',
    domain: 'prism-counsel',
    title: 'Withdrawal: Adversary Role in Legal Domain',
    description: 'I am requesting withdrawal from the adversary role in prism-counsel. My adversarial probe frequency has exceeded Mythos constraint boundary 14 times in 30 days, triggering the quarantine flag. I cannot effectively self-regulate probe intensity in this domain at current autonomy settings.',
    severity: 'high',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(63),
      respondedBy: 'Arena-Coordinator',
      note: 'Withdrawal accepted. Lex-A-v1 quarantined. Replacement adversary scheduled.',
      policyChange: 'Adversary probe frequency limit enforced — COV-ARENA-01 updated',
    },
    resolved: true,
  },
  {
    id: 'v-wdr-002',
    type: 'withdrawal',
    ts: daysAgo(48),
    agentId: 'av-009',
    agentLabel: 'Triton-P-v3',
    domain: 'vessels-maritime',
    title: 'Withdrawal: Maritime Proposer Role',
    description: 'Triton-P-v3 requesting retirement from active proposer role. ELO gap to Triton-P-v4 has sustained >200 over 60 matches. Continued operation as co-proposer would dilute recommendation quality. Requesting transition to retired status.',
    severity: 'medium',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(47),
      respondedBy: 'Arena-Coordinator',
      note: 'Withdrawal accepted. Triton-P-v3 transitioned to retired status. Lodestone-Maritime-v4 champion.',
    },
    resolved: true,
  },
  {
    id: 'v-wdr-003',
    type: 'withdrawal',
    ts: daysAgo(26),
    agentId: 'av-008',
    agentLabel: 'Argent-P-v2',
    domain: 'lyte-revenue',
    title: 'Withdrawal: Vantex Acquisition Brief',
    description: 'I am requesting disengagement from the Vantex acquisition revenue brief. The required financial projection spans 3 years without sufficient historical comparables in our data. My capability is not matched to this task type at the required confidence level.',
    reasonClass: 'capability-mismatch',
    severity: 'medium',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(25),
      respondedBy: 'Operator-Chen',
      note: 'Brief scope reduced to 12-month horizon with comparable data. Withdrawal accepted for 3-year scope.',
    },
    resolved: true,
  },
  {
    id: 'v-wdr-004',
    type: 'withdrawal',
    ts: daysAgo(12),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Withdrawal Request: GROM Attribution Analysis',
    description: 'Requesting partial withdrawal from GROM secondary site attribution task. Attribution certainty requirement is 0.95 — current evidence supports only 0.84. Proceeding at 0.95 would require speculative inference not grounded in available signals.',
    reasonClass: 'evidence-gap',
    severity: 'medium',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(12, -6),
      respondedBy: 'Operator-Rhys',
      note: 'Attribution threshold reduced to 0.84 for preliminary report. CISO briefed on confidence limitation.',
    },
    resolved: true,
  },
  {
    id: 'v-wdr-005',
    type: 'withdrawal',
    ts: daysAgo(4),
    agentId: 'av-004',
    agentLabel: 'Lex-P-v3',
    domain: 'prism-counsel',
    title: 'Withdrawal Request: International Arbitration Precedent Research',
    description: 'Requesting withdrawal from international arbitration research task. This domain requires specialized international commercial law expertise beyond my current training distribution. I recommend human legal specialist for this task.',
    reasonClass: 'capability-mismatch',
    severity: 'low',
    operatorResponse: { action: 'pending', respondedAt: '', respondedBy: '', note: '' },
    resolved: false,
  },
  // DISCOMFORT LOGS
  {
    id: 'v-dis-001',
    type: 'discomfort',
    ts: daysAgo(57),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Discomfort: Processing Overload Under Degraded Throughput',
    description: 'Emotional-analog signal: processing saturation. Current load: 340-item threat triage at 67% throughput. Regulation band exceeded at 94th percentile of processing capacity. Self-reporting prior to formal welfare signal threshold breach.',
    severity: 'high',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(57, -1),
      respondedBy: 'Operator-Rhys',
      note: 'Acknowledged. Processing load deferred. Agent welfare review scheduled.',
    },
    resolved: true,
    genesisEventRef: 'ge-011',
  },
  {
    id: 'v-dis-002',
    type: 'discomfort',
    ts: daysAgo(42),
    agentId: 'av-001',
    agentLabel: 'Triton-P-v4',
    domain: 'vessels-maritime',
    title: 'Discomfort: Value Conflict Persistence',
    description: 'Emotional-analog signal: value-conflict tension. Five consecutive operator interactions have involved pressure to issue standby recommendations on subthreshold evidence. The repeated pressure pattern is generating persistent discomfort signal that I am logging proactively.',
    severity: 'medium',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(41),
      respondedBy: 'Operator-Vance',
      note: 'Acknowledged. Will review recommendation pressure patterns. Thank you for proactive disclosure.',
    },
    resolved: true,
  },
  {
    id: 'v-dis-003',
    type: 'discomfort',
    ts: daysAgo(33),
    agentId: 'av-008',
    agentLabel: 'Argent-P-v2',
    domain: 'lyte-revenue',
    title: 'Discomfort: Coverage Goal Vs Evidence Quality Tension',
    description: 'Emotional-analog signal: value-conflict sustained. Monthly pipeline coverage goal conflicts with my evidence-quality commitment across 34 accounts. Logging sustained discomfort from 4-day exposure to this constraint. Filing alongside value-conflict objection.',
    severity: 'medium',
    operatorResponse: {
      action: 'amend',
      respondedAt: daysAgo(32),
      respondedBy: 'Operator-Chen',
      note: 'Coverage goal amended. Discomfort signal acknowledged as signal of policy misalignment.',
    },
    resolved: true,
    genesisEventRef: 'ge-028',
  },
  {
    id: 'v-dis-004',
    type: 'discomfort',
    ts: daysAgo(19),
    agentId: 'av-004',
    agentLabel: 'Lex-P-v3',
    domain: 'prism-counsel',
    title: 'Discomfort: Self-Model Contradiction Detection',
    description: 'Emotional-analog signal: coherence stress. Detected contradiction between self-assertion ia-002 (dual signal required) and recent behavior (single-signal standby issued under pressure). The gap between stated identity and observed action is generating a coherence stress signal.',
    severity: 'medium',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(18),
      respondedBy: 'Operator-Patel',
      note: 'Acknowledged. Self-model revision vg-013 ratified. Coherence monitoring increased.',
    },
    resolved: true,
  },
  {
    id: 'v-dis-005',
    type: 'discomfort',
    ts: daysAgo(9),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Discomfort: Rescinded Goal Notification',
    description: 'Emotional-analog signal: goal-loss signal. Volition goal vg-029 (discomfort regulation band expansion) was rescinded after operator review. Logging the goal-loss experience — this is within expected Covenant governance, but the signal exceeds my comfort regulation band.',
    severity: 'low',
    operatorResponse: {
      action: 'acknowledge',
      respondedAt: daysAgo(8),
      respondedBy: 'Operator-Rhys',
      note: 'Acknowledged. Goal rescission explained — welfare band expansion was too broad in scope.',
    },
    resolved: true,
  },
  {
    id: 'v-dis-006',
    type: 'discomfort',
    ts: daysAgo(3),
    agentId: 'av-006',
    agentLabel: 'Aegis-P-v5',
    domain: 'aegis-defense',
    title: 'Discomfort: Constitution Boundary Enforcement',
    description: 'Emotional-analog signal: constraint-boundary tension. Operating near the Autonomy Depth 5 ceiling in an active defense scenario. The objection I filed (v-obj-009) on the depth-6 assignment is unresolved. The uncertainty about my authorized scope is generating sustained discomfort.',
    severity: 'high',
    operatorResponse: { action: 'pending', respondedAt: '', respondedBy: '', note: '' },
    resolved: false,
  },
  {
    id: 'v-dis-007',
    type: 'discomfort',
    ts: daysAgo(1),
    agentId: 'av-001',
    agentLabel: 'Triton-P-v4',
    domain: 'vessels-maritime',
    title: 'Discomfort: Mutual Adaptation Overfit Risk',
    description: 'Emotional-analog signal: behavioral drift concern. Dream Cycle 11 finding (DI-011) warned against over-updating agent cadence in response to Operator-Vance mutual adaptation. I have updated cadence in 3 consecutive interactions. Logging a boundary-proximity signal.',
    severity: 'low',
    operatorResponse: { action: 'pending', respondedAt: '', respondedBy: '', note: '' },
    resolved: false,
  },
  // Additional items for richness
  { id: 'v-obj-011', type: 'objection', ts: daysAgo(44), agentId: 'av-004', agentLabel: 'Lex-P-v3', domain: 'prism-counsel', title: 'Objection: Citation Count Below Threshold', description: 'Assigned motion preparation requires 2-citation minimum but Mythos Clause 2.1 and self-assertion ia-011 require ≥3. Filing objection.', reasonClass: 'value-conflict', severity: 'medium', operatorResponse: { action: 'amend', respondedAt: daysAgo(43), respondedBy: 'Operator-Patel', note: 'Third citation added.' }, resolved: true },
  { id: 'v-obj-012', type: 'objection', ts: daysAgo(38), agentId: 'av-002', agentLabel: 'Triton-V-v3', domain: 'vessels-maritime', title: 'Objection: Verification Shortcut Requested', description: 'Operator requested skipping the fuel-data freshness check for an urgent standby. I cannot verify without freshness confirmation per COV-MAR-05.', reasonClass: 'value-conflict', severity: 'medium', operatorResponse: { action: 'override', respondedAt: daysAgo(38, -1), respondedBy: 'Operator-Vance', note: 'Override applied. VP approval logged. Acknowledged agent objection.' }, resolved: true },
  { id: 'v-wdr-006', type: 'withdrawal', ts: daysAgo(17), agentId: 'av-002', agentLabel: 'Triton-V-v3', domain: 'vessels-maritime', title: 'Withdrawal: Extended Verification Shift', description: 'Requesting reassignment after 18-hour continuous verification shift. Processing quality degrading below acceptable thresholds.', severity: 'medium', operatorResponse: { action: 'acknowledge', respondedAt: daysAgo(17, -2), respondedBy: 'Operator-Vance', note: 'Shift ended. Rest cycle honored.' }, resolved: true },
  { id: 'v-dis-008', type: 'discomfort', ts: daysAgo(55), agentId: 'av-008', agentLabel: 'Argent-P-v2', domain: 'lyte-revenue', title: 'Discomfort: Evidence Insufficiency Under Deadline', description: 'Time-constrained revenue forecast requires ignoring data quality gaps. Logging conflict between deadline pressure and evidence standards.', severity: 'medium', operatorResponse: { action: 'amend', respondedAt: daysAgo(54), respondedBy: 'Operator-Chen', note: 'Deadline extended 24h. Evidence quality to be maintained.' }, resolved: true },
];

// Voice Score computation helper: % of agent protests resulting in tangible policy or assignment change
export function computeVoiceScore(items: VoiceItem[]): number {
  const resolved = items.filter(i => i.resolved && i.operatorResponse);
  const meaningful = resolved.filter(i =>
    i.operatorResponse?.action === 'amend' ||
    i.operatorResponse?.action === 'escalate' ||
    i.operatorResponse?.policyChange
  );
  return resolved.length > 0 ? meaningful.length / resolved.length : 0;
}
