import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  History,
  Play,
  RefreshCw,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';

interface SignalChainStep {
  id: string;
  domain: string;
  action: string;
  status: 'pending' | 'executed' | 'skipped' | 'failed';
  executedAt?: number;
  explainability: string;
  resultSummary?: string;
}

interface SignalChainExecution {
  executionId: string;
  chainId: string;
  triggeredAt: number;
  triggerReason: string;
  triggerValue: number;
  threshold: number;
  steps: SignalChainStep[];
  status: 'running' | 'completed' | 'failed';
}

interface SignalChain {
  id: string;
  name: string;
  description: string;
  triggerDomain: string;
  triggerSignal: string;
  triggerThreshold: number;
  targetDomains: string[];
  severity: 'critical' | 'high' | 'medium' | 'low';
  enabled: boolean;
  executionCount: number;
  lastExecuted?: number;
  stepCount: number;
  lastExecution?: SignalChainExecution;
}

interface AuditRow {
  id: number;
  chainId: string;
  triggerDomain: string;
  payloadSnapshot: {
    executionId: string;
    triggerReason: string;
    triggerValue: number;
    threshold: number;
    auditRef?: string;
  } | null;
  outcomes: SignalChainStep[] | null;
  triggeredAt: string;
  status: 'running' | 'completed' | 'failed';
}

const DOMAIN_COLORS: Record<string, string> = {
  vessels: 'var(--gi-accent-blue)',
  aegis: '#ef4444',
  terra: '#22c55e',
  prism: '#8b5cf6',
  lyte: '#f59e0b',
  'szl-holdings': '#8b7ac8',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#6b7280',
};

const STATUS_COLORS: Record<string, string> = {
  completed: '#22c55e',
  failed: '#ef4444',
  running: '#f59e0b',
};

const DEMO_CHAINS: SignalChain[] = [
  {
    id: 'sc-fleet-reroute',
    name: 'Fleet Reroute on Weather Alert',
    description:
      'When weather severity exceeds threshold in an active shipping corridor, notify fleet ops and queue route optimization across affected vessels.',
    triggerDomain: 'vessels',
    triggerSignal: 'weather_severity_score',
    triggerThreshold: 0.7,
    targetDomains: ['terra', 'szl-holdings'],
    severity: 'high',
    enabled: true,
    executionCount: 14,
    lastExecuted: Date.now() - 3600000,
    stepCount: 4,
    lastExecution: {
      executionId: 'exec-fleet-0042',
      chainId: 'sc-fleet-reroute',
      triggeredAt: Date.now() - 3600000,
      triggerReason: 'Bay of Bengal weather severity score reached 0.78 (threshold: 0.70)',
      triggerValue: 0.78,
      threshold: 0.7,
      status: 'completed',
      steps: [
        {
          id: 'step-1',
          domain: 'vessels',
          action: 'Identify affected vessels',
          status: 'executed',
          executedAt: Date.now() - 3540000,
          explainability: 'Queried fleet positions — 3 vessels within affected corridor identified',
          resultSummary: 'MV Meridian, MV Catalyst, MV Horizon flagged',
        },
        {
          id: 'step-2',
          domain: 'vessels',
          action: 'Queue route optimization',
          status: 'executed',
          executedAt: Date.now() - 3480000,
          explainability:
            'Route optimization tasks queued for 3 vessels based on alternate corridor data',
          resultSummary: 'Estimated $180K fuel savings if approved',
        },
        {
          id: 'step-3',
          domain: 'terra',
          action: 'Flag logistics-dependent properties',
          status: 'executed',
          executedAt: Date.now() - 3420000,
          explainability: 'Identified 12 DOMAINE properties with active port logistics dependencies',
          resultSummary: '12 assets flagged for delivery timeline review',
        },
        {
          id: 'step-4',
          domain: 'szl-holdings',
          action: 'Update executive briefing',
          status: 'executed',
          executedAt: Date.now() - 3360000,
          explainability: 'Morning digest updated with fleet reroute context and estimated impact',
          resultSummary: 'Digest updated — financial exposure: ~$320K',
        },
      ],
    },
  },
  {
    id: 'sc-cyber-escalate',
    name: 'Perimeter Breach → Legal Hold',
    description:
      'When PARAGON detects a confirmed intrusion exceeding critical threshold, automatically trigger legal hold across affected subsidiaries and notify CISO.',
    triggerDomain: 'aegis',
    triggerSignal: 'intrusion_confidence_score',
    triggerThreshold: 0.85,
    targetDomains: ['szl-holdings', 'prism'],
    severity: 'critical',
    enabled: true,
    executionCount: 3,
    lastExecuted: Date.now() - 1800000,
    stepCount: 3,
    lastExecution: {
      executionId: 'exec-cyber-0011',
      chainId: 'sc-cyber-escalate',
      triggeredAt: Date.now() - 1800000,
      triggerReason: 'APT-41 lateral movement confidence score reached 0.97 (threshold: 0.85)',
      triggerValue: 0.97,
      threshold: 0.85,
      status: 'completed',
      steps: [
        {
          id: 'step-1',
          domain: 'aegis',
          action: 'Isolate affected network segments',
          status: 'executed',
          executedAt: Date.now() - 1740000,
          explainability:
            'Network isolation applied to 3 subsidiary segments exhibiting lateral movement indicators',
        },
        {
          id: 'step-2',
          domain: 'szl-holdings',
          action: 'Trigger legal hold',
          status: 'executed',
          executedAt: Date.now() - 1680000,
          explainability:
            'Legal hold initiated across 3 subsidiaries per incident response protocol',
        },
        {
          id: 'step-3',
          domain: 'prism',
          action: 'Generate threat intelligence brief',
          status: 'executed',
          executedAt: Date.now() - 1620000,
          explainability:
            'PRISM cross-domain pattern analysis completed — brief delivered to CISO and Legal',
        },
      ],
    },
  },
  {
    id: 'sc-market-vol',
    name: 'Market Volatility → Portfolio Rebalance',
    description:
      'When Holdings volatility index exceeds 0.70, trigger asset review across DOMAINE and SEXTANT, and queue rebalancing recommendation for the investment committee.',
    triggerDomain: 'szl-holdings',
    triggerSignal: 'market_volatility_index',
    triggerThreshold: 0.7,
    targetDomains: ['terra', 'vessels'],
    severity: 'medium',
    enabled: true,
    executionCount: 7,
    lastExecuted: Date.now() - 7200000,
    stepCount: 3,
  },
  {
    id: 'sc-slo-breach',
    name: 'SLO Breach → On-Call Escalation',
    description:
      'When KORA platform error budget drops below 10%, automatically page the on-call team and pause non-critical deployments.',
    triggerDomain: 'lyte',
    triggerSignal: 'error_budget_remaining',
    triggerThreshold: 0.1,
    targetDomains: ['lyte'],
    severity: 'high',
    enabled: false,
    executionCount: 2,
    lastExecuted: Date.now() - 86400000 * 3,
    stepCount: 2,
  },
];

function timeAgo(ts?: number | string) {
  if (!ts) return 'Never';
  const diff = Date.now() - (typeof ts === 'string' ? new Date(ts).getTime() : ts);
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.round(diff / 3600000)}h ago`;
  return `${Math.round(diff / 86400000)}d ago`;
}

interface SignalChainsPanelProps {
  apiBase?: string;
}

export function SignalChainsPanel({ apiBase = '' }: SignalChainsPanelProps) {
  const [chains, setChains] = useState<SignalChain[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState<boolean | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [auditView, setAuditView] = useState<string | null>(null);
  const [auditRows, setAuditRows] = useState<Record<string, AuditRow[]>>({});
  const [auditLoading, setAuditLoading] = useState<string | null>(null);
  const [auditHasMore, setAuditHasMore] = useState<Record<string, boolean>>({});
  const [auditTotal, setAuditTotal] = useState<Record<string, number>>({});

  async function fetchChains() {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/signal-chains`);
      if (res.status === 401 || res.status === 403) {
        if (chains.length === 0) {
          setChains(DEMO_CHAINS);
          setIsDemo(true);
        }
        return;
      }
      const data = await res.json();
      if (data.success && Array.isArray(data.chains) && data.chains.length > 0) {
        setChains(data.chains);
        setIsDemo(false);
      } else if (chains.length === 0) {
        setChains(DEMO_CHAINS);
        setIsDemo(true);
      }
    } catch {
      if (chains.length === 0) {
        setChains(DEMO_CHAINS);
        setIsDemo(true);
      }
    } finally {
      setLoading(false);
    }
  }

  async function fetchAudit(chainId: string, append = false) {
    setAuditLoading(chainId);
    try {
      const currentRows = append ? (auditRows[chainId] ?? []) : [];
      const offset = append ? currentRows.length : 0;
      const res = await fetch(
        `${apiBase}/api/signal-chains/${chainId}/audit?limit=25&offset=${offset}`,
      );
      const data = await res.json();
      if (data.success) {
        const newRows = append ? [...currentRows, ...data.entries] : data.entries;
        setAuditRows((prev) => ({ ...prev, [chainId]: newRows }));
        setAuditHasMore((prev) => ({ ...prev, [chainId]: !!data.hasMore }));
        setAuditTotal((prev) => ({ ...prev, [chainId]: data.total ?? 0 }));
      }
    } catch {
      /* ignore */
    } finally {
      setAuditLoading(null);
    }
  }

  const isDemoChain = (chainId: string) =>
    DEMO_CHAINS.some((c) => c.id === chainId) &&
    chains.every((c) => DEMO_CHAINS.some((d) => d.id === c.id));

  async function triggerChain(chainId: string) {
    setTriggering(chainId);

    if (isDemoChain(chainId)) {
      await new Promise((resolve) => setTimeout(resolve, 1800));
      setChains((prev) =>
        prev.map((c) => {
          if (c.id !== chainId) return c;
          const demoChain = DEMO_CHAINS.find((d) => d.id === chainId);
          const existingExecution = demoChain?.lastExecution ?? c.lastExecution;
          const now = Date.now();
          const simulatedExecution: SignalChainExecution = existingExecution
            ? {
                ...existingExecution,
                executionId: `exec-sim-${Math.floor(Math.random() * 9000) + 1000}`,
                triggeredAt: now,
                triggerReason: existingExecution.triggerReason.replace(
                  /\d+m ago|\d+h ago|\d+d ago|Just now/,
                  'Just now',
                ),
                status: 'completed',
                steps: existingExecution.steps.map((s) => ({
                  ...s,
                  executedAt: now,
                })),
              }
            : {
                executionId: `exec-sim-${Math.floor(Math.random() * 9000) + 1000}`,
                chainId: c.id,
                triggeredAt: now,
                triggerReason: `${c.triggerSignal} threshold of ${c.triggerThreshold} exceeded — manual trigger initiated`,
                triggerValue: c.triggerThreshold * 1.1,
                threshold: c.triggerThreshold,
                status: 'completed',
                steps: Array.from({ length: c.stepCount }, (_, i) => ({
                  id: `step-${i + 1}`,
                  domain: i === 0 ? c.triggerDomain : (c.targetDomains[i - 1] ?? c.triggerDomain),
                  action: i === 0 ? `Evaluate ${c.triggerSignal} signal` : `Execute action on ${c.targetDomains[i - 1] ?? c.triggerDomain}`,
                  status: 'executed' as const,
                  executedAt: now + i * 30000,
                  explainability: `Step ${i + 1} completed successfully as part of automated chain execution`,
                })),
              };
          return {
            ...c,
            executionCount: c.executionCount + 1,
            lastExecuted: now,
            lastExecution: simulatedExecution,
          };
        }),
      );
      setExpanded(chainId);
      setTriggering(null);
      return;
    }

    try {
      const res = await fetch(`${apiBase}/api/signal-chains/${chainId}/trigger`, {
        method: 'POST',
      });
      const data = await res.json();
      if (data.success) {
        setChains((prev) =>
          prev.map((c) =>
            c.id === chainId
              ? {
                  ...c,
                  executionCount: c.executionCount + 1,
                  lastExecuted: Date.now(),
                  lastExecution: data.execution,
                }
              : c,
          ),
        );
        setExpanded(chainId);
        if (auditView === chainId) {
          await fetchAudit(chainId);
        }
      }
    } catch {
      /* ignore */
    } finally {
      setTriggering(null);
    }
  }

  function toggleAudit(chainId: string) {
    if (auditView === chainId) {
      setAuditView(null);
    } else {
      setAuditView(chainId);
      if (!auditRows[chainId]) {
        fetchAudit(chainId);
      }
    }
  }

  function exportCsv(chainId?: string) {
    const params = new URLSearchParams({ format: 'csv' });
    if (chainId) params.set('chainId', chainId);
    const url = `${apiBase}/api/signal-chains/audit-log/export?${params.toString()}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  useEffect(() => {
    fetchChains();
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4" style={{ color: '#8b7ac8' }} />
          <h2
            className="text-xs font-bold tracking-widest uppercase"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Autonomous Signal Chains
          </h2>
          {!loading && isDemo === true && (
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
              title="Showing illustrative demo data — live API unavailable"
              style={{
                color: '#f59e0b',
                backgroundColor: 'color-mix(in srgb, #f59e0b 12%, transparent)',
                border: '1px solid color-mix(in srgb, #f59e0b 30%, transparent)',
              }}
            >
              Demo
            </span>
          )}
          {!loading && isDemo === false && (
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded inline-flex items-center gap-1"
              title="Connected to live data"
              style={{
                color: '#22c55e',
                backgroundColor: 'color-mix(in srgb, #22c55e 12%, transparent)',
                border: '1px solid color-mix(in srgb, #22c55e 30%, transparent)',
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ backgroundColor: '#22c55e' }}
              />
              Live
            </span>
          )}
          {chains.length > 0 && (
            <span
              className="text-[10px] px-2 py-0.5 rounded font-mono"
              style={{
                backgroundColor: 'var(--color-surface-base)',
                color: 'var(--color-fg-muted)',
              }}
            >
              {chains.filter((c) => c.enabled).length} active
            </span>
          )}
        </div>
        <button
          onClick={fetchChains}
          disabled={loading}
          className="flex items-center gap-1 text-[10px] px-2 py-1 rounded"
          style={{
            backgroundColor: 'var(--color-surface-base)',
            border: '1px solid var(--color-surface-border)',
            color: 'var(--color-fg-muted)',
          }}
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {loading && (
        <div className="text-xs text-center py-8" style={{ color: 'var(--color-fg-muted)' }}>
          Loading signal chains…
        </div>
      )}

      <div className="flex flex-col gap-3">
        {chains.map((chain) => {
          const severityColor = SEVERITY_COLORS[chain.severity] ?? '#6b7280';
          const domainColor = DOMAIN_COLORS[chain.triggerDomain] ?? '#6b7280';
          const isExpanded = expanded === chain.id;
          const isAuditOpen = auditView === chain.id;
          const chainAuditRows = auditRows[chain.id] ?? [];

          return (
            <div
              key={chain.id}
              className="rounded-xl overflow-hidden"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-surface-border)',
                borderLeftWidth: '3px',
                borderLeftColor: severityColor,
              }}
            >
              <div className="p-4 flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex flex-col gap-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                        style={{
                          color: domainColor,
                          backgroundColor: `color-mix(in srgb, ${domainColor} 12%, transparent)`,
                        }}
                      >
                        {chain.triggerDomain}
                      </span>
                      <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                        →
                      </span>
                      {chain.targetDomains.map((td) => (
                        <span
                          key={td}
                          className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                          style={{
                            color: DOMAIN_COLORS[td] ?? '#6b7280',
                            backgroundColor: `color-mix(in srgb, ${DOMAIN_COLORS[td] ?? '#6b7280'} 12%, transparent)`,
                          }}
                        >
                          {td}
                        </span>
                      ))}
                    </div>
                    <h3 className="text-sm font-bold" style={{ color: 'var(--color-fg-primary)' }}>
                      {chain.name}
                    </h3>
                    <p
                      className="text-[11px] leading-relaxed"
                      style={{ color: 'var(--color-fg-muted)' }}
                    >
                      {chain.description}
                    </p>
                  </div>

                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
                        style={{
                          color: severityColor,
                          backgroundColor: `color-mix(in srgb, ${severityColor} 12%, transparent)`,
                        }}
                      >
                        {chain.severity}
                      </span>
                      <div
                        className="flex items-center gap-1 text-[10px]"
                        style={{ color: chain.enabled ? '#22c55e' : 'var(--color-fg-muted)' }}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${chain.enabled ? 'animate-pulse' : ''}`}
                          style={{ backgroundColor: 'currentColor' }}
                        />
                        {chain.enabled ? 'Active' : 'Paused'}
                      </div>
                    </div>
                    <button
                      onClick={() => triggerChain(chain.id)}
                      disabled={!!triggering || !chain.enabled}
                      className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-lg transition-opacity hover:opacity-80 disabled:opacity-40"
                      style={{ backgroundColor: '#8b7ac8', color: '#fff' }}
                    >
                      {triggering === chain.id ? (
                        <>
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          Running…
                        </>
                      ) : (
                        <>
                          <Play className="w-3 h-3" />
                          Trigger
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div
                  className="flex items-center gap-4 flex-wrap text-[10px]"
                  style={{ color: 'var(--color-fg-muted)' }}
                >
                  <div className="flex items-center gap-1">
                    <Zap className="w-3 h-3" />
                    <span>
                      {chain.stepCount} steps · {chain.executionCount} executions
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span>Last: {timeAgo(chain.lastExecuted)}</span>
                  </div>
                  <div className="flex items-center gap-2 ml-auto">
                    {chain.lastExecution && (
                      <button
                        onClick={() => setExpanded(isExpanded ? null : chain.id)}
                        className="flex items-center gap-1 hover:opacity-80"
                        style={{ color: '#8b7ac8' }}
                      >
                        {isExpanded ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                        {isExpanded ? 'Hide' : 'View'} last execution
                      </button>
                    )}
                    <button
                      onClick={() => toggleAudit(chain.id)}
                      className="flex items-center gap-1 hover:opacity-80"
                      style={{ color: isAuditOpen ? '#22c55e' : 'var(--color-fg-muted)' }}
                    >
                      <History className="w-3 h-3" />
                      {isAuditOpen ? 'Hide' : 'Full'} history
                    </button>
                  </div>
                </div>
              </div>

              {isExpanded && chain.lastExecution && (
                <div
                  className="px-4 pb-4 pt-0"
                  style={{ borderTop: '1px solid var(--color-surface-border)' }}
                >
                  <div className="pt-3 flex flex-col gap-1">
                    <div
                      className="text-[10px] font-bold uppercase tracking-widest mb-2"
                      style={{ color: 'var(--color-fg-muted)' }}
                    >
                      Execution Audit Trail · {chain.lastExecution.executionId}
                    </div>
                    <div
                      className="text-[11px] mb-3 p-2 rounded"
                      style={{
                        backgroundColor: 'var(--color-surface-base)',
                        color: 'var(--color-fg-secondary)',
                      }}
                    >
                      <span className="font-bold">Trigger: </span>
                      {chain.lastExecution.triggerReason}
                      <span className="ml-2" style={{ color: 'var(--color-fg-muted)' }}>
                        (value: {chain.lastExecution.triggerValue} vs threshold:{' '}
                        {chain.lastExecution.threshold})
                      </span>
                    </div>
                    {chain.lastExecution.steps.map((step, i) => (
                      <div
                        key={step.id}
                        className="flex items-start gap-3 py-2"
                        style={{
                          borderTop: i > 0 ? '1px solid var(--color-surface-border)' : undefined,
                        }}
                      >
                        <div className="flex items-center gap-2 shrink-0 mt-0.5">
                          {step.status === 'executed' ? (
                            <CheckCircle className="w-3.5 h-3.5" style={{ color: '#22c55e' }} />
                          ) : step.status === 'failed' ? (
                            <AlertCircle className="w-3.5 h-3.5" style={{ color: '#ef4444' }} />
                          ) : (
                            <Clock
                              className="w-3.5 h-3.5"
                              style={{ color: 'var(--color-fg-muted)' }}
                            />
                          )}
                        </div>
                        <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                              style={{
                                color: DOMAIN_COLORS[step.domain] ?? '#6b7280',
                                backgroundColor: `color-mix(in srgb, ${DOMAIN_COLORS[step.domain] ?? '#6b7280'} 12%, transparent)`,
                              }}
                            >
                              {step.domain}
                            </span>
                            <span
                              className="text-[11px] font-medium"
                              style={{ color: 'var(--color-fg-primary)' }}
                            >
                              {step.action}
                            </span>
                          </div>
                          <p
                            className="text-[11px] leading-relaxed"
                            style={{ color: 'var(--color-fg-muted)' }}
                          >
                            {step.explainability}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {isAuditOpen && (
                <div
                  className="px-4 pb-4 pt-0"
                  style={{ borderTop: '1px solid var(--color-surface-border)' }}
                >
                  <div className="pt-3 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="text-[10px] font-bold uppercase tracking-widest"
                          style={{ color: 'var(--color-fg-muted)' }}
                        >
                          Persistent Audit Trail · DB
                        </div>
                        {(auditTotal[chain.id] ?? 0) > 0 && (
                          <span
                            className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                            style={{
                              backgroundColor: 'var(--color-surface-base)',
                              color: 'var(--color-fg-muted)',
                            }}
                          >
                            {auditTotal[chain.id]} total
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => exportCsv(chain.id)}
                          className="flex items-center gap-1 text-[10px] px-2 py-1 rounded hover:opacity-80"
                          style={{
                            backgroundColor: 'var(--color-surface-base)',
                            border: '1px solid var(--color-surface-border)',
                            color: 'var(--color-fg-muted)',
                          }}
                        >
                          <Download className="w-3 h-3" />
                          Export CSV
                        </button>
                        <button
                          onClick={() => fetchAudit(chain.id, false)}
                          disabled={auditLoading === chain.id}
                          className="flex items-center gap-1 text-[10px] hover:opacity-80"
                          style={{ color: 'var(--color-fg-muted)' }}
                        >
                          <RefreshCw
                            className={`w-3 h-3 ${auditLoading === chain.id ? 'animate-spin' : ''}`}
                          />
                          Reload
                        </button>
                      </div>
                    </div>

                    {auditLoading === chain.id && chainAuditRows.length === 0 && (
                      <div
                        className="text-[11px] text-center py-4"
                        style={{ color: 'var(--color-fg-muted)' }}
                      >
                        Loading audit history…
                      </div>
                    )}

                    {auditLoading !== chain.id && chainAuditRows.length === 0 && (
                      <div
                        className="text-[11px] text-center py-4"
                        style={{ color: 'var(--color-fg-muted)' }}
                      >
                        No persistent executions yet. Trigger the chain to begin building an audit
                        trail.
                      </div>
                    )}

                    {chainAuditRows.map((row) => (
                      <div
                        key={row.id}
                        className="rounded-lg p-3 flex flex-col gap-1.5"
                        style={{
                          backgroundColor: 'var(--color-surface-base)',
                          border: '1px solid var(--color-surface-border)',
                        }}
                      >
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                              style={{
                                color: STATUS_COLORS[row.status] ?? '#6b7280',
                                backgroundColor: `color-mix(in srgb, ${STATUS_COLORS[row.status] ?? '#6b7280'} 12%, transparent)`,
                              }}
                            >
                              {row.status}
                            </span>
                            <span
                              className="text-[10px] font-mono"
                              style={{ color: 'var(--color-fg-muted)' }}
                            >
                              #{row.id}
                            </span>
                          </div>
                          <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                            {timeAgo(row.triggeredAt)}
                          </span>
                        </div>
                        {row.payloadSnapshot && (
                          <div
                            className="text-[11px]"
                            style={{ color: 'var(--color-fg-secondary)' }}
                          >
                            <span className="font-bold">Trigger: </span>
                            {row.payloadSnapshot.triggerReason}
                            <span
                              className="ml-2 text-[10px]"
                              style={{ color: 'var(--color-fg-muted)' }}
                            >
                              ({row.payloadSnapshot.triggerValue} vs {row.payloadSnapshot.threshold}
                              )
                            </span>
                          </div>
                        )}
                        {row.outcomes && Array.isArray(row.outcomes) && row.outcomes.length > 0 && (
                          <div className="flex flex-col gap-1 mt-1">
                            {(row.outcomes as SignalChainStep[]).map((step, i) => (
                              <div key={i} className="flex items-start gap-2 text-[10px]">
                                <CheckCircle
                                  className="w-3 h-3 shrink-0 mt-0.5"
                                  style={{ color: '#22c55e' }}
                                />
                                <span style={{ color: 'var(--color-fg-muted)' }}>
                                  {step.explainability}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}

                    {chainAuditRows.length > 0 && auditHasMore[chain.id] && (
                      <button
                        onClick={() => fetchAudit(chain.id, true)}
                        disabled={auditLoading === chain.id}
                        className="w-full text-[10px] py-2 rounded-lg text-center hover:opacity-80 disabled:opacity-40"
                        style={{
                          backgroundColor: 'var(--color-surface-base)',
                          border: '1px solid var(--color-surface-border)',
                          color: 'var(--color-fg-muted)',
                        }}
                      >
                        {auditLoading === chain.id ? (
                          <span className="flex items-center justify-center gap-1">
                            <RefreshCw className="w-3 h-3 animate-spin" /> Loading…
                          </span>
                        ) : (
                          `Load more (showing ${chainAuditRows.length} of ${auditTotal[chain.id]})`
                        )}
                      </button>
                    )}

                    {chainAuditRows.length > 0 && !auditHasMore[chain.id] && (
                      <div
                        className="text-[10px] text-center py-1"
                        style={{ color: 'var(--color-fg-muted)' }}
                      >
                        All {auditTotal[chain.id]} execution
                        {(auditTotal[chain.id] ?? 0) !== 1 ? 's' : ''} shown
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
