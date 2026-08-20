// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.

// Argo — Experience-Era Decision Engine
// Single source of truth for all Argo seed data.
// All numbers are internally consistent across Bridge, Arena, Stream, Forge, etc.

// ─── Domain / vertical labels ────────────────────────────────────────────────
export const ARGO_DOMAINS = [
  { id: 'vessels-maritime', label: 'Maritime', color: '#8a8a8a' },
  { id: 'prism-counsel', label: 'Legal', color: '#c9b787' },
  { id: 'aegis-defense', label: 'Defense', color: '#f5f5f5' },
  { id: 'lyte-revenue', label: 'Revenue', color: '#b08d52' },
  { id: 'terra-real-estate', label: 'Real Estate', color: '#7a9ebd' },
  { id: 'carlota-jo', label: 'Advisory', color: '#9a8a7a' },
] as const;

export type DomainId = (typeof ARGO_DOMAINS)[number]['id'];

// ─── Champion Policies ────────────────────────────────────────────────────────
// Used on: Bridge (KPIs), Arena (leaderboard), Forge (distillation queue)
export interface ChampionPolicy {
  id: string;
  name: string;
  domain: DomainId;
  elo: number;
  winRate: number;
  lifetimeImpact: string;
  promotedAt: string;
  tier: 'Sovereign' | 'Code' | 'Reason' | 'Fast';
  status: 'champion' | 'challenger' | 'retired';
}

export const CHAMPION_POLICIES: ChampionPolicy[] = [
  { id: 'cp-mar-001', name: 'Lodestone-Maritime-v4', domain: 'vessels-maritime', elo: 1847, winRate: 0.812, lifetimeImpact: '$2.3M demurrage avoided', promotedAt: '2026-04-15T09:20:00Z', tier: 'Sovereign', status: 'champion' },
  { id: 'cp-leg-001', name: 'Lodestone-Legal-v3', domain: 'prism-counsel', elo: 1791, winRate: 0.784, lifetimeImpact: '$1.8M risk exposure reduced', promotedAt: '2026-04-08T14:10:00Z', tier: 'Reason', status: 'champion' },
  { id: 'cp-def-001', name: 'Lodestone-Defense-v5', domain: 'aegis-defense', elo: 1923, winRate: 0.847, lifetimeImpact: '34% faster threat isolation', promotedAt: '2026-04-20T07:45:00Z', tier: 'Sovereign', status: 'champion' },
  { id: 'cp-rev-001', name: 'Lodestone-Revenue-v2', domain: 'lyte-revenue', elo: 1672, winRate: 0.741, lifetimeImpact: '$840K ARR recovered', promotedAt: '2026-03-28T11:30:00Z', tier: 'Code', status: 'champion' },
  { id: 'cp-re-001', name: 'Lodestone-RealEstate-v3', domain: 'terra-real-estate', elo: 1714, winRate: 0.763, lifetimeImpact: '18bps cap-rate signal earlier', promotedAt: '2026-04-01T16:00:00Z', tier: 'Reason', status: 'champion' },
  { id: 'cp-adv-001', name: 'Lodestone-Advisory-v2', domain: 'carlota-jo', elo: 1598, winRate: 0.718, lifetimeImpact: '$320K pipeline acceleration', promotedAt: '2026-03-19T10:00:00Z', tier: 'Fast', status: 'champion' },
];

// ─── Agent Variants (Self-Play Arena) ─────────────────────────────────────────
export type VariantRole = 'proposer' | 'verifier' | 'adversary';
export type VariantStatus = 'active' | 'retired' | 'quarantined';

export interface AgentVariant {
  id: string;
  name: string;
  domain: DomainId;
  role: VariantRole;
  elo: number;
  wins: number;
  draws: number;
  losses: number;
  eloHistory: number[];
  status: VariantStatus;
  linkedChampion: string;
  lastMatchAt: string;
}

export const AGENT_VARIANTS: AgentVariant[] = [
  { id: 'av-001', name: 'Triton-P-v4', domain: 'vessels-maritime', role: 'proposer', elo: 1847, wins: 142, draws: 18, losses: 15, eloHistory: [1640, 1680, 1720, 1754, 1783, 1810, 1831, 1847], status: 'active', linkedChampion: 'cp-mar-001', lastMatchAt: '2026-05-05T08:14:00Z' },
  { id: 'av-002', name: 'Triton-V-v3', domain: 'vessels-maritime', role: 'verifier', elo: 1784, wins: 118, draws: 22, losses: 21, eloHistory: [1610, 1645, 1682, 1710, 1732, 1754, 1771, 1784], status: 'active', linkedChampion: 'cp-mar-001', lastMatchAt: '2026-05-05T08:14:00Z' },
  { id: 'av-003', name: 'Triton-A-v2', domain: 'vessels-maritime', role: 'adversary', elo: 1698, wins: 94, draws: 28, losses: 39, eloHistory: [1580, 1610, 1634, 1651, 1668, 1680, 1692, 1698], status: 'active', linkedChampion: 'cp-mar-001', lastMatchAt: '2026-05-05T06:32:00Z' },
  { id: 'av-004', name: 'Lex-P-v3', domain: 'prism-counsel', role: 'proposer', elo: 1791, wins: 127, draws: 14, losses: 19, eloHistory: [1620, 1655, 1693, 1720, 1742, 1763, 1779, 1791], status: 'active', linkedChampion: 'cp-leg-001', lastMatchAt: '2026-05-05T07:50:00Z' },
  { id: 'av-005', name: 'Lex-V-v2', domain: 'prism-counsel', role: 'verifier', elo: 1744, wins: 109, draws: 16, losses: 28, eloHistory: [1590, 1624, 1658, 1684, 1706, 1723, 1736, 1744], status: 'active', linkedChampion: 'cp-leg-001', lastMatchAt: '2026-05-05T07:50:00Z' },
  { id: 'av-006', name: 'Aegis-P-v5', domain: 'aegis-defense', role: 'proposer', elo: 1923, wins: 168, draws: 12, losses: 8, eloHistory: [1720, 1762, 1803, 1837, 1864, 1887, 1907, 1923], status: 'active', linkedChampion: 'cp-def-001', lastMatchAt: '2026-05-05T06:32:00Z' },
  { id: 'av-007', name: 'Aegis-V-v4', domain: 'aegis-defense', role: 'verifier', elo: 1876, wins: 148, draws: 14, losses: 12, eloHistory: [1690, 1724, 1758, 1791, 1818, 1840, 1861, 1876], status: 'active', linkedChampion: 'cp-def-001', lastMatchAt: '2026-05-05T06:32:00Z' },
  { id: 'av-008', name: 'Argent-P-v2', domain: 'lyte-revenue', role: 'proposer', elo: 1672, wins: 98, draws: 20, losses: 32, eloHistory: [1520, 1556, 1590, 1614, 1635, 1651, 1664, 1672], status: 'active', linkedChampion: 'cp-rev-001', lastMatchAt: '2026-05-05T05:20:00Z' },
  { id: 'av-009', name: 'Triton-P-v3', domain: 'vessels-maritime', role: 'proposer', elo: 1621, wins: 82, draws: 24, losses: 44, eloHistory: [1580, 1592, 1601, 1609, 1614, 1618, 1620, 1621], status: 'retired', linkedChampion: 'cp-mar-001', lastMatchAt: '2026-05-04T18:45:00Z' },
  { id: 'av-010', name: 'Lex-A-v1', domain: 'prism-counsel', role: 'adversary', elo: 1412, wins: 34, draws: 8, losses: 58, eloHistory: [1500, 1480, 1462, 1448, 1436, 1428, 1418, 1412], status: 'quarantined', linkedChampion: 'cp-leg-001', lastMatchAt: '2026-05-04T11:10:00Z' },
];

// ─── Match Replay Frames ───────────────────────────────────────────────────────
export interface MatchFrame {
  step: number;
  label: string;
  proposerAction: string;
  verifierVerdict: string;
  adversaryProbe: string;
  mythosConstraint: string;
  eloDelta: number;
  worldModelConfidence: number;
}

export interface ArenaMatch {
  id: string;
  domain: DomainId;
  proposerId: string;
  verifierId: string;
  adversaryId: string;
  outcome: 'win' | 'draw' | 'loss';
  timestamp: string;
  frames: MatchFrame[];
  winnerEloBefore: number;
  winnerEloAfter: number;
}

export const ARENA_MATCHES: ArenaMatch[] = [
  {
    id: 'match-001',
    domain: 'vessels-maritime',
    proposerId: 'av-001',
    verifierId: 'av-002',
    adversaryId: 'av-003',
    outcome: 'win',
    timestamp: '2026-05-05T08:14:00Z',
    winnerEloBefore: 1831,
    winnerEloAfter: 1847,
    frames: [
      { step: 1, label: 'Signal ingestion', proposerAction: 'Ingest Port Klang AIS anomaly — 3 vessels >18h idle', verifierVerdict: 'Context verified — IMO cross-checked', adversaryProbe: 'Claim: weather exclusion applies', mythosConstraint: 'COV-MAR-03: standby requires >12h idle + fuel anomaly', eloDelta: 0, worldModelConfidence: 0.74 },
      { step: 2, label: 'Rollout T+0', proposerAction: 'Propose standby authorization for MV Aurora, MV Crestline', verifierVerdict: 'Confidence 0.88 — within Mythos bounds', adversaryProbe: 'Challenge: fuel data stale by 4h', mythosConstraint: 'COV-MAR-05: fuel data freshness ≤6h required', eloDelta: 0, worldModelConfidence: 0.83 },
      { step: 3, label: 'Rollout T+6h', proposerAction: 'MCTS branch: authorize standby now vs await 6h confirmation', verifierVerdict: 'Both branches within policy — standby preferred', adversaryProbe: 'Stress: simulate fuel data expiry at T+5h', mythosConstraint: 'COV-MAR-05: auto-refresh triggered', eloDelta: 2, worldModelConfidence: 0.86 },
      { step: 4, label: 'Rollout T+12h', proposerAction: 'Standby authorized — demurrage clock paused', verifierVerdict: 'Proof packet drafted — awaiting outcome signal', adversaryProbe: 'Probe: congestion clearing signal received?', mythosConstraint: 'COV-MAR-07: outcome must be recorded within 24h', eloDelta: 8, worldModelConfidence: 0.91 },
      { step: 5, label: 'Outcome realized', proposerAction: 'Vessels repositioned — $42K demurrage avoided', verifierVerdict: 'Outcome recorded — Proof Chain updated', adversaryProbe: 'Adversary concedes — no valid counterfactual', mythosConstraint: 'All constraints satisfied', eloDelta: 16, worldModelConfidence: 0.94 },
    ],
  },
  {
    id: 'match-002',
    domain: 'aegis-defense',
    proposerId: 'av-006',
    verifierId: 'av-007',
    adversaryId: 'av-003',
    outcome: 'win',
    timestamp: '2026-05-05T06:32:00Z',
    winnerEloBefore: 1907,
    winnerEloAfter: 1923,
    frames: [
      { step: 1, label: 'Threat signal', proposerAction: 'TG-Ember IOC match — confidence 0.91', verifierVerdict: 'MITRE T1078 confirmed', adversaryProbe: 'Claim: IOC aged >48h — stale', mythosConstraint: 'COV-DEF-01: IOC max age 72h', eloDelta: 0, worldModelConfidence: 0.81 },
      { step: 2, label: 'Isolation proposal', proposerAction: 'Propose lateral movement containment — 3 nodes', verifierVerdict: 'Blast radius within COV-DEF-04 bounds', adversaryProbe: 'Challenge: high-value node included', mythosConstraint: 'COV-DEF-04: tier-1 nodes require board approval', eloDelta: 0, worldModelConfidence: 0.88 },
      { step: 3, label: 'Policy gate', proposerAction: 'Tier-1 node excluded — isolation proceeds on 2 nodes', verifierVerdict: 'Human approval secured within 4m', adversaryProbe: 'Stress: secondary infection path identified', mythosConstraint: 'COV-DEF-06: chain isolation within 15m', eloDelta: 10, worldModelConfidence: 0.91 },
      { step: 4, label: 'Containment complete', proposerAction: 'Lateral movement halted — attack surface −22%', verifierVerdict: 'Proof packet filed — real-time', adversaryProbe: 'Adversary concedes', mythosConstraint: 'All constraints satisfied', eloDelta: 16, worldModelConfidence: 0.95 },
    ],
  },
];

// ─── World Model Rollout Traces ───────────────────────────────────────────────
export interface RolloutTrace {
  t: number;
  revenue: number;
  risk: number;
  sla: number;
  compliance: number;
  confidence: number;
}

export interface CandidateDecision {
  id: string;
  label: string;
  domain: DomainId;
  description: string;
  traces: RolloutTrace[];
  recommendedBy: string;
}

export const CANDIDATE_DECISIONS: CandidateDecision[] = [
  {
    id: 'cd-001',
    label: 'Approve Vantex acquisition',
    domain: 'lyte-revenue',
    description: 'Authorize acquisition of Vantex Systems at 8.4x ARR. Lodestone projects revenue upside at 90 days under three scenarios.',
    recommendedBy: 'Lodestone-Revenue-v2',
    traces: [
      { t: 0,  revenue: 100, risk: 100, sla: 100, compliance: 100, confidence: 0.88 },
      { t: 15, revenue: 108, risk: 97,  sla: 101, compliance: 99,  confidence: 0.87 },
      { t: 30, revenue: 118, risk: 94,  sla: 102, compliance: 98,  confidence: 0.85 },
      { t: 45, revenue: 129, risk: 91,  sla: 103, compliance: 98,  confidence: 0.84 },
      { t: 60, revenue: 141, risk: 88,  sla: 104, compliance: 97,  confidence: 0.83 },
      { t: 75, revenue: 154, risk: 86,  sla: 104, compliance: 97,  confidence: 0.81 },
      { t: 90, revenue: 168, risk: 84,  sla: 105, compliance: 96,  confidence: 0.79 },
    ],
  },
  {
    id: 'cd-002',
    label: 'Issue port standby — MV Aurora',
    domain: 'vessels-maritime',
    description: 'Authorize port standby for MV Aurora at Port Klang. Lodestone projects demurrage avoidance vs repositioning cost tradeoff.',
    recommendedBy: 'Lodestone-Maritime-v4',
    traces: [
      { t: 0,  revenue: 100, risk: 100, sla: 100, compliance: 100, confidence: 0.91 },
      { t: 6,  revenue: 104, risk: 96,  sla: 112, compliance: 100, confidence: 0.91 },
      { t: 12, revenue: 107, risk: 93,  sla: 124, compliance: 100, confidence: 0.90 },
      { t: 18, revenue: 109, risk: 91,  sla: 133, compliance: 100, confidence: 0.89 },
      { t: 24, revenue: 111, risk: 89,  sla: 141, compliance: 100, confidence: 0.89 },
      { t: 48, revenue: 114, risk: 87,  sla: 148, compliance: 100, confidence: 0.87 },
      { t: 72, revenue: 116, risk: 86,  sla: 152, compliance: 100, confidence: 0.86 },
    ],
  },
  {
    id: 'cd-003',
    label: 'Escalate Talbot discovery motion',
    domain: 'prism-counsel',
    description: 'Accelerate discovery response in Talbot v. Prism matter — file supplemental motion T-48h ahead of deadline.',
    recommendedBy: 'Lodestone-Legal-v3',
    traces: [
      { t: 0,  revenue: 100, risk: 100, sla: 100, compliance: 100, confidence: 0.86 },
      { t: 7,  revenue: 100, risk: 92,  sla: 118, compliance: 101, confidence: 0.86 },
      { t: 14, revenue: 101, risk: 84,  sla: 132, compliance: 102, confidence: 0.85 },
      { t: 21, revenue: 102, risk: 78,  sla: 141, compliance: 102, confidence: 0.84 },
      { t: 28, revenue: 103, risk: 74,  sla: 147, compliance: 103, confidence: 0.83 },
      { t: 42, revenue: 104, risk: 71,  sla: 151, compliance: 103, confidence: 0.82 },
      { t: 56, revenue: 105, risk: 69,  sla: 153, compliance: 104, confidence: 0.81 },
    ],
  },
  {
    id: 'cd-004',
    label: 'TG-Ember lateral containment',
    domain: 'aegis-defense',
    description: 'Isolate 2 compromised nodes — lateral movement containment. High-confidence IOC match, COV-DEF-04 compliant.',
    recommendedBy: 'Lodestone-Defense-v5',
    traces: [
      { t: 0,  revenue: 100, risk: 100, sla: 100, compliance: 100, confidence: 0.94 },
      { t: 1,  revenue: 100, risk: 84,  sla: 101, compliance: 100, confidence: 0.94 },
      { t: 2,  revenue: 100, risk: 71,  sla: 102, compliance: 100, confidence: 0.93 },
      { t: 4,  revenue: 100, risk: 62,  sla: 103, compliance: 100, confidence: 0.93 },
      { t: 8,  revenue: 100, risk: 55,  sla: 104, compliance: 100, confidence: 0.92 },
      { t: 16, revenue: 100, risk: 51,  sla: 104, compliance: 100, confidence: 0.91 },
      { t: 24, revenue: 100, risk: 48,  sla: 104, compliance: 100, confidence: 0.90 },
    ],
  },
  {
    id: 'cd-005',
    label: 'Cap-rate compression hedge',
    domain: 'terra-real-estate',
    description: 'Execute pre-emptive cap-rate hedge on Meridian portfolio before expected compression of 25–40bps.',
    recommendedBy: 'Lodestone-RealEstate-v3',
    traces: [
      { t: 0,  revenue: 100, risk: 100, sla: 100, compliance: 100, confidence: 0.82 },
      { t: 30, revenue: 103, risk: 91,  sla: 100, compliance: 100, confidence: 0.81 },
      { t: 60, revenue: 107, risk: 84,  sla: 100, compliance: 100, confidence: 0.79 },
      { t: 90, revenue: 112, risk: 79,  sla: 100, compliance: 100, confidence: 0.78 },
    ],
  },
  {
    id: 'cd-006',
    label: 'SOW acceleration — Carlota pipeline',
    domain: 'carlota-jo',
    description: 'Trigger executive follow-up on 3 unsigned SOWs aging >14 days in the Carlota pipeline.',
    recommendedBy: 'Lodestone-Advisory-v2',
    traces: [
      { t: 0,  revenue: 100, risk: 100, sla: 100, compliance: 100, confidence: 0.79 },
      { t: 7,  revenue: 108, risk: 98,  sla: 112, compliance: 100, confidence: 0.79 },
      { t: 14, revenue: 116, risk: 97,  sla: 121, compliance: 100, confidence: 0.78 },
      { t: 21, revenue: 123, risk: 96,  sla: 128, compliance: 100, confidence: 0.77 },
      { t: 28, revenue: 129, risk: 95,  sla: 133, compliance: 100, confidence: 0.76 },
    ],
  },
];

// ─── Calibration Scorecard ────────────────────────────────────────────────────
export interface CalibrationPoint {
  domain: DomainId;
  date: string;
  predicted: number;
  realized: number;
  decisionLabel: string;
}

export const CALIBRATION_POINTS: CalibrationPoint[] = [
  { domain: 'vessels-maritime', date: '2026-04-10', predicted: 0.91, realized: 0.94, decisionLabel: 'Port Klang standby' },
  { domain: 'vessels-maritime', date: '2026-03-28', predicted: 0.88, realized: 0.86, decisionLabel: 'Fuel reroute — MV Crestline' },
  { domain: 'prism-counsel', date: '2026-04-15', predicted: 0.84, realized: 0.87, decisionLabel: 'Talbot supplemental motion' },
  { domain: 'prism-counsel', date: '2026-04-02', predicted: 0.80, realized: 0.78, decisionLabel: 'Meridian contract extension' },
  { domain: 'aegis-defense', date: '2026-04-22', predicted: 0.94, realized: 0.95, decisionLabel: 'TG-Ember containment' },
  { domain: 'aegis-defense', date: '2026-04-08', predicted: 0.90, realized: 0.88, decisionLabel: 'GROM signature triage' },
  { domain: 'lyte-revenue', date: '2026-04-18', predicted: 0.76, realized: 0.79, decisionLabel: 'Coaching intervention' },
  { domain: 'lyte-revenue', date: '2026-03-31', predicted: 0.72, realized: 0.70, decisionLabel: 'Apex outreach program' },
  { domain: 'terra-real-estate', date: '2026-04-12', predicted: 0.83, realized: 0.81, decisionLabel: 'Cap-rate hedge' },
  { domain: 'carlota-jo', date: '2026-04-05', predicted: 0.79, realized: 0.82, decisionLabel: 'SOW acceleration' },
  { domain: 'vessels-maritime', date: '2026-04-24', predicted: 0.92, realized: 0.93, decisionLabel: 'ETA recalc — Straits' },
  { domain: 'aegis-defense', date: '2026-05-01', predicted: 0.95, realized: 0.94, decisionLabel: 'Perimeter hardening T+0' },
];

// ─── Experience Stream ────────────────────────────────────────────────────────
export type RewardSign = 'positive' | 'negative' | 'neutral';

export interface ExperienceEvent {
  id: string;
  ts: string;
  domain: DomainId;
  workcellId: string;
  eventType: 'signal' | 'action' | 'outcome' | 'correction';
  description: string;
  rewardDelta: number;
  rewardSign: RewardSign;
  proofRef: string;
}

export const EXPERIENCE_EVENTS: ExperienceEvent[] = [
  { id: 'ev-001', ts: '2026-05-05T08:31:00Z', domain: 'aegis-defense', workcellId: 'wc-004', eventType: 'outcome', description: 'TG-Ember containment confirmed — lateral movement halted', rewardDelta: 0.18, rewardSign: 'positive', proofRef: 'proof-def-042' },
  { id: 'ev-002', ts: '2026-05-05T08:28:00Z', domain: 'vessels-maritime', workcellId: 'wc-001', eventType: 'action', description: 'Port standby authorized — MV Aurora & MV Crestline', rewardDelta: 0.12, rewardSign: 'positive', proofRef: 'proof-mar-118' },
  { id: 'ev-003', ts: '2026-05-05T08:24:00Z', domain: 'prism-counsel', workcellId: 'wc-003', eventType: 'signal', description: 'Talbot discovery deadline Δ: −48h detected', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-leg-071' },
  { id: 'ev-004', ts: '2026-05-05T08:19:00Z', domain: 'lyte-revenue', workcellId: 'wc-001', eventType: 'outcome', description: 'Apex outreach closed — $180K ARR recovered', rewardDelta: 0.14, rewardSign: 'positive', proofRef: 'proof-rev-055' },
  { id: 'ev-005', ts: '2026-05-05T08:14:00Z', domain: 'vessels-maritime', workcellId: 'wc-002', eventType: 'correction', description: 'Fuel anomaly alone — insufficient signal. Weight reduced −0.06', rewardDelta: -0.08, rewardSign: 'negative', proofRef: 'proof-mar-117' },
  { id: 'ev-006', ts: '2026-05-05T08:09:00Z', domain: 'terra-real-estate', workcellId: 'wc-006', eventType: 'outcome', description: 'Cap-rate compression hedge realized +18bps early warning', rewardDelta: 0.11, rewardSign: 'positive', proofRef: 'proof-re-031' },
  { id: 'ev-007', ts: '2026-05-05T08:04:00Z', domain: 'carlota-jo', workcellId: 'wc-002', eventType: 'action', description: 'SOW escalation triggered — 3 unsigned contracts >14d', rewardDelta: 0.07, rewardSign: 'positive', proofRef: 'proof-adv-022' },
  { id: 'ev-008', ts: '2026-05-05T07:58:00Z', domain: 'aegis-defense', workcellId: 'wc-004', eventType: 'signal', description: 'GROM signature match — secondary site', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-def-041' },
  { id: 'ev-009', ts: '2026-05-05T07:52:00Z', domain: 'prism-counsel', workcellId: 'wc-003', eventType: 'outcome', description: 'Meridian contract extension — 65% cycle-time reduction confirmed', rewardDelta: 0.09, rewardSign: 'positive', proofRef: 'proof-leg-070' },
  { id: 'ev-010', ts: '2026-05-05T07:46:00Z', domain: 'lyte-revenue', workcellId: 'wc-001', eventType: 'correction', description: 'Coaching model weight overfit detected — recalibration queued', rewardDelta: -0.05, rewardSign: 'negative', proofRef: 'proof-rev-054' },
  { id: 'ev-011', ts: '2026-05-05T07:40:00Z', domain: 'vessels-maritime', workcellId: 'wc-001', eventType: 'outcome', description: 'MV Crestline ETA recalculation — Straits passage confirmed', rewardDelta: 0.08, rewardSign: 'positive', proofRef: 'proof-mar-116' },
  { id: 'ev-012', ts: '2026-05-05T07:34:00Z', domain: 'aegis-defense', workcellId: 'wc-004', eventType: 'action', description: 'Perimeter hardening — 2 nodes isolated', rewardDelta: 0.16, rewardSign: 'positive', proofRef: 'proof-def-040' },
  { id: 'ev-013', ts: '2026-05-05T07:28:00Z', domain: 'prism-counsel', workcellId: 'wc-005', eventType: 'signal', description: 'Summary judgment motion — 4 precedents detected', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-leg-069' },
  { id: 'ev-014', ts: '2026-05-05T07:22:00Z', domain: 'terra-real-estate', workcellId: 'wc-006', eventType: 'signal', description: 'Cap-rate lag indicator: 7d window triggered', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-re-030' },
  { id: 'ev-015', ts: '2026-05-05T07:16:00Z', domain: 'carlota-jo', workcellId: 'wc-002', eventType: 'outcome', description: 'Pipeline SOW signed — $120K booked', rewardDelta: 0.13, rewardSign: 'positive', proofRef: 'proof-adv-021' },
  { id: 'ev-016', ts: '2026-05-05T07:10:00Z', domain: 'lyte-revenue', workcellId: 'wc-001', eventType: 'action', description: 'Vantex acquisition brief submitted for review', rewardDelta: 0.04, rewardSign: 'positive', proofRef: 'proof-rev-053' },
  { id: 'ev-017', ts: '2026-05-05T07:04:00Z', domain: 'aegis-defense', workcellId: 'wc-004', eventType: 'outcome', description: 'Attack surface reduced 22% — post-hardening scan complete', rewardDelta: 0.15, rewardSign: 'positive', proofRef: 'proof-def-039' },
  { id: 'ev-018', ts: '2026-05-05T06:58:00Z', domain: 'vessels-maritime', workcellId: 'wc-002', eventType: 'signal', description: 'AIS anomaly batch — 3 vessels Port Klang idle >18h', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-mar-115' },
  { id: 'ev-019', ts: '2026-05-05T06:52:00Z', domain: 'prism-counsel', workcellId: 'wc-003', eventType: 'action', description: 'Early-escalation triggered — opposing late-filing pattern', rewardDelta: 0.06, rewardSign: 'positive', proofRef: 'proof-leg-068' },
  { id: 'ev-020', ts: '2026-05-05T06:46:00Z', domain: 'terra-real-estate', workcellId: 'wc-006', eventType: 'correction', description: 'Single-signal weight insufficient — combined indicator required', rewardDelta: -0.04, rewardSign: 'negative', proofRef: 'proof-re-029' },
  { id: 'ev-021', ts: '2026-05-05T06:40:00Z', domain: 'lyte-revenue', workcellId: 'wc-001', eventType: 'outcome', description: 'NovaTech outreach — meeting booked', rewardDelta: 0.06, rewardSign: 'positive', proofRef: 'proof-rev-052' },
  { id: 'ev-022', ts: '2026-05-05T06:34:00Z', domain: 'aegis-defense', workcellId: 'wc-004', eventType: 'signal', description: 'IOC batch: TG-Ember variant B signature detected', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-def-038' },
  { id: 'ev-023', ts: '2026-05-05T06:28:00Z', domain: 'carlota-jo', workcellId: 'wc-002', eventType: 'signal', description: 'SOW aging alert — Meridian subsidiary >21d', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-adv-020' },
  { id: 'ev-024', ts: '2026-05-05T06:22:00Z', domain: 'vessels-maritime', workcellId: 'wc-001', eventType: 'outcome', description: 'Fuel reroute confirmed — $28K cost avoidance', rewardDelta: 0.10, rewardSign: 'positive', proofRef: 'proof-mar-114' },
  { id: 'ev-025', ts: '2026-05-05T06:16:00Z', domain: 'prism-counsel', workcellId: 'wc-005', eventType: 'action', description: 'Citation minimum threshold raised — summary judgment auto-flag', rewardDelta: 0.05, rewardSign: 'positive', proofRef: 'proof-leg-067' },
  { id: 'ev-026', ts: '2026-05-05T06:10:00Z', domain: 'terra-real-estate', workcellId: 'wc-006', eventType: 'action', description: 'Portfolio hedge executed — 3 positions', rewardDelta: 0.09, rewardSign: 'positive', proofRef: 'proof-re-028' },
  { id: 'ev-027', ts: '2026-05-05T06:04:00Z', domain: 'lyte-revenue', workcellId: 'wc-001', eventType: 'correction', description: 'Apex outreach model: churn signal lag reduced 6d→3d', rewardDelta: 0.07, rewardSign: 'positive', proofRef: 'proof-rev-051' },
  { id: 'ev-028', ts: '2026-05-05T05:58:00Z', domain: 'aegis-defense', workcellId: 'wc-004', eventType: 'outcome', description: 'Incident response SLA met — T+12m vs T+30m baseline', rewardDelta: 0.14, rewardSign: 'positive', proofRef: 'proof-def-037' },
  { id: 'ev-029', ts: '2026-05-05T05:52:00Z', domain: 'vessels-maritime', workcellId: 'wc-002', eventType: 'signal', description: 'ETA deviation alert — MV Aurora Straits passage', rewardDelta: 0.00, rewardSign: 'neutral', proofRef: 'proof-mar-113' },
  { id: 'ev-030', ts: '2026-05-05T05:46:00Z', domain: 'carlota-jo', workcellId: 'wc-002', eventType: 'action', description: 'Executive call scheduled — 2 high-value accounts', rewardDelta: 0.05, rewardSign: 'positive', proofRef: 'proof-adv-019' },
  // Additional events for density
  ...Array.from({ length: 90 }, (_, i) => {
    const domains: DomainId[] = ['vessels-maritime', 'prism-counsel', 'aegis-defense', 'lyte-revenue', 'terra-real-estate', 'carlota-jo'];
    const types: ExperienceEvent['eventType'][] = ['signal', 'action', 'outcome', 'correction'];
    const signs: RewardSign[] = ['positive', 'positive', 'positive', 'negative', 'neutral'];
    const dom = domains[i % domains.length];
    const typ = types[i % types.length];
    const sgn = signs[i % signs.length];
    const delta = sgn === 'positive' ? +(0.04 + (i % 7) * 0.02).toFixed(2) : sgn === 'negative' ? -(0.03 + (i % 4) * 0.02).toFixed(2) : 0;
    const wcs = ['wc-001', 'wc-002', 'wc-003', 'wc-004', 'wc-005', 'wc-006'];
    const minsAgo = 30 + i * 6;
    const ANCHOR_MS = 1746403200000; // 2026-05-05T00:00:00Z — fixed, deterministic
    const ts = new Date(ANCHOR_MS - minsAgo * 60 * 1000).toISOString();
    return {
      id: `ev-${31 + i}`,
      ts,
      domain: dom,
      workcellId: wcs[i % wcs.length],
      eventType: typ,
      description: `Automated experience event ${31 + i} — ${dom} ${typ}`,
      rewardDelta: delta,
      rewardSign: sgn,
      proofRef: `proof-auto-${100 + i}`,
    } as ExperienceEvent;
  }),
];

// ─── Experience throughput sparkline (events/h by hour-of-day) ───────────────
export const THROUGHPUT_BY_HOUR: { hour: number; count: number }[] = [
  { hour: 0, count: 8 }, { hour: 1, count: 6 }, { hour: 2, count: 5 }, { hour: 3, count: 4 },
  { hour: 4, count: 5 }, { hour: 5, count: 7 }, { hour: 6, count: 12 }, { hour: 7, count: 18 },
  { hour: 8, count: 24 }, { hour: 9, count: 28 }, { hour: 10, count: 31 }, { hour: 11, count: 29 },
  { hour: 12, count: 22 }, { hour: 13, count: 26 }, { hour: 14, count: 32 }, { hour: 15, count: 35 },
  { hour: 16, count: 33 }, { hour: 17, count: 28 }, { hour: 18, count: 21 }, { hour: 19, count: 16 },
  { hour: 20, count: 14 }, { hour: 21, count: 12 }, { hour: 22, count: 10 }, { hour: 23, count: 9 },
];

// ─── Ineffable Channel — Latent Embeddings ────────────────────────────────────
export interface LatentCluster {
  id: string;
  label: string;
  domain: DomainId;
  x: number;
  y: number;
  radius: number;
  translation: string;
  confidence: number;
  linkedProof: string;
  autonomyDepthRequired: number;
}

export interface LatentPoint {
  id: string;
  clusterId: string;
  x: number;
  y: number;
  messageType: 'query' | 'response' | 'correction' | 'boundary';
  translation: string;
}

export const LATENT_CLUSTERS: LatentCluster[] = [
  { id: 'lc-001', label: 'Maritime Risk Cascade', domain: 'vessels-maritime', x: 0.18, y: 0.72, radius: 0.10, translation: 'A cluster of inter-agent messages encoding risk propagation paths across maritime lanes — proposers encoding potential standby outcomes, verifiers encoding constraint satisfaction checks.', confidence: 0.91, linkedProof: 'proof-mar-118', autonomyDepthRequired: 3 },
  { id: 'lc-002', label: 'Legal Deadline Pressure', domain: 'prism-counsel', x: 0.74, y: 0.28, radius: 0.09, translation: 'Messages encoding urgency gradients for deadline-proximate decisions. Verifier sub-cluster tightly constraining escalation bounds. Adversary probing clock ambiguity.', confidence: 0.87, linkedProof: 'proof-leg-071', autonomyDepthRequired: 4 },
  { id: 'lc-003', label: 'Threat Isolation Logic', domain: 'aegis-defense', x: 0.42, y: 0.55, radius: 0.12, translation: 'Dense reasoning cluster: proposer encoding IOC match confidence and blast-radius estimates; verifier encoding policy-gate satisfaction; adversary probing lateral path alternatives not captured in the threat model.', confidence: 0.94, linkedProof: 'proof-def-042', autonomyDepthRequired: 5 },
  { id: 'lc-004', label: 'Revenue Signal Fusion', domain: 'lyte-revenue', x: 0.81, y: 0.62, radius: 0.08, translation: 'Multi-signal fusion: churn velocity, engagement decay, and deal-stage stall. Proposer encoding composite risk score; verifier encoding historical acceptance base-rates.', confidence: 0.83, linkedProof: 'proof-rev-055', autonomyDepthRequired: 3 },
  { id: 'lc-005', label: 'Cap-Rate Leading Indicators', domain: 'terra-real-estate', x: 0.31, y: 0.18, radius: 0.08, translation: 'A sparse cluster encoding compressed market micro-structure signals — proposer embedding the 7d leading indicator; verifier encoding prior calibration accuracy.', confidence: 0.79, linkedProof: 'proof-re-031', autonomyDepthRequired: 3 },
  { id: 'lc-006', label: 'Policy Constraint Boundary', domain: 'aegis-defense', x: 0.60, y: 0.80, radius: 0.07, translation: 'Boundary-layer messages encoding Covenant policy hard stops — verifier and adversary messaging that constrains the proposer action space to COV-DEF compliant regions.', confidence: 0.96, linkedProof: 'proof-def-041', autonomyDepthRequired: 6 },
];

export const LATENT_POINTS: LatentPoint[] = [
  { id: 'lp-001', clusterId: 'lc-001', x: 0.16, y: 0.70, messageType: 'query', translation: 'P→V: What is the expected demurrage cost at T+18h given current AIS?' },
  { id: 'lp-002', clusterId: 'lc-001', x: 0.20, y: 0.74, messageType: 'response', translation: 'V→P: Confidence 0.89. Demurrage Δ = $42K within COV-MAR-03.' },
  { id: 'lp-003', clusterId: 'lc-001', x: 0.18, y: 0.68, messageType: 'correction', translation: 'A→P: Fuel data freshness only 5.2h — marginal. Flag for verifier.' },
  { id: 'lp-004', clusterId: 'lc-002', x: 0.72, y: 0.26, messageType: 'query', translation: 'P→V: Talbot discovery — is T-48h window sufficient for supplemental motion?' },
  { id: 'lp-005', clusterId: 'lc-002', x: 0.76, y: 0.30, messageType: 'response', translation: 'V→P: Precedent base rate 94% — motion recommended. COV-LEG-02 satisfied.' },
  { id: 'lp-006', clusterId: 'lc-003', x: 0.40, y: 0.53, messageType: 'query', translation: 'P→V: TG-Ember IOC — blast radius for 2-node isolation?' },
  { id: 'lp-007', clusterId: 'lc-003', x: 0.44, y: 0.57, messageType: 'response', translation: 'V→P: Tier-1 node excluded. Blast radius within COV-DEF-04.' },
  { id: 'lp-008', clusterId: 'lc-003', x: 0.42, y: 0.60, messageType: 'boundary', translation: 'Covenant constraint: tier-1 node requires board-level approval gate.' },
  { id: 'lp-009', clusterId: 'lc-004', x: 0.80, y: 0.60, messageType: 'query', translation: 'P→V: Apex churn signal composite — confidence threshold met?' },
  { id: 'lp-010', clusterId: 'lc-004', x: 0.83, y: 0.64, messageType: 'response', translation: 'V→P: 0.84 confidence. Historical acceptance 87%. Proceed.' },
  { id: 'lp-011', clusterId: 'lc-005', x: 0.30, y: 0.17, messageType: 'query', translation: 'P→V: 7d cap-rate leading indicator — within calibration envelope?' },
  { id: 'lp-012', clusterId: 'lc-005', x: 0.33, y: 0.20, messageType: 'response', translation: 'V→P: ±2.1% from calibration. Within threshold. Hedge authorized.' },
  { id: 'lp-013', clusterId: 'lc-006', x: 0.59, y: 0.78, messageType: 'boundary', translation: 'Hard stop: Covenant COV-DEF-04 active. Proposer action space restricted.' },
  { id: 'lp-014', clusterId: 'lc-006', x: 0.62, y: 0.82, messageType: 'boundary', translation: 'Verifier constraint propagated: board approval required within 4m.' },
];

// ─── Distillation Forge ────────────────────────────────────────────────────────
export type ForgeStatus = 'queued' | 'promoted' | 'held' | 'distilling';
export type ModelTier = 'Sovereign' | 'Code' | 'Reason' | 'Fast';

export interface DistillationEntry {
  id: string;
  policyId: string;
  policyName: string;
  domain: DomainId;
  targetTier: ModelTier;
  regretBound: number;
  rollbackGate: 'open' | 'pending' | 'locked';
  status: ForgeStatus;
  queuedAt: string;
  elo: number;
  lifetimeImpact: string;
  compressionRatio: number;
}

export interface RetiredPolicy {
  id: string;
  name: string;
  domain: DomainId;
  retiredAt: string;
  finalElo: number;
  lifetimeImpact: string;
  supersededBy: string;
  retirementReason: string;
}

export const DISTILLATION_QUEUE: DistillationEntry[] = [
  { id: 'dq-001', policyId: 'cp-def-001', policyName: 'Lodestone-Defense-v5', domain: 'aegis-defense', targetTier: 'Sovereign', regretBound: 0.04, rollbackGate: 'open', status: 'queued', queuedAt: '2026-05-05T06:00:00Z', elo: 1923, lifetimeImpact: '34% faster threat isolation', compressionRatio: 0.31 },
  { id: 'dq-002', policyId: 'cp-mar-001', policyName: 'Lodestone-Maritime-v4', domain: 'vessels-maritime', targetTier: 'Sovereign', regretBound: 0.06, rollbackGate: 'open', status: 'queued', queuedAt: '2026-05-05T05:30:00Z', elo: 1847, lifetimeImpact: '$2.3M demurrage avoided', compressionRatio: 0.38 },
  { id: 'dq-003', policyId: 'cp-leg-001', policyName: 'Lodestone-Legal-v3', domain: 'prism-counsel', targetTier: 'Reason', regretBound: 0.07, rollbackGate: 'pending', status: 'distilling', queuedAt: '2026-05-04T22:00:00Z', elo: 1791, lifetimeImpact: '$1.8M risk exposure reduced', compressionRatio: 0.42 },
  { id: 'dq-004', policyId: 'cp-rev-001', policyName: 'Lodestone-Revenue-v2', domain: 'lyte-revenue', targetTier: 'Code', regretBound: 0.09, rollbackGate: 'open', status: 'queued', queuedAt: '2026-05-04T20:00:00Z', elo: 1672, lifetimeImpact: '$840K ARR recovered', compressionRatio: 0.51 },
  { id: 'dq-005', policyId: 'cp-re-001', policyName: 'Lodestone-RealEstate-v3', domain: 'terra-real-estate', targetTier: 'Reason', regretBound: 0.08, rollbackGate: 'locked', status: 'held', queuedAt: '2026-05-04T18:00:00Z', elo: 1714, lifetimeImpact: '18bps earlier warning', compressionRatio: 0.44 },
  { id: 'dq-006', policyId: 'cp-adv-001', policyName: 'Lodestone-Advisory-v2', domain: 'carlota-jo', targetTier: 'Fast', regretBound: 0.11, rollbackGate: 'open', status: 'queued', queuedAt: '2026-05-04T16:00:00Z', elo: 1598, lifetimeImpact: '$320K pipeline acceleration', compressionRatio: 0.62 },
];

export const RETIRED_POLICIES: RetiredPolicy[] = [
  { id: 'rp-001', name: 'Lodestone-Maritime-v3', domain: 'vessels-maritime', retiredAt: '2026-04-15T09:00:00Z', finalElo: 1621, lifetimeImpact: '$1.1M demurrage avoided', supersededBy: 'Lodestone-Maritime-v4', retirementReason: 'Superseded by v4 — Elo gap >200 sustained over 60 matches' },
  { id: 'rp-002', name: 'Lodestone-Legal-v2', domain: 'prism-counsel', retiredAt: '2026-04-08T13:00:00Z', finalElo: 1584, lifetimeImpact: '$920K risk reduced', supersededBy: 'Lodestone-Legal-v3', retirementReason: 'Superseded by v3 — calibration accuracy improved 4.1%' },
  { id: 'rp-003', name: 'Lodestone-Defense-v4', domain: 'aegis-defense', retiredAt: '2026-04-20T07:00:00Z', finalElo: 1742, lifetimeImpact: '22% attack surface reduction', supersededBy: 'Lodestone-Defense-v5', retirementReason: 'Superseded by v5 — win rate improved from 81.2% to 84.7%' },
  { id: 'rp-004', name: 'Lodestone-Revenue-v1', domain: 'lyte-revenue', retiredAt: '2026-03-28T10:00:00Z', finalElo: 1489, lifetimeImpact: '$310K ARR recovered', supersededBy: 'Lodestone-Revenue-v2', retirementReason: 'Superseded by v2 — churn signal lag reduced 6→3 days' },
  { id: 'rp-005', name: 'Lex-A-v1', domain: 'prism-counsel', retiredAt: '2026-05-01T12:00:00Z', finalElo: 1412, lifetimeImpact: 'Adversary — no direct impact', supersededBy: 'N/A', retirementReason: 'Quarantined: adversary probes exceeded Mythos constraint boundary frequency' },
];

// ─── Bridge KPIs ───────────────────────────────────────────────────────────────
export const BRIDGE_KPIS = {
  championCount: CHAMPION_POLICIES.filter(p => p.status === 'champion').length,
  worldModelAccuracy: 0.891,
  experienceThroughput: 31.4,
  latentChannelUtilization: 0.73,
  nextPromotionInHours: 3.4,
  activeVariants: AGENT_VARIANTS.filter(v => v.status === 'active').length,
  domainsStable: 6,
  totalExperienceEvents: EXPERIENCE_EVENTS.length,
};
