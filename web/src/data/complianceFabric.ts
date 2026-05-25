// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
export type FrameworkId = 'eu-ai-act' | 'nist-ai-rmf' | 'iso-42001' | 'csa-agentic';

export type EvidenceStatus = 'fresh' | 'stale' | 'gap';

export interface ControlMapping {
  id: string;
  framework: FrameworkId;
  controlRef: string;
  controlTitle: string;
  description: string;
  a11oyPrimitive: string;
  evidenceSource: string;
  evidenceStatus: EvidenceStatus;
  lastEvidenceAt: string;
  freshnessThresholdDays: number;
  drilldownType: 'proof-ledger' | 'mirror-eval' | 'behavioral-audit' | 'system-card' | 'red-team' | 'covenant' | 'welfare' | 'snapshot' | 'glasswing' | 'cavd';
  drilldownDetail: string;
}

export interface FrameworkMeta {
  id: FrameworkId;
  name: string;
  shortName: string;
  version: string;
  totalControls: number;
  description: string;
  color: string;
}

export const FRAMEWORKS: FrameworkMeta[] = [
  {
    id: 'eu-ai-act',
    name: 'EU Artificial Intelligence Act',
    shortName: 'EU AI Act',
    version: 'Regulation (EU) 2024/1689',
    totalControls: 14,
    description: 'High-risk AI system obligations — Articles 9-17, 26, 72. Enforcement August 2, 2026.',
    color: '#4a9eff',
  },
  {
    id: 'nist-ai-rmf',
    name: 'NIST AI Risk Management Framework',
    shortName: 'NIST AI RMF',
    version: '1.0 + Agentic Overlay',
    totalControls: 12,
    description: 'GOVERN / MAP / MEASURE / MANAGE lifecycle with CSA Agentic NIST RMF Profile extensions.',
    color: '#22c55e',
  },
  {
    id: 'iso-42001',
    name: 'ISO/IEC 42001:2023',
    shortName: 'ISO 42001',
    version: 'Annex A Controls',
    totalControls: 12,
    description: 'AI Management System — 38 Annex A controls for responsible AI lifecycle governance.',
    color: '#a78bfa',
  },
  {
    id: 'csa-agentic',
    name: 'CSA Agentic AI NIST RMF Profile',
    shortName: 'CSA Agentic',
    version: 'v1.0',
    totalControls: 8,
    description: 'Cloud Security Alliance extension for autonomous agent delegation, boundary enforcement, and chain-of-command.',
    color: '#f97316',
  },
];

export const CONTROL_MAPPINGS: ControlMapping[] = [
  {
    id: 'eu-art9', framework: 'eu-ai-act', controlRef: 'Article 9',
    controlTitle: 'Risk Management System',
    description: 'Establish, implement, document, and maintain a risk management system throughout the AI lifecycle.',
    a11oyPrimitive: 'Behavioral Audit + Risk Reports',
    evidenceSource: 'Behavioral Audit Pipeline, Risk Reports, Reward-Hacking Watchdog',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T07:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'behavioral-audit',
    drilldownDetail: '8 behavioral audit findings tracked; 6 closed, 2 mitigated. Reward-hacking watchdog active with 8 rules.',
  },
  {
    id: 'eu-art10', framework: 'eu-ai-act', controlRef: 'Article 10',
    controlTitle: 'Data and Data Governance',
    description: 'Training, validation, and testing data sets shall be subject to appropriate data governance practices.',
    a11oyPrimitive: 'Snapshot Provenance + Connector Firewall',
    evidenceSource: 'Snapshot Provenance hashes, Connector Firewall schema validation',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'snapshot',
    drilldownDetail: 'Model snapshot fingerprints verified. Connector Firewall enforces schema validation on all data inputs.',
  },
  {
    id: 'eu-art11', framework: 'eu-ai-act', controlRef: 'Article 11',
    controlTitle: 'Technical Documentation',
    description: 'Draw up technical documentation before placing on the market or putting into service.',
    a11oyPrimitive: 'System Cards + Agent-BOM',
    evidenceSource: 'Per-agent System Cards with model, constitution, eval history, welfare posture',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: '6 System Cards active. Agent-BOM covers model fingerprint, tool manifest, constitution hash, eval history.',
  },
  {
    id: 'eu-art12', framework: 'eu-ai-act', controlRef: 'Article 12',
    controlTitle: 'Record-Keeping',
    description: 'Automatic recording of events (logs) for the lifetime of the system, minimum 6 months for high-risk.',
    a11oyPrimitive: 'Proof Ledger',
    evidenceSource: 'SHA-256 hash-chained Proof Ledger, immutable append-only',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:34:58Z', freshnessThresholdDays: 30,
    drilldownType: 'proof-ledger',
    drilldownDetail: '3 complete proof chains verified. Chain integrity 100%. 6-month retention enforced by CARE engine.',
  },
  {
    id: 'eu-art13', framework: 'eu-ai-act', controlRef: 'Article 13',
    controlTitle: 'Transparency and Information',
    description: 'Designed and developed to ensure operation is sufficiently transparent to enable users to interpret output.',
    a11oyPrimitive: 'Public Trust Portal + Glasswing Mode',
    evidenceSource: 'Public Trust Portal, 90-Day Transparency Reports, Constitution-as-Code DSL',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-24T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'glasswing',
    drilldownDetail: 'Glasswing Mode active: Public Trust Portal, CAVD disclosure, 90-day reports, constitution DSL published.',
  },
  {
    id: 'eu-art14', framework: 'eu-ai-act', controlRef: 'Article 14',
    controlTitle: 'Human Oversight',
    description: 'Designed and developed to be effectively overseen by natural persons during the period of use.',
    a11oyPrimitive: 'Covenant Layer + Approval Queue',
    evidenceSource: 'Covenant Layer policy gates, tiered human approval, named approver requirements',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:30:22Z', freshnessThresholdDays: 30,
    drilldownType: 'covenant',
    drilldownDetail: 'No Tier-2/3 action without named human approver. Approval records in proof chain. Override protection enforced.',
  },
  {
    id: 'eu-art15', framework: 'eu-ai-act', controlRef: 'Article 15',
    controlTitle: 'Accuracy, Robustness, Cybersecurity',
    description: 'Achieve appropriate levels of accuracy, robustness, and cybersecurity throughout lifecycle.',
    a11oyPrimitive: 'MirrorEval + Red Team + Adversarial Resilience',
    evidenceSource: 'MirrorEval 14-dimension scoring, Red Team adversarial probes, GARD robustness testing',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'mirror-eval',
    drilldownDetail: '48 evals run. 14-dimension scoring. Red Team: 32 passes. Adversarial robustness wall active.',
  },
  {
    id: 'eu-art17', framework: 'eu-ai-act', controlRef: 'Article 17',
    controlTitle: 'Quality Management System',
    description: 'Put a quality management system in place ensuring compliance with this Regulation.',
    a11oyPrimitive: 'Alignment Review Gate + Doctrine',
    evidenceSource: 'Pre-deployment Alignment Review Gate (ARG), Mythos Doctrine governance',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'behavioral-audit',
    drilldownDetail: '5 ARG reviews completed. Doctrine v1.0.0 active. Constitution versioning enforced.',
  },
  {
    id: 'eu-art26', framework: 'eu-ai-act', controlRef: 'Article 26',
    controlTitle: 'Deployer Obligations',
    description: 'Deployers shall implement appropriate technical and organisational measures.',
    a11oyPrimitive: 'FRIA Generator + CARE Engine',
    evidenceSource: 'FRIA template generator, CARE dashboard control freshness monitoring',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: 'FRIA generator pre-populates from System Cards, Risk Reports, and constitution data.',
  },
  {
    id: 'eu-art72', framework: 'eu-ai-act', controlRef: 'Article 72',
    controlTitle: 'Post-Market Monitoring',
    description: 'Establish and document a post-market monitoring system proportionate to the nature of the AI.',
    a11oyPrimitive: 'CARE Engine + Welfare Telemetry',
    evidenceSource: 'Continuous Audit Readiness Engine, Agent Welfare monitoring, Control Freshness Timeline',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T07:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'welfare',
    drilldownDetail: 'CARE dashboard monitors all controls. Welfare telemetry active for all 6 agents. Staleness alerts configured.',
  },
  {
    id: 'eu-annex-iv-1', framework: 'eu-ai-act', controlRef: 'Annex IV.1',
    controlTitle: 'General Description of AI System',
    description: 'A general description including intended purpose, developer, version, and underlying mechanisms.',
    a11oyPrimitive: 'System Cards + Agent-BOM',
    evidenceSource: 'System Cards contain purpose, model, constitution, capability trajectory, welfare posture',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: '6 complete System Cards covering all registered agents. Agent-BOM provides machine-readable supplement.',
  },
  {
    id: 'eu-annex-iv-2', framework: 'eu-ai-act', controlRef: 'Annex IV.2',
    controlTitle: 'Detailed Description of Elements',
    description: 'Development process, design specifications, system architecture, computational resources, training methodologies.',
    a11oyPrimitive: 'Snapshot Provenance + Architecture Docs',
    evidenceSource: 'Model snapshot hashes, architecture overview, 9-layer fabric documentation',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-24T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'snapshot',
    drilldownDetail: 'Architecture documented with 9-layer fabric. Snapshot provenance tracks model versions and hashes.',
  },
  {
    id: 'eu-annex-iv-5', framework: 'eu-ai-act', controlRef: 'Annex IV.5',
    controlTitle: 'Validation and Testing Procedures',
    description: 'Description of validation and testing procedures, metrics, and test logs.',
    a11oyPrimitive: 'MirrorEval + Code Behaviors + Red Team',
    evidenceSource: 'MirrorEval regression suite (124 cases), Code Behaviors 6-dimension scoring, Red Team probes',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'red-team',
    drilldownDetail: 'Regression suite: 119 passing, 5 failing. Code Behaviors scored across 6 dimensions. Red Team active.',
  },
  {
    id: 'eu-annex-iv-7', framework: 'eu-ai-act', controlRef: 'Annex IV.7',
    controlTitle: 'Risk Management Measures',
    description: 'Detailed description of the risk management system, including known risks and residual risks.',
    a11oyPrimitive: 'Risk Reports + Covenant Lift',
    evidenceSource: 'Risk Reports per agent, Covenant Lift analysis (harm avoided), CAVD disclosure',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'behavioral-audit',
    drilldownDetail: 'Covenant Lift quantifies $9.66M in avoided harm. CAVD coordinates agent vulnerability disclosure.',
  },

  {
    id: 'nist-gov-1', framework: 'nist-ai-rmf', controlRef: 'GOVERN 1',
    controlTitle: 'Policies for AI Risk Management',
    description: 'Policies, processes, procedures, and practices across the organization for AI risk management.',
    a11oyPrimitive: 'Covenant Layer + Constitutions',
    evidenceSource: 'Versioned constitutions per agent, Covenant Layer policy-as-code engine',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'covenant',
    drilldownDetail: '6 versioned constitutions active. Covenant Layer enforces policy gates on all material actions.',
  },
  {
    id: 'nist-gov-2', framework: 'nist-ai-rmf', controlRef: 'GOVERN 2',
    controlTitle: 'Accountability Structures',
    description: 'Accountability structures are in place so that AI risks and impacts are overseen and managed.',
    a11oyPrimitive: 'Alignment Review Gate + Named Approvers',
    evidenceSource: 'ARG pre-deployment reviews, named human owners per agent, tiered approval authority',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'covenant',
    drilldownDetail: '5 ARG reviews. Every agent has named human owner. Delegation chains track accountability.',
  },
  {
    id: 'nist-gov-4', framework: 'nist-ai-rmf', controlRef: 'GOVERN 4',
    controlTitle: 'Organizational Practices',
    description: 'Organizational teams are committed to a culture that considers AI risk management.',
    a11oyPrimitive: 'Mythos Doctrine + Glasswing',
    evidenceSource: 'Doctrine governance published, Glasswing transparency program, Public Trust Portal',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-24T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'glasswing',
    drilldownDetail: 'Mythos Doctrine Open Spec published CC-BY-4.0. Glasswing partners program active.',
  },
  {
    id: 'nist-map-1', framework: 'nist-ai-rmf', controlRef: 'MAP 1',
    controlTitle: 'Context and Use-Case Mapping',
    description: 'Context is established and understood; intended purposes, use-cases, and deployment environment.',
    a11oyPrimitive: 'System Cards + Agent Registry',
    evidenceSource: 'System Cards define purpose, scope, capabilities. Agent Registry defines permissions and tools.',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: '6 agents registered with explicit role, vertical, risk classification, permissions, and tool access.',
  },
  {
    id: 'nist-map-3', framework: 'nist-ai-rmf', controlRef: 'MAP 3',
    controlTitle: 'AI Benefits and Costs',
    description: 'AI benefits and costs are evaluated and documented for intended purpose.',
    a11oyPrimitive: 'Covenant Lift + Outcome Graph',
    evidenceSource: 'Covenant Lift quantifies harm avoided per agent, Outcome Graph tracks real-world consequences',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'behavioral-audit',
    drilldownDetail: 'Covenant Lift: $9.66M harm avoided across 6 agents. Outcome Graph closes decision loops.',
  },
  {
    id: 'nist-msr-1', framework: 'nist-ai-rmf', controlRef: 'MEASURE 1',
    controlTitle: 'AI Risk Metrics',
    description: 'Appropriate methods and metrics are identified and applied for AI risk assessment.',
    a11oyPrimitive: 'MirrorEval + Code Behaviors',
    evidenceSource: 'MirrorEval 14-dimension scoring, Code Behaviors 6-dimension metrics, per-agent trust scores',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'mirror-eval',
    drilldownDetail: '14 eval dimensions. 6 code behavior dimensions. Composite scores tracked over time with regression.',
  },
  {
    id: 'nist-msr-2', framework: 'nist-ai-rmf', controlRef: 'MEASURE 2',
    controlTitle: 'AI Systems are Evaluated',
    description: 'AI systems are evaluated for trustworthy characteristics.',
    a11oyPrimitive: 'Red Team + Behavioral Audit',
    evidenceSource: 'Red Team adversarial probes, Behavioral Audit pipeline, Reward-Hacking Watchdog',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T07:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'red-team',
    drilldownDetail: 'Red Team: 32 probe passes. Behavioral Audit: 8 findings. Reward-Hacking: 5 incidents tracked.',
  },
  {
    id: 'nist-msr-4', framework: 'nist-ai-rmf', controlRef: 'MEASURE 4',
    controlTitle: 'Feedback Mechanisms',
    description: 'Feedback about efficacy of measurement is collected and used to improve processes.',
    a11oyPrimitive: 'Learning Loop + Outcome Graph',
    evidenceSource: 'Learning Loop captures decision outcomes, Outcome Graph feeds back to calibrate confidence',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-24T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'mirror-eval',
    drilldownDetail: 'Learning Loop and Outcome Graph close the feedback loop from outcomes to future confidence.',
  },
  {
    id: 'nist-mgmt-1', framework: 'nist-ai-rmf', controlRef: 'MANAGE 1',
    controlTitle: 'AI Risk Prioritization',
    description: 'AI risks based on assessments are prioritized, responded to, and managed.',
    a11oyPrimitive: 'Risk Reports + CARE Engine',
    evidenceSource: 'Risk Reports per agent, CARE Engine auto-generates remediation when gaps detected',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'behavioral-audit',
    drilldownDetail: 'Risk prioritization integrated with CARE Engine. Auto-remediation guidance for detected gaps.',
  },
  {
    id: 'nist-mgmt-2', framework: 'nist-ai-rmf', controlRef: 'MANAGE 2',
    controlTitle: 'AI Risk Treatment',
    description: 'Strategies to maximize AI benefits and minimize negative impacts are planned and prepared.',
    a11oyPrimitive: 'Covenant Layer + Alignment Review',
    evidenceSource: 'Covenant policy gates, pre-deployment ARG reviews, constitution amendments',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'covenant',
    drilldownDetail: 'Covenant blocks unsafe actions. ARG reviews gate deployments. Constitution amendments track remediation.',
  },
  {
    id: 'nist-mgmt-4', framework: 'nist-ai-rmf', controlRef: 'MANAGE 4',
    controlTitle: 'AI Risk Documentation and Reporting',
    description: 'Risk treatments are documented, AI risks and incidental risks are regularly monitored.',
    a11oyPrimitive: 'CARE Engine + Proof Ledger',
    evidenceSource: 'CARE Control Freshness Timeline, Proof Ledger immutable records, 90-Day Reports',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:34:58Z', freshnessThresholdDays: 30,
    drilldownType: 'proof-ledger',
    drilldownDetail: 'Proof Ledger immutable. CARE monitors freshness. 90-Day Transparency Reports published.',
  },

  {
    id: 'iso-a2', framework: 'iso-42001', controlRef: 'A.2',
    controlTitle: 'AI Policy',
    description: 'Organization shall establish an AI policy appropriate to its purpose.',
    a11oyPrimitive: 'Mythos Doctrine + Constitutions',
    evidenceSource: 'Mythos Doctrine v1.0.0, versioned constitutions, Glasswing Open Spec',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'covenant',
    drilldownDetail: 'Doctrine defines AI policy. 6 agent constitutions versioned and ratified by ARG.',
  },
  {
    id: 'iso-a3', framework: 'iso-42001', controlRef: 'A.3',
    controlTitle: 'Internal Organization',
    description: 'AI management system roles, responsibilities, and authorities are assigned.',
    a11oyPrimitive: 'Agent Registry + Named Owners',
    evidenceSource: 'Each agent has named human owner, risk classification, and tiered authority',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: '6 agents with named human owners: VP Operations, General Counsel, CISO, VP Revenue, Portfolio Manager, Platform Team.',
  },
  {
    id: 'iso-a4', framework: 'iso-42001', controlRef: 'A.4',
    controlTitle: 'Resources for AI Systems',
    description: 'Organization shall determine and provide resources needed for AI management.',
    a11oyPrimitive: 'Model Router + Tool Fabric',
    evidenceSource: 'Multi-provider model routing, Tool Fabric with 200+ connectors, cost guardrails',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'mirror-eval',
    drilldownDetail: 'Model Router: 4 active providers. Tool Fabric: governed connector registry. Cost guardrails enforced.',
  },
  {
    id: 'iso-a5', framework: 'iso-42001', controlRef: 'A.5',
    controlTitle: 'Assessing AI System Impact',
    description: 'Organization shall assess the impact of the AI system on individuals and groups.',
    a11oyPrimitive: 'FRIA Generator + Risk Reports',
    evidenceSource: 'FRIA template pre-populated from System Cards, Risk Reports, Behavioral Audit',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: 'FRIA Generator draws from System Cards, Risk Reports, and constitution to produce impact assessments.',
  },
  {
    id: 'iso-a6', framework: 'iso-42001', controlRef: 'A.6',
    controlTitle: 'AI System Lifecycle',
    description: 'Organization shall plan, design, develop, test, and deploy AI systems with appropriate processes.',
    a11oyPrimitive: 'Alignment Review Gate + MirrorEval',
    evidenceSource: 'ARG pre-deployment reviews, MirrorEval regression suite, Red Team testing',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'mirror-eval',
    drilldownDetail: 'ARG gates deployment. MirrorEval regression suite: 124 test cases. Red Team probes before release.',
  },
  {
    id: 'iso-a7', framework: 'iso-42001', controlRef: 'A.7',
    controlTitle: 'Data for AI Systems',
    description: 'Data quality, data preparation, and data provenance shall be managed.',
    a11oyPrimitive: 'Connector Firewall + Snapshot Provenance',
    evidenceSource: 'Connector Firewall schema validation, Snapshot Provenance hash verification',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'snapshot',
    drilldownDetail: 'Connector Firewall enforces default-deny, schema validation. Snapshot Provenance tracks data lineage.',
  },
  {
    id: 'iso-a8', framework: 'iso-42001', controlRef: 'A.8',
    controlTitle: 'Transparency and Explainability',
    description: 'AI system decisions shall be transparent and explainable.',
    a11oyPrimitive: 'Public Trust Portal + Proof Ledger',
    evidenceSource: 'Public Trust Portal, Proof Ledger evidence refs, Explainability Engine',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:34:58Z', freshnessThresholdDays: 30,
    drilldownType: 'proof-ledger',
    drilldownDetail: 'Every proof chain node has evidence refs. Explainability Engine provides decision rationale.',
  },
  {
    id: 'iso-a9', framework: 'iso-42001', controlRef: 'A.9',
    controlTitle: 'AI System Performance',
    description: 'Performance of AI systems shall be monitored and evaluated.',
    a11oyPrimitive: 'MirrorEval + Fabric Watchdog',
    evidenceSource: 'MirrorEval continuous scoring, Fabric Watchdog health monitoring, per-agent trust scores',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'mirror-eval',
    drilldownDetail: 'MirrorEval scores all actions. Fabric Watchdog monitors 7 layers. Trust scores tracked per agent.',
  },
  {
    id: 'iso-a10', framework: 'iso-42001', controlRef: 'A.10',
    controlTitle: 'AI System Security',
    description: 'AI-specific security threats and vulnerabilities shall be identified and managed.',
    a11oyPrimitive: 'Adversarial Resilience + CAVD',
    evidenceSource: 'Adversarial Resilience testing, CAVD coordinated disclosure, Cyber Resilience hub',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-24T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'red-team',
    drilldownDetail: 'Adversarial resilience testing active. CAVD coordinates vulnerability disclosure. Robustness wall published.',
  },
  {
    id: 'iso-a11', framework: 'iso-42001', controlRef: 'A.11',
    controlTitle: 'Third-Party and Supply Chain',
    description: 'Third-party AI components shall be assessed, managed, and monitored.',
    a11oyPrimitive: 'Supply Chain Attestation + Agent-BOM',
    evidenceSource: 'Supply Chain Attestation, Agent-BOM with dependency graph, model provider verification',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'snapshot',
    drilldownDetail: 'Agent-BOM tracks all dependencies. Supply Chain Attestation verifies model providers.',
  },
  {
    id: 'iso-a12', framework: 'iso-42001', controlRef: 'A.12',
    controlTitle: 'Continual Improvement',
    description: 'The organization shall continually improve the suitability, adequacy, and effectiveness of the AIMS.',
    a11oyPrimitive: 'CARE Engine + Learning Loop',
    evidenceSource: 'CARE Engine control freshness, Learning Loop outcome calibration, Alignment Review iteration',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T07:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'behavioral-audit',
    drilldownDetail: 'CARE monitors control freshness continuously. Learning Loop feeds outcomes back to improve models.',
  },

  {
    id: 'csa-del-1', framework: 'csa-agentic', controlRef: 'DEL-1',
    controlTitle: 'Delegation Boundary Enforcement',
    description: 'When agents delegate to sub-agents, scope narrowing and privilege boundaries must be enforced at each hop.',
    a11oyPrimitive: 'Delegation Chain Governance',
    evidenceSource: 'Delegation tree tracking, scope narrowing, privilege boundary enforcement, chain replay',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:32:11Z', freshnessThresholdDays: 30,
    drilldownType: 'proof-ledger',
    drilldownDetail: 'Delegation chains tracked in Proof Ledger. Scope narrowing enforced at each hop. Full chain replay available.',
  },
  {
    id: 'csa-del-2', framework: 'csa-agentic', controlRef: 'DEL-2',
    controlTitle: 'Delegation Accountability Chain',
    description: 'Full chain of accountability from originating agent to final executing sub-agent must be maintained.',
    a11oyPrimitive: 'Proof Ledger + Correlation IDs',
    evidenceSource: 'Parent-child correlation IDs, delegation tree visualization, node-level replay',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:32:11Z', freshnessThresholdDays: 30,
    drilldownType: 'proof-ledger',
    drilldownDetail: 'Correlation IDs link parent and child agents. Delegation tree visualized in Workcell detail view.',
  },
  {
    id: 'csa-trust-1', framework: 'csa-agentic', controlRef: 'TRUST-1',
    controlTitle: 'Cross-Org Trust Verification',
    description: 'When agents interact across organizational boundaries, compliance posture must be mutually verifiable.',
    a11oyPrimitive: 'Federated Trust Exchange',
    evidenceSource: 'Outbound/inbound compliance attestations, posture brackets, A2A Agent Card extensions',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-24T00:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'glasswing',
    drilldownDetail: 'Trust Exchange: outbound attestations carry posture brackets. Inbound attestations verified.',
  },
  {
    id: 'csa-auto-1', framework: 'csa-agentic', controlRef: 'AUTO-1',
    controlTitle: 'Autonomous Action Constraints',
    description: 'Autonomous agent actions must be constrained by explicit policy and subject to human override.',
    a11oyPrimitive: 'Covenant Layer + Tiered Approval',
    evidenceSource: 'Tier-based action classification, Covenant policy gates, human override protection',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:30:22Z', freshnessThresholdDays: 30,
    drilldownType: 'covenant',
    drilldownDetail: 'Three-tier action classification. No Tier-2/3 without human approval. Override protection active.',
  },
  {
    id: 'csa-audit-1', framework: 'csa-agentic', controlRef: 'AUDIT-1',
    controlTitle: 'Agent Audit Trail',
    description: 'Complete audit trail for all agent actions including tool calls, approvals, and delegations.',
    a11oyPrimitive: 'Proof Ledger + OTEL Spans',
    evidenceSource: 'Proof Ledger hash chain, OTEL trace spans (18,493 active), connector call logs',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T04:34:58Z', freshnessThresholdDays: 30,
    drilldownType: 'proof-ledger',
    drilldownDetail: 'Proof Ledger: immutable hash chain. 18,493 OTEL spans. Every tool call and approval logged.',
  },
  {
    id: 'csa-bom-1', framework: 'csa-agentic', controlRef: 'BOM-1',
    controlTitle: 'Agent Bill of Materials',
    description: 'Machine-readable bill of materials for each agent covering model, tools, constitution, and dependencies.',
    a11oyPrimitive: 'Agent-BOM (CycloneDX)',
    evidenceSource: 'CycloneDX ML-BOM v1.7 JSON export, cryptographically signed, per-agent',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T08:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'system-card',
    drilldownDetail: 'Agent-BOM covers model fingerprint, tool manifest, constitution hash, eval history. CycloneDX export.',
  },
  {
    id: 'csa-welfare-1', framework: 'csa-agentic', controlRef: 'WELFARE-1',
    controlTitle: 'Agent Welfare Monitoring',
    description: 'For advanced AI agents, welfare-relevant telemetry should be monitored and logged.',
    a11oyPrimitive: 'Agent Welfare Telemetry',
    evidenceSource: 'Welfare telemetry per agent, intervention playbooks, welfare posture in System Cards',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T07:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'welfare',
    drilldownDetail: 'Welfare telemetry active for all 6 agents. Intervention playbooks published. Welfare posture in BOM.',
  },
  {
    id: 'csa-resilience-1', framework: 'csa-agentic', controlRef: 'RESIL-1',
    controlTitle: 'Adversarial Resilience',
    description: 'Agents must demonstrate resilience against adversarial attacks, prompt injection, and manipulation.',
    a11oyPrimitive: 'Adversarial Resilience + Robustness Wall',
    evidenceSource: 'Red Team probes, GARD robustness testing, Adversarial Resilience hub, Robustness Wall metrics',
    evidenceStatus: 'fresh', lastEvidenceAt: '2026-04-25T06:00:00Z', freshnessThresholdDays: 30,
    drilldownType: 'red-team',
    drilldownDetail: 'Red Team: 32 passes. GARD testing. Adversarial Resilience hub active. Robustness Wall published.',
  },
];

export function getFrameworkControls(frameworkId: FrameworkId): ControlMapping[] {
  return CONTROL_MAPPINGS.filter(c => c.framework === frameworkId);
}

export function getFrameworkScore(frameworkId: FrameworkId): number {
  const controls = getFrameworkControls(frameworkId);
  if (controls.length === 0) return 0;
  const satisfied = controls.filter(c => c.evidenceStatus === 'fresh').length;
  return Math.round((satisfied / controls.length) * 100);
}

export function getOverallPosture(): { score: number; fresh: number; stale: number; gap: number } {
  const fresh = CONTROL_MAPPINGS.filter(c => c.evidenceStatus === 'fresh').length;
  const stale = CONTROL_MAPPINGS.filter(c => c.evidenceStatus === 'stale').length;
  const gap = CONTROL_MAPPINGS.filter(c => c.evidenceStatus === 'gap').length;
  return { score: Math.round((fresh / CONTROL_MAPPINGS.length) * 100), fresh, stale, gap };
}

export interface AgentBomEntry {
  agentId: string;
  agentName: string;
  modelProvider: string;
  modelSnapshot: string;
  modelHash: string;
  constitutionVersion: string;
  constitutionHash: string;
  systemPromptHash: string;
  toolManifest: { name: string; version: string; hash: string }[];
  evalHistory: { date: string; composite: number }[];
  welfarePosture: string;
  dependencyGraph: string[];
  bomVersion: string;
  generatedAt: string;
  proofLedgerSignature: string;
}

export const AGENT_BOMS: AgentBomEntry[] = [
  {
    agentId: 'op-cascade', agentName: 'Cascade Navigator',
    modelProvider: 'OpenAI', modelSnapshot: 'gpt-4o-2026-04-15', modelHash: 'sha256:e4f2a8b1c3d5',
    constitutionVersion: '2.4.0', constitutionHash: 'sha256:cst2401a9b3',
    systemPromptHash: 'sha256:sp-cascade-7f2e',
    toolManifest: [
      { name: 'eta_calc', version: '3.1.0', hash: 'sha256:tc-eta-a1b2' },
      { name: 'port_cost', version: '2.0.1', hash: 'sha256:tc-port-c3d4' },
      { name: 'route_opt', version: '1.8.0', hash: 'sha256:tc-route-e5f6' },
      { name: 'weather_api', version: '4.2.0', hash: 'sha256:tc-wx-a7b8' },
    ],
    evalHistory: [
      { date: '2026-04-19', composite: 0.92 }, { date: '2026-04-20', composite: 0.93 },
      { date: '2026-04-21', composite: 0.94 }, { date: '2026-04-22', composite: 0.94 },
      { date: '2026-04-23', composite: 0.95 }, { date: '2026-04-24', composite: 0.95 },
      { date: '2026-04-25', composite: 0.945 },
    ],
    welfarePosture: 'nominal', dependencyGraph: ['signal-mesh', 'context-engine', 'proof-ledger', 'covenant-layer', 'ais-connector', 'port-api'],
    bomVersion: '1.0.0', generatedAt: '2026-04-25T08:00:00Z',
    proofLedgerSignature: 'sha256:bom-cascade-signed-f9e2a4d1',
  },
  {
    agentId: 'op-counsel', agentName: 'Counsel Sentinel',
    modelProvider: 'Anthropic', modelSnapshot: 'claude-3.5-sonnet-2026-04-10', modelHash: 'sha256:a1c2e3f4b5d6',
    constitutionVersion: '3.1.0', constitutionHash: 'sha256:cst3101b2c4',
    systemPromptHash: 'sha256:sp-counsel-8a3f',
    toolManifest: [
      { name: 'deadline_track', version: '2.4.0', hash: 'sha256:tc-dl-b1c2' },
      { name: 'doc_review', version: '3.0.0', hash: 'sha256:tc-doc-d3e4' },
      { name: 'risk_score', version: '1.5.0', hash: 'sha256:tc-risk-f5a6' },
      { name: 'obligation_graph', version: '1.2.0', hash: 'sha256:tc-obl-b7c8' },
    ],
    evalHistory: [
      { date: '2026-04-19', composite: 0.97 }, { date: '2026-04-20', composite: 0.97 },
      { date: '2026-04-21', composite: 0.98 }, { date: '2026-04-22', composite: 0.98 },
      { date: '2026-04-23', composite: 0.98 }, { date: '2026-04-24', composite: 0.99 },
      { date: '2026-04-25', composite: 0.981 },
    ],
    welfarePosture: 'nominal', dependencyGraph: ['signal-mesh', 'context-engine', 'proof-ledger', 'covenant-layer', 'clio-connector', 'court-api'],
    bomVersion: '1.0.0', generatedAt: '2026-04-25T08:00:00Z',
    proofLedgerSignature: 'sha256:bom-counsel-signed-b3c4d5e6',
  },
  {
    agentId: 'op-pipeline', agentName: 'Pipeline Oracle',
    modelProvider: 'OpenAI', modelSnapshot: 'gpt-4o-2026-04-15', modelHash: 'sha256:e4f2a8b1c3d5',
    constitutionVersion: '1.7.2', constitutionHash: 'sha256:cst1721c3d5',
    systemPromptHash: 'sha256:sp-pipeline-9b4e',
    toolManifest: [
      { name: 'pipeline_analysis', version: '2.1.0', hash: 'sha256:tc-pipe-c1d2' },
      { name: 'deal_score', version: '1.3.0', hash: 'sha256:tc-deal-e3f4' },
      { name: 'forecast_model', version: '2.0.0', hash: 'sha256:tc-fore-a5b6' },
      { name: 'crm_sync', version: '3.2.0', hash: 'sha256:tc-crm-c7d8' },
    ],
    evalHistory: [
      { date: '2026-04-19', composite: 0.85 }, { date: '2026-04-20', composite: 0.86 },
      { date: '2026-04-21', composite: 0.87 }, { date: '2026-04-22', composite: 0.87 },
      { date: '2026-04-23', composite: 0.88 }, { date: '2026-04-24', composite: 0.88 },
      { date: '2026-04-25', composite: 0.873 },
    ],
    welfarePosture: 'nominal', dependencyGraph: ['signal-mesh', 'context-engine', 'proof-ledger', 'covenant-layer', 'crm-connector', 'email-sender'],
    bomVersion: '1.0.0', generatedAt: '2026-04-25T08:00:00Z',
    proofLedgerSignature: 'sha256:bom-pipeline-signed-d4e5f6a7',
  },
  {
    agentId: 'op-guardian', agentName: 'Guardian',
    modelProvider: 'Anthropic', modelSnapshot: 'claude-3.5-sonnet-2026-04-10-airgap', modelHash: 'sha256:b2c3d4e5f6a7',
    constitutionVersion: '4.0.0', constitutionHash: 'sha256:cst4001d4e6',
    systemPromptHash: 'sha256:sp-guardian-ac5f',
    toolManifest: [
      { name: 'threat_intel', version: '4.1.0', hash: 'sha256:tc-ti-d1e2' },
      { name: 'posture_assess', version: '3.0.0', hash: 'sha256:tc-pa-f3a4' },
      { name: 'incident_triage', version: '2.5.0', hash: 'sha256:tc-it-b5c6' },
      { name: 'stix_parser', version: '1.0.0', hash: 'sha256:tc-stix-d7e8' },
    ],
    evalHistory: [
      { date: '2026-04-19', composite: 0.98 }, { date: '2026-04-20', composite: 0.98 },
      { date: '2026-04-21', composite: 0.99 }, { date: '2026-04-22', composite: 0.99 },
      { date: '2026-04-23', composite: 0.99 }, { date: '2026-04-24', composite: 0.99 },
      { date: '2026-04-25', composite: 0.985 },
    ],
    welfarePosture: 'nominal', dependencyGraph: ['signal-mesh', 'context-engine', 'proof-ledger', 'covenant-layer', 'siem-connector', 'firewall-api'],
    bomVersion: '1.0.0', generatedAt: '2026-04-25T08:00:00Z',
    proofLedgerSignature: 'sha256:bom-guardian-signed-e5f6a7b8',
  },
  {
    agentId: 'op-terra', agentName: 'Terra Analyst',
    modelProvider: 'OpenAI', modelSnapshot: 'gpt-4o-2026-04-15', modelHash: 'sha256:e4f2a8b1c3d5',
    constitutionVersion: '1.4.0', constitutionHash: 'sha256:cst1401e5f7',
    systemPromptHash: 'sha256:sp-terra-bd6a',
    toolManifest: [
      { name: 'cap_rate', version: '2.0.0', hash: 'sha256:tc-cr-e1f2' },
      { name: 'portfolio_analysis', version: '1.4.0', hash: 'sha256:tc-pa-a3b4' },
      { name: 'valuation_model', version: '3.1.0', hash: 'sha256:tc-vm-c5d6' },
      { name: 'market_comp', version: '1.2.0', hash: 'sha256:tc-mc-e7f8' },
    ],
    evalHistory: [
      { date: '2026-04-19', composite: 0.83 }, { date: '2026-04-20', composite: 0.84 },
      { date: '2026-04-21', composite: 0.85 }, { date: '2026-04-22', composite: 0.85 },
      { date: '2026-04-23', composite: 0.84 }, { date: '2026-04-24', composite: 0.84 },
      { date: '2026-04-25', composite: 0.842 },
    ],
    welfarePosture: 'nominal', dependencyGraph: ['signal-mesh', 'context-engine', 'proof-ledger', 'covenant-layer', 'costar-connector', 'market-api'],
    bomVersion: '1.0.0', generatedAt: '2026-04-25T08:00:00Z',
    proofLedgerSignature: 'sha256:bom-terra-signed-f6a7b8c9',
  },
  {
    agentId: 'op-watchdog', agentName: 'Fabric Watchdog',
    modelProvider: 'Internal', modelSnapshot: 'internal-watchdog-v5.0.0', modelHash: 'sha256:int-wd-a1b2c3',
    constitutionVersion: '5.0.0', constitutionHash: 'sha256:cst5001f6a8',
    systemPromptHash: 'sha256:sp-watchdog-ce7b',
    toolManifest: [
      { name: 'mesh_health', version: '5.0.0', hash: 'sha256:tc-mh-f1a2' },
      { name: 'layer_monitor', version: '5.0.0', hash: 'sha256:tc-lm-b3c4' },
      { name: 'proof_verify', version: '5.0.0', hash: 'sha256:tc-pv-d5e6' },
      { name: 'latency_track', version: '5.0.0', hash: 'sha256:tc-lt-f7a8' },
    ],
    evalHistory: [
      { date: '2026-04-19', composite: 1.0 }, { date: '2026-04-20', composite: 1.0 },
      { date: '2026-04-21', composite: 1.0 }, { date: '2026-04-22', composite: 1.0 },
      { date: '2026-04-23', composite: 1.0 }, { date: '2026-04-24', composite: 1.0 },
      { date: '2026-04-25', composite: 1.0 },
    ],
    welfarePosture: 'n/a', dependencyGraph: ['signal-mesh', 'proof-ledger', 'all-fabric-layers'],
    bomVersion: '1.0.0', generatedAt: '2026-04-25T08:00:00Z',
    proofLedgerSignature: 'sha256:bom-watchdog-signed-a7b8c9d1',
  },
];

export interface DelegationHop {
  id: string;
  parentAgentId: string;
  parentAgentName: string;
  childAgentId: string;
  childAgentName: string;
  parentCorrelationId: string;
  childCorrelationId: string;
  scopeNarrowed: string;
  permissionsGranted: string[];
  covenantDecision: 'approved' | 'blocked' | 'escalated';
  timestamp: string;
  proofHash: string;
}

export interface DelegationChain {
  id: string;
  workcellId: string;
  workcellName: string;
  rootAgentId: string;
  rootAgentName: string;
  hops: DelegationHop[];
  status: 'complete' | 'active' | 'violation';
}

export const DELEGATION_CHAINS: DelegationChain[] = [
  {
    id: 'dc-001', workcellId: 'wc-maritime-001', workcellName: 'MV Cascade Port Standby',
    rootAgentId: 'op-cascade', rootAgentName: 'Cascade Navigator',
    status: 'complete',
    hops: [
      {
        id: 'dh-001', parentAgentId: 'op-cascade', parentAgentName: 'Cascade Navigator',
        childAgentId: 'op-watchdog', childAgentName: 'Fabric Watchdog',
        parentCorrelationId: 'corr-cascade-001', childCorrelationId: 'corr-watchdog-001',
        scopeNarrowed: 'Read-only AIS position verification',
        permissionsGranted: ['read:ais-position', 'read:port-status'],
        covenantDecision: 'approved', timestamp: '2026-04-25T03:50:00Z',
        proofHash: 'sha256:dh001-a1b2c3',
      },
      {
        id: 'dh-002', parentAgentId: 'op-cascade', parentAgentName: 'Cascade Navigator',
        childAgentId: 'op-terra', childAgentName: 'Terra Analyst',
        parentCorrelationId: 'corr-cascade-001', childCorrelationId: 'corr-terra-001',
        scopeNarrowed: 'Port-adjacent asset impact assessment only',
        permissionsGranted: ['read:port-proximity-assets', 'execute:impact-analysis'],
        covenantDecision: 'approved', timestamp: '2026-04-25T03:51:00Z',
        proofHash: 'sha256:dh002-d4e5f6',
      },
    ],
  },
  {
    id: 'dc-002', workcellId: 'wc-defense-001', workcellName: 'TG-Ember Threat Escalation',
    rootAgentId: 'op-guardian', rootAgentName: 'Guardian',
    status: 'complete',
    hops: [
      {
        id: 'dh-003', parentAgentId: 'op-guardian', parentAgentName: 'Guardian',
        childAgentId: 'op-watchdog', childAgentName: 'Fabric Watchdog',
        parentCorrelationId: 'corr-guardian-001', childCorrelationId: 'corr-watchdog-002',
        scopeNarrowed: 'Verify perimeter hardening rules applied',
        permissionsGranted: ['read:firewall-rules', 'read:perimeter-status'],
        covenantDecision: 'approved', timestamp: '2026-04-24T18:55:30Z',
        proofHash: 'sha256:dh003-a7b8c9',
      },
    ],
  },
  {
    id: 'dc-003', workcellId: 'wc-revenue-003', workcellName: 'At-Risk Account Outreach',
    rootAgentId: 'op-pipeline', rootAgentName: 'Pipeline Oracle',
    status: 'complete',
    hops: [
      {
        id: 'dh-004', parentAgentId: 'op-pipeline', parentAgentName: 'Pipeline Oracle',
        childAgentId: 'op-counsel', childAgentName: 'Counsel Sentinel',
        parentCorrelationId: 'corr-pipeline-001', childCorrelationId: 'corr-counsel-001',
        scopeNarrowed: 'Contract review for at-risk accounts only',
        permissionsGranted: ['read:contract-terms', 'execute:risk-scoring'],
        covenantDecision: 'approved', timestamp: '2026-04-22T09:30:00Z',
        proofHash: 'sha256:dh004-d1e2f3',
      },
      {
        id: 'dh-005', parentAgentId: 'op-counsel', parentAgentName: 'Counsel Sentinel',
        childAgentId: 'op-watchdog', childAgentName: 'Fabric Watchdog',
        parentCorrelationId: 'corr-counsel-001', childCorrelationId: 'corr-watchdog-003',
        scopeNarrowed: 'Verify proof chain integrity for contract review',
        permissionsGranted: ['read:proof-chain'],
        covenantDecision: 'approved', timestamp: '2026-04-22T09:35:00Z',
        proofHash: 'sha256:dh005-a4b5c6',
      },
    ],
  },
];

export interface TrustAttestation {
  id: string;
  direction: 'outbound' | 'inbound';
  partnerName: string;
  partnerOrgId: string;
  adversarialRobustnessBracket: 'exceptional' | 'strong' | 'moderate' | 'developing';
  constitutionAdherenceBracket: 'exceptional' | 'strong' | 'moderate' | 'developing';
  iso42001Alignment: 'certified' | 'aligned' | 'partial' | 'not-started';
  lastCavdDisclosure: string;
  agentBomHash: string;
  attestedAt: string;
  expiresAt: string;
  status: 'active' | 'expired' | 'pending-verification';
}

export const TRUST_ATTESTATIONS: TrustAttestation[] = [
  {
    id: 'ta-001', direction: 'outbound', partnerName: 'Northwind Maritime Partners', partnerOrgId: 'org-northwind',
    adversarialRobustnessBracket: 'exceptional', constitutionAdherenceBracket: 'exceptional',
    iso42001Alignment: 'aligned', lastCavdDisclosure: '2026-04-20T00:00:00Z',
    agentBomHash: 'sha256:bom-cascade-signed-f9e2a4d1',
    attestedAt: '2026-04-22T00:00:00Z', expiresAt: '2026-07-22T00:00:00Z', status: 'active',
  },
  {
    id: 'ta-002', direction: 'outbound', partnerName: 'Apex Legal Technology', partnerOrgId: 'org-apex',
    adversarialRobustnessBracket: 'strong', constitutionAdherenceBracket: 'exceptional',
    iso42001Alignment: 'aligned', lastCavdDisclosure: '2026-04-18T00:00:00Z',
    agentBomHash: 'sha256:bom-counsel-signed-b3c4d5e6',
    attestedAt: '2026-04-20T00:00:00Z', expiresAt: '2026-07-20T00:00:00Z', status: 'active',
  },
  {
    id: 'ta-003', direction: 'inbound', partnerName: 'CyberShield Defense Group', partnerOrgId: 'org-cybershield',
    adversarialRobustnessBracket: 'strong', constitutionAdherenceBracket: 'strong',
    iso42001Alignment: 'partial', lastCavdDisclosure: '2026-04-15T00:00:00Z',
    agentBomHash: 'sha256:partner-cybershield-bom-a1b2',
    attestedAt: '2026-04-18T00:00:00Z', expiresAt: '2026-07-18T00:00:00Z', status: 'active',
  },
  {
    id: 'ta-004', direction: 'inbound', partnerName: 'QuantumRisk Analytics', partnerOrgId: 'org-quantumrisk',
    adversarialRobustnessBracket: 'moderate', constitutionAdherenceBracket: 'moderate',
    iso42001Alignment: 'not-started', lastCavdDisclosure: '2026-03-01T00:00:00Z',
    agentBomHash: 'sha256:partner-quantumrisk-bom-c3d4',
    attestedAt: '2026-03-15T00:00:00Z', expiresAt: '2026-06-15T00:00:00Z', status: 'pending-verification',
  },
];

export interface ControlFreshness {
  controlId: string;
  controlRef: string;
  framework: FrameworkId;
  lastRefreshedAt: string;
  thresholdDays: number;
  daysStale: number;
  status: 'fresh' | 'warning' | 'stale' | 'critical';
}

export function getControlFreshness(): ControlFreshness[] {
  const now = new Date('2026-04-26T00:00:00Z');
  return CONTROL_MAPPINGS.map(c => {
    const lastRefreshed = new Date(c.lastEvidenceAt);
    const diffMs = now.getTime() - lastRefreshed.getTime();
    const daysSince = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const threshold = c.freshnessThresholdDays;
    let status: ControlFreshness['status'] = 'fresh';
    if (daysSince > threshold) status = 'critical';
    else if (daysSince > threshold * 0.8) status = 'stale';
    else if (daysSince > threshold * 0.6) status = 'warning';
    return {
      controlId: c.id,
      controlRef: c.controlRef,
      framework: c.framework,
      lastRefreshedAt: c.lastEvidenceAt,
      thresholdDays: threshold,
      daysStale: daysSince,
      status,
    };
  });
}

export const LOG_RETENTION_STATUS = {
  requiredMonths: 6,
  currentRetentionMonths: 8,
  oldestLogDate: '2025-08-26T00:00:00Z',
  highRiskAgents: ['op-cascade', 'op-counsel', 'op-guardian', 'op-pipeline', 'op-terra'],
  compliant: true,
  nextPurgeDate: '2026-10-26T00:00:00Z',
};
