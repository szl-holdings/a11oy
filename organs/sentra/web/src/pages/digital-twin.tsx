// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — artifacts/sentra/src/pages/digital-twin.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardMutation, useStandardQuery } from '@szl-holdings/api-client-react';
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Database,
  Globe,
  Layers,
  Network,
  Play,
  RefreshCw,
  Server,
  Shield,
  Target,
} from 'lucide-react';
import { api } from '../lib/api';
import { AEGIS_MITRE_COVERAGE, metricDisplay } from '../lib/claims';

interface TwinNode {
  id: string;
  name: string;
  type: string;
  zone: string;
  tier: string;
  syncState: string;
  criticalityTier: number;
  vulnerabilities: number;
  lastSync: string;
  lastSyncLabel: string;
  ip: string;
  os?: string;
}

interface AttackSurfaceItem {
  area: string;
  risk: number;
}

interface TwinScenario {
  id: string;
  name: string;
  technique: string;
  status: string;
  progress: number;
  findings: number;
  criticalFindings: number;
  duration: string;
  startedAt?: string;
}

const typeIcon: Record<string, typeof Server> = {
  server: Server,
  workstation: Activity,
  network: Network,
  cloud: Globe,
  database: Database,
  firewall: Shield,
};
const typeColor: Record<string, string> = {
  server: '#c9b787',
  workstation: '#c9b787',
  network: '#8a8a8a',
  cloud: '#8a8a8a',
  database: '#c9b787',
  firewall: '#f5f5f5',
};

const syncColor: Record<string, string> = {
  synced: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  drifted: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  offline: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/30',
};

const scenarioStatusColor: Record<string, string> = {
  queued: 'text-zinc-400',
  running: 'text-[#c9b787]',
  completed: 'text-[#c9b787]',
  failed: 'text-[#f5f5f5]',
};

export default function DigitalTwin() {
  const qc = useQueryClient();

  const topologyQuery = useStandardQuery({
    queryKey: ['digital-twin', 'topology'],
    queryFn: () => api.digitalTwin.topology(),
    refetchInterval: 30000,
  });

  const scenariosQuery = useStandardQuery({
    queryKey: ['digital-twin', 'scenarios'],
    queryFn: () => api.digitalTwin.scenarios(),
    refetchInterval: 15000,
  });

  const syncMutation = useStandardMutation({
    mutationFn: () => api.digitalTwin.sync(),
    onSuccess: (data: { data?: { message?: string } }) => {
      qc.invalidateQueries({ queryKey: ['digital-twin', 'topology'] });
      toast.success(data?.data?.message ?? 'Digital twin synchronized');
    },
    onError: () => toast.error('Sync failed'),
  });

  const runScenarioMutation = useStandardMutation({
    mutationFn: (id: string) => api.digitalTwin.runScenario(id),
    onSuccess: (data: { data?: { message?: string } }) => {
      qc.invalidateQueries({ queryKey: ['digital-twin', 'scenarios'] });
      toast.success(data?.data?.message ?? 'Scenario launched');
    },
    onError: () => toast.error('Failed to launch scenario'),
  });

  type TopologyResponse = {
    data?: {
      nodes?: TwinNode[];
      attackSurface?: AttackSurfaceItem[];
      syncedCount?: number;
      totalVulns?: number;
      fidelity?: string;
    };
  };
  type ScenariosResponse = { data?: { scenarios?: TwinScenario[] } };
  const topology = (topologyQuery.data as TopologyResponse | null)?.data;
  const nodes: TwinNode[] = topology?.nodes ?? [];
  const attackSurface: AttackSurfaceItem[] = topology?.attackSurface ?? [];
  const scenarios: TwinScenario[] =
    (scenariosQuery.data as ScenariosResponse | null)?.data?.scenarios ?? [];

  const syncedCount = topology?.syncedCount ?? nodes.filter((n) => n.syncState === 'synced').length;
  const totalVulns =
    topology?.totalVulns ?? nodes.reduce((s, n) => s + (n.vulnerabilities ?? 0), 0);

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-5 h-5 text-[#8a8a8a]" />
            <h1 className="text-lg font-semibold text-white">Cyber Digital Twin</h1>
          </div>
          <p className="text-xs text-zinc-500">
            Virtual replica of your entire network. Red team scenarios run against the twin to
            identify vulnerabilities before attackers do.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg',
              'bg-[#c9b787]/10 border border-[#c9b787]/20 text-[#c9b787]',
            )}
          >
            <Activity className="w-3 h-3 animate-pulse" />
            Live Sync Active
          </div>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#8a8a8a]/15 border border-[#8a8a8a]/30 text-[#8a8a8a] text-xs font-medium hover:bg-[#8a8a8a]/25 transition-colors"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', syncMutation.isPending && 'animate-spin')} />
            {syncMutation.isPending ? 'Syncing...' : 'Sync Twin'}
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Assets Modeled',
            value: nodes.length || '—',
            sub: `${syncedCount} synced, ${nodes.length - syncedCount} drifted`,
            color: '#8a8a8a',
            icon: Layers,
          },
          {
            label: 'Twin Fidelity',
            value: topology?.fidelity ?? '99.1%',
            sub: 'config accuracy vs live',
            color: '#c9b787',
            icon: CheckCircle,
          },
          {
            label: 'Total Vulns Found',
            value: totalVulns || '—',
            sub: 'across all twin nodes',
            color: '#f5f5f5',
            icon: AlertTriangle,
          },
          {
            label: 'Scenarios Run Today',
            value: scenarios.filter((s) => s.status !== 'queued').length || '—',
            sub: `${scenarios.filter((s) => s.criticalFindings > 0).length} with critical findings`,
            color: '#8a8a8a',
            icon: Target,
          },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-2xl font-bold text-white">
                {topologyQuery.isLoading ? (
                  <span className="text-zinc-500 text-lg">loading…</span>
                ) : (
                  m.value
                )}
              </div>
              <div className="text-xs text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Infrastructure Map */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Twin Infrastructure Map
          </h2>
          {topologyQuery.isLoading ? (
            <div className="text-xs text-zinc-500 text-center py-8">Loading topology…</div>
          ) : (
            <div className="space-y-1.5">
              {nodes.map((node: TwinNode) => {
                const Icon = typeIcon[node.type] ?? Server;
                return (
                  <div key={node.id} className="rounded-xl border border-white/8 bg-white/3 p-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                        style={{ background: `${typeColor[node.type] ?? '#888'}20` }}
                      >
                        <Icon
                          className="w-3.5 h-3.5"
                          style={{ color: typeColor[node.type] ?? '#888' }}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-white">{node.name}</span>
                          <span className="text-[10px] text-zinc-500 font-mono">{node.ip}</span>
                          <span
                            className={cn(
                              'text-[10px] px-1 py-0.5 rounded',
                              'text-zinc-500 bg-zinc-500/10',
                            )}
                          >
                            T{node.criticalityTier}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 mt-0.5 text-[10px]">
                          <span className="text-zinc-500">
                            Sync: {node.lastSyncLabel ?? node.lastSync}
                          </span>
                          {node.vulnerabilities > 0 && (
                            <span className="text-[#f5f5f5]">{node.vulnerabilities} vulns</span>
                          )}
                        </div>
                      </div>
                      <span
                        className={cn(
                          'text-[10px] px-1.5 py-0.5 rounded border capitalize shrink-0',
                          syncColor[node.syncState] ?? 'text-zinc-400',
                        )}
                      >
                        {node.syncState}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Red Team Scenarios */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Red Team Scenarios
            </h2>
            <button
              onClick={() =>
                toast.success(`Scenario library opened — ${metricDisplay(AEGIS_MITRE_COVERAGE)}`)
              }
              className="text-[10px] text-[#8a8a8a] hover:text-[#8a8a8a]"
            >
              Browse Library →
            </button>
          </div>
          {scenariosQuery.isLoading ? (
            <div className="text-xs text-zinc-500 text-center py-8">Loading scenarios…</div>
          ) : (
            <div className="space-y-2">
              {scenarios.map((scenario: TwinScenario) => (
                <div
                  key={scenario.id}
                  className={cn(
                    'rounded-xl border p-3',
                    scenario.status === 'running'
                      ? 'border-[#c9b787]/30 bg-[#c9b787]/5'
                      : 'border-white/8 bg-white/3',
                  )}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="text-xs font-medium text-white">{scenario.name}</div>
                      <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                        {scenario.technique}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={cn(
                          'text-[10px] font-medium capitalize',
                          scenarioStatusColor[scenario.status] ?? 'text-zinc-400',
                        )}
                      >
                        {scenario.status === 'running' ? '⟳ Running' : scenario.status}
                      </span>
                      {scenario.status === 'queued' && (
                        <button
                          onClick={() => runScenarioMutation.mutate(scenario.id)}
                          disabled={runScenarioMutation.isPending}
                          className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#8a8a8a]/15 border border-[#8a8a8a]/30 text-[#8a8a8a] text-[10px] hover:bg-[#8a8a8a]/25"
                        >
                          <Play className="w-2.5 h-2.5" /> Run
                        </button>
                      )}
                    </div>
                  </div>
                  {scenario.status === 'running' && (
                    <div className="mb-2">
                      <div className="h-1.5 rounded-full bg-white/8">
                        <div
                          className="h-full rounded-full bg-[#c9b787]/60 transition-all"
                          style={{ width: `${scenario.progress}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-0.5">
                        {scenario.progress}% complete
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-4 text-[10px] text-zinc-500">
                    <span>{scenario.duration}</span>
                    {scenario.findings > 0 && <span>{scenario.findings} findings</span>}
                    {scenario.criticalFindings > 0 && (
                      <span className="text-[#f5f5f5]">{scenario.criticalFindings} critical</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Attack Surface Heatmap Summary */}
          {attackSurface.length > 0 && (
            <div className="rounded-xl border border-[#8a8a8a]/20 bg-[#8a8a8a]/5 p-4 mt-3">
              <div className="text-xs font-semibold text-[#8a8a8a] mb-3">
                Attack Surface Heatmap (Twin Analysis)
              </div>
              <div className="space-y-2">
                {attackSurface.map((item: AttackSurfaceItem) => {
                  const color =
                    item.risk >= 70 ? '#f5f5f5' : item.risk >= 55 ? '#c9b787' : '#c9b787';
                  return (
                    <div key={item.area}>
                      <div className="flex items-center justify-between text-[10px] mb-1">
                        <span className="text-zinc-400">{item.area}</span>
                        <span style={{ color }}>{item.risk}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/5">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${item.risk}%`, background: `${color}80` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
