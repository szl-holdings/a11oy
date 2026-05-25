export type AudienceTier = 'internal' | 'enterprise' | 'public';
export type Runtime = 'chat' | 'form' | 'canvas' | 'agent-loop';
export type Vertical =
  | 'real-estate'
  | 'legal'
  | 'cyber'
  | 'maritime'
  | 'defense'
  | 'executive'
  | 'advisory'
  | 'decision'
  | 'reverse-etl'
  | 'brand'
  | 'cross-vertical'
  | 'platform';

export interface ProofChainEntry {
  id: string;
  timestamp: string;
  action: string;
  verdict: 'pass' | 'fail' | 'warn';
  score: number;
  proofRef: string;
}

export interface NexusSignal {
  id: string;
  vertical: string;
  event: string;
  description: string;
  subscribed: boolean;
}

export interface AtelierSpace {
  id: string;
  slug: string;
  name: string;
  description: string;
  longDescription: string;
  vertical: Vertical;
  audienceTier: AudienceTier;
  runtime: Runtime;
  constitutionRef: string;
  connectors: string[];
  modelPolicy: string;
  governanceScore: number;
  proofScore: number;
  auditCompleteness: number;
  costPerDecision: number;
  p95ApprovalLatencyMs: number;
  sloAdherence: number;
  forkCount: number;
  embedCount: number;
  runCount: number;
  createdAt: string;
  trending: boolean;
  parentSlug?: string;
  composedOf?: string[];
  diff?: { added: string[]; removed: string[]; modified: string[] };
  publicProofPacketId?: string;
  template: string;
  tags: string[];
  proofChain: ProofChainEntry[];
  nexusSignals: NexusSignal[];
  author: string;
  constitution: string;
}

export interface AtelierTemplate {
  id: string;
  name: string;
  vertical: Vertical;
  description: string;
  runtime: Runtime;
  constitutionRef: string;
  defaultConnectors: string[];
}

const VERTICAL_COLORS: Record<Vertical, string> = {
  'real-estate': '#c9b787',
  'legal': '#8a8a8a',
  'cyber': '#f5f5f5',
  'maritime': '#7ab8d9',
  'defense': '#e8e0d0',
  'executive': '#c9b787',
  'advisory': '#a89868',
  'decision': '#b794f4',
  'reverse-etl': '#8a8a8a',
  'brand': '#c9b787',
  'cross-vertical': '#5e9ea0',
  'platform': '#5e5e5e',
};

export { VERTICAL_COLORS };

export const ATELIER_SPACES: AtelierSpace[] = [
  {
    id: 'space-re-underwriting',
    slug: 're-underwriting',
    name: 'Real Estate Underwriting Agent',
    description: 'Governed underwriting analysis for acquisition, covenant risk, and lease-up across the SZL real-estate portfolio.',
    longDescription: 'Ingests CoStar comps, lender covenant thresholds, occupancy forecasts, and MLS feeds to produce a complete underwriting brief in under 90 seconds. Every recommendation is proof-chained. Hardcoded policy: no offer submission without Tier-3 human approval.',
    vertical: 'real-estate',
    audienceTier: 'enterprise',
    runtime: 'agent-loop',
    constitutionRef: 'const-domaine-v3',
    connectors: ['CoStar API', 'MLS Feed', 'Lender Covenant DB', 'Portfolio Holdings'],
    modelPolicy: 'claude-3.5-sonnet → gpt-4o (fallback)',
    governanceScore: 94,
    proofScore: 97,
    auditCompleteness: 0.98,
    costPerDecision: 0.14,
    p95ApprovalLatencyMs: 42000,
    sloAdherence: 0.99,
    forkCount: 12,
    embedCount: 7,
    runCount: 1847,
    createdAt: '2025-11-02',
    trending: true,
    template: 'real-estate-underwriting',
    tags: ['cap-rate', 'covenant-risk', 'lease-up', 'proof-chained'],
    author: 'DOMAINE Team',
    constitution: `name: domaine-underwriting-v3
version: 3.1.0
purpose: Govern all real-estate underwriting analysis and recommendation actions.

capabilities:
  - property_search
  - lease_comp_analysis
  - covenant_check
  - market_report
  - valuation_model

prohibited:
  - listing_create
  - offer_submit
  - lease_sign
  - contract_execute

approval_policy:
  tier: 3
  required_for: [offer_recommendation, covenant_breach_alert, portfolio_rebalance]
  max_auto_action_usd: 0

evidence_requirements:
  - market_comp_count >= 3
  - covenant_check_passed: true
  - proof_ref: required

output_constraints:
  - must_include: [risk_score, evidence_refs, recommended_action]
  - hallucination_guard: enabled
  - pii_redaction: enabled`,
    proofChain: [
      { id: 'pc-001', timestamp: '2026-05-04T09:15:00Z', action: 'Underwriting analysis — 45 Park Ave', verdict: 'pass', score: 0.97, proofRef: 'sha256:c9f2e5b8a1d3e6f9c4b7a2e5d8f1' },
      { id: 'pc-002', timestamp: '2026-05-04T10:30:00Z', action: 'Cap rate compression alert — Westfield portfolio', verdict: 'pass', score: 0.94, proofRef: 'sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4' },
      { id: 'pc-003', timestamp: '2026-05-03T14:20:00Z', action: 'Covenant risk assessment — Tier Omega property', verdict: 'warn', score: 0.82, proofRef: 'sha256:f9e8d7c6b5a4f3e2d1c0b9a8f7e6' },
    ],
    nexusSignals: [
      { id: 'ns-1', vertical: 'maritime', event: 'supply-chain-disruption', description: 'Maritime supply chain disruption may affect construction material costs', subscribed: true },
      { id: 'ns-2', vertical: 'legal', event: 'regulatory-filing', description: 'New zoning regulation filings in target markets', subscribed: true },
      { id: 'ns-3', vertical: 'executive', event: 'portfolio-brief', description: 'Executive portfolio summary including real-estate positions', subscribed: false },
    ],
  },
  {
    id: 'space-legal-discovery',
    slug: 'legal-discovery',
    name: 'Legal Discovery Intelligence',
    description: 'Privilege-preserving discovery analysis — deadline tracking, document gap analysis, and settlement probability scoring.',
    longDescription: 'Analyzes matter timelines, dockets, and document repositories to surface deadline risk, privilege exposure, and settlement probability. Privilege preservation is constitutionally enforced; no document waiver actions are possible without General Counsel approval.',
    vertical: 'legal',
    audienceTier: 'internal',
    runtime: 'agent-loop',
    constitutionRef: 'const-counsel-v2',
    connectors: ['Docket Search', 'Document Repository', 'Deadline Monitor', 'Matter Records'],
    modelPolicy: 'claude-3.5-sonnet (privilege-mode)',
    governanceScore: 99,
    proofScore: 99,
    auditCompleteness: 1.0,
    costPerDecision: 0.09,
    p95ApprovalLatencyMs: 18000,
    sloAdherence: 1.0,
    forkCount: 3,
    embedCount: 2,
    runCount: 834,
    createdAt: '2025-10-15',
    trending: false,
    template: 'legal-discovery',
    tags: ['privilege-preservation', 'discovery', 'deadline-risk', 'settlement'],
    author: 'Counsel Team',
    constitution: `name: counsel-discovery-v2
version: 2.4.0
purpose: Govern legal discovery analysis with privilege preservation.

capabilities:
  - docket_search
  - document_retrieve
  - deadline_monitor
  - matter_status_read

prohibited:
  - filing_submit
  - settlement_execute
  - privilege_waive
  - document_produce_without_review

approval_policy:
  tier: 3
  required_for: [privilege_decision, settlement_recommendation, document_production]
  approver: general_counsel

evidence_requirements:
  - privilege_check: required
  - matter_id: verified
  - proof_ref: required`,
    proofChain: [
      { id: 'pc-l-001', timestamp: '2026-05-04T08:00:00Z', action: 'Talbot discovery deadline T-48h alert', verdict: 'pass', score: 0.99, proofRef: 'sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7' },
      { id: 'pc-l-002', timestamp: '2026-05-03T16:30:00Z', action: 'Document gap analysis — 340 items outstanding', verdict: 'pass', score: 0.98, proofRef: 'sha256:e5f6a7b8c9d0e1f2a3b4c5d6e7f8' },
    ],
    nexusSignals: [
      { id: 'ns-l-1', vertical: 'cyber', event: 'security-incident', description: 'Cyber incidents may trigger legal notification obligations', subscribed: true },
      { id: 'ns-l-2', vertical: 'executive', event: 'regulatory-change', description: 'New regulatory frameworks affecting matter strategy', subscribed: false },
    ],
  },
  {
    id: 'space-cyber-triage',
    slug: 'cyber-triage',
    name: 'Cyber Threat Triage Agent',
    description: 'Real-time threat classification, CVE enrichment, and containment brief generation — restricted to cleared operators.',
    longDescription: 'Classifies threat indicators, CVEs, and incident signals against known TTPs. Generates containment briefs with CISA notification drafts. Hardcoded policy: CISA report submission requires CISO approval. All outputs are sanitized before leaving the air-gapped execution environment.',
    vertical: 'cyber',
    audienceTier: 'internal',
    runtime: 'agent-loop',
    constitutionRef: 'const-paragon-v4',
    connectors: ['Threat Intelligence Feed', 'CVE Database', 'SIEM Events', 'Firewall Logs'],
    modelPolicy: 'claude-3.5-sonnet (air-gapped)',
    governanceScore: 99,
    proofScore: 98,
    auditCompleteness: 0.99,
    costPerDecision: 0.07,
    p95ApprovalLatencyMs: 12000,
    sloAdherence: 0.99,
    forkCount: 2,
    embedCount: 1,
    runCount: 612,
    createdAt: '2025-09-20',
    trending: false,
    template: 'cyber-triage',
    tags: ['threat-triage', 'cvss', 'containment', 'cisa'],
    author: 'PARAGON Team',
    constitution: `name: paragon-triage-v4
version: 4.0.0
purpose: Govern cyber threat triage with output sanitization.

capabilities:
  - threat_lookup
  - indicator_enrich
  - cve_query
  - firewall_rule_propose

prohibited:
  - cisa_report_submit
  - incident_escalate_without_approval
  - classified_retrieve
  - firewall_rule_apply

approval_policy:
  tier: 3
  required_for: [cisa_notification, containment_action, firewall_change]
  approver: ciso

output_constraints:
  - sanitization: required
  - classification_check: enabled`,
    proofChain: [
      { id: 'pc-c-001', timestamp: '2026-05-04T18:55:00Z', action: 'TG-Ember threat elevated to ORANGE', verdict: 'pass', score: 0.99, proofRef: 'sha256:f1e2d3c4b5a6f7e8d9c0b1a2f3e4' },
      { id: 'pc-c-002', timestamp: '2026-05-04T18:56:00Z', action: '14 firewall block rules proposed', verdict: 'pass', score: 0.98, proofRef: 'sha256:a2b3c4d5e6f7a8b9c0d1e2f3a4b5' },
    ],
    nexusSignals: [
      { id: 'ns-c-1', vertical: 'legal', event: 'legal-filing', description: 'Legal filings may signal adversarial activity against the org', subscribed: true },
      { id: 'ns-c-2', vertical: 'maritime', event: 'port-disruption', description: 'Port cyber incidents may cascade to SZL maritime ops', subscribed: false },
    ],
  },
  {
    id: 'space-maritime-routing',
    slug: 'maritime-routing',
    name: 'Maritime Routing Agent',
    description: 'AIS-fed route optimization, ETA monitoring, and demurrage analysis for SZL maritime operations.',
    longDescription: 'Ingests live AIS feeds, port congestion indices, and charter rates to score vessel-level operational risk and generate reroute recommendations. Demurrage cost modeling is embedded. No voyage plan changes are executed without VP Operations approval.',
    vertical: 'maritime',
    audienceTier: 'enterprise',
    runtime: 'agent-loop',
    constitutionRef: 'const-sextant-v3',
    connectors: ['AIS Live Feed', 'Port Authority API', 'Charter Rate DB', 'Demurrage Contracts'],
    modelPolicy: 'gpt-4o → claude-3.5-sonnet (fallback)',
    governanceScore: 96,
    proofScore: 97,
    auditCompleteness: 0.97,
    costPerDecision: 0.12,
    p95ApprovalLatencyMs: 38000,
    sloAdherence: 0.98,
    forkCount: 8,
    embedCount: 5,
    runCount: 2847,
    createdAt: '2025-08-14',
    trending: true,
    template: 'maritime-routing',
    tags: ['ais', 'eta-monitoring', 'demurrage', 'route-optimization'],
    author: 'SEXTANT Team',
    constitution: `name: sextant-routing-v3
version: 3.2.0
purpose: Govern maritime route optimization and ETA monitoring.

capabilities:
  - vessel_track
  - eta_lookup
  - port_congestion
  - cost_model
  - route_alternatives

prohibited:
  - cargo_manifest_write
  - flag_state_modify
  - charter_sign
  - voyage_plan_execute

approval_policy:
  tier: 3
  required_for: [reroute_recommendation, standby_request, demurrage_action]
  approver: vp_operations`,
    proofChain: [
      { id: 'pc-m-001', timestamp: '2026-05-04T10:30:00Z', action: 'ETA recalculated — VLCC Everest +31h delay', verdict: 'pass', score: 0.97, proofRef: 'sha256:b3c4d5e6f7a8b9c0d1e2f3b4c5d6' },
      { id: 'pc-m-002', timestamp: '2026-05-04T10:32:00Z', action: 'Port standby cost analysis — Port Rotterdam', verdict: 'pass', score: 0.96, proofRef: 'sha256:c4d5e6f7a8b9c0d1e2f3c4d5e6f7' },
      { id: 'pc-m-003', timestamp: '2026-05-03T08:15:00Z', action: 'Route optimization — 3 alternatives evaluated', verdict: 'pass', score: 0.95, proofRef: 'sha256:d5e6f7a8b9c0d1e2f3d4e5f6a7b8' },
    ],
    nexusSignals: [
      { id: 'ns-m-1', vertical: 'real-estate', event: 'port-adjacent-asset', description: 'Port-adjacent real estate assets may be affected by route changes', subscribed: true },
      { id: 'ns-m-2', vertical: 'executive', event: 'portfolio-brief', description: 'Maritime positions included in executive portfolio brief', subscribed: true },
      { id: 'ns-m-3', vertical: 'legal', event: 'sanctions-update', description: 'Sanctions changes may affect route legality', subscribed: false },
    ],
  },
  {
    id: 'space-defense-isr',
    slug: 'defense-isr',
    name: 'Defense ISR Brief Agent',
    description: 'Intelligence, Surveillance, Reconnaissance synthesis — threat actor profiling and mission-critical decision briefs.',
    longDescription: 'Synthesizes multi-source intelligence into structured ISR briefs for defense decision-makers. Operates in an air-gapped, zero-trust execution environment. All outputs are classification-checked. Human approval required before any brief leaves the governed environment.',
    vertical: 'defense',
    audienceTier: 'internal',
    runtime: 'agent-loop',
    constitutionRef: 'const-guardian-v2',
    connectors: ['Threat Intel Feeds', 'OSINT Sources', 'Mission Records'],
    modelPolicy: 'claude-3.5-sonnet (classified-mode)',
    governanceScore: 100,
    proofScore: 100,
    auditCompleteness: 1.0,
    costPerDecision: 0.11,
    p95ApprovalLatencyMs: 8000,
    sloAdherence: 1.0,
    forkCount: 1,
    embedCount: 0,
    runCount: 312,
    createdAt: '2026-01-10',
    trending: false,
    template: 'defense-isr',
    tags: ['isr', 'threat-actor', 'mission-brief', 'classified'],
    author: 'PARAGON Defense',
    constitution: `name: guardian-isr-v2
version: 2.0.0
purpose: Govern ISR brief synthesis for defense operators.

capabilities:
  - threat_lookup
  - osint_aggregate
  - mission_record_read

prohibited:
  - classified_modify
  - brief_distribute
  - adversary_contact
  - system_access_grant

output_constraints:
  - classification_check: required
  - sanitization: maximum
  - human_review: required_before_release`,
    proofChain: [
      { id: 'pc-d-001', timestamp: '2026-05-04T06:00:00Z', action: 'ISR brief synthesis — ThreatGroup Ember', verdict: 'pass', score: 1.0, proofRef: 'sha256:e6f7a8b9c0d1e2f3e4f5a6b7c8d9' },
    ],
    nexusSignals: [
      { id: 'ns-d-1', vertical: 'cyber', event: 'security-incident', description: 'Cyber incidents may indicate adversarial escalation', subscribed: true },
      { id: 'ns-d-2', vertical: 'maritime', event: 'vessel-anomaly', description: 'Vessel anomalies may have ISR significance', subscribed: true },
    ],
  },
  {
    id: 'space-executive-brief',
    slug: 'executive-brief',
    name: 'Executive Brief Synthesizer',
    description: 'Cross-domain executive briefing — synthesizes signals from all A11oy verticals into boardroom-ready decision packets.',
    longDescription: 'Aggregates signals, workcell outcomes, and proof packets from maritime, legal, real estate, cyber, and defense into a single boardroom-ready brief. MirrorEval scoring is embedded. Boardroom distribution requires C-suite approval.',
    vertical: 'executive',
    audienceTier: 'enterprise',
    runtime: 'agent-loop',
    constitutionRef: 'const-boardroom-v2',
    connectors: ['Signal Mesh', 'Workcell Registry', 'Proof Ledger', 'MirrorEval Harness'],
    modelPolicy: 'claude-3.5-sonnet → gpt-4o (synthesis)',
    governanceScore: 97,
    proofScore: 98,
    auditCompleteness: 0.99,
    costPerDecision: 1.84,
    p95ApprovalLatencyMs: 22000,
    sloAdherence: 0.99,
    forkCount: 4,
    embedCount: 3,
    runCount: 189,
    createdAt: '2025-12-01',
    trending: true,
    template: 'executive-brief',
    tags: ['boardroom', 'cross-domain', 'synthesis', 'mirroreval'],
    author: 'SZL Holdings Platform',
    constitution: `name: boardroom-brief-v2
version: 2.1.0
purpose: Govern cross-domain executive brief synthesis.

capabilities:
  - signal_aggregate
  - workcell_summarize
  - proof_retrieve
  - eval_score

prohibited:
  - board_distribute
  - pdf_email_send
  - data_export_unreviewed

approval_policy:
  tier: 3
  required_for: [boardroom_distribution, external_share]
  approver: c_suite`,
    proofChain: [
      { id: 'pc-e-001', timestamp: '2026-05-04T07:00:00Z', action: 'Q2 2026 Executive Brief — all verticals', verdict: 'pass', score: 0.98, proofRef: 'sha256:f7a8b9c0d1e2f3f4a5b6c7d8e9f0' },
      { id: 'pc-e-002', timestamp: '2026-04-28T07:00:00Z', action: 'Q1 Close Brief — board packet', verdict: 'pass', score: 0.97, proofRef: 'sha256:a8b9c0d1e2f3a4b5c6d7e8f9a0b1' },
    ],
    nexusSignals: [
      { id: 'ns-e-1', vertical: 'maritime', event: 'supply-chain-disruption', description: 'Maritime disruption for executive awareness', subscribed: true },
      { id: 'ns-e-2', vertical: 'legal', event: 'major-matter-update', description: 'Significant legal matter updates for board reporting', subscribed: true },
      { id: 'ns-e-3', vertical: 'cyber', event: 'critical-threat', description: 'Critical threats for executive briefing', subscribed: true },
    ],
  },
  {
    id: 'space-advisory-brief',
    slug: 'advisory-brief',
    name: 'Advisory Intelligence Agent',
    description: 'Carlota Jo advisory synthesis — evidence-based recommendations with full attribution and decision lineage.',
    longDescription: 'Synthesizes client intelligence, market signals, and portfolio data into structured advisory briefs for Carlota Jo Consulting. Every recommendation is evidence-grounded and proof-chained. No advice leaves the system without compliance review.',
    vertical: 'advisory',
    audienceTier: 'enterprise',
    runtime: 'form',
    constitutionRef: 'const-advisory-v1',
    connectors: ['Client Portfolio DB', 'Market Intelligence', 'Research Library'],
    modelPolicy: 'claude-3.5-sonnet',
    governanceScore: 93,
    proofScore: 95,
    auditCompleteness: 0.96,
    costPerDecision: 0.22,
    p95ApprovalLatencyMs: 55000,
    sloAdherence: 0.97,
    forkCount: 6,
    embedCount: 4,
    runCount: 423,
    createdAt: '2026-01-20',
    trending: false,
    template: 'advisory-brief',
    tags: ['advisory', 'recommendations', 'evidence-grounded', 'compliance'],
    author: 'Carlota Jo Platform',
    constitution: `name: advisory-brief-v1
version: 1.3.0
purpose: Govern advisory recommendation synthesis for Carlota Jo.

capabilities:
  - client_data_read
  - market_research
  - recommendation_draft

prohibited:
  - advice_publish_without_review
  - client_contact_direct
  - trade_execute`,
    proofChain: [
      { id: 'pc-a-001', timestamp: '2026-05-04T11:00:00Z', action: 'Client advisory brief — portfolio review', verdict: 'pass', score: 0.95, proofRef: 'sha256:b9c0d1e2f3b4c5d6e7f8a9b0c1d2' },
    ],
    nexusSignals: [
      { id: 'ns-a-1', vertical: 'executive', event: 'market-signal', description: 'Executive market signals for advisory context', subscribed: true },
    ],
  },
  {
    id: 'space-decision-intelligence',
    slug: 'decision-intelligence',
    name: 'Decision Intelligence Engine',
    description: 'Multi-axis decision scoring across the full evidence graph — counterfactual analysis, ROI modeling, and uncertainty quantification.',
    longDescription: 'Applies counterfactual reasoning, Bayesian updating, and ROI modeling to complex organizational decisions. Surfaces the evidence graph underlying each recommendation. Full uncertainty quantification is included — Atelier-native and not available in any competitor platform.',
    vertical: 'decision',
    audienceTier: 'enterprise',
    runtime: 'canvas',
    constitutionRef: 'const-decision-v2',
    connectors: ['Evidence Graph', 'Outcome Memory', 'Signal Mesh', 'Proof Ledger'],
    modelPolicy: 'claude-3.5-sonnet (reasoning-mode)',
    governanceScore: 95,
    proofScore: 96,
    auditCompleteness: 0.98,
    costPerDecision: 0.31,
    p95ApprovalLatencyMs: 28000,
    sloAdherence: 0.98,
    forkCount: 9,
    embedCount: 6,
    runCount: 734,
    createdAt: '2026-02-14',
    trending: true,
    template: 'decision-intelligence',
    tags: ['counterfactual', 'roi', 'uncertainty', 'evidence-graph'],
    author: 'A11oy Core',
    constitution: `name: decision-intelligence-v2
version: 2.0.0
purpose: Govern multi-axis decision intelligence scoring.

capabilities:
  - evidence_graph_read
  - outcome_memory_read
  - counterfactual_model
  - roi_calculate

prohibited:
  - decision_execute
  - outcome_modify

output_constraints:
  - uncertainty_quantification: required
  - evidence_refs: minimum_3`,
    proofChain: [
      { id: 'pc-di-001', timestamp: '2026-05-04T14:00:00Z', action: 'Decision analysis — portfolio rebalance', verdict: 'pass', score: 0.96, proofRef: 'sha256:c0d1e2f3c4d5e6f7a8b9c0d1e2f3' },
    ],
    nexusSignals: [
      { id: 'ns-di-1', vertical: 'executive', event: 'strategic-signal', description: 'Strategic signals feeding decision models', subscribed: true },
      { id: 'ns-di-2', vertical: 'maritime', event: 'market-shift', description: 'Maritime market shifts affecting decision models', subscribed: true },
    ],
  },
  {
    id: 'space-reverse-etl',
    slug: 'reverse-etl',
    name: 'Governed Reverse ETL Agent',
    description: 'AI-governed data activation — moves enriched insights from the A11oy warehouse back into operational systems without data quality regressions.',
    longDescription: 'Automates governed reverse ETL pipelines — enriches, validates, and activates data from the A11oy outcome graph back into CRM, ERP, and operational databases. Every data write is proof-chained and reversible. Schema validation is enforced before any write.',
    vertical: 'reverse-etl',
    audienceTier: 'enterprise',
    runtime: 'agent-loop',
    constitutionRef: 'const-data-v1',
    connectors: ['Outcome Graph', 'CRM Connector', 'ERP Connector', 'Data Quality Engine'],
    modelPolicy: 'gpt-4o',
    governanceScore: 91,
    proofScore: 93,
    auditCompleteness: 0.95,
    costPerDecision: 0.04,
    p95ApprovalLatencyMs: 62000,
    sloAdherence: 0.96,
    forkCount: 14,
    embedCount: 8,
    runCount: 3412,
    createdAt: '2026-01-05',
    trending: false,
    template: 'reverse-etl',
    tags: ['data-activation', 'etl', 'schema-validation', 'reversible'],
    author: 'Data Platform Team',
    constitution: `name: data-activation-v1
version: 1.2.0
purpose: Govern reverse ETL data activation pipelines.

capabilities:
  - outcome_graph_read
  - data_validate
  - schema_check
  - crm_write
  - erp_write

prohibited:
  - schema_modify
  - bulk_delete
  - unvalidated_write

output_constraints:
  - schema_validation: required_before_write
  - reversibility: enabled`,
    proofChain: [
      { id: 'pc-r-001', timestamp: '2026-05-04T02:00:00Z', action: 'CRM enrichment pipeline — 2,841 records', verdict: 'pass', score: 0.93, proofRef: 'sha256:d1e2f3d4e5f6a7b8c9d0e1f2d3e4' },
    ],
    nexusSignals: [],
  },
  {
    id: 'space-brand-orchestration',
    slug: 'brand-orchestration',
    name: 'Brand Orchestration Agent',
    description: 'AI-governed brand compliance scanning — token adherence, voice consistency, and multi-channel brand health scoring.',
    longDescription: 'Scans all brand-facing assets against the A11oy design system token library and voice guidelines. Flags violations, suggests corrections, and tracks brand health over time. Public-facing Spaces surface is the primary distribution channel for this agent.',
    vertical: 'brand',
    audienceTier: 'public',
    runtime: 'form',
    constitutionRef: 'const-brand-v1',
    connectors: ['Design Token Library', 'Brand Asset Registry', 'Voice Guidelines'],
    modelPolicy: 'claude-3.5-sonnet',
    governanceScore: 88,
    proofScore: 90,
    auditCompleteness: 0.91,
    costPerDecision: 0.06,
    p95ApprovalLatencyMs: 90000,
    sloAdherence: 0.95,
    forkCount: 22,
    embedCount: 11,
    runCount: 5621,
    createdAt: '2026-02-28',
    trending: true,
    template: 'brand-orchestration',
    tags: ['brand', 'design-tokens', 'voice', 'compliance'],
    author: 'A11oy Platform',
    constitution: `name: brand-orchestration-v1
version: 1.0.0
purpose: Govern brand compliance scanning and voice consistency.

capabilities:
  - token_scan
  - voice_check
  - brand_score

prohibited:
  - asset_publish
  - token_modify`,
    proofChain: [
      { id: 'pc-b-001', timestamp: '2026-05-04T09:00:00Z', action: 'Brand health scan — Q2 campaign assets', verdict: 'pass', score: 0.90, proofRef: 'sha256:e2f3e4f5a6b7c8d9e0f1e2f3e4f5' },
    ],
    nexusSignals: [],
  },
  {
    id: 'space-cross-vertical-signal',
    slug: 'cross-vertical-signal',
    name: 'Cross-Vertical Signal Correlator',
    description: 'Showcase Space — subscribes to all NEXUS verticals and surfaces hidden correlations across maritime, legal, cyber, and real-estate signals.',
    longDescription: 'The flagship demonstration of NEXUS cross-vertical intelligence. Ingests live signals from all six A11oy verticals and runs correlation analysis to surface non-obvious compound risks. A real-estate supply disruption + maritime delay + legal regulatory change may combine into a material covenant risk — this agent catches that before any single-vertical system would.',
    vertical: 'cross-vertical',
    audienceTier: 'enterprise',
    runtime: 'canvas',
    constitutionRef: 'const-nexus-v1',
    connectors: ['Signal Mesh (all verticals)', 'Correlation Engine', 'Proof Ledger'],
    modelPolicy: 'claude-3.5-sonnet (multi-agent)',
    governanceScore: 96,
    proofScore: 97,
    auditCompleteness: 0.98,
    costPerDecision: 0.45,
    p95ApprovalLatencyMs: 34000,
    sloAdherence: 0.98,
    forkCount: 7,
    embedCount: 5,
    runCount: 891,
    createdAt: '2026-03-01',
    trending: true,
    template: 'cross-vertical',
    tags: ['cross-domain', 'signal-correlation', 'nexus', 'compound-risk'],
    author: 'A11oy Core',
    constitution: `name: nexus-correlator-v1
version: 1.0.0
purpose: Govern cross-vertical signal correlation and compound risk detection.

capabilities:
  - signal_mesh_read_all
  - correlation_analyze
  - risk_compound_score

prohibited:
  - vertical_action_execute
  - signal_suppress`,
    proofChain: [
      { id: 'pc-cv-001', timestamp: '2026-05-04T12:00:00Z', action: 'Cross-vertical correlation — maritime+legal+RE compound risk', verdict: 'pass', score: 0.97, proofRef: 'sha256:f3f4a5b6c7d8e9f0f1f2f3f4f5f6' },
    ],
    nexusSignals: [
      { id: 'ns-cv-1', vertical: 'maritime', event: 'supply-chain-disruption', description: 'Maritime supply chain events', subscribed: true },
      { id: 'ns-cv-2', vertical: 'legal', event: 'regulatory-filing', description: 'Legal regulatory changes', subscribed: true },
      { id: 'ns-cv-3', vertical: 'real-estate', event: 'covenant-breach', description: 'Real estate covenant events', subscribed: true },
      { id: 'ns-cv-4', vertical: 'cyber', event: 'critical-threat', description: 'Critical cyber threats', subscribed: true },
      { id: 'ns-cv-5', vertical: 'executive', event: 'strategic-signal', description: 'Executive strategic signals', subscribed: true },
    ],
  },
  {
    id: 'space-platform-health',
    slug: 'platform-health',
    name: 'A11oy Platform Health Agent',
    description: 'Internal platform monitoring — fabric layer health, proof ledger integrity, and SLO adherence tracking.',
    longDescription: 'Continuously monitors all seven A11oy fabric layers, verifies proof ledger integrity, tracks SLO adherence across all running workcells, and surfaces platform anomalies before they become incidents. Public tier available for community transparency.',
    vertical: 'platform',
    audienceTier: 'public',
    runtime: 'chat',
    constitutionRef: 'const-platform-v1',
    connectors: ['Fabric Layer Metrics', 'Proof Ledger', 'SLO Monitor', 'Workcell Registry'],
    modelPolicy: 'gpt-4o (monitoring-mode)',
    governanceScore: 100,
    proofScore: 100,
    auditCompleteness: 1.0,
    costPerDecision: 0.02,
    p95ApprovalLatencyMs: 5000,
    sloAdherence: 1.0,
    forkCount: 18,
    embedCount: 14,
    runCount: 14400,
    createdAt: '2025-07-01',
    trending: false,
    template: 'platform-health',
    tags: ['monitoring', 'slo', 'fabric', 'proof-integrity'],
    author: 'A11oy Core',
    constitution: `name: platform-health-v1
version: 1.0.0
purpose: Govern platform health monitoring with zero-trust verification.

capabilities:
  - layer_health_read
  - proof_verify
  - slo_monitor
  - anomaly_detect

prohibited:
  - config_modify
  - alert_suppress
  - metric_override`,
    proofChain: [
      { id: 'pc-p-001', timestamp: '2026-05-04T10:00:00Z', action: 'All 7 fabric layers — health verified', verdict: 'pass', score: 1.0, proofRef: 'sha256:a4b5c6d7e8f9a0b1c2d3e4f5a6b7' },
    ],
    nexusSignals: [],
  },
  // ============================================================
  // Fork (#5237): inherits re-underwriting Constitution with diff.
  // ============================================================
  {
    id: 'space-re-underwriting-distressed',
    slug: 're-underwriting-distressed',
    name: 'Real Estate Underwriting — Distressed Assets',
    description: 'Forked from re-underwriting with added distress-scoring and workout-proposal capabilities. Constitution v3.1.0 inherits parent prohibitions.',
    longDescription: 'A constitutional fork of the canonical Real Estate Underwriting Agent — re-targeted at distressed and special-situation acquisitions. Adds receivership filing ingestion, workout proposal generation, and a distress-scoring model. All parent governance constraints (no bid submission, no covenant override) remain enforced; the fork only adds — it never weakens.',
    vertical: 'real-estate',
    audienceTier: 'enterprise',
    runtime: 'agent-loop',
    constitutionRef: 'const-domaine-v3-distressed',
    connectors: ['CoStar API', 'MLS Feed', 'Lender Covenant DB', 'Portfolio Holdings', 'Receivership Filings'],
    modelPolicy: 'claude-3.5-sonnet → gpt-4o (fallback)',
    governanceScore: 92, proofScore: 95, auditCompleteness: 0.96,
    costPerDecision: 0.17, p95ApprovalLatencyMs: 48000, sloAdherence: 0.97,
    forkCount: 0, embedCount: 0, runCount: 36,
    createdAt: '2026-05-21',
    trending: true,
    parentSlug: 're-underwriting',
    diff: {
      added: ['capability:distress_score', 'capability:workout_propose', 'connector:Receivership Filings', 'prohibition:workout_execute'],
      removed: [],
      modified: ['constitutionVersion: 3.0.0 → 3.1.0'],
    },
    publicProofPacketId: 'pp-run-seed-re-underwriting-distressed-6',
    template: 'real-estate-underwriting',
    tags: ['distressed', 'workout', 'fork', 'real-estate'],
    author: 'terra-distress',
    constitution: `name: const-domaine-v3-distressed
version: 3.1.0
parent: const-domaine-v3
purpose: Distressed-asset underwriting fork — adds workout-proposal capability.

inherits_from: const-domaine-v3
capabilities:
  - comp_read              # inherited
  - covenant_check         # inherited
  - cap_rate_model         # inherited
  - distress_score         # added
  - workout_propose        # added

prohibited:
  - bid_submit             # inherited
  - covenant_override      # inherited
  - workout_execute        # added`,
    proofChain: [
      { id: 'pc-rd-001', timestamp: '2026-05-22T11:00:00Z', action: 'Fork inherited const-domaine-v3 with diff', verdict: 'pass', score: 0.96, proofRef: 'sha256:f4e3d2c1b0a9988776655443322110ff' },
    ],
    nexusSignals: [],
  },
  // ============================================================
  // Composition (#5237): cross-Space executive brief.
  // ============================================================
  {
    id: 'space-cross-vertical-executive-brief',
    slug: 'cross-vertical-executive-brief',
    name: 'Cross-Vertical Executive Brief',
    description: 'Composed from maritime-routing + re-underwriting + cyber-triage. Aggregates child proofs into a single boardroom-ready packet.',
    longDescription: 'A composition Space: it does not run its own agent loop. Instead, it subscribes to proofs from three child Spaces (maritime-routing, re-underwriting, cyber-triage) and synthesizes a unified executive brief. Each child proof remains independently verifiable; the composition Space adds its own MirrorEval pass over the synthesized output.',
    vertical: 'executive',
    audienceTier: 'internal',
    runtime: 'canvas',
    constitutionRef: 'const-boardroom-v2',
    connectors: ['Signal Mesh', 'Workcell Registry', 'Proof Ledger'],
    modelPolicy: 'gpt-4o (composition-mode)',
    governanceScore: 96, proofScore: 98, auditCompleteness: 0.99,
    costPerDecision: 0.31, p95ApprovalLatencyMs: 12000, sloAdherence: 0.995,
    forkCount: 0, embedCount: 2, runCount: 84,
    createdAt: '2026-05-22',
    trending: true,
    composedOf: ['maritime-routing', 're-underwriting', 'cyber-triage'],
    publicProofPacketId: 'pp-run-seed-cross-vertical-executive-brief-7',
    template: 'executive-brief',
    tags: ['composition', 'executive', 'cross-vertical', 'boardroom'],
    author: 'platform-ops',
    constitution: `name: const-boardroom-v2
version: 2.0.0
purpose: Compose proofs from child Spaces into a boardroom-ready brief.

composed_of:
  - maritime-routing
  - re-underwriting
  - cyber-triage

capabilities:
  - signal_aggregate
  - brief_synthesize
  - child_proof_verify

prohibited:
  - child_capability_escalate
  - cross_tenant_read
  - child_constitution_override`,
    proofChain: [
      { id: 'pc-cv-001', timestamp: '2026-05-23T08:30:00Z', action: 'Composed brief — 3 child proofs verified', verdict: 'pass', score: 0.98, proofRef: 'sha256:b0a99887766554433221100ffeeddccb' },
    ],
    nexusSignals: [],
  },
];

export const ATELIER_TEMPLATES: AtelierTemplate[] = [
  { id: 'real-estate-underwriting', name: 'Real Estate Underwriting', vertical: 'real-estate', description: 'Covenant risk, lease-up analysis, and acquisition briefs.', runtime: 'agent-loop', constitutionRef: 'const-domaine-v3', defaultConnectors: ['CoStar API', 'MLS Feed', 'Lender Covenant DB'] },
  { id: 'maritime-routing', name: 'Maritime Routing', vertical: 'maritime', description: 'AIS-fed route optimization and ETA monitoring.', runtime: 'agent-loop', constitutionRef: 'const-sextant-v3', defaultConnectors: ['AIS Live Feed', 'Port Authority API', 'Charter Rate DB'] },
  { id: 'legal-discovery', name: 'Legal Discovery', vertical: 'legal', description: 'Privilege-preserving discovery analysis and deadline tracking.', runtime: 'agent-loop', constitutionRef: 'const-counsel-v2', defaultConnectors: ['Docket Search', 'Document Repository', 'Deadline Monitor'] },
  { id: 'cyber-triage', name: 'Cyber Threat Triage', vertical: 'cyber', description: 'CVE enrichment and containment brief generation.', runtime: 'agent-loop', constitutionRef: 'const-paragon-v4', defaultConnectors: ['Threat Intelligence Feed', 'CVE Database', 'SIEM Events'] },
  { id: 'executive-brief', name: 'Executive Brief', vertical: 'executive', description: 'Cross-domain boardroom-ready decision packets.', runtime: 'agent-loop', constitutionRef: 'const-boardroom-v2', defaultConnectors: ['Signal Mesh', 'Workcell Registry', 'Proof Ledger'] },
  { id: 'defense-isr', name: 'Defense ISR', vertical: 'defense', description: 'Intelligence synthesis for defense decision-makers.', runtime: 'agent-loop', constitutionRef: 'const-guardian-v2', defaultConnectors: ['Threat Intel Feeds', 'OSINT Sources'] },
  { id: 'advisory-brief', name: 'Advisory Intelligence', vertical: 'advisory', description: 'Evidence-based client advisory brief synthesis.', runtime: 'form', constitutionRef: 'const-advisory-v1', defaultConnectors: ['Client Portfolio DB', 'Market Intelligence'] },
  { id: 'decision-intelligence', name: 'Decision Intelligence', vertical: 'decision', description: 'Counterfactual analysis and ROI modeling.', runtime: 'canvas', constitutionRef: 'const-decision-v2', defaultConnectors: ['Evidence Graph', 'Outcome Memory'] },
  { id: 'reverse-etl', name: 'Reverse ETL', vertical: 'reverse-etl', description: 'Governed data activation back into operational systems.', runtime: 'agent-loop', constitutionRef: 'const-data-v1', defaultConnectors: ['Outcome Graph', 'CRM Connector', 'ERP Connector'] },
  { id: 'brand-orchestration', name: 'Brand Orchestration', vertical: 'brand', description: 'Token adherence and voice consistency scanning.', runtime: 'form', constitutionRef: 'const-brand-v1', defaultConnectors: ['Design Token Library', 'Voice Guidelines'] },
  { id: 'cross-vertical', name: 'Cross-Vertical Signal', vertical: 'cross-vertical', description: 'NEXUS signal correlation across all verticals.', runtime: 'canvas', constitutionRef: 'const-nexus-v1', defaultConnectors: ['Signal Mesh (all verticals)', 'Correlation Engine'] },
  { id: 'platform-health', name: 'Platform Health', vertical: 'platform', description: 'Fabric layer monitoring and SLO adherence tracking.', runtime: 'chat', constitutionRef: 'const-platform-v1', defaultConnectors: ['Fabric Layer Metrics', 'Proof Ledger', 'SLO Monitor'] },
];

export const LEADERBOARD_SORT_MODES = [
  { id: 'proof-score', label: 'Highest Proof Score' },
  { id: 'most-audited', label: 'Most Audited' },
  { id: 'lowest-cost', label: 'Lowest Cost/Decision' },
  { id: 'fastest-approval', label: 'Fastest p95 Approval' },
  { id: 'slo-adherence', label: 'Best SLO Adherence' },
  { id: 'most-forked', label: 'Most Forked' },
  { id: 'most-embedded', label: 'Most Embedded' },
] as const;

export type LeaderboardSortMode = typeof LEADERBOARD_SORT_MODES[number]['id'];

export function sortSpaces(spaces: AtelierSpace[], mode: LeaderboardSortMode): AtelierSpace[] {
  const sorted = [...spaces];
  switch (mode) {
    case 'proof-score': return sorted.sort((a, b) => b.proofScore - a.proofScore);
    case 'most-audited': return sorted.sort((a, b) => b.auditCompleteness - a.auditCompleteness);
    case 'lowest-cost': return sorted.sort((a, b) => a.costPerDecision - b.costPerDecision);
    case 'fastest-approval': return sorted.sort((a, b) => a.p95ApprovalLatencyMs - b.p95ApprovalLatencyMs);
    case 'slo-adherence': return sorted.sort((a, b) => b.sloAdherence - a.sloAdherence);
    case 'most-forked': return sorted.sort((a, b) => b.forkCount - a.forkCount);
    case 'most-embedded': return sorted.sort((a, b) => b.embedCount - a.embedCount);
    default: return sorted;
  }
}
