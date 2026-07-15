// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — artifacts/a11oy/src/data/blueprint.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { DOMAIN_PROFILES } from '@szl-holdings/domain-profiles';

export const SEVEN_PRINCIPLES = [
  {
    step: '01',
    label: 'Ingest',
    glyph: '↓',
    desc: 'Ingest data from multiple systems — market feeds, IoT telemetry, document streams, API webhooks — and unify them into a business ontology.',
  },
  {
    step: '02',
    label: 'Understand',
    glyph: '◉',
    desc: 'Interpret signals and goals using domain intelligence and context memory. Build causal graphs that answer why, not just what.',
  },
  {
    step: '03',
    label: 'Plan',
    glyph: '⬡',
    desc: 'A planner agent decomposes objectives into steps and assigns them to specialized operators — research, execution, risk, and verification.',
  },
  {
    step: '04',
    label: 'Act',
    glyph: '→',
    desc: 'Execution agents call tools and services via the tool fabric. Every call requires proper permissions. Sensitive actions require human approval.',
  },
  {
    step: '05',
    label: 'Verify',
    glyph: '✓',
    desc: 'Verifier agents ensure tasks executed successfully and match expected business outcomes before the proof chain is closed.',
  },
  {
    step: '06',
    label: 'Audit',
    glyph: '◆',
    desc: 'The Proof Chain logs each step, tool call, approval, and result in an immutable, queryable record built for compliance.',
  },
  {
    step: '07',
    label: 'Learn',
    glyph: '↻',
    desc: 'Outcome memory captures what worked and what did not — feeding calibrated confidence back to the next cycle.',
  },
] as const;

export type PrincipleLabel = typeof SEVEN_PRINCIPLES[number]['label'];

export const PRINCIPLE_LABELS: PrincipleLabel[] = SEVEN_PRINCIPLES.map(p => p.label);

export const BLUEPRINT_COMPONENTS = [
  {
    id: 'agent-runtime',
    name: 'Agent Runtime',
    purpose: "Manages every agent's identity, state, memory, reasoning trace, task lifecycle, and audit logs — the central orchestration engine.",
    principles: ['Plan', 'Act', 'Audit'] as PrincipleLabel[],
    adjacent: ['Agent Roles', 'Orchestration', 'Agent Identity'],
    category: 'Core' as const,
  },
  {
    id: 'business-ontology',
    name: 'Business Ontology',
    purpose: 'A domain-specific model of objects, events, roles, policies, and outcomes that provides meaning to data and actions across verticals.',
    principles: ['Ingest', 'Understand'] as PrincipleLabel[],
    adjacent: ['Tool Fabric', 'Memory', 'Agent Runtime'],
    category: 'Intelligence' as const,
  },
  {
    id: 'tool-fabric',
    name: 'Tool Fabric',
    purpose: 'Standardized connectors to enterprise systems with input/output schemas, permission requirements, risk levels, approval requirements, and rollback options.',
    principles: ['Act', 'Audit'] as PrincipleLabel[],
    adjacent: ['Business Ontology', 'Human-in-the-Loop', 'Agent Runtime'],
    category: 'Execution' as const,
  },
  {
    id: 'human-in-the-loop',
    name: 'Human-in-the-Loop',
    purpose: 'Human approvals are first-class. Agents recommend; humans approve, edit, or reject. Approval gates pause execution and persist state for safe resumption.',
    principles: ['Act', 'Verify'] as PrincipleLabel[],
    adjacent: ['Tool Fabric', 'Durable Execution', 'Command Surface'],
    category: 'Governance' as const,
  },
  {
    id: 'durable-execution',
    name: 'Durable Execution',
    purpose: 'Workflows persist state, survive interruptions, and resume from the last checkpoint. Agents cannot lose progress across long-running tasks.',
    principles: ['Act', 'Verify'] as PrincipleLabel[],
    adjacent: ['Human-in-the-Loop', 'Agent Runtime', 'Evaluation'],
    category: 'Execution' as const,
  },
  {
    id: 'agent-roles',
    name: 'Agent Roles',
    purpose: 'Specialized agents — planner, research, execution, verifier, risk, narrative, audit — each with defined scope, tool access, and handoff contracts.',
    principles: ['Plan', 'Act', 'Verify'] as PrincipleLabel[],
    adjacent: ['Agent Runtime', 'Agent Identity', 'Orchestration'],
    category: 'Core' as const,
  },
  {
    id: 'evaluation',
    name: 'Evaluation',
    purpose: 'An evaluation harness that scores agents on accuracy, success rate, hallucination rate, approval compliance, cost, and outcome quality.',
    principles: ['Verify', 'Learn'] as PrincipleLabel[],
    adjacent: ['Durable Execution', 'Memory', 'Agent Runtime'],
    category: 'Intelligence' as const,
  },
  {
    id: 'memory',
    name: 'Memory',
    purpose: 'Layered memory: short-term task context, long-term preferences, business memory (accounts, vendors, policies), outcome memory, and institutional patterns.',
    principles: ['Understand', 'Learn'] as PrincipleLabel[],
    adjacent: ['Business Ontology', 'Evaluation', 'Agent Runtime'],
    category: 'Intelligence' as const,
  },
  {
    id: 'agent-identity',
    name: 'Agent Identity',
    purpose: 'Each agent has identity, role, permissions, allowed tools, risk level, approval threshold, and full audit trail — enforced at the platform layer.',
    principles: ['Audit', 'Plan'] as PrincipleLabel[],
    adjacent: ['Agent Roles', 'Agent Runtime', 'Tool Fabric'],
    category: 'Governance' as const,
  },
  {
    id: 'command-surface',
    name: 'Command Surface',
    purpose: 'The operator interface: signal timeline, agent queue, pending approvals, recommended actions, evidence panel, confidence scores, and execution logs.',
    principles: ['Understand', 'Act', 'Audit'] as PrincipleLabel[],
    adjacent: ['Human-in-the-Loop', 'Orchestration', 'Agent Runtime'],
    category: 'Core' as const,
  },
  {
    id: 'orchestration',
    name: 'Orchestration',
    purpose: 'Multi-agent coordination justified by cross-domain tasks or distinct security boundaries — specialization, scalability, maintainability, and optimization.',
    principles: ['Plan', 'Act'] as PrincipleLabel[],
    adjacent: ['Agent Runtime', 'Agent Roles', 'Command Surface'],
    category: 'Execution' as const,
  },
] as const;

export const IMPLEMENTATION_PRIORITIES = [
  { num: '01', name: 'Agent Registry', desc: 'Roles, permissions, and risk classification for every agent in the system.' },
  { num: '02', name: 'Tool Fabric', desc: 'Schemas, permissions, logging, and approval rules for every connector.' },
  { num: '03', name: 'Proof Chain', desc: 'Record every recommendation, source, tool call, approval, and result.' },
  { num: '04', name: 'Outcome Graph', desc: 'Link actions to real-world business outcomes for closed-loop learning.' },
  { num: '05', name: 'Human Approval Queue', desc: 'Approval, rejection, editing, escalation, and evidence requests.' },
  { num: '06', name: 'Verifier Agent', desc: 'Ensure tasks complete successfully before closing the proof chain.' },
  { num: '07', name: 'Evaluation Harness', desc: 'Regression testing and continuous monitoring for every agent.' },
  { num: '08', name: 'Command Surface UI', desc: 'Operator-facing interface for signal, approval, and execution management.' },
] as const;

export type ApplicationStatus = 'operational' | 'in-development' | 'planned';
export type ApplicationSector = 'Maritime' | 'Legal' | 'Real Estate' | 'Defense & Security' | 'Cyber' | 'Revenue' | 'Operations' | 'Consulting' | 'AI Infrastructure' | 'Infrastructure' | 'Crisis' | 'Intelligence';

export interface ApplicationEntry {
  id: string;
  name: string;
  vertical: string;
  sector: ApplicationSector;
  status: ApplicationStatus;
  tier: string;
  description: string;
  icon: string;
  color: string;
  principles: PrincipleLabel[];
  registryProfileId?: string;
}

export const APPLICATIONS: ApplicationEntry[] = [
  {
    id: 'vessels', name: 'Vessels', vertical: 'Maritime', sector: 'Maritime',
    status: 'operational', tier: 'Enterprise',
    description: DOMAIN_PROFILES.vessels.description + ' AIS ingestion, voyage economics, port scheduling, demurrage risk, and sanctions screening.',
    icon: '⚓', color: '#8a8a8a',
    principles: ['Ingest', 'Understand', 'Audit'],
    registryProfileId: 'vessels',
  },
  {
    id: 'counsel', name: 'Counsel', vertical: 'Legal', sector: 'Legal',
    status: 'operational', tier: 'Enterprise',
    description: 'Legal matter lifecycle — filings, obligations, risk scoring, document intelligence, and privilege review automation with chain-of-custody proof.',
    icon: '⚖', color: '#c9b787',
    principles: ['Ingest', 'Plan', 'Audit'],
    registryProfileId: 'prism',
  },
  {
    id: 'terra', name: 'Terra', vertical: 'Real Estate', sector: 'Real Estate',
    status: 'operational', tier: 'Enterprise',
    description: DOMAIN_PROFILES.terra.description + ' Climate-adjusted valuations, deal pipeline analytics, tenant churn prediction, and ESG compliance reporting.',
    icon: '▣', color: '#8a8a8a',
    principles: ['Understand', 'Act', 'Verify'],
    registryProfileId: 'terra',
  },
  {
    id: 'aegis', name: 'Aegis', vertical: 'Defense & Security', sector: 'Defense & Security',
    status: 'operational', tier: 'Sovereign',
    description: DOMAIN_PROFILES.aegis.description + ' MITRE ATT&CK mapping, threat detection, incident response, and resilience verification.',
    icon: '⬡', color: '#f5f5f5',
    principles: ['Ingest', 'Verify', 'Audit'],
    registryProfileId: 'aegis',
  },
  {
    id: 'tenax', name: 'TENAX', vertical: 'Cyber Resilience', sector: 'Cyber',
    status: 'operational', tier: 'Enterprise',
    description: 'Cyber resilience command — posture monitoring, threat surface analysis, CISO intelligence, and incident escalation with governed approval flow.',
    icon: '⬡', color: '#c9b787',
    principles: ['Ingest', 'Understand', 'Verify'],
  },
  {
    id: 'lyte', name: 'Lyte', vertical: 'Revenue Intelligence', sector: 'Revenue',
    status: 'operational', tier: 'Enterprise',
    description: DOMAIN_PROFILES.lyte.description + ' Pipeline health, forecast modeling, decision debt ledger, and governed deal actions with full attribution.',
    icon: '◆', color: '#c9b787',
    principles: ['Understand', 'Plan', 'Learn'],
    registryProfileId: 'lyte',
  },
  {
    id: 'pulse', name: 'Pulse', vertical: 'Founder Operations', sector: 'Operations',
    status: 'operational', tier: 'Platform',
    description: 'Founder operating channel — daily briefings, signal synthesis across all domains, and decision orchestration for executive operators.',
    icon: '◉', color: '#8a8a8a',
    principles: ['Understand', 'Act', 'Audit'],
  },
  {
    id: 'carlota-jo', name: 'Carlota Jo', vertical: 'Consulting', sector: 'Consulting',
    status: 'operational', tier: 'Professional',
    description: DOMAIN_PROFILES.carlota.description + ' Advisory brief generation, engagement signal tracking, and proof-chained deliverables.',
    icon: '◎', color: '#c9b787',
    principles: ['Plan', 'Act', 'Learn'],
    registryProfileId: 'carlota',
  },
  {
    id: 'nuro-forge', name: 'NuroForge', vertical: 'AI Infrastructure', sector: 'AI Infrastructure',
    status: 'in-development', tier: 'Platform',
    description: 'Agent forge — custom agent training, fine-tuning orchestration, and evaluation harness for domain-specific model optimization.',
    icon: '⬟', color: '#5e5e5e',
    principles: ['Plan', 'Learn'],
  },
  {
    id: 'meridian', name: 'Meridian', vertical: 'Infrastructure', sector: 'Infrastructure',
    status: 'in-development', tier: 'Enterprise',
    description: 'Infrastructure intelligence — cloud cost optimization, capacity planning, incident correlation, and governed change management.',
    icon: '⬡', color: '#5e5e5e',
    principles: ['Ingest', 'Plan', 'Verify'],
  },
  {
    id: 'firestorm', name: 'Firestorm', vertical: 'Crisis Operations', sector: 'Crisis',
    status: 'planned', tier: 'Sovereign',
    description: 'Crisis operations — incident command, rapid response orchestration, impact simulation, and post-incident learning with full proof coverage.',
    icon: '⬢', color: '#5e5e5e',
    principles: ['Act', 'Verify', 'Learn'],
  },
  {
    id: 'constellation', name: 'Constellation', vertical: 'Graph Intelligence', sector: 'Intelligence',
    status: 'planned', tier: 'Platform',
    description: 'Cross-domain intelligence graph — entity relationships, causal chains, emergent patterns, and cross-vertical signal correlation.',
    icon: '✦', color: '#5e5e5e',
    principles: ['Understand', 'Learn'],
  },
];
