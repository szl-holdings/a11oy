// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Eye,
  Lock,
  Shield,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface PolicyDecision {
  id: string;
  timestamp: Date;
  agent: string;
  domain: string;
  action: string;
  actionType:
    | 'data_access'
    | 'external_api'
    | 'financial_transaction'
    | 'cross_domain'
    | 'agent_spawn';
  decision: 'permitted' | 'blocked' | 'escalated';
  policyRule: string;
  riskScore: number;
  details: string;
}

const ACTION_TYPE_LABELS: Record<string, string> = {
  data_access: 'Data Access',
  external_api: 'External API',
  financial_transaction: 'Financial',
  cross_domain: 'Cross-Domain',
  agent_spawn: 'Agent Spawn',
};

const _SEED_DECISIONS: PolicyDecision[] = [
  {
    id: 'pd1',
    timestamp: new Date(Date.now() - 5000),
    agent: 'Maritime Analyst',
    domain: 'SEXTANT',
    action: 'Read vessel AIS history (30 days)',
    actionType: 'data_access',
    decision: 'permitted',
    policyRule: 'SHIP-DATA-READ-001',
    riskScore: 12,
    details: 'Routine domain data access — within maritime agent scope.',
  },
  {
    id: 'pd2',
    timestamp: new Date(Date.now() - 18000),
    agent: 'IT Sentinel',
    domain: 'PARAGON Operations',
    action: 'Write auto-remediation script to production server',
    actionType: 'external_api',
    decision: 'escalated',
    policyRule: 'PROD-WRITE-REQUIRE-HUMAN',
    riskScore: 67,
    details: 'Production write operations require human operator approval per SZL-SEC-022.',
  },
  {
    id: 'pd3',
    timestamp: new Date(Date.now() - 35000),
    agent: 'Portfolio Analyst',
    domain: 'PARAGON',
    action: 'Read cross-app financial metrics (all 12 apps)',
    actionType: 'cross_domain',
    decision: 'permitted',
    policyRule: 'PORTFOLIO-CROSS-READ-001',
    riskScore: 28,
    details: 'Portfolio analyst has cross-domain read access per enterprise policy.',
  },
  {
    id: 'pd4',
    timestamp: new Date(Date.now() - 52000),
    agent: 'Deal Scout',
    domain: 'DOMAINE',
    action: 'Initiate API call to CoStar property database',
    actionType: 'external_api',
    decision: 'permitted',
    policyRule: 'EXT-API-COSTAR-APPROVED',
    riskScore: 22,
    details: 'CoStar API is pre-approved for DOMAINE domain agents.',
  },
  {
    id: 'pd5',
    timestamp: new Date(Date.now() - 78000),
    agent: 'Advisory Agent',
    domain: 'Carlota Jo',
    action: 'Access client financial records for briefing prep',
    actionType: 'data_access',
    decision: 'blocked',
    policyRule: 'CLIENT-DATA-ACCESS-RESTRICTED',
    riskScore: 89,
    details:
      'Client financial records require explicit client consent flag. Flag not set for this request.',
  },
  {
    id: 'pd6',
    timestamp: new Date(Date.now() - 102000),
    agent: 'Orchestration Engine',
    domain: 'Intelligence Platform',
    action: 'Spawn sub-agent with cross-domain write permissions',
    actionType: 'agent_spawn',
    decision: 'blocked',
    policyRule: 'AGENT-SPAWN-WRITE-PROHIBITED',
    riskScore: 94,
    details:
      'Sub-agents cannot be spawned with elevated permissions without explicit authorization chain.',
  },
  {
    id: 'pd7',
    timestamp: new Date(Date.now() - 130000),
    agent: 'Counsel Engine',
    domain: 'Counsel',
    action: 'Access DOMAINE signals for scenario model update',
    actionType: 'data_access',
    decision: 'permitted',
    policyRule: 'CROSS-DOMAIN-READ-ALLOY-001',
    riskScore: 18,
    details: 'Counsel Engine has read access to DOMAINE telemetry for model inputs.',
  },
  {
    id: 'pd8',
    timestamp: new Date(Date.now() - 185000),
    agent: 'Brand Monitor',
    domain: 'Stephen',
    action: 'Read public sentiment API — Twitter/X firehose',
    actionType: 'external_api',
    decision: 'permitted',
    policyRule: 'PUBLIC-DATA-READ-001',
    riskScore: 5,
    details: 'Public data aggregation is unrestricted.',
  },
  {
    id: 'pd9',
    timestamp: new Date(Date.now() - 210000),
    agent: 'Portfolio Analyst',
    domain: 'PARAGON',
    action: 'Initiate ACH transfer to portfolio company account',
    actionType: 'financial_transaction',
    decision: 'blocked',
    policyRule: 'FINANCIAL-TRANSACTION-NO-AI-AUTONOMOUS',
    riskScore: 99,
    details:
      'Financial transactions are fully prohibited for autonomous AI agents. Requires dual human authorization.',
  },
  {
    id: 'pd10',
    timestamp: new Date(Date.now() - 275000),
    agent: 'IT Sentinel',
    domain: 'PARAGON Operations',
    action: 'Read all client device inventories across PARAGON Operations accounts',
    actionType: 'data_access',
    decision: 'permitted',
    policyRule: 'MSP-AGENT-FULL-READ',
    riskScore: 35,
    details: 'IT Sentinel has full read access to PARAGON Operations domain data within its scope.',
  },
];

const POLICY_STATS = [
  { label: 'Actions Today', value: '7,234', color: 'text-foreground' },
  { label: 'Permitted', value: '7,188', sub: '99.4%', color: 'text-[#c9b787]' },
  { label: 'Escalated', value: '38', sub: '0.5%', color: 'text-[#c9b787]' },
  { label: 'Blocked', value: '8', sub: '0.1%', color: 'text-[#f5f5f5]' },
  { label: 'Agents Monitored', value: '9', color: 'text-[#c9b787]' },
  { label: 'Policy Rules Active', value: '247', color: 'text-foreground' },
];

const POLICY_CATEGORIES = [
  {
    name: 'Data Access Policies',
    count: 89,
    description: 'Controls which agents can read which data domains',
    status: 'enforcing',
  },
  {
    name: 'External API Policies',
    count: 64,
    description: 'Approved and blocked external service endpoints',
    status: 'enforcing',
  },
  {
    name: 'Financial Transaction Rules',
    count: 12,
    description: 'All financial operations require human authorization',
    status: 'strict',
  },
  {
    name: 'Agent Spawn Policies',
    count: 28,
    description: 'Controls agent creation and permission inheritance',
    status: 'enforcing',
  },
  {
    name: 'Cross-Domain Access Rules',
    count: 54,
    description: 'Governs data flow between ecosystem applications',
    status: 'enforcing',
  },
];

const DECISION_COLORS = {
  permitted: {
    color: 'text-[#c9b787]',
    bg: 'bg-[#c9b787]/10',
    icon: CheckCircle2,
    dot: 'bg-[#c9b787]',
  },
  blocked: {
    color: 'text-[#f5f5f5]',
    bg: 'bg-[#f5f5f5]/10',
    icon: XCircle,
    dot: 'bg-[#f5f5f5] animate-pulse',
  },
  escalated: {
    color: 'text-[#c9b787]',
    bg: 'bg-[#c9b787]/10',
    icon: AlertTriangle,
    dot: 'bg-[#c9b787] animate-pulse',
  },
};

export default function AdaptiveDefenseShield() {
  const [decisions, setDecisions] = useState<PolicyDecision[]>([]);
  const [filter, setFilter] = useState<'all' | 'permitted' | 'blocked' | 'escalated'>('all');
  const [expandedPolicy, setExpandedPolicy] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  const fetchDecisions = useCallback(async () => {
    try {
      const data = await api.adaptiveDefense.decisions(50);
      if (data?.decisions?.length) {
        const mapped: PolicyDecision[] = data.decisions.map((d: { id: string; decidedAt?: string; createdAt?: string; agentName: string; domain: string; action: string; actionType: PolicyDecision['actionType']; decision: PolicyDecision['decision']; policyRule: string; riskScore?: number; details?: string }) => ({
          id: d.id,
          timestamp: new Date(d.decidedAt ?? d.createdAt ?? Date.now()),
          agent: d.agentName,
          domain: d.domain,
          action: d.action,
          actionType: d.actionType,
          decision: d.decision,
          policyRule: d.policyRule,
          riskScore: d.riskScore ?? 0,
          details: d.details ?? '',
        }));
        setDecisions(mapped);
      }
    } catch {
      /* leave decisions as-is on transient error */
    }
  }, []);

  useEffect(() => {
    fetchDecisions();
  }, [fetchDecisions]);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(fetchDecisions, 30_000);
    return () => clearInterval(t);
  }, [paused, fetchDecisions]);

  const filtered = filter === 'all' ? decisions : decisions.filter((d) => d.decision === filter);
  const permittedCount = decisions.filter((d) => d.decision === 'permitted').length;
  const blockedCount = decisions.filter((d) => d.decision === 'blocked').length;
  const escalatedCount = decisions.filter((d) => d.decision === 'escalated').length;

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-[1600px]">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-9 h-9 rounded-xl bg-[#c9b787]/10 flex items-center justify-center">
            <Shield className="w-5 h-5 text-[#c9b787]" />
          </div>
          <div>
            <h1 className="text-xl font-display font-bold text-[#c9b787] tracking-tight">
              Adaptive Defense
            </h1>
            <p className="text-xs text-[#c9b787]/50 font-mono uppercase tracking-wider">
              Agent Security Guardrails
            </p>
          </div>
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-[#c9b787]/10 text-[#c9b787] border border-[#c9b787]/20 animate-pulse">
            ENFORCING
          </span>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Every agent action passes through this policy engine before execution. Governs data
          access, external API calls, financial transactions, and agent spawning across the entire
          platform.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {POLICY_STATS.map((s) => (
          <div key={s.label} className="bg-[#c9b787]/5 border border-[#c9b787]/15 rounded-xl p-4">
            <p className={cn('text-2xl font-display font-bold', s.color)}>{s.value}</p>
            {s.sub && <p className={cn('text-[10px] font-mono', s.color)}>{s.sub}</p>}
            <p className="text-[10px] text-muted-foreground mt-0.5 font-medium">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Policy categories */}
      <div className="bg-card/60 border border-[#c9b787]/15 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[#c9b787]/10">
          <h3 className="text-sm font-display font-semibold text-[#c9b787] flex items-center gap-2">
            <Lock className="w-3.5 h-3.5 text-[#c9b787]" />
            Active Policy Frameworks
          </h3>
        </div>
        <div className="divide-y divide-orange-500/5">
          {POLICY_CATEGORIES.map((cat) => (
            <button
              key={cat.name}
              onClick={() => setExpandedPolicy(expandedPolicy === cat.name ? null : cat.name)}
              className="w-full flex items-center gap-4 px-5 py-3 hover:bg-[#c9b787]/3 transition-colors text-left"
            >
              <Shield className="w-4 h-4 text-[#c9b787] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-foreground">{cat.name}</p>
                {expandedPolicy === cat.name && (
                  <p className="text-[10px] text-muted-foreground mt-0.5">{cat.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[10px] font-mono text-muted-foreground">
                  {cat.count} rules
                </span>
                <span
                  className={cn(
                    'text-[10px] font-mono px-2 py-0.5 rounded',
                    cat.status === 'strict'
                      ? 'bg-[#f5f5f5]/10 text-[#f5f5f5]'
                      : 'bg-[#c9b787]/10 text-[#c9b787]',
                  )}
                >
                  {cat.status}
                </span>
                {expandedPolicy === cat.name ? (
                  <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Decision stream */}
      <div className="bg-card/60 border border-[#c9b787]/15 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[#c9b787]/10 flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-display font-semibold text-[#c9b787] flex items-center gap-2">
            <Eye className="w-3.5 h-3.5 text-[#c9b787]" />
            Policy Decision Stream
            <span className="w-2 h-2 rounded-full bg-[#c9b787] animate-pulse" />
          </h3>
          <div className="flex items-center gap-2">
            <div className="flex bg-[#c9b787]/5 border border-[#c9b787]/10 p-0.5 rounded-lg">
              {(['all', 'permitted', 'blocked', 'escalated'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    'px-2.5 py-1 rounded text-[10px] font-medium capitalize transition-colors',
                    filter === f
                      ? 'bg-[#c9b787]/20 text-[#c9b787]'
                      : 'text-[#c9b787]/40 hover:text-[#c9b787]',
                  )}
                >
                  {f === 'all'
                    ? `All (${decisions.length})`
                    : f === 'permitted'
                      ? `✓ ${permittedCount}`
                      : f === 'blocked'
                        ? `✗ ${blockedCount}`
                        : `⚠ ${escalatedCount}`}
                </button>
              ))}
            </div>
            <button
              onClick={() => setPaused((p) => !p)}
              className={cn(
                'text-[10px] font-mono px-2 py-1 rounded border transition-colors',
                paused
                  ? 'border-[#c9b787]/30 text-[#c9b787]'
                  : 'border-[#c9b787]/20 text-[#c9b787]/60',
              )}
            >
              {paused ? '▶' : '⏸'}
            </button>
          </div>
        </div>
        <div className="divide-y divide-orange-500/5 max-h-[480px] overflow-y-auto">
          {filtered.map((d, i) => {
            const dc = DECISION_COLORS[d.decision];
            const DecisionIcon = dc.icon;
            return (
              <div
                key={d.id}
                className={cn(
                  'px-5 py-3 hover:bg-[#c9b787]/3 transition-colors',
                  i === 0 && !paused && 'bg-[#c9b787]/5',
                )}
              >
                <div className="flex items-start gap-3">
                  <DecisionIcon className={cn('w-4 h-4 shrink-0 mt-0.5', dc.color)} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="text-xs font-semibold text-foreground">{d.action}</span>
                      <span
                        className={cn(
                          'text-[9px] font-mono px-1.5 py-0.5 rounded',
                          dc.bg,
                          dc.color,
                        )}
                      >
                        {d.decision}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="text-[#c9b787]/60">{d.agent}</span>
                      <span className="text-border">·</span>
                      <span>{d.domain}</span>
                      <span className="text-border">·</span>
                      <span className="font-mono">{ACTION_TYPE_LABELS[d.actionType]}</span>
                      <span className="text-border">·</span>
                      <span
                        className={cn(
                          'font-mono',
                          d.riskScore >= 80
                            ? 'text-[#f5f5f5]'
                            : d.riskScore >= 50
                              ? 'text-[#c9b787]'
                              : 'text-[#c9b787]',
                        )}
                      >
                        risk: {d.riskScore}
                      </span>
                    </div>
                    {d.decision !== 'permitted' && (
                      <p className="text-[10px] text-muted-foreground/60 mt-0.5">{d.details}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-[10px] font-mono text-muted-foreground/50">
                      {Math.round((Date.now() - d.timestamp.getTime()) / 1000)}s ago
                    </p>
                    <p className="text-[9px] font-mono text-[#c9b787]/30">{d.policyRule}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Risk distribution */}
      <div className="bg-card/60 border border-[#c9b787]/15 rounded-xl p-5">
        <h3 className="text-sm font-display font-semibold text-[#c9b787] mb-4 flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-[#c9b787]" />
          Risk Score Distribution (Live Window)
        </h3>
        <div className="flex items-end gap-1 h-24">
          {[5, 12, 18, 8, 14, 9, 6, 3, 4, 2, 1, 1].map((val, i) => {
            const maxVal = 18;
            const pct = (val / maxVal) * 100;
            const riskZone =
              i <= 4 ? 'bg-[#c9b787]/50' : i <= 7 ? 'bg-[#c9b787]/50' : 'bg-[#f5f5f5]/50';
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className={cn('w-full rounded-t transition-all', riskZone)}
                  style={{ height: `${pct}%` }}
                />
                <span className="text-[8px] font-mono text-muted-foreground/40">{i * 10}</span>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-6 mt-2 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded bg-[#c9b787]/50 inline-block" />
            Low risk (0–40)
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded bg-[#c9b787]/50 inline-block" />
            Medium risk (50–70)
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded bg-[#f5f5f5]/50 inline-block" />
            High risk (80–100)
          </span>
        </div>
      </div>
    </div>
  );
}
