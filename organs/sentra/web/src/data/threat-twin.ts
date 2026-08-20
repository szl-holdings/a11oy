export type ThreatSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical';
export type ThreatStatus =
  | 'open'
  | 'investigating'
  | 'contained'
  | 'remediated'
  | 'closed'
  | 'false_positive';
export type ExposureLevel = 'none' | 'minimal' | 'moderate' | 'elevated' | 'critical';
export type ReadinessStatus = 'ready' | 'partial' | 'degraded' | 'not_ready';

export interface AssetTwin {
  id: string;
  name: string;
  type:
    | 'server'
    | 'endpoint'
    | 'cloud_resource'
    | 'network_device'
    | 'application'
    | 'identity'
    | 'ot_ics';
  criticality: 'low' | 'medium' | 'high' | 'critical';
  owner: string;
  environment: 'production' | 'staging' | 'dev' | 'corp';
  exposureLevel: ExposureLevel;
  vulnerabilityCount: number;
  criticalVulnCount: number;
  patchStatus: 'current' | 'behind' | 'critical_missing';
  lastSeenAt: string;
  complianceFrameworks: string[];
  tags: string[];
  anomalyFlags: string[];
  externalDataConnectors: Array<{
    name: string;
    type: 'edr' | 'siem' | 'vuln_scanner' | 'identity_provider' | 'cloud_posture';
    status: 'not_connected' | 'connected' | 'error';
    lastSyncAt?: string;
  }>;
}

export interface ThreatTwin {
  id: string;
  title: string;
  type:
    | 'malware'
    | 'phishing'
    | 'ransomware'
    | 'data_exfiltration'
    | 'insider_threat'
    | 'supply_chain'
    | 'zero_day'
    | 'social_engineering'
    | 'ddos'
    | 'lateral_movement';
  severity: ThreatSeverity;
  status: ThreatStatus;
  confidence: number;
  affectedAssets: string[];
  affectedAssetCount: number;
  sourceIndicators: string[];
  mitreTactics: string[];
  mitreTechniques: string[];
  killChainStage:
    | 'reconnaissance'
    | 'weaponization'
    | 'delivery'
    | 'exploitation'
    | 'installation'
    | 'c2'
    | 'actions_objectives';
  detectedAt: string;
  lastActivityAt: string;
  resolvedAt?: string;
  assignedTo?: string;
  responseState: 'no_action' | 'triage' | 'containment' | 'eradication' | 'recovery';
  readinessImpact: ReadinessStatus;
  approvals: ThreatApproval[];
  auditTrail: ThreatAuditEntry[];
  externalDataConnectors: Array<{
    name: string;
    type: 'threat_intel' | 'sandbox' | 'osint' | 'dark_web';
    status: 'not_connected' | 'connected' | 'error';
  }>;
}

export interface ExposureTwin {
  id: string;
  name: string;
  type:
    | 'vulnerability_cluster'
    | 'misconfiguration'
    | 'identity_gap'
    | 'third_party_risk'
    | 'compliance_gap';
  severity: ThreatSeverity;
  exposureLevel: ExposureLevel;
  affectedAssetCount: number;
  affectedAssets: string[];
  cvssScore?: number;
  cveIds?: string[];
  description: string;
  remediationStatus: 'open' | 'in_progress' | 'patched' | 'risk_accepted' | 'false_positive';
  dueDate?: string;
  owner?: string;
  complianceImpact: string[];
  riskScore: number;
  lastUpdatedAt: string;
  externalDataConnectors: Array<{
    name: string;
    type: 'vuln_scanner' | 'cloud_posture' | 'sbom' | 'cve_db';
    status: 'not_connected' | 'connected' | 'error';
  }>;
}

export interface ThreatApproval {
  id: string;
  threatId: string;
  threatTitle: string;
  actionClass:
    | 'containment_action'
    | 'remediation_plan'
    | 'risk_acceptance'
    | 'escalation'
    | 'governance_review'
    | 'export_report';
  title: string;
  description: string;
  status: 'pending' | 'approved' | 'rejected' | 'escalated' | 'withdrawn';
  priority: 'low' | 'medium' | 'high' | 'critical';
  requestedBy: string;
  requestedAt: string;
  approver?: string;
  approvedAt?: string;
  comments: Array<{ author: string; body: string; at: string; internal?: boolean }>;
  payload?: Record<string, unknown>;
}

export interface ThreatAuditEntry {
  id: string;
  threatId?: string;
  exposureId?: string;
  action: string;
  actor: string;
  actorRole: string;
  at: string;
  details?: Record<string, unknown>;
}

export interface IncidentReadiness {
  id: string;
  area: 'detection' | 'response' | 'recovery' | 'communication' | 'governance';
  label: string;
  status: ReadinessStatus;
  score: number;
  lastTestedAt?: string;
  issues: string[];
  pendingActions: number;
}

export interface AegisWhatChangedEvent {
  id: string;
  entityId: string;
  entityType: 'threat' | 'exposure' | 'asset' | 'governance';
  entityName: string;
  eventType:
    | 'new_threat'
    | 'severity_change'
    | 'status_change'
    | 'asset_compromised'
    | 'exposure_discovered'
    | 'approval_action'
    | 'governance_update'
    | 'readiness_change'
    | 'containment_action';
  summary: string;
  detail?: string;
  severity: 'info' | 'warning' | 'critical';
  source: string;
  occurredAt: string;
  actor?: string;
}

export interface ActionQueueItem {
  id: string;
  threatId?: string;
  exposureId?: string;
  title: string;
  description: string;
  type: 'containment' | 'remediation' | 'investigation' | 'governance' | 'communication';
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'in_progress' | 'blocked' | 'completed';
  assignedTo?: string;
  dueDate?: string;
  completedAt?: string;
  blocker?: string;
}

export interface ThreatActor {
  id: string;
  name: string;
  alias: string;
  affiliation: string;
  motivation: string;
  description: string;
  ttps: string[];
  confidence: number;
  lastActivityAt: string;
}

export interface IndicatorTimeline {
  id: string;
  value: string;
  type: 'ip' | 'domain' | 'hash';
  tlp: 'white' | 'green' | 'amber' | 'red';
  firstSeenAt: string;
  lastSeenAt: string;
  description: string;
}

export interface ContainmentWorkflow {
  id: string;
  title: string;
  steps: Array<{
    action: string;
    target: string;
    description: string;
  }>;
  recommendedAt: string;
  status: 'pending' | 'approved' | 'rejected';
}

const now = new Date();
const daysAgo = (n: number) => new Date(now.getTime() - n * 86400000).toISOString();
const hoursAgo = (n: number) => new Date(now.getTime() - n * 3600000).toISOString();
const minsAgo = (n: number) => new Date(now.getTime() - n * 60000).toISOString();

export const assetTwins: AssetTwin[] = [
  {
    id: 'asset-001',
    name: 'prod-api-cluster-01',
    type: 'server',
    criticality: 'critical',
    owner: 'Platform Engineering',
    environment: 'production',
    exposureLevel: 'moderate',
    vulnerabilityCount: 14,
    criticalVulnCount: 2,
    patchStatus: 'critical_missing',
    lastSeenAt: minsAgo(5),
    complianceFrameworks: ['NIST CSF', 'SOC 2'],
    tags: ['api', 'core', 'public-facing'],
    anomalyFlags: ['lateral_movement_attempt', 'patch_overdue'],
    externalDataConnectors: [
      { name: 'CrowdStrike Falcon', type: 'edr', status: 'not_connected' },
      { name: 'Splunk SIEM', type: 'siem', status: 'not_connected' },
      { name: 'Tenable.io', type: 'vuln_scanner', status: 'not_connected' },
    ],
  },
  {
    id: 'asset-002',
    name: 'corp-identity-azure-ad',
    type: 'identity',
    criticality: 'critical',
    owner: 'IT Security',
    environment: 'corp',
    exposureLevel: 'elevated',
    vulnerabilityCount: 6,
    criticalVulnCount: 1,
    patchStatus: 'behind',
    lastSeenAt: minsAgo(15),
    complianceFrameworks: ['NIST CSF', 'ISO 27001'],
    tags: ['identity', 'sso', 'privileged-access'],
    anomalyFlags: ['mfa_bypass_attempt'],
    externalDataConnectors: [
      { name: 'Microsoft Sentinel', type: 'siem', status: 'not_connected' },
      { name: 'Okta Identity', type: 'identity_provider', status: 'not_connected' },
    ],
  },
  {
    id: 'asset-003',
    name: 'aws-prod-vpc-us-east-1',
    type: 'cloud_resource',
    criticality: 'high',
    owner: 'Cloud Platform',
    environment: 'production',
    exposureLevel: 'minimal',
    vulnerabilityCount: 3,
    criticalVulnCount: 0,
    patchStatus: 'current',
    lastSeenAt: minsAgo(10),
    complianceFrameworks: ['SOC 2', 'StateRAMP'],
    tags: ['aws', 'vpc', 'prod'],
    anomalyFlags: [],
    externalDataConnectors: [
      { name: 'AWS Security Hub', type: 'cloud_posture', status: 'not_connected' },
      { name: 'Prisma Cloud', type: 'cloud_posture', status: 'not_connected' },
    ],
  },
];

export const threatTwins: ThreatTwin[] = [
  {
    id: 'threat-001',
    title: 'Suspected Lateral Movement — prod-api-cluster-01',
    type: 'lateral_movement',
    severity: 'critical',
    status: 'investigating',
    confidence: 87,
    affectedAssets: ['asset-001', 'asset-002'],
    affectedAssetCount: 2,
    sourceIndicators: [
      'Anomalous RPC call chain',
      'Credential enumeration attempt',
      'Process injection artifact',
    ],
    mitreTactics: ['TA0008 - Lateral Movement', 'TA0006 - Credential Access'],
    mitreTechniques: ['T1021 - Remote Services', 'T1552 - Unsecured Credentials'],
    killChainStage: 'exploitation',
    detectedAt: hoursAgo(4),
    lastActivityAt: hoursAgo(1),
    assignedTo: 'SOC Lead',
    responseState: 'containment',
    readinessImpact: 'partial',
    approvals: [
      {
        id: 'tapr-001',
        threatId: 'threat-001',
        threatTitle: 'Suspected Lateral Movement — prod-api-cluster-01',
        actionClass: 'containment_action',
        title: 'Isolate prod-api-cluster-01 from network segment',
        description:
          'SOC Lead requesting authorization to isolate compromised cluster. Estimated service disruption: 15-30 mins.',
        status: 'pending',
        priority: 'critical',
        requestedBy: 'SOC Lead',
        requestedAt: hoursAgo(2),
        comments: [
          {
            author: 'CISO',
            body: 'Approved in principle. Confirm blast radius before executing.',
            at: hoursAgo(1),
            internal: true,
          },
        ],
      },
    ],
    auditTrail: [
      {
        id: 'taud-001',
        threatId: 'threat-001',
        action: 'threat_detected',
        actor: 'siem.correlation',
        actorRole: 'system',
        at: hoursAgo(4),
      },
      {
        id: 'taud-002',
        threatId: 'threat-001',
        action: 'assigned_to_analyst',
        actor: 'SOC Manager',
        actorRole: 'manager',
        at: hoursAgo(3.5),
      },
      {
        id: 'taud-003',
        threatId: 'threat-001',
        action: 'containment_requested',
        actor: 'SOC Lead',
        actorRole: 'analyst',
        at: hoursAgo(2),
      },
    ],
    externalDataConnectors: [
      { name: 'VirusTotal', type: 'threat_intel', status: 'not_connected' },
      { name: 'MISP Platform', type: 'threat_intel', status: 'not_connected' },
      { name: 'Joe Sandbox', type: 'sandbox', status: 'not_connected' },
    ],
  },
  {
    id: 'threat-002',
    title: 'MFA Bypass Attempt — Azure AD corp identity',
    type: 'social_engineering',
    severity: 'high',
    status: 'open',
    confidence: 72,
    affectedAssets: ['asset-002'],
    affectedAssetCount: 1,
    sourceIndicators: [
      'Impossible travel detected',
      'MFA fatigue pattern',
      'Conditional access policy circumvention',
    ],
    mitreTactics: ['TA0001 - Initial Access'],
    mitreTechniques: ['T1566 - Phishing', 'T1621 - MFA Request Generation'],
    killChainStage: 'delivery',
    detectedAt: hoursAgo(18),
    lastActivityAt: hoursAgo(6),
    assignedTo: 'Identity Security Analyst',
    responseState: 'triage',
    readinessImpact: 'partial',
    approvals: [],
    auditTrail: [
      {
        id: 'taud-010',
        threatId: 'threat-002',
        action: 'threat_detected',
        actor: 'identity.monitor',
        actorRole: 'system',
        at: hoursAgo(18),
      },
      {
        id: 'taud-011',
        threatId: 'threat-002',
        action: 'triage_started',
        actor: 'Identity Security Analyst',
        actorRole: 'analyst',
        at: hoursAgo(16),
      },
    ],
    externalDataConnectors: [
      { name: 'VirusTotal', type: 'threat_intel', status: 'not_connected' },
      { name: 'Dark Web Monitor', type: 'dark_web', status: 'not_connected' },
    ],
  },
];

export const exposureTwins: ExposureTwin[] = [
  {
    id: 'exp-001',
    name: 'Critical Patch Gap — prod-api-cluster',
    type: 'vulnerability_cluster',
    severity: 'critical',
    exposureLevel: 'elevated',
    affectedAssetCount: 3,
    affectedAssets: ['asset-001'],
    cvssScore: 9.8,
    cveIds: ['CVE-2025-1234', 'CVE-2025-5678'],
    description:
      'Two critical CVEs unpatched on production API cluster. Remote code execution risk. Patch window needed.',
    remediationStatus: 'in_progress',
    dueDate: daysAgo(-2),
    owner: 'Platform Engineering',
    complianceImpact: ['NIST CSF PR.IP-12', 'SOC 2 CC6.8'],
    riskScore: 94,
    lastUpdatedAt: hoursAgo(6),
    externalDataConnectors: [
      { name: 'Tenable.io', type: 'vuln_scanner', status: 'not_connected' },
      { name: 'NVD CVE Database', type: 'cve_db', status: 'not_connected' },
    ],
  },
  {
    id: 'exp-002',
    name: 'Identity MFA Coverage Gap',
    type: 'identity_gap',
    severity: 'high',
    exposureLevel: 'moderate',
    affectedAssetCount: 12,
    affectedAssets: ['asset-002'],
    description:
      '18% of privileged accounts lack enforced MFA. Policy exists but enforcement gaps in legacy SSO.',
    remediationStatus: 'in_progress',
    dueDate: daysAgo(-7),
    owner: 'IT Security',
    complianceImpact: ['NIST CSF PR.AC-7', 'ISO 27001 A.9.4'],
    riskScore: 78,
    lastUpdatedAt: daysAgo(1),
    externalDataConnectors: [
      { name: 'Okta Identity', type: 'cloud_posture', status: 'not_connected' },
    ],
  },
  {
    id: 'exp-003',
    name: 'Cloud Storage Public Access Misconfiguration',
    type: 'misconfiguration',
    severity: 'high',
    exposureLevel: 'minimal',
    affectedAssetCount: 2,
    affectedAssets: ['asset-003'],
    description:
      '2 S3 buckets found with public read access enabled. Contents appear to be non-sensitive (static assets). Risk accepted pending review.',
    remediationStatus: 'risk_accepted',
    owner: 'Cloud Platform',
    complianceImpact: ['SOC 2 CC6.6'],
    riskScore: 42,
    lastUpdatedAt: daysAgo(14),
    externalDataConnectors: [
      { name: 'AWS Security Hub', type: 'cloud_posture', status: 'not_connected' },
    ],
  },
];

export const incidentReadiness: IncidentReadiness[] = [
  {
    id: 'read-001',
    area: 'detection',
    label: 'Threat Detection',
    status: 'partial',
    score: 72,
    lastTestedAt: daysAgo(30),
    issues: ['SIEM not connected', 'EDR coverage gap on 3 endpoints'],
    pendingActions: 3,
  },
  {
    id: 'read-002',
    area: 'response',
    label: 'Incident Response',
    status: 'partial',
    score: 68,
    lastTestedAt: daysAgo(90),
    issues: [
      'IR playbook last updated 6 months ago',
      'Containment authorization flow needs approval',
    ],
    pendingActions: 2,
  },
  {
    id: 'read-003',
    area: 'recovery',
    label: 'Recovery & Continuity',
    status: 'ready',
    score: 85,
    lastTestedAt: daysAgo(60),
    issues: [],
    pendingActions: 0,
  },
  {
    id: 'read-004',
    area: 'communication',
    label: 'Stakeholder Communication',
    status: 'ready',
    score: 91,
    lastTestedAt: daysAgo(14),
    issues: [],
    pendingActions: 0,
  },
  {
    id: 'read-005',
    area: 'governance',
    label: 'Governance & Compliance',
    status: 'degraded',
    score: 54,
    lastTestedAt: daysAgo(120),
    issues: [
      '3 governance reviews overdue',
      'Board reporting cadence lapsed',
      'Policy exceptions not formally approved',
    ],
    pendingActions: 5,
  },
];

export const aegisWhatChanged: AegisWhatChangedEvent[] = [
  {
    id: 'awc-001',
    entityId: 'threat-001',
    entityType: 'threat',
    entityName: 'Suspected Lateral Movement — prod-api-cluster-01',
    eventType: 'new_threat',
    summary: 'CRITICAL: Lateral movement detected on production cluster',
    detail:
      'Anomalous RPC chain and credential enumeration detected. Confidence 87%. SOC Lead assigned. Containment action pending approval.',
    severity: 'critical',
    source: 'SIEM Correlation',
    occurredAt: hoursAgo(4),
  },
  {
    id: 'awc-002',
    entityId: 'threat-001',
    entityType: 'threat',
    entityName: 'Suspected Lateral Movement — prod-api-cluster-01',
    eventType: 'containment_action',
    summary: 'Containment request pending: Isolate cluster from network segment',
    detail:
      'SOC Lead requested network isolation of prod-api-cluster-01. CISO acknowledged. Awaiting final authorization.',
    severity: 'critical',
    source: 'Approvals',
    occurredAt: hoursAgo(2),
    actor: 'SOC Lead',
  },
  {
    id: 'awc-003',
    entityId: 'threat-002',
    entityType: 'threat',
    entityName: 'MFA Bypass Attempt — Azure AD',
    eventType: 'new_threat',
    summary: 'HIGH: MFA bypass attempt detected on corporate identity',
    detail:
      'Impossible travel + MFA fatigue pattern detected. Identity Security Analyst assigned. Triage in progress.',
    severity: 'warning',
    source: 'Identity Monitor',
    occurredAt: hoursAgo(18),
  },
  {
    id: 'awc-004',
    entityId: 'exp-001',
    entityType: 'exposure',
    entityName: 'Critical Patch Gap — prod-api-cluster',
    eventType: 'exposure_discovered',
    summary: 'Patch deadline exceeded: CVE-2025-1234 + CVE-2025-5678',
    detail:
      'Two critical CVEs are 2 days past remediation deadline. Risk score: 94. Platform Engineering team alerted.',
    severity: 'critical',
    source: 'Vulnerability Scanner',
    occurredAt: hoursAgo(6),
  },
  {
    id: 'awc-005',
    entityId: 'read-005',
    entityType: 'governance',
    entityName: 'Governance & Compliance',
    eventType: 'governance_update',
    summary: 'Governance readiness degraded: 3 reviews overdue',
    detail: 'Board reporting lapse + 3 policy exception reviews unresolved. Readiness score: 54.',
    severity: 'warning',
    source: 'Governance Engine',
    occurredAt: daysAgo(1),
  },
];

export const actionQueue: ActionQueueItem[] = [
  {
    id: 'act-001',
    threatId: 'threat-001',
    title: 'Execute network isolation — prod-api-cluster-01',
    description: 'Pending approval. Isolate cluster from segment post-authorization.',
    type: 'containment',
    priority: 'critical',
    status: 'blocked',
    assignedTo: 'SOC Lead',
    dueDate: hoursAgo(-2),
    blocker: 'Awaiting authorization approval',
  },
  {
    id: 'act-002',
    threatId: 'threat-001',
    title: 'Forensic memory capture — compromised endpoints',
    description: 'Capture memory dumps from affected hosts for analysis.',
    type: 'investigation',
    priority: 'high',
    status: 'in_progress',
    assignedTo: 'Forensics Analyst',
  },
  {
    id: 'act-003',
    threatId: 'threat-002',
    title: 'Block suspicious session — Azure AD',
    description: 'Revoke active session exhibiting impossible travel pattern.',
    type: 'containment',
    priority: 'high',
    status: 'open',
    assignedTo: 'Identity Security Analyst',
    dueDate: daysAgo(-1),
  },
  {
    id: 'act-004',
    exposureId: 'exp-001',
    title: 'Emergency patch — CVE-2025-1234 & CVE-2025-5678',
    description: 'Schedule maintenance window for critical patch deployment.',
    type: 'remediation',
    priority: 'critical',
    status: 'in_progress',
    assignedTo: 'Platform Engineering',
    dueDate: daysAgo(-2),
  },
  {
    id: 'act-005',
    exposureId: 'exp-002',
    title: 'Enforce MFA on remaining privileged accounts',
    description: 'Apply conditional access policy to 12 remaining non-compliant accounts.',
    type: 'remediation',
    priority: 'high',
    status: 'open',
    assignedTo: 'IT Security',
    dueDate: daysAgo(-7),
  },
  {
    id: 'act-006',
    title: 'Board security briefing — Q1 2026',
    description:
      'Prepare and deliver overdue board security briefing. Include threat landscape and posture summary.',
    type: 'governance',
    priority: 'medium',
    status: 'open',
    assignedTo: 'CISO',
    dueDate: daysAgo(-14),
  },
];

export const phantomClusterActor: ThreatActor = {
  id: 'actor-2891',
  name: 'TA-2891',
  alias: 'Phantom Cluster',
  affiliation: 'Nation-State',
  motivation: 'Financial / Strategic',
  description:
    'Advanced persistent threat actor focusing on supply chain and financial systems. Known for stealthy lateral movement.',
  ttps: [
    'DLL Search Order Hijacking',
    'Credential Dumping',
    'Lateral Movement via WMI',
    'C2 via DNS Tunneling',
    'Data Exfiltration via HTTP/S',
  ],
  confidence: 0.94,
  lastActivityAt: hoursAgo(1),
};

export const phantomIndicators: IndicatorTimeline[] = [
  {
    id: 'ioc-001',
    value: '185.234.12.89',
    type: 'ip',
    tlp: 'red',
    firstSeenAt: daysAgo(7),
    lastSeenAt: hoursAgo(2),
    description: 'Known C2 IP address for Phantom Cluster',
  },
  {
    id: 'ioc-002',
    value: '45.122.34.11',
    type: 'ip',
    tlp: 'red',
    firstSeenAt: daysAgo(3),
    lastSeenAt: hoursAgo(4),
    description: 'Anomalous connection source',
  },
  {
    id: 'ioc-003',
    value: 'update-server.phantom-net.org',
    type: 'domain',
    tlp: 'amber',
    firstSeenAt: daysAgo(5),
    lastSeenAt: hoursAgo(1),
    description: 'Suspicious domain beaconing',
  },
  {
    id: 'ioc-004',
    value: '7d8f9a2b3c4d5e6f7g8h9i0j1k2l3m4n',
    type: 'hash',
    tlp: 'red',
    firstSeenAt: daysAgo(10),
    lastSeenAt: daysAgo(1),
    description: 'Malicious payload hash',
  },
];

export const affectedSystems = [
  { name: 'Finance DB', type: 'Database', status: 'at_risk', criticality: 'critical' },
  { name: 'Identity Provider', type: 'Auth', status: 'compromised', criticality: 'critical' },
  { name: 'Mail Gateway', type: 'Network', status: 'beaconing', criticality: 'high' },
];

export const containmentWorkflow: ContainmentWorkflow = {
  id: 'wf-contain-2891',
  title: 'Threat Containment: TA-2891',
  steps: [
    {
      action: 'Isolate',
      target: 'Finance DB',
      description: 'Segment from production network to prevent exfiltration',
    },
    {
      action: 'Rotate',
      target: 'Identity Provider',
      description: 'Force credential rotation for all privileged accounts',
    },
    {
      action: 'Block',
      target: 'Mail Gateway',
      description: 'Disable outbound relay for suspicious SMTP traffic',
    },
  ],
  recommendedAt: minsAgo(15),
  status: 'pending',
};
