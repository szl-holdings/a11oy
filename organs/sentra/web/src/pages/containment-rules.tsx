// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/pages/containment-rules.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  Download,
  Edit2,
  Gauge,
  Globe,
  Lock,
  Plus,
  Radio,
  Server,
  Shield,
  ShieldOff,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  buildGatewayExportUrl,
  type EnforcementMode,
  type GatewayDecisionFilter,
  type GatewayLatencyBucket,
  MESH_AGENT_CLASS_DISPLAY_NAMES,
  useAgentMesh,
  useAgentMeshGateway,
  useAgentMeshGatewayLatency,
} from '@/data/agent-mesh';

const TIER_STYLES: Record<string, string> = {
  critical: 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10',
  elevated: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  standard: 'text-[#8a8a8a] border-sky-500/30 bg-[#8a8a8a]/10',
};

const MODE_META: Record<
  EnforcementMode,
  { label: string; icon: typeof Radio; color: string; ring: string; desc: string }
> = {
  'log-only': {
    label: 'Log-Only',
    icon: Radio,
    color: 'text-slate-300',
    ring: 'border-slate-600/40 bg-slate-700/20',
    desc: 'Observe and record violations as Exposures. Calls still reach the MCP server.',
  },
  block: {
    label: 'Block',
    icon: Ban,
    color: 'text-[#c9b787]',
    ring: 'border-[#c9b787]/30 bg-[#c9b787]/10',
    desc: 'Reject offending calls at the gateway. Other calls pass through normally.',
  },
  quarantine: {
    label: 'Quarantine',
    icon: ShieldOff,
    color: 'text-[#f5f5f5]',
    ring: 'border-[#f5f5f5]/30 bg-[#f5f5f5]/10',
    desc: 'Reject all calls from this agent class until the rule is cleared.',
  },
};

const DECISION_STYLES: Record<string, { dot: string; chip: string; label: string }> = {
  allowed: {
    dot: 'bg-[#c9b787]',
    chip: 'text-[#c9b787] border-[#c9b787]/20',
    label: 'ALLOWED',
  },
  logged: { dot: 'bg-[#8a8a8a]', chip: 'text-[#8a8a8a] border-sky-500/20', label: 'LOGGED' },
  blocked: { dot: 'bg-[#c9b787]', chip: 'text-[#c9b787] border-[#c9b787]/20', label: 'BLOCKED' },
  quarantined: { dot: 'bg-[#f5f5f5]', chip: 'text-[#f5f5f5] border-[#f5f5f5]/20', label: 'QUARANTINED' },
};

function formatUptime(s: number) {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  return `${d}d ${h}h`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const DECISION_FILTER_OPTIONS: GatewayDecisionFilter[] = [
  'blocked',
  'quarantined',
  'allowed',
  'logged',
];

function latencyTone(p95: number): { row: string; p95: string } {
  if (p95 >= 1500) {
    return { row: 'border-[#f5f5f5]/30 bg-[#f5f5f5]/10', p95: 'text-[#f5f5f5]' };
  }
  if (p95 >= 600) {
    return { row: 'border-[#c9b787]/30 bg-[#c9b787]/10', p95: 'text-[#c9b787]' };
  }
  return { row: 'border-slate-800/60 bg-slate-900/40', p95: 'text-[#c9b787]' };
}

interface LatencyBreakdownPanelProps {
  breakdown: {
    windowHours: number;
    perServer: GatewayLatencyBucket[];
    perTool: GatewayLatencyBucket[];
  } | null;
  source: 'live' | 'empty';
  getMcpName: (id: string) => string;
}

function LatencyBreakdownPanel({ breakdown, source, getMcpName }: LatencyBreakdownPanelProps) {
  const perServer = breakdown?.perServer ?? [];
  const perTool = breakdown?.perTool ?? [];
  const windowHours = breakdown?.windowHours ?? 24;

  // Show the slowest 5 (server, tool) combos so operators can pinpoint
  // which downstream call is dragging — not just which server.
  const topTools = perTool.slice(0, 5);

  return (
    <section className="sentra-panel p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[10px] text-slate-500 font-mono uppercase flex items-center gap-1.5">
            <Gauge className="w-3 h-3" /> MCP Server Latency · last {windowHours}h
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            p50/p95 latency per downstream MCP server, computed from gateway proxy events.
            Identifies which service is slow.
          </p>
        </div>
        <div
          className={cn(
            'flex items-center gap-2 text-[10px] font-mono',
            source === 'live' && perServer.length > 0 ? 'text-[#c9b787]' : 'text-[#c9b787]',
          )}
        >
          <span
            className={cn(
              'w-1.5 h-1.5 rounded-full',
              source === 'live' && perServer.length > 0
                ? 'bg-[#c9b787] animate-pulse'
                : 'bg-[#c9b787]',
            )}
          />
          {source === 'live' && perServer.length > 0 ? 'STREAMING' : 'AWAITING TIMED CALLS'}
        </div>
      </div>

      {perServer.length === 0 ? (
        <div className="text-[11px] font-mono text-slate-500 text-center py-6 border border-slate-800/60 rounded bg-slate-900/40">
          No timed gateway calls recorded in the last {windowHours}h. Per-server latency will appear
          here once calls flow through the MCP gateway.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-12 gap-3 px-3 py-2 text-[9px] font-mono uppercase text-slate-500 border-b border-slate-800/60">
            <div className="col-span-4">MCP Server</div>
            <div className="col-span-2 text-right">Calls</div>
            <div className="col-span-2 text-right">p50</div>
            <div className="col-span-2 text-right">p95</div>
            <div className="col-span-2 text-right">Max</div>
          </div>
          <div className="space-y-1.5 mt-1.5">
            {perServer.map((row) => {
              const tone = latencyTone(row.p95Ms);
              return (
                <div
                  key={row.mcpServerId}
                  className={cn(
                    'grid grid-cols-12 items-center gap-3 rounded border px-3 py-2',
                    tone.row,
                  )}
                >
                  <div className="col-span-4 flex items-center gap-2 text-xs font-mono text-slate-200 truncate">
                    <Server className="w-3 h-3 text-slate-500 shrink-0" />
                    <span className="truncate">{getMcpName(row.mcpServerId)}</span>
                    <span className="text-[10px] text-slate-600 truncate">{row.mcpServerId}</span>
                  </div>
                  <div className="col-span-2 text-right text-[11px] font-mono text-slate-300">
                    {row.calls.toLocaleString()}
                  </div>
                  <div className="col-span-2 text-right text-[11px] font-mono text-slate-300">
                    {row.p50Ms}
                    <span className="text-slate-600 ml-0.5">ms</span>
                  </div>
                  <div
                    className={cn(
                      'col-span-2 text-right text-[11px] font-mono font-bold',
                      tone.p95,
                    )}
                  >
                    {row.p95Ms}
                    <span className="text-slate-600 ml-0.5">ms</span>
                  </div>
                  <div className="col-span-2 text-right text-[11px] font-mono text-slate-400">
                    {row.maxMs}
                    <span className="text-slate-600 ml-0.5">ms</span>
                  </div>
                </div>
              );
            })}
          </div>

          {topTools.length > 0 && (
            <div className="mt-5 pt-4 border-t border-slate-800/60">
              <div className="text-[10px] text-slate-500 font-mono uppercase mb-2">
                Slowest tool calls (server / tool, by p95)
              </div>
              <div className="grid grid-cols-12 gap-3 px-3 py-1.5 text-[9px] font-mono uppercase text-slate-500">
                <div className="col-span-3">Server</div>
                <div className="col-span-3">Tool</div>
                <div className="col-span-2 text-right">Calls</div>
                <div className="col-span-2 text-right">p50</div>
                <div className="col-span-2 text-right">p95</div>
              </div>
              <div className="space-y-1">
                {topTools.map((row) => {
                  const tone = latencyTone(row.p95Ms);
                  return (
                    <div
                      key={`${row.mcpServerId}::${row.tool ?? ''}`}
                      className="grid grid-cols-12 items-center gap-3 rounded bg-slate-900/40 border border-slate-800/60 px-3 py-1.5"
                    >
                      <div className="col-span-3 text-[11px] font-mono text-slate-300 truncate">
                        {getMcpName(row.mcpServerId)}
                      </div>
                      <div className="col-span-3 text-[11px] font-mono text-slate-200 truncate">
                        {row.tool ?? '—'}
                      </div>
                      <div className="col-span-2 text-right text-[11px] font-mono text-slate-400">
                        {row.calls.toLocaleString()}
                      </div>
                      <div className="col-span-2 text-right text-[11px] font-mono text-slate-300">
                        {row.p50Ms}
                        <span className="text-slate-600 ml-0.5">ms</span>
                      </div>
                      <div
                        className={cn(
                          'col-span-2 text-right text-[11px] font-mono font-bold',
                          tone.p95,
                        )}
                      >
                        {row.p95Ms}
                        <span className="text-slate-600 ml-0.5">ms</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default function ContainmentRules() {
  const { state } = useAgentMesh();
  const { containmentRules: liveRules, mcpServers } = state;
  // Operator-driven filters for the gateway event stream. These are sent to
  // /api/agent-mesh/gateway as query params so the count + events both come
  // back filtered by the server.
  const [decisionFilter, setDecisionFilter] = useState<GatewayDecisionFilter | undefined>(
    undefined,
  );
  const [agentClassFilter, setAgentClassFilter] = useState<string | undefined>(undefined);
  const [ruleIdFilter, setRuleIdFilter] = useState<string | undefined>(undefined);
  const gatewayFilters = useMemo(
    () => ({
      decision: decisionFilter,
      agentClass: agentClassFilter,
      ruleId: ruleIdFilter,
    }),
    [decisionFilter, agentClassFilter, ruleIdFilter],
  );
  // Live gateway endpoint config + 24h decision counts and the recent
  // gateway events stream come from /api/agent-mesh/gateway, which reads
  // straight from the agent_mesh_gateway_events table. Falls back to seed
  // when the API is unreachable.
  const {
    gateway,
    gatewayEvents,
    filteredEventCount,
    source: gatewaySource,
    streamStatus,
  } = useAgentMeshGateway(gatewayFilters);
  const { breakdown: latencyBreakdown, source: latencySource } = useAgentMeshGatewayLatency();
  const [rules, setRules] = useState(liveRules);
  // Re-sync local rule state whenever the live mesh refreshes.
  useEffect(() => {
    setRules(liveRules);
  }, [liveRules]);
  const [expandedId, setExpandedId] = useState<string | null>('rule-codex-restricted');

  const getMcpName = (id: string) =>
    mcpServers.find((m) => m.id === id)?.name ?? id.replace('mcp-', '');

  const setMode = (ruleId: string, mode: EnforcementMode) => {
    setRules((prev) =>
      prev.map((r) => {
        if (r.id !== ruleId) return r;
        if (r.enforcementMode === mode && !r.pendingModeChange) return r;

        if (r.tier === 'critical' && r.enforcementMode !== mode) {
          // Critical-tier changes route through Guardian — stage as pending.
          return {
            ...r,
            pendingModeChange: {
              requestedMode: mode,
              requestedBy: 'operator@sentra',
              requestedAt: new Date().toISOString(),
              guardianApprovalId: `approval-mcp-gw-${ruleId.slice(-4)}-${Date.now().toString(36)}`,
            },
          };
        }
        return { ...r, enforcementMode: mode, pendingModeChange: undefined };
      }),
    );
  };

  const cancelPending = (ruleId: string) => {
    setRules((prev) =>
      prev.map((r) => (r.id === ruleId ? { ...r, pendingModeChange: undefined } : r)),
    );
  };

  const totals = useMemo(
    () => ({
      rules: rules.length,
      violations: rules.reduce((a, r) => a + r.violationCount, 0),
      blocking: rules.filter((r) => r.enforcementMode !== 'log-only').length,
      pendingApproval: rules.filter((r) => r.pendingModeChange).length,
    }),
    [rules],
  );

  const recentEvents = useMemo(
    () => [...gatewayEvents].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt)).slice(0, 8),
    [gatewayEvents],
  );

  // Surface every agent class / rule observed in the loaded events so the
  // chip set always lines up with what's actually in the stream, rather
  // than with hard-coded options.
  const agentClassOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const e of gatewayEvents) seen.add(e.agentClass);
    if (agentClassFilter) seen.add(agentClassFilter);
    return Array.from(seen).sort();
  }, [gatewayEvents, agentClassFilter]);
  const ruleOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const r of rules) map.set(r.id, r.name);
    if (ruleIdFilter && !map.has(ruleIdFilter)) map.set(ruleIdFilter, ruleIdFilter);
    return Array.from(map.entries());
  }, [rules, ruleIdFilter]);
  const hasActiveFilter = Boolean(decisionFilter || agentClassFilter || ruleIdFilter);
  const clearFilters = () => {
    setDecisionFilter(undefined);
    setAgentClassFilter(undefined);
    setRuleIdFilter(undefined);
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">Containment Rules</h1>
          <p className="text-slate-400 mt-1">
            Define what each agent class can access — choose log-only, block, or quarantine
            enforcement at the MCP gateway.
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded bg-[#f5f5f5]/20 hover:bg-[#f5f5f5]/30 border border-[#f5f5f5]/30 text-[#f5f5f5] text-sm font-bold transition-colors">
          <Plus className="w-4 h-4" />
          New Rule
        </button>
      </header>

      <section className="sentra-panel p-5 border-[#c9b787]/20">
        <div className="flex items-start justify-between gap-6">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                'w-12 h-12 rounded flex items-center justify-center border shrink-0',
                gateway.status === 'online'
                  ? 'bg-[#c9b787]/10 border-[#c9b787]/30'
                  : 'bg-[#c9b787]/10 border-[#c9b787]/30',
              )}
            >
              <Activity
                className={cn(
                  'w-5 h-5',
                  gateway.status === 'online' ? 'text-[#c9b787]' : 'text-[#c9b787]',
                )}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase text-[#c9b787]">
                  MCP Traffic Gateway
                </span>
                <span
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[9px] font-mono uppercase border',
                    gateway.status === 'online'
                      ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10'
                      : 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
                  )}
                >
                  ● {gateway.status}
                </span>
              </div>
              <code className="block text-sm font-mono text-slate-100 mt-1.5 select-all">
                {gateway.endpoint}
              </code>
              <p className="text-xs text-slate-500 mt-2 max-w-xl">
                Configure this URL as the MCP endpoint in agent runtimes (Claude Desktop, Cursor,
                Codex CLI). The gateway evaluates every call against active Containment Rules in
                real time and blocks violations before they reach external services.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-right shrink-0">
            <div>
              <div className="text-[9px] text-slate-500 font-mono uppercase">Calls / 24h</div>
              <div className="text-xl font-display font-bold text-slate-100">
                {gateway.callsLast24h.toLocaleString()}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 font-mono uppercase">Avg latency</div>
              <div className="text-xl font-display font-bold text-slate-100">
                {gateway.averageLatencyMs == null ? (
                  <span className="text-slate-500">—</span>
                ) : (
                  <>
                    {gateway.averageLatencyMs}
                    <span className="text-xs text-slate-500 ml-0.5">ms</span>
                  </>
                )}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 font-mono uppercase">Blocked</div>
              <div className="text-xl font-display font-bold text-[#c9b787]">
                {gateway.blockedLast24h}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 font-mono uppercase">Quarantined</div>
              <div className="text-xl font-display font-bold text-[#f5f5f5]">
                {gateway.quarantinedLast24h}
              </div>
            </div>
          </div>
        </div>
        <div className="mt-3 pt-3 border-t border-slate-800/60 text-[10px] font-mono text-slate-500 flex items-center gap-2">
          <Clock className="w-3 h-3" /> Uptime {formatUptime(gateway.uptimeSeconds)} · Critical-tier
          mode changes require Guardian approval before taking effect.
        </div>
      </section>

      <LatencyBreakdownPanel
        breakdown={latencyBreakdown}
        source={latencySource}
        getMcpName={getMcpName}
      />

      <div className="grid grid-cols-4 gap-4 mb-2">
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Active Rules</div>
          <div className="text-3xl font-display font-bold text-slate-100">{totals.rules}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">
            Total Violations
          </div>
          <div className="text-3xl font-display font-bold text-[#f5f5f5]">{totals.violations}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Enforcing</div>
          <div className="text-3xl font-display font-bold text-[#c9b787]">
            {totals.blocking}
            <span className="text-base text-slate-500">/{totals.rules}</span>
          </div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">
            Pending Guardian
          </div>
          <div className="text-3xl font-display font-bold text-[#8a8a8a]">
            {totals.pendingApproval}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {rules.map((rule) => {
          const modeMeta = MODE_META[rule.enforcementMode];
          const ModeIcon = modeMeta.icon;
          return (
            <div key={rule.id} className="sentra-panel overflow-hidden">
              <button
                className="w-full p-6 flex items-center justify-between gap-4 text-left hover:bg-slate-800/20 transition-colors"
                onClick={() => setExpandedId(expandedId === rule.id ? null : rule.id)}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      'w-10 h-10 rounded flex items-center justify-center border shrink-0',
                      rule.violationCount > 0
                        ? 'bg-[#f5f5f5]/10 border-[#f5f5f5]/20'
                        : 'bg-[#c9b787]/10 border-[#c9b787]/20',
                    )}
                  >
                    <Shield
                      className={cn(
                        'w-5 h-5',
                        rule.violationCount > 0 ? 'text-[#f5f5f5]' : 'text-[#c9b787]',
                      )}
                    />
                  </div>
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-slate-100">{rule.name}</span>
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-mono uppercase border font-bold',
                          TIER_STYLES[rule.tier],
                        )}
                      >
                        {rule.tier}
                      </span>
                      <span
                        className={cn(
                          'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase border',
                          modeMeta.ring,
                          modeMeta.color,
                        )}
                      >
                        <ModeIcon className="w-3 h-3" />
                        {modeMeta.label}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 font-mono mt-1">
                      Agent class: {rule.agentClass} · Last evaluated:{' '}
                      {new Date(rule.lastEvaluatedAt).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  {rule.violationCount > 0 ? (
                    <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 text-xs text-[#f5f5f5] font-bold">
                      <AlertTriangle className="w-3 h-3" />
                      {rule.violationCount} violation{rule.violationCount > 1 ? 's' : ''}
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 text-xs text-[#c9b787]">
                      <CheckCircle2 className="w-4 h-4" />
                      Compliant
                    </div>
                  )}
                  <Edit2 className="w-4 h-4 text-slate-600" />
                </div>
              </button>

              {expandedId === rule.id && (
                <div className="px-6 pb-6 border-t border-slate-800">
                  <div className="pt-5">
                    <div className="text-[10px] text-slate-500 font-mono uppercase mb-3 flex items-center gap-1.5">
                      <Activity className="w-3 h-3" />
                      Gateway Enforcement Mode
                      {rule.tier === 'critical' && (
                        <span className="flex items-center gap-1 text-[10px] font-mono uppercase text-[#f5f5f5]">
                          <Lock className="w-3 h-3" /> Guardian-gated
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {(Object.keys(MODE_META) as EnforcementMode[]).map((mode) => {
                        const meta = MODE_META[mode];
                        const Icon = meta.icon;
                        const isActive = rule.enforcementMode === mode;
                        const isPending = rule.pendingModeChange?.requestedMode === mode;
                        return (
                          <button
                            key={mode}
                            onClick={(e) => {
                              e.stopPropagation();
                              setMode(rule.id, mode);
                            }}
                            className={cn(
                              'text-left rounded border p-3 transition-colors',
                              isActive
                                ? `${meta.ring} ${meta.color}`
                                : 'border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:bg-slate-800/40',
                              isPending && 'ring-1 ring-sky-500/40',
                            )}
                          >
                            <div className="flex items-center gap-2 mb-1.5">
                              <Icon className="w-3.5 h-3.5" />
                              <span className="text-[11px] font-mono uppercase font-bold">
                                {meta.label}
                              </span>
                              {isActive && (
                                <span className="ml-auto text-[9px] font-mono text-[#c9b787]">
                                  ACTIVE
                                </span>
                              )}
                              {isPending && (
                                <span className="ml-auto text-[9px] font-mono text-[#8a8a8a]">
                                  PENDING
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] leading-snug text-slate-500">{meta.desc}</p>
                          </button>
                        );
                      })}
                    </div>

                    {rule.pendingModeChange && (
                      <div className="mt-3 flex items-start gap-3 rounded border border-sky-500/30 bg-[#8a8a8a]/10 p-3">
                        <Lock className="w-4 h-4 text-[#8a8a8a] shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-bold text-[#8a8a8a]">
                            Awaiting Guardian approval to switch to{' '}
                            {MODE_META[rule.pendingModeChange.requestedMode].label}
                          </div>
                          <div className="text-[11px] font-mono text-[#8a8a8a]/70 mt-0.5">
                            Requested by {rule.pendingModeChange.requestedBy} ·{' '}
                            {timeAgo(rule.pendingModeChange.requestedAt)} ·{' '}
                            {rule.pendingModeChange.guardianApprovalId}
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            cancelPending(rule.id);
                          }}
                          className="text-[11px] font-mono text-[#8a8a8a] hover:text-[#8a8a8a] underline shrink-0"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-6 pt-5 mt-5 border-t border-slate-800">
                    <div>
                      <div className="text-[10px] text-slate-500 font-mono uppercase mb-3 flex items-center gap-1.5">
                        <Server className="w-3 h-3" />
                        Allowed MCP Servers
                      </div>
                      <div className="space-y-1.5">
                        {rule.allowedMcpServers.map((id) => (
                          <div
                            key={id}
                            className="flex items-center gap-2 text-[11px] font-mono text-[#c9b787]"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            {getMcpName(id)}
                          </div>
                        ))}
                        {mcpServers
                          .filter((m) => !rule.allowedMcpServers.includes(m.id))
                          .map((m) => (
                            <div
                              key={m.id}
                              className="flex items-center gap-2 text-[11px] font-mono text-slate-600 line-through"
                            >
                              <AlertTriangle className="w-3 h-3 text-slate-700" />
                              {m.name}
                            </div>
                          ))}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] text-slate-500 font-mono uppercase mb-3">
                        Allowed Tools
                      </div>
                      <div className="space-y-1.5">
                        {rule.allowedTools.map((t) => (
                          <div
                            key={t}
                            className="text-[11px] font-mono text-slate-300 px-2 py-0.5 rounded bg-slate-800 inline-block"
                          >
                            {t}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] text-slate-500 font-mono uppercase mb-3">
                        Read Paths
                      </div>
                      <div className="space-y-1.5">
                        {rule.allowedReadPaths.map((p) => (
                          <div key={p} className="text-[11px] font-mono text-slate-400">
                            {p}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] text-slate-500 font-mono uppercase mb-3 flex items-center gap-1.5">
                        <Globe className="w-3 h-3" />
                        Allowed Egress
                      </div>
                      {rule.allowedEgressDomains.length > 0 ? (
                        <div className="space-y-1.5">
                          {rule.allowedEgressDomains.map((d) => (
                            <div key={d} className="text-[11px] font-mono text-slate-300">
                              {d}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-[11px] font-mono text-[#c9b787] flex items-center gap-1.5">
                          <CheckCircle2 className="w-3 h-3" />
                          Egress blocked
                        </div>
                      )}
                    </div>
                  </div>

                  {rule.violationCount > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-800">
                      <div className="text-[10px] text-slate-500 font-mono uppercase mb-2">
                        Violation Details
                      </div>
                      <p className="text-xs text-[#f5f5f5]/80">
                        {rule.agentClass === 'codex-cli'
                          ? 'Codex CLI connected to quarantined mcp-ext-scraper server — not in allowlist. 3 tool calls blocked at the MCP gateway.'
                          : 'Agent accessed filesystem paths outside the allowed read scope. Gateway logged the call and emitted an Exposure.'}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <section className="sentra-panel p-5">
        <div className="flex items-center justify-between mb-3 gap-4">
          <div>
            <div className="text-[10px] text-slate-500 font-mono uppercase flex items-center gap-2">
              Recent Gateway Decisions
              <span className="text-slate-300">
                · {filteredEventCount.toLocaleString()} {hasActiveFilter ? 'match' : 'event'}
                {filteredEventCount === 1 ? '' : 'es'}
                {hasActiveFilter ? ' (filtered)' : ''}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Live stream of MCP calls evaluated against active Containment Rules.
            </p>
          </div>
          {(() => {
            // Two independent freshness signals feed this badge:
            //   - `streamStatus` reflects the SSE push channel
            //   - `gatewaySource` reflects whether the most recent
            //     snapshot fetch succeeded or fell back to seed data
            // The badge prefers the worst of the two so operators see
            // any drop in freshness immediately.
            const seed = gatewaySource !== 'live';
            let label: string;
            let tone: 'emerald' | 'amber' | 'slate';
            let pulse = false;
            if (seed) {
              label = 'SEED FALLBACK';
              tone = 'amber';
            } else if (streamStatus === 'live') {
              label = 'STREAMING';
              tone = 'emerald';
              pulse = true;
            } else if (streamStatus === 'connecting') {
              label = 'CONNECTING…';
              tone = 'amber';
              pulse = true;
            } else if (streamStatus === 'reconnecting') {
              label = 'RECONNECTING…';
              tone = 'amber';
              pulse = true;
            } else {
              label = 'POLLING ONLY';
              tone = 'slate';
            }
            const text =
              tone === 'emerald'
                ? 'text-[#c9b787]'
                : tone === 'amber'
                  ? 'text-[#c9b787]'
                  : 'text-slate-400';
            const dot =
              tone === 'emerald'
                ? 'bg-[#c9b787]'
                : tone === 'amber'
                  ? 'bg-[#c9b787]'
                  : 'bg-slate-400';
            return (
              <div
                className={cn('flex items-center gap-2 text-[10px] font-mono', text)}
                title={
                  seed
                    ? 'Live API unreachable — showing seed snapshot until it returns'
                    : streamStatus === 'live'
                      ? 'Receiving live gateway pushes'
                      : streamStatus === 'connecting'
                        ? 'Opening live push channel…'
                        : streamStatus === 'reconnecting'
                          ? 'Push channel dropped — retrying with backoff (60s safety-net poll still active)'
                          : 'Browser does not support live push — using 60s safety-net poll'
                }
              >
                <span className={cn('w-1.5 h-1.5 rounded-full', dot, pulse && 'animate-pulse')} />
                {label}
              </div>
            );
          })()}
        </div>

        <div className="mb-4 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[9px] font-mono uppercase text-slate-500 mr-1">Decision</span>
            {DECISION_FILTER_OPTIONS.map((d) => {
              const meta = DECISION_STYLES[d]!;
              const active = decisionFilter === d;
              return (
                <button
                  key={d}
                  onClick={() => setDecisionFilter(active ? undefined : d)}
                  className={cn(
                    'flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono uppercase border transition-colors',
                    active
                      ? meta.chip
                      : 'border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300',
                  )}
                >
                  <span className={cn('w-1.5 h-1.5 rounded-full', meta.dot)} />
                  {meta.label}
                </button>
              );
            })}
          </div>
          {agentClassOptions.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[9px] font-mono uppercase text-slate-500 mr-1">
                Agent class
              </span>
              {agentClassOptions.map((ac) => {
                const active = agentClassFilter === ac;
                return (
                  <button
                    key={ac}
                    onClick={() => setAgentClassFilter(active ? undefined : ac)}
                    className={cn(
                      'px-2 py-0.5 rounded text-[10px] font-mono border transition-colors',
                      active
                        ? 'border-sky-500/40 bg-[#8a8a8a]/10 text-[#8a8a8a]'
                        : 'border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300',
                    )}
                  >
                    {MESH_AGENT_CLASS_DISPLAY_NAMES[ac] ?? ac}
                  </button>
                );
              })}
            </div>
          )}
          {ruleOptions.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[9px] font-mono uppercase text-slate-500 mr-1">Rule</span>
              {ruleOptions.map(([id, name]) => {
                const active = ruleIdFilter === id;
                return (
                  <button
                    key={id}
                    onClick={() => setRuleIdFilter(active ? undefined : id)}
                    className={cn(
                      'px-2 py-0.5 rounded text-[10px] font-mono border transition-colors',
                      active
                        ? 'border-[#c9b787]/40 bg-[#c9b787]/10 text-[#c9b787]'
                        : 'border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300',
                    )}
                  >
                    {name}
                  </button>
                );
              })}
              {hasActiveFilter && (
                <button
                  onClick={clearFilters}
                  className="ml-1 flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 hover:text-slate-200 border border-slate-800 hover:border-slate-700"
                >
                  <X className="w-3 h-3" /> Clear
                </button>
              )}
            </div>
          )}
          <div className="flex items-center justify-between gap-2 pt-1">
            <span className="text-[9px] font-mono uppercase text-slate-600">
              Export honors active filters · up to 50,000 rows
            </span>
            <a
              href={buildGatewayExportUrl(gatewayFilters)}
              // download attribute is a hint — the server already sets
              // Content-Disposition: attachment, so the browser will save
              // the file regardless. Open in same tab to keep behavior
              // consistent with other download links in the dashboard.
              download
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-mono uppercase border border-slate-700 bg-slate-800/40 text-slate-200 hover:bg-slate-700/60 hover:text-white transition-colors"
              title={
                hasActiveFilter
                  ? 'Download every event matching the active filters as CSV'
                  : 'Download every gateway event as CSV'
              }
            >
              <Download className="w-3 h-3" />
              Download CSV
            </a>
          </div>
        </div>

        <div className="space-y-1.5">
          {recentEvents.length === 0 && (
            <div className="text-[11px] font-mono text-slate-500 text-center py-6 border border-slate-800/60 rounded bg-slate-900/40">
              No gateway decisions recorded yet. Calls routed through the MCP gateway will appear
              here.
            </div>
          )}
          {recentEvents.map((evt) => {
            const decoration = DECISION_STYLES[evt.decision] ?? DECISION_STYLES.allowed!;
            return (
              <div
                key={evt.id}
                className="grid grid-cols-12 items-center gap-3 rounded bg-slate-900/40 border border-slate-800/60 px-3 py-2 hover:bg-slate-800/40 transition-colors"
              >
                <div className="col-span-1 flex items-center gap-2">
                  <span className={cn('w-1.5 h-1.5 rounded-full', decoration.dot)} />
                  <span
                    className={cn(
                      'text-[9px] font-mono font-bold border px-1.5 py-0.5 rounded',
                      decoration.chip,
                    )}
                  >
                    {decoration.label}
                  </span>
                </div>
                <div className="col-span-3 text-xs text-slate-200 font-mono truncate">
                  {MESH_AGENT_CLASS_DISPLAY_NAMES[evt.agentClass] ?? evt.agentClass}
                  <span className="text-slate-600"> → </span>
                  <span className="text-slate-400">{getMcpName(evt.mcpServerId)}</span>
                </div>
                <div className="col-span-2 text-[11px] font-mono text-slate-300 truncate">
                  {evt.tool}
                </div>
                <div className="col-span-2 text-[11px] font-mono text-slate-500 truncate">
                  {evt.egressDomain ?? '—'}
                </div>
                <div className="col-span-3 text-[11px] text-slate-400 truncate" title={evt.reason}>
                  {evt.reason}
                </div>
                <div className="col-span-1 text-right text-[10px] font-mono text-slate-600">
                  {timeAgo(evt.occurredAt)}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <div className="sentra-panel p-5 border-sky-500/20">
        <div className="text-[10px] text-[#8a8a8a] font-mono uppercase mb-3">Tier-Policy Mapping</div>
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div className="p-3 rounded bg-slate-800/50">
            <div className="font-bold text-[#f5f5f5] mb-1">Critical Tier</div>
            <p className="text-slate-500">
              Enforcement mode changes require Guardian approval. Blocked calls create P0 Exposures
              immediately.
            </p>
          </div>
          <div className="p-3 rounded bg-slate-800/50">
            <div className="font-bold text-[#c9b787] mb-1">Elevated Tier</div>
            <p className="text-slate-500">
              Operators can switch between log-only and block. Quarantine still requires Guardian
              sign-off.
            </p>
          </div>
          <div className="p-3 rounded bg-slate-800/50">
            <div className="font-bold text-[#8a8a8a] mb-1">Standard Tier</div>
            <p className="text-slate-500">
              Operators may freely toggle enforcement modes. All blocked calls are logged as
              Exposures.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
