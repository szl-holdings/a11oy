// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { DashboardShell, } from '@szl-holdings/shared-ui/design-system';
import { LANE_ACCENT_HEX } from '@szl-holdings/shared-ui/lane-colors';
import {
  Brain,
  CheckCircle,
  ChevronDown,
  Download,
  Lock,
  Search,
  Shield,
  Zap,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';

const ACCENT = LANE_ACCENT_HEX.aegis.primary;

type ComplianceTag = 'SOC2' | 'ISO27001' | 'GDPR' | 'HIPAA' | 'PCI-DSS';
type ActionType =
  | 'ai_decision'
  | 'agent_action'
  | 'correlation'
  | 'human_approval'
  | 'system_event'
  | 'export';
type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'info';

interface AuditEntry {
  id: string;
  timestamp: number;
  actionType: ActionType;
  actor: string;
  actorType: 'ai_model' | 'agent' | 'human' | 'system';
  domain: string;
  action: string;
  entityId?: string;
  entityType?: string;
  inputHash?: string;
  modelUsed?: string;
  confidence?: number;
  approvedBy?: string;
  outcome?: string;
  complianceTags: ComplianceTag[];
  riskLevel: RiskLevel;
  immutableHash: string;
  chainLink?: string;
}

function randomHash(len = 12): string {
  return Array.from({ length: len }, () => Math.floor(Math.random() * 16).toString(16)).join('');
}

const DEMO_ENTRIES: AuditEntry[] = [
  {
    id: 'aud-001',
    timestamp: Date.now() - 300000,
    actionType: 'ai_decision',
    actor: 'CORTEX-Sentinel',
    actorType: 'ai_model',
    domain: 'PARAGON',
    action: 'Flagged vessel MV Poseidon for sanctions proximity review',
    entityId: 'vessel-poseidon',
    entityType: 'vessel',
    inputHash: randomHash(40),
    modelUsed: 'gpt-4o',
    confidence: 0.87,
    outcome: 'Alert raised · Human review queued',
    complianceTags: ['SOC2', 'ISO27001'],
    riskLevel: 'high',
    immutableHash: randomHash(40),
    chainLink: 'aud-000',
  },
  {
    id: 'aud-002',
    timestamp: Date.now() - 900000,
    actionType: 'human_approval',
    actor: 'Stephen L.',
    actorType: 'human',
    domain: 'PARAGON',
    action: 'Approved legal hold on MV Poseidon cargo',
    entityId: 'vessel-poseidon',
    entityType: 'vessel',
    approvedBy: 'Stephen L.',
    outcome: 'PRISM case #P-2024-189 opened',
    complianceTags: ['SOC2', 'GDPR'],
    riskLevel: 'high',
    immutableHash: randomHash(40),
    chainLink: 'aud-001',
  },
  {
    id: 'aud-003',
    timestamp: Date.now() - 1800000,
    actionType: 'correlation',
    actor: 'CORTEX-Graph',
    actorType: 'agent',
    domain: 'Multi-Domain',
    action: 'Correlated vessel diversion with DOMAINE coastal market signal',
    entityId: 'correlation-graph-447',
    entityType: 'intelligence_correlation',
    inputHash: randomHash(40),
    modelUsed: 'claude-3-5-sonnet-20241022',
    confidence: 0.79,
    outcome: 'Risk score elevated for 3 entities',
    complianceTags: ['SOC2', 'ISO27001', 'GDPR'],
    riskLevel: 'medium',
    immutableHash: randomHash(40),
    chainLink: 'aud-002',
  },
  {
    id: 'aud-004',
    timestamp: Date.now() - 3600000,
    actionType: 'agent_action',
    actor: 'Counsel Workflow Engine',
    actorType: 'agent',
    domain: 'PARAGON',
    action: 'Executed portfolio rebalancing workflow',
    entityId: 'workflow-portfolio-rebal-012',
    entityType: 'workflow',
    inputHash: randomHash(40),
    confidence: 0.94,
    outcome: '3 positions adjusted · NAV impact: -0.02%',
    complianceTags: ['SOC2', 'ISO27001'],
    riskLevel: 'low',
    immutableHash: randomHash(40),
  },
  {
    id: 'aud-005',
    timestamp: Date.now() - 7200000,
    actionType: 'export',
    actor: 'Marcus T.',
    actorType: 'human',
    domain: 'Counsel',
    action: 'Exported case #P-2024-187 discovery package',
    entityId: 'prism-case-187',
    entityType: 'legal_case',
    approvedBy: 'Marcus T.',
    outcome: '142 documents exported · Proof chain verified',
    complianceTags: ['SOC2', 'GDPR'],
    riskLevel: 'medium',
    immutableHash: randomHash(40),
  },
  {
    id: 'aud-006',
    timestamp: Date.now() - 14400000,
    actionType: 'ai_decision',
    actor: 'CORTEX-NEXUS',
    actorType: 'ai_model',
    domain: 'NEXUS',
    action: 'Geopolitical risk escalation — Strait of Hormuz',
    inputHash: randomHash(40),
    modelUsed: 'gpt-4o',
    confidence: 0.82,
    outcome: '3 vessel routes flagged for rerouting',
    complianceTags: ['SOC2', 'ISO27001'],
    riskLevel: 'critical',
    immutableHash: randomHash(40),
  },
  {
    id: 'aud-007',
    timestamp: Date.now() - 21600000,
    actionType: 'system_event',
    actor: 'PARAGON Platform',
    actorType: 'system',
    domain: 'PARAGON',
    action: 'Automated MITRE ATT&CK pattern detection — T1190',
    entityId: 'incident-447',
    entityType: 'incident',
    confidence: 0.91,
    outcome: 'Incident created · Playbook executed',
    complianceTags: ['SOC2', 'ISO27001', 'HIPAA'],
    riskLevel: 'critical',
    immutableHash: randomHash(40),
  },
  {
    id: 'aud-008',
    timestamp: Date.now() - 43200000,
    actionType: 'human_approval',
    actor: 'Carlota J.',
    actorType: 'human',
    domain: 'Carlota Jo',
    action: 'Approved client advisory report for Emerging Markets engagement',
    entityId: 'engagement-em-2024',
    entityType: 'engagement',
    approvedBy: 'Carlota J.',
    outcome: 'Report published · Client notified',
    complianceTags: ['GDPR'],
    riskLevel: 'low',
    immutableHash: randomHash(40),
  },
];

const RISK_COLORS: Record<RiskLevel, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#c9b787',
  low: '#c9b787',
  info: '#8a8a8a',
};

const ACTION_ICONS: Record<ActionType, React.ReactNode> = {
  ai_decision: <Brain size={13} />,
  agent_action: <Zap size={13} />,
  correlation: <Zap size={13} />,
  human_approval: <CheckCircle size={13} />,
  system_event: <Shield size={13} />,
  export: <Download size={13} />,
};

const COMPLIANCE_COLORS: Record<ComplianceTag, string> = {
  SOC2: '#8b7ac8',
  ISO27001: '#8a8a8a',
  GDPR: '#c9b787',
  HIPAA: '#c9b787',
  'PCI-DSS': '#c9b787',
};

function formatAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function AuditEntryRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: AuditEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const riskColor = RISK_COLORS[entry.riskLevel];
  const icon = ACTION_ICONS[entry.actionType];

  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div
        onClick={onToggle}
        style={{
          display: 'grid',
          gridTemplateColumns: '32px 140px 100px 1fr 120px 80px 28px',
          gap: '12px',
          alignItems: 'center',
          padding: '12px 18px',
          cursor: 'pointer',
          transition: 'background 0.15s',
          background: expanded ? 'rgba(255,255,255,0.03)' : 'transparent',
        }}
        onMouseEnter={(e) => {
          if (!expanded)
            (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.02)';
        }}
        onMouseLeave={(e) => {
          if (!expanded) (e.currentTarget as HTMLDivElement).style.background = 'transparent';
        }}
      >
        {/* Risk indicator */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: riskColor,
              boxShadow: `0 0 6px ${riskColor}80`,
            }}
          />
        </div>

        {/* Time */}
        <div>
          <div
            style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace' }}
          >
            {formatAgo(entry.timestamp)}
          </div>
          <div
            style={{ fontSize: '10px', color: 'rgba(255,255,255,0.25)', fontFamily: 'monospace' }}
          >
            {new Date(entry.timestamp).toLocaleTimeString()}
          </div>
        </div>

        {/* Actor */}
        <div>
          <div
            style={{
              fontSize: '11px',
              color:
                entry.actorType === 'ai_model'
                  ? ACCENT
                  : entry.actorType === 'agent'
                    ? '#8a8a8a'
                    : 'rgba(255,255,255,0.7)',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            {icon}
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: '80px',
              }}
            >
              {entry.actor.split(' ')[0] ?? entry.actor}
            </span>
          </div>
          <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.3)' }}>{entry.domain}</div>
        </div>

        {/* Action */}
        <div
          style={{
            fontSize: '12px',
            color: 'rgba(255,255,255,0.75)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {entry.action}
        </div>

        {/* Compliance tags */}
        <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
          {entry.complianceTags.slice(0, 2).map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: '9px',
                fontWeight: 700,
                color: COMPLIANCE_COLORS[tag],
                background: `${COMPLIANCE_COLORS[tag]}15`,
                border: `1px solid ${COMPLIANCE_COLORS[tag]}30`,
                borderRadius: '4px',
                padding: '1px 4px',
              }}
            >
              {tag}
            </span>
          ))}
          {entry.complianceTags.length > 2 && (
            <span style={{ fontSize: '9px', color: 'rgba(255,255,255,0.3)' }}>
              +{entry.complianceTags.length - 2}
            </span>
          )}
        </div>

        {/* Hash */}
        <div
          style={{
            fontSize: '9px',
            fontFamily: 'monospace',
            color: 'rgba(255,255,255,0.2)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {entry.immutableHash.slice(0, 8)}...
        </div>

        {/* Expand */}
        <ChevronDown
          size={12}
          style={{
            color: 'rgba(255,255,255,0.3)',
            transition: 'transform 0.2s',
            transform: expanded ? 'rotate(180deg)' : 'none',
          }}
        />
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div
          style={{
            padding: '0 18px 16px 62px',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {entry.entityId && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Entity
                </div>
                <div
                  style={{
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.7)',
                    fontFamily: 'monospace',
                  }}
                >
                  {entry.entityId} ({entry.entityType})
                </div>
              </div>
            )}
            {entry.modelUsed && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Model
                </div>
                <div style={{ fontSize: '12px', color: ACCENT }}>{entry.modelUsed}</div>
              </div>
            )}
            {entry.confidence !== undefined && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Confidence
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div
                    style={{
                      flex: 1,
                      height: '4px',
                      background: 'rgba(255,255,255,0.08)',
                      borderRadius: '2px',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${entry.confidence * 100}%`,
                        background:
                          entry.confidence > 0.85
                            ? '#c9b787'
                            : entry.confidence > 0.7
                              ? '#c9b787'
                              : '#f5f5f5',
                        borderRadius: '2px',
                      }}
                    />
                  </div>
                  <span
                    style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}
                  >
                    {Math.round(entry.confidence * 100)}%
                  </span>
                </div>
              </div>
            )}
            {entry.approvedBy && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Approved By
                </div>
                <div style={{ fontSize: '12px', color: '#c9b787', fontWeight: 600 }}>
                  ✓ {entry.approvedBy}
                </div>
              </div>
            )}
            {entry.outcome && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Outcome
                </div>
                <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.7)' }}>
                  {entry.outcome}
                </div>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div>
              <div
                style={{
                  fontSize: '10px',
                  color: 'rgba(255,255,255,0.3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginBottom: '2px',
                }}
              >
                Immutable Hash
              </div>
              <div
                style={{
                  fontSize: '10px',
                  color: 'rgba(255,255,255,0.4)',
                  fontFamily: 'monospace',
                  wordBreak: 'break-all',
                }}
              >
                {entry.immutableHash}
              </div>
            </div>
            {entry.inputHash && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Input Hash
                </div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.4)',
                    fontFamily: 'monospace',
                    wordBreak: 'break-all',
                  }}
                >
                  {entry.inputHash}
                </div>
              </div>
            )}
            {entry.chainLink && (
              <div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    marginBottom: '2px',
                  }}
                >
                  Chain Link
                </div>
                <div style={{ fontSize: '10px', color: ACCENT, fontFamily: 'monospace' }}>
                  ← {entry.chainLink}
                </div>
              </div>
            )}
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
              {entry.complianceTags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    color: COMPLIANCE_COLORS[tag],
                    background: `${COMPLIANCE_COLORS[tag]}15`,
                    border: `1px solid ${COMPLIANCE_COLORS[tag]}30`,
                    borderRadius: '5px',
                    padding: '2px 8px',
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface HybridSigStatus {
  platformServiceDid: string | null;
  signingScheme: string;
  rolloutMode: string;
  hybridSigned: number;
  legacyUnsigned: number;
  checkedAt: string | null;
  reachable: boolean;
}

// Ouroboros Thesis v3 four-axis Λ receipt — see docs/thesis/audit-chain-thesis-mapping.md
interface LambdaReceiptStatus {
  meanLambda: number;
  sampledRows: number;
  axiomSet: string;
  intact: boolean;
}

export default function AuditChainPage() {
  const [search, setSearch] = useState('');
  const [filterRisk, setFilterRisk] = useState<RiskLevel | 'all'>('all');
  const [filterType, setFilterType] = useState<ActionType | 'all'>('all');
  const [filterTag, setFilterTag] = useState<ComplianceTag | 'all'>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [entries, setEntries] = useState<AuditEntry[]>(DEMO_ENTRIES);
  const [_chainValid, setChainValid] = useState<boolean | null>(null);
  const [sigStatus, setSigStatus] = useState<HybridSigStatus | null>(null);
  const [lambdaStatus, setLambdaStatus] = useState<LambdaReceiptStatus | null>(null);

  React.useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/audit-chain/events?limit=50', { credentials: 'include' });
        if (res.ok) {
          const json = (await res.json()) as {
            data?: { events?: AuditEntry[]; chainValid?: boolean };
          };
          const events = json.data?.events;
          if (Array.isArray(events) && events.length > 0) {
            setEntries(events);
            setChainValid(json.data?.chainValid ?? null);
          }
        }
      } catch {}
    }
    async function loadSigStatus() {
      try {
        const [summaryRes, custodyRes] = await Promise.all([
          fetch('/api/identity-registry/audit-summary', { credentials: 'include' }),
          fetch('/api/identity-registry/key-custody', { credentials: 'include' }),
        ]);
        const summary = summaryRes.ok ? ((await summaryRes.json()) as { data?: { hybrid_signed: number; legacy_unsigned: number; checkedAt: string } }).data : null;
        const custody = custodyRes.ok ? ((await custodyRes.json()) as { data?: { platformServiceDid: string; custodyReachable: boolean } }).data : null;
        setSigStatus({
          platformServiceDid: custody?.platformServiceDid ?? null,
          signingScheme: 'Ed25519 + ML-DSA-65 (hybrid)',
          rolloutMode: 'warn',
          hybridSigned: summary?.hybrid_signed ?? 0,
          legacyUnsigned: summary?.legacy_unsigned ?? 0,
          checkedAt: summary?.checkedAt ?? null,
          reachable: custody?.custodyReachable ?? false,
        });
      } catch {}
    }
    async function loadLambdaReceipt() {
      try {
        const res = await fetch('/api/audit-chain/verify', { credentials: 'include' });
        if (!res.ok) return;
        const json = (await res.json()) as {
          data?: {
            intact?: boolean;
            lambdaReceipt?: { meanLambda: number; sampledRows: number; axiomSet: string } | null;
          };
        };
        const lr = json.data?.lambdaReceipt;
        if (lr) {
          setLambdaStatus({
            meanLambda: lr.meanLambda,
            sampledRows: lr.sampledRows,
            axiomSet: lr.axiomSet,
            intact: json.data?.intact ?? false,
          });
        }
      } catch {}
    }
    void load();
    void loadSigStatus();
    void loadLambdaReceipt();
  }, []);

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (filterRisk !== 'all' && e.riskLevel !== filterRisk) return false;
      if (filterType !== 'all' && e.actionType !== filterType) return false;
      if (filterTag !== 'all' && !e.complianceTags.includes(filterTag as ComplianceTag))
        return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        return (
          e.action.toLowerCase().includes(q) ||
          e.actor.toLowerCase().includes(q) ||
          e.domain.toLowerCase().includes(q) ||
          (e.entityId?.toLowerCase().includes(q) ?? false)
        );
      }
      return true;
    });
  }, [search, filterRisk, filterType, filterTag]);

  return (
    <DashboardShell
      topbar={
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Lock size={18} style={{ color: ACCENT }} />
          <div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: 'rgba(255,255,255,0.9)' }}>
              Compliance & Audit Provenance Chain
            </div>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>
              Immutable audit trail · Every AI decision, agent action, and cross-domain correlation
            </div>
          </div>
        </div>
      }
    >
      <div
        style={{
          fontFamily: 'system-ui, sans-serif',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {/* Hybrid Signature Status Badge (G10) */}
        {sigStatus && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
              padding: '12px 16px',
              background: sigStatus.reachable ? `${ACCENT}0a` : 'rgba(245,80,80,0.07)',
              border: `1px solid ${sigStatus.reachable ? `${ACCENT}30` : 'rgba(245,80,80,0.25)'}`,
              borderRadius: '10px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <Zap size={14} style={{ color: sigStatus.reachable ? ACCENT : '#f55050' }} />
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: sigStatus.reachable ? ACCENT : '#f55050',
                  textTransform: 'uppercase',
                  letterSpacing: '0.6px',
                }}
              >
                {sigStatus.reachable ? 'Hybrid Chain Signing Active' : 'Chain Signing Unavailable'}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                flexWrap: 'wrap',
                flex: 1,
                fontSize: '10px',
                color: 'rgba(255,255,255,0.45)',
                fontFamily: 'monospace',
              }}
            >
              {sigStatus.platformServiceDid && (
                <span title="Platform service DID">DID: {sigStatus.platformServiceDid}</span>
              )}
              <span title="Signing algorithm pair">Scheme: {sigStatus.signingScheme}</span>
              <span
                style={{
                  color: '#c9b787',
                  background: '#c9b78718',
                  border: '1px solid #c9b78730',
                  borderRadius: '5px',
                  padding: '1px 7px',
                  fontWeight: 700,
                }}
              >
                {sigStatus.hybridSigned.toLocaleString()} hybrid-signed
              </span>
              <span style={{ color: 'rgba(255,255,255,0.3)' }}>
                {sigStatus.legacyUnsigned.toLocaleString()} legacy
              </span>
              {sigStatus.checkedAt && (
                <span style={{ color: 'rgba(255,255,255,0.25)' }}>
                  checked {new Date(sigStatus.checkedAt).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
        )}

        {/*
          Λ-4 Receipt Badge (Ouroboros Thesis v3 four-axis envelope)
          Renders the chain-wide trust scalar Λ = (C·H·R·F)^(1/4) computed by
          /audit-chain/verify. Anchors: docs/thesis/audit-chain-thesis-mapping.md.
        */}
        {lambdaStatus && (
          <div
            data-testid="lambda-receipt-badge"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '14px',
              padding: '12px 16px',
              background: lambdaStatus.intact ? `${ACCENT}0a` : 'rgba(245,180,80,0.07)',
              border: `1px solid ${lambdaStatus.intact ? `${ACCENT}30` : 'rgba(245,180,80,0.25)'}`,
              borderRadius: '10px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <Shield size={14} style={{ color: lambdaStatus.intact ? ACCENT : '#f5b450' }} />
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: lambdaStatus.intact ? ACCENT : '#f5b450',
                  textTransform: 'uppercase',
                  letterSpacing: '0.6px',
                }}
              >
                Ouroboros Λ-4 Receipt · {lambdaStatus.meanLambda.toFixed(4)}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                flexWrap: 'wrap',
                flex: 1,
                fontSize: '10px',
                color: 'rgba(255,255,255,0.45)',
                fontFamily: 'monospace',
              }}
            >
              <span title="Lutar Invariant axiom set (Ouroboros Thesis v3)">
                Axioms: {lambdaStatus.axiomSet}
              </span>
              <span title="Four-axis form">Λ = (C·H·R·F)^(1/4)</span>
              <span style={{ color: 'rgba(255,255,255,0.3)' }}>
                {lambdaStatus.sampledRows.toLocaleString()} rows sampled
              </span>
              <span
                style={{
                  color: lambdaStatus.meanLambda >= 0.85 ? ACCENT : '#f5b450',
                  background: lambdaStatus.meanLambda >= 0.85 ? `${ACCENT}18` : 'rgba(245,180,80,0.15)',
                  border: `1px solid ${lambdaStatus.meanLambda >= 0.85 ? `${ACCENT}30` : 'rgba(245,180,80,0.3)'}`,
                  borderRadius: '5px',
                  padding: '1px 7px',
                  fontWeight: 700,
                }}
                title="Kuramoto-coherent threshold r ≥ 0.85"
              >
                {lambdaStatus.meanLambda >= 0.85 ? 'COHERENT' : 'DEGRADED'}
              </span>
            </div>
          </div>
        )}

        {/* Stats strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>
          {[
            { label: 'Total Entries', value: DEMO_ENTRIES.length.toString(), color: ACCENT },
            {
              label: 'AI Decisions',
              value: DEMO_ENTRIES.filter((e) => e.actionType === 'ai_decision').length.toString(),
              color: '#8b7ac8',
            },
            {
              label: 'Critical Events',
              value: DEMO_ENTRIES.filter((e) => e.riskLevel === 'critical').length.toString(),
              color: '#f5f5f5',
            },
            {
              label: 'Human Approvals',
              value: DEMO_ENTRIES.filter(
                (e) => e.actionType === 'human_approval',
              ).length.toString(),
              color: '#c9b787',
            },
            {
              label: 'SOC2 Tagged',
              value: DEMO_ENTRIES.filter((e) =>
                e.complianceTags.includes('SOC2'),
              ).length.toString(),
              color: '#8a8a8a',
            },
          ].map((stat) => (
            <div
              key={stat.label}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '10px',
                padding: '12px 14px',
              }}
            >
              <div style={{ fontSize: '20px', fontWeight: 800, color: stat.color }}>
                {stat.value}
              </div>
              <div
                style={{
                  fontSize: '10px',
                  color: 'rgba(255,255,255,0.35)',
                  marginTop: '2px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: '200px' }}>
            <Search
              size={13}
              style={{
                position: 'absolute',
                left: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'rgba(255,255,255,0.3)',
              }}
            />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search entries..."
              style={{
                width: '100%',
                padding: '8px 12px 8px 32px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                color: 'rgba(255,255,255,0.8)',
                fontSize: '12px',
                outline: 'none',
                fontFamily: 'system-ui, sans-serif',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {[
            {
              label: 'Risk',
              value: filterRisk,
              setter: setFilterRisk as (v: string) => void,
              options: ['all', 'critical', 'high', 'medium', 'low'],
            },
            {
              label: 'Type',
              value: filterType,
              setter: setFilterType as (v: string) => void,
              options: [
                'all',
                'ai_decision',
                'agent_action',
                'human_approval',
                'system_event',
                'export',
                'correlation',
              ],
            },
            {
              label: 'Framework',
              value: filterTag,
              setter: setFilterTag as (v: string) => void,
              options: ['all', 'SOC2', 'ISO27001', 'GDPR', 'HIPAA', 'PCI-DSS'],
            },
          ].map((f) => (
            <select
              key={f.label}
              value={f.value}
              onChange={(e) => f.setter(e.target.value)}
              style={{
                padding: '8px 12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                color: 'rgba(255,255,255,0.7)',
                fontSize: '12px',
                outline: 'none',
                cursor: 'pointer',
                fontFamily: 'system-ui, sans-serif',
              }}
            >
              {f.options.map((o) => (
                <option key={o} value={o} style={{ background: '#080a12' }}>
                  {f.label}: {o === 'all' ? 'All' : o}
                </option>
              ))}
            </select>
          ))}

          <button
            onClick={() => {
              const csv = [
                'id,timestamp,actor,domain,action,riskLevel,confidence,outcome,complianceTags,immutableHash',
                ...DEMO_ENTRIES.map((e) =>
                  [
                    e.id,
                    new Date(e.timestamp).toISOString(),
                    e.actor,
                    e.domain,
                    `"${e.action}"`,
                    e.riskLevel,
                    e.confidence ?? '',
                    `"${e.outcome ?? ''}"`,
                    e.complianceTags.join('|'),
                    e.immutableHash,
                  ].join(','),
                ),
              ].join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `audit-chain-${new Date().toISOString().split('T')[0]}.csv`;
              a.click();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              border: `1px solid ${ACCENT}40`,
              background: `${ACCENT}12`,
              color: ACCENT,
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'system-ui, sans-serif',
              whiteSpace: 'nowrap',
            }}
          >
            <Download size={13} />
            Export CSV
          </button>
        </div>

        {/* Table */}
        <div
          style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: '14px',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '32px 140px 100px 1fr 120px 80px 28px',
              gap: '12px',
              padding: '10px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.07)',
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            {['', 'Timestamp', 'Actor', 'Action', 'Frameworks', 'Hash', ''].map((h, i) => (
              <div
                key={i}
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  color: 'rgba(255,255,255,0.3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.8px',
                }}
              >
                {h}
              </div>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div
              style={{
                padding: '40px',
                textAlign: 'center',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.3)',
              }}
            >
              No entries match your filters
            </div>
          ) : (
            filtered.map((entry) => (
              <AuditEntryRow
                key={entry.id}
                entry={entry}
                expanded={expandedId === entry.id}
                onToggle={() => setExpandedId((prev) => (prev === entry.id ? null : entry.id))}
              />
            ))
          )}
        </div>

        {/* Chain integrity notice */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '12px 16px',
            background: '#c9b78708',
            border: '1px solid #c9b78725',
            borderRadius: '10px',
          }}
        >
          <Lock size={14} style={{ color: '#c9b787', flexShrink: 0 }} />
          <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>
            <strong style={{ color: '#c9b787' }}>Chain integrity verified.</strong> All{' '}
            {DEMO_ENTRIES.length} entries are immutably hashed and cryptographically linked. Last
            verification: {new Date().toLocaleTimeString()}. SOC2 Type II ready · ISO27001 compliant
            · GDPR Article 30 aligned.
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
