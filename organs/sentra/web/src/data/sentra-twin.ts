export interface CyberAsset {
  id: string;
  name: string;
  type: 'OT' | 'IT' | 'IoT';
  criticality: 'critical' | 'high' | 'medium' | 'low';
  exposureScore: number;
  backupStatus: 'current' | 'stale' | 'none';
  lastBackupAt?: string;
  controlGaps: string[];
  status: 'active' | 'compromised' | 'isolated';
}

export interface Incident {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'active' | 'contained' | 'resolved';
  mitreStage: string;
  detectedAt: string;
  description: string;
  affectedAssets: string[];
}

export interface ControlDrift {
  family: 'Identify' | 'Protect' | 'Detect' | 'Respond' | 'Recover';
  control: string;
  status: 'compliant' | 'drift_detected' | 'remediation_pending';
  evidence: string;
}

export interface SentraTwin {
  assets: CyberAsset[];
  incidents: Incident[];
  controlDrifts: ControlDrift[];
  recoveryPosture: number;
  financialExposure: number;
}

const now = new Date();
const hoursAgo = (n: number) => new Date(now.getTime() - n * 3600000).toISOString();

export const sentraTwin: SentraTwin = {
  assets: [
    {
      id: 'asset-001',
      name: 'SCADA Server',
      type: 'OT',
      criticality: 'critical',
      exposureScore: 88,
      backupStatus: 'stale',
      lastBackupAt: hoursAgo(72),
      controlGaps: ['Endpoint Isolation missing', 'MFA not enforced on admin'],
      status: 'compromised',
    },
    {
      id: 'asset-002',
      name: 'HMI Workstation',
      type: 'OT',
      criticality: 'high',
      exposureScore: 65,
      backupStatus: 'current',
      lastBackupAt: hoursAgo(12),
      controlGaps: ['Patching overdue'],
      status: 'active',
    },
    {
      id: 'asset-003',
      name: 'PLC Controller',
      type: 'OT',
      criticality: 'critical',
      exposureScore: 92,
      backupStatus: 'none',
      controlGaps: ['Network segmentation breach'],
      status: 'compromised',
    },
    {
      id: 'asset-004',
      name: 'Domain Controller',
      type: 'IT',
      criticality: 'critical',
      exposureScore: 45,
      backupStatus: 'stale',
      lastBackupAt: hoursAgo(48),
      controlGaps: ['RDP exposed'],
      status: 'active',
    },
  ],
  incidents: [
    {
      id: 'INC-2026-0891',
      title: 'Ransomware-Adjacent OT Payload Detected',
      severity: 'critical',
      status: 'active',
      mitreStage: 'Execution / C2',
      detectedAt: hoursAgo(4),
      description:
        'Encrypted payload detected on 3 OT assets (SCADA, PLC). Anomalous C2 beaconing to known malicious IPs.',
      affectedAssets: ['asset-001', 'asset-003'],
    },
  ],
  controlDrifts: [
    {
      family: 'Respond',
      control: 'Incident Response Plan',
      status: 'drift_detected',
      evidence: 'Isolation playbooks failed to execute on legacy SCADA systems.',
    },
    {
      family: 'Recover',
      control: 'Backup Verification',
      status: 'drift_detected',
      evidence: '2 critical server backups failed integrity check.',
    },
  ],
  recoveryPosture: 42,
  financialExposure: 2800000,
};

export const SENTRA_SIGNAL_LABELS = [
  {
    id: 'sig-sentra-001',
    label: 'Ransomware Payload Detected',
    severity: 'critical',
    occurredAt: hoursAgo(4),
  },
  {
    id: 'sig-sentra-002',
    label: 'Anomalous C2 Callback',
    severity: 'critical',
    occurredAt: hoursAgo(3.5),
  },
] as const;

export const SENTRA_RECOMMENDATION_LABELS = [
  { id: 'rec-sentra-001', title: 'Isolate Compromised OT Assets', confidence: 0.95 },
  { id: 'rec-sentra-002', title: 'Initiate Bare-Metal Recovery', confidence: 0.88 },
] as const;

export type {
  QuantumCryptoInventory,
  HardwareProvenanceChain,
  MicrosystemIntegrityRecord,
  PhotonicSensorNode,
  BioSubstrateAsset,
  ThreatHorizonVector,
} from './quantum-resilience';
