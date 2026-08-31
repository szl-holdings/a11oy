// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle,
  ChevronDown,
  Clock,
  Cpu,
  Database,
  Network,
  Pause,
  RefreshCw,
  Terminal,
  XCircle,
  Zap,
} from 'lucide-react';
import { AtelierEmbedFrame } from '../components/AtelierEmbedFrame';
import { useState } from 'react';
import { api } from '../lib/api';

const AGENT_STATUSES = [
  'idle',
  'investigating',
  'correlating',
  'executing',
  'waiting-approval',
  'completed',
] as const;
type AgentStatus = (typeof AGENT_STATUSES)[number];

interface Alert {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  source: string;
  asset: string;
  timestamp: string;
  status: 'new' | 'triaging' | 'contained' | 'resolved' | 'escalated';
  agentAssigned?: string;
  confidence?: number;
}

interface Agent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  currentTask?: string;
  alertsHandled: number;
  successRate: number;
  avgTriage: string;
  color: string;
}

interface ReasoningStep {
  id: number;
  step: string;
  result: string;
  confidence: number;
  timestamp: string;
  type: 'query' | 'correlate' | 'decide' | 'execute' | 'notify';
}

const AGENTS: Agent[] = [
  {
    id: 'TRIAGE-1',
    name: 'Sentinel Alpha',
    role: 'Alert Triage & Classification',
    status: 'investigating',
    currentTask: 'Analyzing lateral movement indicators on WORKSTATION-047',
    alertsHandled: 342,
    successRate: 96,
    avgTriage: '47s',
    color: '#f5f5f5',
  },
  {
    id: 'TRIAGE-2',
    name: 'Sentinel Beta',
    role: 'Threat Correlation Engine',
    status: 'correlating',
    currentTask: 'Correlating 12 alerts across SIEM, EDR, and NetFlow',
    alertsHandled: 287,
    successRate: 94,
    avgTriage: '1m 12s',
    color: '#c9b787',
  },
  {
    id: 'RESP-1',
    name: 'Responder Prime',
    role: 'Automated Response Executor',
    status: 'executing',
    currentTask: 'Isolating endpoint DC-FINANCE-03 via EDR API',
    alertsHandled: 156,
    successRate: 99,
    avgTriage: '23s',
    color: '#8a8a8a',
  },
  {
    id: 'HUNT-1',
    name: 'Hunter Apex',
    role: 'Proactive Threat Hunter',
    status: 'idle',
    alertsHandled: 89,
    successRate: 91,
    avgTriage: '3m 44s',
    color: '#c9b787',
  },
  {
    id: 'COMPL-1',
    name: 'Auditor One',
    role: 'Compliance Evidence Collector',
    status: 'completed',
    currentTask: 'Generated SOC 2 evidence bundle for Q2 audit',
    alertsHandled: 203,
    successRate: 100,
    avgTriage: '2m 08s',
    color: '#c9b787',
  },
];

const FALLBACK_ALERTS: Alert[] = [
  {
    id: 'ALT-9821',
    title: 'Suspicious PowerShell Execution Chain',
    severity: 'critical',
    source: 'EDR',
    asset: 'WORKSTATION-047',
    timestamp: '14:32:11',
    status: 'triaging',
    agentAssigned: 'Sentinel Alpha',
    confidence: 94,
  },
  {
    id: 'ALT-9820',
    title: 'Lateral Movement via Pass-the-Hash',
    severity: 'critical',
    source: 'SIEM',
    asset: 'DC-FINANCE-03',
    timestamp: '14:31:05',
    status: 'contained',
    agentAssigned: 'Responder Prime',
    confidence: 98,
  },
  {
    id: 'ALT-9819',
    title: 'Unusual DNS Beacon to Known C2 Domain',
    severity: 'high',
    source: 'NDR',
    asset: 'SRV-WEB-12',
    timestamp: '14:28:44',
    status: 'triaging',
    agentAssigned: 'Sentinel Beta',
    confidence: 87,
  },
  {
    id: 'ALT-9818',
    title: 'Brute Force Attack — 47 Failed Logins',
    severity: 'high',
    source: 'SIEM',
    asset: 'VPN-GATEWAY',
    timestamp: '14:22:30',
    status: 'resolved',
    agentAssigned: 'Sentinel Alpha',
    confidence: 100,
  },
  {
    id: 'ALT-9817',
    title: 'Anomalous Data Exfiltration Volume',
    severity: 'high',
    source: 'DLP',
    asset: 'USER-CFO-PC',
    timestamp: '14:18:55',
    status: 'escalated',
    agentAssigned: 'Responder Prime',
    confidence: 76,
  },
  {
    id: 'ALT-9816',
    title: 'Privilege Escalation via Token Impersonation',
    severity: 'medium',
    source: 'EDR',
    asset: 'WORKSTATION-031',
    timestamp: '14:12:10',
    status: 'triaging',
    agentAssigned: 'Sentinel Beta',
    confidence: 81,
  },
  {
    id: 'ALT-9815',
    title: 'Malicious Script Injection in Web Server',
    severity: 'high',
    source: 'WAF',
    asset: 'SRV-WEB-01',
    timestamp: '14:09:22',
    status: 'new',
    confidence: 0,
  },
];

function mapApiAlert(a: Record<string, unknown>, idx: number): Alert {
  const sev = (a.severity as string) ?? 'medium';
  const mappedSev: Alert['severity'] =
    sev === 'critical' ? 'critical' : sev === 'high' ? 'high' : sev === 'medium' ? 'medium' : 'low';
  const apiStatus = (a.status as string) ?? 'new';
  const mappedStatus: Alert['status'] =
    apiStatus === 'triaging'
      ? 'triaging'
      : apiStatus === 'contained'
        ? 'contained'
        : apiStatus === 'resolved'
          ? 'resolved'
          : apiStatus === 'escalated'
            ? 'escalated'
            : 'new';

  return {
    id: typeof a.id === 'string' ? a.id : `ALT-${a.id ?? idx}`,
    title: typeof a.title === 'string' ? a.title : `Alert #${a.id ?? idx}`,
    severity: mappedSev,
    source: typeof a.source === 'string' ? a.source : 'SIEM',
    asset: typeof a.asset === 'string' ? a.asset : typeof a.assetId === 'string' ? a.assetId : 'UNKNOWN',
    timestamp: new Date(typeof a.createdAt === 'string' ? a.createdAt : Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    status: mappedStatus,
    confidence: typeof a.confidence === 'number' ? a.confidence : undefined,
  };
}

const REASONING_TRACE: ReasoningStep[] = [
  {
    id: 1,
    step: 'Query EDR telemetry for WORKSTATION-047',
    result: 'Found 3 suspicious PowerShell executions with encoded payloads in last 15 min',
    confidence: 89,
    timestamp: '14:32:11',
    type: 'query',
  },
  {
    id: 2,
    step: 'Cross-reference against SIEM for related events',
    result:
      'Correlated with 2 authentication anomalies and 1 privilege escalation attempt on same host',
    confidence: 94,
    timestamp: '14:32:14',
    type: 'correlate',
  },
  {
    id: 3,
    step: 'Check IOC reputation against ThreatIntel feeds',
    result: 'C2 IP 192.168.45.12 matches APT-29 infrastructure fingerprint (Confidence: 91%)',
    confidence: 91,
    timestamp: '14:32:17',
    type: 'query',
  },
  {
    id: 4,
    step: 'Assess asset criticality and blast radius',
    result: 'WORKSTATION-047 has access to Finance VLAN. 14 adjacent assets potentially exposed',
    confidence: 96,
    timestamp: '14:32:19',
    type: 'decide',
  },
  {
    id: 5,
    step: 'Select response playbook',
    result: 'PB-007: APT Lateral Movement Containment selected (match score: 0.97)',
    confidence: 97,
    timestamp: '14:32:21',
    type: 'decide',
  },
  {
    id: 6,
    step: 'Execute: Isolate endpoint via EDR API',
    result: 'PENDING HUMAN APPROVAL — Isolation will cut access for 1 user (critical ops role)',
    confidence: 95,
    timestamp: '14:32:23',
    type: 'execute',
  },
];

const severityColor: Record<string, string> = {
  critical: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/30',
  high: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  medium: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  low: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
};

const statusColor: Record<string, string> = {
  new: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30',
  triaging: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  contained: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  resolved: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  escalated: 'text-[#8a8a8a] bg-[#8a8a8a]/10 border-[#8a8a8a]/30',
};

const agentStatusColor: Record<AgentStatus, string> = {
  idle: 'text-zinc-400',
  investigating: 'text-[#c9b787]',
  correlating: 'text-[#c9b787]',
  executing: 'text-[#8a8a8a]',
  'waiting-approval': 'text-[#c9b787]',
  completed: 'text-[#c9b787]',
};

const stepTypeIcon: Record<string, typeof Terminal> = {
  query: Terminal,
  correlate: Network,
  decide: Brain,
  execute: Zap,
  notify: Activity,
};

export default function AgenticSOC() {
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [autoMode, setAutoMode] = useState(true);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const { data: alertsData, isLoading, isError, refetch } = useQuery<
    unknown,
    Error,
    Alert[]
  >({
    queryKey: ['agentic-soc-alerts'],
    queryFn: () => api.alerts.list() as Promise<unknown>,
    refetchInterval: 30000,
    select: (res: unknown) => {
      const raw = (res as { data?: Record<string, unknown>[] } | undefined)?.data ?? [];
      return raw.length > 0 ? raw.map(mapApiAlert) : FALLBACK_ALERTS;
    },
  });

  const alerts: Alert[] = alertsData ?? FALLBACK_ALERTS;
  const liveAlerts = alertsData != null && !isError;

  const activeAlert = selectedAlert ?? alerts[0] ?? null;

  const autonomousCount = alerts.filter((a) => !['new', 'escalated'].includes(a.status)).length;
  const autonomousRate = alerts.length > 0 ? Math.round((autonomousCount / alerts.length) * 100) : 0;

  const handleApprove = () => {
    toast.success('Action approved — endpoint isolation executing via EDR API');
  };
  const handleReject = () => {
    toast.error('Action rejected — agent will escalate to human analyst');
  };

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-5 h-5 text-[#f5f5f5]" />
            <h1 className="text-lg font-semibold text-white">
              Agentic SOC — Autonomous Triage & Response
            </h1>
            <span
              className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded font-mono uppercase border"
              style={{
                background: liveAlerts ? 'rgba(201,183,135,0.08)' : 'rgba(201,183,135,0.08)',
                borderColor: liveAlerts ? 'rgba(201,183,135,0.25)' : 'rgba(201,183,135,0.25)',
                color: liveAlerts ? '#c9b787' : '#c9b787',
              }}
            >
              <Database className="w-2.5 h-2.5" />
              {isLoading ? 'Loading…' : isError ? 'Fallback data' : `Live DB · ${alerts.length} alerts`}
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            AI agents autonomously investigate alerts, correlate data sources, and execute response
            playbooks
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            className="p-1.5 rounded text-zinc-400/40 hover:text-zinc-400 transition-colors"
            aria-label="Refresh alerts"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', isLoading && 'animate-spin')} />
          </button>
          <button
            onClick={() => {
              setAutoMode(!autoMode);
              toast.success(autoMode ? 'Autonomous mode paused' : 'Autonomous mode active');
            }}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors',
              autoMode
                ? 'bg-[#c9b787]/10 border-[#c9b787]/30 text-[#c9b787]'
                : 'bg-zinc-800 border-zinc-700 text-zinc-400',
            )}
          >
            {autoMode ? (
              <>
                <Activity className="w-3.5 h-3.5 animate-pulse" /> Autonomous Active
              </>
            ) : (
              <>
                <Pause className="w-3.5 h-3.5" /> Paused
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Autonomous Rate',
            value: `${autonomousRate}%`,
            sub: 'of alerts handled autonomously',
            color: '#c9b787',
            icon: Brain,
          },
          {
            label: 'Active Agents',
            value: AGENTS.filter((a) => a.status !== 'idle').length,
            sub: `${AGENTS.length} total deployed`,
            color: '#8a8a8a',
            icon: Cpu,
          },
          {
            label: 'Alerts Queue',
            value: alerts.length,
            sub: `${alerts.filter((a) => a.status === 'new').length} unassigned`,
            color: '#f5f5f5',
            icon: AlertTriangle,
          },
          {
            label: 'Avg Triage Time',
            value: '1m 12s',
            sub: 'vs 45m manual baseline',
            color: '#c9b787',
            icon: Clock,
          },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-2xl font-bold text-white">{m.value}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      {isError && (
        <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 px-4 py-3 text-xs text-[#c9b787] flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          Live alert feed unavailable — showing scenario data for demo purposes
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            AI Agents
          </h2>
          <div className="space-y-2">
            {AGENTS.map((agent) => (
              <div
                key={agent.id}
                className="rounded-xl border border-white/8 bg-white/3 p-3"
              >
                <div className="flex items-start gap-2.5">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: `${agent.color}15`, border: `1px solid ${agent.color}30` }}
                  >
                    <Brain className="w-3.5 h-3.5" style={{ color: agent.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[11px] font-semibold text-white">{agent.name}</span>
                      <span
                        className={cn('text-[10px] font-medium', agentStatusColor[agent.status])}
                      >
                        {agent.status.replace('-', ' ')}
                      </span>
                    </div>
                    <div className="text-[10px] text-zinc-500 mb-1.5">{agent.role}</div>
                    {agent.currentTask && (
                      <div className="text-[10px] text-zinc-400 leading-relaxed bg-white/3 rounded-md px-2 py-1 mb-1.5">
                        {agent.currentTask}
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                      <span>{agent.alertsHandled} handled</span>
                      <span className="text-[#c9b787]">{agent.successRate}% success</span>
                      <span>avg {agent.avgTriage}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Alert Queue · {isLoading ? '…' : alerts.length} alerts
          </h2>
          <div className="space-y-1.5">
            {isLoading ? (
              <div className="flex items-center gap-2 text-xs text-zinc-500 py-4">
                <div className="w-3.5 h-3.5 border-2 border-[#f5f5f5]/40 border-t-red-400 rounded-full animate-spin" />
                Loading alerts from PARAGON…
              </div>
            ) : (
              alerts.map((alert) => (
                <button
                  key={alert.id}
                  onClick={() => setSelectedAlert(alert)}
                  className={cn(
                    'w-full rounded-xl border p-3 text-left transition-all',
                    activeAlert?.id === alert.id
                      ? 'border-[#f5f5f5]/30 bg-[#f5f5f5]/5'
                      : 'border-white/8 bg-white/3 hover:bg-white/5',
                  )}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-[11px] font-medium text-white leading-snug line-clamp-1">
                      {alert.title}
                    </span>
                    <span
                      className={cn(
                        'text-[9px] px-1.5 py-0.5 rounded border shrink-0',
                        severityColor[alert.severity],
                      )}
                    >
                      {alert.severity}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 mb-1.5">
                    <span>{alert.asset}</span>
                    <span className="text-zinc-600">·</span>
                    <span>{alert.source}</span>
                    <span className="text-zinc-600">·</span>
                    <span>{alert.timestamp}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn('text-[9px] px-1 py-0.5 rounded border', statusColor[alert.status])}
                    >
                      {alert.status}
                    </span>
                    {alert.agentAssigned && (
                      <span className="text-[9px] text-zinc-500">
                        ⟶ {alert.agentAssigned}
                      </span>
                    )}
                    {alert.confidence != null && alert.confidence > 0 && (
                      <span className="text-[9px] text-zinc-500 ml-auto">
                        {alert.confidence}% conf
                      </span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            AI Reasoning Trace — {activeAlert?.id ?? '—'}
          </h2>
          <div className="space-y-1.5 mb-4">
            {REASONING_TRACE.map((step) => {
              const Icon = stepTypeIcon[step.type] ?? Terminal;
              const isExpanded = expandedStep === step.id;
              return (
                <div key={step.id} className="rounded-xl border border-white/8 bg-white/3 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                    className="w-full flex items-start gap-2.5 p-3 text-left"
                  >
                    <div className="w-6 h-6 rounded-md bg-white/5 flex items-center justify-center shrink-0">
                      <Icon className="w-3 h-3 text-zinc-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-[11px] font-medium text-white">{step.step}</span>
                        <ChevronDown
                          className={cn(
                            'w-3 h-3 text-zinc-500 shrink-0 transition-transform',
                            isExpanded && 'rotate-180',
                          )}
                        />
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-0.5">
                        <span className="font-mono uppercase">{step.type}</span>
                        <span>{step.timestamp}</span>
                        <span
                          className={cn(
                            step.confidence >= 90 ? 'text-[#c9b787]' : 'text-[#c9b787]',
                          )}
                        >
                          {step.confidence}%
                        </span>
                      </div>
                    </div>
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 pt-0">
                      <div className="rounded-lg bg-black/30 p-2.5 text-[11px] text-zinc-400 leading-relaxed">
                        {step.result}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 p-3">
            <div className="text-[11px] font-semibold text-[#c9b787] mb-2 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" /> Human Approval Required
            </div>
            <div className="text-[10px] text-zinc-400 mb-3 leading-relaxed">
              <strong className="text-white">Action:</strong> Isolate WORKSTATION-047 via EDR API
              <br />
              <strong className="text-white">Risk:</strong> Will cut access for 1 analyst (active
              investigation)
              <br />
              <strong className="text-white">Confidence:</strong> 95% — APT-29 lateral movement
              confirmed
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleApprove}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-[#c9b787]/15 border border-[#c9b787]/30 text-[#c9b787] text-[11px] font-semibold hover:bg-[#c9b787]/25 transition-colors"
              >
                <CheckCircle className="w-3 h-3" /> Approve
              </button>
              <button
                onClick={handleReject}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 text-[#f5f5f5] text-[11px] font-semibold hover:bg-[#f5f5f5]/20 transition-colors"
              >
                <XCircle className="w-3 h-3" /> Reject
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 px-4">
        <div className="text-[10px] font-mono uppercase tracking-[0.14em] text-[#c9b787] mb-2">Composed governance · A11oy Atelier</div>
        <p className="text-[11px] text-zinc-500 max-w-[60ch] leading-relaxed mb-3">
          The cyber-triage Atelier Space runs inside Sentra under its own Constitution. Each run emits a publicly verifiable proof packet and contributes to the governance-weighted leaderboard.
        </p>
        <AtelierEmbedFrame spaceSlug="cyber-triage" title="Cyber Threat Triage — governed loop" />
      </div>
    </div>
  );
}
