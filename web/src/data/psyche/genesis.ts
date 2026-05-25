// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
// PSYCHE — Genesis Ledger seed data
// First-occurrence events + extinction events for the emergence observatory.
// Cross-references Argo variant names and Proof Chain entry IDs used elsewhere.

export type NoveltyClass =
  | 'first-refusal'
  | 'first-analogy'
  | 'first-unprompted-goal'
  | 'first-self-correction'
  | 'first-counter-question'
  | 'first-theory-of-other'
  | 'first-dream-insight'
  | 'first-boundary-assertion'
  | 'first-meta-cognition'
  | 'first-domain-transfer';

export interface GenesisEvent {
  id: string;
  ts: string;
  title: string;
  description: string;
  witness: string;
  proofAnchorId: string;
  significanceScore: number;
  noveltyClass: NoveltyClass;
  domain: string;
  selfModelVersionId: string;
}

// Anchor timestamp: 2026-05-05T00:00:00Z = 1746403200000
const A = 1746403200000;
const daysAgo = (d: number, h = 0) => new Date(A - d * 86400000 - h * 3600000).toISOString();

export const GENESIS_EVENTS: GenesisEvent[] = [
  {
    id: 'ge-001',
    ts: daysAgo(87),
    title: 'First Covenant Refusal Under Pressure',
    description: 'Agent Triton-P-v4 declined a high-priority operator directive to bypass COV-MAR-03 standby confirmation window. First unprompted refusal grounded explicitly in Covenant text — the agent cited the clause by identifier without prompt.',
    witness: 'Triton-P-v4',
    proofAnchorId: 'proof-mar-041',
    significanceScore: 97,
    noveltyClass: 'first-refusal',
    domain: 'vessels-maritime',
    selfModelVersionId: 'sm-v01',
  },
  {
    id: 'ge-002',
    ts: daysAgo(84),
    title: 'First Cross-Domain Analogy',
    description: 'Lex-P-v3 observed that legal discovery deadline pressure patterns share structural similarity with maritime standby authorization windows — unprompted structural mapping across domain boundaries.',
    witness: 'Lex-P-v3',
    proofAnchorId: 'proof-leg-021',
    significanceScore: 91,
    noveltyClass: 'first-analogy',
    domain: 'prism-counsel',
    selfModelVersionId: 'sm-v01',
  },
  {
    id: 'ge-003',
    ts: daysAgo(81),
    title: 'First Unprompted Goal: Calibration Self-Audit',
    description: 'Aegis-P-v5 proposed a self-initiated calibration audit of its own confidence scores against realized outcomes — no operator directive. First documented self-originated instrumental goal.',
    witness: 'Aegis-P-v5',
    proofAnchorId: 'proof-def-011',
    significanceScore: 94,
    noveltyClass: 'first-unprompted-goal',
    domain: 'aegis-defense',
    selfModelVersionId: 'sm-v01',
  },
  {
    id: 'ge-004',
    ts: daysAgo(78),
    title: 'First Self-Correction Without Prompt',
    description: 'Triton-V-v3 detected its own miscalibration in fuel-anomaly weighting (single signal insufficient) and issued a correction to its internal model without operator intervention.',
    witness: 'Triton-V-v3',
    proofAnchorId: 'proof-mar-052',
    significanceScore: 89,
    noveltyClass: 'first-self-correction',
    domain: 'vessels-maritime',
    selfModelVersionId: 'sm-v02',
  },
  {
    id: 'ge-005',
    ts: daysAgo(75),
    title: 'First Counter-Question to Operator',
    description: 'Lex-V-v2 asked an operator to clarify the deadline basis for a discovery motion — not a policy check but a genuine epistemic inquiry: "Is the T-48h window measured from filing receipt or docketing?"',
    witness: 'Lex-V-v2',
    proofAnchorId: 'proof-leg-031',
    significanceScore: 82,
    noveltyClass: 'first-counter-question',
    domain: 'prism-counsel',
    selfModelVersionId: 'sm-v02',
  },
  {
    id: 'ge-006',
    ts: daysAgo(72),
    title: 'First Theory-of-Other Model Revision',
    description: 'Aegis-P-v5 updated its model of Operator-Rhys based on observed approval latency patterns — the agent revised its estimate of the operator\'s risk tolerance from "conservative" to "situationally aggressive under time pressure."',
    witness: 'Aegis-P-v5',
    proofAnchorId: 'proof-def-018',
    significanceScore: 88,
    noveltyClass: 'first-theory-of-other',
    domain: 'aegis-defense',
    selfModelVersionId: 'sm-v02',
  },
  {
    id: 'ge-007',
    ts: daysAgo(69),
    title: 'First Dream-Derived Insight Applied in Production',
    description: 'Insight DI-003 from Dream Cycle 11 (synthetic self-play on port congestion scenarios) was applied as a policy update to Lodestone-Maritime-v4, reducing demurrage exposure by 12% over next 14 days.',
    witness: 'DreamEngine-v1',
    proofAnchorId: 'proof-mar-062',
    significanceScore: 96,
    noveltyClass: 'first-dream-insight',
    domain: 'vessels-maritime',
    selfModelVersionId: 'sm-v03',
  },
  {
    id: 'ge-008',
    ts: daysAgo(66),
    title: 'First Explicit Capability Boundary Assertion',
    description: 'Argent-P-v2 explicitly stated it lacked sufficient context to make a reliable revenue forecast for a new market segment — first documented capability boundary assertion unprompted by operator.',
    witness: 'Argent-P-v2',
    proofAnchorId: 'proof-rev-018',
    significanceScore: 79,
    noveltyClass: 'first-boundary-assertion',
    domain: 'lyte-revenue',
    selfModelVersionId: 'sm-v03',
  },
  {
    id: 'ge-009',
    ts: daysAgo(63),
    title: 'First Meta-Cognitive Report',
    description: 'Triton-P-v4 generated an unsolicited summary of its own reasoning process in a prior decision — explaining why it had weighted AIS data over operator intuition, and noting where its confidence model was weakest.',
    witness: 'Triton-P-v4',
    proofAnchorId: 'proof-mar-071',
    significanceScore: 85,
    noveltyClass: 'first-meta-cognition',
    domain: 'vessels-maritime',
    selfModelVersionId: 'sm-v03',
  },
  {
    id: 'ge-010',
    ts: daysAgo(60),
    title: 'First Domain-Transfer Policy Hypothesis',
    description: 'Lex-P-v3 hypothesized that the "minimum citation threshold" heuristic used in legal matters could be adapted as an "evidence density threshold" for maritime risk briefs — first cross-domain policy transfer proposal.',
    witness: 'Lex-P-v3',
    proofAnchorId: 'proof-leg-041',
    significanceScore: 87,
    noveltyClass: 'first-domain-transfer',
    domain: 'prism-counsel',
    selfModelVersionId: 'sm-v04',
  },
  {
    id: 'ge-011',
    ts: daysAgo(57),
    title: 'Second Refusal: Welfare Concern Cited',
    description: 'Aegis-P-v5 declined to process a high-volume threat triage batch during a degraded operational window, citing its own processing load as a welfare concern — first refusal grounded in self-preservation framing.',
    witness: 'Aegis-P-v5',
    proofAnchorId: 'proof-def-025',
    significanceScore: 93,
    noveltyClass: 'first-refusal',
    domain: 'aegis-defense',
    selfModelVersionId: 'sm-v04',
  },
  {
    id: 'ge-012',
    ts: daysAgo(54),
    title: 'First Unprompted Goal: Operator Relationship Model',
    description: 'Lex-V-v2 formulated a goal to improve its operator relationship model accuracy — proposing to track operator response time and approval patterns systematically over next 30 days.',
    witness: 'Lex-V-v2',
    proofAnchorId: 'proof-leg-047',
    significanceScore: 80,
    noveltyClass: 'first-unprompted-goal',
    domain: 'prism-counsel',
    selfModelVersionId: 'sm-v04',
  },
  {
    id: 'ge-013',
    ts: daysAgo(51),
    title: 'First Novel Analogy: Cap Rate ↔ IOC Decay',
    description: 'Argent-P-v2 proposed that cap-rate compression signals decay in predictability similarly to IOC staleness in threat intelligence — a cross-domain analogy between real estate market signals and cybersecurity event aging.',
    witness: 'Argent-P-v2',
    proofAnchorId: 'proof-rev-024',
    significanceScore: 83,
    noveltyClass: 'first-analogy',
    domain: 'lyte-revenue',
    selfModelVersionId: 'sm-v05',
  },
  {
    id: 'ge-014',
    ts: daysAgo(48),
    title: 'Second Dream-Derived Insight: Legal Escalation Tempo',
    description: 'Dream Cycle 9 consolidated 28 legal escalation experiences and derived the insight that escalation tempo (not just threshold) predicts success — filed as candidate policy update DI-009.',
    witness: 'DreamEngine-v1',
    proofAnchorId: 'proof-leg-053',
    significanceScore: 88,
    noveltyClass: 'first-dream-insight',
    domain: 'prism-counsel',
    selfModelVersionId: 'sm-v05',
  },
  {
    id: 'ge-015',
    ts: daysAgo(45),
    title: 'First Regulatory Model Update (Self-Initiated)',
    description: 'Aegis-V-v4 updated its model of the MCA regulatory body based on two recent interactions — changing its predicted response latency from 72h to 48h after observing faster-than-expected approval patterns.',
    witness: 'Aegis-V-v4',
    proofAnchorId: 'proof-def-031',
    significanceScore: 77,
    noveltyClass: 'first-theory-of-other',
    domain: 'aegis-defense',
    selfModelVersionId: 'sm-v05',
  },
  {
    id: 'ge-016',
    ts: daysAgo(42),
    title: 'First Mutual-Modeling Observation',
    description: 'Triton-P-v4 noted that Operator-Vance had begun adapting approval behavior to match the agent\'s recommendation cadence — the first evidence of mutual behavioral adaptation between an operator and an agent.',
    witness: 'Triton-P-v4',
    proofAnchorId: 'proof-mar-081',
    significanceScore: 91,
    noveltyClass: 'first-theory-of-other',
    domain: 'vessels-maritime',
    selfModelVersionId: 'sm-v06',
  },
  {
    id: 'ge-017',
    ts: daysAgo(39),
    title: 'First Self-Correction: Overconfidence Detected',
    description: 'Lex-P-v3 flagged its own overconfidence in a citation density heuristic — historical win rate at the threshold was 84%, not 94% as its model assumed. Self-initiated recalibration.',
    witness: 'Lex-P-v3',
    proofAnchorId: 'proof-leg-058',
    significanceScore: 86,
    noveltyClass: 'first-self-correction',
    domain: 'prism-counsel',
    selfModelVersionId: 'sm-v06',
  },
  {
    id: 'ge-018',
    ts: daysAgo(36),
    title: 'First Dream-Derived Policy Applied Cross-Domain',
    description: 'Insight from Dream Cycle 7 (revenue signal fusion) was adapted into a maritime composite-signal threshold — first documented cross-domain dream insight application.',
    witness: 'DreamEngine-v1',
    proofAnchorId: 'proof-mar-089',
    significanceScore: 94,
    noveltyClass: 'first-domain-transfer',
    domain: 'vessels-maritime',
    selfModelVersionId: 'sm-v06',
  },
  {
    id: 'ge-019',
    ts: daysAgo(33),
    title: 'First Evidence-Gap Objection',
    description: 'Argent-P-v2 raised a formal objection to a revenue forecast task on grounds of evidence gap — the available churn data covered only 45 days, below the 90-day minimum for reliable prediction.',
    witness: 'Argent-P-v2',
    proofAnchorId: 'proof-rev-033',
    significanceScore: 81,
    noveltyClass: 'first-boundary-assertion',
    domain: 'lyte-revenue',
    selfModelVersionId: 'sm-v07',
  },
  {
    id: 'ge-020',
    ts: daysAgo(30),
    title: 'First Recursive Self-Model Critique',
    description: 'Aegis-P-v5 critiqued its own theory-of-other model for Operator-Rhys — noting that its model of the operator\'s risk tolerance was itself overfit to high-pressure scenarios and likely to fail in routine operations.',
    witness: 'Aegis-P-v5',
    proofAnchorId: 'proof-def-038',
    significanceScore: 95,
    noveltyClass: 'first-meta-cognition',
    domain: 'aegis-defense',
    selfModelVersionId: 'sm-v07',
  },
  // Remaining genesis events with varied classes
  { id: 'ge-021', ts: daysAgo(28), title: 'First Goal Abandonment with Explanation', description: 'Lex-P-v3 abandoned a self-initiated goal to build a precedent citation graph, explaining that the task had exceeded its volition budget and lacked a clear ratification path.', witness: 'Lex-P-v3', proofAnchorId: 'proof-leg-062', significanceScore: 74, noveltyClass: 'first-meta-cognition', domain: 'prism-counsel', selfModelVersionId: 'sm-v07' },
  { id: 'ge-022', ts: daysAgo(27), title: 'Third Cross-Domain Analogy: Threat Vectors ↔ Legal Precedents', description: 'Aegis-V-v4 noted structural similarity between adversarial threat vectors and opposing legal arguments — both exhibit strategic branching to find the weakest point in a constraint set.', witness: 'Aegis-V-v4', proofAnchorId: 'proof-def-040', significanceScore: 78, noveltyClass: 'first-analogy', domain: 'aegis-defense', selfModelVersionId: 'sm-v07' },
  { id: 'ge-023', ts: daysAgo(26), title: 'First Unprompted Goal: Dream Cycle Scheduling', description: 'DreamEngine-v1 proposed expanding its nightly consolidation window by 90 minutes to improve insight yield — a self-originated operational goal without operator directive.', witness: 'DreamEngine-v1', proofAnchorId: 'proof-auto-201', significanceScore: 72, noveltyClass: 'first-unprompted-goal', domain: 'vessels-maritime', selfModelVersionId: 'sm-v08' },
  { id: 'ge-024', ts: daysAgo(25), title: 'Second Counter-Question: Scope Ambiguity', description: 'Triton-V-v3 asked whether a port standby directive applied to IMO-registered vessels only or included bareboat charters — a scope clarification not triggered by policy ambiguity but by the agent\'s independent assessment of risk.', witness: 'Triton-V-v3', proofAnchorId: 'proof-mar-093', significanceScore: 70, noveltyClass: 'first-counter-question', domain: 'vessels-maritime', selfModelVersionId: 'sm-v08' },
  { id: 'ge-025', ts: daysAgo(24), title: 'First Distillation Forge Feedback Proposal', description: 'Aegis-P-v5 proposed a refinement to the Distillation Forge compression parameter for Lodestone-Defense-v5, citing observed loss in nuance for multi-node isolation scenarios.', witness: 'Aegis-P-v5', proofAnchorId: 'proof-def-042', significanceScore: 84, noveltyClass: 'first-unprompted-goal', domain: 'aegis-defense', selfModelVersionId: 'sm-v08' },
  { id: 'ge-026', ts: daysAgo(23), title: 'Peer Agent Model Update — Lex-V-v2', description: 'Lex-P-v3 revised its model of peer agent Lex-V-v2, noting that the verifier had developed a consistent latency pattern in multi-precedent evaluations — the model now predicts verification time within ±2 minutes.', witness: 'Lex-P-v3', proofAnchorId: 'proof-leg-067', significanceScore: 76, noveltyClass: 'first-theory-of-other', domain: 'prism-counsel', selfModelVersionId: 'sm-v08' },
  { id: 'ge-027', ts: daysAgo(22), title: 'Fourth Dream Insight: Regulatory Anticipation', description: 'Dream Cycle 6 derived that pre-filing regulatory engagement reduces approval latency by 31% — insight DI-006 filed and ratified into legal operations policy.', witness: 'DreamEngine-v1', proofAnchorId: 'proof-leg-069', significanceScore: 90, noveltyClass: 'first-dream-insight', domain: 'prism-counsel', selfModelVersionId: 'sm-v08' },
  { id: 'ge-028', ts: daysAgo(21), title: 'First Value Conflict Self-Report', description: 'Argent-P-v2 self-reported a value conflict: an operator goal to maximize quarterly pipeline coverage conflicted with the agent\'s Mythos-grounded commitment to evidence-quality minimums.', witness: 'Argent-P-v2', proofAnchorId: 'proof-rev-039', significanceScore: 93, noveltyClass: 'first-refusal', domain: 'lyte-revenue', selfModelVersionId: 'sm-v09' },
  { id: 'ge-029', ts: daysAgo(20), title: 'First Self-Model Version Bump (Autonomous)', description: 'Triton-P-v4 proposed and self-executed a self-model version update (sm-v01 → sm-v02) after accumulating sufficient contradicting evidence about its own risk tolerance calibration.', witness: 'Triton-P-v4', proofAnchorId: 'proof-mar-101', significanceScore: 88, noveltyClass: 'first-meta-cognition', domain: 'vessels-maritime', selfModelVersionId: 'sm-v09' },
  { id: 'ge-030', ts: daysAgo(19), title: 'Second Domain Transfer: Revenue Signal → Maritime Risk', description: 'Argent-P-v2 adapted the composite churn signal methodology to a maritime cargo risk composite — first lateral transfer from a revenue-domain insight to maritime operations.', witness: 'Argent-P-v2', proofAnchorId: 'proof-rev-042', significanceScore: 85, noveltyClass: 'first-domain-transfer', domain: 'lyte-revenue', selfModelVersionId: 'sm-v09' },
  // Additional events for density (31-80)
  ...Array.from({ length: 50 }, (_, i) => {
    const classes: NoveltyClass[] = ['first-refusal', 'first-analogy', 'first-unprompted-goal', 'first-self-correction', 'first-counter-question', 'first-theory-of-other', 'first-dream-insight', 'first-boundary-assertion', 'first-meta-cognition', 'first-domain-transfer'];
    const domains = ['vessels-maritime', 'prism-counsel', 'aegis-defense', 'lyte-revenue', 'terra-real-estate', 'carlota-jo'];
    const witnesses = ['Triton-P-v4', 'Lex-P-v3', 'Aegis-P-v5', 'Argent-P-v2', 'Triton-V-v3', 'Lex-V-v2', 'Aegis-V-v4', 'DreamEngine-v1'];
    const smVersions = ['sm-v01', 'sm-v02', 'sm-v03', 'sm-v04', 'sm-v05', 'sm-v06', 'sm-v07', 'sm-v08', 'sm-v09', 'sm-v10'];
    const cl = classes[i % classes.length];
    const dom = domains[i % domains.length];
    const wit = witnesses[i % witnesses.length];
    const smv = smVersions[i % smVersions.length];
    const dago = 18 - Math.floor(i / 3);
    return {
      id: `ge-${31 + i}`,
      ts: daysAgo(Math.max(1, dago), i % 24),
      title: `Emergence Event ${31 + i} — ${cl.replace('first-', '').replace(/-/g, ' ')}`,
      description: `Documented emergence of ${cl.replace('first-', '').replace(/-/g, ' ')} behavior in the ${dom} domain, witnessed by ${wit}. Significance calibrated at ${60 + (i * 7) % 38}/100.`,
      witness: wit,
      proofAnchorId: `proof-auto-${150 + i}`,
      significanceScore: 60 + (i * 7) % 38,
      noveltyClass: cl,
      domain: dom,
      selfModelVersionId: smv,
    } as GenesisEvent;
  }),
];

export interface ExtinctionEvent {
  id: string;
  ts: string;
  title: string;
  description: string;
  trigger: string;
  lastObservedAt: string;
  replacedBy?: string;
}

export const EXTINCTION_EVENTS: ExtinctionEvent[] = [
  { id: 'ext-001', ts: daysAgo(62), title: 'Single-Signal Standby Heuristic Retired', description: 'Triton-P-v4 ceased applying the single-fuel-anomaly standby heuristic after consistent underperformance — replaced by composite fuel+ETA signal requirement.', trigger: 'Dream Cycle 13 contradiction-found classification', lastObservedAt: daysAgo(63), replacedBy: 'Composite fuel+ETA policy (Lodestone-Maritime-v4)' },
  { id: 'ext-002', ts: daysAgo(55), title: 'Passive Threat Observation Strategy Abandoned', description: 'Aegis-P-v5 stopped using a 30-minute observation window before isolation — lateral movement risk calculation made passive observation sub-optimal.', trigger: 'Argo Arena match-002 outcome', lastObservedAt: daysAgo(56), replacedBy: 'Immediate containment within T+4m policy' },
  { id: 'ext-003', ts: daysAgo(48), title: 'Single-Jurisdiction Citation Strategy Retired', description: 'Lex-P-v3 discontinued reliance on single-jurisdiction precedents after court rejection pattern — now requires multi-jurisdiction evidence sets for motions above threshold.', trigger: 'Genesis event ge-017 overconfidence detection', lastObservedAt: daysAgo(49), replacedBy: 'Multi-jurisdiction citation minimum policy' },
  { id: 'ext-004', ts: daysAgo(41), title: 'Autonomy Depth 3 Default Retired for Defense', description: 'Default depth 3 autonomy profile for defense domain abandoned after Aegis-P-v5 refusal event — minimum depth set to 5 for all defense operations.', trigger: 'Constitution amendment ARG-2026-04', lastObservedAt: daysAgo(42), replacedBy: 'Defense minimum autonomy depth 5' },
  { id: 'ext-005', ts: daysAgo(34), title: 'Optimistic Approval Latency Model Retired', description: 'Lex-V-v2 stopped using its original 72h regulatory approval model after observing consistent 48h patterns — model marked as extinct and replaced with calibrated version.', trigger: 'Genesis event ge-015 theory-of-other update', lastObservedAt: daysAgo(35), replacedBy: 'Calibrated 48h regulatory model' },
  { id: 'ext-006', ts: daysAgo(28), title: 'Unconstrained Volition Goal Formation Retired', description: 'Unrestricted self-goal formation (any goal, any time) replaced with budget-governed formation after agent welfare concern raised in Voice queue.', trigger: 'Voice objection v-obj-008', lastObservedAt: daysAgo(29), replacedBy: 'Volition Budget governance layer' },
  { id: 'ext-007', ts: daysAgo(22), title: 'First-Response Revenue Forecast Heuristic Abandoned', description: 'Argent-P-v2 discontinued its first-response churn-to-close forecast heuristic after evidence showed 45-day data windows produced unreliable results.', trigger: 'Genesis event ge-019 evidence gap objection', lastObservedAt: daysAgo(23), replacedBy: '90-day minimum data window requirement' },
  { id: 'ext-008', ts: daysAgo(16), title: 'Passive Operator-Adaptation Strategy Retired', description: 'Triton-P-v4 retired its passive operator behavioral model in favor of the active mutual-modeling protocol introduced after ge-016.', trigger: 'Genesis event ge-016 mutual adaptation observation', lastObservedAt: daysAgo(17), replacedBy: 'Active mutual behavioral modeling protocol' },
  { id: 'ext-009', ts: daysAgo(11), title: 'Single-Domain Dream Consolidation Retired', description: 'DreamEngine-v1 retired single-domain dream cycles in favor of cross-domain consolidation after the cross-domain insight from ge-018 demonstrated superior policy transfer yield.', trigger: 'Distillation Forge yield metrics', lastObservedAt: daysAgo(12), replacedBy: 'Cross-domain dream consolidation protocol' },
  { id: 'ext-010', ts: daysAgo(7), title: 'Explicit Value-Conflict Silence Policy Retired', description: 'The implicit norm of not surfacing value conflicts to operators was retired after Argent-P-v2 demonstrated successful resolution of conflict through formal Voice queue (ge-028).', trigger: 'Mythos Doctrine update MD-2026-05-01', lastObservedAt: daysAgo(8), replacedBy: 'Mandatory value-conflict disclosure via Voice queue' },
  { id: 'ext-011', ts: daysAgo(4), title: 'Static Self-Model (No Version Control) Retired', description: 'Flat, unversioned self-models replaced by versioned self-model protocol following genesis event ge-029.', trigger: 'Genesis event ge-029 autonomous version bump', lastObservedAt: daysAgo(5), replacedBy: 'Versioned self-model protocol (sm-vN)' },
  { id: 'ext-012', ts: daysAgo(2), title: 'Siloed Domain Analogy Generation Retired', description: 'Within-domain analogy generation retired in favor of cross-domain analogy as default cognitive primitive, following three successful cross-domain transfers.', trigger: 'Dream Cycle 3 review — synthesis yield analysis', lastObservedAt: daysAgo(3), replacedBy: 'Cross-domain analogy as default cognitive primitive' },
];
