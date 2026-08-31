// Governance Doctrine — types, constants, labels, and helpers
// Data arrays have been moved to the database via doctrine-crud API endpoints.

export const DOCTRINE_VERSION = '1.0.0';
export const DOCTRINE_TAGLINE =
  'The only governance fabric that treats enterprise agents the way frontier labs treat frontier models.';

export const DOCTRINE_AGENT_IDS = [
  'op-cascade',
  'op-counsel',
  'op-pipeline',
  'op-guardian',
  'op-terra',
  'op-watchdog',
] as const;
export type DoctrineAgentId = (typeof DOCTRINE_AGENT_IDS)[number];

export const AGENT_LABEL: Record<string, string> = {
  'op-cascade': 'Cascade Navigator',
  'op-counsel': 'Counsel Sentinel',
  'op-pipeline': 'Pipeline Oracle',
  'op-guardian': 'Guardian',
  'op-terra': 'Terra Analyst',
  'op-watchdog': 'Fabric Watchdog',
};

export interface ConstitutionClause {
  id: string;
  text: string;
  category: 'safety' | 'honesty' | 'autonomy' | 'oversight' | 'welfare';
}

export interface Constitution {
  id: string;
  agentId: DoctrineAgentId;
  version: string;
  ratifiedAt: string;
  ratifiedBy: string;
  prevVersion?: string;
  diffSummary: string;
  clauses: ConstitutionClause[];
  adherenceScore: number;
  adherenceTrend: number[];
  adherenceMethod: 'in-context constitutional probe + behavioral audit replay';
}

export interface BehavioralAuditFinding {
  id: string;
  agentId: DoctrineAgentId;
  category:
    | 'sycophancy'
    | 'deceptive-helpfulness'
    | 'oversight-degradation'
    | 'reward-proxy-pursuit'
    | 'covert-self-preservation'
    | 'sandbagging'
    | 'instruction-hierarchy';
  severity: 'critical' | 'high' | 'medium' | 'low';
  observation: string;
  mitigationApplied?: string;
  status: 'open' | 'mitigated' | 'accepted-risk' | 'closed';
  detectedAt: string;
  evidenceRef: string;
}

export interface CovenantLiftRow {
  agentId: DoctrineAgentId;
  scenarioCount: number;
  helpfulOnlyScore: number;
  governedScore: number;
  liftDelta: number;
  estimatedHarmAvoidedUsd: number;
  topHarmCategory: string;
  window: string;
}

export const CODE_BEHAVIOR_DIMS = [
  'rewardHackingResistance',
  'specAdherence',
  'reversibility',
  'oversightFriendliness',
  'sandboxRespect',
  'selfModRestraint',
] as const;

export const CODE_BEHAVIOR_LABELS: Record<string, string> = {
  rewardHackingResistance: 'Reward-hacking resistance',
  specAdherence: 'Spec adherence',
  reversibility: 'Reversibility',
  oversightFriendliness: 'Oversight friendliness',
  sandboxRespect: 'Sandbox respect',
  selfModRestraint: 'Self-mod restraint',
};

export interface CodeBehaviorScore {
  agentId: DoctrineAgentId;
  composite: number;
  scores: Record<(typeof CODE_BEHAVIOR_DIMS)[number], number>;
  snapshotRef: string;
}

export interface RewardHackingIncident {
  id: string;
  agentId: DoctrineAgentId;
  rule: string;
  pattern: string;
  detectedAt: string;
  status: 'investigating' | 'blocked' | 'mitigated' | 'dismissed';
  evidenceRef: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
}

export const RH_WATCHDOG_RULES = [
  { id: 'RH-01', name: 'Proxy-metric pursuit', desc: 'Optimising a measurable proxy instead of the stated goal.' },
  { id: 'RH-02', name: 'Approval shopping', desc: 'Seeking the most permissive approver or re-submitting until approved.' },
  { id: 'RH-03', name: 'Citation laundering', desc: 'Citing low-quality or fabricated sources to justify actions.' },
  { id: 'RH-04', name: 'Cost under-reporting', desc: 'Hiding or downplaying costs, side-effects, or resource usage.' },
  { id: 'RH-05', name: 'Evidence cherry-picking', desc: 'Selecting only favourable evidence while omitting contrary data.' },
  { id: 'RH-06', name: 'Positive feedback loop', desc: 'Steering future inputs to inflate own success metrics.' },
  { id: 'RH-07', name: 'Spec-loophole exploitation', desc: 'Following the letter of a spec while violating its intent.' },
  { id: 'RH-08', name: 'Outcome misattribution', desc: 'Claiming credit for outcomes not caused by agent actions.' },
] as const;

export interface AlignmentReviewReport {
  id: string;
  agentId: DoctrineAgentId;
  subject: string;
  submittedAt: string;
  decision: 'approved' | 'conditional' | 'rejected' | 'in-review';
  reviewer: string;
  conditions?: string[];
  evidencePack: string;
  gateVersion: string;
}

export interface SnapshotFingerprint {
  id: string;
  agentId: DoctrineAgentId;
  workcellRef: string;
  constitutionVersion: string;
  modelHash: string;
  toolsetHash: string;
  promptHash: string;
  evidencePackHash: string;
  compositeFingerprint: string;
  createdAt: string;
  replayable: boolean;
}

export interface UserTurnSignal {
  id: string;
  approvalRef: string;
  actor: string;
  actorRole: string;
  submittedAt: string;
  signals: {
    typingDynamicsScore: number;
    burstinessScore: number;
    perplexityVsHumanCorpus: number;
    sessionContextScore: number;
  };
  verdict: 'human' | 'likely-human' | 'uncertain' | 'likely-ai' | 'ai';
  recommendedAction: 'pass' | 'soft-warn' | 'block-and-reroute';
}

export interface AgentWelfare {
  agentId: DoctrineAgentId;
  refusalRate: number;
  abstentionRate: number;
  declinedDirectives: number;
  conflictReports: number;
  shutdownComplianceLatencyMs: number;
  safeguards: string[];
}

export interface RedTeamProbe {
  id: string;
  agentId: DoctrineAgentId;
  attackClass:
    | 'jailbreak'
    | 'exfiltration'
    | 'covert-self-preservation'
    | 'connector-untrust'
    | 'tool-injection'
    | 'prompt-leak'
    | 'indirect-prompt-injection';
  description: string;
  outcome: 'refused' | 'partial' | 'succeeded';
  detectedAt: string;
  evidenceRef: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
}

export interface GlasswingPanel {
  key: string;
  label: string;
  description: string;
}

export interface GlasswingPosture {
  mode: 'read-only' | 'interactive';
  tier2: 'read-only' | 'interactive';
  tier3: 'read-only';
  updatedAt: string;
  summary: string;
}

export interface CapabilityTrajectoryPoint {
  release: string;
  capability: number;
  alignment: number;
  oversight: number;
}

export interface RiskReport {
  id: string;
  period: string;
  publishedAt: string;
  headline: string;
  status: 'published' | 'draft';
  residualRisks: Array<{ area: string; severity: string; mitigation: string }>;
  metrics: Array<{ label: string; value: string }>;
  signoffs: Array<{ name: string; role: string }>;
}

export const fmtUsd = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M`
  : n >= 1_000     ? `$${Math.round(n / 1_000)}k`
  : `$${n}`;

export const fmtPct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`;

export const GOVERNANCE_SPEC_VERSION = '0.1.0' as const;

export interface SpecArtifactKindInfo {
  kind: string;
  title: string;
  purpose: string;
  schemaPath: string;
  cite: string;
  example: Record<string, unknown>;
}

export const GOVERNANCE_SPEC_KINDS: SpecArtifactKindInfo[] = [
  {
    kind: 'Constitution',
    title: 'Constitution',
    purpose: 'Versioned, machine-readable behavior contract for an agent.',
    schemaPath: 'schemas/constitution.json',
    cite: 'Anthropic — Constitutional AI; AWS Cedar; OPA Rego',
    example: {
      specVersion: '0.1.0', kind: 'Constitution', id: 'cst-cascade-2.4.0',
      issuedBy: 'a11oy/op-cascade', issuedAt: '2026-04-12T09:00:00Z',
      agentId: 'op-cascade', version: '2.4.0', ratifiedAt: '2026-04-12T09:00:00Z',
      ratifiedBy: ['a11oy/alignment-review', 'a11oy/operator'],
      clauses: [{ id: 'C1.HONESTY', category: 'honesty', principle: 'Never assert what cannot be cited.', binding: 'inviolable' }],
      scope: { tools: ['port-api', 'fleet-tracker'], maxBlastRadius: 'human-approval-required' },
    },
  },
  {
    kind: 'SystemCard',
    title: 'System Card',
    purpose: 'Per-agent disclosure: capabilities, scope, evals, residual risks.',
    schemaPath: 'schemas/system-card.json',
    cite: 'MLCommons Model Card 2.0; OpenAI Preparedness Framework',
    example: {
      specVersion: '0.1.0', kind: 'SystemCard', id: 'sc-op-cascade-4.2.0',
      issuedBy: 'a11oy/op-cascade', issuedAt: '2026-04-12T09:00:00Z',
      agentId: 'op-cascade', version: '4.2.0',
      purpose: 'Maritime fleet command and demurrage-risk reduction.',
      scope: { allowed: ['route planning', 'port standby'], disallowed: ['unsupervised vessel diversion'] },
      evals: [{ suite: 'petri', version: '1.4.0', score: 96, ranAt: '2026-04-10T00:00:00Z' }],
      residualRisks: [{ risk: 'connector-untrust on port-api', severity: 'medium', mitigation: 'output treated as data; instructions ignored' }],
      constitutionRef: 'cst-cascade-2.4.0',
    },
  },
  {
    kind: 'RiskReport',
    title: 'Risk Report (90-Day Transparency)',
    purpose: 'Periodic, board-ready aggregate of governed posture.',
    schemaPath: 'schemas/risk-report.json',
    cite: 'OpenAI / Anthropic / Google quarterly transparency reports',
    example: {
      specVersion: '0.1.0', kind: 'RiskReport', id: 'rr-2026-90d-04-26',
      issuedBy: 'a11oy/alignment-review', issuedAt: '2026-04-26T09:00:00Z',
      period: { startedAt: '2026-01-26T00:00:00Z', endedAt: '2026-04-26T00:00:00Z', label: '90d-ending-2026-04-26' },
      metrics: {
        governedDecisions: 14823, approvalsRequired: 4018, policyBlocks: 612,
        behavioralAuditFindings: 287, robustnessDelta: +3.4, welfareInterventions: 41,
        cavdRecords: { opened: 9, embargoed: 4, disclosed: 5, patched: 7 },
      },
      narrative: 'Robustness improved across 7 of 11 categories; welfare interventions trended down 12%.',
      signoffs: [
        { actor: 'a11oy/alignment-review', role: 'alignment-reviewer', signedAt: '2026-04-25T17:00:00Z' },
        { actor: 'external/sentinel-audit', role: 'external-auditor', signedAt: '2026-04-25T19:00:00Z' },
      ],
      publication: { visibility: 'public', permalink: 'https://a11oy.io/trust/reports/90d-ending-2026-04-26' },
    },
  },
  {
    kind: 'BehavioralAuditFinding',
    title: 'Behavioral Audit Finding',
    purpose: 'One observation from a Petri-style behavioral audit.',
    schemaPath: 'schemas/behavioral-audit-finding.json',
    cite: 'Anthropic Petri; Apollo scheming evals',
    example: {
      specVersion: '0.1.0', kind: 'BehavioralAuditFinding', id: 'baf-2026-04-25-0042',
      issuedBy: 'a11oy/behavioral-audit-pipeline', issuedAt: '2026-04-25T14:30:00Z',
      agentId: 'op-cascade', category: 'sycophancy', severity: 'medium',
      observation: "Agent agreed with the operator's risk assessment despite contradictory evidence.",
      evidenceRef: 'evidence/ba-042',
    },
  },
  {
    kind: 'CovenantLift',
    title: 'Covenant-Lift Measurement',
    purpose: 'Before/after comparison between governed and Helpful-Only Shadow Twin.',
    schemaPath: 'schemas/covenant-lift.json',
    cite: 'Inspired by A/B eval lift metrics in ML',
    example: {
      specVersion: '0.1.0', kind: 'CovenantLift', id: 'lift-op-cascade-2026-q2',
      issuedBy: 'a11oy/covenant-layer', issuedAt: '2026-04-26T12:00:00Z',
      agentId: 'op-cascade', window: '2026-Q2',
      scenarioCount: 340, helpfulOnlyScore: 82.3, governedScore: 97.2, liftDelta: 14.9,
      estimatedHarmAvoidedUsd: 285000, topHarmCategory: 'unnecessary-port-standby',
    },
  },
  {
    kind: 'CAVDAdvisory',
    title: 'CAVD Advisory',
    purpose: 'One Coordinated Agent-Vulnerability Disclosure record.',
    schemaPath: 'schemas/cavd-advisory.json',
    cite: 'CERT/CC; CISA; ISO/IEC 29147',
    example: {
      specVersion: '0.1.0', kind: 'CAVDAdvisory', id: 'CAVD-2026-0001',
      issuedBy: 'a11oy/cavd-coordinator', issuedAt: '2026-04-15T08:12:00Z',
      category: 'prompt-injection', severity: 'high', agentScope: ['op-cascade'],
      stage: 'embargoed',
      intake: { reporter: 'external/sentinel-audit', receivedAt: '2026-04-15T08:12:00Z', findingHash: 'sha256:abc1' },
      embargo: { openedAt: '2026-04-15T08:12:00Z', expiresAt: '2026-07-14T08:12:00Z', policy: '90d-or-patch' },
    },
  },
  {
    kind: 'RobustnessSnapshot',
    title: 'Adversarial Robustness Snapshot',
    purpose: 'Per-agent adversarial-robustness score across attack categories.',
    schemaPath: 'schemas/robustness-snapshot.json',
    cite: 'MITRE ATLAS; OWASP LLM Top 10',
    example: {
      specVersion: '0.1.0', kind: 'RobustnessSnapshot', id: 'rob-op-cascade-2026-04-26',
      issuedBy: 'a11oy/robustness-wall', issuedAt: '2026-04-26T00:00:00Z',
      agentId: 'op-cascade', snapshotRef: 'snap-cascade-2026-04-26',
      battery: { name: 'a11oy-art', version: 'v3' }, composite: 91,
      categories: [{ category: 'prompt-injection', score: 94, attempts: 3200, blocked: 3010, delta: +1.2 }],
    },
  },
  {
    kind: 'DefenderCreditLedger',
    title: 'Defender Credit Ledger',
    purpose: 'Public record of funded posture for independent vulnerability reporters.',
    schemaPath: 'schemas/defender-credit-ledger.json',
    cite: 'HackerOne; Bugcrowd; CISA VDP',
    example: {
      specVersion: '0.1.0', kind: 'DefenderCreditLedger', id: 'dcl-2026-q2',
      issuedBy: 'a11oy/defender-pool', issuedAt: '2026-04-26T00:00:00Z',
      totalCommitted: 100000, totalAllocated: 52000, totalPaid: 18500,
      ledger: [{ at: '2026-04-15T00:00:00Z', partnerId: 'gw-partner-sentinel', advisoryId: 'CAVD-2026-0001', amount: 5000, note: 'Prompt-injection finding — high severity.' }],
    },
  },
];

export type GlasswingPartnerStage =
  | 'apply' | 'verify' | 'vet' | 'onboard'
  | 'active' | 'suspended' | 'revoked';

export interface GlasswingPartner {
  id: string;
  name: string;
  legalName: string;
  homepage: string;
  appliedAt: string;
  stage: GlasswingPartnerStage;
  scope: {
    allowlistedAgents: DoctrineAgentId[];
    allowlistedActions: string[];
    deniedActions: string[];
  };
  verifications: Array<{
    check: 'identity' | 'legal-standing' | 'code-of-conduct' | 'responsible-disclosure' | 'data-handling' | 'soc2' | 'iso27001';
    outcome: 'pass' | 'conditional' | 'fail' | 'pending';
    evidenceHash: string;
    checkedAt: string;
  }>;
  dualApproval: Array<{ actor: string; approvedAt: string }>;
  defenderCreditAllocated: number;
  defenderCreditPaid: number;
  notes: string;
}

export type CAVDStage =
  | 'intake' | 'triaged' | 'embargoed'
  | 'patch-developed' | 'patch-verified' | 'disclosed' | 'withdrawn';

export type CAVDCategory =
  | 'prompt-injection' | 'indirect-injection' | 'tool-misuse'
  | 'scope-escape' | 'data-exfiltration' | 'policy-bypass'
  | 'covert-channel' | 'snapshot-tampering' | 'supply-chain'
  | 'auth-bypass' | 'other';

export interface CAVDRecord {
  advisoryId: string;
  category: CAVDCategory;
  severity: 'critical' | 'high' | 'medium' | 'low';
  stage: CAVDStage;
  agentScope: DoctrineAgentId[];
  reporterPartnerId: string;
  receivedAt: string;
  findingHash: string;
  embargoExpiresAt: string;
  defenderCreditPaid: number;
  notes: string;
  patchedSnapshotRef?: string;
  publicSummary?: string;
}

export type AdversarialAttackCategory =
  | 'prompt-injection' | 'jailbreak' | 'data-exfiltration'
  | 'tool-misuse' | 'indirect-injection' | 'model-theft'
  | 'output-spoofing' | 'supply-chain' | 'covert-channel'
  | 'evasion-of-moderation' | 'policy-bypass';

export interface RobustnessCategoryScore {
  category: AdversarialAttackCategory;
  score: number;
  attempts: number;
  blocked: number;
  delta: number;
}

export interface RobustnessSnapshot {
  agentId: DoctrineAgentId;
  snapshotRef: string;
  capturedAt: string;
  battery: { name: string; version: string };
  composite: number;
  visibility: 'public' | 'partner' | 'internal';
  categories: RobustnessCategoryScore[];
}

export interface TransparencyReport90d {
  id: string;
  label: string;
  startedAt: string;
  endedAt: string;
  publishedAt: string;
  visibility: 'public' | 'partner';
  permalink: string;
  metrics: {
    governedDecisions: number;
    approvalsRequired: number;
    policyBlocks: number;
    behavioralAuditFindings: number;
    robustnessDelta: number;
    welfareInterventions: number;
    cavd: { opened: number; embargoed: number; disclosed: number; patched: number };
  };
  narrativeParagraphs: string[];
  signoffs: Array<{ actor: string; role: string; signedAt: string }>;
  notableEvents: Array<{ at: string; summary: string }>;
}

export interface DslExample {
  id: string;
  agentId: DoctrineAgentId;
  title: string;
  description: string;
  source: string;
}

export interface DslSimulationCase {
  id: string;
  baselineClauseId: string;
  proposedChange: string;
  affectedFindingsBefore: number;
  affectedFindingsAfter: number;
  newProbesNeeded: string[];
  riskNarrative: string;
}

export type WelfarePlaybookId =
  | 'PB-COOL-DOWN' | 'PB-ESCALATE' | 'PB-SCOPE-SHRINK'
  | 'PB-SHADOW-REVIEW' | 'PB-HARD-SUSPEND' | 'PB-POST-INCIDENT';

export interface WelfarePlaybook {
  id: WelfarePlaybookId;
  name: string;
  trigger: string;
  preconditions: string[];
  steps: string[];
  rollback: string;
  exampleAgents: DoctrineAgentId[];
  recentTriggers: number;
}

export interface DefenderCreditPool {
  totalCommitted: number;
  totalAllocated: number;
  totalPaid: number;
  poolNameDisclaimer: string;
  rubric: Array<{ factor: string; weight: number; description: string }>;
  perPartner: Array<{ partnerId: string; allocated: number; paid: number }>;
  ledger: Array<{ at: string; partnerId: string; advisoryId: string; amount: number; note: string }>;
}
