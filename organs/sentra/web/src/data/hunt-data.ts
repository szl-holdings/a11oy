export interface HuntNode {
  id: string;
  label: string;
  type: 'endpoint' | 'credential' | 'network' | 'identity' | 'data' | 'business';
  domain: 'tech' | 'deal' | 'vessel' | 'matter' | 'finance';
  risk: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  businessLabel?: string;
  costAtRisk?: number;
}

export interface HuntEdge {
  from: string;
  to: string;
  technique: string;
  mitreId: string;
  confidence: number;
}

export interface AttackPath {
  nodes: HuntNode[];
  edges: HuntEdge[];
  blastRadiusCost: number;
  affectedBusinessEntities: string[];
}

export interface Hunt {
  id: string;
  title: string;
  hypothesis: string;
  reasoning: string;
  proposedAt: string;
  mitreTactics: string[];
  mitreIds: string[];
  falsePositiveRate: number;
  confidenceScore: number;
  signalCount: number;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'proposed' | 'active' | 'completed' | 'dismissed';
  attackPath: AttackPath;
}

export interface RemediationStep {
  id: string;
  order: number;
  action: string;
  target: string;
  rationale: string;
  estimatedMinutes: number;
  reversible: boolean;
  requiredApproval: boolean;
  status: 'pending' | 'approved' | 'executing' | 'done' | 'skipped';
}

export interface RemediationPlan {
  id: string;
  huntId: string;
  huntTitle: string;
  draftedAt: string;
  status: 'draft' | 'approved' | 'executing' | 'complete' | 'cancelled';
  steps: RemediationStep[];
  estimatedTotalMinutes: number;
  blastRadiusCost: number;
  approvedBy?: string;
  approvedAt?: string;
  signalsBroadcast: string[];
}

export interface RedTeamScenario {
  id: string;
  name: string;
  category: 'ransomware' | 'supply_chain' | 'insider';
  severity: 'critical' | 'high' | 'medium';
  description: string;
  objective: string;
  mitreChain: { id: string; name: string; phase: string }[];
  estimatedImpact: string;
  estimatedCost: number;
  durationMinutes: number;
  lastRunAt?: string;
  runCount: number;
  coverageGaps: string[];
}

const now = new Date();
const minsAgo = (n: number) => new Date(now.getTime() - n * 60000).toISOString();
const hoursAgo = (n: number) => new Date(now.getTime() - n * 3600000).toISOString();

export const HUNTS: Hunt[] = [
  {
    id: 'hunt-001',
    title: 'Lateral Movement via Kerberoasting — OT Pivot Risk',
    hypothesis:
      'Adversary has already compromised the Domain Controller service account and is performing Kerberoasting to escalate privileges laterally into OT segment.',
    reasoning:
      'Signal correlation: Domain Controller shows 14 TGS-REQ events for high-privilege SPNs in the last 2 hours, originating from a single non-admin host. Pattern matches T1558.003. OT segment shares authentication boundary.',
    proposedAt: minsAgo(18),
    mitreTactics: ['Credential Access', 'Lateral Movement'],
    mitreIds: ['T1558.003', 'T1550.003'],
    falsePositiveRate: 0.08,
    confidenceScore: 0.91,
    signalCount: 14,
    severity: 'critical',
    status: 'proposed',
    attackPath: {
      nodes: [
        {
          id: 'n1',
          label: 'Employee Workstation',
          type: 'endpoint',
          domain: 'tech',
          risk: 'high',
          description: 'Initial beachhead — phishing payload executed',
        },
        {
          id: 'n2',
          label: 'Domain Controller',
          type: 'identity',
          domain: 'tech',
          risk: 'critical',
          description: 'Kerberoasting TGS requests from compromised host',
        },
        {
          id: 'n3',
          label: 'SCADA Server',
          type: 'endpoint',
          domain: 'tech',
          risk: 'critical',
          description: 'OT entry point via stolen service credential',
        },
        {
          id: 'n4',
          label: 'PLC Controller Network',
          type: 'network',
          domain: 'tech',
          risk: 'critical',
          description: 'Industrial control segment — lateral spread',
        },
        {
          id: 'n5',
          label: 'Deckmaster Deal — $42M LNG Contract',
          type: 'business',
          domain: 'deal',
          risk: 'critical',
          description: 'OT disruption halts LNG loading — contract SLA breach',
          businessLabel: 'Deal',
          costAtRisk: 3400000,
        },
        {
          id: 'n6',
          label: 'MV Atlantic Falcon',
          type: 'business',
          domain: 'vessel',
          risk: 'high',
          description: 'Vessel scheduling system feeds from affected OT segment',
          businessLabel: 'Vessel',
          costAtRisk: 780000,
        },
        {
          id: 'n7',
          label: 'CY-2026-014 Regulatory Matter',
          type: 'business',
          domain: 'matter',
          risk: 'high',
          description: 'OT breach triggers mandatory CISA 72h reporting obligation',
          businessLabel: 'Legal Matter',
          costAtRisk: 620000,
        },
      ],
      edges: [
        {
          from: 'n1',
          to: 'n2',
          technique: 'Kerberoasting',
          mitreId: 'T1558.003',
          confidence: 0.91,
        },
        {
          from: 'n2',
          to: 'n3',
          technique: 'Pass-the-Ticket',
          mitreId: 'T1550.003',
          confidence: 0.86,
        },
        {
          from: 'n3',
          to: 'n4',
          technique: 'Lateral Movement via OT Protocol',
          mitreId: 'T1021',
          confidence: 0.79,
        },
        {
          from: 'n4',
          to: 'n5',
          technique: 'OT Process Disruption',
          mitreId: 'T0836',
          confidence: 0.73,
        },
        {
          from: 'n4',
          to: 'n6',
          technique: 'Scheduling Feed Corruption',
          mitreId: 'T0836',
          confidence: 0.68,
        },
        {
          from: 'n3',
          to: 'n7',
          technique: 'Breach Triggers Regulatory Obligation',
          mitreId: 'T0886',
          confidence: 0.95,
        },
      ],
      blastRadiusCost: 4800000,
      affectedBusinessEntities: ['Deckmaster Deal — $42M LNG Contract', 'MV Atlantic Falcon', 'CY-2026-014 Regulatory Matter'],
    },
  },
  {
    id: 'hunt-002',
    title: 'Supply Chain Trojanized Update — MCP Server Integrity Drift',
    hypothesis:
      'A signed but tampered update package was deployed to three MCP servers. The modification adds a covert outbound channel that exfiltrates agent reasoning logs to an attacker-controlled endpoint.',
    reasoning:
      'Hash mismatch on mcp-data-broker v2.4.1 binary detected by Mesh Drift monitor. Outbound TLS connections to 198.51.x.x increased 340% over baseline in the last 6 hours. Timing correlates with the 03:14 UTC automated update window.',
    proposedAt: hoursAgo(2),
    mitreTactics: ['Initial Access', 'Collection', 'Exfiltration'],
    mitreIds: ['T1195.002', 'T1119', 'T1041'],
    falsePositiveRate: 0.04,
    confidenceScore: 0.96,
    signalCount: 31,
    severity: 'critical',
    status: 'active',
    attackPath: {
      nodes: [
        {
          id: 'n1',
          label: 'mcp-data-broker v2.4.1',
          type: 'endpoint',
          domain: 'tech',
          risk: 'critical',
          description: 'Trojanized update — hash drift confirmed',
        },
        {
          id: 'n2',
          label: 'Agent Reasoning Logs',
          type: 'data',
          domain: 'tech',
          risk: 'critical',
          description: 'Covert channel exfiltrating agent decision traces',
        },
        {
          id: 'n3',
          label: 'C2 Endpoint 198.51.x.x',
          type: 'network',
          domain: 'tech',
          risk: 'critical',
          description: 'Attacker-controlled exfiltration server',
        },
        {
          id: 'n4',
          label: 'Deal Evaluation Pipeline',
          type: 'business',
          domain: 'deal',
          risk: 'high',
          description: 'AI agent reasoning on active M&A deals exposed to adversary',
          businessLabel: 'Deal',
          costAtRisk: 12000000,
        },
        {
          id: 'n5',
          label: 'Executive Comms — Unencrypted Summaries',
          type: 'data',
          domain: 'finance',
          risk: 'high',
          description: 'Board-level briefing content in agent context window',
          costAtRisk: 0,
        },
      ],
      edges: [
        {
          from: 'n1',
          to: 'n2',
          technique: 'Log Harvesting via Covert Module',
          mitreId: 'T1119',
          confidence: 0.96,
        },
        {
          from: 'n2',
          to: 'n3',
          technique: 'Encrypted Exfiltration Channel',
          mitreId: 'T1041',
          confidence: 0.91,
        },
        {
          from: 'n2',
          to: 'n4',
          technique: 'M&A Intelligence Exposure',
          mitreId: 'T1530',
          confidence: 0.87,
        },
        {
          from: 'n2',
          to: 'n5',
          technique: 'Executive Context Window Leak',
          mitreId: 'T1530',
          confidence: 0.82,
        },
      ],
      blastRadiusCost: 12000000,
      affectedBusinessEntities: ['Deal Evaluation Pipeline', 'Executive Comms'],
    },
  },
  {
    id: 'hunt-003',
    title: 'Insider Data Staging — High-Volume Export from Legal Matter Repository',
    hypothesis:
      'A privileged user account is exfiltrating protected legal matter documents to a personal cloud drive, likely in preparation for departure or sale to a competitor.',
    reasoning:
      'DLP signal: 4.2 GB transferred to dropbox.com from the Counsel matter repository in 90 minutes, vs. a 200 MB daily baseline for this account. Activity window is 22:00–23:30 local time — outside normal hours. User is on the HR watch list for redundancy.',
    proposedAt: hoursAgo(5),
    mitreTactics: ['Collection', 'Exfiltration'],
    mitreIds: ['T1213', 'T1567.002'],
    falsePositiveRate: 0.12,
    confidenceScore: 0.82,
    signalCount: 8,
    severity: 'high',
    status: 'proposed',
    attackPath: {
      nodes: [
        {
          id: 'n1',
          label: 'Privileged User Account (GC-0042)',
          type: 'identity',
          domain: 'tech',
          risk: 'high',
          description: 'Senior counsel role — full matter repository access',
        },
        {
          id: 'n2',
          label: 'Counsel Matter Repository',
          type: 'data',
          domain: 'matter',
          risk: 'high',
          description: '4.2 GB bulk export — 247 protected documents',
        },
        {
          id: 'n3',
          label: 'dropbox.com (Personal)',
          type: 'network',
          domain: 'tech',
          risk: 'high',
          description: 'Unapproved cloud destination outside DLP boundary',
        },
        {
          id: 'n4',
          label: 'Active Litigation — Westcoast v. SZL',
          type: 'business',
          domain: 'matter',
          risk: 'high',
          description: 'Privileged strategy documents exposed — litigation risk',
          businessLabel: 'Legal Matter',
          costAtRisk: 8500000,
        },
        {
          id: 'n5',
          label: 'Regulatory Filing — SEC 10-Q Drafts',
          type: 'business',
          domain: 'finance',
          risk: 'high',
          description: 'Pre-publication financial data in exported set',
          businessLabel: 'Finance',
          costAtRisk: 4200000,
        },
      ],
      edges: [
        {
          from: 'n1',
          to: 'n2',
          technique: 'Authorized Access Abuse',
          mitreId: 'T1213',
          confidence: 0.82,
        },
        {
          from: 'n2',
          to: 'n3',
          technique: 'Cloud Exfiltration (Dropbox)',
          mitreId: 'T1567.002',
          confidence: 0.88,
        },
        {
          from: 'n2',
          to: 'n4',
          technique: 'Privileged Document Exposure',
          mitreId: 'T1530',
          confidence: 0.79,
        },
        {
          from: 'n2',
          to: 'n5',
          technique: 'Financial Data Pre-Disclosure',
          mitreId: 'T1530',
          confidence: 0.74,
        },
      ],
      blastRadiusCost: 12700000,
      affectedBusinessEntities: ['Active Litigation — Westcoast v. SZL', 'SEC 10-Q Drafts'],
    },
  },
];

export const REMEDIATION_PLANS: RemediationPlan[] = [
  {
    id: 'rem-001',
    huntId: 'hunt-001',
    huntTitle: 'Lateral Movement via Kerberoasting — OT Pivot Risk',
    draftedAt: minsAgo(5),
    status: 'draft',
    estimatedTotalMinutes: 45,
    blastRadiusCost: 4800000,
    signalsBroadcast: [
      'sentra.remediation.isolation.ot-segment',
      'vessels.alert.scheduling-system-offline',
      'counsel.alert.mandatory-cisa-notification',
    ],
    steps: [
      {
        id: 'step-001-1',
        order: 1,
        action: 'Isolate Employee Workstation',
        target: 'WS-EMPL-0142 (initial beachhead)',
        rationale: 'Prevent further Kerberoasting requests and cut lateral movement chain at the source.',
        estimatedMinutes: 2,
        reversible: true,
        requiredApproval: true,
        status: 'pending',
      },
      {
        id: 'step-001-2',
        order: 2,
        action: 'Revoke & Rotate All Service Account TGTs',
        target: 'Domain Controller — 7 affected SPNs',
        rationale: 'Invalidate stolen Kerberos tickets before adversary escalates to SCADA.',
        estimatedMinutes: 8,
        reversible: true,
        requiredApproval: true,
        status: 'pending',
      },
      {
        id: 'step-001-3',
        order: 3,
        action: 'Network-Segment OT SCADA Server',
        target: 'SCADA-SRV-001 — VLAN isolation',
        rationale: 'Cut OT pivot path even if credentials already compromised.',
        estimatedMinutes: 5,
        reversible: true,
        requiredApproval: true,
        status: 'pending',
      },
      {
        id: 'step-001-4',
        order: 4,
        action: 'Block PLC Controller External Comms',
        target: 'PLC-NET-003 — firewall rule push',
        rationale: 'Prevent any C2 from reaching the industrial control segment.',
        estimatedMinutes: 3,
        reversible: true,
        requiredApproval: false,
        status: 'pending',
      },
      {
        id: 'step-001-5',
        order: 5,
        action: 'Notify SEXTANT Scheduling System',
        target: 'MV Atlantic Falcon — manual scheduling mode',
        rationale: 'OT isolation will interrupt automated scheduling feed. SEXTANT team must switch to manual.',
        estimatedMinutes: 10,
        reversible: false,
        requiredApproval: false,
        status: 'pending',
      },
      {
        id: 'step-001-6',
        order: 6,
        action: 'Draft CISA 72h Incident Notification',
        target: 'Counsel — regulatory filing obligation',
        rationale: 'OT compromise of critical infrastructure triggers mandatory CISA reporting within 72 hours.',
        estimatedMinutes: 17,
        reversible: false,
        requiredApproval: true,
        status: 'pending',
      },
    ],
  },
  {
    id: 'rem-002',
    huntId: 'hunt-002',
    huntTitle: 'Supply Chain Trojanized Update — MCP Server Integrity Drift',
    draftedAt: hoursAgo(1),
    status: 'approved',
    estimatedTotalMinutes: 28,
    blastRadiusCost: 12000000,
    approvedBy: 'J. Okonkwo (CISO)',
    approvedAt: hoursAgo(0.5),
    signalsBroadcast: [
      'sentra.remediation.mcp-rollback.broker',
      'command.alert.supply-chain-compromise',
      'pulse.alert.executive-data-exposure',
    ],
    steps: [
      {
        id: 'step-002-1',
        order: 1,
        action: 'Isolate mcp-data-broker from Agent Mesh',
        target: 'mcp-data-broker v2.4.1 — all 3 instances',
        rationale: 'Stop ongoing exfiltration immediately.',
        estimatedMinutes: 1,
        reversible: true,
        requiredApproval: false,
        status: 'done',
      },
      {
        id: 'step-002-2',
        order: 2,
        action: 'Block Outbound TLS to 198.51.x.x /24',
        target: 'Perimeter firewall — egress rule',
        rationale: 'Cut C2 exfiltration channel even before rollback.',
        estimatedMinutes: 2,
        reversible: true,
        requiredApproval: false,
        status: 'done',
      },
      {
        id: 'step-002-3',
        order: 3,
        action: 'Rollback mcp-data-broker to v2.3.9 (trusted hash)',
        target: 'All 3 MCP server nodes',
        rationale: 'Restore integrity-verified version from artifact registry.',
        estimatedMinutes: 12,
        reversible: false,
        requiredApproval: true,
        status: 'executing',
      },
      {
        id: 'step-002-4',
        order: 4,
        action: 'Rotate Agent API Credentials',
        target: 'All agents with access to mcp-data-broker',
        rationale: 'Assume all credentials in the context window are compromised.',
        estimatedMinutes: 8,
        reversible: false,
        requiredApproval: true,
        status: 'pending',
      },
      {
        id: 'step-002-5',
        order: 5,
        action: 'Notify Executive Team of Potential Data Exposure',
        target: 'Pulse — board briefing channel',
        rationale: 'Executive context window content was in scope of exfiltrated logs.',
        estimatedMinutes: 5,
        reversible: false,
        requiredApproval: false,
        status: 'pending',
      },
    ],
  },
];

export const RED_TEAM_SCENARIOS: RedTeamScenario[] = [
  {
    id: 'rt-001',
    name: 'OT Ransomware Propagation',
    category: 'ransomware',
    severity: 'critical',
    description:
      'Simulates a ransomware strain entering through a phishing email on a corporate endpoint, moving laterally via credential theft to the OT network segment, and deploying an encrypted payload across SCADA and PLC controllers. Measures detection latency, isolation speed, and recovery readiness.',
    objective:
      'Validate that Sentra detects OT-targeted ransomware within 15 minutes and automated containment runs before the payload can encrypt more than 20% of OT assets.',
    mitreChain: [
      { id: 'T1566.001', name: 'Spearphishing Attachment', phase: 'Initial Access' },
      { id: 'T1059.001', name: 'PowerShell Execution', phase: 'Execution' },
      { id: 'T1558.003', name: 'Kerberoasting', phase: 'Credential Access' },
      { id: 'T1550.003', name: 'Pass-the-Ticket', phase: 'Lateral Movement' },
      { id: 'T0836', name: 'Modify Parameter — PLC', phase: 'Impact' },
      { id: 'T0882', name: 'Theft of Operational Information', phase: 'Collection' },
    ],
    estimatedImpact: '$2.8M–$8.4M operational disruption + regulatory exposure',
    estimatedCost: 4800000,
    durationMinutes: 45,
    lastRunAt: hoursAgo(72),
    runCount: 4,
    coverageGaps: [
      'Isolation playbooks failed on SCADA legacy OS (Windows 2008)',
      'OT segment VLAN not reachable by automated containment agent',
    ],
  },
  {
    id: 'rt-002',
    name: 'Supply Chain MCP Compromise',
    category: 'supply_chain',
    severity: 'critical',
    description:
      'Simulates a malicious maintainer inserting a covert exfiltration module into a widely-used MCP server package. The module activates after installation and begins harvesting agent reasoning logs, M&A deal context, and executive briefing content, transmitting to an attacker-controlled server.',
    objective:
      'Validate that Mesh Drift detection catches binary hash mismatch within 60 minutes of deployment, outbound anomaly detection triggers within 6 hours, and agent credential rotation can be completed in under 30 minutes.',
    mitreChain: [
      { id: 'T1195.002', name: 'Compromise Software Supply Chain', phase: 'Initial Access' },
      { id: 'T1027', name: 'Obfuscated Files or Information', phase: 'Defense Evasion' },
      { id: 'T1119', name: 'Automated Collection', phase: 'Collection' },
      { id: 'T1041', name: 'Exfiltration Over C2 Channel', phase: 'Exfiltration' },
    ],
    estimatedImpact: '$12M+ M&A intelligence exposure + reputational damage',
    estimatedCost: 12000000,
    durationMinutes: 60,
    lastRunAt: undefined,
    runCount: 0,
    coverageGaps: [
      'Binary integrity check only runs at 6-hour intervals — detection window too large',
      'No anomaly baseline established for MCP server outbound traffic',
    ],
  },
  {
    id: 'rt-003',
    name: 'Privileged Insider Exfiltration',
    category: 'insider',
    severity: 'high',
    description:
      'Simulates a departing privileged user (senior counsel) performing bulk export of protected legal matter documents and pre-publication financial data to a personal cloud drive during off-hours. Tests DLP detection speed, HR+Legal coordination workflow, and account suspension automation.',
    objective:
      'Validate that DLP triggers within 15 minutes of a 500 MB threshold breach, the account is suspended within 30 minutes of analyst confirmation, and Counsel + HR are automatically notified via the signal bus.',
    mitreChain: [
      { id: 'T1213', name: 'Data from Information Repositories', phase: 'Collection' },
      { id: 'T1048', name: 'Exfiltration Over Alternative Protocol', phase: 'Exfiltration' },
      { id: 'T1567.002', name: 'Exfiltration to Cloud Storage', phase: 'Exfiltration' },
    ],
    estimatedImpact: '$8.5M+ litigation exposure + SEC disclosure risk',
    estimatedCost: 12700000,
    durationMinutes: 30,
    lastRunAt: hoursAgo(240),
    runCount: 2,
    coverageGaps: ['HR escalation workflow requires manual analyst handoff — no automation', 'Dropbox DLP rule not yet extended to cover personal accounts'],
  },
];
